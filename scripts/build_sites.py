"""🌐 지구본 탭의 사이트 목록을 만든다 → data/sites/sites.json

네트워크 없이 저장소 안의 원장만 읽는다(CI에서도 그대로 실행).
  - LNG 터미널: manual/gem/lng_terminals.xlsx (GEM GGIT, 유닛 → 터미널로 묶음, 좌표는 GEM 원본)
  - ESS 공장: manual/ess_factories.json · manual/ess_cell_factories.json
    좌표는 원장에 없어서 manual/site_coords.json(행 id → 위도·경도·정확도)에서 붙인다.
  - 내가 등록한 사이트: manual/sites.json (좌표를 직접 적는다)
좌표가 없는 원장 행은 지도에 그리지 않고 missing_coords로 남긴다(추정해서 채우지 않음).
"""
import datetime as dt
import json
import re
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GEM_LNG = ROOT / 'manual/gem/lng_terminals.xlsx'
GEM_REL = 'Global Energy Monitor, Global Gas Infrastructure Tracker - LNG Terminals, September 2025 release'
ESS_LEDGERS = [ROOT / 'manual/ess_factories.json', ROOT / 'manual/ess_cell_factories.json']
COORDS = ROOT / 'manual/site_coords.json'
USER_SITES = ROOT / 'manual/sites.json'
OUT = ROOT / 'data/sites/sites.json'
DC_FACILITIES = ROOT / 'data/datacenter/dc_facilities.json'
DC_COORDS = ROOT / 'data/sites/dc_coords.json'
DC_SOURCE_URL = 'https://blcm.go.kr/stat/customizedStatic/CustomizedStaticSupplyList.do'

STATUS_LABEL = {'operating': '가동', 'construction': '건설 중', 'planned': '계획·제안', 'inactive': '중단·취소'}
GEM_STATUS = {'operating': 'operating', 'construction': 'construction', 'proposed': 'planned',
              'shelved': 'inactive', 'mothballed': 'inactive', 'idled': 'inactive', 'cancelled': 'inactive', 'retired': 'inactive'}
GEM_STATUS_KO = {'operating': '가동', 'construction': '건설 중', 'proposed': '제안', 'shelved': '보류',
                 'mothballed': '휴지', 'idled': '유휴', 'cancelled': '취소', 'retired': '폐쇄'}
STATUS_RANK = ['operating', 'construction', 'planned', 'inactive']
ESS_STATUS = {'operating': 'operating', 'construction': 'construction', 'planned': 'planned', 'unconfirmed': 'planned'}
STAGE_KO = {'system': 'ESS 완제품 조립', 'component': 'ESS 부품', 'cell': '배터리 셀'}
ACCURACY_KO = {'exact': '시설 좌표', 'approximate': '근사 좌표', 'facility': '시설 좌표', 'town': '읍·면·동 중심',
               'district': '구·지구 중심', 'city': '도시 중심', 'county': '군 중심', 'province': '성·도 중심', 'state': '주 중심'}

LAYERS = [
    {'id': 'lng_export', 'name': 'LNG 수출(액화) 터미널', 'group': 'LNG', 'source': GEM_REL,
     'source_url': 'https://globalenergymonitor.org/projects/global-gas-infrastructure-tracker/'},
    {'id': 'lng_import', 'name': 'LNG 수입(재기화) 터미널', 'group': 'LNG', 'source': GEM_REL,
     'source_url': 'https://globalenergymonitor.org/projects/global-gas-infrastructure-tracker/'},
    {'id': 'ess_system', 'name': 'ESS 완제품·부품 공장', 'group': 'ESS',
     'source': 'ESS 탭 공장 원장(manual/ess_factories.json) · 좌표 OpenStreetMap Nominatim'},
    {'id': 'ess_cell', 'name': 'ESS 배터리 셀 공장', 'group': 'ESS',
     'source': 'ESS 탭 셀 공장 원장(manual/ess_cell_factories.json) · 좌표 OpenStreetMap Nominatim'},
    {'id': 'dc_kr', 'name': '데이터센터 · 한국', 'group': '데이터센터',
     'source': '데이터센터 탭 국내 원장(기준 정리자료 + 국토교통부 건축통계) · 좌표 OpenStreetMap Nominatim', 'source_url': DC_SOURCE_URL},
    {'id': 'dc_kr_candidate', 'name': '데이터센터 · 한국 후보(미확인)', 'group': '데이터센터',
     'source': '데이터센터 탭 국내 원장(기준 정리자료 + 국토교통부 건축통계) · 좌표 OpenStreetMap Nominatim', 'source_url': DC_SOURCE_URL},
    {'id': 'user', 'name': '내가 등록한 사이트', 'group': '내 사이트', 'source': 'manual/sites.json'},
]


def num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def year(v):
    v = num(v)
    return int(v) if v is not None else None


def text(v):
    v = num(v)
    return str(v).strip() if v is not None and str(v).strip() else None


def lng_terminals():
    df = pd.read_excel(GEM_LNG, sheet_name='LNG Terminals')
    df = df[df['Latitude'].notna() & df['Longitude'].notna()]
    df = df[df['FacilityType'].str.lower().isin(['export', 'import'])]
    sites = []
    for (name, kind), units in df.groupby(['TerminalName', df['FacilityType'].str.lower()], sort=True):
        first = units.iloc[0]
        statuses = units['Status'].str.lower()
        norm = [GEM_STATUS.get(s, 'inactive') for s in statuses]
        status = min(norm, key=STATUS_RANK.index)
        cap = {}
        for s, c in zip(statuses, units['CapacityinMtpa']):
            if num(c) is not None:
                cap[s] = round(cap.get(s, 0) + float(c), 2)
        starts = [y for y in units['ActualStartYear'].map(year) if y]
        planned = [y for y in units['LatestPlannedStartYear'].map(year) if y]
        unit_counts = statuses.value_counts()
        detail = [
            ['유닛', ' · '.join(f"{GEM_STATUS_KO.get(s, s)} {n}" for s, n in unit_counts.items())],
            ['용량(Mtpa)', ' · '.join(f"{GEM_STATUS_KO.get(s, s)} {v:g}" for s, v in cap.items()) or None],
            ['가동 시작', str(min(starts)) if starts else None],
            ['계획 시작(최신)', str(max(planned)) if planned and status != 'operating' else None],
            ['소유', text(first['Owner'])],
            ['모회사', text(first['Parent'])],
            ['위치', ', '.join(x for x in [text(first['Location']), text(first['State/Province'])] if x) or None],
        ]
        sites.append({
            'id': f"{kind}:{first['ProjectID']}",
            'layer': 'lng_' + kind,
            'name': name,
            'company': text(first['Parent']) or text(first['Owner']),
            'country': text(first['Country/Area']),
            'lat': round(float(first['Latitude']), 4),
            'lon': round(float(first['Longitude']), 4),
            'accuracy': text(first['Accuracy']) or 'approximate',
            'status': status,
            'status_detail': ' · '.join(f"{GEM_STATUS_KO.get(s, s)} {n}" for s, n in unit_counts.items()),
            'size': round(sum(v for s, v in cap.items() if GEM_STATUS.get(s) in ('operating', 'construction')), 2) or None,
            'size_unit': 'Mtpa',
            'detail': [d for d in detail if d[1]],
            'url': text(first['Wiki']),
            'source': 'GEM',
        })
    return sites


def capacity_text(c):
    if not c:
        return None
    q = {'greater_than': '>', 'approx': '약 ', 'up_to': '최대 '}.get(c.get('qualifier'), '')
    return f"{q}{c['value']:g} {c.get('unit', 'GWh/year')} ({c.get('basis', '')}, {c.get('date', '')})".replace(' ()', '')


def ess_factories(coords, missing):
    sites = []
    for path in ESS_LEDGERS:
        ledger = json.loads(path.read_text(encoding='utf-8'))
        sources = ledger.get('sources', {})
        for row in ledger['rows']:
            geo = coords.get(row['id'])
            if not geo:
                missing.append({'ledger': path.name, 'id': row['id'], 'location': row.get('location')})
                continue
            layer = 'ess_cell' if row.get('stage') == 'cell' else 'ess_system'
            src_ids = row.get('status_sources') or []
            src = sources.get(src_ids[0]) if src_ids else None
            installed = row.get('installed_capacity') or {}
            detail = [
                ['제품', row.get('product')],
                ['단계', STAGE_KO.get(row.get('stage'), row.get('stage'))],
                ['상태', f"{row.get('status_label', '')} ({row.get('status_date', '')})".replace(' ()', '')],
                ['설치 능력', capacity_text(row.get('installed_capacity'))],
                ['설계·계획 능력', capacity_text(row.get('design_capacity'))],
                ['소유·운영', row.get('ownership')],
                ['위치(원장)', row.get('location')],
                ['좌표', f"{ACCURACY_KO.get(geo['accuracy'], geo['accuracy'])} · OSM 검색어 \"{geo['query']}\""],
            ]
            sites.append({
                'id': row['id'], 'layer': layer, 'name': row.get('factory'), 'company': row.get('company_name'),
                'country': (row.get('location') or '').split(' ')[0] or None,
                'lat': geo['lat'], 'lon': geo['lon'], 'accuracy': geo['accuracy'],
                'status': ESS_STATUS.get(row.get('status'), 'planned'), 'status_detail': row.get('status_label'),
                'size': installed.get('value') if installed.get('unit', 'GWh/year') == 'GWh/year' else None,
                'size_unit': 'GWh/년',
                'detail': [d for d in detail if d[1]],
                'url': src['url'] if src else None, 'url_label': src['label'] if src else None,
                'source': 'ESS 원장',
            })
    return sites


def dc_status(dates, today):
    """준공 → 가동, 착공 → 건설 중, 허가만 → 계획. 예정일·미확인 날짜는 단계로 치지 않는다."""
    def happened(step):
        date = dates.get(step) or {}
        return date.get('kind') == 'confirmed' and date.get('date') and date['date'] <= today
    completion = dates.get('completion') or {}
    done_without_date = completion.get('kind') == 'uncertain' and (
        '완료' in (completion.get('text') or '') or (completion.get('year') or 9999) < int(today[:4]))
    if happened('completion') or done_without_date or happened('alteration'):
        return 'operating'
    return 'construction' if happened('start') else 'planned'


def data_centers(today, missing):
    records = json.loads(DC_FACILITIES.read_text(encoding='utf-8'))['records']
    coords = json.loads(DC_COORDS.read_text(encoding='utf-8'))['coords'] if DC_COORDS.exists() else {}
    sites, seen = [], set()
    for row in records:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        key = row.get('address_key') or re.sub(r'[\s\xa0]+', '', row['location'])
        geo = coords.get(key)
        if not geo:
            missing.append({'ledger': DC_FACILITIES.name, 'id': row['id'], 'location': row.get('location')})
            continue
        dates = row.get('dates') or {}
        date_text = lambda step: (dates.get(step) or {}).get('date') or (dates.get(step) or {}).get('text') or None
        status = dc_status(dates, today)
        detail = [
            ['위치(원장)', re.sub(r'[\s\xa0]+', ' ', row['location'])],
            ['구분', row.get('type')],
            ['허가', date_text('permit')],
            ['착공', date_text('start')],
            ['준공', date_text('completion')],
            ['대수선·용도변경', date_text('alteration')],
            ['연면적', f"{row['area']:,.0f} ㎡" if row.get('area') else None],
            ['수전용량', f"{row['capacity']:g} MW" if row.get('capacity') else None],
            ['IT 부하', row.get('it_load')],
            ['임차', row.get('tenant')],
            ['시공', row.get('contractor')],
            ['분류 근거', row.get('classification_reason')],
            ['좌표', f"{ACCURACY_KO.get(geo['accuracy'], geo['accuracy'])} · OSM 검색어 \"{geo['query']}\""],
        ]
        sources = row.get('sources') or []
        sites.append({
            'id': row['id'], 'layer': 'dc_kr' if row.get('classification') == 'confirmed' else 'dc_kr_candidate',
            'name': row['name'], 'company': row.get('owner') or None, 'country': '한국',
            'lat': geo['lat'], 'lon': geo['lon'], 'accuracy': geo['accuracy'], 'status': status,
            'size': row.get('capacity') or None, 'size_unit': 'MW',
            'detail': [d for d in detail if d[1]],
            'url': row.get('url') or (sources[0].get('url') if sources else None) or DC_SOURCE_URL,
            'url_label': '원문 보기' if row.get('url') else '국토교통부 건축통계',
            'source': '데이터센터 원장',
        })
    return sites


def user_sites():
    data = json.loads(USER_SITES.read_text(encoding='utf-8'))
    sites = []
    for row in data['sites']:
        lat, lon = float(row['lat']), float(row['lon'])
        detail = [[k, v] for k, v in (row.get('detail') or {}).items()]
        if row.get('note'):
            detail.append(['메모', row['note']])
        sites.append({
            'id': 'user:' + row['id'], 'layer': 'user', 'name': row['name'], 'company': row.get('company'),
            'country': row.get('country'), 'lat': lat, 'lon': lon, 'accuracy': row.get('accuracy', 'facility'),
            'status': row.get('status', 'operating'), 'status_detail': row.get('status_label'),
            'category': row.get('category'), 'detail': detail, 'url': row.get('url'), 'source': '내 등록',
        })
    return sites, data.get('categories', {})


def build():
    coords = json.loads(COORDS.read_text(encoding='utf-8'))['coords']
    missing = []
    mine, categories = user_sites()
    today = dt.date.today().isoformat()
    sites = lng_terminals() + ess_factories(coords, missing) + data_centers(today, missing) + mine
    counts = {layer['id']: sum(s['layer'] == layer['id'] for s in sites) for layer in LAYERS}
    return {
        'id': 'sites', 'name': '사이트 지도', 'updated': today,
        'note': '좌표 정확도는 사이트마다 다르다(accuracy). ESS 공장·데이터센터는 원장 주소를 지역 단위로 찾은 근사 위치가 많다.',
        'status_labels': STATUS_LABEL, 'accuracy_labels': ACCURACY_KO, 'layers': LAYERS, 'counts': counts,
        'user_categories': categories, 'missing_coords': missing, 'sites': sites,
    }


def main():
    doc = build()
    # 원장이 그대로면 집계일도 그대로 둬서 매일 CI가 같은 파일을 다시 커밋하지 않게 한다.
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding='utf-8'))
        if {k: v for k, v in old.items() if k != 'updated'} == {k: v for k, v in doc.items() if k != 'updated'}:
            doc['updated'] = old['updated']
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    print('sites', len(doc['sites']), doc['counts'], 'missing coords', len(doc['missing_coords']))


if __name__ == '__main__':
    main()

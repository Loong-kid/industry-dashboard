"""KOMIS/USGS annual country production and reserve snapshots, in metric tons.

The map's numeric quantities are already expressed in tons. Its cdVal is the
original USGS chapter unit, not a multiplier to apply to these quantities.
Zero/missing fields do not retain USGS disclosure markers and are omitted.
"""
import json
import math
import re
from pathlib import Path

import requests

from fetch_mineral_prices import korea_today, request

ROOT = Path(__file__).resolve().parent.parent
PAGE = 'https://www.komis.or.kr/Komis/MnrlMap/MnrlMap'
BASE = 'https://www.komis.or.kr'
API = BASE + '/Komis/MnrlMap/MapMnrl/ajax/'
USGS = 'https://pubs.usgs.gov/periodicals/mcs2026/mcs2026.pdf'
OUT = ROOT / 'data/commodities/comm_mineral_supply.json'
CACHE = ROOT / 'data/_mineral_supply/komis.json'
REGISTRY = ROOT / 'scripts/mineral_supply_registry.json'
UNIT_CODES = {'WT001': 'kg', 'WT002': 'ton', 'WT003': 'k ton'}


def parse_rows(rows, start, end):
    if not isinstance(rows, list):
        raise ValueError('Missing country rows')
    countries, seen, units, omitted = {}, {}, set(), 0
    for row in rows:
        year = str(row.get('crtrYr', ''))
        code, name = row.get('ntnEngCd'), row.get('ntnKornNm')
        if not re.fullmatch(r'\d{4}', year) or not start <= int(year) <= end:
            raise ValueError('Unexpected observation year')
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z]{2}', code) or not name:
            raise ValueError('Unexpected country identity')
        if UNIT_CODES.get(row.get('massUnitCd')) != row.get('cdVal'):
            raise ValueError('Unreviewed source unit')
        units.add(row['cdVal'])
        values = []
        for field in ('prdctnQuty', 'burudgQuty'):
            raw = row.get(field)
            if raw in (None, '', '-', 'NA', 'W'):
                values.append(None)
                omitted += 1
                continue
            value = float(str(raw).replace(',', ''))
            if not math.isfinite(value) or value < 0:
                raise ValueError('Invalid country quantity')
            # A zero can mean unavailable/not separately reported in this API.
            values.append(value if value > 0 else None)
            omitted += value == 0
        key = (year, code)
        if key in seen:
            raise ValueError('Duplicate country/year')
        seen[key] = values
        country = countries.setdefault(code, {'name': name, 'production': [], 'reserves': []})
        if country['name'] != name:
            raise ValueError('Country name changed within response')
        for field, value in zip(('production', 'reserves'), values):
            if value is not None:
                country[field].append([year + '-12-31', value])
    for country in countries.values():
        for field in ('production', 'reserves'):
            country[field].sort()
    return countries, sorted(units), omitted


def merge_history(countries, previous, raw_rows):
    """Revisions (including withdrawn values) replace returned country/years.

    Older years outside the returned window remain. A missing previously
    published row is an error, rather than silently erasing or retaining it.
    """
    keys = {(str(r['crtrYr']) + '-12-31', r['ntnEngCd']) for r in raw_rows}
    returned_years = {date for date, _ in keys}
    for code, old in previous.items():
        current = countries.setdefault(code, {'name': old['name'], 'production': [], 'reserves': []})
        if current['name'] != old['name']:
            raise ValueError('Country identity changed')
        for field in ('production', 'reserves'):
            for date, _ in old[field]:
                if date in returned_years and (date, code) not in keys:
                    raise ValueError('Previously published country/year disappeared')
            preserved = [[date, value] for date, value in old[field] if date not in returned_years]
            current[field] = sorted(preserved + current[field])
            if old[field] and current[field] and current[field][-1][0] < old[field][-1][0]:
                raise ValueError('Latest country observation regressed')
    return countries


def atomic_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False,
                                    separators=(',', ':')), encoding='utf-8')
    temporary.replace(path)


def collect():
    today = korea_today()
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    session = requests.Session()
    session.headers.update({'User-Agent': 'IndustryDashboard/1.0 (public mineral statistics)',
                            'Referer': PAGE, 'X-Requested-With': 'XMLHttpRequest'})
    def post(url, data):
        payload = request(session, 'POST', url, data=data).json()
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
            raise ValueError('Missing KOMIS JSON data')
        return payload['data']
    minerals = post(BASE + '/ajax/komiscommon/getListSearchMnrl', {'stngCd': 'MNRL_MNRL'})
    discovered = {r['mnrkndUnqCd']: r['mnrkndKornNm'] for r in minerals}
    if len(discovered) != len(minerals) or discovered != registry['minerals']:
        raise ValueError('KOMIS mineral list changed; review names and production bases')
    years = sorted({int(r['crtrYr']) for r in post(API + 'getMapMnrlCrtrYr', {})})
    if not years or years[-1] >= today.year or years != list(range(years[0], years[-1] + 1)):
        raise ValueError('Unexpected published year coverage')
    old = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'minerals': []}
    old_minerals = {r['id']: r for r in old['minerals']}
    collected, raw_cache = [], []
    for entry in registry['entries']:
        params = {'srchMnrkndUnqCd': entry['code'], 'srchMnrkndSeCd': entry['variant'],
                  'srchDateS': str(years[0]), 'srchDateE': str(years[-1]),
                  'selectedTab': 'prdctn', 'srchNtnEngCd': ''}
        rows = post(API + 'getListMapMnrlChartData', params)
        countries, units, omitted = parse_rows(rows, years[0], years[-1])
        previous = old_minerals.get(entry['id'], {})
        if previous.get('available') and not rows:
            raise ValueError(f"{entry['id']}: previously available mineral is empty")
        countries = merge_history(countries, previous.get('countries', {}), rows)
        dates = [point[0] for country in countries.values()
                 for field in ('production', 'reserves') for point in country[field]]
        mineral = {**entry, 'countries': countries, 'available': bool(dates),
                   'updated': max(dates) if dates else None, 'source_units': units,
                   'omitted_fields': omitted}
        collected.append(mineral)
        raw_cache.append({'id': entry['id'], 'parameters': params, 'rows': rows})
        print(f"{entry['id']}: {len(countries)} countries, latest {mineral['updated']}")
    if not any(r['available'] for r in collected):
        raise ValueError('No available mineral statistics')
    updated = max(r['updated'] for r in collected if r['available'])
    if old.get('updated') and updated < old['updated']:
        raise ValueError('Latest published year regressed')
    doc = {'id': 'comm_mineral_supply', 'name': '세계 국가별 광물 생산량 / 매장량',
           'unit': '톤', 'frequency': 'yearly', 'fetched': today.isoformat(),
           'updated': updated, 'source': 'KOMIS · USGS Mineral Commodity Summaries',
           'source_url': PAGE, 'methodology_url': USGS,
           'years': years, 'default_mineral': 'MNRL0008', 'minerals': collected,
           'available_count': sum(r['available'] for r in collected),
           'description': '광종별 국가 생산량과 공표 매장량의 연간 추이. 생산량에는 추정치가 포함되며, 매장량은 공표시점의 경제적 채굴 가능량 추정입니다.',
           'note': '모든 수치는 미터톤입니다. 광종마다 생산품·함유량 기준이 다르므로 광종끼리 더하지 않습니다. 공개 국가 합계는 기타 국가·비공개 물량이 빠져 세계 전체와 다를 수 있습니다. 미공개·0 표기는 그래프에서 제외하며 빈 구간을 연결하지 않습니다.'}
    # Validate all minerals before replacing either output. A failed source
    # preserves the published dashboard and leaves the run visibly failed.
    atomic_json(CACHE, {'fetched': today.isoformat(), 'source_url': PAGE, 'minerals': raw_cache})
    atomic_json(OUT, doc)
    print(f"Published {doc['available_count']} mineral/product selections")


if __name__ == '__main__':
    collect()

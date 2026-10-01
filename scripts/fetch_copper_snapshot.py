"""Accumulate free, CC BY 4.0 copper snapshots from The Vault Report.

No paid endpoints, inferred historical observations, or direct CME/LME scraping.
The provider's catalog and response explicitly identify this free API and licence.
"""
import datetime as dt
import json
import math
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/commodities'
URL = 'https://thevaultreport.com/api/v1/snapshot'
SHORT_TON_TO_TONNE = 0.90718474
TOTAL = '총재고'
REGISTERED = '등록재고 (Registered)'
ELIGIBLE = '적격재고 (Eligible · 계산)'
LME = 'LME 구리 재고'


def read_signal(payload, key, unit, today):
    rows = [r for r in payload['signals'] if r.get('key') == key]
    if len(rows) != 1:
        raise ValueError(f'Missing or duplicate signal: {key}')
    row = rows[0]
    if row['unit'] != unit:
        raise ValueError(f'Unexpected unit for {key}')
    value = row['value']
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'Invalid value for {key}')
    date = dt.date.fromisoformat(row['as_of'])
    if date > today or row['as_of'] != date.isoformat():
        raise ValueError(f'Invalid/future observation date for {key}')
    return row


def build_documents(payload, today):
    if payload.get('schema_version') != 1 or payload.get('license') != 'CC BY 4.0':
        raise ValueError('Unexpected snapshot schema or licence')
    total = read_signal(payload, 'comex_copper_total', 'short tons', today)
    registered = read_signal(payload, 'comex_registered_copper', 'short tons', today)
    lme = read_signal(payload, 'lme_copper', 'mt', today)
    if total['as_of'] != registered['as_of'] or registered['value'] > total['value']:
        raise ValueError('COMEX components have different dates or exceed total')
    common = dict(unit='톤', frequency='daily', fetched=today.isoformat(), data_stale_days=10,
                  source='The Vault Report · CC BY 4.0', source_url='https://thevaultreport.com',
                  source_api=URL, license='CC BY 4.0', license_url='https://creativecommons.org/licenses/by/4.0/',
                  provider_generated_at=payload.get('generated_at'), snapshot_history=True)
    def points(value):
        return [[total['as_of'], round(value * SHORT_TON_TO_TONNE, 3)]]
    comex = dict(common, id='comm_copper_comex_inventory', name='COMEX 구리 재고',
                 updated=total['as_of'], default_series=[TOTAL],
                 series={TOTAL: points(total['value']), REGISTERED: points(registered['value']),
                         ELIGIBLE: points(total['value']-registered['value'])},
                 source_original='CME Group COMEX warehouse stocks',
                 source_values={'unit': 'short tons', 'total': total['value'], 'registered': registered['value']},
                 description='미국 COMEX 총재고와 등록재고를 비교합니다. 등록재고는 창고증권이 발행된 물량이고, 적격재고는 총재고에서 등록재고를 뺀 값입니다.',
                 note='총재고 = 등록재고 + 적격재고입니다. 1 short ton = 0.90718474톤으로 환산했습니다. 지역 간 이동·관세·등록 상태 변화도 재고에 영향을 줍니다. CME 직접 수집이 아닌 제3자 공개 API 자료입니다.')
    london = dict(common, id='comm_copper_lme_inventory', name=LME, updated=lme['as_of'],
                  series={LME: [[lme['as_of'], lme['value']]]}, source_original='LME warehouse stocks',
                  description='LME 거래소 창고의 구리 재고입니다. SHFE·COMEX와 서로 다른 지역의 재고 흐름을 확인하는 보조 지표입니다.',
                  note='LME 직접 수집이 아닌 제3자 공개 API 자료입니다. 취소 창고증권·실제 출고 예정량을 별도로 보여주지 않으며, 총재고 감소만으로 소비 증가를 단정하지 않습니다.')
    return [comex, london]


def merge_history(old, new):
    if old and (old.get('unit') != new['unit'] or set(old['series']) != set(new['series'])):
        raise ValueError('Existing history schema changed')
    if old and new['updated'] < old['updated']:
        raise ValueError('Provider snapshot regressed; existing data preserved')
    for key in ('history_source', 'history_source_url', 'history_csv', 'history_note'):
        if key in old:
            new[key] = old[key]
    for name, points in new['series'].items():
        values = dict(old.get('series', {}).get(name, []))
        values.update(points)
        new['series'][name] = sorted(values.items())
    new['history_started'] = min(p[0] for s in new['series'].values() for p in s)
    return new


def run():
    response = requests.get(URL, timeout=(5, 25))
    response.raise_for_status()
    today = dt.datetime.now(dt.timezone.utc).date()
    docs = build_documents(response.json(), today)
    prepared = []
    for doc in docs:
        path = OUT / (doc['id']+'.json')
        old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        prepared.append((path, merge_history(old, doc)))
    OUT.mkdir(parents=True, exist_ok=True)
    for path, doc in prepared:
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        temp.replace(path)
        print(f"{doc['id']}: {doc['updated']}, {len(next(iter(doc['series'].values())))} observations")


if __name__ == '__main__':
    run()

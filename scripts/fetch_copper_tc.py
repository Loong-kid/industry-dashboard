"""Accumulate the public SMM weekly concentrate TC, without gated history.

Keep negative TCs, original dates, and sources. Never invent RCs from TCs.
"""
import copy
import datetime as dt
import json
import re

import requests
from bs4 import BeautifulSoup

from derive_copper_market import ROOT, OUT, check_date, check_number, save

PAGE = 'https://www-old.metal.com/Copper'
PRODUCT_PAGE = 'https://www-old.metal.com/Copper/201910240001'
PRODUCT = 'SMM Copper Concentrate Index (Weekly)'
NAME = '정광 TC · SMM 중국 수입 주간 지수'
ID = 'comm_copper_concentrate_tc'


def parse_public_row(text, today):
    soup = BeautifulSoup(text, 'html.parser')
    links = [a for a in soup.find_all('a', href=True) if a['href'] == '/Copper/201910240001']
    if len(links) != 1:
        raise ValueError('Missing or duplicate public weekly TC row')
    row = links[0].parent
    cells = [c.get_text(' ', strip=True) for c in row.find_all(recursive=False)]
    if len(cells) != 5 or cells[0] != PRODUCT + ' ($/dmt)':
        raise ValueError('TC identity, unit or columns changed')
    number = r'-?\d+(?:\.\d+)?'
    match = re.fullmatch(rf'({number})-({number})', cells[1])
    if not match or not re.fullmatch(number, cells[2]):
        raise ValueError('TC price is unavailable or malformed')
    low, high, value = float(match[1]), float(match[2]), float(cells[2])
    check_number(value)
    if not low <= value <= high or abs((low+high)/2-value) > .001:
        raise ValueError('TC average/range mismatch')
    date = dt.datetime.strptime(cells[4], '%b %d, %Y').date().isoformat()
    check_date(date, today)
    return dict(date=date, value=value, low=low, high=high, unit='USD/dmt', provider='SMM',
        product=PRODUCT, source_url=PRODUCT_PAGE, checked=today,
        locator='공개 Copper 가격 목록 · Weekly 지수의 Avg. 및 Date · 로그인 이력은 수집하지 않음')


def merge(old, seeds, record, today):
    if old and (old['id'] != ID or old['unit'] != 'USD/건조정광톤'):
        raise ValueError('Existing TC schema changed')
    if old and record['date'] < old['updated']:
        raise ValueError('TC snapshot regressed')
    values = {r['date']:copy.deepcopy(r) for r in old.get('source_records', [])}
    for row in [*seeds, record]:
        check_date(row['date'], today)
        check_number(row['value'])
        if row['unit'] != 'USD/dmt' or row['provider'] != 'SMM' or row['product'] != PRODUCT or not row['source_url'].startswith('https://'):
            raise ValueError('Wrong TC unit, product, provider or source')
        existing = values.get(row['date'])
        if existing and existing['value'] != row['value']:
            raise ValueError('TC revision requires review; saved values preserved')
        values[row['date']] = row
    records = [values[key] for key in sorted(values)]
    return dict(id=ID, name=NAME, unit='USD/건조정광톤', frequency='weekly',
        updated=records[-1]['date'], fetched=today, data_stale_days=21,
        source='SMM 공식 공개 주간 TC · 공개 기사 확인값 포함', source_url=PRODUCT_PAGE,
        series={NAME:[[r['date'],r['value']] for r in records]}, source_records=records,
        reference_value=0, reference_label='TC 0', highlight_gaps=True, change_mode='none',
        snapshot_history=True, history_started=records[0]['date'],
        history_note='공개 기사에서 확인한 2026-08-28·09-04와 수집 이후 공개 주간 값을 누적합니다. 전체 과거 이력은 미확보이며 빈 주를 생성하지 않습니다. 기사 공표 당시 값과 이후 정정 빈티지가 다를 수 있습니다.',
        description='TC(Treatment Charge)는 광산 정광을 제련하는 대가입니다. 단위는 구리 금속 1톤이 아닌 건조 정광 1톤(USD/dmt)입니다. SMM의 중국 제련소 수입 현물 주간 지수이며 연간 장기계약 TC와 구분합니다.',
        note='TC 하락은 정광 공급이 제련능력 대비 타이트해졌음을 시사합니다. 음수이면 같은 지급대상 금속가치 기준에서 TC 공제액이 가산액으로 바뀝니다. 구리 가격 자체가 음수이거나 모든 제련소가 적자라는 뜻은 아닙니다. RC는 지급대상 구리의 cents/lb이며 별도 계약값입니다. TC에서 RC를 자동 환산하지 않습니다. 매일 공개 가격표만 확인하고 원래 지수 날짜를 보존합니다. 7일 초과 공백은 점선이며, 장기 이력/API는 SMM 회원 서비스입니다.')


def run(today=None):
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    path = OUT / (ID+'.json')
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    seeds = json.loads((ROOT/'manual/copper_market_sources.json').read_text(encoding='utf-8'))['tc_history']
    try:
        response = requests.get(PAGE, timeout=(8, 25))
        response.raise_for_status()
        response.encoding = 'utf-8'
        doc = merge(old, seeds, parse_public_row(response.text, today), today)
        doc['collection_status'] = dict(checked=today, ok=True, message='공식 공개 가격표 확인 · 지수 기준일은 별도')
        save(doc)
        print(ID, doc['updated'], len(next(iter(doc['series'].values()))), 'observations')
    except Exception:
        if old:
            old['collection_status'] = dict(checked=today, ok=False, message='공개 TC 확인 실패 · 기존 관측값 보존')
            save(old)
        raise


if __name__ == '__main__':
    run()

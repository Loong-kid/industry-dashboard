"""Daily TGA closing balances (Treasury DTS) and overnight RRP (FRED).

Public endpoints need no API key. Re-fetch history to capture corrections;
validate each card before replacing it and preserve it when collection fails.
"""
import csv
import io
import json
import math
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'macro'
TGA_API = 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance'
TGA_URL = 'https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/operating-cash-balance'
RRP_URL = 'https://fred.stlouisfed.org/series/RRPONTSYD'
RRP_CSV = 'https://fred.stlouisfed.org/graph/fredgraph.csv'
TGA_FIELDS = {
    'Federal Reserve Account': 'close_today_bal',
    'Treasury General Account (TGA)': 'close_today_bal',
    'Treasury General Account (TGA) Closing Balance': 'open_today_bal',
}


def get(session, url, params):
    for attempt in range(3):
        try:
            response = session.get(url, params=params, timeout=(5, 30))
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def add_point(points, day, raw, today, divisor=1):
    if date.fromisoformat(day) > today:
        raise ValueError('Future observation')
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid balance')
    value = round(value / divisor, 3)
    if day in points and points[day] != value:
        raise ValueError('Conflicting observations for one day')
    points[day] = value


def parse_tga(payload, account, today):
    field = TGA_FIELDS[account]
    if payload.get('meta', {}).get('dataFormats', {}).get(field) != '$1,000,000':
        raise ValueError('Treasury amount unit changed')
    rows = payload.get('data')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Empty Treasury response')
    points = {}
    for row in rows:
        if row.get('account_type') != account:
            raise ValueError('Unexpected Treasury account')
        # After April 18, 2022 the closing-balance ROW uses open_today_bal.
        # Never substitute the opening-balance row or a null closing field.
        add_point(points, row['record_date'], row[field], today, 1000)
    return points


def collect_tga(session, today):
    points = {}
    for account in TGA_FIELDS:
        page, count, expected = 1, 0, None
        while True:
            payload = get(session, TGA_API, {
                'filter': 'account_type:eq:' + account,
                'fields': 'record_date,account_type,open_today_bal,close_today_bal',
                'sort': 'record_date', 'page[size]': 10000, 'page[number]': page,
            }).json()
            meta = payload['meta']
            if expected is None:
                expected = int(meta['total-count'])
            if int(meta['total-count']) != expected:
                raise ValueError('Treasury pagination changed during collection')
            parsed = parse_tga(payload, account, today)
            for day, value in parsed.items():
                add_point(points, day, value, today)
            count += len(payload['data'])
            if page >= int(meta['total-pages']):
                break
            page += 1
        if count != expected:
            raise ValueError('Incomplete Treasury history')
    return sorted(points.items())


def parse_rrp(text, today):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ['observation_date', 'RRPONTSYD']:
        raise ValueError('Unexpected FRED CSV schema')
    points = {}
    for row in reader:
        # FRED blanks/dots are unpublished observations, not zero usage.
        raw = (row.get('RRPONTSYD') or '').strip()
        if raw in ('', '.'):
            continue
        add_point(points, row['observation_date'], raw, today)
    if not points:
        raise ValueError('Empty FRED history')
    return sorted(points.items())


def make_doc(cid, points, today):
    if len(points) < 250:
        raise ValueError('Insufficient daily history')
    doc = dict(id=cid, unit='십억 달러', frequency='daily', updated=points[-1][0],
               fetched=today.isoformat(), zero_baseline=True, span_gaps=False,
               table_limit=10000, data_stale_days=10, compact_ticks=True)
    if cid == 'liquidity_tga':
        label = 'TGA 마감 잔고'
        doc.update(name='미 재무부 일반계정 (TGA)', source='미 재무부 · Daily Treasury Statement',
                   source_url=TGA_URL, methodology_url=TGA_URL,
                   description='TGA는 미 재무부가 연준에 보유하는 계정입니다. 재무부 일일보고서(DTS)의 하루 마감 잔고를 표시하며, 세금 수납·정부 지출·국채 조달 등에 따라 변합니다.',
                   note='연준 H.4.1의 주간 평균(WTREGEN)이나 수요일 잔고(WDTGAL)와 구분됩니다. 미국 영업일 기준이며 공표 지연·휴일 때문에 RRP와 최신 관측일이 다를 수 있습니다.',
                   basis_details=[
                       {'label': '집계', 'value': 'DTS Table I의 TGA 마감 잔고. 원단위 백만 달러를 1,000으로 나눠 십억 달러로 표시합니다.'},
                       {'label': '과거 표 형식', 'value': '2005년 이후 Federal Reserve Account와 이후 Treasury General Account (TGA) 행은 마감 필드를 사용합니다. 2022-04-18부터는 별도 TGA Closing Balance 행의 금액을 사용합니다. TT&L 계정·보충조달 계정은 포함하지 않습니다.'},
                       {'label': '기간 / 갱신', 'value': '2005년부터 제공되는 일간 이력. 매일 KST 07:30 수집 일정에서 새 공표와 과거 정정을 확인합니다. 휴일을 0으로 채우거나 주간 자료로 보간하지 않습니다.'},
                   ])
    else:
        label = '오버나이트 RRP'
        doc.update(name='연준 오버나이트 역레포 (RRP)', source='뉴욕 연은 · FRED RRPONTSYD',
                   source_url=RRP_URL, methodology_url='https://www.newyorkfed.org/markets/rrp_faq',
                   description='뉴욕 연은이 미 국채를 담보로 실시한 오버나이트 역레포의 일별 거래금액입니다. 적격 거래상대방이 연준에 자금을 맡기는 규모를 보여줍니다.',
                   note='연준 대차대조표상의 전체 역레포 잔액이나 외국 공적기관용 역레포와 구분됩니다. 보고된 0은 유지하고 휴일·미공표 값은 0으로 바꾸지 않습니다.',
                   basis_details=[
                       {'label': '시리즈 / 단위', 'value': 'FRED RRPONTSYD: 뉴욕 연은 임시 공개시장조작의 미 국채 오버나이트 RRP 일별 합계. 원단위 십억 달러, 계절조정 없음.'},
                       {'label': '장기 이력', 'value': '2003년부터의 공개 시계열을 제공합니다. 2013-09-23 이전에는 현재 ON RRP 시설 도입 전의 오버나이트 운영이 포함되어 제도적 배경이 다릅니다.'},
                       {'label': '갱신', 'value': '미국 영업일별 자료를 매일 KST 07:30 수집 일정에서 확인합니다. 최신 수치는 공표된 관측일 기준이며 실시간 값이 아닙니다.'},
                   ])
    doc.update(default_series=[label], series={label: points})
    return doc


def save(doc):
    path = OUT / (doc['id'] + '.json')
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        previous = next(iter(old['series'].values()))
        current = next(iter(doc['series'].values()))
        if doc['updated'] < old['updated'] or not {p[0] for p in previous} <= {p[0] for p in current}:
            raise ValueError('History regressed; preserving previous card')
    OUT.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temp.replace(path)


def run():
    today = datetime.now(timezone(timedelta(hours=9))).date()
    failed = False
    with requests.Session() as session:
        collectors = [('liquidity_tga', lambda: collect_tga(session, today)),
                      ('liquidity_rrp', lambda: parse_rrp(get(session, RRP_CSV, {
                          'id': 'RRPONTSYD', 'cosd': '2003-01-01', 'coed': today.isoformat(),
                      }).text, today))]
        for cid, collect in collectors:
            try:
                doc = make_doc(cid, collect(), today)
                save(doc)
                print(f'{cid}: {len(next(iter(doc["series"].values())))} observations; latest {doc["updated"]}')
            except Exception as error:
                failed = True
                print(f'ERROR {cid}: {type(error).__name__}: {error}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(run())

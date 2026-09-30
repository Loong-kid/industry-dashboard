"""SHFE public weekly copper stocks. Preserve history and never invent missing weeks.

python scripts/fetch_copper_inventory.py --backfill-weeks 156
Default: recheck the last 21 calendar days (including holiday-shortened weeks).
"""
import argparse
import datetime as dt
import json
import math
import time
from html.parser import HTMLParser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'data/commodities/comm_copper_shfe_inventory.json'
URL = 'https://www.shfe.cn/data/tradedata/future/weeklydata/{date}weeklystock.dat'
HTML_URL = 'https://www.shfe.cn/data/tradedata/future/stockdata/weeklystock_{date}/ZH/all.html'
SOURCE = 'https://www.shfe.cn/eng/reports/StatisticalData/WeeklyData/'
NAME = 'SHFE 구리 주간 재고'


class ReportTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            if self.row is not None:
                self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def validate_values(value, previous, change):
    if not all(math.isfinite(v) for v in (value, previous, change)) or min(value, previous) < 0:
        raise ValueError('Invalid inventory')
    if abs(value - previous - change) > .01:
        raise ValueError('Inventory change does not reconcile')
    return value, change


def parse_html_report(text, date):
    table = ReportTable()
    table.feed(text)
    iso = dt.datetime.strptime(date, '%Y%m%d').date().isoformat()
    if not table.rows or not table.rows[0] or not table.rows[0][0].startswith(iso + ' '):
        raise ValueError('HTML report date does not match requested date')
    headers = ['地区', '仓库', '上周库存', '本周库存', '库存增减', '可用库容量']
    subheaders = ['小计', '期货', '小计', '期货', '小计', '期货', '上周', '本周', '增减']
    active = False
    totals = []
    for index, row in enumerate(table.rows):
        if len(row) == 2 and row[1].startswith('单位'):
            active = row[0] == '铜'
            if active and (row[1] != '单位：吨' or table.rows[index-2:index] != [headers, subheaders]):
                raise ValueError('Unexpected copper unit or table columns')
        elif active and row and row[0] == '总计':
            if len(row) != 10:
                raise ValueError('Unexpected total row width')
            numbers = [float(v.replace(',', '')) for v in row[1:]]
            totals.append(validate_values(numbers[2], numbers[0], numbers[4]))
    if len(totals) != 1:
        raise ValueError('Expected exactly one copper total')
    return totals[0]


def parse_report(doc, date):
    if doc.get('report_date') != date or doc.get('o_tradingday') != date:
        raise ValueError('Report date does not match requested date')
    rows = [r for r in doc['o_cursor']
            if r.get('VARNAME', '').split('$$')[0].strip() == '铜'
            and r.get('WHABBRNAME', '').split('$$')[0].strip() == '总计']
    if len(rows) != 1 or str(rows[0]['WGHTUNIT']) != '2':
        raise ValueError('Expected one copper total in tonnes')
    row = rows[0]
    # SPOTWGHTS = actual inventory; WHSTOCKS is warehouse capacity.
    values = [float(row[k]) for k in ('SPOTWGHTS', 'PRESPOTWGHTS', 'SPOTCHANGE')]
    return validate_values(*values)


def fetch_report(session, stamp):
    # The official page uses HTML first, and legacy JSON only as a fallback.
    response = session.get(HTML_URL.format(date=stamp), timeout=(5, 15))
    if response.status_code != 404:
        response.raise_for_status()
        response.encoding = 'utf-8'
        return (*parse_html_report(response.text, stamp), HTML_URL.format(date=stamp))
    response = session.get(URL.format(date=stamp), timeout=(5, 15))
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return (*parse_report(response.json(), stamp), URL.format(date=stamp))


def run(backfill_weeks=0):
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    old = json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else {}
    history = dict(old.get('series', {}).get(NAME, []))
    changes = dict(old.get('weekly_changes', []))
    start = today - dt.timedelta(days=backfill_weeks * 7 if backfill_weeks else 21)
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'
    found, errors = 0, []
    report_url = old.get('report_url')
    day = start
    while day <= today:
        # Include holiday-shortened weeks; do not assume reports always land on Friday.
        if day.weekday() < 5 and (day.isoformat() not in history or (today-day).days <= 21):
            stamp = day.strftime('%Y%m%d')
            try:
                result = fetch_report(session, stamp)
                if result is not None:
                    value, change, url = result
                    history[day.isoformat()] = value
                    changes[day.isoformat()] = change
                    if day.isoformat() == max(history):
                        report_url = url
                    found += 1
            except (requests.RequestException, ValueError, KeyError) as exc:
                errors.append(f'{stamp}: {exc}')
            time.sleep(.05)
        day += dt.timedelta(days=1)
    if not history:
        raise RuntimeError('No valid SHFE reports; existing file left unchanged')
    if not found:
        raise RuntimeError('No recent SHFE report available; existing data and fetched date preserved')
    latest = max(history)
    doc = dict(old, id='comm_copper_shfe_inventory', name=NAME, unit='톤', frequency='weekly',
               source='SHFE 주간 재고 보고서', source_url=SOURCE,
               updated=latest, fetched=today.isoformat(), data_stale_days=14,
               series={NAME: sorted(history.items())}, weekly_changes=sorted(changes.items()),
               inventory_summary=True,
               description='상하이선물거래소 지정 창고의 구리 재고입니다. 중국 전체 재고가 아니며, 창고증권 재고를 별도로 더하지 않습니다.',
               note='재고 감소는 수요 증가뿐 아니라 창고·지역 간 이동에서도 발생합니다. 춘절 등 계절성을 함께 보세요. 누락 주차는 보간하지 않습니다.',
               report_url=report_url)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix('.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(OUTPUT)
    print(f'SHFE: {len(history)} observations, latest {latest}, {len(errors)} errors')
    if errors:
        print('\n'.join(errors[:5]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill-weeks', type=int, default=0)
    run(parser.parse_args().backfill_weeks)

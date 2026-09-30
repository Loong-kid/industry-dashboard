"""SHFE public weekly copper stocks. Preserve history and never invent missing weeks.

python scripts/fetch_copper_inventory.py --backfill-weeks 156
Default: recheck the last 21 calendar days (including holiday-shortened weeks).
"""
import argparse
import datetime as dt
import json
import math
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'data/commodities/comm_copper_shfe_inventory.json'
URL = 'https://www.shfe.cn/data/tradedata/future/weeklydata/{date}weeklystock.dat'
SOURCE = 'https://www.shfe.cn/eng/reports/StatisticalData/WeeklyData/'
NAME = 'SHFE 구리 주간 재고'


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
    if not all(math.isfinite(v) for v in values) or min(values[:2]) < 0:
        raise ValueError('Invalid inventory')
    if abs(values[0] - values[1] - values[2]) > .01:
        raise ValueError('Inventory change does not reconcile')
    return values[0], values[2]


def run(backfill_weeks=0):
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    old = json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else {}
    history = dict(old.get('series', {}).get(NAME, []))
    changes = dict(old.get('weekly_changes', []))
    start = today - dt.timedelta(days=backfill_weeks * 7 if backfill_weeks else 21)
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'
    found, errors = 0, []
    day = start
    while day <= today:
        # Backfill Friday reports; incremental runs include shortened trading weeks.
        if day.weekday() < 5 and (not backfill_weeks or day.weekday() == 4 or (today-day).days <= 21):
            stamp = day.strftime('%Y%m%d')
            try:
                response = session.get(URL.format(date=stamp), timeout=(5, 15))
                if response.status_code != 404:
                    response.raise_for_status()
                    value, change = parse_report(response.json(), stamp)
                    history[day.isoformat()] = value
                    changes[day.isoformat()] = change
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
               report_url=URL.format(date=latest.replace('-', '')))
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

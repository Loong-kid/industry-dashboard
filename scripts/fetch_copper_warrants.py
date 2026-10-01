"""SHFE daily copper warrants, in tonnes. Not additive to weekly inventory."""
import argparse
import datetime as dt
import json
import time
from pathlib import Path

import requests
from fetch_copper_inventory import ReportTable, validate_values

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'data/commodities/comm_copper_shfe_warrants.json'
URL = 'https://www.shfe.cn/data/tradedata/future/stockdata/dailystock_{date}/ZH/all.html'
NAME = 'SHFE 구리 일간 창고증권'


def parse_report(text, stamp):
    table = ReportTable()
    table.feed(text)
    date = dt.datetime.strptime(stamp, '%Y%m%d').date().isoformat()
    if not table.rows or not table.rows[0] or not table.rows[0][0].startswith(date + ' '):
        raise ValueError('Report date mismatch')
    active = False
    totals = []
    for index, row in enumerate(table.rows):
        if len(row) == 2 and row[1].startswith('单位'):
            active = row[0] == '铜'
            if active and (row[1] != '单位：吨' or table.rows[index-1] != ['地区', '仓库', '期货', '增减']):
                raise ValueError('Unexpected unit or columns')
        elif active and row and row[0] == '总计':
            if len(row) != 3:
                raise ValueError('Unexpected total width')
            value, change = (float(v.replace(',', '')) for v in row[1:])
            totals.append(validate_values(value, value-change, change))
    if len(totals) != 1:
        raise ValueError('Expected one copper total')
    return totals[0]


def run(backfill_days=14):
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    old = json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else {}
    values = dict(old.get('series', {}).get(NAME, []))
    changes = dict(old.get('daily_changes', []))
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'
    found, errors = 0, []
    for offset in range(backfill_days, -1, -1):
        day = today - dt.timedelta(days=offset)
        if day.weekday() >= 5 or (day.isoformat() in values and offset > 14):
            continue
        try:
            response = session.get(URL.format(date=day.strftime('%Y%m%d')), timeout=(5, 15))
            if response.status_code == 404:
                continue
            response.raise_for_status()
            response.encoding = 'utf-8'
            value, change = parse_report(response.text, day.strftime('%Y%m%d'))
            values[day.isoformat()] = value
            changes[day.isoformat()] = change
            found += 1
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors.append(f'{day}: {exc}')
        time.sleep(.05)
    if not found:
        raise RuntimeError('No valid daily report; existing file preserved')
    latest = max(values)
    doc = dict(id='comm_copper_shfe_warrants', name=NAME, unit='톤', frequency='daily',
               source='SHFE 일간 창고증권 보고서',
               source_url='https://www.shfe.cn/reports/tradedata/dailyandweeklydata/',
               report_url=URL.format(date=latest.replace('-', '')),
               updated=latest, fetched=today.isoformat(), data_stale_days=14,
               series={NAME: sorted(values.items())}, daily_changes=sorted(changes.items()),
               stock_summary=True,
               description='SHFE 지정 창고에서 창고증권이 발행된 구리 물량입니다. 선물 인도에 사용할 수 있는 등록 물량의 일간 변화를 보여줍니다.',
               note='주간 재고에 포함되는 물량이므로 두 수치를 합산하지 않습니다. 증권 발행·취소만으로도 변하며, 감소가 실제 출고나 최종 소비를 뜻하지는 않습니다.')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix('.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temp.replace(OUTPUT)
    print(f'SHFE warrants: {len(values)} observations, latest {latest}; errors={len(errors)}')
    if errors:
        print('\n'.join(errors[:3]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill-days', type=int, default=14)
    run(parser.parse_args().backfill_days)

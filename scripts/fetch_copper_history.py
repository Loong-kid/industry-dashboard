"""Backfill public copper stocks; --backfill fetches Westmetall from 2008.

Only published observations are imported. No chart digitization or interpolation.
CSV exports retain the original source units. Existing observations win overlaps.
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import re

import requests

from fetch_copper_inventory import ReportTable
from fetch_copper_snapshot import OUT, TOTAL, REGISTERED, ELIGIBLE, LME, SHORT_TON_TO_TONNE

WESTMETALL = 'https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Cu_cash'
COMEX_URL = 'https://www.meiyuanhuanliu.com/copper_stocks/'
MONTHS = {name: i for i, name in enumerate(
    'January February March April May June July August September October November December'.split(), 1)}


def number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean inventory')
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('Invalid inventory')
    return result


def valid_date(value, today):
    date = dt.date.fromisoformat(value)
    if date.isoformat() != value or date > today:
        raise ValueError('Invalid/future date')
    return value


def parse_lme(text, year, today):
    table = ReportTable()
    table.feed(text)
    header = ['date', 'LME Copper Cash-Settlement', 'LME Copper 3-month', 'LME Copper stock']
    if header not in table.rows:
        raise ValueError('Unexpected Westmetall columns')
    rows = {}
    for row in table.rows:
        if len(row) != 4 or row == header:
            continue
        match = re.fullmatch(r'(\d{2})\. ([A-Za-z]+) (\d{4})', row[0])
        if not match:
            continue
        day, month, actual_year = match.groups()
        if int(actual_year) != year:
            raise ValueError('Wrong Westmetall year')
        date = valid_date(dt.date(year, MONTHS[month], int(day)).isoformat(), today)
        # Explicit missing stock is not zero; prices are not stock substitutes.
        if row[3] in ('', '-', '–'):
            continue
        if not re.fullmatch(r'\d{1,3}(?:,\d{3})*|\d+', row[3]):
            raise ValueError('Unexpected stock number format')
        if date in rows:
            raise ValueError('Duplicate Westmetall date')
        rows[date] = number(row[3].replace(',', ''))
    if not rows:
        raise ValueError('Empty Westmetall year')
    return sorted(rows.items())


def parse_comex(text, today):
    if 'const ST_TO_MT = 0.9072;' not in text:
        raise ValueError('COMEX source unit contract changed')
    matches = re.findall(r'const chartData\s*=\s*(\{[^;]+\});', text)
    if len(matches) != 1:
        raise ValueError('Missing/ambiguous COMEX data')
    data = json.loads(matches[0])
    dates = data['labels']
    if not dates or len(set(dates)) != len(dates) or dates != sorted(dates):
        raise ValueError('Empty, duplicate or unordered COMEX dates')
    if any(len(data[key]) != len(dates) for key in ('total', 'registered', 'eligible')):
        raise ValueError('COMEX array lengths differ')
    rows = []
    for i, date in enumerate(dates):
        valid_date(date, today)
        total, registered, eligible = [number(data[key][i]) for key in ('total', 'registered', 'eligible')]
        if abs(total - registered - eligible) > .001:
            raise ValueError('COMEX components do not reconcile')
        rows.append((date, total, registered, eligible))
    return rows


def merge(doc, incoming, source, url, csv_path):
    if set(incoming) != set(doc['series']) or doc['unit'] != '톤':
        raise ValueError('Existing series/unit mismatch')
    for name, points in incoming.items():
        existing = dict(doc['series'][name])
        values = dict(points)
        overlap = existing.keys() & values.keys()
        if not overlap:
            raise ValueError('No overlap available to validate historical source')
        if any(abs(existing[d] - values[d]) > .002 for d in overlap):
            raise ValueError('Historical source conflicts with existing observation')
        values.update(existing)
        doc['series'][name] = sorted(values.items())
    doc['updated'] = max(p[0] for p in next(iter(doc['series'].values())))
    doc['history_started'] = min(p[0] for p in next(iter(doc['series'].values())))
    doc['history_source'] = source
    doc['history_source_url'] = url
    doc['history_csv'] = csv_path
    doc['history_note'] = '공개 과거 자료와 일별 수집값을 연결했습니다. 원출처에 없는 날짜는 보간하지 않습니다.'
    return doc


def get(url):
    response = requests.get(url, timeout=(8, 35))
    response.raise_for_status()
    return response.text


def write(doc, rows, columns, stem):
    path = OUT / (stem + '.json')
    csv_path = OUT / 'history' / (stem + '.csv')
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(columns)
    writer.writerows(rows)
    temp = csv_path.with_suffix('.tmp')
    temp.write_text(output.getvalue(), encoding='utf-8')
    temp.replace(csv_path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)
    print(f"{stem}: {doc['history_started']}..{doc['updated']}, {len(next(iter(doc['series'].values())))} observations")


def run(backfill=False):
    today = dt.datetime.now(dt.timezone.utc).date()
    failures = []
    for exchange in ('comex', 'lme'):
        try:
            stem = f'comm_copper_{exchange}_inventory'
            doc = json.loads((OUT / (stem + '.json')).read_text(encoding='utf-8'))
            csv_rel = f'data/commodities/history/{stem}.csv'
            if exchange == 'comex':
                rows = parse_comex(get(COMEX_URL), today)
                incoming = {name: [(r[0], round(r[i] * SHORT_TON_TO_TONNE, 3)) for r in rows]
                            for i, name in enumerate((TOTAL, REGISTERED, ELIGIBLE), 1)}
                source, url = '美元环流 · CME COMEX 공개 원수치', COMEX_URL
                columns = ['date', 'total_short_tons', 'registered_short_tons', 'eligible_short_tons']
            else:
                # Current and previous year on daily runs; full archive only on explicit backfill.
                start = 2008 if backfill else today.year - 1
                rows = []
                for year in range(start, today.year + 1):
                    rows.extend(parse_lme(get(f'{WESTMETALL}&year={year}'), year, today))
                incoming = {LME: rows}
                source, url = 'Westmetall · LME 공개 재고', WESTMETALL
                columns = ['date', 'stock_metric_tonnes']
            doc = merge(doc, incoming, source, url, csv_rel)
            # CSV is cumulative too, including older rows outside the rolling source window.
            csv_file = OUT / 'history' / (stem + '.csv')
            old_rows = {}
            if csv_file.exists():
                with csv_file.open(encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)
                    if next(reader) != columns:
                        raise ValueError('CSV schema mismatch')
                    old_rows = {r[0]: r for r in reader if r}
            old_rows.update({r[0]: r for r in rows})
            write(doc, [old_rows[d] for d in sorted(old_rows)], columns, stem)
        except Exception as error:
            failures.append(f'{exchange}: {error}')
    if failures:
        raise RuntimeError('; '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill', action='store_true')
    run(parser.parse_args().backfill)

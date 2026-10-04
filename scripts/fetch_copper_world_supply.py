"""USGS copper world totals, separate from KOMIS disclosed-country subtotals."""
import argparse
import json
import re
from pathlib import Path

import fitz
import requests

from fetch_mineral_prices import korea_today, request
from fetch_mineral_supply import atomic_json

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'data/_mineral_supply/usgs_copper_world.json'
OUT = ROOT / 'data/commodities/comm_copper_world_supply.json'
FIRST_YEAR = 2019


def pdf_url(edition):
    return f'https://pubs.usgs.gov/periodicals/mcs{edition}/mcs{edition}.pdf'


def parse_chapter(text, unit_text, edition, page):
    if not re.search(r'(?m)^COPPER\s*$', text) or 'World total (rounded)' not in text:
        raise ValueError('Not the copper world production chapter')
    if not re.search(r'thousand metric tons[^\n]*(?:copper|contained copper)', unit_text):
        raise ValueError('Copper unit is not thousand metric tons of copper content')
    if not re.search(rf'Mineral Commodity Summaries, [A-Za-z]+ {edition}', text):
        raise ValueError('Wrong USGS report edition')
    table = text[text.index('World Mine'):text.index('World Resources')]
    if 'Mine production' not in table or 'Reserves' not in table or 'Other countries' not in table:
        raise ValueError('Unexpected world table coverage')
    header_start = table.index('Mine production')
    header = table[header_start:table.index('United States', header_start)]
    years = re.findall(r'\b(20\d{2})(e?)\b', header)
    expected = [(str(edition - 2), ''), (str(edition - 1), 'e')]
    with_refinery = 'Refinery production' in header
    if years != expected * (2 if with_refinery else 1):
        raise ValueError('Unexpected production years or columns')
    numbers = re.findall(r'[0-9,]+', table.split('World total (rounded)', 1)[1])
    if len(numbers) != (5 if with_refinery else 3):
        raise ValueError('Unexpected number of world total columns')
    values = [int(number.replace(',', '')) * 1000 for number in numbers]
    if not all(10_000_000 <= value <= 50_000_000 for value in values[:2]) or not 100_000_000 <= values[-1] <= 3_000_000_000:
        raise ValueError('Unexpected copper world quantity')
    return {'edition': edition, 'source_url': pdf_url(edition), 'page': page,
            'production': [[f'{edition - 2}-12-31', values[0]], [f'{edition - 1}-12-31', values[1]]],
            'reserves': [[f'{edition - 1}-12-31', values[-1]]]}


def parse_pdf(content, edition):
    matches = []
    with fitz.open(stream=content, filetype='pdf') as pdf:
        for index, page in enumerate(pdf):
            text = page.get_text()
            if re.search(r'(?m)^COPPER\s*$', text) and 'World total (rounded)' in text:
                if index == 0:
                    raise ValueError('Missing copper unit page')
                matches.append(parse_chapter(text, pdf[index - 1].get_text(), edition, index + 1))
    if len(matches) != 1:
        raise ValueError('Expected one copper world totals table')
    return matches[0]


def build_document(editions, fetched):
    series, sources, estimated = {}, {}, {}
    for field in ('production', 'reserves'):
        points, links, flags = {}, {}, {}
        for row in sorted(editions, key=lambda row: row['edition']):
            for date, value in row[field]:
                if int(date[:4]) < FIRST_YEAR:
                    continue
                points[date] = value
                links[date] = row['source_url'] + '#page=' + str(row['page'])
                flags[date] = field == 'production' and int(date[:4]) == row['edition'] - 1
        if not points or sorted(points) != [f'{year}-12-31' for year in range(FIRST_YEAR, int(max(points)[:4]) + 1)]:
            raise ValueError('Missing world total history')
        series[field] = sorted(map(list, points.items()))
        sources[field], estimated[field] = links, flags
    return {'id': 'comm_copper_world_supply', 'name': '구리 세계 전체 생산량 / 매장량',
            'unit': '톤', 'frequency': 'yearly', 'fetched': fetched,
            'updated': max(points[0] for values in series.values() for points in values),
            'source': 'USGS Mineral Commodity Summaries', 'source_url': pdf_url(max(row['edition'] for row in editions)),
            'series': series, 'sources': sources, 'estimated': estimated,
            'note': 'USGS World total (rounded), 기타 국가 포함. 생산량은 광산의 구리 함유량이며 제련·정련 생산량과 다릅니다. 매장량은 각 연도에 연결된 보고서의 공표시점 추정치입니다. 생산량은 다음 판의 수정값을 우선하며, 나라별 KOMIS 자료와 빈티지·반올림 차이가 있을 수 있습니다.'}


def collect(pdf_dir=None):
    today = korea_today()
    old_cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'editions': []}
    editions = {row['edition']: row for row in old_cache['editions']}
    latest = today.year
    # A new edition is normally published in February. Only a genuine 404
    # falls back to the previous edition; network/access failures keep data.
    session = requests.Session()
    def read_pdf(edition):
        local = Path(pdf_dir) / f'mcs{edition}.pdf' if pdf_dir else None
        if local and local.exists():
            return local.read_bytes()
        return request(session, 'GET', pdf_url(edition)).content
    try:
        editions[latest] = parse_pdf(read_pdf(latest), latest)
    except requests.HTTPError as error:
        if error.response.status_code != 404:
            raise
        latest -= 1
        editions[latest] = parse_pdf(read_pdf(latest), latest)
    for edition in range(FIRST_YEAR + 1, latest):
        if edition not in editions or edition == latest - 1:
            editions[edition] = parse_pdf(read_pdf(edition), edition)
    doc = build_document(list(editions.values()), today.isoformat())
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding='utf-8'))
        if doc['updated'] < old['updated']:
            raise ValueError('Latest world total regressed')
        for field in ('production', 'reserves'):
            if set(dict(old['series'][field])) - set(dict(doc['series'][field])):
                raise ValueError('World total history disappeared')
    atomic_json(CACHE, {'fetched': today.isoformat(), 'editions': sorted(editions.values(), key=lambda row: row['edition'])})
    atomic_json(OUT, doc)
    print(f"Copper world totals: latest {doc['updated']}, {len(doc['series']['production'])} production years")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf-dir', help='Use previously downloaded official reports for initial import')
    collect(parser.parse_args().pdf_dir)

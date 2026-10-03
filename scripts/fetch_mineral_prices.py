"""Cameco uranium, EIA annual SWU and all reviewed KOMIS prices (no API keys).

Initial run imports the published history. Later runs recheck two years of
KOMIS data and merge revisions, preserving older observations. Each source
fails independently; invalid responses never replace existing card files.
"""
import argparse
import calendar
import datetime as dt
import json
import math
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/commodities'
CAMECO = 'https://www.cameco.com/invest/markets/uranium-price'
EIA_SWU = 'https://www.eia.gov/uranium/marketing/summarytable2.php'
EIA_SWU_CHECK = 'https://www.eia.gov/uranium/marketing/table16.php'
KOMIS = 'https://www.komis.or.kr'
KOMIS_PAGE = KOMIS + '/Komis/RsrcPrice/MinorMetals'
KOMIS_API = KOMIS + '/Komis/RsrcPrice/ajax/'
SPOT = '현물 가격'
TERM = '장기계약 가격'


def korea_today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()


def price(value):
    number = float(str(value).replace(',', ''))
    if not math.isfinite(number) or number <= 0:
        raise ValueError('Price must be finite and positive')
    return number


def add_point(points, date, value, today):
    if dt.date.fromisoformat(date) > today:
        raise ValueError('Future price observation')
    value = price(value)
    if date in points and points[date] != value:
        raise ValueError(f'Conflicting duplicate price: {date}')
    points[date] = value


def parse_cameco(html, today):
    soup = BeautifulSoup(html, 'html.parser')
    tables = [table for table in soup.select('table')
              if [th.get_text(' ', strip=True) for th in table.select('thead th')]
              == ['', 'Uranium Spot Price', 'Long-term Uranium Price']]
    if len(tables) != 1:
        raise ValueError('Expected one Cameco monthly spot/term price table')
    spot, term = {}, {}
    for row in tables[0].select('tbody tr'):
        cells = [cell.get_text(' ', strip=True) for cell in row.select('td')]
        if len(cells) != 3:
            raise ValueError('Unexpected Cameco table columns')
        raw_date = dt.datetime.strptime(cells[0], '%Y/%m/%d').date()
        # Old rows are dated on the first of the month, but quote month-end
        # prices. Use month ends consistently, without manufacturing averages.
        date = raw_date.replace(day=calendar.monthrange(raw_date.year, raw_date.month)[1]).isoformat()
        add_point(spot, date, cells[1], today)
        if cells[2]:
            add_point(term, date, cells[2], today)
    if not spot or not term or max(spot) != max(term):
        raise ValueError('Missing or misaligned latest Cameco spot/term prices')
    return {SPOT: sorted(map(list, spot.items())), TERM: sorted(map(list, term.items()))}


def validate_komis_product(payload, reference, product, purity='99.5'):
    matches = [row for row in payload.get('data', []) if str(row.get('cdKey')) == str(reference)]
    if len(matches) != 1 or matches[0].get('cdVal') != product or str(matches[0].get('spcfct')) != purity:
        raise ValueError('KOMIS product, reference or purity changed')


def parse_komis(payload, mineral, today, purity='99.5'):
    info = payload.get('dataAvg', {}).get('INFO', {})
    expected = {'mnrkndKornNm': mineral, 'prcCrtr': purity + '%min FOB China',
                'weigUnitCd': 'kg', 'prcUnitCdNm': 'USD'}
    if any(info.get(key) != value for key, value in expected.items()):
        raise ValueError('KOMIS mineral, unit or price specification changed')
    points = {}
    for row in payload.get('data', {}).get('defaultMnrl', []):
        date = dt.datetime.strptime(row['crtrYmd'], '%Y%m%d').date().isoformat()
        value = price(row['cmercPrc'])
        # Old observations sometimes have 0/0 for an unpublished price range.
        # These are not zero prices; only validate ranges when provided.
        low, high = float(row.get('lowstPrc') or 0), float(row.get('hghstPrc') or 0)
        if not math.isfinite(low) or not math.isfinite(high) or min(low, high) < 0:
            raise ValueError('Invalid KOMIS price range')
        if (low or high) and not (0 < low <= value <= high):
            raise ValueError('KOMIS quoted price outside range')
        add_point(points, date, value, today)
    if not points:
        raise ValueError('Empty KOMIS price response')
    latest = payload.get('dataAvg', {}).get('stdMap', {}).get('CRTRYMD', {})
    if latest:
        date = dt.datetime.strptime(latest['crtrYmd'], '%Y%m%d').date().isoformat()
        if date != max(points) or price(latest['cmercPrc']) != points[date]:
            raise ValueError('KOMIS rows disagree with latest-price summary')
    return sorted(map(list, points.items()))


def text(element):
    return ' '.join(element.get_text(' ', strip=True).split())


def eia_table(html, caption_start):
    tables = [table for table in BeautifulSoup(html, 'html.parser').select('table')
              if table.find('caption') and text(table.find('caption')).startswith(caption_start)]
    if len(tables) != 1 or 'owners and operators of U.S. civilian nuclear power reactors' not in text(tables[0].find('caption')):
        raise ValueError('Expected one EIA civilian-reactor enrichment table')
    return tables[0]


def parse_eia_swu(html, today):
    table = eia_table(html, 'Table S2. Uranium feed deliveries, enrichment services,')
    headers = [text(cell) for cell in table.select('thead tr')[-1].select('th')]
    if headers.count('Year') != 1 or headers.count('Average price (US$ per SWU)') != 1:
        raise ValueError('EIA annual price column or unit changed')
    year_index, value_index = headers.index('Year'), headers.index('Average price (US$ per SWU)')
    points, years = {}, set()
    for row in table.select('tbody tr'):
        cells = [text(cell) for cell in row.select('td')]
        if len(cells) != len(headers) or not re.fullmatch(r'\d{4}', cells[year_index]):
            raise ValueError('Unexpected EIA annual row')
        year = int(cells[year_index])
        if year >= today.year or year < 1900 or year in years:
            raise ValueError('EIA annual row is duplicated or not a completed year')
        years.add(year)
        # '-' = no data reported; W = withheld. Never substitute zero.
        if cells[value_index] not in ('-', '–', '—', 'W'):
            add_point(points, f'{year}-12-31', cells[value_index], today)
    if not points or int(max(points)[:4]) != max(years):
        raise ValueError('Missing latest EIA annual SWU price')
    return sorted(map(list, points.items()))


def validate_eia_swu(points, html, today):
    table = eia_table(html, 'Table 16. Purchases of enrichment services')
    headers = [text(cell) for cell in table.select('thead th')]
    if not headers or headers[0] != 'Country of enrichment service (SWU-origin)':
        raise ValueError('EIA verification table header changed')
    years = headers[1:]
    if len(years) < 2 or len(set(years)) != len(years) or any(
            not re.fullmatch(r'\d{4}', year) or int(year) >= today.year for year in years):
        raise ValueError('Invalid EIA verification years')
    rows = [[text(cell) for cell in row.select('td')] for row in table.select('tbody tr')]
    prices = [row for row in rows if row and row[0] == 'Average price (US$ per SWU)']
    if len(prices) != 1 or len(prices[0]) != len(headers):
        raise ValueError('EIA verification price row or unit changed')
    summary = dict(points)
    if max(years) + '-12-31' != max(summary):
        raise ValueError('EIA annual tables have different latest years')
    for year, value in zip(years, prices[0][1:]):
        if summary.get(year + '-12-31') != price(value):
            raise ValueError('EIA summary and Table 16 prices disagree')


def request(session, method, url, **kwargs):
    error = None
    for attempt in range(3):
        try:
            response = session.request(method, url, timeout=(10, 30), **kwargs)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response
        except requests.RequestException as exc:
            error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise RuntimeError(f'Request failed: {url}') from error


def save_document(doc):
    path = OUT / (doc['id'] + '.json')
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        empty_lithium_placeholder = (doc['id'] == 'comm_lithium' and old.get('manual') is True
                                     and not any(old.get('series', {}).values()))
        if not empty_lithium_placeholder and (old.get('unit') != doc['unit'] or old.get('price_reference') != doc['price_reference']):
            raise ValueError('Existing series has a different unit or price reference')
        for name, incoming in doc['series'].items():
            previous = old.get('series', {}).get(name, [])
            if previous and incoming[-1][0] < previous[-1][0]:
                raise ValueError('Source latest date regressed; existing file preserved')
            points = dict(previous)
            points.update(incoming)  # Published revisions replace matching dates.
            doc['series'][name] = [[date, points[date]] for date in sorted(points)]
    doc['updated'] = max(points[-1][0] for points in doc['series'].values())
    OUT.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(doc, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')
    temporary.replace(path)
    print(f"{doc['id']}: {sum(len(s) for s in doc['series'].values())} observations, latest {doc['updated']}")


def fetch_uranium(session, today):
    series = parse_cameco(request(session, 'GET', CAMECO).text, today)
    save_document({
        'id': 'comm_uranium', 'name': '우라늄 현물·장기계약 가격',
        'unit': '$/lb U₃O₈', 'frequency': 'monthly', 'fetched': today.isoformat(),
        'source': 'Cameco · UxC/TradeTech 월말 가격', 'source_url': CAMECO,
        'price_reference': 'Cameco month-end U3O8 spot and long-term indicators',
        'default_series': [SPOT, TERM], 'series': series, 'data_stale_days': 70,
        'description': 'U₃O₈(우라늄 정광)의 월말 현물 가격과 장기계약 가격 지표. 일별 선물 종가나 월평균 가격이 아닙니다.',
        'note': '장기는 특정 5년물이 아니라 다년 공급계약의 기준가격 지표입니다. UxC의 일반 기준은 최소 3년 뒤 인도 시작·최소 5년간 공급이며 인도 시 가격 조정이 붙을 수 있습니다. Cameco는 UxC·TradeTech를 평균하며 2004년 5월 이전 장기 가격은 TradeTech 단독입니다.',
    })


def fetch_swu(session, today):
    points = parse_eia_swu(request(session, 'GET', EIA_SWU).text, today)
    validate_eia_swu(points, request(session, 'GET', EIA_SWU_CHECK).text, today)
    save_document({
        'id': 'comm_swu', 'name': '미국 원전 농축서비스 구매가격 (SWU)',
        'unit': '$/SWU', 'frequency': 'yearly', 'year_labels': True,
        'source': 'EIA · Uranium Marketing Annual Survey', 'source_url': EIA_SWU,
        'verification_url': EIA_SWU_CHECK,
        'price_reference': 'EIA-858 annual average price paid by US civilian nuclear reactor owners/operators',
        'fetched': today.isoformat(), 'series': {'연간 평균 구매가격': points},
        'data_stale_days': 730,
        'description': 'SWU는 우라늄 농축의 분리작업량 단위입니다. 미국 민간 원전 사업자가 해당 연도에 구매한 농축서비스의 실제 평균 지불가격을 보여줍니다.',
        'note': '기존 계약의 인도분도 포함하는 연간 명목 가격이며, 현재 신규 계약의 현물·장기 시장가격과 다릅니다. 물가 조정은 하지 않았습니다. 다음 해 연간 보고서에서 갱신되며, 미공개 연도는 채우지 않습니다.',
    })


def run(backfill=False):
    import fetch_komis_prices

    today = korea_today()
    session = requests.Session()
    session.headers['User-Agent'] = 'IndustryDashboard/1.0 (public mineral price monitoring)'
    errors = []
    jobs = [('uranium', lambda: fetch_uranium(session, today)),
            ('swu', lambda: fetch_swu(session, today)),
            ('komis', lambda: fetch_komis_prices.run(backfill, session, today))]
    for name, job in jobs:
        try:
            job()
        except Exception as exc:
            errors.append(name)
            print(f'ERROR {name}: {exc}')
    if errors:
        raise RuntimeError('Failed sources (existing files preserved): ' + ', '.join(errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backfill', action='store_true', help='Recheck all published KOMIS history')
    run(parser.parse_args().backfill)

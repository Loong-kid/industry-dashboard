"""Cameco monthly uranium and KOMIS rare-earth oxide prices (no API keys).

Initial run imports the published history. Later runs recheck two years of
KOMIS data and merge revisions, preserving older observations. Each source
fails independently; invalid responses never replace existing card files.
"""
import argparse
import calendar
import datetime as dt
import json
import math
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/commodities'
CAMECO = 'https://www.cameco.com/invest/markets/uranium-price'
KOMIS = 'https://www.komis.or.kr'
KOMIS_PAGE = KOMIS + '/Komis/RsrcPrice/MinorMetals'
KOMIS_API = KOMIS + '/Komis/RsrcPrice/ajax/'
SPOT = '현물 가격'
TERM = '장기계약 가격'
RARE_EARTHS = [
    ('comm_neodymium', '네오디뮴 산화물 (Nd₂O₃)', 'MNRL1001', 757, 'Neodymium Oxide', '네오디뮴'),
    ('comm_dysprosium', '디스프로슘 산화물 (Dy₂O₃)', 'MNRL1004', 803, 'Dysprosium Oxide', '디스프로슘'),
]


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


def validate_komis_product(payload, reference, product):
    matches = [row for row in payload.get('data', []) if str(row.get('cdKey')) == str(reference)]
    if len(matches) != 1 or matches[0].get('cdVal') != product or str(matches[0].get('spcfct')) != '99.5':
        raise ValueError('KOMIS product, reference or purity changed')


def parse_komis(payload, mineral, today):
    info = payload.get('dataAvg', {}).get('INFO', {})
    expected = {'mnrkndKornNm': mineral, 'prcCrtr': '99.5%min FOB China',
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
        if old.get('unit') != doc['unit'] or old.get('price_reference') != doc['price_reference']:
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
        'note': 'Cameco가 UxC·TradeTech의 월말 가격을 평균한 값입니다. 2004년 5월 이전 장기 가격은 TradeTech 단일 자료원입니다. 과거 월초 표기 날짜도 해당 월말로 통일했습니다.',
    })


def fetch_rare_earth(session, today, card, backfill=False):
    cid, name, mineral_code, reference, product, mineral = card
    options = request(session, 'POST', KOMIS_API + 'getMnrlPriceCrtr',
                      data={'HP000': 'HP002', 'mnrkndUnqCd': mineral_code}).json()
    validate_komis_product(options, reference, product)
    start = 1990 if backfill or not (OUT / (cid + '.json')).exists() else today.year - 1
    params = {'HP000': 'HP002', 'srchMnrkndUnqCd': mineral_code, 'srchPrcCrtr': reference,
              'srchAvgOpt': '', 'srchField': 'year', 'srchStartDate': start, 'srchEndDate': today.year}
    payload = request(session, 'POST', KOMIS_API + 'getMnrlPrcByMnrkndUnqCd', data=params).json()
    points = parse_komis(payload, mineral, today)
    save_document({
        'id': cid, 'name': name, 'unit': '$/kg', 'frequency': 'daily',
        'source': 'KOMIS 한국자원정보서비스', 'source_url': KOMIS + '/',
        'price_reference': {'mineral_code': mineral_code, 'reference': reference,
                            'product': product, 'purity': '99.5%', 'basis': 'FOB China'},
        'fetched': today.isoformat(), 'series': {name: points}, 'data_stale_days': 21,
        'description': '순도 99.5% 이상 산화물의 중국 FOB 가격 지표입니다. 금속 가격이나 중국 내수 가격과 기준이 다릅니다.',
        'note': 'KOMIS는 2026년부터 희토류 등의 자료원을 단계적으로 변경한다고 안내합니다. 변경 전후 가격은 같은 규격이어도 차이가 날 수 있습니다. 일자별 게시값이며 가격이 매일 변하는 것은 아닙니다.',
        'methodology_notice_url': KOMIS_PAGE,
    })


def run(backfill=False):
    today = korea_today()
    session = requests.Session()
    session.headers['User-Agent'] = 'IndustryDashboard/1.0 (public mineral price monitoring)'
    errors = []
    jobs = [('uranium', lambda: fetch_uranium(session, today))]
    # Use the website's ordinary session, without login or API credentials.
    jobs.extend((card[0], lambda card=card: fetch_rare_earth(session, today, card, backfill))
                for card in RARE_EARTHS)
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

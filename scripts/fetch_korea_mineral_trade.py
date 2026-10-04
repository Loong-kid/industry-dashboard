"""Public KOMIS / Korea Customs mineral trade. Raw USD and kg, not metal content.

Annual chart and exact-period country endpoints are separate published views.
The country endpoint returns only 30 ranked rows; its sum fields are the true
published totals. Never reconstruct totals from those rows or label a partial
current year as a full year. Validate the complete batch before publication.
"""
import calendar
import datetime as dt
import json
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from fetch_mineral_prices import korea_today
from fetch_mineral_supply import atomic_json

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://www.komis.or.kr'
PAGE = BASE + '/Komis/MnrlMap/Korea'
API = BASE + '/Komis/MnrlMap/MapKorea/ajax/'
OUT = ROOT / 'data/commodities/comm_korea_mineral_trade.json'
REGISTRY = ROOT / 'scripts/korea_mineral_trade_registry.json'
FIELDS = ('incmAmt', 'incmWeig', 'expAmt', 'expWeig')


def number(raw):
    if isinstance(raw, bool) or raw is None or raw == '':
        raise ValueError('Missing trade amount/weight')
    value = float(str(raw).replace(',', ''))
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid trade amount/weight')
    return int(value) if value.is_integer() else value


def annual_rows(rows, first, last):
    if not isinstance(rows, list):
        raise ValueError('Missing annual rows')
    result = {}
    for row in rows:
        year = str(row.get('crtrYmd', ''))
        if not re.fullmatch(r'\d{4}', year) or not first <= int(year) <= last:
            raise ValueError('Unexpected annual observation')
        if year in result:
            raise ValueError('Duplicate annual observation')
        result[year] = {field: number(row.get('total' + field[0].upper() + field[1:])) for field in FIELDS}
    return result


def ranked_rows(payload, start, end, direction):
    rows = payload.get('list')
    if not isinstance(rows, list):
        raise ValueError('Missing ranked country rows')
    if payload.get('srchDateS') != start or payload.get('srchDateE') != end:
        raise ValueError('Country period does not match request')
    if not rows:
        # No rows cannot distinguish no trade from unavailable totals.
        return {'start': start, 'end': end, 'totals': None, 'countries': [], 'direction': direction}
    totals = {field: number(rows[0].get('sum' + field[0].upper() + field[1:])) for field in FIELDS}
    countries, seen = [], set()
    for row in rows:
        if {field: number(row.get('sum' + field[0].upper() + field[1:])) for field in FIELDS} != totals:
            raise ValueError('Inconsistent published total')
        code, name = row.get('ntnCd'), row.get('ntnKornNm')
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z0-9]{2,3}', code) or code in seen:
            raise ValueError(f'Invalid or duplicate country: {code!r} / {name!r}, {start}-{end}')
        seen.add(code)
        countries.append({'code': code, 'name': name or f'국가명 미제공({code})', 'name_missing': not bool(name),
                          **{field: number(row.get(field)) for field in FIELDS}})
    rank_field = 'incmAmt' if direction == 'I' else 'expAmt'
    if any(a[rank_field] < b[rank_field] for a, b in zip(countries, countries[1:])):
        raise ValueError('Country ranking is not ordered')
    if any(sum(row[field] for row in countries) > totals[field] + 1e-6 for field in FIELDS):
        raise ValueError('Ranked countries exceed published total')
    return {'start': start, 'end': end, 'totals': totals, 'countries': countries, 'direction': direction}


def query(code, start, end, direction='I', flow=''):
    return {'srchMnrkndUnqCd': code, 'srchMttrFlowCd': flow, 'srchMttrFlowDtlCd': '',
            'srchHsCd': '', 'srchNtnCd': '', 'srchCrtrYmd': 'Y', 'srchDateS': start,
            'srchDateE': end, 'srchDatePS': start, 'srchDatePE': end,
            'srchIncmExp': direction, 'srchTypeAW': 'A', 'page': 1, 'listCount': 300,
            'orderBy': 'incmAmt' if direction == 'I' else 'expAmt', 'orderSort': 'DESC'}


def post(session, url, params):
    for attempt in range(3):
        try:
            response = session.post(url, data=params, timeout=45)
            response.raise_for_status()
            return json.loads(response.content.decode('utf-8'))
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def session():
    client = requests.Session()
    client.headers.update({'Referer': PAGE, 'X-Requested-With': 'XMLHttpRequest',
                           'User-Agent': 'IndustryDashboard/1.0 (public mineral trade)'})
    return client


def collect():
    today = korea_today()
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    client = session()
    discovered = post(client, BASE + '/ajax/komiscommon/getListSearchMnrl', {'stngCd': 'MNRL_KOREA'})['data']
    identity = {row['mnrkndUnqCd']: row['mnrkndKornNm'] for row in discovered}
    if len(identity) != len(discovered) or identity != registry['minerals']:
        raise ValueError('KOMIS Korean trade mineral list changed; review classifications')
    coverage = post(client, API + 'getMapKoreaCrtrYr', {})['data']
    latest = max((int(row['crtrYr']), int(row['crtrMm'])) for row in coverage)
    year, month = latest
    end = dt.date(year, month, calendar.monthrange(year, month)[1])
    if end >= today or year < 2020:
        raise ValueError('Unexpected latest published month')
    first = min(int(row['crtrYr']) for row in coverage)
    # Even December of a current year is kept out until the following March
    # annual finalisation window stated by KOMIS.
    last_full = min(year if month == 12 else year - 1, today.year - 1 if today.month >= 4 else today.year - 2)
    previous_month = end.replace(day=1) - dt.timedelta(days=1)
    previous_ytd = dt.date(year - 1, month, calendar.monthrange(year - 1, month)[1])
    periods = {
        'annual': (f'{last_full}0101', f'{last_full}1231'),
        'ytd': (f'{year}0101', end.strftime('%Y%m%d')),
        'previous_ytd': (f'{year - 1}0101', previous_ytd.strftime('%Y%m%d')),
        'month': (end.replace(day=1).strftime('%Y%m%d'), end.strftime('%Y%m%d')),
        'previous_month': (previous_month.replace(day=1).strftime('%Y%m%d'), previous_month.strftime('%Y%m%d')),
    }

    def mineral(row):
        code, name = row['mnrkndUnqCd'], row['mnrkndKornNm']
        with session() as worker:
            history = {}
            for final in [*range(first + 4, last_full, 5), last_full]:
                rows = post(worker, API + 'getLineChartDataKorea', query(code, f'{first}0101', f'{final}1231'))['data']
                parsed = annual_rows(rows, first, final)
                for date, values in parsed.items():
                    if date in history and history[date] != values:
                        raise ValueError(f'{code}: annual data changed during collection')
                    history[date] = values
            snapshots = {}
            for key, (start, finish) in periods.items():
                imports = ranked_rows(post(worker, API + 'getListKoreaData', query(code, start, finish)), start, finish, 'I')
                snapshots[key] = imports
                if key in ('annual', 'ytd'):
                    exports = ranked_rows(post(worker, API + 'getListKoreaData', query(code, start, finish, 'E')), start, finish, 'E')
                    if imports['totals'] != exports['totals']:
                        raise ValueError(f'{code}: import/export ranking totals disagree')
                    imports['export_countries'] = exports['countries']
            metadata = {'srchMnrkndUnqCd': code, 'srchMttrFlowCd': '', 'srchMttrFlowDtlCd': '', 'openYn': 'Y', 'isFront': 'Y'}
            hs = post(worker, BASE + '/ajax/komiscommon/getListOnlyHsCode', metadata)['data']
            if not isinstance(hs, list) or any(not re.fullmatch(r'\d{10}', str(item.get('hsCd', ''))) or not item.get('itemNm') for item in hs):
                raise ValueError('Invalid HS classification')
            flows = post(worker, BASE + '/ajax/komiscommon/getListMttrFlow', metadata)['data']
            products = []
            for flow in flows:
                start, finish = periods['ytd']
                totals = ranked_rows(post(worker, API + 'getListKoreaData', query(code, start, finish, flow=flow['mttrFlowCd'])), start, finish, 'I')['totals']
                products.append({'code': flow['mttrFlowCd'], 'name': flow['mttrFlowNm'], 'totals': totals})
            full = snapshots['annual']['totals']
            if str(last_full) in history and full and history[str(last_full)] != full:
                raise ValueError(f'{code}: latest annual chart and country totals disagree')
            result = {'id': code, 'name': {'동': '구리', '연': '납', '창연': '비스무트'}.get(name, name),
                      'komis_name': name, 'classification': row['clsfNm'],
                      'annual': dict(sorted(history.items())), 'snapshots': snapshots,
                      'products': products, 'hs_codes': hs, 'available': bool(history) or any(s['totals'] for s in snapshots.values())}
            print(f'{code}: {len(history)} annual observations, {len(hs)} HS codes', flush=True)
            return result

    with ThreadPoolExecutor(max_workers=3) as workers:
        minerals = list(workers.map(mineral, discovered))
    old = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else None
    if old:
        if end.isoformat() < old['updated']:
            raise ValueError('Latest published trade month regressed')
        previous = {row['id']: row for row in old['minerals']}
        for row in minerals:
            before = previous.get(row['id'], {})
            if before.get('available') and not row['available']:
                raise ValueError('Previously available mineral became empty')
            if set(before.get('annual', {})) - set(row['annual']):
                raise ValueError('Previously published annual history disappeared')
    doc = {'id': 'comm_korea_mineral_trade', 'name': '한국 광물 수출입', 'source': 'KOMIS · 관세청 수출입 무역통계',
           'source_url': PAGE, 'updated': end.isoformat(), 'fetched': today.isoformat(),
           'raw_units': {'amount': 'USD', 'weight': 'kg'}, 'last_full_year': last_full,
           'year': year, 'month': month, 'minerals': minerals,
           'note': '광물별 HS 품목 묶음의 통관 금액·제품 총중량입니다. 광석·금속·화합물·가공품·스크랩을 포함하며 순수 금속 함유량·국내 소비량과 다릅니다. 광물 간 HS 코드가 겹칠 수 있어 광물끼리 합산하지 않습니다.',
           'publication_note': 'KOMIS 공표 기준: 월 자료는 다음 달 15일, 연 자료는 다음 해 3월 중순 확정. 최신 공표월까지만 표시하며 연간 확정치·동기간 누적·최근 월을 나눕니다.'}
    atomic_json(OUT, doc)
    print(f'Published {len(minerals)} mineral categories through {end.isoformat()}')


if __name__ == '__main__':
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    collect()

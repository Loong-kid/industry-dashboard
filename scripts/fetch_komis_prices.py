"""Collect all reviewed KOMIS mineral price references, preserving their units.

The checked-in registry pins product and quotation metadata. Daily discovery
detects newly added/removed options without silently combining different bases.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

import requests

import fetch_mineral_prices as common

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / 'scripts/komis_prices.json'
BASE = 'https://www.komis.or.kr'
API = BASE + '/Komis/RsrcPrice/ajax/'
GROUPS = {
    'HP001': ('komis_base', '비철 / LME', '/Komis/RsrcPrice/BaseMetals'),
    'HP002': ('komis_minor', '희소 / 희토류', '/Komis/RsrcPrice/MinorMetals'),
    'HP003': ('komis_energy', '철 / 에너지', '/Komis/RsrcPrice/IronOre'),
    'HP004': ('komis_other', '귀금속 / 흑연', '/'),
}
INFO_KEYS = ('mnrkndKornNm', 'prcCrtr', 'weigUnitCd', 'prcUnitCdNm', 'isISE')
CHANGE_NOTE = ('KOMIS는 2026년부터 자료원을 단계적으로 변경한다고 안내합니다. '
               '같은 규격도 변경 전후 가격이 달라질 수 있으며 품목별 정확한 전환일은 공개되지 않았습니다.')


def normalized(value):
    return ' '.join(str(value or '').split())


def load_registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))


def identity(card):
    return card['group'], card['mineral_code'], int(card['reference'])


def options_for(session, group, code):
    payload = common.request(session, 'POST', API + 'getMnrlPriceCrtr',
                             data={'HP000': group, 'mnrkndUnqCd': code}).json()
    rows = payload.get('data')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Missing KOMIS product options')
    result = {}
    for row in rows:
        key = int(row['cdKey'])
        if key in result:
            raise ValueError('Duplicate KOMIS product reference')
        result[key] = {'product': normalized(row.get('cdVal')), 'specification': normalized(row.get('spcfct'))}
    return result


def validate_option(card, options):
    expected = {'product': card['product'], 'specification': card['specification']}
    if options.get(card['reference']) != expected:
        raise ValueError('KOMIS product or specification changed')


def parse_payload(payload, card, today):
    info = payload.get('dataAvg', {}).get('INFO', {})
    if any(normalized(info.get(key)) != card['info'][key] for key in INFO_KEYS):
        raise ValueError('KOMIS quotation basis, unit, currency or attribution changed')
    points, omitted, range_issues = {}, [], []
    rows = payload.get('data', {}).get('defaultMnrl')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Empty KOMIS price response')
    for row in rows:
        date = dt.datetime.strptime(row['crtrYmd'], '%Y%m%d').date().isoformat()
        if dt.date.fromisoformat(date) > today:
            raise ValueError('Future KOMIS observation')
        raw = row.get('cmercPrc')
        # Historical uranium rows use zero for unpublished observations. Keep
        # an explicit omission record rather than drawing a zero price.
        if raw in (None, '', '-', '–') or float(str(raw).replace(',', '')) == 0:
            omitted.append(date)
            continue
        value = common.price(raw)
        common.add_point(points, date, value, today)
        # Ancillary low/high fields contain known source errors, including a
        # date in the low-price column. The published reference price is kept
        # unchanged and its inconsistency is recorded for users to inspect.
        try:
            low, high = float(row.get('lowstPrc') or 0), float(row.get('hghstPrc') or 0)
            valid = math.isfinite(low) and math.isfinite(high) and min(low, high) >= 0
            if low > 0 and high > 0:
                valid = valid and low <= value <= high
            if not valid:
                range_issues.append(date)
        except (TypeError, ValueError):
            range_issues.append(date)
    if not points:
        raise ValueError('No published positive KOMIS prices')
    summary = payload.get('dataAvg', {}).get('stdMap', {}).get('CRTRYMD', {})
    if not summary or summary.get('crtrYmd') != max(points).replace('-', '') or common.price(summary.get('cmercPrc')) != points[max(points)]:
        raise ValueError('KOMIS rows disagree with latest-price summary')
    return sorted(map(list, points.items())), {'omitted_dates': sorted(set(omitted)), 'range_mismatch_dates': sorted(set(range_issues))}


def quotation_details(card, quality):
    info = card['info']
    details = [{'label': '제품·규격', 'value': card['product'] or info['prcCrtr']},
               {'label': '가격 기준 원문', 'value': info['prcCrtr']},
               {'label': '통화·단위', 'value': f"{info['prcUnitCdNm']} / {info['weigUnitCd']}"},
               {'label': '기준 해설', 'value': card['explanation']}]
    if card['specification']:
        details.insert(1, {'label': '규격 원문', 'value': card['specification']})
    details.append({'label': '발표 방식', 'value': '주간 지표의 실제 게시일입니다.' if card['frequency'] == 'weekly' else
                    '일자별 게시 기준가격입니다. 같은 값이 반복될 수 있으며 실시간 체결가격이나 거래량 가중평균을 뜻하지 않습니다.'})
    unit = info['weigUnitCd']
    if unit in ('ton', 'mt'):
        details.append({'label': '중량 단위', 'value': '미터톤(t) 기준, 1톤 = 1,000kg. kg 단위 가격으로 환산하지 않았습니다.'})
    elif unit in ('troz', 'ozt'):
        details.append({'label': '중량 단위', 'value': '트로이온스 기준, 1 트로이온스 ≈ 31.1035g.'})
    elif unit == 'mtu':
        details.append({'label': '함유량 단위', 'value': 'mtu는 metric tonne unit(1톤의 1%, 함유량 10kg)입니다. 제품 1톤당 가격과 다릅니다.'})
    if quality['range_mismatch_dates']:
        details.append({'label': '원문 범위값 불일치', 'value': ', '.join(quality['range_mismatch_dates']) +
                        ' · 원문의 최저·최고값과 기준가격이 일치하지 않습니다. 기준가격 원문값을 표시하며 임의로 정정하지 않았습니다.'})
    if quality['omitted_dates']:
        details.append({'label': '미공개 값 제외', 'value': ', '.join(quality['omitted_dates']) +
                        ' · 원문 0 또는 미공개 가격은 차트에서 제외했습니다.'})
    return details


def fetch_card(session, today, card, options, backfill=False):
    validate_option(card, options)
    path = common.OUT / (card['id'] + '.json')
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    start = 1987 if backfill or not old or not any(old.get('series', {}).values()) else today.year - 1
    payload = common.request(session, 'POST', API + 'getMnrlPrcByMnrkndUnqCd', data={
        'HP000': card['group'], 'srchMnrkndUnqCd': card['mineral_code'], 'srchPrcCrtr': card['reference'],
        'srchAvgOpt': '', 'srchField': 'year', 'srchStartDate': start, 'srchEndDate': today.year}).json()
    points, quality = parse_payload(payload, card, today)
    # Rechecked dates replace quality markers, while older markers survive an
    # incremental request. They always refer to the data actually displayed.
    for key in quality:
        quality[key] = sorted(set(quality[key]) | {date for date in (old or {}).get('data_quality', {}).get(key, [])
                                                 if date < f'{start}-01-01'})
    info = card['info']
    unit = {'ton': 't', 'mt': 't', 'troz': '트로이oz', 'ozt': '트로이oz'}.get(info['weigUnitCd'], info['weigUnitCd'])
    unit = f"{info['prcUnitCdNm']}/{unit}"
    if card['id'] in ('comm_neodymium', 'comm_dysprosium', 'comm_terbium', 'comm_praseodymium'):
        unit = '$/kg'  # Keep the existing four references and histories intact.
    doc = {'id': card['id'], 'name': card['name'], 'unit': unit, 'frequency': card['frequency'],
           'source': 'KOMIS · ' + card['attribution'], 'source_url': BASE + GROUPS[card['group']][2],
           'price_reference': card['price_reference'], 'komis_info': info, 'komis_group': card['group'],
           'fetched': today.isoformat(), 'series': {card['series_name']: points}, 'data_stale_days': 21,
           'description': f"{info['prcCrtr']} · {info['prcUnitCdNm']}/{info['weigUnitCd']} · {card['attribution']}",
           'note': CHANGE_NOTE if info['isISE'] == 'Y' or card['group'] in ('HP002', 'HP003') else '',
           'price_details': quotation_details(card, quality), 'data_quality': quality,
           'methodology_url': card['methodology_url']}
    common.save_document(doc)


def run(backfill=False, session=None, today=None):
    registry = load_registry()
    today = today or common.korea_today()
    session = session or requests.Session()
    session.headers['User-Agent'] = 'IndustryDashboard/1.0 (public mineral price monitoring)'
    errors, current = [], set()
    known = {identity(card) for card in registry['cards'] + registry['excluded']}
    for group in GROUPS:
        try:
            payload = common.request(session, 'POST', BASE + '/ajax/common/getMnrlKndInfoCodeList',
                                     data={'cdType': 'HP000', 'cdGrp': group}).json()
            minerals = payload.get('data')
            if not isinstance(minerals, list) or not minerals:
                raise ValueError('Missing KOMIS mineral list')
        except Exception as exc:
            errors.append(group)
            print(f'ERROR {group}: {exc}')
            continue
        for mineral in minerals:
            code = mineral['cdKey']
            try:
                options = options_for(session, group, code)
                current.update((group, code, ref) for ref in options)
            except Exception as exc:
                errors.append(code)
                print(f'ERROR {code}: {exc}')
                continue
            for card in registry['cards']:
                if (card['group'], card['mineral_code']) != (group, code):
                    continue
                try:
                    fetch_card(session, today, card, options, backfill)
                except Exception as exc:
                    errors.append(card['id'])
                    print(f"ERROR {card['id']}: {exc}")
            # Previously empty options are rechecked: a new price must not
            # remain silently excluded after the site starts publishing it.
            for card in registry['excluded']:
                if (card['group'], card['mineral_code']) != (group, code) or card['reference'] not in options:
                    continue
                try:
                    response = common.request(session, 'POST', API + 'getMnrlPrcByMnrkndUnqCd', data={
                        'HP000': group, 'srchMnrkndUnqCd': code, 'srchPrcCrtr': card['reference'],
                        'srchAvgOpt': '', 'srchField': 'year', 'srchStartDate': 1987, 'srchEndDate': today.year}).json()
                    if response.get('data', {}).get('defaultMnrl'):
                        raise ValueError('Previously empty option now publishes prices; review registry')
                except Exception as exc:
                    errors.append(str(identity(card)))
                    print(f'ERROR excluded option {identity(card)}: {exc}')
    if current != known:
        errors.append('inventory')
        print(f'ERROR KOMIS inventory changed: added={sorted(current-known)}, missing={sorted(known-current)}')
    if errors:
        raise RuntimeError('Failed KOMIS sources (existing files preserved): ' + ', '.join(errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backfill', action='store_true')
    run(parser.parse_args().backfill)

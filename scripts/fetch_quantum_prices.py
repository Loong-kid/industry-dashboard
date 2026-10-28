"""Completed-session USD prices for the four registered quantum ETFs."""
import argparse
import datetime as dt
import json
from pathlib import Path
import time

import requests

from drone_sources import prices
from fetch_drone import price_document
from fetch_cpu_companies import load, save

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/quantum'
CACHE = ROOT / '.cache/quantum/prices'
SYMBOLS = {'qtum': ('QTUM', 'NGM'), 'qtup': ('QTUP', 'BTS'),
           'wqtm_us': ('WQTM', 'BTS'), 'qntm_ucits': ('QNTM.L', 'LSE')}


def parse(payload, key, asof, now):
    symbol, exchange = SYMBOLS[key]
    meta = payload['chart']['result'][0]['meta']
    if meta.get('instrumentType') != 'ETF' or meta.get('exchangeName') != exchange:
        raise ValueError('ETF identity/exchange mismatch')
    return prices(payload, symbol, asof, now)


def collect(offline=False, asof=None):
    now = dt.datetime.now(dt.timezone.utc)
    asof = asof or now.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    etfs = load(ROOT / 'manual/quantum/etfs.json', [])
    state = load(OUT / 'prices_state.json', {'etfs': {}})
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'
    for etf in etfs:
        key = etf['id']; symbol, exchange = SYMBOLS[key]
        prior = state['etfs'].get(key, {})
        path = CACHE / (symbol + '.json')
        try:
            if offline:
                payload = load(path, {})
            else:
                response = session.get('https://query1.finance.yahoo.com/v8/finance/chart/' + symbol,
                    params={'period1': 1388534400, 'period2': int(now.timestamp()), 'interval': '1d', 'events': 'splits,div'}, timeout=40)
                response.raise_for_status(); payload = response.json()
            rows = parse(payload, key, asof, int(now.timestamp()))
            if prior.get('rows') and (rows[-1][0] < prior['rows'][-1][0] or rows[0][0] > prior['rows'][0][0]):
                raise ValueError('Price history regressed')
            state['etfs'][key] = dict(rows=rows, symbol=symbol, exchange=exchange,
                fetched=prior.get('fetched', asof) if offline else asof,
                checked=prior.get('checked', asof) if offline else asof, ok=True)
            if not offline: save(path, payload)
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, OSError) as e:
            state['etfs'][key] = dict(prior, symbol=symbol, exchange=exchange, checked=asof, ok=False)
            print(key, 'price source unavailable:', type(e).__name__, flush=True)
        cohort = state['etfs'][key]
        if not cohort.get('rows'):
            raise RuntimeError(key + ' has no verified ETF price history')
        doc = price_document('price_' + key, etf['ticker'] + ' · ' + etf['name'], symbol, cohort['rows'], cohort['fetched'], cohort['ok'], etf['url'],
            etf['market'] + '. ' + etf['scope'] + ' ' + etf['note'])
        doc['collection_status']['checked'] = cohort['checked']
        doc['compact_ticks'] = True
        doc['basis_details'].append(dict(label='거래 종목', value=symbol + ' · ' + exchange + ' · USD. ' +
            ('런던 상장 UCITS ETF이며 미국 QNTM 바이오 주가를 사용하지 않습니다.' if key == 'qntm_ucits' else
             '미국 WQTM 펀드이며 유럽의 동명 UCITS ETF와 구분합니다.' if key == 'wqtm_us' else
             '이전 LQTM에서 이어진 가격 이력입니다. 명칭·티커 변경 전후의 운용 범위는 운용사 원문에서 확인합니다.' if key == 'qtup' else '미국 상장 ETF입니다.')))
        save(OUT / ('price_' + key + '.json'), doc)
        print(key, len(cohort['rows']), 'daily ETF prices through', cohort['rows'][-1][0], flush=True)
        time.sleep(.25)
    if not offline: state['updated'] = now.isoformat(timespec='seconds')
    save(OUT / 'prices_state.json', state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--asof')
    args = parser.parse_args()
    collect(args.offline, args.asof)

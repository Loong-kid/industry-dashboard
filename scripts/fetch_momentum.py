"""Collect completed daily closes for US/Korea industry price momentum."""
import argparse
import copy
import datetime as dt
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from momentum_model import build_market, valid
from semicon_valuation_sources import price_rows

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT/'manual/momentum/universe.json'
OUT = ROOT/'data/momentum'
CACHE = ROOT/'.cache/momentum'


def read(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    temp.replace(path)


def validate_universe(config):
    ids = []
    for market in config['markets']:
        assert market['id'] in ('us','kr')
        for row in market['industries']:
            ids.append(row['id'])
            assert row['kind'] in ('etf','basket')
            if row['kind']=='etf':
                assert len(row['instruments'])==1
            assert row['instruments'] and (row['kind']!='basket' or len(row['instruments'])>=3)
        for instrument in [market['benchmark'],*(i for row in market['industries'] for i in row['instruments'])]:
            assert re.fullmatch(r'[A-Z0-9][A-Z0-9.-]*',instrument['symbol'])
            assert instrument['source_url'].startswith('https://')
    assert len(ids)==len(set(ids))
    assert {m['id'] for m in config['markets']}=={'us','kr'}


def naver_price_rows(payload, symbol, now, since):
    """One consistent KR daily-close feed; do not splice mismatched vendor tails."""
    code, venue = symbol.split('.')
    basic = payload['basic']
    if basic.get('itemCode')!=code or basic.get('stockExchangeType',{}).get('code')!=venue:
        raise ValueError('Naver issuer/venue mismatch')
    root = ET.fromstring(payload['chart_xml'])
    chart = root.find('chartdata')
    if chart is None or chart.get('symbol')!=code or chart.get('timeframe')!='day':
        raise ValueError('Naver chart identity/interval mismatch')
    local = now.astimezone(dt.timezone(dt.timedelta(hours=9)))
    today = local.date().isoformat()
    # Conservative buffer for delayed/special closing sessions. Daily schedules
    # are 08:40 and 18:40 KST; no partially completed Korean daily candle is used.
    last_allowed = (local.date()-dt.timedelta(days=1)).isoformat() if local.hour<18 else today
    values = {}
    for item in chart.findall('item'):
        raw = item.get('data','').split('|')
        if len(raw)<6 or not re.fullmatch(r'\d{8}',raw[0]):
            continue
        date = dt.datetime.strptime(raw[0],'%Y%m%d').date().isoformat()
        close = float(raw[4])
        if since<=date<=last_allowed and valid(close):
            values[date] = close
    if not values:
        raise ValueError('No completed Naver daily closes')
    return [[date,value] for date,value in sorted(values.items())],basic,chart.get('name') or basic.get('stockName')


def fetch_snapshot(instrument, market, old, now, since, offline=False):
    symbol = instrument['symbol']
    provider = 'naver' if market['id']=='kr' else 'yahoo'
    cache_path = CACHE/(symbol+('_naver' if provider=='naver' else '')+'.json')
    try:
        if offline:
            # A cached raw response may contain a candle that was intraday when
            # fetched. Replaying it after the bell must not promote that candle.
            if old.get('symbol')!=symbol or old.get('currency')!=market['currency'] or old.get('provider')!=provider or not old.get('prices'):
                raise ValueError('No saved completed-session history for offline rebuild')
            return copy.deepcopy(old)
        else:
            error = None
            for attempt in range(2):
                try:
                    if provider=='naver':
                        code = symbol.split('.')[0]
                        basic = requests.get(f'https://m.stock.naver.com/api/stock/{code}/basic',headers={'User-Agent':'Mozilla/5.0'},timeout=35)
                        basic.raise_for_status()
                        chart = requests.get('https://fchart.stock.naver.com/sise.nhn',params={'symbol':code,'timeframe':'day','count':5000,'requestType':0},headers={'User-Agent':'Mozilla/5.0'},timeout=35)
                        chart.raise_for_status()
                        payload = {'basic':basic.json(),'chart_xml':chart.text}
                    else:
                        response = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/'+symbol,
                                                params={'period1':int(dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp()),
                                                        'period2':int(now.timestamp()),'interval':'1d','events':'splits,div'},
                                                headers={'User-Agent':'Mozilla/5.0'},timeout=35)
                        response.raise_for_status()
                        payload = response.json()
                    error = None
                    break
                except (requests.RequestException,ValueError) as caught:
                    error = caught
                    if not attempt:
                        time.sleep(.7)
            if error:
                raise error
        asof = now.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
        if provider=='naver':
            prices,basic,quote_name = naver_price_rows(payload,symbol,now,since)
            actual_type = 'ETF' if basic.get('stockEndType')=='etf' else 'EQUITY' if basic.get('stockEndType')=='stock' else None
            if actual_type!=instrument['quote_type'] or market['currency']!='KRW':
                raise ValueError('Naver security type/currency mismatch')
            splits = []
            exchange = basic['stockExchangeType']['code']
        else:
            prices, splits, meta = price_rows(payload,symbol,market['currency'],asof,int(now.timestamp()),since)
            if meta.get('exchangeTimezoneName')!=market['timezone']:
                raise ValueError('Exchange timezone mismatch')
            if meta.get('instrumentType')!=instrument['quote_type']:
                raise ValueError('Security type mismatch')
            quote_name = meta.get('longName') or meta.get('shortName') or ''
            exchange = meta.get('exchangeName')
        if instrument['quote_type']=='ETF' and re.search(r'\b[23]x\b|leveraged|inverse|레버리지|인버스|covered.call|커버드콜',quote_name,re.I):
            raise ValueError('Leveraged/inverse/covered-call fund excluded')
        if old.get('provider')==provider and old.get('prices') and (prices[0][0]>old['prices'][0][0] or prices[-1][0]<old['prices'][-1][0]):
            raise ValueError('Price history regressed')
        if not offline:
            write(cache_path,payload)
        return {'symbol':symbol,'currency':market['currency'],'quote_type':instrument['quote_type'],'quote_name':quote_name,
                'provider':provider,'exchange':exchange,'prices':prices,'splits':splits,'ok':True,'errors':[],
                'fetched':old.get('fetched',asof) if offline else asof,'checked':asof}
    except Exception as error:
        preserved = copy.deepcopy(old) if old.get('symbol')==symbol and old.get('currency')==market['currency'] else {'symbol':symbol,'currency':market['currency'],'prices':[]}
        preserved.update(ok=False,errors=[type(error).__name__+': '+str(error)[:180]],checked=now.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat())
        return preserved


def run(offline=False):
    config = read(REGISTRY,{})
    validate_universe(config)
    previous_state = read(OUT/'state.json',{})
    previous = previous_state.get('snapshots',{})
    now = dt.datetime.now(dt.timezone.utc)
    instruments = {}
    for market in config['markets']:
        for instrument in [market['benchmark'],*(i for row in market['industries'] for i in row['instruments'])]:
            instruments[instrument['symbol']] = (instrument,market)
    snapshots = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_snapshot,i,m,previous.get(symbol,{}),now,config['history_since'],offline):symbol for symbol,(i,m) in instruments.items()}
        for future in as_completed(futures):
            symbol = futures[future]
            snapshots[symbol] = future.result()
            result = snapshots[symbol]
            print(symbol,len(result.get('prices',[])),'closes', 'OK' if result['ok'] else result['errors'],flush=True)
    if not any(snapshots[m['benchmark']['symbol']].get('ok') for m in config['markets']):
        raise RuntimeError('Neither benchmark could be confirmed; existing published data was preserved')
    collected_at = previous_state.get('checked') if offline else now.astimezone(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds')
    write(OUT/'state.json',{'version':config['version'],'checked':collected_at,'snapshots':dict(sorted(snapshots.items()))})
    for market in config['markets']:
        result = build_market(market,snapshots,collected_at,config['version'])
        write(OUT/(result['id']+'.json'),result)
        print(market['id'],result['updated'],len(result['rows']),'industries;',result['collection_status']['excluded'],'excluded',flush=True)
    return snapshots


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    run(parser.parse_args().offline)

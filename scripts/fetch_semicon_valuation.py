"""Daily lazy-loaded semiconductor prices and actual TTM PER/PBR reference bands."""
import argparse,copy,datetime as dt,json,time
from pathlib import Path
import requests
from semicon_valuation_sources import price_rows,yahoo_fundamentals,naver_fundamentals,analytics

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/semicon/valuation';CACHE=ROOT/'.cache/valuation'
TYPES=','.join(p+t for p in ('annual','quarterly') for t in ('DilutedEPS','CommonStockEquity','OrdinarySharesNumber','StockholdersEquity','PreferredSharesNumber'))+',trailingDilutedEPS'


def load(path,fallback):return json.loads(path.read_text(encoding='utf8')) if path.exists() else fallback


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf8');tmp.replace(path)


def collect(offline=False):
    now=dt.datetime.now(dt.timezone.utc);asof=now.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    registry=load(ROOT/'manual/semicon-valuation/companies.json',[]);summaries=[];session=requests.Session();session.headers['User-Agent']='Mozilla/5.0'
    reviews=load(ROOT/'manual/semicon-valuation/ttm_split_reviews.json',{})
    fx_cache={}
    def get(name,url,params=None):
        path=CACHE/(name+'.json')
        if offline:return load(path,{})
        r=session.get(url,params=params,timeout=35);r.raise_for_status();data=r.json();save(path,data);time.sleep(.12);return data
    price_params=dict(period1=1388534400,period2=int(now.timestamp()),interval='1d',events='splits,div')
    for spec in registry:
        key=spec['id'];path=OUT/(key+'.json');old=load(path,{})
        if spec['status']!='listed':summaries.append(dict(spec,price=None,per=None,pbr=None));continue
        errors=[];c=copy.deepcopy(old);symbol=spec['symbol'];currency=spec['currency']
        try:
            payload=get(symbol+'_price','https://query1.finance.yahoo.com/v8/finance/chart/'+symbol,price_params)
            prices,splits,meta=price_rows(payload,symbol,currency,asof,int(now.timestamp()),spec.get('price_since','2014-01-01'))
            if old.get('prices') and (prices[0][0]>old['prices'][0][0] or prices[-1][0]<old['prices'][-1][0]):raise ValueError('Price history regressed')
            c.update(prices=prices,splits=splits,exchange=meta['exchangeName'],timezone=meta['exchangeTimezoneName'],price_fetched=old.get('price_fetched',asof) if offline else asof)
        except Exception as e:errors.append('주가: '+type(e).__name__)
        try:
            if spec.get('naver_code'):
                code=spec['naver_code'];payloads=[get('naver_'+code+'_'+kind,f'https://m.stock.naver.com/api/stock/{code}/finance/{kind}') for kind in ('annual','quarter')]
                fund=naver_fundamentals(*payloads,code,asof);source='https://finance.naver.com/item/main.naver?code='+code
            else:
                payload=get(symbol+'_fund','https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/'+symbol,
                    dict(type=TYPES,period1=1388534400,period2=int(now.timestamp())))
                fund=yahoo_fundamentals(payload,symbol,asof,c.get('splits',[]),reviews.get(symbol));source='https://finance.yahoo.com/quote/'+symbol+'/financials/'
            if not fund['eps'] and not fund['bps']:raise ValueError('No reported EPS or BPS')
            if old.get('fundamentals'):
                for field in ('eps','bps'):
                    prior=old['fundamentals'][field]
                    # Keep collected history when provider rolling windows shorten.
                    merged={r[0]:copy.deepcopy(r) for r in prior if r[0]>='2022-01-01'}
                    for row in merged.values():
                        for split_date,factor in c.get('splits',[]):
                            if row[0]<split_date and old.get('price_fetched','9999')<split_date<=asof:row[1]/=factor
                    merged.update({r[0]:r for r in fund[field]});fund[field]=[r for _,r in sorted(merged.items())]
            c.update(fundamentals=fund,financial_source=source,financial_fetched=old.get('financial_fetched',asof) if offline else asof)
        except Exception as e:
            errors.append('실적: '+type(e).__name__)
            if old.get('prices') and any(old.get('price_fetched','9999')<date<=asof for date,factor in c.get('splits',[])):
                for field in ('prices','splits','price_fetched'):c[field]=old[field]
        fx={}
        for financial_currency in sorted({r[2] for field in ('eps','bps') for r in c.get('fundamentals',{}).get(field,[])}-{currency}):
            pair=financial_currency+currency
            try:
                if pair not in fx_cache:
                    p=get(pair+'_fx','https://query1.finance.yahoo.com/v8/finance/chart/'+pair+'=X',price_params)
                    fx_cache[pair]=price_rows(p,pair+'=X',currency,asof,int(now.timestamp()))[0]
                fx[pair]=fx_cache[pair]
            except Exception as e:
                if pair in old.get('fx',{}):fx[pair]=old['fx'][pair]
                errors.append('환율 '+pair+': '+type(e).__name__)
        c.update(spec,kind='semicon_valuation',checked=asof,errors=errors,ok=not errors,fx=fx,
            price_source='https://finance.yahoo.com/quote/'+symbol+'/history/',
            methodology='분할 반영 종가(배당 재투자 미반영). EPS는 실적 TTM(완결 연간 포함), BPS는 공시 기반 기말 값. 상장 법인 전사 기준이며 반도체·개별 사업부만의 배수가 아닙니다. 과거 밴드는 재작성된 회계기간 기준 참고치이며 공시일 당시의 투자 가능 정보를 재현하지 않습니다. 기준 배수는 2022년 이후 양의 유효 PER/PBR 중앙값이며 밴드는 그 배수의 0.5·0.75·1·1.25·1.5배입니다. 적자·0 이하 EPS 또는 순자산은 배수를 계산하지 않습니다.')
        fund=c.get('fundamentals',dict(eps=[],bps=[]));prices=c.get('prices',[])
        latest,bands=analytics(prices,fund,currency,fx);c.update(latest=latest,bands=bands)
        save(path,c)
        summaries.append(dict(spec,price=prices[-1][1] if prices else None,price_date=prices[-1][0] if prices else None,
            **latest,eps_basis=fund.get('eps_basis'),bps_basis=fund.get('bps_basis'),checked=asof,price_fetched=c.get('price_fetched'),financial_fetched=c.get('financial_fetched'),ok=c['ok'],errors=errors,
            price_source=c['price_source'],financial_source=c.get('financial_source'),price_count=len(prices),eps_count=len(fund['eps']),bps_count=len(fund['bps'])))
        print(key,len(prices),'closes;',len(fund['eps']),'EPS;',len(fund['bps']),'BPS;',len(errors),'warnings',flush=True)
    fetched=min((c.get(f) for c in summaries for f in ('price_fetched','financial_fetched') if c.get(f)),default=asof)
    save(OUT/'valuation_index.json',dict(id='semicon_valuation_index',updated=max((c.get('price_date') or '' for c in summaries),default=''),generated=now.isoformat(timespec='seconds'),fetched=fetched,checked=asof,companies=summaries,auto_collect_time='08:10'))
    return summaries


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');a=p.parse_args();collect(a.offline)

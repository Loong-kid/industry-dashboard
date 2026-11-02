"""Public split-adjusted closes and reported (never consensus) EPS/BPS."""
import calendar,datetime as dt,math
from zoneinfo import ZoneInfo


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def price_rows(payload,symbol,currency,asof,now,since='2014-01-01'):
    if payload['chart'].get('error'):raise ValueError('Price source error')
    d=payload['chart']['result'][0];m=d['meta']
    if m['symbol'].upper()!=symbol.upper() or m['currency']!=currency:raise ValueError('Price identity/currency mismatch')
    if m.get('dataGranularity')!='1d':raise ValueError('Unexpected price interval')
    zone=ZoneInfo(m['exchangeTimezoneName']);end=m['currentTradingPeriod']['regular']['end']
    session=dt.datetime.fromtimestamp(end,zone).date().isoformat();rows={}
    for stamp,value in zip(d.get('timestamp',[]),d['indicators']['quote'][0]['close']):
        date=dt.datetime.fromtimestamp(stamp,zone).date().isoformat()
        if not since<=date<=asof or date==session and now<end or not finite(value) or value<=0:continue
        rows[date]=round(value,6)
    if not rows:raise ValueError('No completed-session closes')
    splits=sorted([[dt.datetime.fromtimestamp(v['date'],zone).date().isoformat(),v['numerator']/v['denominator']] for v in d.get('events',{}).get('splits',{}).values()])
    return [[date,value] for date,value in sorted(rows.items())],splits,m


def yahoo_fundamentals(payload,symbol,asof,splits=(),review=None):
    timeseries=payload['timeseries']
    if timeseries.get('error'):raise ValueError('Fundamental source error')
    values={};eps={};bps={}
    for s in timeseries.get('result') or []:
        if s['meta']['symbol'][0].upper()!=symbol.upper():raise ValueError('Fundamental issuer mismatch')
        name=s['meta']['type'][0];values[name]={}
        for r in s.get(name,[]):
            date=r['asOfDate'];value=r.get('reportedValue',{}).get('raw');currency=r.get('currencyCode')
            if not '2022-01-01'<=date<=asof or not finite(value) or not currency:continue
            if name.startswith('trailing') and r.get('periodType')!='TTM':continue
            if name.startswith('annual') and r.get('periodType')!='12M':continue
            values[name][date]=(float(value),currency)
    annual=values.get('annualDilutedEPS',{});trailing=values.get('trailingDilutedEPS',{});apply_review=False
    if review:
        if not any(d==review['split_date'] and abs(f-review['factor'])<.0001 for d,f in splits):raise ValueError('Reviewed split missing from price source')
        anchor=review.get('anchor')
        if anchor and anchor in annual and anchor in trailing and annual[anchor][0]:
            ratio=trailing[anchor][0]/annual[anchor][0]
            if abs(ratio-1)<.04:apply_review=False
            elif abs(ratio/review['factor']-1)<.04:apply_review=True
            else:raise ValueError('TTM split review no longer reconciles to annual EPS')
        else:apply_review=True
    latest_split=max((d for d,f in splits if abs(f-1)>.0001),default='')
    for date,(value,currency) in trailing.items():
        if review:
            if date<=review['through'] and apply_review:value/=review['factor']
        elif date<latest_split:continue # Unreviewed pre-split TTM is not assumed adjusted.
        eps[date]=[date,value,currency,'trailingDilutedEPS'+(' · reviewed split basis' if review else '')]
    # Annual EPS is already restated by the supplier. Prefer it at year end,
    # rather than double-adjusting it or replacing it with an old-basis TTM.
    for date,(value,currency) in annual.items():eps[date]=[date,value,currency,'annualDilutedEPS · completed 12 months']
    for prefix in ('annual','quarterly'):
        equities=values.get(prefix+'CommonStockEquity',{});shares=values.get(prefix+'OrdinarySharesNumber',{})
        for date,(value,currency) in equities.items():
            count=shares.get(date,(None,None))[0]
            if not finite(count) or count<=0:continue
            bps[date]=[date,value/count,currency,prefix+'CommonStockEquity / '+prefix+'OrdinarySharesNumber']
    return dict(eps=[r for _,r in sorted(eps.items())],bps=[r for _,r in sorted(bps.items())],
                eps_basis='희석 EPS · TTM(완결 연간 포함)',bps_basis='보통주 귀속 자본 / 동일 기말 보통주 유통주식수')


def number(text):
    try:value=float(text.replace(',',''))
    except (ValueError,AttributeError):return None
    return value if math.isfinite(value) else None


def naver_fundamentals(annual,quarter,code,asof):
    eps={};bps={};quarters={}
    for payload,kind in [(annual,'annual'),(quarter,'quarter')]:
        if payload['itemCode']!=code:raise ValueError('Naver issuer mismatch')
        info=payload['financeInfo'];allowed={r['key'] for r in info['trTitleList'] if r['isConsensus']=='N'}
        for row in info['rowList']:
            if row['title'] not in ('EPS','BPS'):continue
            for key,column in row['columns'].items():
                if key not in allowed:continue
                year,month=int(key[:4]),int(key[4:6]);date=f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]}'
                value=number(column['value'])
                if date>asof or value is None:continue
                r=[date,value,'KRW','NAVER/FnGuide 보고 '+row['title']+' · '+kind]
                if row['title']=='BPS':bps[date]=r
                elif kind=='annual':eps[date]=r
                else:quarters[date]=r
    for date,r in sorted(quarters.items()):
        y,m=int(date[:4]),int(date[5:7]);prior=[]
        for lag in range(4):
            idx=y*12+m-1-lag*3;py,pm=idx//12,idx%12+1
            d=f'{py}-{pm:02d}-{calendar.monthrange(py,pm)[1]}'
            if d in quarters:prior.append(quarters[d])
        if len(prior)==4:eps[date]=[date,sum(x[1] for x in prior),'KRW','NAVER/FnGuide 실제 최근 4개 분기 EPS 합계']
    return dict(eps=[r for _,r in sorted(eps.items())],bps=[r for _,r in sorted(bps.items())],eps_basis='보고 EPS · 최근 4개 분기 합계(완결 연간 포함)',bps_basis='NAVER/FnGuide 공시 기반 BPS · 보통주 기준')


def at_or_before(rows,date,max_age=460):
    row=next((r for r in reversed(rows) if r[0]<=date),None)
    return row if row and (dt.date.fromisoformat(date)-dt.date.fromisoformat(row[0])).days<=max_age else None


def converted(row,date,currency,fx):
    if row is None:return None
    if row[2]==currency:return row[1]
    rates=fx.get(row[2]+currency,[]);rate=at_or_before(rates,date,7)
    return row[1]*rate[1] if rate else None


def positive_ratio(price,value):return price/value if finite(value) and value>0 else None


def percentile(values,q):
    s=sorted(values)
    if not s:return None
    pos=(len(s)-1)*q;i=int(pos)
    return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(pos-i)


def analytics(prices,fund,currency,fx):
    history={'per':[],'pbr':[]};latest={}
    for date,price in prices:
        current={}
        for key,field in [('per','eps'),('pbr','bps')]:
            source=at_or_before(fund[field],date);value=converted(source,date,currency,fx);ratio=positive_ratio(price,value)
            if ratio is not None and date>='2022-01-01':history[key].append(ratio)
            current[key]=round(ratio,4) if ratio is not None else None
            current[field]=round(value,6) if value is not None else None
            current[field+'_date']=source[0] if source else None
            current[field+'_reason']='자료 없음' if value is None else '적자·0 이하' if value<=0 else ''
        latest=current
    bands={key:sorted(set(round(percentile(v,.5)*factor,2) for factor in (.5,.75,1,1.25,1.5))) if v else [] for key,v in history.items()}
    return latest,bands

"""Actual issuer periods and completed-session prices for the drone dashboard."""
import calendar,copy,datetime as dt,math
from zoneinfo import ZoneInfo

METRICS={'revenue':'매출','profit':'영업이익','netincome':'순이익'}
TAGS={'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','Revenues'],
      'profit':['OperatingIncomeLoss'],'netincome':['NetIncomeLoss','ProfitLoss']}


def prepare(payload,meta):
    if meta['ticker']!='RCAT':return payload
    payload=copy.deepcopy(payload);facts=payload['facts']['us-gaap']
    def index(tag):return {(f['accn'],f.get('start'),f['end']):f for f in facts.get(tag,{}).get('units',{}).get('USD',[]) if f.get('start')}
    gross,expense=index('GrossProfit'),index('OperatingExpenses')
    target=facts.setdefault('OperatingIncomeLoss',dict(units={'USD':[]}))['units']['USD']
    reported={(f['accn'],f.get('start'),f['end']) for f in target}
    for context,g in gross.items():
        if context in reported or context not in expense:continue
        e=expense[context]
        target.append(dict(g,val=g['val']-e['val'],derivation='GAAP gross profit minus operating expenses; same accession/start/end',inputs=[dict(tag='GrossProfit',value=g['val']),dict(tag='OperatingExpenses',value=e['val'])]))
    return payload


def days(a,b):return (dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days+1


def fiscal(end,meta):
    date=dt.date.fromisoformat(end)
    if meta['ticker']=='RCAT' and '2024-05-01'<=end<='2024-12-31':
        if end not in ('2024-07-31','2024-10-31'):raise ValueError('Non-original Red Cat comparative calendar period')
        q=1 if end<'2024-08-15' else 2
        return 2024,q,f'2024 전환기 · {q}번째 3개월','transition'
    start=5 if meta['ticker']=='RCAT' and end<'2024-05-01' else meta['fiscal_start']
    candidates=[]
    for year in range(date.year-1,date.year+3):
        for q in range(1,5):
            month_index=(year-(start!=1))*12+start-1+q*3
            nominal=dt.date(month_index//12,month_index%12+1,1)-dt.timedelta(days=1)
            candidates.append((abs((date-nominal).days),year,q))
    gap,year,q=min(candidates)
    if gap>10:raise ValueError('Unrecognized fiscal quarter '+end)
    regime=('april' if end<'2024-05-01' else 'calendar') if meta['ticker']=='RCAT' else 'regular'
    return year,q,f'FY{year} Q{q}',regime


def accounts(payload,submissions,meta,asof):
    if int(payload['cik'])!=meta['cik'] or int(submissions['cik'])!=meta['cik']:raise ValueError('Issuer mismatch')
    payload=prepare(payload,meta)
    recent=submissions['filings']['recent']
    report_ends={a:d for a,d,form in zip(recent['accessionNumber'],recent['reportDate'],recent['form']) if form in ('10-Q','10-Q/A','10-K','10-K/A') and d}
    all_facts={};selected={}
    for metric,tags in TAGS.items():
        tags=meta.get('tags',{}).get(metric,tags)
        found=[];chosen={}
        for priority,tag in enumerate(tags):
            for f in payload['facts'].get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[]):
                if not f.get('start') or not meta['minimum_start']<=f['start']<=f['end']<=asof or f['filed']>asof:continue
                if f.get('form') not in ('10-Q','10-Q/A','10-K','10-K/A') or not isinstance(f['val'],(int,float)) or not math.isfinite(f['val']):continue
                # Red Cat used the contract-revenue tag in a disaggregation
                # note while its consolidated total was explicitly Revenues.
                rank=(-priority,f['filed'],f['accn']) if metric=='netincome' or meta['ticker']=='RCAT' and metric=='revenue' else (f['filed'],-priority,f['accn'])
                item=dict(f,tag='us-gaap:'+tag,rank=rank);found.append(item)
                key=f['start'],f['end']
                if key not in chosen or item['rank']>chosen[key]['rank']:chosen[key]=item
        all_facts[metric]=found;selected[metric]=chosen
    # Current-report dates are authoritative when comparative XBRL contexts
    # round a 52/53-week end to a nearby calendar month-end.
    canonical={f['end'] for f in all_facts['revenue'] if report_ends.get(f['accn'])==f['end'] and
        (75<=days(f['start'],f['end'])<=105 or 350<=days(f['start'],f['end'])<=380)}
    def accepted(end):return end in canonical or not any(abs((dt.date.fromisoformat(end)-dt.date.fromisoformat(c)).days)<=7 for c in canonical)
    def reference(f):
        a=f['accn'];return dict(url=f'https://www.sec.gov/Archives/edgar/data/{meta["cik"]}/{a.replace("-","")}/{a}-index.html',filed=f['filed'],start=f['start'],end=f['end'],tag=f['tag'],**({k:f[k] for k in ('derivation','inputs')} if f.get('derivation') else {}))
    rows={}
    def add(metric,f,value,refs,kind,start=None):
        end=f['end'];start=start or f['start']
        if end<'2014-01-01' or not accepted(end):return
        if kind=='annual':year=int(end[:4]);q=None;label=f'FY{year}';regime='regular'
        elif kind=='transition':year=2024;q=None;label='2024 전환기 · 8개월';regime='transition'
        else:
            try:year,q,label,regime=fiscal(end,meta)
            except ValueError:
                if meta['ticker']=='RCAT' and end<'2025-01-01':return
                raise
        key=kind,end
        row=rows.setdefault(key,dict(kind=kind,start=start,date=end,year=year,quarter=q,period=label,regime=regime,refs={}))
        row[metric]=value/1e6;row['refs'][metric]=dict(refs[0],components=refs,calculation='reported '+kind if len(refs)==1 else 'same fiscal-year YTD minus prior YTD')
    for metric,values in selected.items():
        for (start,end),f in sorted(values.items()):
            length=days(start,end)
            if 75<=length<=105:add(metric,f,f['val'],[reference(f)],'quarter')
            elif 350<=length<=380:add(metric,f,f['val'],[reference(f)],'annual')
            elif meta['ticker']=='RCAT' and start=='2024-05-01' and end=='2024-12-31':add(metric,f,f['val'],[reference(f)],'transition')
        for (start,end),f in sorted(values.items()):
            if metric in rows.get(('quarter',end),{}) or days(start,end)<150 or not accepted(end):continue
            previous=[p for p in all_facts[metric] if p['start']==start and p['tag']==f['tag'] and p['end']<end and p['filed']<=f['filed'] and 75<=days(p['end'],end)-1<=105]
            if not previous:continue
            prior=max(previous,key=lambda p:(p['end'],p['accn']==f['accn'],p['rank']))
            value=f['val']-prior['val']
            if metric=='revenue' and value<0:continue
            add(metric,f,value,[reference(f),reference(prior)],'quarter',(dt.date.fromisoformat(prior['end'])+dt.timedelta(days=1)).isoformat())
    result=sorted((r for r in rows.values() if 'revenue' in r),key=lambda r:(r['date'],r['kind']))
    if not result or any(not any(m in r for r in result) for m in METRICS):raise ValueError('Incomplete operating accounts')
    return result


def prices(payload,ticker,asof,now):
    if payload['chart'].get('error'):raise ValueError('Price source error')
    data=payload['chart']['result'][0];meta=data['meta']
    if meta['symbol'].upper()!=ticker.upper() or meta['currency']!='USD':raise ValueError('Price symbol/currency mismatch')
    if meta.get('dataGranularity')!='1d':raise ValueError('Daily source silently resampled')
    adjusted=data['indicators']['adjclose'][0]['adjclose'];close=data['indicators']['quote'][0]['close']
    zone=ZoneInfo(meta.get('exchangeTimezoneName','America/New_York'))
    regular_end=meta['currentTradingPeriod']['regular']['end'];session_date=dt.datetime.fromtimestamp(regular_end,zone).date().isoformat()
    rows={}
    for stamp,c,a in zip(data['timestamp'],close,adjusted):
        day=dt.datetime.fromtimestamp(stamp,zone).date().isoformat()
        if day>asof or day==session_date and now<regular_end:continue
        if c is None or a is None or not all(math.isfinite(v) and v>0 for v in (c,a)):continue
        rows[day]=dict(close=c,adjusted=a)
    if not rows:raise ValueError('No completed-session price observations')
    return [[date,values['close'],values['adjusted']] for date,values in sorted(rows.items())]


def indexed(histories):
    common=set.intersection(*(set(r[0] for r in rows) for rows in histories.values())) if histories else set()
    if not common:raise ValueError('No common comparison date')
    baseline=min(common)
    return baseline,{key:[[d,round(a/next(r[2] for r in rows if r[0]==baseline)*100,6)] for d,c,a in rows if d>=baseline] for key,rows in histories.items()}

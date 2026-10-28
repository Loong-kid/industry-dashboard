"""LNG carrier issuer statements: actual periods, signed total earnings, USD."""
import copy
import datetime as dt
import math
import re

from quantum_sources import period,METRICS


def source_rows(source,asof):
    if source['filed']>asof:return []
    if set(source['fields'])!=set(METRICS) or source['scale_to_millions']!=.001:raise ValueError('unreviewed statement rows or units')
    result=[]
    for col in source['columns']:
        if col['end']>asof:continue
        values={m:f['values'][col['index']]*source['scale_to_millions'] for m,f in source['fields'].items()}
        if not all(math.isfinite(v) for v in values.values()) or values['revenue']<0:raise ValueError('invalid native statement amount')
        result.append(dict(start=col['start'],date=col['end'],kind=col['kind'],year=int(col['end'][:4]),currency='USD',**values,
            refs={m:dict(url=source['url']+'#page='+str(source['page']+1),filed=source['filed'],start=col['start'],end=col['end'],
                tag=source['fields'][m]['label'],location='공식 연결 손익계산서',source_sha256=source['sha256'],
                calculation='reported '+col['kind'],unaudited=True) for m in METRICS}))
    return result


def annual_facts(payload,meta,asof):
    """Use the first available complete audit for each original fiscal year.

    Later 20-Fs may reclassify disposed businesses. Do not silently replace a
    year's original operating scope with a later continuing-operations scope.
    Golar ProfitLoss includes NCI; NetIncomeLoss is parent attribution there.
    """
    if int(payload['cik'])!=meta['cik']:raise ValueError('SEC issuer mismatch')
    groups={}
    for metric,tags in meta['tags'].items():
        for priority,tag in enumerate(tags):
            for f in payload.get('facts',{}).get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[]):
                if f.get('form') not in ['20-F','20-F/A'] or not f.get('start') or f['filed']>asof:continue
                year=int(f['end'][:4])
                if year<2014 or f['start']!=f'{year}-01-01' or f['end']!=f'{year}-12-31':continue
                if not isinstance(f['val'],(float,int)) or not math.isfinite(f['val']):continue
                key=(year,f['filed'],f['accn']);group=groups.setdefault(key,{})
                if metric not in group or priority<group[metric]['priority']:group[metric]=dict(f,tag='us-gaap:'+tag,priority=priority)
    selected={}
    for (year,filed,acc),fields in sorted(groups.items()):
        if year in selected or set(fields)!=set(METRICS):continue
        row=period(f'{year}-01-01',f'{year}-12-31','USD')
        for metric,f in fields.items():
            row[metric]=f['val']/1e6
            row['refs'][metric]=dict(url=f'https://www.sec.gov/Archives/edgar/data/{meta["cik"]}/{acc.replace("-","")}/{acc}-index.html',
                filed=filed,start=row['start'],end=row['date'],tag=f['tag'],location='SEC 감사 연결 실적',calculation='reported annual',unaudited=False)
        selected[year]=row
    return list(selected.values())


def accounts(sources,annual,asof):
    selected={}
    # Later same-year packets can correct the preceding quarter. Never replace
    # prior-year scope from a later-year disposal/restatement comparator.
    for source in sorted(sources,key=lambda s:(s['filed'],s['quarter'])):
        for row in source_rows(source,asof):selected[row['start'],row['date']]=row
    rows=[dict(period(r['start'],r['date'],'USD'),**{m:r[m] for m in METRICS},refs=copy.deepcopy(r['refs'])) for r in selected.values() if r['kind'] in ['quarter','annual']]
    # Recover one missing actual quarter from a real same-year cumulative.
    # E.g. original H1 minus Q2, or 9M minus actual Q1 and Q3. No equal splits.
    for year in sorted({r['year'] for r in selected.values()}):
        for q in [2,3,4]:
            end=f'{year}-{q*3:02d}-{30 if q in [2,3] else 31}'
            cumulative=selected.get((f'{year}-01-01',end))
            if not cumulative:continue
            quarters={r['quarter']:r for r in rows if r['kind']=='quarter' and r['year']==year and r['quarter']<=q}
            missing=set(range(1,q+1))-set(quarters)
            if len(missing)!=1:continue
            quarter=missing.pop();date=f'{year}-{quarter*3:02d}-{30 if quarter in [2,3] else 31}'
            row=period(f'{year}-{quarter*3-2:02d}-01',date,'USD')
            for metric in METRICS:
                value=cumulative[metric]-sum(r[metric] for r in quarters.values())
                if metric=='revenue' and value<0:continue
                row[metric]=value
                row['refs'][metric]=dict(cumulative['refs'][metric],calculation='same fiscal-year cumulative minus actual reported quarters',
                    components=[cumulative['refs'][metric]]+[r['refs'][metric] for _,r in sorted(quarters.items())])
            if row['refs']:rows.append(row)
    audits={r['year']:r for r in annual}
    rows=[r for r in rows if r['kind']!='annual' or r['year'] not in audits]+annual
    issues=[]
    for a in [r for r in rows if r['kind']=='annual']:
        qs=[r for r in rows if r['kind']=='quarter' and r['year']==a['year']]
        for metric in METRICS:
            if len(qs)==4 and all(metric in r for r in qs) and abs(sum(r[metric] for r in qs)-a[metric])>.01:
                issues.append(dict(year=a['year'],metric=metric,quarter_total=sum(r[metric] for r in qs),annual=a[metric],
                    note='분기는 해당 연도 분기 공시, 연간은 감사 공시입니다. 감사 조정·사업 범위 재분류로 합계가 다를 수 있습니다.'))
    return sorted(rows,key=lambda r:(r['date'],r['kind'])),issues

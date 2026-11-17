"""Selected cleanroom/HVAC peers: DART, issuer IR and TWSE/TPEx open data."""
import argparse,copy,math,re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from fetch_cpu_companies import load,save,today
from fetch_cleanroom_domestic import collect as domestic_collect
from import_cleanroom_ir import collect_issuer
from cleanroom_sources import end,accounts

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/semicon'
META=ROOT/'manual/cleanroom/companies.json';STATE=OUT/'cleanroom_state.json'
KGB='https://kelington-group.com/financial-infomation/'

def merge_rows(prior,current):
    result={r['date']:copy.deepcopy(r) for r in prior}
    for r in current:
        row=result.setdefault(r['date'],dict(date=r['date'],year=r['year'],refs={}))
        row.update({k:v for k,v in r.items() if k!='refs'});row['refs'].update(r['refs'])
    return [v for _,v in sorted(result.items())]

def kelington_html(text):
    """The issuer's PBT/PAT tables are never labeled as operating profit."""
    annual=[];rows=[]
    for table in BeautifulSoup(text,'html.parser').select('table'):
        lines=[[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])] for tr in table.select('tr')]
        years=next(([int(c) for c in line if re.fullmatch(r'20\d\d',c)] for line in lines if sum(bool(re.fullmatch(r'20\d\d',c)) for c in line)>3),None)
        if years:
            index={}
            for line in lines:
                if not line:continue
                metric={'Revenue':'revenue','Profit Before Tax':'pbt','Profit After Tax':'net'}.get(line[0])
                if not metric:continue
                values=line[-len(years):]
                for y,value in zip(years,values):
                    if not re.fullmatch(r'-?[\d,]+',value):continue
                    row=index.setdefault(y,dict(year=y,date=end(y,4),refs={}))
                    row[metric]=float(value.replace(',',''))/1000;row['refs'][metric]=dict(url=KGB,account_name=line[0],calculation='reported annual')
            annual.extend(index.values());continue
        header=next((line for line in lines if any(c=='Q1' for c in line)),None)
        if not header:continue
        metric={'Revenue':'revenue','Profit Before Tax':'pbt','Profit After Tax':'net'}.get(header[0])
        if not metric:continue
        for line in lines:
            if not line or not re.fullmatch(r'20\d\d',line[0]) or int(line[0])<2014:continue
            year=int(line[0])
            for q,value in enumerate(line[1:5],1):
                if not re.fullmatch(r'-?[\d,]+',value):continue
                rows.append(dict(year=year,quarter=q,date=end(year,q),**{metric:float(value.replace(',',''))/1000},refs={metric:dict(url=KGB,account_name=header[0],calculation='reported quarter')}))
    annual=merge_rows([],annual);rows=merge_rows([],rows)
    if not annual or not rows or any(not any(m in r for r in rows) for m in ('revenue','pbt','net')):raise ValueError('Kelington financial table changed')
    return dict(rows=rows,annual=annual)

def kelington(prior,refresh=False):
    seed=load(ROOT/'manual/cleanroom/kelington-reviewed.json',{})
    co=dict(rows=merge_rows(seed['rows'],prior.get('rows',[])),annual=merge_rows(seed['annual'],prior.get('annual',[])),ytd=prior.get('ytd',[]),checked=today(),fetched=prior.get('fetched',seed['reviewed']),ok=prior.get('ok',True))
    if refresh:
        try:
            r=requests.get(KGB,timeout=(10,35));r.raise_for_status();fresh=kelington_html(r.text)
            if fresh['rows'][-1]['date']<co['rows'][-1]['date']:raise ValueError('Kelington source regressed')
            for kind in ('rows','annual'):co[kind]=merge_rows(co[kind],fresh[kind])
            co.update(fetched=today(),ok=True)
        except (requests.RequestException,ValueError):co.update(ok=False)
    # Explicitly sourced cash PP&E. Six-month amounts remain YTD, never Q2.
    url='https://kelington-group.com/wp-content/uploads/2026/02/KGB-Q4-2025-Report-final.pdf'
    for year,value in [(2024,48.508),(2025,31.482)]:
        co['annual']=merge_rows(co['annual'],[dict(year=year,date=end(year,4),capex=value,refs={'capex':dict(url=url,account_name='Purchase of property, plant and equipments',calculation='reported annual cash outflow; 2025 unaudited Q4 statement')})])
    url='https://kelington-group.com/wp-content/uploads/2026/08/KGB-Q2-2026.pdf'
    co['ytd']=merge_rows(co['ytd'],[dict(year=y,quarter=2,date=end(y,2),capex=v,refs={'capex':dict(url=url,account_name='Purchase of property, plant and equipments',calculation='reported six-month cash outflow; not a standalone quarter')}) for y,v in [(2025,5.733),(2026,11.612)]])
    return co

def latest_taiwan(meta,companies):
    urls={'TWSE':'https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci','TPEx':'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci'}
    for market,url in urls.items():
        r=requests.get(url,timeout=(10,35));r.raise_for_status();payload=r.json()
        for key,spec in meta.items():
            if spec['market']!=market:continue
            matches=[r for r in payload if r.get('公司代號',r.get('SecuritiesCompanyCode'))==spec['ticker']]
            if len(matches)!=1:raise ValueError('TWSE issuer mapping changed')
            raw=matches[0];year=int(raw.get('年度',raw.get('Year')))+1911;q=int(raw.get('季別',raw.get('Season')))
            if q not in (1,2,3,4) or end(year,q)>today():raise ValueError('Future/invalid MOPS quarter')
            co=companies[key];fields={}
            for m,label in [('revenue','營業收入'),('profit','營業利益（損失）')]:
                value=float(raw[label])/1000
                if not math.isfinite(value) or m=='revenue' and value<0:raise ValueError('Invalid MOPS amount')
                fields[m]=dict(value=value if q==1 else None,ytd=value,url=url,start=f'{year}-01-01',end=end(year,q),account_name=label)
            # Keep the latest YTD as its own view, even if a prior-quarter PDF
            # has not been published. Never draw 9-month sales as Q3 sales.
            ytd=dict(date=end(year,q),year=year,quarter=q,refs={})
            for m,f in fields.items():ytd[m]=f['ytd'];ytd['refs'][m]=dict(f,calculation='reported year-to-date; not a standalone quarter')
            co['ytd']=merge_rows(co.get('ytd',[]),[ytd])
            previous=next((r for r in co.get('reports',[]) if r['year']==year and r['quarter']==q-1),None)
            if previous or q==1:
                quarter=dict(date=end(year,q),year=year,quarter=q,refs={})
                for m,f in fields.items():
                    p=previous['fields'].get(m) if previous else None
                    if q!=1 and (not p or p.get('ytd') is None):continue
                    quarter[m]=round(f['ytd']-(p['ytd'] if p else 0),6)
                    quarter['refs'][m]=dict(f,calculation='same-year consolidated YTD minus prior reported YTD' if p else 'reported first quarter',components=[f,p] if p else [f])
                if quarter['refs']:co['rows']=merge_rows(co['rows'],[quarter])
            co['latest_checked']=today()

def reviewed_income(key,co):
    seed=load(ROOT/'manual/cleanroom/taiwan-income-reviewed.json',{})['companies'].get(key)
    if not seed:return
    reports={(r['year'],r['quarter']):r for r in co['reports']};year=seed['year'];q=seed['quarter']
    for period in (1,q):
        if (year,period) in reports and not reports[year,period].get('reviewed_income_only'):continue
        fields={}
        for m in ('revenue','profit'):
            value=seed[m]/1000 if period==q else (seed[m+'_ytd']-seed[m])/1000
            fields[m]=dict(value=value,ytd=seed[m+'_ytd']/1000 if period==q else value,url=seed['source_url'],start=f'{year}-01-01',end=end(year,period),account_name='공시 재게시 · '+('營業收入合計' if m=='revenue' else '營業利益（損失）'),source_type='issuer statement republished by MoneyDJ',derivation='reported Q2 and six-month YTD' if period==q else 'six-month YTD minus reported Q2')
        reports[year,period]=dict(year=year,quarter=period,date=end(year,period),fields=fields,reviewed_income_only=True)
    combined=accounts(list(reports.values()))
    co['rows']=merge_rows(co['rows'],combined['rows']);co['annual']=merge_rows(co['annual'],combined['annual']);co['reports']=combined['reports']

def view(co,metric,kind):
    rows=co.get('annual' if kind=='annual' else 'ytd' if kind=='ytd' else 'rows',[])
    valid=[r for r in rows if metric in r]
    if not valid:return None
    first,last=valid[0]['date'],valid[-1]['date'];axis={r['date'] for r in rows if first<=r['date']<=last}
    if kind=='quarter':
        for year in range(int(first[:4]),int(last[:4])+1):
            for q in range(1,5):
                d=end(year,q)
                if first<=d<=last:axis.add(d)
    bydate={r['date']:r for r in rows};label={'revenue':'연결 매출','profit':'연결 영업이익','capex':'유형자산 취득 현금지출','pbt':'세전이익 · PBT','net':'당기순이익 · PAT'}[metric]
    refs={r['date']:dict(url=r['refs'][metric]['url'],label=f"FY{r['year']}"+('' if kind=='annual' else f" Q{r['quarter']}"+(' 누적' if kind=='ytd' else '')),
        supporting_sources=[dict(url=f['url'],label=f.get('start','')+' ~ '+f.get('end','')) for f in r['refs'][metric].get('components',[]) if f],source_separator=' − ') for r in valid}
    return dict(label={'quarter':'분기','annual':'연간','ytd':'누적 공시 · YTD'}[kind],frequency='yearly' if kind=='annual' else 'quarterly',frequency_label='연간' if kind=='annual' else '누적 공시 · 단독 분기 아님' if kind=='ytd' else '분기',quarter_labels=kind!='annual',year_labels=kind=='annual',annual_axis=kind=='annual',
        series={label:[[d,bydate.get(d,{}).get(metric)] for d in sorted(axis)]},default_series=[label],updated=last,source_url=valid[-1]['refs'][metric]['url'],point_sources=refs,
        period_labels={r['date']:refs[r['date']]['label'] for r in valid},quarterly_revenue_summary=kind=='quarter' and metric in ('revenue','capex'),quarterly_profit_summary=kind=='quarter' and metric in ('profit','pbt','net'),change_mode='none' if kind=='ytd' else 'standard')

def build(meta,state):
    docs={};universe=[]
    for key,spec in {**meta['companies'],**meta['global_companies']}.items():
        co=state['companies'][key];currency=spec.get('currency','KRW')
        metrics=[('revenue','매출'),('pbt','세전이익 · PBT'),('net','당기순이익 · PAT'),('capex','CAPEX')] if key=='kelington' else [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]
        for metric,title in metrics:
            views={kind:v for kind in ('quarter','annual','ytd') if (v:=view(co,metric,kind))}
            if not views:continue
            default='quarter' if 'quarter' in views else 'annual' if 'annual' in views else 'ytd'
            identifier=f'company_cleanroom_{key}_{metric}'
            note=spec['scope']+'. '+spec['note']
            if metric=='capex':note+=' CAPEX는 회사 자신의 유형자산 취득 현금지출이며 고객사 투자·클린룸 수주액과 다릅니다. 무형자산·M&A·비현금 리스 취득을 제외합니다.'
            if key=='kelington':note+=' PBT는 금융손익 등을 포함하는 세전이익이며 영업이익으로 표시하지 않습니다. 분기·연간 공표값의 재작성 차이를 임의 조정하지 않습니다. CAPEX는 확보한 연간·6개월 누적만 표시하며 2025 연간 취득지출은 미감사 Q4 공시입니다.'
            doc=dict(id=identifier,name=spec['name']+' · '+title,unit=currency+' 백만',source=('DART' if spec['country']=='한국' else 'TWSE·TPEx / 공식 IR' if spec['country']=='대만' else 'Kelington 공식 IR'),fetched=co['fetched'],description=note,company_kpi=True,compact_tooltip=True,span_gaps=False,table_limit=120,default_view=default,series_views=views,
                basis_details=[dict(label='사업·실적 범위',value=note),dict(label='기간 기준',value='연간은 완결 회계연도 공시, 분기는 실제 3개월 또는 같은 해 누적 차분입니다. YTD는 연초 이후 누적이며 단독 분기와 구분합니다. 확보하지 못한 기간·항목은 0이나 연간의 1/4로 채우지 않습니다.'),dict(label='통화·연결 범위',value=currency+' 백만. 연결 우선이며 국내 연결 미공시 기간은 별도입니다. 국가별 통화와 사업 범위가 달라 합산하지 않습니다.'),dict(label='공시 확인',value=co['checked']+' · '+('원문 확인' if co['ok'] else '일부 원문 확인 실패 · 확보한 자료 유지'))])
            if not co['ok']:doc['collection_status']=dict(ok=False,checked=co['checked'],message='일부 원문 확인 실패 · 확보한 이력 유지')
            doc.update(copy.deepcopy(views[default]));doc.pop('label',None);docs[identifier]=doc
        latest=co.get('ytd',[])[-1] if co.get('ytd') else co['rows'][-1]
        universe.append(dict(spec,id=key,currency=currency,quarter_start=co['rows'][0]['date'],quarter_end=co['rows'][-1]['date'],annual_start=co['annual'][0]['date'],latest_date=latest['date'],latest_basis='누적 YTD' if co.get('ytd') else '분기',ok=co['ok']))
    docs['cleanroom_universe']=dict(id='cleanroom_universe',name='클린룸·공조 기업 비교',companies=universe,selection_basis=meta['selection_basis'],fetched=state['fetched'],updated=max(c['latest_date'] for c in universe))
    return docs

def collect(refresh=False,full=False,from_state=False):
    meta=load(META,{});prior=load(STATE,dict(companies={}))
    if from_state:state=prior
    else:
        companies=copy.deepcopy(prior['companies']);asof=today()
        if refresh:
            try:domestic=domestic_collect(True,full)
            except (ValueError,RuntimeError):
                domestic=load(OUT/'cleanroom_domestic_state.json',{})
                if not domestic:raise
                for co in domestic['companies'].values():co.update(ok=False,checked=asof)
        else:domestic=load(OUT/'cleanroom_domestic_state.json',{})
        companies.update(domestic['companies'])
        global_seed=load(OUT/'cleanroom_global_state.json',dict(companies={}))
        for key in ('uis','lk','acter'):
            old=companies.get(key,global_seed['companies'].get(key,{}))
            if refresh:
                try:
                    fresh=collect_issuer(key,old,full)
                    for kind in ('rows','annual'):fresh[kind]=merge_rows(old.get(kind,[]),fresh[kind])
                    if not fresh['ok'] and old.get('fetched'):fresh['fetched']=old['fetched']
                    companies[key]=fresh
                except (requests.RequestException,ValueError):
                    if not old:raise
                    companies[key]=dict(old,ok=False,checked=asof)
            else:companies[key]=old
            reviewed_income(key,companies[key])
            # Recreate historical YTD from the actual reports, not quarter sums.
            historical=[]
            for r in companies[key].get('reports',[]):
                row=dict(date=r['date'],year=r['year'],quarter=r['quarter'],refs={})
                for m,f in r['fields'].items():
                    if f.get('ytd') is not None:row[m]=f['ytd'];row['refs'][m]=dict(f,calculation='reported year-to-date')
                historical.append(row)
            companies[key]['ytd']=merge_rows(historical,old.get('ytd',[]))
        companies['kelington']=kelington(companies.get('kelington',{}),refresh)
        try:latest_taiwan(meta['global_companies'],companies)
        except (requests.RequestException,ValueError,KeyError):
            for key in ('uis','lk','acter'):companies[key].update(ok=False,checked=asof,fetched=prior['companies'].get(key,{}).get('fetched',companies[key]['fetched']))
        state=dict(companies=companies,checked=asof,fetched=min(c['fetched'] for c in companies.values()))
        save(STATE,state)
    docs=build(meta,state)
    for identifier,doc in docs.items():save(OUT/(identifier+'.json'),doc)
    print('Published',len(docs),'cleanroom documents',flush=True)
    return state

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true');a=p.parse_args()
    collect(a.refresh,a.full_history,a.from_state)

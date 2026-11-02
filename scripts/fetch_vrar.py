"""Public original accounts for Korean and overseas XR device/component firms."""
import argparse,calendar,copy,datetime as dt,hashlib,json,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from cpu_business_history import SecClient
from fetch_cpu_companies import load,save,parse_facts,parse_annual
from vrar_sources import METRICS,reality_labs,htc_links,parse_htc_text,htc_accounts

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/vrar';CACHE=ROOT/'.cache/vrar'


def cached(url,refresh=False):
    path=CACHE/'http'/(hashlib.sha256(url.encode()).hexdigest()+'.raw')
    if path.exists() and not refresh:return path.read_bytes()
    for attempt in range(3):
        try:
            r=requests.get(url,headers={'User-Agent':'industry-dashboard personal research wkorotk@gmail.com'},timeout=(12,65));r.raise_for_status()
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content);return r.content
        except requests.RequestException:
            if attempt==2:raise
            time.sleep(attempt+1)


def collect_htc(prior,asof,full=False):
    import pymupdf
    base='https://investors.htc.com/en/financial-information/quarterly-results/'
    root=BeautifulSoup(cached(base,True),'html.parser');pages=[]
    for a in root.select('a[href]'):
        if a.get_text(strip=True)!='Learn More':continue
        year=next((y for y in range(2014,int(asof[:4])+1) if str(y) in a['href']),None)
        if year and (full or not prior.get('htc_reports') or year>=int(asof[:4])-1):pages.append(urljoin(base,a['href']))
    if not pages:raise ValueError('HTC report-year discovery failed')
    specs={}
    for page in pages:
        for item in htc_links(cached(page,True),page):
            if f"{item['year']}-{item['quarter']*3:02d}-01"<=asof:specs[item['year'],item['quarter']]=item
    reports={(r['year'],r['quarter']):r for r in prior.get('htc_reports',[])};errors=[]
    def parse(item):
        try:
            raw=cached(item['url'])
            with pymupdf.open(stream=raw,filetype='pdf') as pdf:text='\n'.join(pdf[i].get_text(sort=True) for i in range(min(14,len(pdf))))
            report=parse_htc_text(text,item['year'],item['quarter'],item['url'],asof)
            report['sha256']=hashlib.sha256(raw).hexdigest()
            return report,None
        except (requests.RequestException,ValueError,RuntimeError,StopIteration) as e:return None,((item['year'],item['quarter']),f"{item['year']} Q{item['quarter']} · {type(e).__name__} · {item['url']}")
    with ThreadPoolExecutor(max_workers=3) as pool:
        for report,error in pool.map(parse,specs.values()):
            if error:errors.append(error);print('HTC source review:',error[1],flush=True)
            else:reports[report['year'],report['quarter']]=report;print('HTC',report['year'],report['quarter'],'original PDF',flush=True)
    # Some historical IR links point to a press release instead of the labeled
    # statement. Use the following year's actual comparative columns when the
    # original period is missing; never substitute rounded press-release sales.
    for r in list(reports.values()):
        for c in r.get('comparatives',[]):
            if c['year']>=2014:reports.setdefault((c['year'],c['quarter']),c)
    errors=[message for identity,message in errors if identity not in reports]
    if not reports:raise ValueError('No HTC original statements')
    result=htc_accounts(list(reports.values()))
    if not result['annual'] or not result['rows']:raise ValueError('HTC annual/quarter history missing')
    return dict(result,htc_reports=list(reports.values()),source_errors=errors,ok=not errors,checked=asof,fetched=asof)


def collect_rl(client,meta,prior,asof,full=False):
    fields=copy.deepcopy(prior.get('rl_facts',{'revenue':[],'profit':[]}))
    reviewed=set(prior.get('rl_filings',[]))
    filings=[f for f in client.filings(meta['cik'],asof) if f['reportDate']>='2021-01-01']
    for f in filings:
        if f['accessionNumber'] in reviewed and not full:continue
        parsed=reality_labs(client.instance(f),f,meta['cik'])
        for metric,values in parsed.items():
            fields[metric]=[v for v in fields[metric] if v['accn']!=f['accessionNumber']]+values
        reviewed.add(f['accessionNumber']);print('Reality Labs',f['reportDate'],len(parsed['revenue']),'contexts',flush=True)
    payload=dict(cik=meta['cik'],facts={'us-gaap':{m:dict(units={'USD':v}) for m,v in fields.items()}})
    tags={m:[m] for m in fields}
    rows=parse_facts(payload,meta,asof,tags);annual=parse_annual(payload,meta,asof,tags)
    if not rows or not annual:raise ValueError('Reality Labs operating history missing')
    return dict(rows=rows,annual=annual,rl_facts=fields,rl_filings=sorted(reviewed),ok=True,checked=asof,fetched=asof)


def financial_document(key,metric,spec,cohort,segment=False):
    title='영업이익률' if metric=='margin' else METRICS[metric]
    views={}
    for kind,label in [('quarter','분기'),('annual','연간')]:
        rows=copy.deepcopy(cohort['rows' if kind=='quarter' else 'annual'])
        if metric=='margin':
            for r in rows:
                if r.get('revenue',0)>0 and r.get('profit') is not None:
                    r['margin']=r['profit']/r['revenue']*100
                    r['refs']['margin']=dict(r['refs']['profit'],components=r['refs']['profit']['components']+r['refs']['revenue']['components'],calculation='same actual period operating profit / revenue × 100')
        actual={r['date']:r for r in rows};axis=set(actual);lookup={(r['year'],r.get('quarter')):r['date'] for r in rows}
        if kind=='quarter' and rows:
            for year in range(rows[0]['year'],rows[-1]['year']+1):
                for q in range(1,5):
                    if (year,q) not in lookup:
                        day=f'{year}-{q*3:02d}-{calendar.monthrange(year,q*3)[1]}'
                        if rows[0]['date']<day<rows[-1]['date']:axis.add(day)
        valid=[r for r in rows if metric in r];refs={};notes={}
        for r in valid:
            ref=r['refs'][metric];components=ref['components'];period=f"FY{r['year']}"+('' if kind=='annual' else f" Q{r['quarter']}")
            refs[r['date']]=dict(url=ref['url'],label=period,supporting_sources=[dict(url=c['url'],label=c.get('start','')+' ~ '+c.get('end','')) for c in components],source_separator=' ÷ ' if metric=='margin' else ' − ' if len(components)==2 else ' / ')
            notes[r['date']]=[period,ref.get('calculation','공시 실적'),ref.get('tag',ref.get('account_name','DART 공시 항목'))]
            if r.get('fs_div'):notes[r['date']].append('연결' if r['fs_div']=='CFS' else '별도')
        series_label=('Reality Labs ' if segment else '')+title
        views[kind]=dict(label=label,frequency='quarterly' if kind=='quarter' else 'yearly',frequency_label=label+' · 실제 공시 기간',
            quarter_labels=kind=='quarter',year_labels=kind=='annual',annual_axis=kind=='annual',
            series={series_label:[[d,actual.get(d,{}).get(metric)] for d in sorted(axis)]} if valid else {},default_series=[series_label],
            period_labels={r['date']:f"FY{r['year']}"+('' if kind=='annual' else f" Q{r['quarter']}") for r in rows},point_sources=refs,point_notes=notes,
            updated=valid[-1]['date'] if valid else '',source_url=valid[-1]['refs'][metric]['url'] if valid else spec['source_url'],
            comparison_dates={r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),r['quarter']-1 or 4))) for r in rows} if kind=='quarter' else {},
            quarterly_revenue_summary=kind=='quarter' and metric in ('revenue','capex'),quarterly_profit_summary=kind=='quarter' and metric=='profit',change_mode='none')
    name='Meta · Reality Labs' if segment else spec['name'];identifier=f"company_vrar_{key}_{'rl_' if segment else ''}{metric}"
    capex_note='CAPEX는 현금흐름표의 유형자산 취득 현금지출입니다. 무형자산·M&A·비현금 리스와 외주 생산업체의 투자를 포함하지 않습니다. 사업부 CAPEX가 아니라 전사 기준입니다.'
    missing=[r['date'] for r in cohort['rows'] if metric=='capex' and 'capex' not in r]
    return dict(id=identifier,name=name+' · '+title,unit='%' if metric=='margin' else spec['currency']+' 백만',company_kpi=True,span_gaps=False,compact_ticks=True,compact_tooltip=True,table_limit=120,
        source='DART 정기 공시' if spec['source_type']=='dart' else 'HTC 공식 연결 재무제표' if spec['source_type']=='htc' else 'SEC 정기 공시 · Reality Labs 사업부' if segment else 'SEC 연결 재무제표',
        fetched=cohort['fetched'],description=('Reality Labs 사업부 실적. '+spec['note'] if segment else spec['scope']+'. '+spec['note'])+(' '+capex_note if metric=='capex' else ''),
        basis_details=[dict(label='사업·실적 범위',value='Reality Labs 사업부 · 전사와 구분' if segment else spec['scope']+'. '+spec['note']),
          dict(label='기간·금액',value='실제 3개월과 완결 회계연도를 구분합니다. 4분기·누적 현금흐름은 동일 회계연도의 누적−직전 누적으로 계산하며 연간을 4로 나누지 않습니다. 미확인 분기는 공백입니다. 원통화 백만 단위로 통화가 다른 회사를 단순 합산하지 않습니다.'),
          dict(label='CAPEX·영업손익',value=capex_note+' 영업손익은 공시 영업이익/손실로 순이익·조정 EBITDA와 다릅니다. Reality Labs 영업이익률은 해당 사업부 영업손익÷매출입니다.'),
          dict(label='이력·갱신',value=cohort['checked']+' · '+('원문 확인 완료' if cohort['ok'] else '일부 원문 검토 필요 · 기존 성공 이력 보존')),
          *([dict(label='분기 취득지출 공백',value=', '.join(missing)+' · 누적 취득지출의 역전 또는 비교 누적 미확보로 해당 분기 값을 계산하지 않았습니다. 음수 지출이나 0으로 대체하지 않으며 최근 확인된 분기의 금액을 표시합니다.')] if missing else []),
          *([dict(label='원문 검토',value=' / '.join(cohort['source_errors']))] if cohort.get('source_errors') else [])],
        collection_status=dict(ok=cohort['ok'],checked=cohort['checked'],message='원문 확인 완료' if cohort['ok'] else '조회·원문 검토 필요 · 기존 성공 이력 보존'),
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})


def build(state,meta):
    docs={}
    for key,spec in meta['companies'].items():
        for metric in METRICS:
            d=financial_document(key,metric,spec,state['companies'][key]);docs[d['id']]=d
        if key=='meta':
            for metric in ('revenue','profit','margin'):
                d=financial_document(key,metric,spec,state['reality_labs'],True);docs[d['id']]=d
    return docs


def collect(refresh=False,full=False,skip_korea=False,from_state=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();meta=load(ROOT/'manual/vrar/companies.json',{})
    state=load(OUT/'state.json',dict(companies={}))
    if not from_state:
        if refresh and not skip_korea:
            from collect_vrar_korea import refresh as korea_refresh
            try:korea_refresh(full)
            except (ValueError,RuntimeError) as e:
                if not (OUT/'korea_state.json').exists():raise
                korean=load(OUT/'korea_state.json',{})
                for co in korean['companies'].values():co.update(ok=False,checked=asof)
                save(OUT/'korea_state.json',korean);print('Korean original query failed; retained last accounts',type(e).__name__,flush=True)
        korean=load(OUT/'korea_state.json',{})
        for key,co in korean.get('companies',{}).items():state['companies'][key]=co
        if refresh:
            client=SecClient(CACHE/'sec')
            for key,spec in meta['companies'].items():
                if spec['source_type']=='dart':continue
                prior=state['companies'].get(key,{})
                try:
                    if spec['source_type']=='htc':co=collect_htc(prior,asof,full)
                    else:
                        payload=json.loads(client.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',True))
                        rows=parse_facts(payload,spec,asof);annual=parse_annual(payload,spec,asof)
                        co=dict(rows=rows,annual=annual,ok=True,checked=asof,fetched=asof)
                    if prior.get('rows') and co['rows'][-1]['date']<prior['rows'][-1]['date']:raise ValueError('Source history regressed')
                    state['companies'][key]=co;print(key,len(co['rows']),'quarters',len(co['annual']),'annuals',flush=True)
                except (requests.RequestException,ValueError,RuntimeError) as e:
                    if not prior:raise
                    state['companies'][key]=dict(prior,ok=False,checked=asof);print(key,'preserved prior accounts',type(e).__name__,flush=True)
            try:state['reality_labs']=collect_rl(client,meta['companies']['meta'],state.get('reality_labs',{}),asof,full)
            except (requests.RequestException,ValueError,ET.ParseError) as e:
                if not state.get('reality_labs'):raise
                state['reality_labs'].update(ok=False,checked=asof);print('Reality Labs retained prior accounts',type(e).__name__,flush=True)
    docs=build(state,meta)
    for identifier,doc in docs.items():save(OUT/(identifier+'.json'),doc)
    public=dict(meta,updated=asof,companies=[dict(spec,id=key,financial_end=state['companies'][key]['rows'][-1]['date'],quarters=len(state['companies'][key]['rows']),annual_start=state['companies'][key]['annual'][0]['date'],ok=state['companies'][key]['ok']) for key,spec in meta['companies'].items()])
    save(OUT/'universe.json',public);state['updated']=asof;save(OUT/'state.json',state)
    print('Published',len(docs),'VR/AR charts',flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--skip-korea',action='store_true');p.add_argument('--from-state',action='store_true');a=p.parse_args()
    collect(a.refresh,a.full_history,a.skip_korea,a.from_state)

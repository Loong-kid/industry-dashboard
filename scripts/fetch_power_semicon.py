"""NXP, onsemi and STMicroelectronics consolidated US-GAAP accounts.

SEC companyfacts plus original US-GAAP statements for the foreign issuers.
CAPEX is gross cash PP&E acquisition; quarterly YTD differences never cross FY.
"""
import argparse
import copy
import datetime as dt
import hashlib
import re
import time
import requests
from fetch_cpu_companies import ROOT, OUT, load, save, today, parse_facts, parse_annual, build_company, TAGS
from power_semicon_sources import statement_facts

CACHE=ROOT/'.cache/power-semicon'
COMPANIES={
    'nxp':dict(name='NXP Semiconductors',cik=1413447,fiscal_start=1,
        scope='NXP 전사 연결 · 자동차·산업·IoT·모바일·통신 포함',
        note='전력반도체 단독 실적이 아닙니다. 자동차 MCU·프로세서·아날로그·보안·연결 칩 등을 포함합니다. Freescale 인수(2015), Standard Products 매각(2017), 인수계약 해지 보상금(2018)과 MEMS 사업 매각(2026) 등으로 기간별 비교에 주의합니다.'),
    'onsemi':dict(name='onsemi',cik=1097864,fiscal_start=1,
        scope='onsemi 전사 연결 · 전력·아날로그·센싱 포함',
        note='전력반도체·SiC 외 아날로그·센싱 등 전사 연결 실적입니다. 실제 52/53주 회계 종료일을 보존합니다. 구조조정·손상차손 등을 포함한 GAAP 영업이익이며 조정 영업이익과 구분합니다.'),
    'stm':dict(name='STMicroelectronics',cik=932787,fiscal_start=1,
        scope='STM 전사 연결 · 아날로그·전력·MCU·디지털·MEMS 포함',
        note='전력반도체·SiC 외 MCU·아날로그·디지털·MEMS 등 전사 연결 실적입니다. 미국 SEC 공시의 US GAAP 기준이며 유럽 연차·반기 보고서의 IFRS 수치와 혼합하지 않습니다. CAPEX는 유형자산 취득 현금지출이며 보조금·기여금·자산 처분을 차감한 Non-GAAP Net CAPEX와 다릅니다.'),
}
for company in COMPANIES.values():
    company.update(revenue_description='전력반도체 외 사업을 포함한 전사 연결 매출입니다. 사업 인수·매각 및 연결 범위 변경을 포함합니다.',
        capex_description='현금흐름표의 유형자산 취득 현금지출입니다. 보조금·자산 처분 수입을 차감하지 않으며 무형자산 취득과 기업 인수는 제외합니다.')


def combined_payload(payload, extras, company):
    """Canonical metric tags let original statements fill API omissions.

Keep original source tags in each observation; the canonical names are only an
internal join key, not a claim that SEC assigned XBRL tags to legacy HTML.
"""
    if int(payload['cik'])!=company['cik']:raise ValueError('SEC company mismatch')
    extras=copy.deepcopy(extras)
    # Full interim reports state the actual week-based end. Recover direct
    # quarter starts from the previous observed end instead of calendar months.
    ends={}
    for f in extras:
        end=dt.date.fromisoformat(f['end']);q=round((end-dt.date(end.year,1,1)).days/91.25)
        ends.setdefault((end.year,q),set()).add(end)
    for f in extras:
        start,end=map(dt.date.fromisoformat,(f['start'],f['end']))
        q=round((end-dt.date(end.year,1,1)).days/91.25)
        previous=ends.get((end.year,q-1),set())
        if 75<=(end-start).days+1<=105 and q>1 and len(previous)==1:
            f['start']=(next(iter(previous))+dt.timedelta(days=1)).isoformat()
    # Legacy NXP releases report a stand-alone quarter rather than YTD. Sum
    # three explicitly reported quarters to support annual-minus-nine-months;
    # never divide an annual figure by four or mix fiscal years.
    if company['cik']==1413447:
        for metric in TAGS:
            direct={}
            for f in extras:
                if f['metric']!=metric or not 75<=(dt.date.fromisoformat(f['end'])-dt.date.fromisoformat(f['start'])).days+1<=105:continue
                q=round((dt.date.fromisoformat(f['end'])-dt.date(int(f['end'][:4]),1,1)).days/91.25)
                key=int(f['end'][:4]),q
                if key not in direct or f['filed']<direct[key]['filed']:direct[key]=f
            for (year,q),last in sorted(direct.items()):
                if q<2 or any((year,n) not in direct for n in range(1,q+1)):continue
                start=f'{year}-01-01'
                if any(f['metric']==metric and f['start']==start and f['end']==last['end'] for f in extras):continue
                parts=[direct[year,n] for n in range(1,q+1)]
                extras.append(dict(last,start=start,val=sum(f['val'] for f in parts),filed=max(f['filed'] for f in parts),
                    derivation='sum of reported quarters in the same fiscal year',inputs=[dict(url=f['source_url'],filed=f['filed'],start=f['start'],end=f['end'],tag=f['source_tag']) for f in parts]))
    facts={};tags={}
    for metric,names in TAGS.items():
        name='Power'+metric.title();tags[metric]=[name];values=[]
        for original in names:
            for f in payload['facts'].get('us-gaap',{}).get(original,{}).get('units',{}).get('USD',[]):
                values.append(dict(f,source_tag='us-gaap:'+original))
        values.extend({k:v for k,v in f.items() if k!='metric'} for f in extras if f['metric']==metric)
        facts[name]=dict(units={'USD':values})
    return dict(cik=company['cik'],facts={'us-gaap':facts}),tags


def refresh_originals(get, prior, asof):
    """Only new STM 20-F/financial 6-K filings; never European IFRS SAR/DAR.

    Existing normalized statement observations are durable in the public state,
    so scheduled jobs do not re-download a decade of HTML.
    """
    extra=copy.deepcopy(prior)
    recent=get('stm_submissions', 'https://data.sec.gov/submissions/CIK0000932787.json').get('filings',{}).get('recent',{})
    boundary=extra.get('checked','2014-01-01');sources=extra.setdefault('sources',[])
    known={s['url'] for s in sources}
    for i,form in enumerate(recent.get('form',[])):
        filed=recent['filingDate'][i];doc=recent['primaryDocument'][i];acc=recent['accessionNumber'][i]
        if not boundary<=filed<=asof:continue
        financial=(form=='20-F' or form=='6-K' and re.search(r'^stm-6k_(?:q[123]|20\d{6})',doc,re.I))
        if not financial:continue
        url=f'https://www.sec.gov/Archives/edgar/data/932787/{acc.replace("-","")}/{doc}'
        if url in known:continue
        html=get(acc+'_'+doc,url,raw=True)
        observations=statement_facts(html,url,filed,acc,form)
        # Some historical named 6-Ks are shareholder notices. A report named
        # for a quarter, however, must yield all three primary metrics.
        if re.search(r'^stm-6k_q[123]',doc,re.I) and {f['metric'] for f in observations}!={'revenue','profit','capex'}:
            raise ValueError('STM financial statement format changed')
        if observations:
            extra.setdefault('facts',[]).extend(observations)
            sources.append(dict(url=url,filed=filed,sha256=hashlib.sha256(html).hexdigest()))
    extra['checked']=asof
    return extra


def collect(offline=False,cached=False):
    asof=today();state=load(OUT/'power_semicon_state.json',dict(companies={}))
    seed=load(ROOT/'manual/power_semicon_history.json',{})
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    def get(name,url,raw=False):
        path=CACHE/(name+('.html' if raw else '.json'))
        if cached:return path.read_bytes() if raw else load(path,{})
        response=session.get(url,timeout=60);response.raise_for_status()
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(response.content);time.sleep(.2)
        return response.content if raw else response.json()
    for key,company in COMPANIES.items():
        prior=state['companies'].get(key,{})
        if offline:
            if not prior.get('rows'):raise ValueError('No cached financial history: '+key)
            continue
        try:
            extras=copy.deepcopy(prior.get('originals',dict(seed.get('companies',{}).get(key,{}),checked=seed['reviewed'])))
            if key=='stm':extras=refresh_originals(get,extras,asof)
            payload=get(key+'_facts',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{company["cik"]:010d}.json')
            merged,tags=combined_payload(payload,extras.get('facts',[]),company)
            spec=dict(company,tags=tags)
            rows=parse_facts(merged,spec,asof);annual=parse_annual(merged,spec,asof)
            for row in rows:
                for ref in row['refs'].values():
                    ref['components']=[part for component in ref['components'] for part in component.get('inputs',[component])]
            if any(rows[-1].get(m) is None for m in TAGS):raise ValueError('Latest quarter incomplete')
            if prior.get('rows') and (rows[-1]['date']<prior['rows'][-1]['date'] or len(rows)<len(prior['rows'])):
                raise ValueError('Financial history regressed')
            state['companies'][key]=dict(rows=rows,annual=annual,originals=extras,fetched=asof,checked=asof,ok=True)
            print(key,len(rows),'quarters',rows[0]['date'],'to',rows[-1]['date'],flush=True)
        except Exception as error:
            if not prior.get('rows'):raise RuntimeError(key+': no successful financial history') from error
            state['companies'][key]=dict(prior,checked=asof,ok=False)
            print(key,'retained previous history:',type(error).__name__,flush=True)
    docs={}
    for key,company in COMPANIES.items():
        for identifier,doc in build_company(key,state['companies'][key],company).items():
            doc['basis_details'][1]['value']='실제 공시 분기 종료일을 보존합니다. 직접 공시 분기는 공시 비교 수치, 누적 공시만 있는 CAPEX·4분기는 동일 회계연도 누적 차분입니다. 2014년 이후 확보된 공시를 제공하며 미확인 기간은 공란으로 둡니다. 공시 재분류·반올림으로 분기 합계와 재작성된 연간 수치가 다를 수 있습니다.'
            docs[identifier]=doc
    save(OUT/'power_semicon_state.json',state)
    for identifier,doc in docs.items():save(OUT/(identifier+'.json'),doc)
    return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true');parser.add_argument('--cached',action='store_true')
    args=parser.parse_args();collect(args.offline,args.cached)

"""Public telecom equipment accounts, separate from operator investments."""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fetch_cpu_companies import save, reference
from fetch_game_fx import SOURCE, parse_rates, build_snapshot
from fetch_telecom import collect_dart, document, load, merge_rows
from telecom_sources import sec_accounts, dart_accounts, reporting_period
from telecom_equipment_sources import parse_ericsson_pdf, parse_nokia_pdf, zte_report

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/telecom'
CACHE=ROOT/'.cache/telecom/equipment'
META=ROOT/'manual/telecom/equipment.json'
METRICS=['revenue','profit','capex']
SOURCES=ROOT/'manual/telecom/equipment-sources.json'


def fetch(session,url,offline=False):
    path=CACHE/(hashlib.sha256(url.encode()).hexdigest()[:18]+'.bin')
    if offline:return path.read_bytes()
    r=session.get(url,timeout=40);r.raise_for_status()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content)
    return r.content


def ifrs_annual(payload,meta,asof):
    if int(payload['cik'])!=meta['cik']:raise ValueError('issuer mismatch')
    tags={'revenue':['RevenueFromContractsWithCustomers','Revenue'],
          'profit':['ProfitLossFromOperatingActivities'],
          'capex':['PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'] if meta['currency']=='SEK' else ['PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets']}
    rows={}
    for metric,names in tags.items():
        selected={}
        for priority,tag in enumerate(names):
            for f in payload['facts']['ifrs-full'].get(tag,{}).get('units',{}).get(meta['currency'],[]):
                if not f.get('start') or not '2020-01-01'<=f['end']<=asof or f['filed']>asof:continue
                if not 350<=(dt.date.fromisoformat(f['end'])-dt.date.fromisoformat(f['start'])).days+1<=380:continue
                rank=(f['filed'],-priority,f['accn'])
                if f['end'] not in selected or rank>selected[f['end']]['rank']:selected[f['end']]=dict(f,tag='ifrs-full:'+tag,rank=rank)
        for end,f in selected.items():
            row=rows.setdefault(end,dict(reporting_period(int(end[:4])),start=f['start'],date=end))
            row[metric]=f['val']/1e6;row['refs'][metric]=dict(reference(f,meta['cik']),calculation='reported annual')
    return list(rows.values())


def european_quarters(key,session,asof,offline,prior):
    sources=load(SOURCES,{})[key] if key=='nokia' else [dict(year=2026,quarter=3,filed='2026-10-15',url='https://mb.cision.com/Main/15448/4409101/4319119.pdf')]
    errors=[]
    if key=='ericsson' and not offline:
        try:
            soup=BeautifulSoup(fetch(session,'https://news.cision.com/ericsson'),'html.parser')
            candidates=list(dict.fromkeys(a['href'] for a in soup.select('a[href]') if re.search(r'ericsson-reports-(?:first|second|third|fourth)-quarter-results-20\d{2}',a['href'])))[:3]
            for link in candidates:
                match=re.search(r'reports-(first|second|third|fourth)-quarter-results-(20\d{2})',link)
                year=int(match[2]);quarter=['first','second','third','fourth'].index(match[1])+1
                release=BeautifulSoup(fetch(session,link),'html.parser')
                pdfs=[a['href'] for a in release.select('a[href]') if 'mb.cision.com/Main/' in a['href'] and a['href'].endswith('.pdf')]
                if pdfs:sources.append(dict(year=year,quarter=quarter,filed=asof,url=pdfs[0]))
        except (requests.RequestException,ValueError):errors.append('최신 Cision 공시 목록 조회 미완료')
    sources=list({r['url']:r for r in sources}.values())
    rows=[r for r in prior.get('rows',[]) if r['kind']=='quarter']
    for source in sorted(sources,key=lambda s:(s['year'],s['quarter'])):
        if source['filed']>asof:continue
        try:
            parser=parse_ericsson_pdf if key=='ericsson' else parse_nokia_pdf
            updates=parser(fetch(session,source['url'],offline),source['url'],source['year'],source['quarter'],asof)
            rows=merge_rows(rows,updates)
        except (requests.RequestException,ValueError,OSError) as error:
            errors.append(f"{source['year']} Q{source['quarter']} 원문 조회·형식 검토 필요 ({type(error).__name__})")
    if key=='nokia' and not offline:
        # Nokia's direct IR asset server may reject automation. SEC is used to
        # detect a newer material filing; reviewed PDFs remain visibly dated.
        try:
            submissions=json.loads(fetch(session,'https://data.sec.gov/submissions/CIK0000924613.json'))['filings']['recent']
            latest=max(s['filed'] for s in sources)
            newer=[d for i,d in enumerate(submissions['filingDate']) if latest<d<=asof and submissions['form'][i]=='6-K' and submissions['size'][i]>1000000]
            if newer:errors.append('확보한 분기 원문 이후 새 대형 6-K 공시 확인 · 신규 분기/수정 표 검토 필요: '+max(newer))
        except (requests.RequestException,ValueError,KeyError):errors.append('신규 Nokia 6-K 공시 확인 미완료')
    return rows,errors


def collect_zte(session,asof,offline,prior):
    sources=load(SOURCES,{})['zte'];errors=[]
    reviewed=load(ROOT/'manual/telecom/zte-reviewed.json',{})['reports']
    reviewed_urls={r['fields']['capex']['url'] for r in reviewed}
    if not offline:
        try:
            base='https://www.zte.com.cn/global/about/investorrelations.html'
            soup=BeautifulSoup(fetch(session,base),'html.parser')
            for a in soup.select('a[href$=".pdf"]'):
                text=a.get_text(' ',strip=True);match=re.search(r'(20\d{2})\s+(THIRD QUARTERLY REPORT|FIRST QUARTERLY REPORT|Interim Report|Annual Report)',text,re.I)
                date=re.search(r'(20\d{2})-(\d{1,2})-(\d{1,2})',text)
                if not match or not date:continue
                filed=f'{int(date[1]):04d}-{int(date[2]):02d}-{int(date[3]):02d}'
                quarter=3 if 'THIRD' in match[2].upper() else 1 if 'FIRST' in match[2].upper() else 2 if 'INTERIM' in match[2].upper() else 4
                url=urljoin(base,a['href'])
                if url not in reviewed_urls:sources.append(dict(year=int(match[1]),quarter=quarter,filed=filed,url=url))
        except (requests.RequestException,ValueError):errors.append('최신 ZTE 공시 목록 조회 미완료')
    reports={(r['year'],r['quarter']):r for r in prior.get('reports',[])}
    sources=list({r['url']:r for r in sources}.values())
    for source in sorted(sources,key=lambda s:s['filed']):
        if source['filed']>asof:continue
        try:
            updates=zte_report(fetch(session,source['url'],offline),source['url'],source['year'],source['quarter'],source['filed'])
            for r in updates:reports[r['year'],r['quarter']]=r
        except (requests.RequestException,ValueError,OSError) as error:errors.append(f"{source['year']} Q{source['quarter']} 원문 조회·검토 필요 ({type(error).__name__})")
    for r in reviewed:
        if next(iter(r['fields'].values()))['filed']<=asof:reports.setdefault((r['year'],r['quarter']),r)
    rows=dart_accounts(list(reports.values()),asof)
    for row in rows:
        for ref in row['refs'].values():
            if ref.get('calculation')=='reported quarter' and ref.get('direct_pdf_page'):ref['pdf_page']=ref['direct_pdf_page']
    return dict(rows=rows,reports=list(reports.values()),source_errors=errors)


def equipment_document(key,metric,meta,cohort,fx):
    doc=document(key,metric,meta,cohort,fx)
    if metric=='capex':doc['name']=meta['name']+' · 자체 CAPEX'
    doc['source']='SEC IFRS·공식 IR' if meta.get('ifrs') else doc['source']
    doc['basis_details']=[dict(label='투자 연결 분야',value=meta['investment_link'])]+doc['basis_details']
    for detail in doc['basis_details']:
        if detail['label']=='환산·기간':detail['value']='USD 외 통화는 실제 실적 기간의 ECB 일별 평균환율로 환산합니다. 금액·차트·표에서 원통화를 확인할 수 있습니다. 장비사 자체 CAPEX는 공장·시험설비·소프트웨어 등 자체 투자로, 고객 통신사의 CAPEX·장비 주문액과 구분합니다.'
    if meta.get('source_review'):
        doc['basis_details'].append(dict(label='분기 원문 갱신',value=meta['source_review']))
    return doc


def collect(offline=False,full=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=load(META,{});state=load(OUT/'equipment_state.json',dict(companies={}))
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    def korean_job(key):
        return collect_dart(meta[key],state['companies'].get(key,{}),requests.Session(),asof,full)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={key:pool.submit(korean_job,key) for key,m in meta.items() if m.get('corp_code')} if not offline else {}
        for key,m in meta.items():
            prior=state['companies'].get(key,{})
            try:
                if m.get('corp_code'):
                    fresh=dict(prior,rows=dart_accounts(prior['reports'],asof)) if offline else jobs[key].result()
                elif m.get('cik'):
                    payload=json.loads(fetch(session,f'https://data.sec.gov/api/xbrl/companyfacts/CIK{m["cik"]:010d}.json',offline))
                    if m.get('minimum_end'):
                        payload=copy.deepcopy(payload)
                        for fact in payload['facts'].get('us-gaap',{}).values():
                            for unit,values in fact.get('units',{}).items():fact['units'][unit]=[f for f in values if f['end']>=m['minimum_end']]
                    fresh=dict(rows=ifrs_annual(payload,m,asof) if m.get('ifrs') else sec_accounts(payload,m,asof))
                    if m.get('ifrs'):
                        quarters,errors=european_quarters(key,session,asof,offline,prior)
                        fresh['rows']=merge_rows(fresh['rows'],quarters);fresh['source_errors']=errors
                    time.sleep(.2)
                else:fresh=collect_zte(session,asof,offline,prior)
                if not fresh['rows']:raise ValueError('no public financial history')
                state['companies'][key]=dict(prior,**fresh) if offline else dict(prior,**fresh,checked=asof,fetched=asof,status='ok')
                print(key,len(fresh['rows']),'periods',flush=True)
            except (requests.RequestException,ValueError,KeyError,OSError) as error:
                state['companies'][key]=dict(prior,checked=asof,status='최신 조회 미완료 · 기존 자료 유지 ('+type(error).__name__+')')
                print(key,'retained previous accounts:',type(error).__name__,flush=True)
    intervals=sorted({(meta[key]['currency'],r['start'],r['date']) for key,c in state['companies'].items() for r in c.get('rows',[]) if meta[key]['currency']!='USD'})
    previous=load(OUT/'equipment_fx.json',{});rates=None;raw=None;error=None
    try:raw=fetch(session,SOURCE,offline);rates=parse_rates(raw)
    except (requests.RequestException,ValueError,OSError):error='ECB feed unavailable; exact completed intervals retained'
    fx=build_snapshot(previous,intervals,rates,asof,hashlib.sha256(raw).hexdigest() if raw else None,error)
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'equipment_state.json',state);save(OUT/'equipment_fx.json',fx)
    for key,m in meta.items():
        for metric in METRICS:save(OUT/f'company_{key}_{metric}.json',equipment_document(key,metric,m,state['companies'][key],fx))
    print('Published 30 equipment cards;',len(fx['periods']),'FX intervals;',len(fx['missing']),'missing',flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--full-history',action='store_true');a=p.parse_args();collect(a.offline,a.full_history)

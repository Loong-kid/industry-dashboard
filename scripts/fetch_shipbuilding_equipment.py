"""Free OpenDART ship-engine/parts/aftermarket financials; native KRW + USD."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
import zipfile

import requests

from fetch_cpu_companies import save
from fetch_game_fx import SOURCE, parse_rates, build_snapshot
from fetch_quantum import document as financial_document
from quantum_sources import METRICS
from shipbuilding_equipment_sources import report, accounts, provisional, end

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/shipbuilding'
META=ROOT/'manual/shipbuilding-equipment/companies.json'
CACHE=ROOT/'.cache/shipbuilding-equipment'


def load(path, default):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else default


def api(session, name, key, **params):
    try:
        r=session.get('https://opendart.fss.or.kr/api/'+name,params=dict(crtfc_key=key,**params),timeout=40)
        r.raise_for_status()
        return r
    except requests.RequestException:
        # Do not expose the credential-bearing request URL through tracebacks.
        raise ValueError('OpenDART request unavailable') from None


def entities(session, key, meta):
    try:
        raw=api(session,'corpCode.xml',key).content
        with zipfile.ZipFile(io.BytesIO(raw)) as z:tree=ET.fromstring(z.read('CORPCODE.xml'))
        result={}
        for company,m in meta.items():
            matches=[r for r in tree.findall('list') if r.findtext('stock_code','').strip()==m['ticker']]
            if len(matches)!=1:raise ValueError('ambiguous ticker mapping')
            r=matches[0];name=r.findtext('corp_name')
            if name not in [m['name']]+m.get('aliases',[]):raise ValueError('issuer name changed; review required')
            result[company]=dict(corp_code=r.findtext('corp_code'),stock_code=m['ticker'],name=name)
        return result
    except (ValueError,ET.ParseError,zipfile.BadZipFile,KeyError):
        raise ValueError('OpenDART issuer registry unavailable or changed') from None


def public_get(session,url):
    p=CACHE/(hashlib.sha256(url.encode()).hexdigest()[:18]+'.bin')
    try:r=session.get(url,timeout=40)
    except requests.exceptions.SSLError:
        # Keep certificate verification enabled; some public Korean sites use
        # chains trusted by the OS bundle but absent from certifi's root set.
        system_bundle=Path('/etc/ssl/certs/ca-certificates.crt')
        if not system_bundle.exists():raise
        r=session.get(url,timeout=40,verify=str(system_bundle))
    r.raise_for_status();p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.content)
    return r.content


def preliminaries(session,key,entity,meta,asof,fs):
    payload=api(session,'list.json',key,corp_code=entity['corp_code'],bgn_de=asof[:4]+'0101',end_de=asof.replace('-',''),last_reprt_at='Y',page_count=100).json()
    if payload.get('status')=='013':return [],[]
    if payload.get('status')!='000':raise ValueError('provisional disclosure list unavailable')
    candidates=[r for r in payload['list'] if '영업(잠정)실적' in r['report_nm'] and ('연결재무제표' in r['report_nm'])==(fs=='CFS')][:3]
    rows=[];errors=[]
    for entry in candidates:
        receipt=entry['rcept_no']
        try:
            main=public_get(session,f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}').decode('utf8')
            if not any(name in main for name in [meta['name']]+meta.get('aliases',[])):raise ValueError('provisional issuer mismatch')
            values=re.findall(r'viewDoc\("'+receipt+r'",\s*"(\d+)",\s*"(\d+)",\s*"(\d+)",\s*"(\d+)",\s*"([A-Z]+)"',main)
            if len(set(values))!=1:raise ValueError('provisional document mapping changed')
            dcm,ele,offset,length,dtd=values[0]
            url=f'https://dart.fss.or.kr/report/viewer.do?rcpNo={receipt}&dcmNo={dcm}&eleId={ele}&offset={offset}&length={length}&dtd={dtd}'
            rows.append(provisional(public_get(session,url),receipt,fs,asof))
        except (requests.RequestException,ValueError,UnicodeError) as e:
            errors.append('잠정 공시 수치 확인 필요: '+receipt+' ('+type(e).__name__+')')
    return rows,errors


def collect_company(company,meta,entity,key,prior,asof,full):
    session=requests.Session();reports={(r['year'],r['quarter']):r for r in prior.get('reports',[])};errors=[]
    first=meta.get('first_year',2015) if full or not reports else int(asof[:4])-1
    for year in range(first,int(asof[:4])+1):
        for q,code in [(1,'11013'),(2,'11012'),(3,'11014'),(4,'11011')]:
            if end(year,q)>asof:continue
            try:
                for fs in ('CFS','OFS'):
                    payload=api(session,'fnlttSinglAcntAll.json',key,corp_code=entity['corp_code'],bsns_year=year,reprt_code=code,fs_div=fs).json()
                    save(CACHE/f'{company}-{year}-q{q}-{fs}.json',dict(status=payload.get('status'),list=payload.get('list',[])))
                    if payload.get('status')=='013':continue
                    if payload.get('status')!='000':raise ValueError('OpenDART statement unavailable')
                    reports[year,q]=report(payload['list'],year,q,entity['corp_code'],fs);break
            except (ValueError,KeyError) as e:
                errors.append(f'{year} Q{q} 정기 공시 조회·확인 필요 ({type(e).__name__})')
            time.sleep(.12)
        print(company,year,'checked',flush=True)
    expanded=dict(reports);filled=set()
    for r in sorted(reports.values(),key=lambda r:(r['year'],r['quarter'])):
        for comparative in r.get('comparatives',[]):
            k=comparative['year'],comparative['quarter']
            if k not in expanded:expanded[k]=comparative;filled.add(k)
    errors=[e for e in errors if not any(e.startswith(f'{year} Q{q} ') for year,q in filled)]
    rows=accounts(list(expanded.values()),asof)
    pending={r['date']:r for r in prior.get('provisional_rows',[])}
    try:
        fs=rows[-1]['fs_div'] if rows else 'CFS'
        fresh,issues=preliminaries(session,key,entity,meta,asof,fs);errors+=issues
        for r in fresh:pending[r['date']]=r
    except (ValueError,KeyError) as e:errors.append('잠정실적 목록 확인 미완료 ('+type(e).__name__+')')
    regular_dates={r['date'] for r in rows if r['kind']=='quarter'}
    pending={d:r for d,r in pending.items() if d not in regular_dates and d<=asof}
    rows=sorted(rows+list(pending.values()),key=lambda r:(r['date'],r['kind']))
    return dict(entity=entity,reports=list(reports.values()),provisional_rows=list(pending.values()),rows=rows,
                checked=asof,fetched=asof if rows else prior.get('fetched'),status='partial' if errors else 'ok',source_errors=errors)


def document(company,metric,meta,cohort,fx):
    doc=financial_document(company,metric,meta,cohort,fx)
    doc['source']='OpenDART·기업 공식 잠정 공시'
    for detail in doc['basis_details']:
        if detail['label']=='손익 기준':detail['value']='연결 재무제표를 우선하고, 연결 공시가 없는 기간은 별도 재무제표임을 메모에 명시합니다. 순이익은 지배주주 귀속이 아닌 전체 당기순손익입니다. 중단영업·지분법·금융상품 평가·일회성 항목 등이 포함될 수 있습니다. 연결/별도 기준이 다른 누적끼리는 차감하지 않습니다.'
        if detail['label']=='환산·기간':detail['value']='실제 실적 기간의 ECB 일별 원/USD 평균환율로 백만 USD 환산합니다. 원화 공시 금액·환율·관측 기간은 메모에 보존합니다. 4분기는 같은 연도·같은 연결/별도 기준의 연간 − 9개월 누적으로 계산하며, 연간을 4등분하지 않습니다. 잠정실적은 잠정 표시 후 정기 공시 확보 시 교체합니다.'
    for kind,view in doc['series_views'].items():
        relevant=[r for r in cohort.get('rows',[]) if r['kind']==kind and r.get(metric) is not None]
        for r in relevant:
            view['point_notes'][r['date']].append('재무제표: '+('연결' if r['fs_div']=='CFS' else '별도'))
            if r['refs'][metric].get('comparative'):view['point_notes'][r['date']].append('후속 정기 공시의 실제 비교기간 수치')
            if r.get('provisional'):view['point_notes'][r['date']].append('잠정실적 · 정기 공시에서 변경될 수 있음')
    doc.update({k:v for k,v in doc['series_views'][doc['default_view']].items() if k!='label'})
    return doc


def collect(offline=False,full=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=load(META,{});state=load(OUT/'equipment_state.json',dict(companies={}))
    session=requests.Session();key=os.getenv('DART_API_KEY');registry={};registry_error=None
    if not offline:
        try:
            if not key:raise ValueError('DART credential unavailable')
            registry=entities(session,key,meta)
        except ValueError:registry_error='OpenDART 법인 조회 미완료 · 기존 성공 자료 유지'
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={c:pool.submit(collect_company,c,m,registry[c],key,state['companies'].get(c,{}),asof,full) for c,m in meta.items()} if registry else {}
        for company,m in meta.items():
            old=state['companies'].get(company,{})
            if offline:
                if not old.get('rows'):raise ValueError('offline financial history unavailable')
                cohort=old
            elif registry_error:cohort=dict(old,checked=asof,status='partial',source_errors=[registry_error])
            else:
                try:cohort=jobs[company].result()
                except Exception as e:cohort=dict(old,checked=asof,status='partial',source_errors=['기업 공시 조회 미완료 ('+type(e).__name__+')'])
            state['companies'][company]=cohort
            print(company,len(cohort.get('rows',[])),'periods;',cohort.get('status'),'; '.join(cohort.get('source_errors',[])),flush=True)
    intervals=sorted({(r['currency'],r['start'],r['date']) for c in state['companies'].values() for r in c.get('rows',[])})
    previous=load(OUT/'equipment_fx.json',{});raw=None;rates=None;error=None
    if not offline:
        try:raw=public_get(session,SOURCE);rates=parse_rates(raw)
        except (requests.RequestException,ValueError):error='ECB unavailable; exact completed intervals retained'
    fx=previous if offline else build_snapshot(previous,intervals,rates,asof,hashlib.sha256(raw).hexdigest() if raw else None,error)
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'equipment_state.json',state);save(OUT/'equipment_fx.json',fx)
    for company,m in meta.items():
        for metric in METRICS:save(OUT/f'company_{company}_{metric}.json',document(company,metric,m,state['companies'][company],fx))
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--full-history',action='store_true');a=p.parse_args();collect(a.offline,a.full_history)

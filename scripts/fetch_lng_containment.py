"""Free DART / GTT IR histories for LNG containment technology and insulation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import io
import os
from pathlib import Path
import zipfile

import requests

from fetch_cpu_companies import save
from fetch_game_fx import SOURCE, parse_rates, build_snapshot
from fetch_quantum import document as financial_document
from fetch_shipbuilding_equipment import load, api, entities, expanded_accounts, document as korean_document
from shipbuilding_equipment_sources import report, end
from quantum_sources import METRICS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/natgas'
MANUAL=ROOT/'manual/lng-containment'
CACHE=ROOT/'.cache/lng-containment'


def collect_korean(company, meta, entity, key, previous, asof, full=False):
    session=requests.Session(); reports={(r['year'],r['quarter']):r for r in previous.get('reports',[])};errors=[]
    first=meta['first_year'] if full or not reports else int(asof[:4])-1
    for year in range(first,int(asof[:4])+1):
        for q,code in [(1,'11013'),(2,'11012'),(3,'11014'),(4,'11011')]:
            if end(year,q)>asof:continue
            try:
                for fs in ['CFS','OFS']:
                    payload=api(session,'fnlttSinglAcntAll.json',key,corp_code=entity['corp_code'],bsns_year=year,reprt_code=code,fs_div=fs).json()
                    save(CACHE/f'{company}-{year}-{q}-{fs}.json',dict(status=payload.get('status'),list=payload.get('list',[])))
                    if payload.get('status')=='013':continue
                    if payload.get('status')!='000':raise ValueError('statement unavailable')
                    reports[year,q]=report(payload['list'],year,q,entity['corp_code'],fs);break
            except (ValueError,KeyError):errors.append(f'{year} Q{q} 정기 공시 확인 필요')
        print(company,year,'checked',flush=True)
    rows,filled=expanded_accounts(list(reports.values()),asof)
    errors=[e for e in errors if not any(e.startswith(f'{y} Q{q} ') for y,q in filled)]
    # Preserve the actual full-report XML for business KPIs, not credentials.
    receipts=sorted({f['url'].split('rcpNo=')[-1] for r in reports.values() if r['year']>=2022 for f in r['fields'].values()})
    for receipt in receipts:
        path=CACHE/f'{company}-{receipt}.xml'
        if path.exists():continue
        try:
            raw=api(session,'document.xml',key,rcept_no=receipt).content
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names=[n for n in z.namelist() if n.lower().endswith('.xml')]
                chosen=next((n for n in names if n.startswith(receipt)),names[0])
                path.write_bytes(z.read(chosen))
        except (ValueError,zipfile.BadZipFile,IndexError,KeyError):
            print(company,receipt,'business XML unavailable',flush=True)
    return dict(entity=entity,reports=list(reports.values()),rows=rows,checked=asof,fetched=asof if rows else previous.get('fetched'),status='partial' if errors else 'ok',source_errors=errors)


def collect(offline=False,full=False,korean_only=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=load(MANUAL/'companies.json',{});state=load(OUT/'containment_state.json',dict(companies={}))
    CACHE.mkdir(parents=True,exist_ok=True)
    korean={c:m for c,m in meta.items() if m['currency']=='KRW'}
    key=os.getenv('DART_API_KEY');registry={};error=None
    if not offline:
        try:
            if not key:raise ValueError('no credential')
            registry=entities(requests.Session(),key,korean)
        except ValueError:error='OpenDART 법인 조회 미완료 · 이전 자료 유지'
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={c:pool.submit(collect_korean,c,m,registry[c],key,state['companies'].get(c,{}),asof,full) for c,m in korean.items()} if registry else {}
        for c,m in korean.items():
            old=state['companies'].get(c,{})
            if offline:
                rows,_=expanded_accounts(old.get('reports',[]),old.get('checked',asof));cohort=dict(old,rows=rows)
            elif error:cohort=dict(old,checked=asof,status='partial',source_errors=[error])
            else:
                try:cohort=jobs[c].result()
                except Exception as exc:cohort=dict(old,checked=asof,status='partial',source_errors=['조회 미완료 ('+type(exc).__name__+')'])
            state['companies'][c]=cohort
            print(c,len(cohort.get('rows',[])),'periods',cohort.get('status'),flush=True)
    if not korean_only:
        from lng_containment_sources import collect_gtt
        state['companies']['gtt']=collect_gtt(state['companies'].get('gtt',{}),asof,offline)
    intervals=sorted({(r['currency'],r['start'],r['date']) for c in state['companies'].values() for r in c.get('rows',[])})
    previous=load(OUT/'containment_fx.json',{});raw=None;rates=None;fx_error=None
    if not offline:
        try:
            response=requests.get(SOURCE,timeout=40);response.raise_for_status();raw=response.content;rates=parse_rates(raw)
        except (requests.RequestException,ValueError):fx_error='ECB unavailable; completed exact-period quotes retained'
    fx=previous if offline else build_snapshot(previous,intervals,rates,asof,hashlib.sha256(raw).hexdigest() if raw else None,fx_error)
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'containment_state.json',state);save(OUT/'containment_fx.json',fx)
    for c,cohort in state['companies'].items():
        if c not in meta:continue
        for metric in METRICS:
            doc=(korean_document if c in korean else financial_document)(c,metric,meta[c],cohort,fx)
            if c=='gtt':
                doc['source']='GTT 공식 연결 실적·IR'
                for item in doc['basis_details']:
                    if item['label']=='손익 기준':item['value']='영업이익은 IFRS 연결 손익계산서의 비경상 항목 포함 영업손익입니다. 회사 요약표의 EBIT·EBITDA를 대신 쓰지 않습니다. 순이익은 비지배지분 포함 연결 전체 당기순손익입니다.'
                    if item['label']=='환산·기간':item['value']='매출만 실제 분기별 공시 또는 같은 연도 누적 차감입니다. 손익은 공표된 H1과 FY−H1인 H2, 연간을 표시하며 분기 추정은 하지 않습니다. EUR 원금액·실제 보고기간의 ECB 평균환율을 메모에 보존합니다.'
            save(OUT/f'containment_{c}_{metric}.json',doc)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--korean-only',action='store_true');a=p.parse_args();collect(a.offline,a.full_history,a.korean_only)

"""Free SEC annual audits and original quarterly releases for FLNG / GLNG."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin

import pymupdf
import requests
from bs4 import BeautifulSoup

from fetch_cpu_companies import save
from fetch_quantum import document as financial_document
from lng_carrier_sources import accounts,annual_facts
from quantum_sources import METRICS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/natgas'
CACHE=ROOT/'.cache/lng-carriers'
MANUAL=ROOT/'manual/lng-carriers'
UA='industry-dashboard personal research wkorotk@gmail.com'


def load(path,fallback):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else fallback


def get(url,path):
    response=requests.get(url,headers={'User-Agent':UA},timeout=(8,35));response.raise_for_status()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(response.content)
    return response.content


def verify_pdf(raw,source):
    if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('reviewed original changed')
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        text=pdf[source['page']].get_text(sort=True)
    normal=lambda s:re.sub(r'\s+',' ',s).strip()
    if not all(normal(f['anchor']) in normal(text) for f in source['fields'].values()):raise ValueError('reviewed statement row changed')


def new_reports(company,asof,sources):
    year=int(asof[:4]);known={(s['year'],s['quarter']) for s in sources};known_urls={s['url'] for s in sources};issues=[]
    urls=['https://www.flexlng.com/category/quarterly-reports/'] if company=='flng' else [f'https://www.golarlng.com/investors/quarterly-reports/{y}.aspx' for y in [year,year-1]]
    found=False
    for url in urls:
        raw=get(url,CACHE/(company+'-ir-'+str(hashlib.sha256(url.encode()).hexdigest()[:8])+'.html'))
        soup=BeautifulSoup(raw,'html.parser')
        for a in soup.select('a[href]'):
            title=a.get_text(' ',strip=True);href=urljoin(url,a['href'])
            if not any(s in href.lower() for s in ['.pdf','cision.com','globenewswire.com']):continue
            match=re.search(r'Q([1-4])\s*[, -]?\s*(20\d{2})',title,re.I) if company=='flng' else re.search(r'(20\d{2})\s*Q([1-4])\s*Results',title,re.I)
            if not match:continue
            found=True
            y,q=(int(match[2]),int(match[1])) if company=='flng' else (int(match[1]),int(match[2]))
            if (y,q) not in known or href not in known_urls:
                if y>=year-1:issues.append(f'새 분기 공시 원문 검토 필요: {y} Q{q} · '+href)
    if not found:raise ValueError('issuer IR report index changed')
    return list(dict.fromkeys(issues))


def document(company,metric,meta,cohort):
    doc=financial_document(company,metric,meta,cohort,{})
    doc.update(id=f'carrier_{company}_{metric}',source='SEC 20-F·회사 공식 분기 실적')
    for b in doc['basis_details']:
        if b['label']=='손익 기준':b['value']='매출·영업손익·비지배지분 포함 연결 전체 순손익입니다. 조정 EBITDA·조정 순익·TCE 또는 Golar의 주주 귀속 순익으로 대체하지 않습니다. 중단영업·처분손익·파생상품 평가손익 등이 포함될 수 있습니다.'
        if b['label']=='환산·기간':b['value']='원문 백만 USD 그대로이며 환율 환산은 없습니다. 분기는 회사의 실제 분기 공시, 연간은 해당 회계연도의 최초 확보한 감사 연결 공시를 우선합니다. 감사 원자료가 없는 초기 연간은 회사의 감사 전 결산 발표임을 메모에 표시합니다. 최신 연도의 중단영업 재분류로 과거 전사 범위를 일괄 덮어쓰지 않습니다. 공시 누적에서 확인된 분기를 차감하는 경우 계산 출처를 함께 남깁니다.'
    issues={i['year']:i for i in cohort.get('reconciliation',[]) if i['metric']==metric}
    for kind,view in doc['series_views'].items():
        for row in cohort['rows']:
            if row['kind']!=kind or metric not in row:continue
            notes=view['point_notes'][row['date']];ref=row['refs'][metric]
            notes.append('회사 분기·결산 발표 · 감사 전 수치' if ref.get('unaudited') else 'SEC 감사 연결 실적')
            if row['year'] in issues:notes.append(issues[row['year']]['note'])
    if issues:doc['basis_details'].append(dict(label='분기·연간 비교',value='감사 조정 또는 사업 범위 재분류로 분기 합계와 연간이 다른 연도: '+', '.join(map(str,sorted(issues)))+'. 차트·표 메모의 원문 기준을 함께 확인하세요.'))
    doc.update({k:v for k,v in doc['series_views'][doc['default_view']].items() if k!='label'})
    return doc


def collect(offline=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    CACHE.mkdir(parents=True,exist_ok=True)
    meta=load(MANUAL/'companies.json',{});sources=load(MANUAL/'reports.json',[])
    state=load(OUT/'lng_carriers_state.json',dict(companies={}))
    for company,m in meta.items():
        old=state['companies'].get(company,{});own=[s for s in sources if s['company']==company]
        verified=set(old.get('verified_sources',[]));errors=[];annual=old.get('annual_sources',[])
        latest=max(s['filed'] for s in own)
        def verify(source):
            path=CACHE/source['file']
            # Reviewed immutable history is retained. Check the latest original
            # afresh so corrected/replaced issuer PDFs never become silent data.
            if source['sha256'] in verified and source['filed']<latest:return source['sha256']
            raw=path.read_bytes() if path.exists() else get(source['url'],path)
            verify_pdf(raw,source);return source['sha256']
        if not offline:
            try:
                facts=json.loads(get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{m["cik"]:010d}.json',CACHE/(company+'-facts.json')))
                annual=annual_facts(facts,m,asof)
                if not annual:raise ValueError('SEC annual history empty')
            except (requests.RequestException,ValueError,KeyError):errors.append('SEC 감사 연간 조회 미완료 · 이전 실적 유지')
            try:
                errors+=new_reports(company,asof,own)
            except (requests.RequestException,ValueError):errors.append('공식 분기 공시 목록 조회 미완료')
            # Fetch latest release every run; history is verified once.
            for s in own:
                if s['filed']==latest:
                    try:get(s['url'],CACHE/s['file'])
                    except requests.RequestException:errors.append('최신 분기 원문 조회 미완료')
            with ThreadPoolExecutor(max_workers=3) as pool:
                tasks=[(s,pool.submit(verify,s)) for s in own]
                for s,task in tasks:
                    try:verified.add(task.result())
                    except (requests.RequestException,ValueError,RuntimeError,OSError):errors.append(f"분기 원문 행·해시 확인 필요: {s['year']} Q{s['quarter']}")
        rows,reconciliation=accounts(own,annual,asof)
        cohort=dict(rows=rows,annual_sources=annual,reconciliation=reconciliation,verified_sources=sorted(verified),
            checked=old.get('checked',asof) if offline else asof,fetched=old.get('fetched') if offline or errors else asof,
            status='partial' if errors else 'ok',source_errors=list(dict.fromkeys(errors)))
        if offline:cohort.update(status=old.get('status','partial'),source_errors=old.get('source_errors',[]))
        state['companies'][company]=cohort
        for metric in METRICS:save(OUT/f'carrier_{company}_{metric}.json',document(company,metric,m,cohort))
        print(company,len(rows),'periods',cohort['status'],'; '.join(cohort['source_errors']),flush=True)
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'lng_carriers_state.json',state)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');collect(p.parse_args().offline)

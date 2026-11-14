"""Refresh movie calendars, box-office facts and film-exposed SEC companies."""
import argparse
import copy
import datetime as dt
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from cpu_business_history import SecClient
from fetch_cpu_companies import load,save,today
from movie_financials import SPECS,accounts,facts_from_company,cnk_instance,documents
from movie_sources import BASE,parse_schedule,parse_worldwide,combine

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/movies'
CACHE=ROOT/'.cache/movies'
UA='industry-dashboard personal research wkorotk@gmail.com'


def download(url,path,offline=False):
    if offline:
        if not path.exists():raise ValueError('Original source cache missing')
        return path.read_bytes()
    for attempt in range(3):
        try:
            response=requests.get(url,headers={'User-Agent':UA},timeout=35)
            response.raise_for_status();raw=response.content
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            return raw
        except requests.RequestException:
            if attempt==2:raise RuntimeError('Public source unavailable') from None
            time.sleep(attempt+1)


def collect_films(offline=False,full=False):
    checked=today();current=int(checked[:4]);previous=load(OUT/'release_index.json',dict(years=[]))
    reviewed=load(ROOT/'manual/movies/imax-reviewed.json',dict(films=[]))['films']
    years=list(range(2014,current+3)) if full or not previous['years'] else list(range(current-1,current+3))
    if offline:years=sorted({y['year'] for y in previous['years']} or set(years))
    meta={r['year']:r for r in previous['years']};errors=[]
    def fetch(year):
        schedule=parse_schedule(download(f'{BASE}/movies/release-schedule/{year}',CACHE/f'schedule_{year}.raw',offline),year)
        worldwide=parse_worldwide(download(f'{BASE}/box-office-records/worldwide/all-movies/cumulative/released-in-{year}',CACHE/f'world_{year}.raw',offline),year) if year<=current else []
        observed=meta.get(year,{}).get('fetched',checked) if offline else checked
        return year,combine(year,schedule,worldwide,reviewed,observed)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(fetch,year):year for year in years}
        for future in as_completed(futures):
            year=futures[future]
            try:
                _,doc=future.result()
                old=load(OUT/f'films_{year}.json',{})
                if old and len(doc['films'])<len(old['films'])*.7:raise ValueError('Release coverage unexpectedly regressed')
                save(OUT/f'films_{year}.json',doc)
                prior=meta.get(year,{})
                meta[year]=dict(year=year,file=f'films_{year}.json',films=len(doc['films']),imax=sum(f['imax_confirmed'] for f in doc['films']),
                    fetched=doc['fetched'],checked=prior.get('checked',checked) if offline else checked,ok=prior.get('ok',True) if offline else True)
                print('Film year',year,len(doc['films']),'films;',meta[year]['imax'],'IMAX confirmed',flush=True)
            except Exception as error:
                if year not in meta:raise
                meta[year]=dict(meta[year],checked=checked,ok=False,error_type=type(error).__name__)
                errors.append(year);print('Film year',year,'unavailable; kept prior verified data',flush=True)
    if not meta:raise ValueError('No movie calendar coverage')
    doc=dict(id='release_index',name='영화 개봉·흥행',fetched=max(y['fetched'] for y in meta.values()),updated=checked,default_year=current,
        release_market='북미(미국·캐나다)',years=sorted(meta.values(),key=lambda r:r['year'],reverse=True),
        description='개봉 일정은 북미 기준, 박스오피스는 작품의 누적 매출입니다. 영화사·극장·IMAX의 매출이나 이익과 구분합니다.',
        source='The Numbers 공개 개봉 일정·세계 흥행 표 / IMAX 공식 IR 확인',source_url=BASE+'/movies/release-schedule',
        collection_status=dict(ok=all(y['ok'] for y in meta.values()),checked=checked,failed_years=sorted(y['year'] for y in meta.values() if not y['ok'])))
    save(OUT/'release_index.json',doc)
    return doc


def collect_financials(offline=False,full=False):
    checked=today();previous=load(OUT/'financial_state.json',dict(companies={}))
    state=dict(id='financial_state',fetched=checked,checked=checked,companies={})
    client=SecClient(CACHE/'sec')
    for key,spec in SPECS.items():
        old=previous['companies'].get(key,{})
        try:
            if offline:
                payload=load(CACHE/(key+'_facts.json'),{})
                filings=load(CACHE/(key+'_filings.json'),[])
            else:
                payload=json.loads(client.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',refresh=True))
                save(CACHE/(key+'_facts.json'),payload)
                filings=client.filings(spec['cik'],checked);save(CACHE/(key+'_filings.json'),filings)
            facts=facts_from_company(payload,key)
            native=old.get('native',load(CACHE/'cnk_native.json',[]) if key=='cnk' else [])
            if key=='cnk':
                known={f['accn'] for f in native}
                pending=[f for f in filings if f['reportDate']>='2021-01-01' and (f['accessionNumber'] not in known or full)]
                for f in pending:
                    if offline:raise ValueError('Missing reviewed Cinemark legal-entity facts')
                    fresh=cnk_instance(client.instance(f),f)
                    native=[r for r in native if r['accn']!=f['accessionNumber']]+fresh
                    save(CACHE/'cnk_native.json',native)
                facts+=native
            rows,annual=accounts(key,facts,filings,checked)
            if len(rows)<45 or rows[0]['date']>'2014-06-01':raise ValueError('Historical movie accounts incomplete')
            latest=max(f['reportDate'] for f in filings if f['form'] in ('10-Q','10-K'))
            if rows[-1]['date']!=latest or not all(m in rows[-1] for m in ('revenue','profit','capex')):raise ValueError('Latest movie financial quarter incomplete')
            if old and (len(rows)<len(old['rows']) or rows[-1]['date']<old['rows'][-1]['date']):raise ValueError('Movie financial coverage regressed')
            cohort=dict(rows=rows,annual=annual,native=native,filings=filings,
                fetched=old.get('fetched',checked) if offline else checked,
                checked=old.get('checked',checked) if offline else checked,ok=old.get('ok',True) if offline else True)
        except Exception as error:
            if not old:raise
            cohort=copy.deepcopy(old);cohort.update(checked=checked,ok=False,error_type=type(error).__name__)
            print(key,'financial source unavailable; retained prior dataset',flush=True)
        state['companies'][key]=cohort
        for id,doc in documents(key,cohort).items():save(OUT/(id+'.json'),doc)
        print(key,len(cohort['rows']),'quarters;',len(cohort['annual']),'complete fiscal years;',cohort['ok'],flush=True)
    state['ok']=all(c['ok'] for c in state['companies'].values())
    state['fetched']=max(c['fetched'] for c in state['companies'].values())
    save(OUT/'financial_state.json',state)
    overview=dict(id='company_overview',name='영화 노출 기업의 사업 구조',fetched=checked,updated=checked,
        companies=[dict(id=key,name=spec['name'],scope=spec['scope'],note=spec['note']) for key,spec in SPECS.items()])
    save(OUT/'company_overview.json',overview)
    return state


def collect(offline=False,full=False,only='all'):
    CACHE.mkdir(parents=True,exist_ok=True)
    result={}
    if only in ('all','films'):result['films']=collect_films(offline,full)
    if only in ('all','financials'):result['financials']=collect_financials(offline,full)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--offline',action='store_true');p.add_argument('--full-history',action='store_true')
    p.add_argument('--only',choices=['all','films','financials'],default='all')
    a=p.parse_args();collect(a.offline,a.full_history,a.only)

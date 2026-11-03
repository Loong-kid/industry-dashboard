"""Semiconductor parts cleaning/coating service peers: original DART and SEC accounts."""
import argparse
import copy
from pathlib import Path
import requests
from collect_ring_sources import collect as collect_originals
from fetch_cosmetics import offline
from fetch_korea_equipment import normalize, build as build_korean
from fetch_rings import validate
from fetch_cpu_companies import load, save, today, parse_facts, parse_annual, build_company

ROOT=Path(__file__).resolve().parents[1]
META=ROOT/'manual/semicon-cleaning/companies.json'
CACHE=ROOT/'.cache/semicon-cleaning'
STATE=ROOT/'data/semicon/cleaning_state.json'


def global_spec(spec):
    spec=copy.deepcopy(spec)
    spec['revenue_description']=spec['scope']+' 매출입니다. 세정 서비스 단독 매출이 아닙니다.'
    spec['profit_description']=spec['scope']+' GAAP 영업이익입니다. 비GAAP 조정 영업이익·EBITDA와 구분합니다.'
    return spec


def build(meta,state):
    docs={}
    domestic=dict(meta,companies={k:v for k,v in meta['companies'].items() if k in state['companies']})
    for identifier,doc in build_korean(domestic,state).items():
        identifier=identifier.replace('company_kr_equipment_','company_cleaning_',1)
        doc['id']=identifier
        docs[identifier]=doc
    for key,spec in meta['global_companies'].items():
        if key not in state['companies']:continue
        for identifier,doc in build_company('cleaning_'+key,state['companies'][key],global_spec(spec)).items():
            doc['compact_tooltip']=True
            docs[identifier]=doc
    return docs


def collect(refresh=False,full_history=False,from_state=False):
    asof=today();meta=load(META,{});old=load(STATE,dict(companies={}))
    if from_state:
        state=copy.deepcopy(old)
    else:
        status=None
        if refresh:
            try:status=collect_originals(full_history,cache=CACHE,metadata=META)
            except ValueError:
                if any(k not in old['companies'] for k in meta['companies']):raise
                status={k:dict(ok=False) for k in meta['companies']}
        domestic=offline(meta,old,asof,status,cache=CACHE,normalize_report=normalize)
        state=dict(domestic,companies=dict(domestic['companies']))
        session=requests.Session()
        session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
        CACHE.mkdir(parents=True,exist_ok=True)
        for key,spec in meta['global_companies'].items():
            prior=old['companies'].get(key,{})
            try:
                if refresh:
                    r=session.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',timeout=45)
                    r.raise_for_status();payload=r.json();save(CACHE/(key+'_facts.json'),payload)
                else:payload=load(CACHE/(key+'_facts.json'),{})
                rows=parse_facts(payload,spec,asof);annual=parse_annual(payload,spec,asof)
                if not rows or not annual or any(not any(m in r for r in rows) for m in ('revenue','profit','capex')):raise ValueError('Incomplete SEC history')
                if prior.get('rows') and (rows[-1]['date']<prior['rows'][-1]['date'] or len(rows)<len(prior['rows'])):raise ValueError('SEC history regressed')
                state['companies'][key]=dict(rows=rows,annual=annual,checked=asof,fetched=asof,ok=True)
                print(key,len(rows),'quarters',len(annual),'fiscal years',flush=True)
            except Exception as error:
                if not prior:raise RuntimeError(key+': no successful original SEC history') from error
                state['companies'][key]=dict(copy.deepcopy(prior),checked=asof,ok=False)
                print(key,'retained last successful history:',type(error).__name__,flush=True)
        state.update(checked=asof,fetched=max(c['fetched'] for c in state['companies'].values()))
    for key in meta['companies']:validate(state['companies'][key],asof)
    docs=build(meta,state)
    if len(docs)!=15:raise ValueError('Missing cleaning company documents')
    save(STATE,state)
    for identifier,doc in docs.items():save(ROOT/'data/semicon'/(identifier+'.json'),doc)
    print('Published',len(docs),'cleaning company financial charts',flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true')
    args=p.parse_args();collect(args.refresh,args.full_history,args.from_state)

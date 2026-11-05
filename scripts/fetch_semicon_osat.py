"""Packaging/test service peers: original DART, SEC and ASE earnings statements."""
import argparse,copy
from pathlib import Path
import requests
from collect_ring_sources import collect as collect_dart
from collect_osat_sources import CACHE,META
from fetch_cpu_companies import load,save,today,parse_facts,parse_annual
from fetch_cosmetics import offline
from fetch_korea_equipment import normalize,first_period,build as build_korean
from fetch_rings import validate
from fetch_vrar import financial_document
from osat_sources import ase_annual,parse_ase_release,collect_ase_releases

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/semicon';STATE=OUT/'osat_state.json'

def build_ase(cache,spec,prior,asof):
    rows={r['date']:copy.deepcopy(r) for r in prior.get('rows',[])}
    releases=[]
    for entry in load(cache/'ase-releases.json',[]):
        if entry['filed']>asof:continue
        raw=(cache/entry['path']).read_bytes()
        for row in parse_ase_release(raw,entry):
            if row['date']<spec['minimum_start'] or row['date']>asof:continue
            # Later directly disclosed or retrospectively adjusted quarters win.
            old=rows.get(row['date'])
            if old and old['refs']['revenue']['filed']>entry['filed']:continue
            rows[row['date']]=row
        if 'ASE Technology' in raw.decode('utf8',errors='ignore'):releases.append(entry)
    annual=ase_annual(load(cache/'ase_facts.json',{}),spec,asof)
    result=sorted(rows.values(),key=lambda r:r['date'])
    if not result or not annual:raise ValueError('Incomplete ASE original history')
    if prior.get('annual') and annual[-1]['date']<prior['annual'][-1]['date']:raise ValueError('ASE annual history regressed')
    if prior.get('rows') and (result[-1]['date']<prior['rows'][-1]['date'] or len(result)<len(prior['rows'])):raise ValueError('ASE quarter history regressed')
    return dict(rows=result,annual=annual,releases=releases,checked=asof,fetched=asof,ok=True)

def build(meta,state):
    domestic=dict(meta,companies={k:v for k,v in meta['companies'].items() if k in state['companies']})
    docs={}
    for identifier,doc in build_korean(domestic,state).items():
        identifier=identifier.replace('company_kr_equipment_','company_osat_',1);doc['id']=identifier;docs[identifier]=doc
    for key,spec in meta['global_companies'].items():
        cohort=state['companies'][key];spec=dict(spec,source_type='sec')
        for metric in ['revenue','profit','capex']:
            doc=financial_document(key,metric,spec,cohort)
            identifier=f'company_osat_{key}_{metric}';doc['id']=identifier
            doc['series_views']={k:v for k,v in doc['series_views'].items() if v['series']}
            default='quarter' if 'quarter' in doc['series_views'] else 'annual'
            doc.update(copy.deepcopy(doc['series_views'][default]));doc.pop('label',None);doc['default_view']=default
            if key=='ase':
                doc['basis_details'].append(dict(label='ASE 공시 범위',value='2018년 통합 이후 분기부터 표시합니다. 연간은 IFRS 20-F, 분기 매출·영업이익은 공식 6-K 실적 발표의 실제 3개월 값입니다. 이후 발표의 수정 비교 수치를 반영하며 연간 1/4 추정은 하지 않습니다.'))
                if metric=='capex':
                    doc['name']='ASE · CAPEX (연간 총취득)'
                    doc['basis_details']=[r for r in doc['basis_details'] if r['label']!='분기 취득지출 공백']
                    doc['basis_details'].append(dict(label='분기·연간 지출 차이',value='이 카드는 20-F의 유형자산 총취득 현금지출입니다. 분기 실적 발표의 Net payments는 순지출이어서 합치지 않으며 아래 별도 그래프로 제공합니다. 분기 Equipment CAPEX의 USD 발표값을 임의 환율로 변환하지 않습니다.'))
            docs[identifier]=doc
        if key=='ase':
            net=copy.deepcopy(cohort);net['annual']=[]
            net['rows']=[r for r in net['rows'] if 'net_ppe_cash' in r]
            for row in net['rows']:row['capex']=row['net_ppe_cash'];row['refs']['capex']=row['refs']['net_ppe_cash']
            doc=financial_document(key,'capex',spec,net)
            identifier='company_osat_ase_net_ppe_cash';doc.update(id=identifier,wide_card=True,name='ASE · 유형자산 순현금지출 (분기)',description='ASE 전사 연결 분기 실적 발표의 Net payments for property, plant and equipment입니다. 총취득 CAPEX와 구분하며 연간 총취득 지출로 합산하지 않습니다. 설비 CAPEX USD 발표값을 환산한 수치가 아닙니다.')
            doc['series_views']={k:v for k,v in doc['series_views'].items() if v['series']}
            doc['basis_details']=[dict(label='현금지출 정의',value=doc['description']),dict(label='기간·통화',value='공식 6-K의 실제 3개월 TWD 백만 수치입니다. 순지출의 음수 현금흐름을 양수 지출로 표시합니다. Equipment CAPEX·총취득·인수대금과 구분합니다.'),dict(label='연결 범위',value=spec['scope']+'. '+spec['note'])]
            def relabel(view):
                view['series']={'유형자산 순현금지출':next(iter(view['series'].values()))};view['default_series']=['유형자산 순현금지출']
            relabel(doc)
            for view in doc['series_views'].values():relabel(view)
            docs[identifier]=doc
    return docs

def universe(meta,state):
    firms=[]
    for key,spec in {**meta['companies'],**meta['global_companies']}.items():
        co=state['companies'][key]
        firms.append(dict(spec,id=key,group='domestic' if key in meta['companies'] else 'global',currency=spec.get('currency','KRW'),quarter_start=co['rows'][0]['date'],quarter_end=co['rows'][-1]['date'],annual_start=co['annual'][0]['date'],ok=co['ok'],checked=co['checked']))
    return dict(id='osat_universe',reviewed=meta['reviewed'],fetched=state['fetched'],selection_basis=meta['selection_basis'],companies=firms)

def collect(refresh=False,full=False,from_state=False):
    asof=today();meta=load(META,{});old=load(STATE,dict(companies={}))
    if from_state:state=copy.deepcopy(old)
    else:
        status=None
        if refresh:
            try:status=collect_dart(full,cache=CACHE,metadata=META)
            except ValueError:
                if any(k not in old['companies'] for k in meta['companies']):raise
                status={k:dict(ok=False) for k in meta['companies']}
        state=offline(meta,old,asof,status,cache=CACHE,normalize_report=normalize)
        for key,spec in meta['companies'].items():first_period(state['companies'][key],spec);validate(state['companies'][key],asof)
        session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
        for key,spec in meta['global_companies'].items():
            prior=old['companies'].get(key,{})
            try:
                if refresh:
                    r=session.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',timeout=45);r.raise_for_status();save(CACHE/(key+'_facts.json'),r.json())
                    if key=='ase':collect_ase_releases(CACHE,full)
                if key=='ase':co=build_ase(CACHE,spec,prior,asof)
                else:
                    payload=load(CACHE/(key+'_facts.json'),{});rows=parse_facts(payload,spec,asof);annual=parse_annual(payload,spec,asof)
                    if not rows or not annual:raise ValueError('Empty SEC financial history')
                    if prior.get('rows') and (rows[-1]['date']<prior['rows'][-1]['date'] or len(rows)<len(prior['rows'])):raise ValueError('SEC quarter history regressed')
                    co=dict(rows=rows,annual=annual,ok=True,checked=asof,fetched=asof)
                state['companies'][key]=co;print(key,len(co['rows']),'quarters,',len(co['annual']),'annual periods',flush=True)
            except Exception as error:
                if not prior:raise RuntimeError(key+': no successful original financial history') from error
                state['companies'][key]=dict(copy.deepcopy(prior),ok=False,checked=asof);print(key,'retained successful history',type(error).__name__,flush=True)
        state.update(checked=asof,fetched=max(co['fetched'] for co in state['companies'].values()))
    docs=build(meta,state)
    if len(docs)!=25:raise ValueError('Incomplete OSAT chart set')
    save(STATE,state);save(OUT/'osat_universe.json',universe(meta,state))
    for identifier,doc in docs.items():save(OUT/(identifier+'.json'),doc)
    print('Published',len(docs),'packaging and test service charts',flush=True)
    return state

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true');a=p.parse_args();collect(a.refresh,a.full_history,a.from_state)

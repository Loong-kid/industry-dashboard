"""Twenty Korean semiconductor suppliers, preserving issuer and fiscal scope."""
import argparse
import copy
import datetime as dt
from pathlib import Path

from collect_ring_sources import collect as collect_originals
from fetch_cosmetics import offline
from fetch_korea_equipment import normalize as normalize_equipment,first_period,build as build_equipment
from fetch_rings import validate
from fetch_cpu_companies import load,save,today
from ring_financial_sources import accounts

ROOT=Path(__file__).resolve().parents[1]
META=ROOT/'manual/semicon-supplychain/companies.json'
CACHE=ROOT/'.cache/semicon-supplychain'
STATE=ROOT/'data/semicon/supplychain_state.json'


def normalize(items,year,q,corp,fs,spec):
    minimum=spec.get('minimum_source_filed')
    if year<spec.get('minimum_primary_year',0):
        return dict(year=year,quarter=q,fs_div=fs,fields={},comparatives=[])
    if minimum:
        receipts=[r.get('rcept_no','') for r in items if r.get('rcept_no')]
        if receipts and max(receipts)<minimum.replace('-',''):
            return dict(year=year,quarter=q,fs_div=fs,fields={},comparatives=[])
    result=normalize_equipment(items,year,q,corp,fs,spec)
    start=spec.get('first_period_start')
    if start:
        # A later filing can be the only available source for a spin-off's
        # first three months. YTD == quarter is legitimate in that period.
        for report in [result]+result.get('comparatives',[]):
            if report['year']!=int(start[:4]):continue
            fields=report['fields']
            for metric in ('revenue','profit'):
                field=fields.get(metric,{})
                end=field.get('end')
                if end and field.get('start')==start and 75<=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days+1<=105 and field.get('ytd') is not None:
                    field['value']=field['ytd'];field.pop('duration_note',None)
    if minimum:
        # Reverse mergers: only the operating company's post-merger filings
        # and their explicitly restated comparative periods are eligible.
        for report in [result]+result.get('comparatives',[]):
            report['fields']={m:f for m,f in report['fields'].items() if f['filed']>=minimum}
    return result


def finalize(co,spec):
    # Empty SPAC shells must not win the CFS/OFS scope selection for a genuine
    # operating-company comparative period in a subsequent merger filing.
    eligible=[r for r in co.get('reports',[]) if all(m in r['fields'] for m in ('revenue','profit'))]
    if eligible:
        co.update(accounts(eligible,today()));co['reports']=eligible
    first_period(co,spec)
    start=spec.get('first_period_start')
    if start:
        sources=[r for report in eligible for r in [report]+report.get('comparatives',[])]
        for row in co['rows']:
            if 'capex' in row or not 75<=(dt.date.fromisoformat(row['date'])-dt.date.fromisoformat(start)).days+1<=105:continue
            matches=[r['fields']['capex'] for r in sources if (r['year'],r['quarter'],r['fs_div'])==(row['year'],row['quarter'],row['fs_div']) and r['fields'].get('capex',{}).get('start')==start and r['fields']['capex'].get('ytd') is not None]
            if matches:
                field=max(matches,key=lambda f:f['filed'])
                row['capex']=field['ytd'];row['refs']['capex']=dict(field,components=[copy.deepcopy(field)],calculation='reported first three-month fiscal cash flow after spin-off')
        # A May/November spin-off's first 2-month stub is not a full Q2/Q4.
        co['rows']=[r for r in co['rows'] if f'{r["year"]}-{r["quarter"]*3-2:02d}-01'>=start]
    validate(co,today())


def documents(meta,state):
    docs={}
    for identifier,doc in build_equipment(meta,state).items():
        identifier=identifier.replace('company_kr_equipment_','company_supplychain_',1);doc['id']=identifier
        key=identifier.removeprefix('company_supplychain_').rsplit('_',1)[0]
        spec=meta['companies'][key];co=state['companies'][key]
        for kind,view in doc['series_views'].items():
            rows=co['annual' if kind=='annual' else 'rows']
            lookup={(r['year'],r.get('quarter')):r for r in rows}
            start=spec.get('first_period_start','')
            stub_year=int(start[:4]) if start and not start.endswith('01-01') else None
            def compare(row,year,quarter):
                previous=lookup.get((year,quarter))
                if not previous or previous['fs_div']!=row['fs_div']:return None
                if kind=='annual' and (row['year']==stub_year or year==stub_year):return None
                return previous['date']
            view['comparison_dates']={r['date']:dict(year_ago=compare(r,r['year']-1,r.get('quarter')),
                quarter_ago=compare(r,r['year']-(r['quarter']==1),(r['quarter']-2)%4+1) if kind=='quarter' else None) for r in rows}
        doc['basis_details'][0]['label']='공정·제품 역할'
        doc['basis_details'].append(dict(label='SPAC·분할 이력',value=spec['note']))
        default=doc['default_view'];doc.update(copy.deepcopy(doc['series_views'][default]));doc.pop('label',None)
        docs[identifier]=doc
    return docs


def overview(meta,state):
    mixes=load(ROOT/'manual/semicon-supplychain/business-mix.json',dict(companies={}))
    companies=[]
    for key,spec in meta['companies'].items():
        co=state['companies'][key];latest=next(r for r in reversed(co['rows']) if 'revenue' in r and 'profit' in r)
        capex=next((r for r in reversed(co['rows']) if 'capex' in r),None)
        companies.append(dict(spec,id=key,valuation_id='supplychain_'+key,
            annual_start=co['annual'][0]['date'],quarter_start=co['rows'][0]['date'],latest=latest,
            latest_capex=capex,ok=co['ok'],checked=co['checked'],fetched=co['fetched'],
            business_mix=mixes['companies'].get(key)))
    return dict(id='supplychain_overview',name='국내 소부장 추가 기업 · 사업 범위와 실적',
        fetched=state['fetched'],updated=max(c['latest']['date'] for c in companies),
        reviewed=meta['reviewed'],selection_basis=meta['selection_basis'],companies=companies)


def collect(refresh=False,full_history=False,from_state=False):
    meta=load(META,{});old=load(STATE,dict(companies={}));asof=today();status=None
    if refresh:
        try:status=collect_originals(full_history,cache=CACHE,metadata=META)
        except ValueError:
            if any(k not in old['companies'] for k in meta['companies']):raise
            status={k:dict(ok=False) for k in meta['companies']}
    state=copy.deepcopy(old) if from_state else offline(meta,old,asof,status,cache=CACHE,normalize_report=normalize)
    for key,spec in meta['companies'].items():finalize(state['companies'][key],spec)
    docs=documents(meta,state)
    if len(docs)!=60:raise ValueError('Expected sixty financial chart documents')
    save(STATE,state)
    for identifier,doc in docs.items():save(ROOT/'data/semicon'/(identifier+'.json'),doc)
    save(ROOT/'data/semicon/supplychain_overview.json',overview(meta,state))
    print('Published 20 companies and',len(docs),'financial charts',flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true')
    a=p.parse_args();collect(a.refresh,a.full_history,a.from_state)

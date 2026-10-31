"""US-headquartered hyperscalers' GLOBAL accounts and disclosed cloud metrics."""
import argparse,copy,datetime as dt,json,time
from pathlib import Path

import requests

from cpu_business_history import SecClient
from fetch_cpu_companies import load,save,parse_facts,parse_annual,TAGS
from us_datacenter_sources import parse_instance
from us_datacenter_xai import collect_xai
from us_datacenter_presentations import comparison_document,METRICS as COMPARISON_METRICS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/datacenter';CACHE=ROOT/'.cache/us-datacenter'
CORE_TAGS=dict(TAGS,lease_principal=['FinanceLeasePrincipalPayments'],lease_additions=['RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability'])
METRICS={'revenue':'전사 매출','cloud_revenue':'클라우드 매출','cloud_share':'클라우드 매출 비중','profit':'전사 영업이익','cloud_profit':'클라우드 영업이익','capex':'전사 현금 CAPEX','capex_extra':'리스 반영 투자 지표'}
XAI_METRICS={'segment_revenue':'AI/SI 매출','segment_profit':'AI/SI 영업이익','segment_share':'SpaceX 매출 대비 비중','segment_capex':'AI/SI CAPEX'}


def metrics_for(key,meta):
    if key=='xai':return ['revenue','profit','capex',*XAI_METRICS]
    return [m for m in METRICS if not (m=='capex_extra' and not meta.get('capex_extra')) and not (key=='meta' and m.startswith('cloud_'))]


def fiscal_payload(payload,meta):
    # Amazon reports rolling TTM capex alongside fiscal cash flows. A TTM
    # observation ending in March must not become a separate fiscal year.
    payload=copy.deepcopy(payload)
    for tag in payload['facts']['us-gaap'].values():
        for unit,values in tag.get('units',{}).items():
            tag['units'][unit]=[f for f in values if not f.get('start') or
                (dt.date.fromisoformat(f['end'])-dt.date.fromisoformat(f['start'])).days<330 or
                f['start'][5:]==f"{meta['fiscal_start']:02d}-01"]
    return payload


def normalized(rows):
    result=[]
    for source in rows:
        r=copy.deepcopy(source)
        if not r.get('start'):r['start']=next(iter(r['refs'].values()))['start']
        result.append(r)
    return result


def merge_business(core,cloud):
    rows=copy.deepcopy(core);index={(r['start'],r['date']):r for r in rows}
    for r in cloud:
        target=index.get((r['start'],r['date']))
        if target is None:continue
        for field in ('cloud_revenue','cloud_profit'):
            if field in r:target[field]=r[field];target['refs'][field]=r['refs'][field]
    for r in rows:
        if r.get('cloud_revenue') is not None and r.get('revenue',0)>0:
            r['cloud_share']=r['cloud_revenue']/r['revenue']*100
            if not 0<=r['cloud_share']<=100.001:raise ValueError('Cloud revenue exceeds consolidated revenue')
            r['refs']['cloud_share']=dict(r['refs']['cloud_revenue'],calculation='same actual period cloud revenue / consolidated revenue × 100',
                components=[r['refs']['cloud_revenue'],r['refs']['revenue']])
    return rows


def parse_business(fields,meta,asof):
    merged=[[],[]]
    for field,values in fields.items():
        alias='profit' if field=='cloud_profit' else 'revenue'
        payload=fiscal_payload(dict(cik=meta['cik'],facts={'us-gaap':{'CloudObservation':dict(units={'USD':values})}}),meta)
        for i,parser in enumerate((parse_facts,parse_annual)):
            rows=normalized(parser(payload,meta,asof,{alias:['CloudObservation']}))
            for r in rows:r[field]=r.pop(alias);r['refs'][field]=r['refs'].pop(alias)
            merged[i]+=rows
    result=[]
    for group in merged:
        by={}
        for r in group:
            target=by.setdefault((r['start'],r['date']),dict(r,refs=dict(r['refs'])))
            for field in ('cloud_revenue','cloud_profit'):
                if field in r:target[field]=r[field];target['refs'][field]=r['refs'][field]
        result.append(sorted(by.values(),key=lambda r:r['date']))
    return result


def extra_capex(rows,meta):
    field=meta.get('capex_extra')
    if not field:return
    for r in rows:
        if r.get('capex') is None or r.get(field) is None:continue
        a,b=r['refs']['capex'],r['refs'][field]
        # Only combine the exact same reported duration; never combine stocks
        # of lease liabilities with cash investment flows.
        if (a['start'],a['end'])!=(b['start'],b['end']):continue
        r['capex_extra']=r['capex']+r[field]
        r['refs']['capex_extra']=dict(a,components=[a,b],calculation='cash PP&E + '+field)


def document(key,metric,meta,cohort):
    identifier=f'us_dc_{key}_{metric}';title={**METRICS,**XAI_METRICS}[metric]
    card_title=title;company_name=meta.get('short_name',meta['name'])
    if key=='xai':company_name='xAI' if metric.startswith('segment_') else 'SpaceX'
    if metric in ('cloud_revenue','cloud_profit') and meta.get('cloud_name'):title+=' · '+meta['cloud_name']
    if metric=='capex_extra':title=meta['capex_extra_name'];card_title=title
    unavailable=(key=='meta' and metric.startswith('cloud_')) or (metric=='cloud_profit' and meta.get('cloud_profit_note'))
    if unavailable:
        note=meta.get('cloud_profit_note') if metric=='cloud_profit' and key!='meta' else 'Meta에는 외부 고객에게 판매하는 퍼블릭 클라우드 사업이 없어 이 지표는 해당 없음입니다. 매출·비중·이익을 0으로 계산하지 않습니다.'
        return dict(id=identifier,name=company_name+' · '+card_title,disclosure_status='not_disclosed',note=note,
            source='SEC · 기업 공식 공시',source_url=cohort['rows'][-1]['refs']['profit']['url'],updated=cohort['checked'],fetched=cohort['fetched'])
    views={}
    for kind,label in [('rows','분기'),('annual','연간')]:
        all_rows=cohort[kind];valid=[r for r in all_rows if r.get(metric) is not None]
        first=valid[0]['date'] if valid else '9999';last=valid[-1]['date'] if valid else ''
        rows=[r for r in all_rows if first<=r['date']<=last]
        dates={r['date']:r for r in rows}
        # Cloud histories start at their first real disclosure; gaps remain null.
        sources={};notes={}
        for r in valid:
            ref=r['refs'][metric];components=ref.get('components',[])
            sources[r['date']]=dict(url=ref['url'],label=f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else ''),
                supporting_sources=[dict(url=c['url'],label=c['start']+' ~ '+c['end']) for c in components],source_separator=' / ' if metric in ('cloud_share','segment_share') else ' + ' if metric=='capex_extra' else ' − ')
            notes[r['date']]=[r['start']+' ~ '+r['date'],ref['tag'],ref.get('calculation','reported'),
                ('매출 비중 = 동일 기간 클라우드 매출 ÷ 전사 매출 × 100' if metric=='cloud_share' else '매출 비중 = 동일 기간 AI/SI 매출 ÷ SpaceX 매출 × 100' if metric=='segment_share' else '글로벌 연결/공시 사업 범위 · 미국 지역 단독이 아님')]
            if metric=='cloud_share':notes[r['date']].append(f"클라우드 {r['cloud_revenue']:,.3f} / 전사 {r['revenue']:,.3f} × 100 = {r['cloud_share']:,.4f}%")
            if metric=='segment_share':notes[r['date']].append(f"AI/SI {r['segment_revenue']:,.3f} / SpaceX {r['revenue']:,.3f} × 100 = {r['segment_share']:,.4f}%")
            if metric=='capex_extra':notes[r['date']].append(f"현금 PP&E {r['capex']:,.3f} + {meta['capex_extra']} {r[meta['capex_extra']]:,.3f} = {r['capex_extra']:,.3f} 백만 USD")
        lookup={(r['year'],r.get('quarter')):r['date'] for r in rows}
        views['quarter' if kind=='rows' else 'annual']=dict(label=label,frequency='quarterly' if kind=='rows' else 'yearly',
            frequency_label=label+' · 실제 회계기간',quarter_labels=kind=='rows',year_labels=kind=='annual',annual_axis=kind=='annual',
            period_labels={r['date']:f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '') for r in rows},
            series={title:[[d,dates[d].get(metric)] for d in sorted(dates)]},point_sources=sources,point_notes=notes,
            source_url=valid[-1]['refs'][metric]['url'] if valid else meta['source_url'],updated=last,
            quarterly_revenue_summary=kind=='rows' and metric in ('revenue','cloud_revenue','capex','capex_extra','segment_revenue','segment_capex'),quarterly_profit_summary=kind=='rows' and metric in ('profit','cloud_profit','segment_profit'),
            comparison_dates={r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),r['quarter']-1 or 4))) for r in rows} if kind=='rows' else {},
            change_mode='none',empty_message='공시된 실제 '+label+' 자료를 아직 확보하지 못했습니다. 미공개 기간을 추정하거나 0으로 채우지 않습니다.')
    healthy=cohort['core_ok'] and (cohort.get('cloud_ok',True) if metric.startswith('cloud_') else True)
    scope=meta['capex_extra_note'] if metric=='capex_extra' else meta['note']
    return dict(id=identifier,name=company_name+' · '+card_title,unit='%' if metric in ('cloud_share','segment_share') else 'USD 백만',company_kpi=True,compact_ticks=True,span_gaps=False,
        description=meta['scope'],source='SEC · 공식 연결·사업 공시',fetched=cohort['fetched'],
        collection_status=dict(ok=healthy,checked=cohort['checked'],message='공시 조회 완료' if healthy else '일부 조회·새 공시 검토 필요 · 기존 이력 유지'),
        basis_details=[dict(label='매출·영업이익·투자 범위',value=scope),dict(label='지역·데이터센터 CAPEX',value='미국 본사 기업의 글로벌 실적입니다. 미국 내 데이터센터 수·위치·용량 또는 미국 데이터센터 전용 CAPEX를 뜻하지 않습니다. CAPEX는 실제 현금 PP&E 취득액을 공통 투자 대리지표로 표시하며 회사별 리스 반영 지표는 따로 구분합니다. 미래 투자 계획·리스 약정·가이던스는 실제 지출에 합산하지 않습니다.'),
            dict(label='회계기간·비율',value='실제 회사 결산일과 동일 기간 공시를 사용합니다. 연간은 완결 회계연도 공시이며 클라우드 비중은 연간 클라우드 매출 / 연간 전사 매출입니다. 분기 비중을 평균하지 않습니다. 사업 재분류·공통비 배분·재작성 때문에 예전 분기 합계와 최근 연간이 다를 수 있습니다.'),
            dict(label='조회 상태',value=' / '.join(cohort.get('errors',[])) or cohort['checked'])],
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})


def collect(full=False,offline=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=load(ROOT/'manual/us-datacenter/companies.json',{})
    state=load(OUT/'us_hyperscalers_state.json',dict(companies={}))
    client=SecClient(CACHE/'sec')
    for key,spec in meta.items():
        old=state['companies'].get(key,{})
        if key=='xai':
            state['companies'][key]=collect_xai(spec,old,client,asof,full,offline)
            print('xai',len(state['companies'][key]['rows']),'quarters;',len(state['companies'][key]['annual']),'years;',len(state['companies'][key]['errors']),'warnings',flush=True)
            continue
        errors=copy.deepcopy(old.get('errors',[])) if offline else []
        core_ok=old.get('core_ok',True) if offline else True;cloud_ok=old.get('cloud_ok',True) if offline else True
        try:
            path=CACHE/(key+'_facts.json')
            if offline or full and path.exists():payload=load(path,{})
            else:payload=json.loads(client.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',refresh=True));save(path,payload)
            payload=fiscal_payload(payload,spec)
            rows=normalized(parse_facts(payload,spec,asof,CORE_TAGS));annual=normalized(parse_annual(payload,spec,asof,CORE_TAGS))
            rows=[r for r in rows if 'revenue' in r]
            if key=='googl' and rows[0]['date']>'2014-03-31':
                cutoff=rows[0]['date']
                legacy=[copy.deepcopy(r) for r in old.get('core_rows',[]) if r['date']<cutoff]
                if not legacy or full:
                    legacy_spec=dict(spec,cik=1288776)
                    legacy_payload=json.loads(client.get('https://data.sec.gov/api/xbrl/companyfacts/CIK0001288776.json'))
                    legacy=[r for r in normalized(parse_facts(fiscal_payload(legacy_payload,legacy_spec),legacy_spec,asof,CORE_TAGS)) if 'revenue' in r and r['date']<cutoff]
                rows=sorted(legacy+rows,key=lambda r:r['date'])
            if any(not any(m in r for r in rows) for m in ('revenue','profit','capex')):raise ValueError('Incomplete consolidated history')
            if old.get('core_rows') and (rows[-1]['date']<old['core_rows'][-1]['date'] or len(rows)<len(old['core_rows'])):raise ValueError('Consolidated history regressed')
        except Exception as e:
            if not old.get('core_rows'):raise RuntimeError(key+' has no verified consolidated accounts') from e
            rows=copy.deepcopy(old['core_rows']);annual=copy.deepcopy(old['core_annual']);core_ok=False;errors.append('전사 공시 조회 실패 · '+type(e).__name__)
        fields=copy.deepcopy(old.get('fields',{}));known=set(old.get('filings',[]))
        if key!='meta' and not offline:
            try:
                filings=[f for f in client.filings(spec['cik'],asof) if f['form'] in ('10-K','10-Q') and f['reportDate']>='2014-01-01']
                pending=[f for f in filings if full or f['accessionNumber'] not in known]
                print(key,len(pending),'cloud filings to read',flush=True)
                for i,f in enumerate(pending):
                    try:
                        fresh=parse_instance(client.instance(f),key,spec,f,asof)
                        threshold='2022-09-01' if key=='orcl' else '2022-01-01'
                        if not fresh and f['reportDate']>=threshold:raise ValueError('New report has no mapped cloud facts')
                        for field,values in fresh.items():
                            all_values=fields.get(field,[])+values
                            unique={(r['start'],r['end'],r['accn'],r['source_tag']):r for r in all_values}
                            fields[field]=sorted(unique.values(),key=lambda r:(r['end'],r['start'],r['filed']))
                        known.add(f['accessionNumber'])
                    except Exception as e:cloud_ok=False;errors.append(f['filingDate']+' 클라우드 공시 검토 필요 · '+type(e).__name__)
                    if (i+1)%10==0:print(key,'read',i+1,'/',len(pending),flush=True)
            except Exception as e:cloud_ok=False;errors.append('클라우드 목록 조회 실패 · '+type(e).__name__)
        cloud_rows,cloud_annual=parse_business(fields,spec,asof) if fields else ([],[])
        if key!='meta' and not any('cloud_revenue' in r for r in cloud_rows):raise RuntimeError(key+' has no verified cloud revenue')
        combined=merge_business(rows,cloud_rows);combined_annual=merge_business(annual,cloud_annual)
        extra_capex(combined,spec);extra_capex(combined_annual,spec)
        cohort=dict(core_rows=rows,core_annual=annual,fields=fields,filings=sorted(known),rows=combined,annual=combined_annual,
            core_ok=core_ok,cloud_ok=cloud_ok,errors=errors,checked=old.get('checked',asof) if offline else asof,
            fetched=old.get('fetched',asof) if offline or not core_ok else asof)
        state['companies'][key]=cohort;save(OUT/'us_hyperscalers_state.json',state)
        print(key,len(combined),'quarters',len(combined_annual),'years;',len(cloud_rows),'cloud quarters; warnings',len(errors),flush=True)
    for key,spec in meta.items():
        for metric in metrics_for(key,spec):
            save(OUT/f'us_dc_{key}_{metric}.json',document(key,metric,spec,state['companies'][key]))
    for metric in COMPARISON_METRICS:
        comparison=comparison_document(metric,meta,state['companies']);save(OUT/(comparison['id']+'.json'),comparison)
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'us_hyperscalers_state.json',state)
    print('Published',sum(len(metrics_for(k,s)) for k,s in meta.items())+len(COMPARISON_METRICS),'hyperscaler metric cards',flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--full-history',action='store_true');p.add_argument('--offline',action='store_true')
    args=p.parse_args();collect(args.full_history,args.offline)

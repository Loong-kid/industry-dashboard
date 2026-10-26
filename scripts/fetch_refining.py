"""Consolidated refiner financial histories, retaining currency and source scope."""
import argparse
import copy
import json
import hashlib
from pathlib import Path

from collect_refining_sources import collect as download, CACHE
from fetch_cpu_companies import (build_company, load, parse_facts, parse_annual,
                                 save, today)
from fetch_oil import merge_rows
from telecom_sources import dart_report, dart_accounts
from refining_sources import statement_facts, reported_accounts

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/oil'
STATE=OUT/'refining_state.json'
METRICS=('revenue','profit','capex')
SPECS={
    'vlo':dict(name='Valero · VLO',cik=1035002,fiscal_start=1,
        scope='전사 연결 · 정유·재생디젤·에탄올 포함',
        note='Valero 연결 전체 실적입니다. Refining 단독 매출·손익·투자가 아닙니다. CAPEX는 현금흐름표의 유형자산 현금취득이며, 정기보수·촉매·비연결 JV 투자 등을 더한 회사 발표 Capital investments와 구분합니다.'),
    'mpc':dict(name='Marathon Petroleum · MPC',cik=1510295,fiscal_start=1,
        scope='전사 연결 · Refining & Marketing·MPLX 미드스트림 포함',
        note='Marathon Petroleum은 Marathon Oil과 다른 회사입니다. MPLX 미드스트림을 포함한 연결 실적이며 정유 단독 수치가 아닙니다. Andeavor 인수와 Speedway 매각·중단영업 재분류 등 연결 범위 변화를 포함합니다. CAPEX는 현금흐름표 유형자산 취득으로 회사 발표 투자 계획과 범위가 다릅니다.'),
    'psx':dict(name='Phillips 66 · PSX',cik=1534701,fiscal_start=1,
        scope='전사 연결 · 정유·미드스트림·화학·마케팅·재생연료 포함',
        note='Phillips 66 전사 연결 실적입니다. 정유 단독 실적이 아니며 DCP 편입 등 연결 범위 변화를 포함합니다. 화학 JV의 지분법 손익은 연결 재무제표 처리에 따릅니다. CAPEX는 현금흐름표 유형자산 현금취득이며 비연결 JV 투자·기업 인수 대금과 구분합니다.'),
    'soil':dict(name='S-Oil · 010950',fiscal_start=1,
        scope='전사 연결 · 정유·석유화학·윤활 포함 · 원화',
        note='S-Oil 연결 전체 매출·영업이익이며 정유 부문만의 실적이 아닙니다. CAPEX는 현금흐름표의 유형자산 취득 현금지출로 무형자산 취득과 기업 인수는 제외합니다. 2014년과 API에 없는 2015년 분기는 회사 공식 연결 재무제표 PDF를 직접 대조하고 이후는 OpenDART 연결 공시를 사용합니다. 미국 기업의 USD와 합산하지 않습니다.'),
}
for spec in SPECS.values():
    spec.update(revenue_description='회사 전체 연결 매출입니다. 정유 단독 매출이 아니며 인수·매각에 따른 연결 범위 변화를 포함합니다.',
                profit_description='회사 전체 연결 영업이익입니다. 정유 부문 손익·조정 EBITDA와 구분합니다.',
                capex_description='현금흐름표의 유형자산 취득 현금지출입니다. 회사별 투자 계획·정기보수·비연결 JV 투자를 포함한 발표 CAPEX와 기준이 다를 수 있습니다.',
                profit_label='연결 영업이익',capex_label='유형자산 현금취득')
SPECS['vlo']['note']+=' 현금 CAPEX는 별도 표시된 연결 VIE의 유형자산 현금취득을 합산합니다. 매출은 원문 기준으로 유류세 포함·제외 표시의 시대별 변경에 유의해야 합니다.'
SPECS['mpc']['note']+=' 매출은 원문 Sales and other operating revenues에 별도 표시된 특수관계자 매출을 더한 연결 매출입니다. 과거 유류세 포함 표시와 이후 제외 표시의 차이에 유의해야 합니다.'
SPECS['psx'].update(profit_label='계산 영업손익',capex_label='회사 기준 CAPEX·투자',
    profit_description='전사 영업이익 별도 공시가 없어 매출 − 총비용 + 이자·부채비용으로 계산한 영업손익입니다. 지분법 손익·자산매각이익·기타 비매출 수익은 제외하고 비이자 비용은 유지합니다. 공시 영업이익이나 조정 EBIT와 동일하지 않습니다.',
    capex_description='현금흐름표 Capital expenditures and investments입니다. 지분 투자 등을 포함한 회사 기준으로, 다른 기업의 유형자산 현금취득과 직접 같은 범위로 비교하지 않습니다. 별도 표시된 기업 인수 대금은 제외합니다.')
SPECS['psx']['note']='Phillips 66 전사 연결이며 정유 단독 실적이 아닙니다. 영업손익은 매출 − 총비용 + 이자·부채비용으로 계산하며 지분법 손익·자산매각이익·기타 비매출 수익은 제외합니다. CAPEX는 현금흐름표 Capital expenditures and investments로 지분 투자 등을 포함하고 별도 기업 인수 대금은 제외합니다. DCP 등 연결 범위 변화와 과거 유류세 표시 기준 변화에 유의해야 합니다.'


def sec_accounts(key):
    facts=[]
    cache_path=CACHE/f'{key}-reviewed-facts.json'
    version=hashlib.sha256((ROOT/'scripts/refining_sources.py').read_bytes()+(ROOT/'scripts/oil_sources.py').read_bytes()).hexdigest()
    cached=load(cache_path,{})
    if cached.get('parser_version')!=version:cached=dict(parser_version=version,files={})
    for accn,meta in load(CACHE/f'{key}-filings.json',{}).items():
        if not meta['date'] or meta['date']<'2014-01-01' or meta['filed']>today():continue
        if meta['form'] not in ['10-K','10-K/A','10-Q','10-Q/A']:continue
        raw=(CACHE/meta['path']).read_bytes();digest=hashlib.sha256(raw).hexdigest()
        entry=cached['files'].get(accn,{})
        if entry.get('digest')!=digest:
            entry=dict(digest=digest,facts=statement_facts(raw,dict(meta,accn=accn),key))
            cached['files'][accn]=entry
        facts.extend(entry['facts'])
    save(cache_path,cached)
    rows,annual=reported_accounts(facts,SPECS[key]['cik'],today())
    return rows,annual,facts


def soil_accounts(prior=None):
    entity=load(CACHE/'soil-entity.json',{})
    if entity.get('stock_code')!='010950':raise ValueError('S-Oil identity unavailable')
    reports={(r['year'],r['quarter']):r for r in (prior or {}).get('reports',[])}
    for path in sorted(CACHE.glob('soil-20*-q*.json')):
        year=int(path.stem.split('-')[1]);q=int(path.stem[-1])
        report=dart_report(load(path,{})['list'],year,q,entity['corp_code'])
        reports[year,q]=report
    for path in sorted((ROOT/'manual/refining').glob('soil-*-reviewed.json')):
        for r in load(path,{})['reports']:reports[r['year'],r['quarter']]=r
    # The cash-flow account label and scope are unchanged across DART's
    # ifrs_ -> ifrs-full_ taxonomy change and the earlier custom account.
    # Keep the original account ID in every source component for auditing.
    for report in reports.values():
        for metric,f in report['fields'].items():
            f.setdefault('source_tag',f['tag']);f['tag']='reviewed:S-Oil:consolidated:'+metric
    rows=dart_accounts(list(reports.values()),today())
    # The 2015 Q3 PDF was reviewed today, so its review date is later than the
    # annual DART filing. Validate the original cumulative total explicitly
    # instead of pretending the PDF review date was its publication date.
    by_period={(r['year'],r['quarter']):r for r in reports.values()}
    for annual in [r for r in rows if r['kind']=='annual']:
        year=annual['year'];previous=by_period.get((year,3),{})
        if not previous or not any(f.get('source_reviewed') for f in previous['fields'].values()):continue
        existing=next((r for r in rows if r['kind']=='quarter' and r['year']==year and r['quarter']==4),None)
        if existing is None:
            from telecom_sources import reporting_period
            existing=reporting_period(year,4);rows.append(existing)
        for metric,f in previous['fields'].items():
            if metric in existing or metric not in annual:continue
            preceding=[r[metric] for r in rows if r['kind']=='quarter' and r['year']==year and r['quarter']<4 and metric in r]
            if len(preceding)!=3 or abs(sum(preceding)-f['ytd'])>3:raise ValueError('Reviewed S-Oil quarters do not match nine months')
            value=annual[metric]-f['ytd']
            if metric!='profit' and value<0:raise ValueError('Negative S-Oil revenue/capex difference')
            existing[metric]=value;existing['refs'][metric]=dict(annual['refs'][metric],components=[copy.deepcopy(annual['refs'][metric]),copy.deepcopy(f)],calculation='reported annual minus reviewed original nine months')
    rows.sort(key=lambda r:(r['date'],r['kind']))
    for r in rows:
        for metric in METRICS:
            if metric not in r:continue
            f=r['refs'][metric]
            if 'components' not in f:f['components']=[copy.deepcopy(f)]
    return ([r for r in rows if r['kind']=='quarter'],
            [r for r in rows if r['kind']=='annual'],list(reports.values()))


def documents(key,cohort):
    spec=SPECS[key];docs=build_company(key,cohort,spec)
    for id,doc in docs.items():
        metric=id.rsplit('_',1)[-1]
        doc['source']='S-Oil 공식 재무제표 · OpenDART' if key=='soil' else 'SEC · 기업 공식 연결 재무제표'
        doc['frequency_label']='분기 · 회사 연결 실적'
        if key!='soil':
            doc['basis_details'][1]['value']+=' 과거 연간은 해당 연도 최초 연차보고서 기준입니다. 분기 손익은 당시 9개월 누적과 맞는 원문·비교 공시를 사용하고 현금 CAPEX는 당시 누적 차분을 사용합니다. 이후 중단영업·세금·투자 재분류로 재작성된 과거 연간과는 다를 수 있습니다.'
        if key=='soil':doc['unit']='KRW 백만'
        if key=='psx' and metric=='profit':doc['name']=spec['name']+' · 영업손익 (계산)'
        if key=='psx' and metric=='capex':doc['name']=spec['name']+' · CAPEX·투자 (회사 기준)'
        observed=[r for r in cohort['rows'] if metric in r]
        annual=[r for r in cohort['annual'] if metric in r]
        doc['basis_details'].insert(0,dict(label='수록 기간',value=f"분기 {observed[0]['date']} ~ {observed[-1]['date']} · {len(observed)}개 / 연간 {annual[0]['year']} ~ {annual[-1]['year']} · {len(annual)}개. 연간을 4등분하지 않습니다."))
    return docs


def validate_accounts(key,rows,annual):
    if not rows or not annual:raise ValueError('empty financial history')
    if rows[0]['date']!='2014-03-31':raise ValueError('historical coverage regressed')
    for r in rows+annual:
        if not all(m in r for m in METRICS):raise ValueError('incomplete financial period')
    for a in annual:
        quarters=[r for r in rows if r['year']==a['year']]
        if len(quarters)!=4:raise ValueError('incomplete historical fiscal year')
        for metric in METRICS:
            if abs(sum(r[metric] for r in quarters)-a[metric])>4:raise ValueError('quarter/annual reporting scope mismatch')


def collect(offline=False,full=False):
    previous=load(STATE,dict(companies={}))
    status=load(CACHE/'collection-status.json',{}) if offline else download(full)
    state=dict(schema_version=1,updated=today(),companies={});docs={}
    for key,spec in SPECS.items():
        old=previous['companies'].get(key,{})
        try:
            if not offline and not status.get(key,{}).get('ok'):raise ValueError('source refresh unavailable')
            if key=='soil':
                rows,annual,reports=soil_accounts(old)
            else:
                rows,annual,facts=sec_accounts(key);reports=[]
            rows=[r for r in rows if r['date']>='2014-01-01']
            if not rows or not annual or not all(any(m in r for r in rows) and any(m in r for r in annual) for m in METRICS):raise ValueError('incomplete issuer metrics')
            if not offline:
                rows=merge_rows(old.get('rows',[]),rows);annual=merge_rows(old.get('annual',[]),annual)
            validate_accounts(key,rows,annual)
            cohort=dict(rows=rows,annual=annual,reports=reports,fetched=today(),checked=today(),ok=True)
        except Exception as error:
            print(key,'collection unavailable:',type(error).__name__,flush=True)
            if offline or not old:raise
            cohort=dict(old,checked=today(),ok=False)
        state['companies'][key]=cohort;docs.update(documents(key,cohort))
        print(key,len(cohort['rows']),'quarters',len(cohort['annual']),'annual reports',flush=True)
    for id,doc in docs.items():save(OUT/(id+'.json'),doc)
    save(STATE,state)
    return state


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--full-history',action='store_true')
    args=parser.parse_args();collect(args.offline,args.full_history)

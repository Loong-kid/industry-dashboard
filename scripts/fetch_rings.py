"""Build Si/SiC parts financial charts from reviewed OpenDART source reports."""
import argparse
import copy
import datetime as dt
import json
import math
from pathlib import Path

from collect_ring_sources import CACHE,META,collect
from fetch_cpu_companies import save
from ring_financial_sources import accounts,parse_report,METRICS,end

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/semicon'
STATE=OUT/'rings_state.json'


def read(path,default=None):return json.loads(path.read_bytes()) if path.exists() else copy.deepcopy(default)


def validate(cohort,asof):
    if not cohort.get('annual') or not cohort.get('rows'):raise ValueError('No confirmed financial history')
    for metric in METRICS:
        if not any(metric in r for r in cohort['annual']+cohort['rows']):raise ValueError('Missing financial metric: '+metric)
    for kind in ['annual','rows']:
        rows=cohort[kind]
        if len(rows)!=len({r['date'] for r in rows}):raise ValueError('Duplicate financial period')
        for r in rows:
            if r['date']>asof or r['fs_div'] not in ['CFS','OFS']:raise ValueError('Invalid period or basis')
            for metric in METRICS:
                if metric not in r:continue
                if not math.isfinite(r[metric]) or metric!='profit' and r[metric]<0:raise ValueError('Invalid financial observation')
                refs=r['refs'][metric]['components']
                if not refs or any(f['filed']>asof or f['fs_div']!=r['fs_div'] for f in refs):raise ValueError('Mixed statement scope or future source')


def offline(meta,old,asof,source_status=None):
    result={};entities=read(CACHE/'entities.json',{})
    for key,spec in meta['companies'].items():
        previous=old.get('companies',{}).get(key,{})
        try:
            if source_status is not None and not source_status.get(key,{}).get('ok'):raise ValueError('Original source check failed')
            entity=entities[key];status=read(CACHE/(key+'-status.json'))
            reports={(r['year'],r['quarter']):r for r in previous.get('reports',[])}
            for item in status['reports']:
                raw=read(CACHE/item['path'])
                report=parse_report(raw['list'],item['year'],item['quarter'],entity['corp_code'],item['fs_div'])
                if all(f['filed']<=asof for f in report['fields'].values()):reports[item['year'],item['quarter']]=report
            co=accounts(list(reports.values()),asof)
            validate(co,asof)
            if previous.get('rows') and co['rows'][-1]['date']<previous['rows'][-1]['date']:raise ValueError('Source history regressed')
            co.update(reports=[r for _,r in sorted(reports.items())],entity=entity,ok=True,checked=asof,fetched=asof)
            print(key,'OK',len(co['rows']),'quarters',len(co['annual']),'annual periods',flush=True)
        except Exception as error:
            if not previous:raise RuntimeError(key+': no successful financial history') from error
            co=copy.deepcopy(previous);co.update(ok=False,checked=asof)
            print(key,'preserved last successful data:',type(error).__name__,flush=True)
        result[key]=co
    return dict(companies=result)


def view(cohort,metric,kind):
    rows=cohort['annual' if kind=='annual' else 'rows'];valid=[r for r in rows if metric in r]
    if not valid:return None
    bydate={r['date']:r for r in rows};axis=set(bydate)
    if kind=='quarter':
        for year in range(rows[0]['year'],rows[-1]['year']+1):
            for q in range(1,5):
                d=end(year,q)
                if rows[0]['date']<d<rows[-1]['date']:axis.add(d)
    label={'revenue':'공시 매출','profit':'공시 영업이익','capex':'유형자산 취득 현금지출'}[metric]
    point_sources={};notes={}
    for r in valid:
        ref=r['refs'][metric];components=ref['components'];point_sources[r['date']]=dict(url=ref['url'],
            label=f"FY{r['year']}"+('' if kind=='annual' else f" Q{r['quarter']}"),
            supporting_sources=[dict(url=f['url'],label=f['start']+' ~ '+f['end']+' · '+f['filed']) for f in components],
            source_separator=' − ' if len(components)==2 else ' / ')
        notes[r['date']]=['재무제표: '+('연결' if r['fs_div']=='CFS' else '별도'),
            '공시 항목: '+ref['account_name'],'산식: '+ref['calculation'],
            '원화 금액: '+f"{r[metric]*1e6:,.0f}원"]
        if ref.get('comparative'):notes[r['date']].append('후속 보고서의 전기 비교표시 금액')
        if ref.get('inputs'):
            notes[r['date']].append('취득지출 세부항목 합계 · 환급은 차감. 무형자산·투자부동산·금융자산·기업인수·보증금 제외.')
            notes[r['date']]+= [f"{f['account_name']}: {f['value']:,.0f}원" for f in ref['inputs'] if f.get('value') is not None]
    lookup={(r['year'],r.get('quarter')):r['date'] for r in rows}
    return dict(label='연간' if kind=='annual' else '분기',frequency='yearly' if kind=='annual' else 'quarterly',
        frequency_label='연간 · DART 사업보고서' if kind=='annual' else '분기 · DART 정기 공시',quarter_labels=kind=='quarter',year_labels=kind=='annual',annual_axis=kind=='annual',
        period_labels={r['date']:f"FY{r['year']}"+('' if kind=='annual' else f" Q{r['quarter']}") for r in rows},
        comparison_dates={} if kind=='annual' else {r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),(r['quarter']-2)%4+1))) for r in rows},
        quarterly_revenue_summary=kind=='quarter' and metric!='profit',quarterly_profit_summary=kind=='quarter' and metric=='profit',
        series={label:[[date,bydate.get(date,{}).get(metric)] for date in sorted(axis)]},default_series=[label],
        updated=valid[-1]['date'],source_url=valid[-1]['refs'][metric]['url'],point_sources=point_sources,point_notes=notes)


def build(meta,state):
    docs={}
    for key,spec in meta['companies'].items():
        co=state['companies'][key]
        bases={'연결' if r['fs_div']=='CFS' else '별도' for r in co['annual']+co['rows']}
        coverage='연간 '+co['annual'][0]['date']+'부터 · 분기 '+co['rows'][0]['date']+'부터. 미확인 분기는 공백으로 남깁니다.'
        for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
            views={kind:v for kind in ['quarter','annual'] if (v:=view(co,metric,kind))}
            default='quarter' if 'quarter' in views else 'annual';id=f'company_rings_{key}_{metric}'
            note=spec['scope']+'. 링 단독 또는 SiC 단독 실적이 아닙니다. '+spec.get('note','')
            if metric=='capex':note+=' CAPEX는 현금흐름표 유형자산 취득 지출이며 장부 증가액·증설 계획·감가상각과 다릅니다. 세부 취득 항목만 공시한 경우 합산하며 시설장치 등의 현금환급은 차감합니다. 무형자산·투자부동산·M&A·금융리스는 제외합니다.'
            doc=dict(id=id,name=spec['name']+' · '+title,unit='KRW 백만',source='OpenDART · '+spec['name']+' 정기 공시',fetched=co['fetched'],description=note,
                series_views=views,default_view=default,company_kpi=True,span_gaps=False,table_limit=120,
                basis_details=[dict(label='제품·사업 범위',value=spec['products']+'. '+note),dict(label='이력',value=coverage),
                  dict(label='연결·별도',value=' / '.join(sorted(bases))+' 재무제표. 연결을 우선하고 연결이 없는 보고서는 별도로 표시합니다. 서로 다른 연결·별도 누적끼리는 차감하지 않습니다.'),
                  dict(label='분기·현금흐름 산식',value='매출·영업이익은 공시 3개월 금액을 우선합니다. 4분기는 연간−9개월 누적, CAPEX는 해당 연도 누적−직전 누적입니다. 비교표시는 확인된 기간에만 쓰며 누적 기준이 맞지 않거나 지출 누적이 역전된 구간은 공백입니다.'),
                  dict(label='자동 갱신',value=co['checked']+' · '+('정상' if co['ok'] else '원문 확인 실패 · 마지막 성공 자료 유지'))])
            doc.update(copy.deepcopy(views[default]));doc.pop('label',None)
            if not co['ok']:doc['collection_status']=dict(ok=False,checked=co['checked'],message='원문 확인 실패 · 마지막 성공 자료 유지')
            docs[id]=doc
    return docs


def main():
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true');args=p.parse_args()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();meta=read(META);old=read(STATE,dict(companies={}))
    status=None
    if args.refresh:
        try:status=collect(args.full_history)
        except ValueError:
            status={key:dict(ok=False) for key in meta['companies']}
    state=old if args.from_state else offline(meta,old,asof,status)
    for co in state['companies'].values():validate(co,asof)
    for id,doc in build(meta,state).items():save(OUT/(id+'.json'),doc)
    save(STATE,state);print('Published 15 Si/SiC parts financial charts',flush=True)


if __name__=='__main__':main()

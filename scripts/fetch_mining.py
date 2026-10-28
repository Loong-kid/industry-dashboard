"""Mining accounts from original statements; preserve successful history on failures."""
import argparse
import copy
import datetime as dt
import json
import math
from pathlib import Path

from fetch_cpu_companies import annual_view, build_company, save
from mining_financial_sources import CACHE, METRICS, sec_periods, glencore_annual, zijin_annual, grupo_annual

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/commodities'
HISTORY=OUT/'mining_financial_history.json'
META=ROOT/'manual/mining/companies.json'


def read(path,default=None):
    return json.loads(path.read_bytes()) if path.exists() else copy.deepcopy(default)


def validate_periods(cohort,asof):
    annual=cohort['annual']
    if not annual or any(not any(m in r for r in annual) for m in METRICS):raise ValueError('Incomplete annual accounts')
    for kind in ['annual','rows','halves']:
        rows=cohort.get(kind,[])
        if len({r['date'] for r in rows})!=len(rows):raise ValueError('Duplicate period')
        for r in rows:
            if r['date']>asof:raise ValueError('Future observation')
            for metric in METRICS:
                if metric not in r:continue
                value=r[metric]
                if not math.isfinite(value) or metric!='profit' and value<0:raise ValueError('Invalid statement value')
                refs=r['refs'][metric]['components']
                if not refs or any(f['filed']>asof or not f['url'].startswith('https://') for f in refs):raise ValueError('Invalid original reference')


def merge_periods(old,new):
    result={**copy.deepcopy(old),**copy.deepcopy(new)}
    for kind in ['annual','rows','halves']:
        rows={r['date']:copy.deepcopy(r) for r in old.get(kind,[])}
        for r in new.get(kind,[]):
            previous=rows.get(r['date'],{})
            refs={**previous.get('refs',{}),**r['refs']}
            rows[r['date']]={**previous,**r,'refs':refs}
        result[kind]=[r for _,r in sorted(rows.items())]
    return result


def collect_offline(meta,asof,old,status=None):
    result={};registry=read(ROOT/'manual/mining/source_files.json')
    for spec in meta['companies']+[meta['ero']]:
        key=spec['id'];previous=old.get(key,{})
        try:
            if status is not None and not status.get(key,{}).get('ok'):raise ValueError('Original source check failed')
            if spec.get('cik'):
                co=sec_periods(read(CACHE/f'{key}-facts.json'),key,spec,asof)
            else:
                prefix={'glen':'glen-','zijin':'zijin-','grupo':'grupo-bmv-'}[key]
                parser={'glen':glencore_annual,'zijin':zijin_annual,'grupo':grupo_annual}[key]
                rows={};halves={}
                for name,source in sorted(registry.items(),key=lambda p:p[1]['year']):
                    if not name.startswith(prefix) or source['filed']>asof or source['kind']!='annual' and key!='glen':continue
                    for r in parser(CACHE/name,source):
                        if source['kind']=='half':halves[r['date']]=r
                        elif key!='glen' or r['year']==source['year'] or r['date'] not in rows:rows[r['date']]=r
                for h in list(halves.values()):
                    annual=rows.get(f"{h['year']}-12-31")
                    if not annual:continue
                    tail=dict(date=annual['date'],year=h['year'],half=2,refs={})
                    for metric in METRICS:
                        tail[metric]=annual[metric]-h[metric]
                        tail['refs'][metric]=dict(annual['refs'][metric],components=[annual['refs'][metric]['components'][0],h['refs'][metric]['components'][0]],calculation='reported full year minus first half')
                    halves[tail['date']]=tail
                co=dict(annual=[r for _,r in sorted(rows.items())],rows=[],halves=[r for _,r in sorted(halves.items())])
            validate_periods(co,asof)
            co=merge_periods(previous,co)
            co.update(ok=True,checked=asof,fetched=asof)
            print(key,'OK',len(co['annual']),'annual',len(co['rows']),'quarters',len(co['halves']),'halves',flush=True)
        except Exception as error:
            if not previous:raise RuntimeError(key+': no successful history') from error
            co=copy.deepcopy(previous);co.update(ok=False,checked=asof)
            print(key,'preserving successful history:',type(error).__name__,str(error)[:140],flush=True)
        result[key]=co
    return result


def period_view(rows,metric,label,kind,note):
    view=annual_view(rows,{metric:label},note) if kind=='annual' else dict(
        series={label:[[r['date'],r.get(metric)] for r in rows]},
        period_labels={r['date']:f"FY{r['year']} H{r['half']}" for r in rows},
        point_sources={r['date']:dict(url=r['refs'][metric]['url'],label=f"FY{r['year']} H{r['half']}",
            supporting_sources=[dict(url=f['url'],label=f['start']+' ~ '+f['end']) for f in r['refs'][metric]['components']]) for r in rows if metric in r['refs']},
        description=note+' 하반기는 동일 회계연도의 연간에서 상반기를 차감한 값입니다. 분기 추정은 하지 않습니다.')
    valid=[r for r in rows if r.get(metric) is not None]
    latest=valid[-1]
    view.update(label='연간' if kind=='annual' else '반기',frequency='yearly' if kind=='annual' else 'semiannual',
        frequency_label='연간 · 회사 회계연도' if kind=='annual' else '반기 · 회사 공시',quarter_labels=False,
        year_labels=kind=='annual',annual_axis=kind=='annual',
        updated=latest['date'],source_url=latest['refs'][metric]['url'],comparison_dates={},
        quarterly_profit_summary=False,quarterly_revenue_summary=False,change_mode='none')
    return view


def build_docs(meta,cohorts):
    docs={}
    for spec in meta['companies']+[meta['ero']]:
        key=spec['id'];co=cohorts[key];name=spec['name'];note=spec['scope']+'. '+spec['note']
        for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
            label=('계산 영업손익' if spec.get('profit_calculated') else '공시 영업손익') if metric=='profit' else '연결 매출' if metric=='revenue' else '현금 CAPEX'
            explanation=note+(' 계산식: '+spec['profit_formula'] if metric=='profit' and spec.get('profit_formula') else '')
            indicator=f'company_mining_{key}_{metric}'
            annual=period_view(co['annual'],metric,label,'annual',explanation)
            views={};doc={}
            # Reuse the existing fiscal-quarter differencing UI only for observed quarters.
            if any(metric in r for r in co['rows']):
                defs=dict(spec,profit_label=label,capex_label='현금 CAPEX',revenue_description=explanation,profit_description=explanation,capex_description=explanation)
                # build_company creates all three metrics; each must have an observation.
                if all(any(m in r for r in co['rows']) for m in METRICS):
                    d=build_company('mining_'+key,co,defs)[indicator]
                    doc=d;views['quarter']={k:copy.deepcopy(d[k]) for k in ['series','period_labels','point_sources','source_url','updated','description','frequency','frequency_label','quarter_labels','comparison_dates','quarterly_profit_summary','quarterly_revenue_summary','default_series']}
                    views['quarter'].update(label='분기',year_labels=False,annual_axis=False)
            if co.get('halves') and any(metric in r for r in co['halves']):views['half']=period_view(co['halves'],metric,label,'half',explanation)
            views['annual']=annual
            default='quarter' if key=='ero' and 'quarter' in views else 'annual'
            doc.update(id=indicator,name=name+' · '+title+(' (계산)' if metric=='profit' and spec.get('profit_calculated') else ''),
                unit=spec['currency']+' 백만',source=name+' · 공식 재무제표',fetched=co['fetched'],description=explanation,
                default_series=[label],span_gaps=False,company_kpi=True,table_limit=100,
                series_views=views,default_view=default,
                basis_details=[dict(label='연결 범위·산식',value=explanation),
                    dict(label='공시 주기',value='연간·분기·반기는 확보된 원문만 표시합니다. 누적 금액의 분기는 같은 회계연도의 직전 누적을 차감합니다. 미확인 값은 0으로 채우지 않습니다.'),
                    dict(label='갱신 확인',value=co['checked']+' · '+('정상' if co['ok'] else '원문 확인 실패 · 마지막 성공 자료 유지'))])
            doc.update(copy.deepcopy(views[default]));doc.pop('label',None)
            if not co['ok']:doc['collection_status']=dict(ok=False,checked=co['checked'],message='원문 확인 실패 · 마지막 성공 자료 유지')
            else:doc.pop('collection_status',None)
            docs[indicator]=doc
    universe=copy.deepcopy(meta);universe.pop('ero')
    universe.update(id='mining_universe',name='글로벌 광산기업 · 순위와 매출 구성',updated=meta['ranking_date'],fetched=meta['ranking_date'],
        source='CompaniesMarketCap · 각 회사 공식 연차보고서',source_url=meta['ranking_source_url'])
    docs['mining_universe']=universe
    return docs


def main():
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--from-state',action='store_true');p.add_argument('--as-of');args=p.parse_args()
    asof=args.as_of or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=read(META);old=read(HISTORY,{});status=None
    if args.refresh:
        from collect_mining_sources import collect
        from collect_mining_ir import collect as ir_collect
        status=collect();ir=ir_collect()
        for key,prefix in [('glen','glen-'),('zijin','zijin-'),('grupo','grupo-bmv-')]:
            status[key]=dict(ok=all(v['ok'] for n,v in ir.items() if n.startswith(prefix)))
    cohorts=old if args.from_state else collect_offline(meta,asof,old,status)
    for co in cohorts.values():validate_periods(co,asof)
    docs=build_docs(meta,cohorts)
    for key,doc in docs.items():save(OUT/(key+'.json'),doc)
    save(HISTORY,cohorts)
    print('Published',len(docs),'mining documents',flush=True)


if __name__=='__main__':main()

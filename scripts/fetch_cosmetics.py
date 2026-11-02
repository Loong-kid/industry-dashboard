"""Cosmetics value-chain accounts; official preliminary income stays separate."""
import argparse
import copy
import datetime as dt
from pathlib import Path

from collect_cosmetics_sources import CACHE,META,collect
from fetch_cpu_companies import save
from fetch_rings import read,validate,view as financial_view
from ring_financial_sources import parse_report,accounts,METRICS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/cosmetics'
STATE=OUT/'state.json'


def normalize(items,year,q,corp,fs,spec):
    report=parse_report(items,year,q,corp,fs)
    for row in [report]+report.get('comparatives',[]):
        fields=row['fields']
        # Pre-IPO reports may supply only a six/nine-month income column. If
        # both sales and operating profit duplicate YTD, do not invent a Q2/Q3.
        if q in [2,3] and all(m in fields and fields[m].get('value') is not None and fields[m]['value']==fields[m].get('ytd') for m in ['revenue','profit']):
            for m in ['revenue','profit']:
                fields[m]['value']=None;fields[m]['duration_note']='Only cumulative income verified; duplicated API columns'
        start=spec.get('first_period_start')
        if start and row['year']==int(start[:4]):
            for f in fields.values():f['start']=max(f['start'],start)
    return report


def with_preliminaries(regular,prior,fresh,asof):
    confirmed={r['date'] for r in regular if 'revenue' in r and 'profit' in r}
    pending={r['date']:copy.deepcopy(r) for r in prior if r['date']<=asof and all(f['filed']<=asof for f in r['refs'].values())}
    for row in fresh:
        if row['date']>asof or any(f['filed']>asof for f in row['refs'].values()):continue
        old=pending.get(row['date'])
        if not old or max(f['filed'] for f in row['refs'].values())>=max(f['filed'] for f in old['refs'].values()):pending[row['date']]=copy.deepcopy(row)
    return [r for date,r in sorted(pending.items()) if date not in confirmed]


def offline(meta,old,asof,status=None):
    entities=read(CACHE/'entities.json',{});result={}
    for key,spec in meta['companies'].items():
        prior=old.get('companies',{}).get(key,{})
        try:
            if status is not None and not status.get(key,{}).get('ok'):raise ValueError('Original source check failed')
            entity=entities[key];originals=read(CACHE/(key+'-status.json'))
            reports={(r['year'],r['quarter']):r for r in prior.get('reports',[])}
            for entry in originals['reports']:
                raw=read(CACHE/entry['path'])
                r=normalize(raw['list'],entry['year'],entry['quarter'],entity['corp_code'],entry['fs_div'],spec)
                if all(f['filed']<=asof for f in r['fields'].values()):reports[r['year'],r['quarter']]=r
            co=accounts(list(reports.values()),asof)
            prelim=read(CACHE/(key+'-preliminaries.json'),dict(rows=[],errors=[]))
            pending=with_preliminaries(co['rows'],prior.get('provisional_rows',[]),prelim['rows'],asof)
            co['rows']=sorted(co['rows']+pending,key=lambda r:r['date'])
            validate(co,asof)
            if prior.get('annual') and co['annual'][-1]['date']<prior['annual'][-1]['date']:raise ValueError('Annual history regressed')
            co.update(reports=[r for _,r in sorted(reports.items())],entity=entity,provisional_rows=pending,preliminary_errors=prelim.get('errors',[]),ok=True,checked=asof,fetched=asof)
            print(key,'OK',len(co['rows']),'quarters',len(co['annual']),'annual periods',len(pending),'preliminary quarters',flush=True)
        except Exception as error:
            if not prior:raise RuntimeError(key+': no successful cosmetics accounts') from error
            co=copy.deepcopy(prior);co.update(ok=False,checked=asof)
            print(key,'preserved successful history:',type(error).__name__,flush=True)
        result[key]=co
    return dict(checked=asof,fetched=max(c['fetched'] for c in result.values()),companies=result)


def views(cohort,metric,spec):
    result={}
    # Income-only preliminary releases do not create a CAPEX period. Its card
    # stays on the latest actual cash-flow report rather than a blank Q3 badge.
    if metric=='capex':
        cohort=dict(cohort,rows=[r for r in cohort['rows'] if not r.get('provisional')])
    for kind in ['quarter','annual']:
        v=financial_view(cohort,metric,kind)
        if not v:continue
        if kind=='quarter' and any(r.get('provisional') and metric in r for r in cohort['rows']):v['frequency_label']='분기 · DART 확정·잠정'
        for row in cohort['rows'] if kind=='quarter' else cohort['annual']:
            date=row['date']
            if row.get('provisional'):
                v['period_labels'][date]+=' · 잠정'
                if date in v['point_sources']:v['point_sources'][date]['label']+=' · 잠정'
                if date in v['point_notes']:v['point_notes'][date].insert(0,'공식 잠정 공시 · 정기보고서 확인 시 확정 값으로 교체합니다.')
            start=spec.get('first_period_start')
            if start and date[:4]==start[:4]:
                v['period_labels'][date]+=' · 분할 후 기간'
                if date in v['point_notes']:v['point_notes'][date].append('첫 회계기간 시작: '+start+' · 12개월 연도와 직접 비교하지 않습니다.')
        result[kind]=v
    return result


def build(meta,state):
    docs={}
    for key,spec in meta['companies'].items():
        co=state['companies'][key];basis={'연결' if r['fs_div']=='CFS' else '별도' for r in co['annual']+co['rows']}
        coverage=f"연간 {co['annual'][0]['date']}부터 · 분기 {co['rows'][0]['date']}부터. 공시 확보 기간만 표시하며 미확인 금액은 0으로 채우지 않습니다."
        for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
            vv=views(co,metric,spec);default='quarter' if 'quarter' in vv else 'annual';id=f'company_cosmetics_{key}_{metric}'
            note=spec['scope']+'. '+spec['note']
            note+=(' CAPEX는 현금흐름표의 유형자산 취득 현금지출입니다. 무형자산·투자부동산·M&A·비현금 리스 취득은 제외하며 총액이 없으면 명시된 유형자산 취득 항목만 합산합니다. 잠정실적의 CAPEX는 추정하지 않습니다.' if metric=='capex' else ' 정기보고서 확정 실적을 우선하고, 이후 공개된 공식 잠정 분기는 잠정 표시 후 정기보고서 확보 시 교체합니다.')
            doc=dict(id=id,name=spec['name']+' · '+title,unit='KRW 백만',source='DART · '+spec['name']+' 공식 공시',fetched=co['fetched'],description=note,
                company_kpi=True,span_gaps=False,table_limit=120,series_views=vv,default_view=default,
                basis_details=[dict(label='선정·사업 역할',value=spec['role']+' · '+meta['selection_basis']),dict(label='연결 범위',value=note),
                  dict(label='이력·공시 기준',value=coverage+' 재무제표: '+' / '.join(sorted(basis))+'. 연결을 우선하며 연결이 없는 기간은 별도임을 표시합니다.'),
                  dict(label='분기·연간·차분',value='매출·영업이익은 실제 3개월 공시를 우선합니다. 4분기는 연간−9개월, CAPEX는 같은 회계연도의 누적−직전 누적입니다. 연결·별도, 원문 기간·공시 순서를 확인하며 기준이 맞지 않거나 현금지출 누적이 역전된 구간은 공백으로 둡니다.'),
                  dict(label='최신 실적',value='정기보고서와 공식 잠정 공시를 구분합니다. 실적 전망·컨센서스·목표치는 사용하지 않으며 잠정 CAPEX를 채우지 않습니다.'),
                  dict(label='갱신 확인',value=co['checked']+' · '+('정상' if co['ok'] else '원문 확인 실패 · 마지막 성공 자료 유지'))])
            if co.get('preliminary_errors'):doc['basis_details'].append(dict(label='잠정 공시 검토',value='일부 공식 잠정 문서의 표·기간을 자동 확인하지 못해 검토가 필요합니다. 확인된 정기보고서·기존 성공 자료는 유지합니다.'))
            doc.update(copy.deepcopy(vv[default]));doc.pop('label',None)
            if not co['ok']:doc['collection_status']=dict(ok=False,checked=co['checked'],message='원문 확인 실패 · 마지막 성공 자료 유지')
            docs[id]=doc
    return docs


def main():
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true');args=p.parse_args()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();meta=read(META);old=read(STATE,dict(companies={}));status=None
    if args.refresh:
        try:status=collect(args.full_history)
        except ValueError:status={key:dict(ok=False) for key in meta['companies']}
    state=old if args.from_state else offline(meta,old,asof,status)
    for co in state['companies'].values():validate(co,asof)
    docs=build(meta,state)
    for id,doc in docs.items():save(OUT/(id+'.json'),doc)
    save(STATE,state);print('Published',len(docs),'cosmetics financial charts',flush=True)


if __name__=='__main__':main()

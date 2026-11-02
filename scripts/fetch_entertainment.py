"""Korean music agencies: actual consolidated income and cash PP&E accounts."""
import argparse,copy,datetime as dt
from pathlib import Path
from collect_entertainment_sources import CACHE,META,collect
from fetch_cosmetics import offline as financial_accounts,views,normalize as normalize_financial
from fetch_rings import read,validate
from fetch_cpu_companies import save
from ring_financial_sources import choose,number

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/entertainment';STATE=OUT/'state.json'
CAPEX_NOTE='CAPEX는 현금흐름표 유형자산 취득 현금지출입니다. 총액을 우선하고 세부 취득 항목만 공시하면 합산하며 환급은 차감합니다. 음원 마스터·카탈로그·계약권 등 무형자산, 콘텐츠 제작비·선급금, 투자부동산, M&A와 비현금 리스는 포함하지 않아 전체 IP 투자액과 다릅니다.'


def offline(meta,old,asof,status=None):
    return financial_accounts(meta,old,asof,status,cache=CACHE,normalize_report=normalize)


def normalize(items,year,q,corp,fs,spec):
    rows=copy.deepcopy(items);total=choose(rows,'capex')
    if total and total['rcept_no'] in spec.get('ppe_cash_separate_cip_receipts',[]):
        # Reviewed original CF tables reconcile only when these two peer cash
        # outflows are added. Other periods already include CIP in the total.
        extra=[r for r in rows if r.get('sj_div')=='CF' and r.get('account_id')=='dart_PurchaseOfConstructionInProgress']
        if len(extra)!=1:raise ValueError('Reviewed separate CIP row changed')
        merged=dict(total,account_nm='유형자산 취득 + 별도 건설중인자산 취득',inputs=[copy.deepcopy(total),copy.deepcopy(extra[0])])
        for field in ['thstrm_amount','frmtrm_q_amount','frmtrm_amount','bfefrmtrm_amount']:
            values=[number(r.get(field)) for r in [total,extra[0]]]
            merged[field]=str(sum(v for v in values if v is not None)) if any(v is not None for v in values) else ''
        rows[rows.index(total)]=merged
    return normalize_financial(rows,year,q,corp,fs,spec)


def build(meta,state):
    docs={}
    for key,spec in meta['companies'].items():
        co=state['companies'][key]
        bases=sorted({'연결' if r['fs_div']=='CFS' else '별도' for r in co['annual']+co['rows']})
        coverage=f"연간 {co['annual'][0]['date']}부터 · 분기 {co['rows'][0]['date']}부터. 실제 공시가 확보된 기간만 표시합니다."
        for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
            vv=views(co,metric,spec);default='quarter' if 'quarter' in vv else 'annual';id=f'company_entertainment_{key}_{metric}'
            note=spec['scope']+'. '+spec['note']
            note+=' '+(CAPEX_NOTE if metric=='capex' else '정기보고서 확정 실적을 우선하고 이후 발표된 공식 잠정 분기는 잠정 표시 후 정기보고서 확보 시 교체합니다. 콘서트·음반 발매·정산 시점에 따라 분기 변동이 크며 조정 EBITDA나 순이익을 영업이익으로 대체하지 않습니다.')
            doc=dict(id=id,name=spec['display_name']+' · '+title,unit='KRW 백만',source='DART · '+spec['name']+' 공식 공시',fetched=co['fetched'],description=note,
                company_kpi=True,span_gaps=False,table_limit=120,series_views=vv,default_view=default,
                basis_details=[dict(label='기업 선정',value=spec['role']+' · '+meta['selection_basis']),dict(label='실적·연결 범위',value=spec['scope']+'. '+spec['note']),
                   dict(label='이력·재무제표',value=coverage+' '+' / '.join(bases)+' 재무제표. 연결 우선이며 연결이 없는 기간은 별도로 표시합니다. 확인되지 않은 과거는 0 또는 추정 값으로 채우지 않습니다.'),
                   dict(label='분기·연간 산식',value='매출·영업이익은 실제 3개월 공시를 우선합니다. 4분기는 연간−9개월 누적, CAPEX는 같은 회계연도의 누적−직전 누적입니다. 서로 다른 연결·별도 및 기준이 다른 누적은 차감하지 않으며 음수가 되는 취득지출 차분은 공백입니다.'),
                   dict(label='CAPEX 범위',value=CAPEX_NOTE),dict(label='잠정·최신 실적',value='공식 잠정 매출·영업이익은 구분 표시하며 정기보고서 확보 시 교체합니다. 잠정 CAPEX는 추정하지 않아 매출·이익과 최신 보고 분기가 다를 수 있습니다.'),
                   dict(label='갱신 확인',value=co['checked']+' · '+('정상' if co['ok'] else '원문 확인 실패 · 마지막 성공 자료 유지'))])
            if co.get('preliminary_errors'):doc['basis_details'].append(dict(label='잠정 공시 검토',value='일부 잠정 공시의 표·기간을 자동 확인하지 못했습니다. 확인된 정기보고서와 기존 성공 이력은 유지합니다.'))
            doc.update(copy.deepcopy(vv[default]));doc.pop('label',None)
            if not co['ok']:doc['collection_status']=dict(ok=False,checked=co['checked'],message='원문 확인 실패 · 마지막 성공 자료 유지')
            docs[id]=doc
    return docs


def main():
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true');a=p.parse_args()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();meta=read(META);old=read(STATE,dict(companies={}));status=None
    if a.refresh:
        try:status=collect(a.full_history)
        except ValueError:status={key:dict(ok=False) for key in meta['companies']}
    state=old if a.from_state else offline(meta,old,asof,status)
    for co in state['companies'].values():validate(co,asof)
    docs=build(meta,state)
    for id,doc in docs.items():save(OUT/(id+'.json'),doc)
    save(STATE,state);print('Published',len(docs),'entertainment financial charts',flush=True)


if __name__=='__main__':main()

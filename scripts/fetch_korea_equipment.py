"""Original DART financials for ten large Korean process-equipment issuers."""
import argparse,copy,datetime as dt
from pathlib import Path
from collect_ring_sources import collect as collect_originals
from fetch_cosmetics import offline,normalize as normalize_financial,views
from ring_financial_sources import parse_report
from fetch_rings import validate
from fetch_cpu_companies import load,save

ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.cache/korea-equipment'
META=ROOT/'manual/korea-equipment/companies.json';STATE=ROOT/'data/semicon/korea_equipment_state.json'


def normalize(items,year,q,corp,fs,spec):
    result=normalize_financial(items,year,q,corp,fs,spec)
    if spec.get('negative_ppe_components'):
        for report in [result]+result.get('comparatives',[]):
            field=report['fields'].get('capex',{})
            inputs=field.get('inputs',[])
            values=[p['value'] for p in inputs if p.get('value') is not None]
            if inputs and field.get('ytd') is not None and field['ytd']<0 and values and all(v<=0 for v in values):
                field['original_signed_inputs']=copy.deepcopy(inputs)
                field['ytd']=-field['ytd']
                for p in inputs:
                    if p.get('value') is not None:p['value']=-p['value']
                field['cash_sign_note']='원문 취득 지출 항목 전체가 음수 현금유출로 공시되어 양수 CAPEX 지출로 부호를 전환했습니다. 원문 부호는 source original_signed_inputs에 보존합니다.'
    first=spec.get('first_period_start')
    if first and year==int(first[:4]):
        end=dt.date(year,q*3,30 if q in (2,3) else 31)
        days=(end-dt.date.fromisoformat(first)).days+1
        if 75<=days<=105:
            raw=parse_report(items,year,q,corp,fs)
            # The first 9-month fiscal year may start in April. Its Q2 report
            # contains three actual months, even when quarter == YTD.
            for metric in ('revenue','profit'):
                if metric in raw['fields'] and raw['fields'][metric].get('value') is not None:
                    result['fields'][metric]=dict(raw['fields'][metric],start=first)
    return result


def build(meta,state):
    docs={}
    for key,spec in meta['companies'].items():
        co=state['companies'][key]
        coverage='연간 '+co['annual'][0]['date']+'부터 · 분기 '+co['rows'][0]['date']+'부터'
        for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
            vv=views(co,metric,spec);default='quarter' if 'quarter' in vv else 'annual';identifier=f'company_kr_equipment_{key}_{metric}'
            if metric=='capex':
                for kind,view in vv.items():
                    for row in co['annual' if kind=='annual' else 'rows']:
                        components=row.get('refs',{}).get(metric,{}).get('components',[])
                        if any(c.get('cash_sign_note') for c in components):view['point_notes'].setdefault(row['date'],[]).append('원문 음수 현금유출 → 양수 취득지출 부호 정규화 · 순유입·환급을 무조건 절댓값 처리하지 않습니다.')
            doc=dict(id=identifier,name=spec['name']+' · '+title,unit='KRW 백만',company_kpi=True,compact_tooltip=True,span_gaps=False,table_limit=120,
                source='DART · '+spec['name']+' 정기 공시',fetched=co['fetched'],description=spec['scope']+'. '+spec['note'],
                basis_details=[dict(label='주력 공정·분류',value=spec['role']+'. '+spec['note']),dict(label='실적 범위',value=spec['scope']+'. 회사 자신의 CAPEX이며 고객사 투자나 장비 수주액이 아닙니다.'),
                    dict(label='분기·연간·연결 기준',value='실제 3개월·완결 회계연도를 구분합니다. 연결 우선이며 연결 미공시 기간은 별도로 표시합니다. 4분기는 연간−9개월, CAPEX는 동일 연도 누적−직전 누적입니다. 연결/별도와 누적 기준이 다르거나 지출 누적이 역전되면 공백입니다.'),
                    dict(label='CAPEX',value='유형자산 취득 현금지출입니다. 총액을 우선하고 세부 항목만 공시하면 합산합니다. 무형자산·투자부동산·M&A·비현금 리스·공급받는 파운드리의 투자를 제외합니다.'),
                    dict(label='확보 이력',value=coverage+'. 법인 신설·분할 전 타 법인의 이력을 이어 붙이지 않으며 미확인 분기를 연간의 1/4이나 0으로 채우지 않습니다.'),
                    dict(label='기업 선정',value=meta['selection_basis']),dict(label='갱신',value=co['checked']+' · '+('원문 확인 완료' if co['ok'] else '조회 실패 · 기존 성공 이력 유지'))],
                collection_status=dict(ok=co['ok'],checked=co['checked'],message='DART 원문 확인 완료' if co['ok'] else '조회 실패 · 기존 성공 이력 유지'),
                series_views=vv,default_view=default)
            doc.update(copy.deepcopy(vv[default]));doc.pop('label',None);docs[identifier]=doc
    return docs


def first_period(co,spec):
    first=spec.get('first_period_start')
    if not first:return
    for kind in ('rows','annual'):co[kind]=[r for r in co[kind] if r['date']>=first]
    for row in co['rows']:
        days=(dt.date.fromisoformat(row['date'])-dt.date.fromisoformat(first)).days+1
        if not 75<=days<=105 or 'capex' in row:continue
        report=next((r for r in co['reports'] if (r['year'],r['quarter'],r['fs_div'])==(row['year'],row['quarter'],row['fs_div'])),{})
        field=report.get('fields',{}).get('capex',{})
        if field.get('ytd') is not None and field.get('start')==first:
            row['capex']=field['ytd'];row['refs']['capex']=dict(field,components=[copy.deepcopy(field)],calculation='reported first three-month fiscal cash flow after spin-off')


def universe(meta,state):
    snapshot=load(ROOT/'manual/korea-equipment/market-cap-selection.json',{})
    quotes={r['ticker']:r for r in snapshot['candidates']};companies=[]
    for key,spec in meta['companies'].items():
        q=quotes[spec['ticker']]
        companies.append(dict(spec,id=key,market_cap_krw=q['market_cap_krw'],market_cap_label=q['market_cap_label'],traded_at=q['traded_at'],market_source_url=q['source_url'],existing=False))
    q=quotes['042700']
    companies.append(dict(id='hanmi',name='한미반도체',ticker='042700',role='후공정 · HBM TC 본더·절단·분류',tabs=['equipment_packaging'],note='기존 한미반도체 연결 실적을 유지합니다.',
        source_url='https://kind.krx.co.kr/external/2026/03/12/002053/20260312004659/11011.htm',market_cap_krw=q['market_cap_krw'],market_cap_label=q['market_cap_label'],traded_at=q['traded_at'],market_source_url=q['source_url'],existing=True))
    return dict(id='korea_equipment_universe',reviewed=meta['reviewed'],fetched=state['fetched'],selection_basis=meta['selection_basis'],scope_notes=meta['scope_notes'],companies=sorted(companies,key=lambda c:c['market_cap_krw'],reverse=True))


def collect(refresh=False,full=False,from_state=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();meta=load(META,{});old=load(STATE,dict(companies={}));status=None
    if refresh:
        try:status=collect_originals(full,cache=CACHE,metadata=META)
        except ValueError:
            if not old['companies']:raise
            status={key:dict(ok=False) for key in meta['companies']}
    state=old if from_state else offline(meta,old,asof,status,cache=CACHE,normalize_report=normalize)
    for key,co in state['companies'].items():
        first_period(co,meta['companies'][key])
        validate(co,asof)
    save(STATE,state)
    docs=build(meta,state)
    for identifier,doc in docs.items():save(ROOT/'data/semicon'/(identifier+'.json'),doc)
    if (ROOT/'manual/korea-equipment/market-cap-selection.json').exists():save(ROOT/'data/semicon/korea_equipment_universe.json',universe(meta,state))
    print('Published',len(docs),'Korean equipment financial charts',flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');p.add_argument('--from-state',action='store_true');a=p.parse_args()
    collect(a.refresh,a.full_history,a.from_state)

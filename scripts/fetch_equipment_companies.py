"""US equipment-company consolidated GAAP accounts from SEC Company Facts."""
import argparse
import copy
import time
import requests
from fetch_cpu_companies import ROOT, OUT, today, load, save, parse_facts, parse_annual, build_company

CACHE=ROOT/'.cache/equipment'
COMPANIES={
    'lam':dict(name='Lam Research · LRCX',cik=707549,fiscal_start=7,
        tags={'capex':['PaymentsToAcquireProductiveAssets']},capex_label='설비·무형자산 현금취득',
        capex_description='현금흐름표의 Capital expenditures and intangible assets입니다. 무형자산 현금취득을 포함하며 다른 회사의 유형자산 취득과 범위가 다릅니다.',
        scope='Lam Research 전사 연결 · 장비·고객지원 포함',
        note='Lam Research 연결 전체 기준입니다. 장비 시스템과 고객지원 사업을 포함하며 특정 공정 장비의 실적만 분리한 값이 아닙니다. 6월 말 52/53주 결산의 실제 종료일을 사용합니다.'),
    'amat':dict(name='Applied Materials · AMAT',cik=6951,fiscal_start=11,
        scope='Applied Materials 전사 연결 · 반도체 장비·서비스 등 포함',
        note='Applied Materials 연결 전체 기준입니다. 반도체 장비 외 서비스·디스플레이 등 공시 연결 사업을 포함합니다. 10월 말 52/53주 결산의 실제 종료일을 사용합니다.'),
    'kla':dict(name='KLA · KLAC',cik=319201,fiscal_start=7,
        profit_label='GAAP 기반 영업이익 · 계산',
        profit_description='GAAP 연결 매출 − 매출원가 − 연구개발비 − 판매관리비 − 영업상 손상차손으로 계산한 연결 영업이익입니다. 영업이익 소계가 없는 공시를 보완하며 회사의 비GAAP 조정 이익과 다릅니다. 직접 공시된 과거 영업이익은 그 값을 사용합니다.',
        scope='KLA 전사 연결 · 공정제어·검사·서비스 등 포함',
        note='KLA 연결 전체 기준입니다. 공정제어·검사·서비스 및 연결 사업을 포함하며 계측 장비만의 매출이 아닙니다. 6월 결산으로 인수·매각 및 사업 재편 영향을 포함합니다.'),
}
for company in COMPANIES.values():
    company['revenue_description']='회사 전체 연결 매출입니다. 개별 장비·공정 매출이나 수주액이 아니며 인수·매각 등 연결 범위 변경을 포함합니다.'
    company['note']+=' 매출·영업이익은 GAAP 기준이며 조정 영업이익과 구분합니다. CAPEX는 회사 자신의 투자 현금지출로 고객사 설비투자나 장비 수주액이 아닙니다. '+company.get('capex_description','CAPEX는 유형자산 취득 현금지출입니다.')+' 연간은 공시된 완결 회계연도 실적입니다.'
    if company.get('profit_description'):company['note']+=' '+company['profit_description']


def prepare_payload(key,payload):
    """Derive KLA's missing operating subtotal within one exact filing context."""
    if key!='kla':return payload
    payload=copy.deepcopy(payload);facts=payload['facts']['us-gaap']
    def index(tags):
        result={}
        for tag in tags:
            for fact in facts.get(tag,{}).get('units',{}).get('USD',[]):
                if fact.get('start'):
                    result.setdefault((fact['accn'],fact['start'],fact['end']),dict(fact,source_tag='us-gaap:'+tag))
        return result
    revenue=index(['RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet','Revenues'])
    cost=index(['CostOfRevenue'])
    research=index(['ResearchAndDevelopmentExpense'])
    administration=index(['SellingGeneralAndAdministrativeExpense'])
    impairment=index(['AssetImpairmentCharges','GoodwillImpairmentLoss'])
    target=facts.setdefault('OperatingIncomeLoss',dict(units={'USD':[]}))['units']['USD']
    reported={(f['accn'],f.get('start'),f['end']) for f in target}
    for context,revenue_fact in revenue.items():
        if revenue_fact['end']<'2014-01-01':continue
        if context in reported or any(context not in source for source in (cost,research,administration)):continue
        inputs=[revenue_fact,cost[context],research[context],administration[context]]
        if context in impairment:inputs.append(impairment[context])
        target.append(dict(revenue_fact,val=inputs[0]['val']-sum(f['val'] for f in inputs[1:]),
            source_tag='derived: GAAP revenue - cost of revenue - R&D - SG&A - operating impairment',
            derivation='GAAP revenue - cost of revenue - R&D - SG&A - operating impairment; same accession/start/end; impairment zero when absent',
            inputs=[dict(tag=f['source_tag'],value=f['val']) for f in inputs]))
    return payload


def collect(offline=False):
    asof=today();state=load(OUT/'equipment_state.json',dict(companies={}))
    CACHE.mkdir(parents=True,exist_ok=True)
    if not offline:
        session=requests.Session()
        session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
        for key,company in COMPANIES.items():
            prior=state['companies'].get(key,{})
            try:
                response=session.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{company["cik"]:010d}.json',timeout=40)
                response.raise_for_status();payload=response.json()
                prepared=prepare_payload(key,payload)
                rows=parse_facts(prepared,company,asof);annual=parse_annual(prepared,company,asof)
                if any(metric not in row for row in rows+annual for metric in ('revenue','profit','capex')):
                    raise ValueError('Incomplete equipment metric history')
                if prior.get('rows') and rows[-1]['date']<prior['rows'][-1]['date']:raise ValueError('Source regressed')
                if prior.get('rows') and len(rows)<len(prior['rows']):raise ValueError('Equipment history shortened')
                if not annual:raise ValueError('Missing annual accounts')
                state['companies'][key]=dict(rows=rows,annual=annual,checked=asof,fetched=asof,ok=True)
                save(CACHE/(key+'_facts.json'),payload)
                print(key,len(rows),'quarters',rows[0]['date'],'to',rows[-1]['date'],len(annual),'fiscal years')
            except Exception as error:
                if not prior.get('rows'):raise RuntimeError(key+': no successful equipment data') from error
                state['companies'][key]=dict(prior,checked=asof,ok=False)
                print(key,'retained previous data:',type(error).__name__)
            time.sleep(.4)
    docs={}
    for key,company in COMPANIES.items():docs.update(build_company(key,state['companies'][key],company))
    save(OUT/'equipment_state.json',state)
    for identifier,doc in docs.items():save(OUT/(identifier+'.json'),doc)
    print('Published',len(docs),'equipment company charts')
    return state


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true')
    collect(parser.parse_args().offline)

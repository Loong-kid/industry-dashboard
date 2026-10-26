"""Oil majors: reviewed consolidated statements with per-point provenance."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import re
import warnings
from bs4 import BeautifulSoup,XMLParsedAsHTMLWarning
from collect_oil_sources import CACHE,collect as download_sec
from fetch_cpu_companies import parse_facts,parse_annual,build_company,save,today
from oil_sources import statement_facts,bp_quarter_facts,shell_quarter_facts,html_row,quarter_end
from oil_ir import tte_pdf,equinor_pdf,shell_workbook,shell_2020_pdf,equinor_usd_history,ref

warnings.filterwarnings('ignore',category=XMLParsedAsHTMLWarning)
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/oil';STATE=OUT/'state.json'
METRICS=['revenue','profit','capex']
SPECS={
 'xom':dict(name='ExxonMobil · XOM',cik=34088,scope='전사 연결 · 통합 석유·가스·정유·화학',capex_label='유형자산 현금취득',capex_description='현금흐름표 Additions to property, plant and equipment. 회사의 Capital and exploration expenditures 총액과 구분합니다.',note='2026년 7월 지주회사 전환 전후를 동일 그룹의 계속 이력으로 연결하며 중복 합산하지 않습니다. 2026년 Q2는 승계 법인의 공시입니다.'),
 'cvx':dict(name='Chevron · CVX',cik=93410,scope='전사 연결 · 통합 석유·가스·정유',capex_label='공시 Capital expenditures',capex_description='연결 현금흐름표 Capital expenditures입니다. 비연결 관계사의 별도 투자·주식 취득과 구분합니다.',note='Hess 등 인수에 따른 연결 범위 변화가 포함됩니다. 연결 매출과 정유 단독 매출은 다릅니다.'),
 'shell':dict(name='Shell · SHEL',cik=1306965,scope='전사 연결 · 석유·가스·LNG·정유·화학·전력',capex_label='공시 Capital expenditure',capex_description='현금흐름표 Capital expenditure의 지출액입니다. JV·관계사·지분증권 투자 등을 더하는 Cash capital expenditure와 다릅니다.',note='Royal Dutch Shell에서 Shell plc로 이어지는 그룹 연결 실적입니다. 원유 단독 매출이 아니며 BG 인수 등 연결 범위 변화가 포함됩니다.'),
 'bp':dict(name='BP',cik=313807,scope='전사 연결 · 통합 석유·가스·정유',capex_label='유·무형자산 등 현금취득',capex_description='현금흐름표 Expenditure on property, plant and equipment, intangible and other assets입니다. 인수 등을 포함하는 회사 발표 Total cash capital expenditure와 구분합니다.',note='매출은 Sales and other operating revenues입니다. 영업손익은 회사 공시 Profit before interest and taxation이며 underlying replacement-cost 조정 이익이 아닙니다. 자산 처분·손상·관계사 이익이 포함될 수 있습니다.'),
 'tte':dict(name='TotalEnergies · TTE',cik=879764,scope='전사 연결 · 석유·가스·정유·화학·전력',capex_label='유·무형자산 현금취득',capex_description='Intangible assets and property, plant and equipment additions의 현금 지출액입니다. Organic/Net investments 및 인수 대금과 구분합니다.',note='매출은 소비세를 뺀 Revenues from sales입니다. 연간·분기는 해당 시점 회사 Accounts 원문의 공표 실적이며 이후 재작성 비교값과 차이가 있을 수 있습니다.'),
 'cop':dict(name='ConocoPhillips · COP',cik=1163165,scope='전사 연결 · 탐사·생산 중심 (통합 정유사와 사업 범위 상이)',capex_label='Capital expenditures and investments',capex_description='현금흐름표 Capital expenditures and investments입니다. 회사 정의에 따른 투자 범위를 유지하며 유형자산만의 취득액으로 해석하지 않습니다.',note='2012년 Phillips 66 분사 이후 탐사·생산 중심 기업입니다. Marathon Oil 등 인수에 따른 연결 범위 변화가 포함됩니다.'),
 'equinor':dict(name='Equinor · EQNR',cik=1140625,scope='전사 연결 · 탐사·생산·가스·마케팅·전력',capex_label='Capital expenditures and investments',capex_description='연결 현금흐름표 Capital expenditures and investments입니다. 회사 별도 Organic capex·인수액과 구분합니다.',note='Statoil에서 Equinor로 이어지는 그룹 이력입니다. 2014–2015년은 회사가 2016년 공개한 USD 환산 자료이며 NOK 원문을 달러 자료에 그대로 붙이지 않습니다. 매출은 Revenues, 영업손익은 Net operating income입니다.'),
}
for key,spec in SPECS.items():
    spec.update(fiscal_start=1,revenue_description='회사 전체 연결 매출입니다. 원유 채굴 매출 또는 정유 단독 매출이 아니며 회사 간 합산하지 않습니다.')
    if key in ['xom','cvx','cop']:
        spec.update(profit_label='계산 영업손익',profit_description='원문 손익계산서의 매출 − 총 비용 + 별도 표시 이자비용으로 계산합니다. 지분법 이익·자산 처분 등 기타 매출 외 수익을 제외하며, 비금융 기타 비용은 포함합니다. 회사가 별도 공시한 GAAP Operating income 항목 또는 조정 이익이 아닙니다.')
    elif key=='shell':spec.update(profit_label='계산 영업손익',profit_description='세전손익 + 이자비용 − Interest and other income으로 계산합니다. JV·관계사 손익은 포함하며, 이자 및 기타수익을 제외합니다. 회사 공시 Adjusted earnings·EBITDA가 아닙니다.')
    elif key=='tte':spec.update(profit_label='계산 영업손익',profit_description='소비세 제외 매출 − 매입 − 기타 영업비용 − 탐사비 − 감가·손상 + 기타수익 − 기타비용으로 계산합니다. 금융손익·지분법손익·법인세는 제외하고, 처분·손상 등 원문 항목은 포함합니다. Adjusted net operating income과 다릅니다.')
    else:spec.update(profit_label='공시 영업손익',profit_description=spec['note'])
    spec['note']+=' '+spec['capex_description']

def load(path,default):return json.loads(path.read_bytes()) if path.exists() else default

def merge_rows(previous,updates):
    rows={r['date']:copy.deepcopy(r) for r in previous}
    for r in updates:
        target=rows.setdefault(r['date'],{k:v for k,v in r.items() if k not in METRICS and k!='refs'});target.setdefault('refs',{})
        for metric in METRICS:
            if metric not in r:continue
            old=target['refs'].get(metric,{})
            if r['refs'][metric].get('filed','')>=old.get('filed',''):
                target[metric]=r[metric];target['refs'][metric]=r['refs'][metric]
    return [r for _,r in sorted(rows.items())]

def normalized_payload(key,facts):
    tags={m:'OilReviewed'+m.title() for m in METRICS}
    return dict(cik=SPECS[key]['cik'],facts={'us-gaap':{tags[m]:dict(units={'USD':[dict(f,tag=tags[m]) for f in facts if f['metric']==m]}) for m in METRICS}}),{m:[t] for m,t in tags.items()}

def sec_rows(key):
    facts=[]
    for identity in (['xom_successor',key] if key=='xom' else [key]):
        for acc,meta in load(CACHE/f'{identity}-filings.json',{}).items():
            if meta['form'] not in ['10-K','10-K/A','10-Q','10-Q/A']:continue
            meta=dict(meta,accn=acc)
            facts+=statement_facts((CACHE/meta['path']).read_bytes(),meta,key)
    payload,tags=normalized_payload(key,facts)
    spec=dict(SPECS[key],tags=tags)
    return parse_facts(payload,spec,today(),tags),parse_annual(payload,spec,today(),tags),facts

def ifrs_rows(key):
    d=load(CACHE/f'{key}-facts.json',{})
    if not d:raise ValueError('Missing IFRS source')
    tags={'revenue':['Revenue' if key=='shell' else 'RevenueAndOperatingIncome'],'profit':['ProfitLossFromOperatingActivities'],'capex':['PurchaseOfOtherLongtermAssetsClassifiedAsInvestingActivities' if key=='shell' else 'PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets']}
    source=d['facts']['ifrs-full'];facts=[]
    for metric,names in tags.items():
        for name in names:
            for f in source.get(name,{}).get('units',{}).get('USD',[]):
                if not f.get('start'):continue
                facts.append(dict(f,metric=metric,source_tag='ifrs-full:'+name))
    if key=='shell':
        # Match exact original filing, start and end; no cross-vintage subtraction.
        maps={name:{(f.get('accn'),f.get('start'),f.get('end')):f for f in source[name]['units']['USD']} for name in ['ProfitLossBeforeTax','InterestExpense','FinanceIncome']}
        for period,pbt in maps['ProfitLossBeforeTax'].items():
            if period not in maps['InterestExpense'] or period not in maps['FinanceIncome']:continue
            interest=maps['InterestExpense'][period];other=maps['FinanceIncome'][period]
            facts.append(dict(pbt,metric='profit',val=pbt['val']+interest['val']-other['val'],source_tag='IFRS original income statement subtotal',derivation='PBT + interest expense − interest and other income',inputs=[pbt,interest,other]))
    if key=='bp':
        facts=[] # Published main statement rows take priority over restated tag pools.
        for acc,meta in load(CACHE/'bp-filings.json',{}).items():
            if meta['form']!='6-K':continue
            facts+=bp_quarter_facts((CACHE/meta['path']).read_bytes(),dict(meta,accn=acc))
    if key=='shell':
        for acc,meta in load(CACHE/'shell-filings.json',{}).items():
            if meta['form']=='6-K':facts+=shell_quarter_facts((CACHE/meta['path']).read_bytes(),dict(meta,accn=acc))
    payload,names=normalized_payload(key,facts);spec=dict(SPECS[key],tags=names)
    annual_payload,_=normalized_payload(key,[f for f in facts if key!='bp' or f['end']==f.get('statement_period')])
    return parse_facts(payload,spec,today(),names),parse_annual(annual_payload,spec,today(),names),facts

def classic_foreign_annual(key):
    result=[]
    patterns={'revenue':r'^Revenue\b','pbt':r'^Income (?:before taxation|before tax)\b','interest':r'^Interest expense\b','other':r'^Interest and other income\b','capex':r'^Capital expenditure\b'} if key=='shell' else {'revenue':r'^Sales and other operating revenues\b','profit':r'^Profit (?:\(loss\) )?before interest and tax(?:ation)?\b','capex':r'^(?:Expenditure on property, plant and equipment, intangible and other assets|Capital expenditure)\b'}
    for meta in load(CACHE/f'{key}-filings.json',{}).values():
        if meta['form'] not in ['20-F','20-F/A']:continue
        y=int(meta['date'][:4]);soup=BeautifulSoup((CACHE/meta['path']).read_bytes(),'lxml');found={}
        for field,pattern in patterns.items():
            inline,values=html_row(soup,pattern,3)
            if values is not None:found[field]=values
        for i in range(3):
            year=y-i
            if year<2014:continue
            r=dict(date=f'{year}-12-31',year=year,refs={})
            for field in METRICS:
                value=found.get(field,[None]*3)[i]
                if field=='profit' and key=='shell' and all(n in found for n in ['pbt','interest','other']):value=found['pbt'][i]+found['interest'][i]-found['other'][i]
                if value is None:continue
                r[field]=abs(value) if field=='capex' else value;r['refs'][field]=ref(meta['url'],f'{year}-01-01',r['date'],'20-F original annual statement row',meta['filed'])
            if r['refs']:result.append(r)
    return result

def documents(key,cohort,spec):
    docs={}
    for id,doc in build_company(key,cohort,spec).items():
        doc['source']='기업 공식 재무제표 · SEC / IR';doc['frequency_label']='분기 · 회사 연결 실적'
        doc['basis_details'][1]['value']='공표된 독립 분기를 우선하며, 누적만 있는 현금흐름표는 동일 회계연도 누적의 차이로 계산합니다. 연간은 공표된 완결 연도입니다. 미확인 분기는 빈칸으로 남기며 연간을 4등분하지 않습니다. 공시 시점·재분류·반올림으로 분기 합계와 재작성 연간에 차이가 있을 수 있습니다.'
        metric=id.rsplit('_',1)[-1]
        observed=[r for r in cohort['rows'] if metric in r];years=[r for r in cohort['annual'] if metric in r]
        doc['basis_details'].insert(0,dict(label='수록 기간',value=f"분기 {observed[0]['date']} ~ {observed[-1]['date']} · {len(observed)}개 / 연간 {years[0]['year']} ~ {years[-1]['year']} · {len(years)}개. 미확인 분기는 선을 연결하지 않습니다."))
        if observed[0]['date']>'2014-03-31':
            doc['description']+=f" 분기는 {observed[0]['date']}부터 확인한 자료이며, 그 이전 실적은 연간 보기에서 확인할 수 있습니다."
        if spec['profit_label']=='계산 영업손익' and id.endswith('_profit'):doc['name']=spec['name']+' · 영업손익 (계산)'
        docs[id]=doc
    return docs

def collect(offline=False,keys=None):
    previous=load(STATE,dict(companies={}))
    status={};ir_status={}
    if not offline:
        status=download_sec()
        from collect_oil_ir import collect as download_ir
        ir_status=download_ir()
    files=load(ROOT/'manual/oil/source_files.json',{})
    docs={};state=dict(schema_version=1,updated=today(),companies=copy.deepcopy(previous.get('companies',{})) if keys else {})
    for key,spec in SPECS.items():
        if keys and key not in keys:continue
        old=previous['companies'].get(key,{})
        try:
            if not offline and not status.get(key,{}).get('ok'):raise ValueError('SEC source check failed')
            if not offline and key in ir_status and not ir_status[key]['ok']:raise ValueError('Issuer IR source check failed')
            if key in ['xom','cvx','cop']:rows,annual,facts=sec_rows(key)
            elif key in ['shell','bp']:
                rows,annual,facts=ifrs_rows(key)
                if key=='shell':annual=merge_rows(classic_foreign_annual(key),annual)
            else:rows=[];annual=[];facts=[]
            if key in ['tte','equinor']:
                parser=tte_pdf if key=='tte' else equinor_pdf
                for name,meta in sorted(files.items()):
                    if not name.startswith(key+'-') or not name.endswith('.pdf') or meta['filed']>today():continue
                    if not (CACHE/name).exists():continue
                    for is_annual,r in parser(CACHE/name,meta['url'],meta['filed']):
                        if is_annual:annual=merge_rows(annual,[r])
                        else:rows=merge_rows(rows,[r])
                if key=='equinor':
                    meta=files['equinor-usd-2014-2015.xlsx']
                    for is_annual,r in equinor_usd_history(CACHE/'equinor-usd-2014-2015.xlsx',meta['url']):
                        if is_annual:annual=merge_rows(annual,[r])
                        else:rows=merge_rows(rows,[r])
            if key=='shell':
                meta=files['shell-2020.pdf']
                for is_annual,r in shell_2020_pdf(CACHE/'shell-2020.pdf',meta['url']):
                    if is_annual:annual=merge_rows(annual,[r])
                    else:rows=merge_rows(rows,[r])
                for name,meta in files.items():
                    if not name.startswith('shell-quarterly-') or meta['filed']>today() or not (CACHE/name).exists():continue
                    for is_annual,r in shell_workbook(CACHE/name,meta['url'],meta['filed']):
                        if is_annual:annual=merge_rows(annual,[r])
                        else:rows=merge_rows(rows,[r])
            rows=[r for r in rows if r['date']>='2014-01-01' and r['date']<=today()];annual=[r for r in annual if r['year']>=2014 and r['date']<=today()]
            if not offline and previous.get('schema_version')==1:
                rows=merge_rows(old.get('rows',[]),rows);annual=merge_rows(old.get('annual',[]),annual)
            if not rows or not annual or not all(any(m in r for r in rows) and any(m in r for r in annual) for m in METRICS):raise ValueError('Incomplete issuer statement metrics')
            cohort=dict(rows=rows,annual=annual,facts=facts,fetched=today(),checked=today(),ok=True)
            print(key,len(rows),'quarters',len(annual),'years',[(m,sum(m in r for r in rows)) for m in METRICS],flush=True)
        except Exception as error:
            print(key,'source check failed:',str(error)[:150],flush=True)
            if not old:raise
            cohort=dict(old,checked=today(),ok=False)
        state['companies'][key]=cohort
        docs.update(documents(key,cohort,spec))
    for id,doc in docs.items():save(OUT/(id+'.json'),doc)
    save(STATE,state)
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--company',choices=list(SPECS),action='append');args=parser.parse_args();collect(args.offline,args.company)

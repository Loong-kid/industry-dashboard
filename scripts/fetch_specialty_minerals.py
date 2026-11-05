"""Public issuer accounts for AA, CENX, ALM, VNP, UAMY and AFM.

SEC companyfacts for US issuers; original IFRS financial-statement PDFs for
Canadian issuers. Each observation retains its source and reporting currency.
"""
import argparse
import calendar
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import pymupdf
import requests
from bs4 import BeautifulSoup

from fetch_cpu_companies import ROOT, TAGS, build_company, load, parse_annual, parse_facts, save, today
from oil_sources import pdf_row

CACHE=ROOT/'.cache/specialty-minerals'
OUT=ROOT/'data/commodities'
HISTORY=OUT/'specialty_financial_history.json'
PDF_SINCE=2022
COMPANIES={
    'aa':dict(name='Alcoa',cik=1675149,currency='USD',fiscal_start=1,tags={'profit':['SpecialtyOperatingSubtotal']},
        scope='알루미늄·알루미나·보크사이트 연결 전체',profit_label='영업손익 · 계산',
        profit_description='별도 영업이익 소계가 없어 세전손익 + 이자비용 − 순영업외손익으로 계산합니다. 회사 조정 EBITDA와 다릅니다.',
        note='2016년 분사한 현재 Alcoa Corporation입니다. 과거 비교 공시는 현재 법인의 연결 범위로 제공된 수치입니다. 영업손익은 세전손익에 이자비용을 더하고 순영업외손익(NonoperatingIncomeExpense)을 차감합니다. CAPEX는 유형자산 현금취득입니다.'),
    'cenx':dict(name='Century Aluminum',cik=949157,currency='USD',fiscal_start=1,
        scope='1차 알루미늄 제련·알루미나 등 연결 전체',note='GAAP 연결 매출·영업손익과 유형자산 현금취득입니다. 주력 제품은 1차 알루미늄이며 자산 인수에 따른 연결 범위 변경을 포함합니다.'),
    'uamy':dict(name='United States Antimony',cik=101538,currency='USD',fiscal_start=1,
        scope='안티모니·제올라이트 등 연결 전체',note='안티모니 제련·판매 외 제올라이트 등도 포함한 GAAP 전사 실적입니다. 미국 상장 보통주 UAMY를 사용합니다. CAPEX는 유형자산 현금취득입니다.'),
    'alm':dict(name='Almonty Industries',cik=1670061,currency='CAD',fiscal_start=1,
        scope='텅스텐 광산·상동 개발 등 연결 전체',profit_label='영업손익 · 계산',
        profit_description='광산 영업손익에서 일반관리비와 주식기준보상비용을 차감한 계산 소계입니다. 이자·환차손익·파생상품 평가손익을 제외합니다. 순이익 또는 광산 EBITDA와 다릅니다.',
        capex_label='광산자산 현금취득',capex_description='현금흐름표 Additions to mining assets입니다. 상동 등 개발투자를 포함하며 회계상 광산자산 증감과 다릅니다.',
        note='IFRS·CAD 백만. 주가 ALM은 USD이므로 밸류에이션에서 환율을 맞춥니다. 영업손익은 광산손익−일반관리비−주식보상 계산값입니다. 2022년 이후 공식 PDF 및 비교 기간을 수집합니다. 이전 9월 결산기를 현재 12월 결산 분기에 이어 붙이지 않습니다.'),
    'vnp':dict(name='5N Plus',cik=900000001,currency='USD',fiscal_start=1,
        scope='Specialty Semiconductors·Performance Materials 연결 전체',profit_label='IFRS 영업이익',
        note='IFRS·USD 백만, 주가 VNP.TO는 CAD입니다. 비스무트 단일 광산기업이 아닌 특수반도체·소재 기업입니다. 비스무트 관련 Performance Materials 외 사업을 포함합니다. CAPEX는 유형자산 현금취득이며 무형자산 취득은 제외합니다. 2022년 이후 공식 PDF와 비교 기간을 수집합니다.'),
    'afm':dict(name='Alphamin Resources',cik=900000002,currency='USD',fiscal_start=1,
        scope='DR콩고 Bisie 주석 광산 연결 전체',profit_label='IFRS 영업이익',
        capex_label='장비 현금취득 · 탐사투자 제외',capex_description='현금흐름표 Purchase of equipment입니다. 별도 표시되는 탐사·평가자산 투자, 환경예치금과 리스 원금은 포함하지 않습니다.',
        note='IFRS·USD 백만, 주가 AFM.V는 CAD입니다. 광산 자회사를 포함한 연결 전체 실적입니다. CAPEX는 장비 현금취득이며 별도 탐사투자를 포함하는 회사 발표 총 CAPEX와 다릅니다. 2022년 이후 공식 PDF 및 비교 기간을 수집하며 아직 발표되지 않은 분기 가이던스는 실적에 넣지 않습니다.'),
}
for meta in COMPANIES.values():
    meta.setdefault('revenue_description','회사 전체 연결 매출입니다. 특정 광물만의 판매액과 다를 수 있으며 인수·매각 등 연결 범위 변경을 포함합니다.')
    meta.setdefault('profit_description','회사 전체 연결 영업손익입니다. 조정 EBITDA·조정 영업이익과 구분합니다.')

MONTHS={m.lower():i for i,m in enumerate(calendar.month_name) if m}
DATE_RE=re.compile(r'('+'|'.join(calendar.month_name[1:])+r')\s+(\d{1,2})\s*,?\s*(20\d{2})',re.I)

def dates(text):
    result=[]
    for month,day,year in DATE_RE.findall(text):
        try:result.append(dt.date(int(year),MONTHS[month.lower()],int(day)).isoformat())
        except ValueError:pass
    return result

def normalize_aa(payload):
    """Match all three inputs to the same original accession AND duration."""
    g=payload['facts']['us-gaap']
    tags=['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest','InterestExpense','NonoperatingIncomeExpense']
    by={tag:{(x.get('start'),x['end'],x['accn']):x for x in g.get(tag,{}).get('units',{}).get('USD',[]) if x.get('start')} for tag in tags}
    facts=[]
    for key in set.intersection(*(set(v) for v in by.values())):
        inputs=[by[tag][key] for tag in tags]
        facts.append(dict(inputs[0],val=inputs[0]['val']+inputs[1]['val']-inputs[2]['val'],
            source_tag='calculated:pre-tax+interest-net-nonoperating',derivation='세전손익 + 이자비용 − 순영업외손익',
            inputs=[dict(tag=tag,val=f['val']) for tag,f in zip(tags,inputs)]))
    g['SpecialtyOperatingSubtotal']={'units':{'USD':facts}}
    return payload

def get(session,url,refresh=False):
    CACHE.mkdir(parents=True,exist_ok=True)
    suffix='.pdf' if '.pdf' in url.lower() else '.html'
    target=CACHE/(hashlib.sha256(url.encode()).hexdigest()+suffix)
    if not target.exists() or (refresh and suffix!='.pdf'):
        response=session.get(url,timeout=65);response.raise_for_status()
        if suffix=='.pdf' and not response.content.startswith(b'%PDF'):raise ValueError('Not a public PDF: '+url)
        target.write_bytes(response.content)
        time.sleep(.12)
    return target

def discover(session,key,refresh=False):
    if key=='vnp':
        urls=[]
        for year in range(PDF_SINCE,int(today()[:4])+1):
            base='https://www.5nplus.com/en/investors/financial-documents/?year='+str(year)
            soup=BeautifulSoup(get(session,base,refresh).read_text(encoding='utf8'),'html.parser')
            urls.extend(urljoin(base,a['href']) for a in soup.select('a[href]') if '.pdf' in a['href'].lower() and 'Financial Statements' in a.get_text())
    else:
        base='https://almonty.com/investors/financials/' if key=='alm' else 'https://www.alphaminresources.com/financial-reports/'
        soup=BeautifulSoup(get(session,base,refresh).read_text(encoding='utf8'),'html.parser');urls=[]
        for a in soup.select('a[href]'):
            url=urljoin(base,a['href']);name=url.rsplit('/',1)[-1].lower()
            if '.pdf' not in name or not re.search(r'financial|(?:^|[_-])fs[_-]',name) or re.search('mda|aif|md_a|certificat',name):continue
            # Re-uploaded archives may have a newer directory; use the filename year.
            years=re.findall(r'20(?:1[0-9]|2[0-9])',name)
            short=re.search(r'(?:fs[_-]|aii_)(2[2-9])(?:0[1-9]|1[0-2])',name)
            if not years and short:years=['20'+short[1]]
            if years and max(map(int,years))<PDF_SINCE:continue
            urls.append(url)
    return list(dict.fromkeys(urls))

def numeric_row(page,label,n):
    values=pdf_row(page,label)
    if values is None or len(values)<n:return None
    return values[-n:]

def statement_rows(document,key,url,asof):
    """Read only statement pages, never MD&A or forecasts. Fail closed on layout."""
    pages=[(i,document[i],document[i].get_text(sort=True)) for i in range(min(30,len(document)))]
    text='\n'.join(t for _,_,t in pages)
    approval=[]
    for match in re.finditer(r'(?:authori[sz]ed for issuance|approved.{0,8}by|approved and authori[sz]ed)',text,re.I):
        approval.extend(dates(text[match.start():match.start()+350]))
    approval=[d for d in approval if d<=asof]
    if not approval:raise ValueError('No dated board approval: '+url)
    filed=max(approval)
    output={m:[] for m in TAGS}
    for page_no,page,content in pages:
        flat=' '.join(content.split())
        is_cash=bool(re.search(r'CONSOLIDATED STATEMENTS OF CASH FLOWS',flat,re.I))
        is_income=bool(re.search(r'CONSOLIDATED STATEMENTS OF (?:\(LOSS\)\s*)?(?:EARNINGS|OPERATIONS|PROFIT)',flat,re.I))
        if not (is_cash or is_income):continue
        first='Net income|Net profit|Operating activities|Cash Flows From Operating' if is_cash else r'Revenue[s]?|REVENUE'
        found=re.search(first,content,re.I)
        if not found:continue
        header=content[:found.start()]
        year_lines=[re.findall(r'\b20\d{2}\b',line) for line in header.splitlines()]
        year_cols=max(year_lines,key=len,default=[])
        if len(year_cols) not in (2,3,4):continue
        currency_text=' '.join(header.lower().split())
        if key=='alm' and not re.search(r'(?:thousands|000.s) of canadian dollars',currency_text):raise ValueError('Unexpected Almonty financial currency or scale')
        if key=='vnp' and 'thousands of united states dollars' not in currency_text:raise ValueError('Unexpected 5N financial currency or scale')
        if key=='afm' and not re.search(r'(?:us dollars|united states dollars)',currency_text):raise ValueError('Unexpected Alphamin currency or scale')
        n=len(year_cols);year=max(map(int,year_cols))
        month_names=re.findall(r'\b('+'|'.join(calendar.month_name[1:])+r')\b',header,re.I)
        if not month_names:continue
        month=MONTHS[month_names[-1].lower()]
        if month not in (3,6,9,12):raise ValueError('Unexpected fiscal month')
        end=dt.date(year,month,calendar.monthrange(year,month)[1]).isoformat()
        if end>asof or filed<end:continue
        annual=month==12 and not re.search(r'three.month|three months',header,re.I)
        if annual:periods=[(int(y),1,12) for y in year_cols]
        elif n==4 and key=='afm':periods=[(year,1,month),(year-1,1,month),(year,month-2,month),(year-1,month-2,month)]
        elif n==4:periods=[(year,month-2,month),(year-1,month-2,month),(year,1,month),(year-1,1,month)]
        elif n==2:periods=[(year,1 if is_cash or month==3 else month-2,month),(year-1,1 if is_cash or month==3 else month-2,month)]
        else:raise ValueError('Unexpected statement columns')
        unit=1000 if key in ('vnp','alm') else 1
        patterns={'revenue':r'^Revenue[s]?\b','profit':r'^Operating (?:\(loss\)\s*)?(?:earnings|profit|income)(?:\s*\(loss\))?',
            'capex':r'^Additions to property, plant and equipment' if key=='vnp' else r'^Additions to mining assets' if key=='alm' else r'^Purchase of equipment'}
        metrics=['capex'] if is_cash else ['revenue','profit']
        for metric in metrics:
            values=numeric_row(page,patterns[metric],n)
            derivation=None
            if key=='alm' and metric=='profit':
                parts=[numeric_row(page,pat,n) for pat in (r'^(?:\(Loss\)\s*)?(?:Income|Loss|Earnings)\s*(?:\(loss\)\s*)?from mining operations',r'^General and administrative',r'^Share.based compensation')]
                values=[a-b-c for a,b,c in zip(*parts)] if all(x is not None for x in parts) else None
                derivation='광산손익 − 일반관리비 − 주식기준보상'
            if values is None:raise ValueError(f'{key} {metric} statement row missing: {url} page {page_no+1}')
            for column,((y,start_month,end_month),value) in enumerate(zip(periods,values)):
                start=f'{y}-{start_month:02d}-01';finish=dt.date(y,end_month,calendar.monthrange(y,end_month)[1]).isoformat()
                fact=dict(start=start,end=finish,val=(abs(value) if metric=='capex' else value)*unit,
                    filed=filed,form='20-F' if annual else '6-K',accn=url,source_url=url+'#page='+str(page_no+1),
                    source_tag='PDF:'+patterns[metric],approval_date=filed)
                if derivation:fact.update(derivation=derivation,source_tag='calculated:mine-profit-general-administration-share-compensation',
                    inputs=[dict(tag=label,val=part[column]*unit) for label,part in zip(('mining operating profit','general and administrative','share-based compensation'),parts)])
                output[metric].append(fact)
    if not all(output.values()):raise ValueError('Incomplete original statements: '+url)
    return output

def pdf_payload(session,key,asof,refresh=False):
    meta=COMPANIES[key];facts={m:[] for m in TAGS};sources=discover(session,key,refresh);errors=[]
    if not sources:raise ValueError('No public statements discovered')
    for url in sources:
        try:
            with pymupdf.open(get(session,url)) as document:values=statement_rows(document,key,url,asof)
            for metric,rows in values.items():facts[metric].extend(rows)
        except Exception as error:
            errors.append(dict(url=url,error=str(error)))
            print(key,'source unavailable:',str(error)[:220],flush=True)
    if not all(facts.values()):raise ValueError('No complete statement series: '+key+' '+str(errors[:2]))
    return dict(cik=meta['cik'],facts={'us-gaap':{TAGS[m][0]:{'units':{meta['currency']:rows}} for m,rows in facts.items()}}),errors,len(sources)

def collect(offline=False):
    asof=today();state=load(HISTORY,dict(companies={}))
    CACHE.mkdir(parents=True,exist_ok=True)
    session=requests.Session();session.headers['User-Agent']='Mozilla/5.0 (industry-dashboard public issuer research)'
    docs={}
    for key,meta in COMPANIES.items():
        prior=state['companies'].get(key,{})
        if not offline:
            try:
                errors=[];count=1
                if key in ('aa','cenx','uamy'):
                    response=session.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{meta["cik"]:010d}.json',timeout=65);response.raise_for_status()
                    payload=response.json();(CACHE/f'{key}_facts.json').write_bytes(response.content)
                    # Calendar-year issuers: quarantine malformed SEC duration
                    # contexts (e.g. UAMY's comparative 2020-09-23 YTD typo).
                    # Do not move them to a different date or duplicate a quarter.
                    for fact in payload['facts']['us-gaap'].values():
                        for unit,values in fact.get('units',{}).items():
                            fact['units'][unit]=[f for f in values if not f.get('start') or f['end'][5:] in ('03-31','06-30','09-30','12-31')]
                    if key=='aa':payload=normalize_aa(payload)
                else:payload,errors,count=pdf_payload(session,key,asof,True)
                if errors and prior.get('rows'):raise ValueError('Incomplete source refresh; retaining the complete successful cohort: '+str(errors[:2]))
                rows=parse_facts(payload,meta,asof);annual=parse_annual(payload,meta,asof)
                if prior.get('rows') and rows[-1]['date']<prior['rows'][-1]['date']:raise ValueError('Source regressed')
                # A changed issuer archive must not erase earlier successful
                # observations. Keep old values only where the new source is
                # absent, never in place of an actual reported revision.
                for field,new_rows in (('rows',rows),('annual',annual)):
                    bydate={r['date']:r for r in new_rows}
                    for old in prior.get(field,[]):
                        if old['date'] not in bydate:
                            bydate[old['date']]=old
                            continue
                        current=bydate[old['date']]
                        for metric in TAGS:
                            if current.get(metric) is None and old.get(metric) is not None:
                                current[metric]=old[metric];current['refs'][metric]=old['refs'][metric]
                    new_rows[:]=[row for _,row in sorted(bydate.items())]
                state['companies'][key]=dict(rows=rows,annual=annual,checked=asof,fetched=asof,ok=not errors,source_count=count,source_errors=errors)
                save(HISTORY,state)
                print(key,len(rows),'quarters',len(annual),'years',rows[-1]['date'],'source errors',len(errors),flush=True)
            except Exception as error:
                if not prior.get('rows'):raise RuntimeError(key+': no successful history') from error
                state['companies'][key]=dict(prior,checked=asof,ok=False,error=str(error));print(key,'retained history',str(error),flush=True)
        cohort=state['companies'][key]
        for id,doc in build_company('specialty_'+key,cohort,meta).items():
            doc.update(unit=meta['currency']+' 백만',frequency_label='분기 · 공식 공시',source=meta['name']+' 공식 재무제표',auto_collect_time='08:35')
            if id.endswith('_profit') and key in ('aa','alm'):doc['name']=meta['name']+' · 영업손익(계산)'
            doc['basis_details'].append(dict(label='자료 범위',value=meta['note']))
            if key in ('alm','vnp','afm'):
                doc['basis_details'].append(dict(label='PDF 날짜',value='원문 표의 실제 기간을 사용합니다. 내부 공시 버전 순서는 재무제표 이사회 승인일 기준이며 SEC 제출일을 뜻하지 않습니다. 연간−9개월 차분은 동일 연도의 같은 기준 항목으로 계산합니다.'))
            docs[id]=doc
    save(HISTORY,state)
    for id,doc in docs.items():save(OUT/(id+'.json'),doc)
    return docs

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--offline',action='store_true')
    collect(parser.parse_args().offline)

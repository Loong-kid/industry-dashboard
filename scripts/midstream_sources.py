"""Reviewed issuer definitions and parsers for gas infrastructure accounts/HP."""
import calendar
import datetime as dt
import re

from bs4 import BeautifulSoup

SPECS={
 'kmi':dict(name='Kinder Morgan · KMI',cik=1506307,fiscal_start=1,scope='천연가스 수송·저장, 제품 파이프라인·터미널·CO₂ 등을 포함한 연결 전체',tags={'revenue':['Revenues']}),
 'wmb':dict(name='Williams · WMB',cik=107263,fiscal_start=1,scope='Transco 등 천연가스 수송·저장·집하·처리·마케팅을 포함한 연결 전체',tags={'revenue':['Revenues']}),
 'et':dict(name='Energy Transfer · ET',cik=1276187,fiscal_start=1,scope='천연가스·NGL·원유·제품·소매 등 연결 전체. USAC를 연결하므로 두 회사 실적을 합산하지 않습니다',tags={'revenue':['Revenues'],'capex':['PaymentsToAcquireProductiveAssets']}),
 'epd':dict(name='Enterprise Products · EPD',cik=1061219,fiscal_start=1,scope='천연가스·NGL·원유·석유화학 파이프라인, 처리·분별·수출 등을 포함한 연결 전체',tags={'revenue':['Revenues','SalesRevenueNet'],'capex':['PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets']}),
 'trgp':dict(name='Targa Resources · TRGP',cik=1389170,fiscal_start=1,scope='천연가스 집하·처리와 NGL 분별·물류·수출 등을 포함한 연결 전체',tags={'revenue':['Revenues','GasGatheringTransportationMarketingAndProcessingRevenue']}),
 'aroc':dict(name='Archrock · AROC',cik=1389050,fiscal_start=1,scope='미국 압축기 계약 운영·애프터마켓 연결 전체. 2015년 Exterran 분할 전후 및 인수에 따른 범위 변경에 주의',tags={'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet'],'capex':['PaymentsToAcquireProductiveAssets']},profit_label='계산 영업손익'),
 'kgs':dict(name='Kodiak Gas Services · KGS',cik=1767042,fiscal_start=1,scope='압축기 계약 서비스·기타 서비스 등 연결 전체. 2026년부터 전력 인프라도 포함. 2023년 상장 전 공개 이력은 제한적',tags={'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax']}),
 'usac':dict(name='USA Compression · USAC',cik=1522727,fiscal_start=1,scope='압축기 계약 서비스 등 연결 전체. 2018년 CDM·2026년 J-W 인수로 자산·마력 범위가 확대됨',tags={'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet']}),
}

HP_NOTES={
 'aroc':'Total available HP는 기말 가용 마력, Total operating HP는 기말 고객 현장에서 가동 중인 마력입니다. 원문 단위가 thousand HP이므로 그대로 표시합니다. 분할 이전 국제 사업 총량·Exterran Partners 별도 수치를 혼합하거나 합산하지 않습니다.',
 'kgs':'가용 마력은 Fleet horsepower(2026 Q2부터 Compression Infrastructure의 Fleet capacity), 대응 지표는 Revenue-generating horsepower입니다. 2024 Q1·Q3 등 일부 공시는 계약·확약 후 배치 가능한 장비도 수익 발생 마력에 포함하므로 실제 가동 마력과 완전히 같지 않습니다. 공시별 정의 차이, 비시장성·노후 마력 제외와 CSI 인수를 고려하세요. 2026 Q2 전력 사업 MW는 HP에 합산하지 않습니다. 미공시 가용 HP는 가동률로 역산하지 않습니다.',
 'usac':'Total available HP에는 현 보유 장비 외 계약된 주문·미인도 장비가 포함될 수 있습니다. 대응 지표는 기말 Revenue-generating HP입니다. 회사의 공표 가동률은 계약 대기·수리 중 장비를 조정하므로 단순 revenue-generating HP / total available HP와 다릅니다. 회사 공표 가동률을 별도 시리즈로 표시합니다.',
}

def clean(text):
    return re.sub(r'\s+',' ',text.replace('\u200b','').replace('\xa0',' ')).strip()

def row_values(tr):
    cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
    first=next((i for i,c in enumerate(cells) if c and not re.fullmatch(r'[$%()\d, .—–−-]+',c)),None)
    if first is None:return '',[]
    label=cells[first];values=[]
    # Parentheses and currency symbols are often separate cells in SEC HTML.
    tail=' '.join(cells[first+1:])
    for match in re.finditer(r'(?<![\w.])(?:\(\s*)?[-−]?\d[\d,]*(?:\.\d+)?(?:\s*\))?|[—–]',tail):
        token=match[0].strip()
        if token in ['—','–']:values.append(0.0);continue
        value=float(re.sub(r'[,()\s]','',token).replace('−','-'))
        values.append(-value if token.startswith('(') else value)
    return label,values

def table_rows(table):
    return [row_values(tr) for tr in table.find_all('tr') if tr.find_parent('table') is table]

def quarter_date(year,q):
    month=q*3
    return f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]}'

def hp_dates(header,meta):
    months='January|February|March|April|May|June|July|August|September|October|November|December'
    exact=re.findall(rf'({months})\s+(\d{{1,2}}),?\s+(20\d{{2}})',header,re.I)
    if len(exact)>1:
        return [dt.datetime.strptime(f'{m} {day} {year}','%B %d %Y').date().isoformat() for m,day,year in exact]
    day=re.search(rf'({months})\s+(\d{{1,2}})',header,re.I)
    if not day:return []
    years=re.findall(r'\b20\d{2}\b',header)
    groups=re.findall(rf'({months})\s+(\d{{1,2}})',header,re.I)
    if len(groups)>1 and len(years)%len(groups)==0:
        slots=[group for group in groups for _ in range(len(years)//len(groups))]
    else:slots=[(day[1],day[2])]*len(years)
    return [f'{year}-{dt.datetime.strptime(month,"%B").month:02d}-{int(day):02d}' for year,(month,day) in zip(years,slots)]

def ipo_revenue_rows(soup,meta):
    rows=[]
    for table in soup.find_all('table'):
        text=clean(table.get_text(' ',strip=True))
        m=re.match(r'(202[12])\b',text)
        if not m or not all(word in text for word in ['First Quarter','Fourth Quarter','Total revenues']):continue
        values=next((vs for label,vs in table_rows(table) if label=='Total revenues'),[])
        if len(values)!=4:continue
        for q,value in enumerate(values,1):
            end=quarter_date(int(m[1]),q);start=f'{m[1]}-{(q-1)*3+1:02d}-01'
            ref=dict(url=meta['url'],filed=meta['filed'],start=start,end=end,tag='IPO:TotalRevenues',form=meta['form'])
            rows.append(dict(date=end,start=start,year=int(m[1]),quarter=q,revenue=value/1000,refs={'revenue':dict(ref,components=[ref],calculation='reported quarter in IPO prospectus')}))
    return rows

def horsepower_tables(soup,key,meta):
    """Use dated operating-data tables; never infer capacity from rounded rates."""
    output=[]
    for table in soup.find_all('table'):
        text=clean(table.get_text(' ',strip=True))
        if len(text)>12000:continue
        rows=table_rows(table)
        available=next(((label,vs) for label,vs in rows if re.match(r'Total available horsepower',label,re.I)),None)
        if not available:available=next(((label,vs) for label,vs in rows if re.match(r'Fleet horsepower|Fleet capacity',label,re.I)),None)
        operating=next(((label,vs) for label,vs in rows if re.match(r'Total operating horsepower|Revenue[- ]generating horsepower(?:\s*\(|\s*$)|Revenue-generating \(hp',label,re.I)),None)
        if not available or not operating or not available[1] or not operating[1]:continue
        header=text.split(available[0])[0]
        dates=hp_dates(header,meta)
        if not dates:continue
        count=min(len(dates),len(available[1]),len(operating[1]))
        # Current and previous year are the first two numeric columns; later
        # change percentages/repeated YTDs never become additional observations.
        for i in range(count):
            d=dates[i]
            if d<'2014-01-01':continue
            a,o=available[1][i],operating[1][i]
            if key=='aroc':
                if not 1000<a<15000 or not 500<o<=a:continue
            else:
                if not 100000<a<15000000 or not 100000<o<=a:continue
                a/=1000;o/=1000
            util=None
            if key=='aroc':
                util=next((vs[i] for label,vs in rows if re.match(r'Spot\s*\(at period end\)|Horsepower Utilization \(at period end\)',label,re.I) and len(vs)>i),None)
            elif key=='kgs':
                util=next((vs[i] for label,vs in rows if re.match(r'(?:Fleet|Horsepower) utilization',label,re.I) and len(vs)>i),None)
            else:
                util=next((vs[i] for label,vs in rows if re.match(r'At period end',label,re.I) and len(vs)>i),None)
            # USAC's fleet HP excludes contracted on-order machines; it must
            # never silently stand in for Total available HP.
            actual_available=not (key=='usac' and not available[0].lower().startswith('total available'))
            output.append(dict(date=d,**({'available':a} if actual_available else {}),operating=o,**({'utilization':util} if util is not None and 0<util<=100 else {}),
                               ref=dict(url=meta['url'],filed=meta['filed'],form=meta['form'],location=available[0]+' / '+operating[0],calculation='reported period-end horsepower; '+('thousand HP as reported' if key=='aroc' else 'HP divided by 1,000'))))
    # The IPO prospectus supplies eight genuine pre-IPO quarters of active HP;
    # their available HP is not disclosed in this table and remains absent.
    if key=='kgs' and meta['form'].startswith('S-1'):
        for table in soup.find_all('table'):
            text=clean(table.get_text(' ',strip=True))
            if not all(word in text for word in ['First Quarter','Fourth Quarter','Revenue-generating horsepower']):continue
            m=re.match(r'(202[12])\b',text)
            if not m:continue
            row=next((vs for label,vs in table_rows(table) if label=='Revenue-generating horsepower'),[])
            if len(row)!=4:continue
            for q,value in enumerate(row,1):
                output.append(dict(date=quarter_date(int(m[1]),q),operating=value/1000,ref=dict(url=meta['url'],filed=meta['filed'],form=meta['form'],location=f'{m[1]} quarterly operating data Q{q}',calculation='reported HP / 1,000; available HP not disclosed')))
    return output

def archrock_operating_facts(soup,meta,payload):
    """A disclosed statement has no operating subtotal. Calculate and label it.

    Revenue less the explicitly named operating costs, including restructuring,
    impairment and transaction costs. Asset-sale/other/financing gains excluded.
    """
    output=[]
    for table in soup.find_all('table'):
        text=clean(table.get_text(' ',strip=True))
        if len(text)>17000 or 'Selling, general and administrative' not in text or not re.search(r'Income.*before income taxes',text,re.I) or 'Weighted' not in text:continue
        rows=table_rows(table)
        sga=next((vs for label,vs in rows if label.lower().startswith('selling, general and administrative')),None)
        if not sga:continue
        header=text.split(next(label for label,vs in rows if label.lower().startswith('selling, general')))[0]
        # Periods derive from the fiscal statement header, not the filing FY tag.
        yearseq=[]
        for label,values in rows:
            if values:break
        year_match=re.search(r'\b(20\d{2})\b',header)
        if not year_match:continue
        year=int(year_match[1]);date=meta.get('date','')
        if not date or int(date[:4])!=year:continue
        q=(int(date[5:7])-1)//3+1
        if meta['form'].startswith('10-K'):
            periods=[(f'{year-i}-01-01',f'{year-i}-12-31') for i in range(min(len(sga),3))]
        else:
            startmonth=(q-1)*3+1
            periods=[(f'{year}-'+f'{startmonth:02d}-01',date),(f'{year-1}-'+f'{startmonth:02d}-01',f'{year-1}'+date[4:])]
            if q>1:periods += [(f'{year}-01-01',date),(f'{year-1}-01-01',f'{year-1}'+date[4:])]
        costpatterns=[r'^Total cost of sales',r'^Selling, general and administrative',r'^Depreciation and amortization',r'^Long-lived.*impairment',r'^Goodwill impairment',r'^Restructuring',r'^Restatement',r'^(?:Merger|Transaction)-related costs']
        costs=[(label,vs) for label,vs in rows if any(re.match(pattern,label,re.I) for pattern in costpatterns)]
        if not any(re.match(r'^Total cost of sales',label,re.I) for label,vs in costs):
            # Older statements show cost-of-sales segment rows without a total.
            active=False
            for label,vs in rows:
                if label.lower().startswith('cost of sales'):active=True;continue
                if active and label.lower().startswith('selling,'):break
                if active and vs and label.lower().startswith(('contract operations','aftermarket services','fabrication','international')):costs.append((label,vs))
        if not any('cost of sales' in label.lower() or label.lower().startswith(('contract operations','aftermarket services')) for label,vs in costs):continue
        for i,(start,end) in enumerate(periods):
            if end<'2014-01-01' or any(len(vs)<=i for label,vs in costs):continue
            revenuefacts=[]
            for tag in ['RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet']:
                revenuefacts += [f for f in payload['facts']['us-gaap'].get(tag,{}).get('units',{}).get('USD',[]) if f.get('start')==start and f['end']==end and f['accn'] in meta['url'].replace('-','')]
            # URL includes hyphenless accession, the fact accession is hyphenated.
            if not revenuefacts:
                for tag in ['RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet']:
                    revenuefacts += [f for f in payload['facts']['us-gaap'].get(tag,{}).get('units',{}).get('USD',[]) if f.get('start')==start and f['end']==end and f['filed']==meta['filed']]
            if not revenuefacts:continue
            rev=revenuefacts[0];value=rev['val']-sum(vs[i]*1000 for label,vs in costs)
            output.append(dict(start=start,end=end,val=value,form=meta['form'],filed=meta['filed'],accn=rev['accn'],source_url=meta['url'],source_tag='calculated:RevenueLessOperatingCosts',derivation='Revenue less COGS, SG&A, depreciation, impairment, restructuring, restatement and transaction costs; excludes asset-sale/other/financing gains',inputs=dict(revenue=rev['val'],costs={label:vs[i]*1000 for label,vs in costs})))
        break
    return output

"""Issuer currency and reported durations; no annual/quarter interpolation."""
import copy
import datetime as dt
import json
import re
from pathlib import Path

import pymupdf
from fetch_cpu_companies import days, parse_annual, parse_facts, reference
from oil_sources import financial_soup, html_row, norm, pdf_row, pdf_lines, NUMBER, number

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/mining'
METRICS=('revenue','profit','capex')
TAGS={
 'bhp':{'revenue':['ifrs-full:Revenue'],'profit':['ifrs-full:ProfitLossFromOperatingActivities'],'capex':['ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities']},
 'rio':{'revenue':['ifrs-full:Revenue'],'profit':['ifrs-full:ProfitLossFromOperatingActivities'],'capex':['ifrs-full:PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets']},
 'scco':{'revenue':['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax','us-gaap:SalesRevenueNet','us-gaap:Revenues'],'profit':['us-gaap:OperatingIncomeLoss'],'capex':['us-gaap:PaymentsToAcquirePropertyPlantAndEquipment']},
 'fcx':{'revenue':['us-gaap:Revenues','us-gaap:SalesRevenueNet'],'profit':['us-gaap:OperatingIncomeLoss'],'capex':['us-gaap:PaymentsToAcquireProductiveAssets']},
 'nem':{'revenue':['us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax','us-gaap:SalesRevenueNet','us-gaap:Revenues'],'profit':[],'capex':['us-gaap:PaymentsToAcquireProductiveAssets','us-gaap:PaymentsToAcquirePropertyPlantAndEquipment']},
 'aem':{'revenue':['ifrs-full:Revenue','us-gaap:SalesRevenueNet'],'profit':[],'capex':['ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities','us-gaap:PaymentsToAcquirePropertyPlantAndEquipment']},
 'barrick':{'revenue':['ifrs-full:Revenue','us-gaap:SalesRevenueNet'],'profit':[],'capex':['ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities','us-gaap:PaymentsToAcquirePropertyPlantAndEquipment']},
 'ero':{'revenue':['ifrs-full:RevenueFromContractsWithCustomers'],'profit':['ifrs-full:ProfitLossFromOperatingActivities'],'capex':['ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities']},
}


def normalize_facts(payload,key,asof):
    output={m:[] for m in METRICS}
    def get(tag):
        ns,name=tag.split(':',1)
        return [dict(f,source_tag=tag,form='20-F' if f.get('form','').startswith('40-F') else f.get('form')) for f in payload['facts'].get(ns,{}).get(name,{}).get('units',{}).get('USD',[]) if f.get('start') and f['end']<=asof and f['filed']<=asof]
    for metric,tags in TAGS[key].items():
        # Preserve tag priority in the canonical name instead of allowing a
        # revenue component to supersede the company's total sales.
        occupied=set()
        for tag in tags:
            rows=get(tag);periods={(f['start'],f['end']) for f in rows}
            output[metric].extend(f for f in rows if (f['start'],f['end']) not in occupied)
            occupied.update(periods)
    if key in ['nem','aem','barrick']:
        first=output['revenue'] if key=='nem' else get('ifrs-full:ProfitLossBeforeTax')
        second=get('us-gaap:CostsAndExpenses') if key=='nem' else get('ifrs-full:FinanceCosts') if key=='aem' else get('ifrs-full:FinanceIncomeCost')
        index={(f['start'],f['end'],f['filed'],f['accn']):f for f in second}
        for f in first:
            other=index.get((f['start'],f['end'],f['filed'],f['accn']))
            if not other:continue
            value=f['val']-other['val'] if key in ['nem','barrick'] else f['val']+other['val']
            output['profit'].append(dict(f,val=value,source_tag='derived: '+('sales minus consolidated operating costs' if key=='nem' else 'profit before tax plus net finance cost' if key=='barrick' else 'profit before tax plus finance costs'),derivation='Calculation from the named consolidated statement rows; not adjusted EBITDA.',inputs=[f,other]))
    return output


def sec_periods(payload,key,spec,asof):
    fields=normalize_facts(payload,key,asof)
    # Explicitly reviewed legacy annual statement rows and Ero interim files.
    for accn,meta in json.loads((CACHE/f'{key}-filings.json').read_bytes()).items():
        if meta['filed']>asof or not meta.get('date'):continue
        legacy=meta['date'][:4] in ['2014','2015']
        missing=any(not any(f['end']==meta['date'] and 350<=days(f['start'],f['end'])<=380 for f in fields[m]) for m in METRICS)
        if not legacy and not missing and not (key=='ero' and meta['form']=='6-K'):continue
        for metric,items in html_statement_fields((CACHE/meta['path']).read_bytes(),key,meta).items():
            fields[metric].extend(dict(f,accn=accn.split('-'+key)[0],filed=meta['filed'],form='6-K' if meta['form']=='6-K' else '20-F',source_url=meta['url']) for f in items)
    tags={m:['MiningReviewed'+m.title()] for m in METRICS}
    canonical=dict(cik=spec['cik'],facts={'us-gaap':{tags[m][0]:dict(units={'USD':items}) for m,items in fields.items()}})
    annual=parse_annual(canonical,spec,asof,tags)
    quarters=[];halves=[]
    if key in ['scco','fcx','nem','ero','barrick']:
        try:quarters=parse_facts(canonical,spec,asof,tags)
        except ValueError:pass
    if key in ['bhp','rio']:
        years={a['year']:a for a in annual}
        for items in fields.values():
            for f in items:
                if 160<=days(f['start'],f['end'])<=200 and f['start'][5:] in ['01-01','07-01']:
                    year=int(f['end'][:4])+(spec['fiscal_start']==7 and f['end'][5:]=='12-31')
                    years.setdefault(year,dict(year=year,date=f'{year}-'+('06-30' if spec['fiscal_start']==7 else '12-31'),refs={}))
        for a in years.values():
            year=a['year'];start=f'{year-1 if spec["fiscal_start"]==7 else year}-{spec["fiscal_start"]:02d}-01'
            h1end=(dt.date(int(start[:4]),int(start[5:7]),1)+dt.timedelta(days=183)).replace(day=1)-dt.timedelta(days=1)
            # Calendar half ends are unambiguous for these two issuers.
            h1end=f'{year-1}-12-31' if spec['fiscal_start']==7 else f'{year}-06-30'
            h1=dict(date=h1end,year=year,half=1,refs={})
            h2=dict(date=a['date'],year=year,half=2,refs={})
            for metric,items in fields.items():
                candidates=[f for f in items if f['start']==start and f['end']==h1end and 160<=days(f['start'],f['end'])<=200]
                if not candidates:continue
                f=max(candidates,key=lambda f:(f['filed'],f['accn']));rf=reference(dict(f,tag=f['source_tag']),spec['cik'])
                h1[metric]=f['val']/1e6;h1['refs'][metric]=dict(rf,components=[rf],calculation='reported half year')
                if metric in a:
                    value=a[metric]-h1[metric]
                    if metric!='profit' and value<0:continue
                    h2[metric]=value;h2['refs'][metric]=dict(a['refs'][metric],components=[a['refs'][metric]['components'][0],rf],calculation='reported full year minus reported first half')
            if h1['refs']:halves.append(h1)
            if h2['refs']:halves.append(h2)
    return dict(annual=annual,rows=quarters,halves=sorted(halves,key=lambda r:r['date']))


def html_statement_fields(raw,key,meta):
    soup=financial_soup(raw);income=None;cash=None
    for table in soup.find_all('table'):
        text=norm(table.get_text(' ',strip=True))
        if len(text)>27000 or re.search(r'Consolidating Adjustments|variance|20\d{2}\s+vs',text,re.I):continue
        if income is None and re.search(r'(?:revenue|sales)',text,re.I) and re.search(r'(?:before.*tax|income from operations|operating profit)',text,re.I) and re.search(r'per share|earnings per',text,re.I):income=table
        if cash is None and re.search(r'(?:cash.*operating activities|operating activities.*cash)',text,re.I) and re.search(r'financing activities',text,re.I) and re.search(r'propert(?:y|ies).*(?:equipment|plant)|capital expenditures',text,re.I):cash=table
    if key=='bhp':
        for heading in soup.find_all(string=re.compile(r'Consolidated Income Statement',re.I)):
            label=norm(str(heading))
            if 'for the year' not in label.lower() and label.lower()!='consolidated income statement':continue
            candidate=heading.parent.find_next('table')
            if candidate is None:continue
            text=norm(candidate.get_text(' ',strip=True))
            if 'Net finance costs' in text and 'Income tax' in text:income=candidate
    patterns={
      'revenue':r'^(?:Consolidated sales revenue|Revenue(?:s)?(?: from mining operations)?|Sales(?: revenue)?)(?: \(Note \d+\))?\b',
      'profit':r'^(?:Profit(?:/\(loss\)| \(loss\))? from operations|Income(?: \(loss\))? from operations|Income(?: \(loss\))? before the undernoted|Operating (?:income|profit|loss)|Profit before financing and (?:income )?tax)\b',
      'pbt':r'^(?:Income|Profit)(?: \(loss\)|/\(loss\))? before income(?: and mining)? tax',
      'finance':r'^(?:Finance costs|Financial expenses|Net finance (?:costs|expense))\b',
      'capex':r'^(?:Purchase(?:s)? of property,? plant and equipment|Purchase(?:s)? of property, plant,? equipment|Additions to (?:mineral propert(?:y|ies),? )?plant,? and equipment|Capital expenditures|Acquisition of property, plant and equipment)\b',
    }
    year=int(meta['date'][:4]);q=(int(meta['date'][5:7])-1)//3+1;annual=meta['form'] not in ['6-K','10-Q','10-Q/A']
    count=2 if key in ['aem','ero'] else 3
    fields={}
    for field,pattern in patterns.items():
        table=cash if field=='capex' else income
        if table is None:continue
        expected=count if annual else 2 if field=='capex' or q==1 else 4
        inline,values=html_row(soup,pattern,expected,table)
        if inline:fields[field]=inline;continue
        if values is None:continue
        if annual:
            endmonth='06-30' if key=='bhp' else '12-31'
            periods=[(f'{year-i-1}-07-01' if key=='bhp' else f'{year-i}-01-01',f'{year-i}-{endmonth}') for i in range(count)]
        else:
            periods=[(f'{year}-{(q-1)*3+1:02d}-01',meta['date']),(f'{year-1}-{(q-1)*3+1:02d}-01',meta['date'].replace(str(year),str(year-1),1))]
            if field=='capex':periods=[(f'{year}-01-01',meta['date']),(f'{year-1}-01-01',meta['date'].replace(str(year),str(year-1),1))]
            elif q>1:periods += [(f'{year}-01-01',meta['date']),(f'{year-1}-01-01',meta['date'].replace(str(year),str(year-1),1))]
        scale=1e3 if key in ['aem','ero'] else 1e6
        fields[field]=[dict(start=s,end=e,val=(abs(v) if field in ['capex','finance'] else v)*scale,source_tag='original statement: '+field) for (s,e),v in zip(periods,values)]
    if key in ['aem','barrick'] and 'pbt' in fields and 'finance' in fields:
        finance={(f['start'],f['end']):f for f in fields['finance']}
        fields['profit']=[dict(f,val=f['val']+abs(finance[f['start'],f['end']]['val']),source_tag='original statement: profit before tax plus net finance expense',derivation='Profit before tax plus disclosed finance expense',inputs=[f,finance[f['start'],f['end']]]) for f in fields['pbt'] if (f['start'],f['end']) in finance]
    if key=='fcx' and 'capex' not in fields and cash is not None:
        # FCX's 2026 cash-flow statement splits PP&E cash payments into five
        # operations, with no total XBRL fact. Sum that original cash-flow block.
        inside=False;parts=[]
        for row in cash.find_all('tr'):
            text=norm(row.get_text(' ',strip=True))
            if not text:continue
            if re.match(r'^Capital expenditures\s*:',text,re.I):inside=True;continue
            if not inside:continue
            if not re.match(r'^(?:U\.S\. copper mines|South America operations|Indonesia operations|Molybdenum mines|Other\s+\()',text,re.I):break
            values=[number(t) for t in NUMBER.findall(text)]
            if len(values)>=2:parts.append(values[-2:])
        if len(parts)==5:
            periods=[(f'{year}-01-01',meta['date']),(f'{year-1}-01-01',meta['date'].replace(str(year),str(year-1),1))]
            fields['capex']=[dict(start=s,end=e,val=sum(abs(part[i]) for part in parts)*1e6,source_tag='cash flow: sum five disclosed PP&E cash payments (US copper, South America, Indonesia, molybdenum, other)') for i,(s,e) in enumerate(periods)]
    return {m:fields.get(m,[]) for m in METRICS}


def glencore_annual(path,meta):
    doc=pymupdf.open(path);income=None;cash=None
    for page in doc:
        t=page.get_text();text=' '.join(t.split()).lower()
        if income is None and re.search(r'consolidated statement of (?:income|loss|\(loss\))',text) and re.search(r'^Revenue\s*$',t,re.M) and 'Cost of goods sold' in t:income=page
        if cash is None and 'consolidated statement of cash flows' in text and 'Purchase of property' in t:cash=page
    if income is None or cash is None:raise ValueError('Glencore original statement layout changed')
    fields={}
    for field,pattern,page in [('revenue',r'^Revenue\b',income),('pbt',r'^(?:Income|Profit|Loss|\(Loss\))(?:/\(?(?:income|loss)\)?| \(loss\))? before income tax',income),('interest_expense',r'^Interest expense\b',income),('interest_income',r'^Interest income\b',income),('capex',r'^Purchase of property, plant and equipment',cash)]:
        values=pdf_row(page,pattern)
        if not values or len(values)<2:raise ValueError('Glencore statement row unavailable: '+field)
        fields[field]=values[-2:]
    rows=[]
    for i in range(2):
        year=meta['year']-i
        if year<2014:continue
        is_half=meta.get('kind')=='half'
        r=dict(date=f'{year}-'+('06-30' if is_half else '12-31'),year=year,revenue=fields['revenue'][i],profit=fields['pbt'][i]+abs(fields['interest_expense'][i])-fields['interest_income'][i],capex=abs(fields['capex'][i]),refs={})
        if is_half:r['half']=1
        for metric in METRICS:
            rf=dict(url=meta['url'],filed=meta['filed'],start=f'{year}-01-01',end=r['date'],tag='Glencore consolidated statement '+metric,pdf_page=(cash.number if metric=='capex' else income.number)+1)
            r['refs'][metric]=dict(rf,components=[rf],calculation='PBT + interest expense - interest income' if metric=='profit' else 'reported half year' if is_half else 'reported annual')
        rows.append(r)
    return rows


def wrapped_pdf_values(page,pattern,count,xmin=.48):
    lines=pdf_lines(page)
    for i,words in enumerate(lines):
        text=norm(' '.join(w[4] for w in words))
        if not re.search(pattern,text,re.I):continue
        for line in lines[i:i+4]:
            right=' '.join(w[4] for w in line if w[0]>=page.rect.width*xmin)
            values=[]
            for token in NUMBER.findall(right):
                try:values.append(number(token))
                except ValueError:pass
            if len(values)>=count:return values[-count:]
    return None


def zijin_annual(path,meta):
    doc=pymupdf.open(path);income=None;cash=None
    for page in doc:
        t=page.get_text();text=' '.join(t.split()).lower()
        if 'consolidated statement of profit' in text and 'operating income' in text and 'operating profit' in text:income=page
        if 'consolidated statement of cash flows' in text and re.search(r'purchase or construction|acquisition.*fixed|(?:cash paid|cash payments) to acquire',text):cash=page
        if income is not None and cash is not None:break
    if income is None or cash is None:raise ValueError('Zijin consolidated statements unavailable')
    values={}
    for field,pattern,page in [('revenue',r'^(?:I\.?\s*)?(?:TOTAL )?OPERATING INCOME\b',income),('profit',r'^(?:III\.?\s*)?OPERATING PROFIT\b',income),('capex',r'^Cash (?:payments for (?:purchase or construction|acquisitions? or constructions?)|payments to acquire or construct|paid for (?:purchase|construction)|paid to acquire)',cash)]:
        vv=wrapped_pdf_values(page,pattern,2)
        if vv is None:raise ValueError('Zijin row unavailable: '+field)
        values[field]=[abs(v) if field=='capex' else v for v in vv]
    output=[]
    for i in range(2):
        y=meta['year']-i
        if y<2014:continue
        r=dict(date=f'{y}-12-31',year=y,refs={})
        for metric in METRICS:
            r[metric]=values[metric][i]/1e6
            f=dict(url=meta['url'],filed=meta['filed'],start=f'{y}-01-01',end=r['date'],tag='Zijin CAS consolidated '+metric,pdf_page=(cash.number if metric=='capex' else income.number)+1)
            r['refs'][metric]=dict(f,components=[f],calculation='reported consolidated annual; CNY')
        output.append(r)
    return output


def grupo_annual(path,meta):
    doc=pymupdf.open(path);income=None;cash=None
    for page in doc:
        t=page.get_text();text=' '.join(t.split()).lower()
        if 'estados consolidados de resultados' in text and 'ventas netas' in text and 'gastos de administraci' in text:income=page
        if 'estados consolidados de flujos de efectivo' in text and re.search(r'adquisici.n de (?:propiedades|inmuebles)',text):cash=page
        if income is not None and cash is not None:break
    if income is None or cash is None:raise ValueError('Grupo Mexico audited consolidated statements unavailable')
    values={}
    for field,pattern,page in [('goods',r'^Ventas netas\b',income),('services',r'^Ingresos por servicios\b',income),('gross',r'^Utilidad bruta\b',income),('admin',r'^Gastos de administraci',income),('capex',r'^Adquisici.n de (?:propiedades|inmuebles)',cash)]:
        vv=wrapped_pdf_values(page,pattern,3)
        if vv is None:raise ValueError('Grupo Mexico statement row unavailable: '+field)
        values[field]=vv
    output=[]
    for i in range(3):
        y=meta['year']-i
        if y<2014:continue
        r=dict(date=f'{y}-12-31',year=y,revenue=(values['goods'][i]+values['services'][i])/1e3,profit=(values['gross'][i]-values['admin'][i])/1e3,capex=abs(values['capex'][i])/1e3,refs={})
        for metric in METRICS:
            f=dict(url=meta['url'],filed=meta['filed'],start=f'{y}-01-01',end=r['date'],tag='Grupo Mexico audited consolidated USD thousands '+metric,pdf_page=(cash.number if metric=='capex' else income.number)+1)
            r['refs'][metric]=dict(f,components=[f],calculation='gross profit minus administration expenses; other/financial/FX/equity-method results excluded' if metric=='profit' else 'net goods sales plus service revenues' if metric=='revenue' else 'cash purchases of property plant equipment')
        output.append(r)
    return output

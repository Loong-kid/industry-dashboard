"""Original financial-statement rows. Never use an ambiguous revenue subtotal."""
import datetime as dt
import re
from bs4 import BeautifulSoup

NUMBER=re.compile(r'(?<![A-Za-z0-9])\(?\s*-?\d[\d,]*(?:\.\d+)?\s*\)?|[—–−]')

def number(text):
    text=re.sub(r'\s','',text).replace(',','')
    if text in ['—','–','−','-']:return 0.
    return -float(text[1:-1]) if text.startswith('(') and text.endswith(')') else float(text)

def norm(text):return re.sub(r'\s+',' ',text.replace('\xa0',' ').replace('\u200b','')).strip()

def financial_soup(content):
    soup=BeautifulSoup(content,'lxml')
    if soup.find('table'):return soup
    # Some ConocoPhillips filings use absolutely positioned XHTML rather than
    # tables. Reconstruct rows from the original coordinates, retaining iXBRL.
    for page in list(soup.find_all('div',id=re.compile(r'^Page\d+$'))):
        cells=[]
        for cell in page.find_all('div',recursive=False):
            style=cell.get('style','');top=re.search(r'top:\s*([\d.]+)px',style);left=re.search(r'left:\s*([\d.]+)px',style)
            if top and left and cell.get_text(strip=True):cells.append((float(top[1]),float(left[1]),cell))
        rows=[]
        for y,x,cell in sorted(cells,key=lambda c:c[:2]):
            if not rows or abs(y-rows[-1][0])>3:rows.append((y,[]))
            rows[-1][1].append((x,cell))
        table=soup.new_tag('table')
        for _,row in rows:
            tr=soup.new_tag('tr')
            for _,cell in sorted(row,key=lambda c:c[0]):
                td=soup.new_tag('td');td.append(cell.extract());tr.append(td)
            table.append(tr)
        page.append(table)
    return soup

def quarter_end(year,q):
    month=q*3
    return (dt.date(year+(month==12),month%12+1,1)-dt.timedelta(days=1)).isoformat()

def html_row(soup,pattern,expected=None,table=None):
    """Choose a statement row, preserving non-dimensional inline contexts."""
    contexts=getattr(soup,'_oil_contexts',None)
    if contexts is None:
        contexts={}
        for context in soup.find_all(lambda x:x.name.lower().endswith(':context')):
            if context.find(lambda x:x.name.lower().endswith((':explicitmember',':typedmember'))):continue
            start=context.find(lambda x:x.name.lower().endswith(':startdate'))
            end=context.find(lambda x:x.name.lower().endswith(':enddate'))
            if start and end:contexts[context.get('id')]=(start.get_text(),end.get_text())
        soup._oil_contexts=contexts
    for row in (table or soup).find_all('tr'):
        txt=norm(row.get_text(' ',strip=True))
        match=re.match(pattern,txt,re.I)
        if not match or len(txt)>1700:continue
        inline=[]
        for el in row.find_all(lambda x:x.name.lower()=='ix:nonfraction'):
            context=contexts.get(el.get('contextref'))
            if not context:continue
            try:value=number(el.get_text())*10**int(el.get('scale',0))
            except ValueError:continue
            if el.get('sign')=='-':value=-value
            inline.append(dict(start=context[0],end=context[1],val=value,source_tag=el.get('name'),location=txt[:100]))
        if inline:return inline,None
        tokens=NUMBER.findall(txt[match.end():]);values=[]
        for token in tokens:
            try:values.append(number(token))
            except ValueError:pass
        if expected and len(values)>=expected:return [],values[-expected:]
    return [],None

US_PATTERNS={
 'revenue':r'^Sales and other operating revenues?\b',
 'cost':r'^Total costs and (?:other deductions|expenses)\b',
 'interest':r'^Interest (?:and debt )?expense\b',
 'xom_capex':r'^Additions to property, plant,? and equipment',
 'cvx_capex':r'^Capital expenditures\b',
 'cop_capex':r'^Capital expenditures and investments\b',
}

def statement_facts(content,meta,key):
    """US main statement rows; total sales and total income can share XBRL tags."""
    soup=financial_soup(content);year=int(meta['date'][:4]);q=(int(meta['date'][5:7])-1)//3+1
    annual=meta['form'].startswith(('10-K','20-F'))
    count=3 if annual else 2 if q==1 else 4
    income=None
    for table in soup.find_all('table'):
        txt=norm(table.get_text(' ',strip=True))
        if len(txt)<26000 and re.search(r'Sales and other operating revenues?',txt,re.I) and re.search(r'Total costs and (other deductions|expenses)',txt,re.I) and re.search(r'(?:income|operations).*before income tax',txt,re.I):
            heading=txt[:re.search(r'Sales and other operating revenues?',txt,re.I).start()]
            if annual and re.search(r'(?:[1-4](?:st|nd|rd|th) Q\b|Quarterly)',heading,re.I):continue
            income=table;break
    if income is None:return []
    # A classic quarterly statement places the three months before YTD.
    txt=norm(income.get_text(' ',strip=True))
    if not annual and q>1 and not re.search(r'three months.*(?:six|nine) months',txt,re.I):return []
    cash=None
    for table in soup.find_all('table'):
        text=norm(table.get_text(' ',strip=True))
        if len(text)<35000 and re.search(r'(?:net cash|cash flows?).*operating activities',text,re.I) and re.search(r'cash.*financing activities',text,re.I) and re.search(US_PATTERNS[key+'_capex'].lstrip('^'),text,re.I):
            cash=table;break
    fields={}
    for field,pattern in US_PATTERNS.items():
        if field.endswith('_capex') and field!=key+'_capex':continue
        if field.endswith('_capex') and cash is None:continue
        inline,values=html_row(soup,pattern,2 if field.endswith('_capex') and not annual else count, income if field in ['revenue','cost','interest'] else cash)
        if inline:fields[field]=inline
        elif values is not None:
            if field.endswith('_capex') and not annual:
                # Cash flow is YTD only; re-read its two columns.
                _,values=html_row(soup,pattern,2,cash)
                periods=[(f'{year}-01-01',meta['date']),(f'{year-1}-01-01',meta['date'].replace(str(year),str(year-1),1))]
            elif annual:periods=[(f'{year-i}-01-01',f'{year-i}-12-31') for i in range(3)]
            else:
                periods=[(f'{year}-{(q-1)*3+1:02d}-01',meta['date']),(f'{year-1}-{(q-1)*3+1:02d}-01',quarter_end(year-1,q))]
                if q>1:periods += [(f'{year}-01-01',meta['date']),(f'{year-1}-01-01',quarter_end(year-1,q))]
            fields[field]=[dict(start=start,end=end,val=abs(val)*1e6 if field.endswith('_capex') else val*1e6,source_tag='original statement row: '+pattern,location=pattern) for (start,end),val in zip(periods,values)]
    result=[]
    for field in ['revenue',key+'_capex']:
        for f in fields.get(field,[]):result.append(dict(f,metric='capex' if field.endswith('_capex') else field,filed=meta['filed'],accn=meta['accn'],form=meta['form'],source_url=meta['url']))
    indexed={field:{(f['start'],f['end']):f for f in fields.get(field,[])} for field in ['revenue','cost','interest']}
    for period,sales in indexed['revenue'].items():
        if period not in indexed['cost']:continue
        if period not in indexed['interest']:
            if key!='cvx':continue
            # Older Chevron statements have no separately presented interest row.
            # The dashboard definition adds back separately presented interest only.
            indexed['interest'][period]=dict(sales,val=0,source_tag='no separate interest line in original statement')
        costs=indexed['cost'][period];interest=indexed['interest'][period]
        result.append(dict(sales,metric='profit',val=sales['val']-costs['val']+interest['val'],filed=meta['filed'],accn=meta['accn'],form=meta['form'],source_url=meta['url'],
            derivation='Sales and other operating revenues − total costs and deductions/expenses + interest expense. Equity earnings and other non-sales income excluded; other non-interest deductions remain.',inputs=[sales,costs,interest]))
    return result

def bp_quarter_facts(content,meta):
    soup=BeautifulSoup(content,'lxml');year=int(meta['date'][:4]);q=(int(meta['date'][5:7])-1)//3+1
    if (dt.date.fromisoformat(meta['filed'])-dt.date.fromisoformat(meta['date'])).days>120:return []
    income=None;cash=None
    for table in soup.find_all('table'):
        txt=norm(table.get_text(' ',strip=True))
        if len(txt)>22000:continue
        if income is None and 'Sales and other operating revenues' in txt and 'Total revenues and other income' in txt and 'before taxation' in txt:income=table
        if cash is None and ('Expenditure on property, plant and equipment' in txt or re.search(r'\bCapital expenditure\b',txt)) and ('Cash and cash equivalents at' in txt or 'cash and cash equivalents at' in txt):cash=table
    result=[]
    for metric,pattern,table in [('revenue',r'Sales and other operating revenues(?: \(Note \d+\))?',income),('profit',r'Profit (?:\(loss\) )?before interest and tax(?:ation)?',income),('capex',r'(?:Expenditure on property, plant and equipment, intangible and other assets|Capital expenditure)',cash)]:
        if table is None:continue
        inline,_=html_row(soup,'^'+pattern,table=table)
        if inline:
            for f in inline:
                if f['end']!=meta['date'] or f['start']<f'{year}-01-01':continue
                result.append(dict(f,metric=metric,val=abs(f['val']) if metric=='capex' else f['val'],filed=meta['filed'],accn=meta['accn'],form='6-K',source_url=meta['url'],statement_period=meta['date']))
            continue
        table_text=norm(table.get_text(' ',strip=True));years=re.findall(r'\b20\d{2}\b',table_text[:table_text.lower().find('sales and other') if metric!='capex' else 400]);quarter_position=0 if not years or int(years[0])==year else 1
        for row in table.find_all('tr'):
            text=norm(row.get_text(' ',strip=True));text=re.sub(r'\(Note \d+\)','',text)
            match=re.search(pattern,text,re.I)
            if not match or len(text)>900:continue
            nums=NUMBER.findall(text[:match.start()])+NUMBER.findall(text[match.end():]);values=[number(n) for n in nums]
            if len(values) not in [2,4]:continue
            periods=[(f'{year}-{(q-1)*3+1:02d}-01',quarter_end(year,q),values[quarter_position])]
            if len(values)==4:periods.append((f'{year}-01-01',quarter_end(year,q),values[2]))
            # Q4 2015 explicitly amended earlier 2015 sales and purchases.
            # The 2016 same-quarter comparatives contain those amended sales.
            if metric=='revenue' and year==2016:
                periods.append((f'2015-{(q-1)*3+1:02d}-01',quarter_end(2015,q),values[1-quarter_position]))
            for start,end,v in periods:
                result.append(dict(metric=metric,start=start,end=end,val=(abs(v) if metric=='capex' else v)*1e6,filed=meta['filed'],accn=meta['accn'],form='6-K',source_url=meta['url'],source_tag='BP original statement row: '+pattern,statement_period=meta['date']))
            break
    return result

def shell_quarter_facts(content,meta):
    soup=financial_soup(content);income=None;cash=None
    for table in soup.find_all('table'):
        text=norm(table.get_text(' ',strip=True))
        if len(text)>25000:continue
        if income is None and 'Revenue' in text and 'Interest expense' in text and re.search(r'Income.*before taxation',text):income=table
        if cash is None and 'Capital expenditure' in text and re.search(r'cash.*operating activities',text,re.I) and re.search(r'cash.*financing activities',text,re.I):cash=table
    if income is None:return []
    header=norm(income.get_text(' ',strip=True))[:700]
    dates=[(int(y),int(q)) for q,y in re.findall(r'Q([1-4])\s+(20\d{2})',header)][:3]
    if len(dates)!=3:return []
    fields={};annual_capex=[]
    for field,table,pattern in [('revenue',income,r'\bRevenue\b'),('pbt',income,r'\bIncome(?:/\(loss\))? before taxation\b'),('interest',income,r'\bInterest expense\b'),('other',income,r'\bInterest and other income(?:/\(expenses\))?\b'),('capex',cash,r'\bCapital expenditure\b')]:
        if table is None:continue
        for row in table.find_all('tr'):
            text=norm(row.get_text(' ',strip=True));m=re.search(pattern,text,re.I)
            text=re.sub(r'(?<=[A-Za-z)])\s+[1-9](?:,[1-9])+(?=\s)',' ',text)
            m=re.search(pattern,text,re.I)
            if not m or len(text)>900:continue
            left=[number(v) for v in NUMBER.findall(text[:m.start()])]
            right=[number(v) for v in NUMBER.findall(text[m.end():])]
            expected=3 if dates[0][1]==1 else 5
            if len(left)>=3:values=left[:3]
            else:
                # Old releases append a percentage-change column. It is not a
                # fourth financial period. Footnote markers precede the values.
                if len(right)>expected and 0<=right[0]<=9:right=right[1:]
                values=right[:3] if len(right)>=3 else []
            if len(values)==3:
                fields[field]=values
                if field=='capex' and dates[0][1]==4 and ((len(left)>=3 and len(right)>=2) or len(right)>=5):
                    for i,value in enumerate(right[-2:]):
                        year=dates[0][0]-i
                        if year>=2014:annual_capex.append(dict(metric='capex',start=f'{year}-01-01',end=f'{year}-12-31',val=abs(value)*1e6,filed=meta['filed'],accn=meta.get('parent_accn',meta['accn']),form='6-K',source_url=meta['url'],source_tag='Shell original full-year cash flow comparative: Capital expenditure'))
                break
    result=annual_capex
    for i,(year,q) in enumerate(dates):
        if year<2014:continue
        start=f'{year}-{(q-1)*3+1:02d}-01';end=quarter_end(year,q)
        values={f:vs[i] for f,vs in fields.items()}
        metrics={field:values[field] for field in ['revenue','capex'] if field in values}
        if all(f in values for f in ['pbt','interest','other']):metrics['profit']=values['pbt']+values['interest']-values['other']
        for metric,value in metrics.items():
            f=dict(metric=metric,start=start,end=end,val=(abs(value) if metric=='capex' else value)*1e6,filed=meta['filed'],accn=meta.get('parent_accn',meta['accn']),form='6-K',source_url=meta['url'],source_tag='Shell original consolidated statement row: '+metric)
            if metric=='profit':f.update(derivation='PBT + interest expense − interest and other income',inputs=values)
            result.append(f)
    return result

def pdf_lines(page):
    """Keep PDF table rows by baseline rather than flattened reading order."""
    words=sorted(page.get_text('words'),key=lambda w:w[3]);groups=[]
    for word in words:
        if not groups or abs(word[3]-groups[-1][0])>3:groups.append([word[3],[]])
        groups[-1][1].append(word)
    return [sorted(ws,key=lambda w:w[0]) for _,ws in groups]

def pdf_row(page,label,side='right',xmin=None,xmax=None):
    for words in pdf_lines(page):
        if xmin is not None:words=[w for w in words if w[0]>=xmin]
        if xmax is not None:words=[w for w in words if w[2]<=xmax]
        text=norm(' '.join(w[4] for w in words));m=re.search(label,text,re.I)
        if not m:continue
        # Extract only the column side of the matched label, not footnote numbers.
        chars=0;chosen=[]
        for w in words:
            a=chars;b=a+len(w[4]);chars=b+1
            if (side=='right' and a>=m.end()) or (side=='left' and b<=m.start()):chosen.append(w)
        tokens=NUMBER.findall(' '.join(w[4] for w in chosen));values=[]
        for token in tokens:
            try:values.append(number(token))
            except ValueError:pass
        if values:return values
    return None

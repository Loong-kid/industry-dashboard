"""Period-preserving XR segment and HTC original-statement parsers."""
import calendar,datetime as dt,math,re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from cpu_business_history import local,REVENUE_TAGS

METRICS={'revenue':'매출','profit':'영업이익','capex':'CAPEX'}


def reality_labs(raw,filing,cik=1326801):
    root=ET.fromstring(raw);contexts={};result={'revenue':[],'profit':[]}
    for c in root.findall('{*}context'):
        identifier=c.find('.//{*}identifier')
        if identifier is None or int(identifier.text)!=cik:raise ValueError('Reality Labs issuer mismatch')
        members={local(x.text).lower() for x in c.findall('.//{*}explicitMember')}
        if members not in ({'realitylabsmember'},{'facebookrealitylabsmember'}):continue
        contexts[c.get('id')]={local(x.tag):x.text for x in c.findall('./{*}period/*')}
    units={u.get('id'):[local(x.text) for x in u.findall('.//{*}measure')] for u in root.findall('{*}unit')}
    seen={}
    for f in root:
        p=contexts.get(f.get('contextRef'),{});tag=local(f.tag)
        metric='revenue' if tag in REVENUE_TAGS else 'profit' if tag=='OperatingIncomeLoss' else None
        if not metric or not p.get('startDate') or not p.get('endDate') or units.get(f.get('unitRef'))!=['USD']:continue
        try:value=float(f.text)
        except (ValueError,TypeError):continue
        if not math.isfinite(value) or metric=='revenue' and value<0:raise ValueError('Invalid Reality Labs amount')
        key=metric,p['startDate'],p['endDate']
        if key in seen:
            if seen[key]!=value:raise ValueError('Conflicting Reality Labs contexts')
            continue
        seen[key]=value
        result[metric].append(dict(start=p['startDate'],end=p['endDate'],val=value,accn=filing['accessionNumber'],filed=filing['filingDate'],form=filing['form'],source_url=filing['url'],source_tag=tag+' · Reality Labs'))
    return result


def htc_links(html,base):
    from urllib.parse import urljoin
    result=[]
    for tr in BeautifulSoup(html,'html.parser').select('tr'):
        label=tr.get_text(' ',strip=True)
        match=re.search(r'(20\d{2})\s+Q([1-4])\s*Financial Results\s*-\s*Consolidated Financial Report',label,re.I)
        a=tr.select_one('a[href]')
        if not match or not a or 'mandarin' in label.lower():continue
        url=urljoin(base,a['href']).replace('https://investors-express.htc.com/','https://investors.htc.com/')
        if '?' not in url:url+='?download=1'
        result.append(dict(year=int(match[1]),quarter=int(match[2]),url=url))
    return result


def amounts(lines,index):
    text=' '.join(lines[index:index+4])
    text=re.sub(r'\(Notes?\s+[\d\s,and-]+\)','',text,flags=re.I)
    # Actual columns are separated from the left-side account labels by >=2
    # spaces. Preserve the sign of operating losses and cash outflows.
    match=re.search(r' {2,}(?=\$?\s*\(?-?\d|[-–—](?:\s|$))',text)
    if not match:raise ValueError('HTC numeric columns not found')
    text=text[match.end():]
    text=re.split(r'\s{2,}(?=[A-Za-z])',text)[0]
    tokens=re.findall(r'\(?-?\d[\d,]*(?:\.\d+)?\)?|(?<!\w)[–—-](?!\w)',text)
    return [0. if t in ('-','–','—') else float(t.replace(',','').strip('()'))*(-1 if t.startswith('(') else 1) for t in tokens]


def parse_htc_text(text,year,quarter,url,checked):
    if 'HTC CORPORATION AND SUBSIDIARIES' not in text or not re.search(r'Thousands of New Taiwan Dollars',text,re.I):raise ValueError('HTC issuer/unit mismatch')
    end=f'{year}-{quarter*3:02d}-{calendar.monthrange(year,quarter*3)[1]}'
    if end>checked:raise ValueError('Future HTC report')
    lines=text.splitlines();income=[];cash=[]
    for i,line in enumerate(lines):
        if 'CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME' in line:income.append(i)
        if 'CONSOLIDATED STATEMENTS OF CASH FLOWS' in line:cash.append(i)
    if not income or not cash:raise ValueError('Missing consolidated HTC statements')
    chunk=lines[income[0]:cash[0]];header=' '.join(chunk[:16])
    years=re.findall(r'\b20\d{2}\b',header)
    if not years or int(years[0])!=year:raise ValueError('HTC statement year mismatch')
    values={};direct={};previous_values={};previous_direct={}
    for field,pattern in [('revenue',r'^(?:OPERATING )?REVENUES?\b'),('profit',r'^(?:OPERATING (?:PROFIT|LOSS|INCOME)(?:\s*\(LOSS\))?\b|(?:\(LOSS\)\s*)?(?:PROFIT|LOSS)(?:\s*\(LOSS\))?\s+FROM OPERATIONS\b)')]:
        i=next((i for i,l in enumerate(chunk) if re.search(pattern,l.strip())),None)
        if i is None:raise ValueError('HTC income subtotal missing: '+field)
        nums=amounts(chunk,i)
        # Two income columns in Q1/annual; four in Q2/Q3. Each has a %.
        columns=4 if quarter in (2,3) and len(nums)>=8 else 2
        if len(nums)<columns*2:raise ValueError('HTC income columns incomplete')
        values[field]=nums[4] if columns==4 else nums[0]
        previous_values[field]=nums[6] if columns==4 else nums[2]
        if quarter!=4:direct[field]=nums[0]
        if quarter!=4:previous_direct[field]=nums[2]
    cf=lines[cash[0]:]
    index=next((i for i,l in enumerate(cf) if re.search(r'(Payments for|Acquisition of|Purchase[s]? of) property,? plant and equipment',l,re.I)),None)
    if index is None:raise ValueError('HTC cash PP&E row missing')
    cash_amounts=amounts(cf,index)
    values['capex']=abs(cash_amounts[0]);previous_values['capex']=abs(cash_amounts[1])
    refs={m:dict(url=url,filed=checked,start=f'{year}-01-01',end=end,tag='HTC consolidated original PDF · '+m,calculation='reported YTD; NT$ thousand / 1000') for m in values}
    previous_end=f'{year-1}-'+end[5:]
    comparative=dict(year=year-1,quarter=quarter,date=previous_end,start=f'{year-1}-01-01',values={m:v/1000 for m,v in previous_values.items()},direct={m:v/1000 for m,v in previous_direct.items()},
        refs={m:dict(ref,start=f'{year-1}-01-01',end=previous_end,comparative=True) for m,ref in refs.items()})
    return dict(year=year,quarter=quarter,date=end,start=f'{year}-01-01',values={m:v/1000 for m,v in values.items()},direct={m:v/1000 for m,v in direct.items()},refs=refs,comparatives=[comparative])


def htc_accounts(reports):
    by={(r['year'],r['quarter']):r for r in reports};annual=[];rows=[]
    for (year,q),r in sorted(by.items()):
        if q==4:
            a=dict(date=r['date'],start=r['start'],year=year,refs={})
            for m,v in r['values'].items():a[m]=v;a['refs'][m]=dict(r['refs'][m],components=[r['refs'][m]],calculation='reported annual · NT$ thousand / 1000')
            annual.append(a)
        out=dict(date=r['date'],start=f'{year}-{(q-1)*3+1:02d}-01',year=year,quarter=q,refs={})
        for m,v in r['values'].items():
            if m in r['direct']:value=r['direct'][m];components=[r['refs'][m]];calc='reported three months · NT$ thousand / 1000'
            elif q==1:value=v;components=[r['refs'][m]];calc='reported first quarter · NT$ thousand / 1000'
            elif (year,q-1) in by:
                previous=by[year,q-1];value=v-previous['values'][m];components=[r['refs'][m],previous['refs'][m]];calc='same fiscal-year YTD minus prior YTD · NT$ thousand / 1000'
            else:continue
            if m!='profit' and value<0:continue
            out[m]=value;out['refs'][m]=dict(r['refs'][m],components=components,calculation=calc)
        if 'revenue' in out:rows.append(out)
    return dict(rows=rows,annual=annual)

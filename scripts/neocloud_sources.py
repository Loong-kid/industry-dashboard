"""Native USD segment facts and Nebius's untagged 6-K financial tables."""
import calendar,datetime as dt,math,re,xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from cpu_business_history import local

REVENUE={'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax'}


def native_cloud(raw,key,spec,filing):
    root=ET.fromstring(raw);contexts={};result=[]
    for c in root.findall('{*}context'):
        entity=c.find('./{*}entity/{*}identifier')
        if entity is None or int(entity.text)!=spec['cik']:raise ValueError('Neocloud issuer mismatch')
        period={local(p.tag):p.text for p in c.findall('./{*}period/*')}
        members={local(m.text).lower() for m in c.findall('.//{*}explicitMember')}-{'operatingsegmentsmember'}
        contexts[c.get('id')]=(period,members)
    units={u.get('id'):[local(x.text) for x in u.findall('.//{*}measure')] for u in root.findall('{*}unit')}
    wanted={'nbis':{'nebiussegmentmember'},'iren':{'aicloudservicesmember'}}[key]
    for x in root:
        period,members=contexts.get(x.get('contextRef'),({},set()))
        if local(x.tag) not in REVENUE or members!=wanted or units.get(x.get('unitRef'))!=['USD'] or not period.get('startDate'):continue
        value=float(x.text)
        if not math.isfinite(value) or value<0:raise ValueError('Invalid cloud revenue')
        result.append(fact(value,period['startDate'],period['endDate'],filing,local(x.tag)+' · '+','.join(sorted(members))))
    return {'cloud_revenue':result} if result else {}


def fact(value,start,end,filing,tag):
    return dict(start=start,end=end,val=value,filed=filing['filingDate'],form=filing['form'],accn=filing['accessionNumber'],source_url=filing['url'],source_tag=tag)


def clean(s):return re.sub(r'\s+',' ',s.replace('\u200b','')).strip()


def numbers(cells):
    # Parentheses can occupy a separate TD in EDGAR's financial tables.
    text=' '.join(cells).replace(',','').replace('$','')
    tokens=re.findall(r'\(?\s*-?\d+(?:\.\d+)?\s*\)?|[—–]',text)
    return [0. if t in ('—','–') else float(t.strip().strip('()').replace(' ',''))*(-1 if '(' in t else 1) for t in tokens]


def columns(table):
    """Read actual months and comparative years; never the filing/reportDate."""
    headers=[];years=[]
    for tr in table.find_all('tr',recursive=False) or table.select('tr'):
        cs=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
        if any(re.fullmatch(r'20\d{2}\*?',s) for s in cs):
            years=[int(s.rstrip('*')) for s in cs if re.fullmatch(r'20\d{2}\*?',s)];break
        headers.extend(cs)
    text=' '.join(headers)
    groups=re.findall(r'(Three\s+months|Six\s+months|Nine\s+months|Twelve\s+months|Years?)\s+ended\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})',text,re.I)
    if not groups or not years or len(years)%len(groups):return []
    result=[];n=len(years)//len(groups)
    for i,(duration,month,day) in enumerate(groups):
        months={'three months':3,'six months':6,'nine months':9,'twelve months':12,'year':12,'years':12}[duration.lower()]
        m=dt.datetime.strptime(month,'%B').month
        for y in years[i*n:(i+1)*n]:
            startmonth=m-months+1
            if startmonth<1:raise ValueError('Unexpected Nebius fiscal period')
            result.append((f'{y}-{startmonth:02d}-01',f'{y}-{m:02d}-{int(day):02d}'))
    return result


def nebius_tables(raw,filing):
    soup=BeautifulSoup(raw,'html.parser');fields={}
    for table in soup.select('table'):
        text=clean(table.get_text(' ',strip=True));periods=columns(table)
        if not periods or 'Change' in text[:400]:continue
        statement='Total operating costs and expenses' in text and 'Loss from operations' in text
        cash='Purchases of property and equipment and intangible assets' in text
        segment='Total segment revenues' in text and 'Revenues:' in text
        if not(statement or cash or segment):continue
        mode=None
        for tr in table.select('tr'):
            cs=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
            nonempty=[s for s in cs if s]
            if not nonempty:continue
            label=nonempty[0]
            if label=='Revenues:':mode='revenue'
            if 'Adjusted EBITDA' in label:mode=None
            field='revenue' if statement and label=='Revenues' else 'profit' if statement and label=='Loss from operations' else 'capex' if cash and label=='Purchases of property and equipment and intangible assets' else 'cloud_revenue' if segment and label in ('Nebius','Nebius AI cloud') and mode=='revenue' else None
            if not field:continue
            amounts=numbers(nonempty[1:])
            if len(amounts)!=len(periods):raise ValueError('Unexpected Nebius statement columns: '+label)
            for (start,end),value in zip(periods,amounts):
                if field=='capex':value=abs(value)
                fields.setdefault(field,[]).append(fact(value*1e6,start,end,filing,'Nebius GAAP statement · '+label))
    return fields


def nebius_letter(raw,filing):
    text=clean(BeautifulSoup(raw,'html.parser').get_text(' ',strip=True))
    result=[]
    # Exact narrative disclosures, not rounded infographic values or ARR.
    for m in re.finditer(r'(?:Nebius AI cloud|Core AI cloud) revenue was \$([\d,.]+) million in Q([1-4])[’\'](\d{2})',text):
        value,q,y=float(m[1].replace(',','')),int(m[2]),2000+int(m[3]);month=q*3
        result.append(fact(value*1e6,f'{y}-{month-2:02d}-01',f'{y}-{month:02d}-{calendar.monthrange(y,month)[1]}',filing,'Nebius shareholder letter · actual AI cloud revenue'))
    # 2026 Q1 and prior letters provide exact financial narrative separately.
    return {'cloud_revenue':result} if result else {}


def nebius_rpo(raw,filing):
    text=clean(BeautifulSoup(raw,'html.parser').get_text(' ',strip=True));result=[]
    pattern=r'As of ([A-Za-z]+ \d{1,2}, 20\d{2}), the amount of unsatisfied RPO was \$([\d,.]+)'
    for m in re.finditer(pattern,text,re.I):
        if 'in millions' not in text.lower():raise ValueError('Unverified Nebius RPO unit')
        end=dt.datetime.strptime(m[1],'%B %d, %Y').date().isoformat()
        r=fact(float(m[2].replace(',',''))*1e6,end,end,filing,'Nebius financial statement · ASC 606 unsatisfied RPO')
        r['instant']=True;result.append(r)
    if 'amount of unsatisfied RPO' in text and not result:raise ValueError('Unmapped new Nebius RPO note')
    return {'rpo':result} if result else {}

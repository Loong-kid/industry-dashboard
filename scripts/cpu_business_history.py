"""Public SEC XBRL revenue dimensions, preserving company/product scope.

Company Facts omits segment dimensions. Read the filing's native XBRL instance
instead of interpreting a missing Company Facts tag as an undisclosed quarter.
"""
import datetime as dt
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup

UA='industry-dashboard personal research wkorotk@gmail.com'
REVENUE_TAGS={'RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet','SalesRevenueGoodsNet','SalesRevenueServicesNet'}


def local(tag):return tag.rsplit('}',1)[-1].split(':')[-1]


def field_for(company,tag,members):
    names={local(v).lower() for v in members}
    names-={'operatingsegmentsmember','reportablesegmentmember'}
    if tag not in REVENUE_TAGS:return None
    if not members:
        if company=='qualcomm':return '_total' if tag=='Revenues' else None
        return '_total' if tag in ('RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet','Revenues') else None
    if company=='arm':
        return {'royaltymember':'royalty','licenseandotherrevenuemember':'license'}.get(next(iter(names),'') ) if len(names)==1 else None
    if company=='apple' and len(names)==1:
        return {'iphonemember':'iphone','macmember':'mac','macintoshmember':'mac','ipadmember':'ipad',
          'applemacmember':'mac',
          'servicemember':'services','itunessoftwareandservicesmember':'services',
          'wearableshomeandaccessoriesmember':'wearables','otherproductsmember':'other_products',
          'ipodmember':'ipod','accessoriesmember':'accessories'}.get(next(iter(names)))
    if company=='qualcomm':
        if names=={'qtlmember'}:return 'qtl'
        for member,field in [('handsetsmember','handsets'),('mobilehandsetsmember','handsets'),('automotivemember','automotive'),('iotmember','iot')]:
            if names in ({member},{member,'qctmember'}):return field
    if company=='intel' and len(names)==1:
        return {'clientcomputingandphysicalaigroupmember':'client','clientcomputinggroupmember':'client',
          'datacenterandaimember':'datacenter'}.get(next(iter(names)))
    if company=='amd':
        if names in ({'clientmember'},{'clientmember','clientandgamingmember'}):return 'client'
        if names=={'datacentermember'}:return 'datacenter'
    return None


def parse_instance(body,company,filing):
    root=ET.fromstring(body)
    contexts={}
    for context in root.findall('{*}context'):
        period={local(x.tag):x.text for x in context.findall('./{*}period/*')}
        members=[x.text for x in context.findall('.//{*}explicitMember')]
        contexts[context.get('id')]=(period,members)
    units={u.get('id'):[x.text for x in u.findall('.//{*}measure')] for u in root.findall('{*}unit')}
    result={}
    for fact in root:
        if not fact.get('contextRef'):continue
        period,members=contexts.get(fact.get('contextRef'),({},[]))
        if not period.get('startDate') or not period.get('endDate'):continue
        if not any(local(m)=='USD' for m in units.get(fact.get('unitRef'),[])):continue
        field=field_for(company,local(fact.tag),members)
        if not field:continue
        try:value=float(fact.text)
        except (ValueError,TypeError):continue
        if value<0:continue
        row=dict(start=period['startDate'],end=period['endDate'],val=value,accn=filing['accessionNumber'],
            filed=filing['filingDate'],form=filing['form'],source_tag=local(fact.tag),source_url=filing['url'])
        key=(field,row['start'],row['end'])
        # Redundant segment and consolidated contexts must agree, never be summed.
        if key in result and result[key]['val']!=value:
            raise ValueError('Conflicting revenue dimension '+field)
        result[key]=row
    fields={}
    for (field,_,_),row in result.items():fields.setdefault(field,[]).append(row)
    return fields


def parse_apple_legacy(html,instance,filing):
    """Pre-2019 product rows were in MD&A, not separate numeric XBRL facts."""
    root=ET.fromstring(instance);periods={};annual_periods={}
    for context in root.findall('{*}context'):
        if context.findall('.//{*}explicitMember'):continue
        period={local(x.tag):x.text for x in context.findall('./{*}period/*')}
        if period.get('startDate') and period.get('endDate'):
            days=(dt.date.fromisoformat(period['endDate'])-dt.date.fromisoformat(period['startDate'])).days+1
            if 75<=days<=300:periods.setdefault(period['endDate'],set()).add((period['startDate'],period['endDate'],days))
            if 350<=days<=380:annual_periods[period['endDate']]=(period['startDate'],period['endDate'],days)
    fields={}
    soup=BeautifulSoup(html,'html.parser')
    for table in soup.select('table'):
        text=table.get_text(' ',strip=True)
        if len(text)>20000 or not all(t in text for t in ('iPhone','Mac')):continue
        annual=filing['form']=='10-K' and 'Three Months Ended' not in text
        if not annual and 'Three Months Ended' not in text:continue
        if annual and not re.search('Net Sales by (Product|Category)',text,re.I):continue
        dates=re.findall(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(20\d{2})',text)
        ends=[]
        for month,day,year in dates:
            end=dt.datetime.strptime(f'{month} {day} {year}','%B %d %Y').date().isoformat()
            if end not in ends:ends.append(end)
        if annual:ends=sorted((e for e in annual_periods if e<=filing['reportDate']),reverse=True)[:3]
        if len(ends)<2 or ends[0]!=filing['reportDate']:continue
        mode='sales' if 'Unit Sales' not in text else None
        for row in table.select('tr'):
            cells=[x.get_text(' ',strip=True) for x in row.find_all(['td','th'],recursive=False)]
            nonempty=[s for s in cells if s]
            if not nonempty:continue
            label=nonempty[0]
            if re.match(r'Net Sales by (Product|Category)',label,re.I):mode='sales';continue
            if re.match(r'Unit Sales',label,re.I):mode='units';continue
            if mode!='sales':continue
            label=re.sub(r'(?:\s*\([a-z0-9]+\))+$','',label).strip().lower()
            field={'iphone':'iphone','ipad':'ipad','mac':'mac','ipod':'ipod','itunes, software and services':'services',
                   'services':'services','accessories':'accessories','other products':'other_products'}.get(label)
            if not field:continue
            amounts=[]
            for i,cell in enumerate(nonempty[1:]):
                tail=nonempty[i+2:]
                if '%' in cell or (tail and tail[0]=='%'):continue
                token=cell.replace('$','').replace(',','').strip()
                if re.fullmatch(r'\d+(?:\.\d+)?',token):amounts.append(float(token)*1e6)
            if annual:
                if len(amounts)!=len(ends):continue
                for end,amount in zip(ends,amounts):
                    period=annual_periods[end]
                    fields.setdefault(field,[]).append(dict(start=period[0],end=end,val=amount,
                        accn=filing['accessionNumber'],filed=filing['filingDate'],form=filing['form'],
                        source_tag='Apple MD&A net sales by product',source_url=filing['url']))
                continue
            if len(amounts) not in (2,4):continue
            for i,end in enumerate(ends[:2]):
                available=periods.get(end,set())
                direct=[p for p in available if 75<=p[2]<=105]
                cumulative=[p for p in available if 105<p[2]<=300]
                for period,index in [(max(direct,key=lambda p:p[0]) if direct else None,i),
                                     (max(cumulative,key=lambda p:p[2]) if cumulative and len(amounts)==4 else None,i+2)]:
                    if not period:continue
                    fields.setdefault(field,[]).append(dict(start=period[0],end=end,val=amounts[index],
                        accn=filing['accessionNumber'],filed=filing['filingDate'],form=filing['form'],
                        source_tag='Apple MD&A net sales by product',source_url=filing['url']))
    return fields


class SecClient:
    def __init__(self,cache):
        self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.session=requests.Session();self.session.headers['User-Agent']=UA
        self.last=0
    def get(self,url,refresh=False):
        path=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.raw')
        if path.exists() and not refresh:return path.read_bytes()
        time.sleep(max(0,.36-(time.monotonic()-self.last)))
        self.last=time.monotonic()
        response=self.session.get(url,timeout=45);response.raise_for_status()
        path.write_bytes(response.content)
        return response.content
    def filings(self,cik,asof):
        doc=json.loads(self.get(f'https://data.sec.gov/submissions/CIK{cik:010d}.json',refresh=True))
        blocks=[doc['filings']['recent']]
        for block in doc['filings']['files']:
            if block['filingTo']>='2013-01-01':
                blocks.append(json.loads(self.get('https://data.sec.gov/submissions/'+block['name'])))
        result={}
        for rows in blocks:
            for i,form in enumerate(rows['form']):
                date=rows['filingDate'][i]
                if form not in ('10-K','10-Q','20-F','6-K') or not '2013-01-01'<=date<=asof:continue
                row={k:rows[k][i] for k in ('form','filingDate','reportDate','accessionNumber','primaryDocument')}
                row['url']=f'https://www.sec.gov/Archives/edgar/data/{cik}/{row["accessionNumber"].replace("-","")}/{row["primaryDocument"]}'
                result[row['accessionNumber']]=row
        return sorted(result.values(),key=lambda r:r['filingDate'])
    def instance(self,filing):
        base=filing['url'].rsplit('/',1)[0]+'/'
        index=json.loads(self.get(base+'index.json'))
        files=[f['name'] for f in index['directory']['item'] if f['name'].endswith('_htm.xml')]
        if not files:
            files=[f['name'] for f in index['directory']['item'] if f['name'].endswith('.xml') and not any(x in f['name'].lower() for x in ('_cal','_def','_lab','_pre','filingsummary','metalinks'))]
        if len(files)!=1:raise ValueError('XBRL instance missing or ambiguous')
        return self.get(base+files[0])


def collect_business(companies,prior,cache,asof,full=False):
    client=SecClient(cache)
    result=json.loads(json.dumps(prior))
    for key,company in companies.items():
        old=result.get(key,{})
        try:
            filings=client.filings(company['cik'],asof)
            # Arm business updates without financial XBRL are not earnings filings.
            if key=='arm':filings=[f for f in filings if f['form']=='20-F' or f['reportDate'][5:] in ('03-31','06-30','09-30','12-31')]
            # Intel/AMD: current segment basis from 2023; avoid joining older divisions.
            since='2023-01-01' if key in ('intel','amd') else '2014-01-01' if key in ('apple','qualcomm') else '2013-01-01'
            filings=[f for f in filings if f['filingDate']>=since]
            known=set(old.get('filings',[]))
            merged={field:{(r['start'],r['end'],r['filed'],r['accn']):r for r in rows} for field,rows in old.get('facts',{}).items()}
            failures=[]
            for filing in filings:
                if filing['accessionNumber'] in known and not full:continue
                try:
                    instance=client.instance(filing)
                    fields=parse_instance(instance,key,filing)
                    if key=='apple' and filing['filingDate']<'2019-01-01':
                        legacy=parse_apple_legacy(client.get(filing['url']),instance,filing)
                        for field,rows in legacy.items():
                            existing={(r['start'],r['end']) for r in fields.get(field,[])}
                            fields.setdefault(field,[]).extend(r for r in rows if (r['start'],r['end']) not in existing)
                    if not fields:raise ValueError('No mapped revenue dimensions')
                    for field,rows in fields.items():
                        cohort=merged.setdefault(field,{})
                        for r in rows:cohort[r['start'],r['end'],r['filed'],r['accn']]=r
                    known.add(filing['accessionNumber'])
                except Exception as error:
                    failures.append(dict(date=filing['filingDate'],form=filing['form'],reason=type(error).__name__))
            if not merged:raise ValueError('No successful business evidence')
            result[key]=dict(facts={field:sorted(rows.values(),key=lambda r:(r['end'],r['start'],r['filed'])) for field,rows in merged.items()},
                filings=sorted(known),checked=asof,fetched=asof if len(known)>len(old.get('filings',[])) else old.get('fetched',asof),
                ok=not failures,failed=failures)
            print(key,'business',len(known),'filings,',sum(len(x) for x in merged.values()),'facts, failures',len(failures),flush=True)
        except Exception as error:
            if not old.get('facts'):raise RuntimeError(key+': no business history') from error
            result[key]=dict(old,checked=asof,ok=False)
            print(key,'business retained:',type(error).__name__,flush=True)
    return result

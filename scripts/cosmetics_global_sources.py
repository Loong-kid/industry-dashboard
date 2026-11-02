"""Official issuer releases and SEC facts; retain actual reporting frequencies."""
import calendar,datetime as dt,json,re,ast
from pathlib import Path
from bs4 import BeautifulSoup
from fetch_cpu_companies import parse_facts,parse_annual

NUM=r'\(?[−–-]?[\d][\d,]*(?:\.\d+)?\)?'
def number(value):
    text=re.sub(r'[\s,\u00a0]','',value).replace('−','-').replace('–','-')
    if not re.fullmatch(r'\(?-?\d+(?:\.\d+)?\)?',text):return None
    return -float(text[1:-1]) if text.startswith('(') else float(text)

def end(y,q):return f'{y}-{q*3:02d}-{calendar.monthrange(y,q*3)[1]}'
def reference(url,start,finish,label,filed,basis):
    return dict(url=url,start=start,end=finish,tag=label,filed=filed,basis=basis)
def add(rows,kind,year,q,metric,value,ref):
    finish=ref['end'];key=(kind,finish)
    r=rows.setdefault(key,dict(kind=kind,date=finish,year=year,quarter=q,refs={},basis=ref['basis']))
    r[metric]=value;r['refs'][metric]=dict(ref,components=[dict(ref)],calculation='reported '+kind)


def loreal_release(raw,meta):
    soup=BeautifulSoup(raw,'html.parser');text=soup.get_text(' ',strip=True)
    if not soup.select_one('h1') or str(meta['year']) not in soup.select_one('h1').get_text():raise ValueError('Wrong Loreal result year')
    y=meta['year'];kind=meta['kind'];rows={};url=meta['url']
    date=re.search(r'(?:Press release|Other)\s+(\d{1,2}\s+[A-Za-z]+\s+20\d{2})',text)
    if not date:raise ValueError('Loreal release date unavailable')
    filed=dt.datetime.strptime(date[1],'%d %B %Y').date().isoformat()
    def ref(start,finish,label):return reference(url,start,finish,label,filed,'L’Oréal company-reported')
    for table in soup.select('table'):
        tr=[[c.get_text(' ',strip=True) for c in r.find_all(['td','th'],recursive=False)] for r in table.select('tr')]
        flat=table.get_text(' ',strip=True)
        if 'Cost of sales' in flat and 'Operating profit' in flat:
            for label,metric in [('Sales','revenue'),('Operating profit','profit')]:
                cells=next((r for r in tr if r and r[0]==label),None)
                if not cells:continue
                values=[number(v) for v in cells[1:] if number(v) is not None]
                if not values:continue
                # The first management P&L table orders prior periods first,
                # followed by the current annual or current H1 period.
                value=values[-1];finish=f'{y}-12-31' if kind=='annual' else f'{y}-06-30'
                add(rows,'annual' if kind=='annual' else 'half',y,4 if kind=='annual' else 2,metric,value,ref(f'{y}-01-01',finish,label))
            break
    if kind in ['annual','half']:
        candidates=[]
        for p in soup.select('p'):
            t=p.get_text(' ',strip=True)
            if not re.search(r'\binvestments\b',t,re.I) or not re.search(r'million euros',t,re.I):continue
            # Match the reported amount, never a percentage or growth rate.
            patterns=[r'\bAt\s+('+NUM+r')\s+million euros,?\s+(?:the\s+)?investments',r'\bInvestments\b[^.]{0,100}?(?:amounted to|at|of|to)\s+('+NUM+r')\s+million euros']
            for pattern in patterns:
                m=re.search(pattern,t,re.I)
                if m:candidates.append(number(m[1]));break
        candidates=set(candidates)
        if len(candidates)!=1:raise ValueError(f'Loreal investments require review: {y} {kind} {candidates}')
        finish=f'{y}-12-31' if kind=='annual' else f'{y}-06-30'
        add(rows,'annual' if kind=='annual' else 'half',y,4 if kind=='annual' else 2,'capex',next(iter(candidates)),ref(f'{y}-01-01',finish,'Investments · company definition'))
    for table in soup.select('table'):
        tr=[[c.get_text(' ',strip=True) for c in r.find_all(['td','th'],recursive=False)] for r in table.select('tr')]
        if not any(r and re.fullmatch(r'First quarter(?: total)?',r[0]) for r in tr):continue
        # Appendix is prior year / current year. Empty future cells stay empty.
        for q,word in enumerate(['First','Second','Third','Fourth'],1):
            candidates=[r for r in tr if r and re.fullmatch(word+r' quarter(?: total)?',r[0])]
            if not candidates:continue
            cells=candidates[-1]
            if len(cells) not in [3,5] or any('%' not in c for c in cells[3:] if c):raise ValueError('Loreal quarterly appendix columns changed')
            value=number(cells[2])
            if value is not None:add(rows,'quarter',y,q,'revenue',value,ref(f'{y}-{q*3-2:02d}-01',end(y,q),word+' quarter total'))
        break
    return list(rows.values())


def shiseido_statement(text,meta):
    # Inner financial statements, not the headline table containing Core profit
    # or the forecast. Two actual columns are prior period / current period.
    header=text[:12000]
    if 'Shiseido Company, Limited' not in header or '4911' not in header or not re.search(r'Millions of yen',text,re.I):raise ValueError('Shiseido issuer/currency not verified')
    match=re.search(r'(Three|Six|Nine) Months Ended\s+(March|June|September)\s+\d{1,2},?\s*(20\d{2})',header,re.I)
    if match:y=int(match[3]);q={'Three':1,'Six':2,'Nine':3}[match[1].title()]
    else:
        old=re.search(r'(First|Second|Third) (Quarter|Half) of the Fiscal Year Ending December 31,?\s*(20\d{2})',header,re.I)
        match=re.search(r'(?:Fiscal )?Year Ended\s+December\s+31,?\s*(20\d{2})',header,re.I)
        if old:y=int(old[3]);q=2 if old[2].lower()=='half' else {'First':1,'Second':2,'Third':3}[old[1].title()]
        elif match:y=int(match[1]);q=4
        else:raise ValueError('Unrecognized Shiseido statement period')
    basis='IFRS' if '[IFRS]' in header else 'JGAAP'
    filed=meta['filed'];rows={}
    patterns={'revenue':r'Net sales','profit':r'Operating (?:profit|income|loss)(?:\s*\((?:loss|profit)\))?','capex':r'(?:Acquisition|Purchase|Purchases|Payments for purchases) of property,? plant and equipment'}
    for metric,label in patterns.items():
        matches=re.findall(r'^\s*('+label+r')\s+('+NUM+r')\s+('+NUM+r')\s*$',text,re.M|re.I)
        if not matches:
            if metric=='capex':continue
            raise ValueError('Shiseido actual statement row missing: '+metric)
        # First matching inner statement row; following rows may be segment
        # reconciliations but cannot replace the consolidated statement.
        name,prior,current=matches[0]
        for year,value in [(y,number(current)),(y-1,number(prior))]:
            if value is None:continue
            if metric=='capex':value=abs(value)
            elif metric=='profit' and re.fullmatch(r'Operating loss',name,re.I):value=-abs(value)
            finish=end(year,q);ref=reference(meta['url'],f'{year}-01-01',finish,name,filed,basis)
            add(rows,'annual' if q==4 else 'ytd',year,q,metric,value,ref)
    return list(rows.values())


def quarterly_from_ytd(rows,versions=()):
    result=[];index={(r['year'],r['quarter']):r for r in rows if r['kind'] in ['ytd','annual']}
    for (year,q),row in sorted(index.items()):
        r=dict(kind='quarter',date=row['date'],year=year,quarter=q,refs={},basis=row['basis'])
        for metric in ['revenue','profit','capex']:
            if metric not in row:continue
            if q==1:r[metric]=row[metric];r['refs'][metric]=row['refs'][metric];continue
            prior=index.get((year,q-1))
            if not prior or metric not in prior or prior['basis']!=row['basis']:continue
            a,b=row['refs'][metric],prior['refs'][metric]
            if b['filed']>a['filed']:
                candidates=[r for r in versions if r['year']==year and r['quarter']==q-1 and r['basis']==row['basis'] and metric in r and r['refs'][metric]['filed']<=a['filed']]
                if not candidates:continue
                prior=max(candidates,key=lambda r:r['refs'][metric]['filed']);b=prior['refs'][metric]
            value=row[metric]-prior[metric]
            if metric!='profit' and value<0:continue
            r[metric]=value;r['refs'][metric]=dict(a,start=f'{year}-{q*3-2:02d}-01',components=[a,b],calculation='same fiscal year/basis YTD minus prior YTD')
        if r['refs']:result.append(r)
    return result


def estee_accounts(payload,asof):
    spec=dict(cik=1001250,fiscal_start=7)
    return dict(rows=parse_facts(payload,spec,asof),annual=parse_annual(payload,spec,asof))


def shiseido_chart(text,url,asof,jgaap=False):
    categories=re.search(r'var mcategories\s*=\s*(\[[\s\S]*?\]);',text)
    if not categories:raise ValueError('Shiseido annual categories missing')
    categories=ast.literal_eval(categories[1])
    def block(name):
        match=re.search(r'\b'+name+r'\s*:\s*\{[\s\S]*?master\s*:\s*(\[[\s\S]*?\])\s*,\s*indexes',text)
        if not match:raise ValueError('Shiseido chart block missing')
        return json.loads(re.sub(r',\s*]',']',match[1]))
    income=block('gyouseki');capex=block('other');rows={}
    for i,category in enumerate(categories):
        y,m=map(int,category.split('.'));finish=f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]}'
        if finish>asof:continue
        kind='transition' if category=='2015.12' else 'annual'
        start=f'{y-1}-04-01' if m==3 else f'{y}-04-01' if kind=='transition' else f'{y}-01-01'
        ref=lambda label:reference(url,start,finish,label,asof,'JGAAP' if jgaap else 'IFRS')
        # IFRS chart uses Core operating profit; never pass it as reported OP.
        if jgaap:
            add(rows,kind,y,4,'revenue',float(income[0][i])*1000,ref('Net Sales · official chart rounded JPY billion'))
            add(rows,kind,y,4,'profit',float(income[3][i])*1000,ref('Operating profit · official chart rounded JPY billion'))
        add(rows,'reported_annual',y,4,'capex',float(capex[0][i])*1000,ref('Capital expenditures · company definition (includes intangibles)'))
        if kind=='transition':rows['reported_annual',finish]['transition']=True
    return list(rows.values())

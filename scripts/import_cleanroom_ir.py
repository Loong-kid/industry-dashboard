"""Import issuer-hosted consolidated PDF financial statements; no chart estimates."""
import re,time,unicodedata
from urllib.parse import urljoin
import requests
import pymupdf
from bs4 import BeautifulSoup
from cleanroom_sources import ROOT,CACHE,end,accounts,number
from fetch_cpu_companies import load,save,today

IR_CACHE=ROOT/'.cache/cleanroom/ir'

def pdf(url,key,refresh=False):
    path=IR_CACHE/(key+'.pdf');path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or refresh:
        info=load(path.with_suffix('.json'),{});headers={}
        if path.exists() and info.get('etag'):headers['If-None-Match']=info['etag']
        if path.exists() and info.get('modified'):headers['If-Modified-Since']=info['modified']
        r=requests.get(url,headers=headers,timeout=(10,45));r.raise_for_status()
        if r.status_code!=304:
            if not r.content.startswith(b'%PDF'):raise ValueError('Not a PDF statement')
            path.write_bytes(r.content)
            save(path.with_suffix('.json'),dict(etag=r.headers.get('ETag'),modified=r.headers.get('Last-Modified')))
        time.sleep(.4)
    with pymupdf.open(path) as doc:
        pages=[]
        for p in list(doc)[:18]:
            if p.rotation:p.remove_rotation()
            pages.append(unicodedata.normalize('NFKC',p.get_text(sort=True)))
        return pages

def numeric_tail(line):
    m=re.search(r'\s{2,}([\d,\s().$%−-]+)$',line)
    if not m:return []
    return [number(s) for s in re.findall(r'\(?-?\d[\d,]*(?:\.\d+)?\)?|(?<!\S)-(?=\s|$)',m[1])]

def parse_pdf(pages,year,q,url,english=False,comparative=False):
    income=next((t for t in pages if ('consolidatedstatementsofcomprehensiveincome' in re.sub(r'\s+','',t).lower() or '合併綜合損益表' in re.sub(r'\s+','',t)) and ('operating income' in t.lower() or '營業利益' in t or '營業淨利' in t)),None)
    cash=next((t for t in pages if ('statementsofcashflow' in re.sub(r'\s+','',t).lower() or '合併現金流量表' in t) and ('acquisition of property, plant and equipment' in t.lower() or '取得不動產' in t)),None)
    if not income or not cash:raise ValueError('Consolidated statement pages not found')
    if not any(s in income.lower() for s in ('新台幣仟元','新台幣千元','thousands of new taiwan dollars')):raise ValueError('PDF unit mismatch')
    fields={};lines=income.splitlines();n=8 if q in (2,3) else 4
    for i,line in enumerate(lines):
        metric='profit' if (re.match(r'\s*(?:Net )?Operating income',line,re.I) or re.match(r'\s*(?:6900\s+)?營業(?:利益|淨利)',line)) else 'revenue' if re.match(r'\s*(?:4000\s+營業收入|營業收入淨額)',line) else None
        if english and re.search(r'Operating revenues\b',line,re.I):
            for following in lines[i+1:]:
                if re.search(r'(?:Operating cost|Cost of|Costs of)',following,re.I):break
                if re.fullmatch(r'[\d,\s().$%-]+',following) and len(numeric_tail(following))==n:
                    metric='revenue';line=following
        if english and ('Net sales revenue' in line or 'Sales revenue' in line):
            # The unlabeled next row is the issuer's total of engineering + goods.
            following=lines[i+1] if i+1<len(lines) else ''
            values=numeric_tail(following)
            if len(values)==n:metric='revenue';line=following
        if not metric:continue
        values=numeric_tail(line)
        if not values:continue
        if len(values)!=n:raise ValueError(f'Income column count changed: {metric} {values}')
        offset=2 if comparative else 0
        fields[metric]=dict(value=values[offset]/1000 if q<4 else None,ytd=values[(4 if q in (2,3) else 0)+offset]/1000,account_name='Consolidated operating revenue' if metric=='revenue' else 'Consolidated operating income',comparative=comparative)
    for line in cash.splitlines():
        if 'acquisition of property, plant and equipment' not in line.lower() and '取得不動產' not in line:continue
        values=numeric_tail(line)
        if len(values)!=2 or values[0] is not None and values[0]>0:raise ValueError('PP&E cash columns/sign changed')
        fields['capex']=dict(value=None,ytd=-(values[1 if comparative else 0] or 0)/1000,account_name='Cash acquisition of property, plant and equipment',comparative=comparative)
    if len(fields)!=3:raise ValueError('Incomplete statement metrics: '+str(fields.keys()))
    year-=bool(comparative)
    for field in fields.values():field.update(url=url,start=f'{year}-01-01',end=end(year,q))
    return dict(year=year,quarter=q,date=end(year,q),fields=fields)

def collect_issuer(key,old,full=False):
    reports={(r['year'],r['quarter']):r for r in old.get('reports',[])};links=[];asof=today()
    if key=='uis':
        url='https://www.uisco.com.tw/ConsolidatedFinance.htm';r=requests.get(url,timeout=30);r.raise_for_status();r.encoding=r.apparent_encoding
        for a in BeautifulSoup(r.text,'html.parser').select('a[href]'):
            m=re.fullmatch(r'(\d{3})-(\d).pdf',a['href'])
            if m and int(m[1])+1911>=2025:links.append((int(m[1])+1911,int(m[2]),urljoin(url,a['href'])))
    elif key=='lk':
        url='https://www.lkeng.com.tw/tw/finance/report';r=requests.get(url,timeout=30);r.raise_for_status()
        for a in BeautifulSoup(r.content,'html.parser').select('a[href]'):
            m=re.search(r'QuartRP(20\d\d)(?:0([1-4])|(A))\.pdf$',a['href'])
            if m:links.append((int(m[1]),int(m[2] or 4),urljoin(url,a['href'])))
    else:
        for year in range(2014 if full or not reports else int(asof[:4])-1,int(asof[:4])+1):
            u=f'https://www.acter.com.tw/index.php/en/investors/financial-report/report/json?year={year}'
            r=requests.get(u,timeout=30);r.raise_for_status()
            for item in r.json():
                m=re.search(r'Q([1-4]) Consolidated',item['title'])
                if m:links.append((year,int(m[1]),item['link']))
            time.sleep(.2)
    errors=[]
    for year,q,url in sorted(set(links)):
        if end(year,q)>asof:continue
        if reports and not full and year<int(asof[:4])-1:continue
        try:
            cache_key=f'{key}-{year}q{q}'+('-A' if url.endswith('A.pdf') else '')
            pages=pdf(url,cache_key,refresh=year>=int(asof[:4])-1)
            if key=='lk' and q==4 and not any('合併綜合損益表' in re.sub(r'\s+','',p) for p in pages):continue
            reports[year,q]=parse_pdf(pages,year,q,url,key=='acter')
            if year>2014 and (year-1,q) not in reports:
                reports[year-1,q]=parse_pdf(pages,year,q,url,key=='acter',True)
        except Exception as e:errors.append(dict(year=year,quarter=q,error=str(e)));print(key,year,q,type(e).__name__,str(e)[:160],flush=True)
    errors=[e for e in errors if (e['year'],e['quarter']) not in reports]
    result=accounts(list(reports.values()));result.update(checked=asof,fetched=asof,ok=not errors,errors=errors)
    save(IR_CACHE/(key+'-state.json'),result)
    print(key,len(result['rows']),'quarters',len(result['annual']),'years',len(errors),'IR issues',flush=True)
    return result

if __name__=='__main__':
    state=load(ROOT/'data/semicon/cleanroom_global_state.json',dict(companies={}))
    for key in ('uis','lk','acter'):
        old=state['companies'].get(key) or load(CACHE/(key+'-state.json'),{})
        state['companies'][key]=collect_issuer(key,old)
        save(ROOT/'data/semicon/cleanroom_global_state.json',state)

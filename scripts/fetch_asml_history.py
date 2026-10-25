"""Backfill ASML's actual US-GAAP quarters from issuer 6-K exhibits.

The five-quarter tables contain discrete quarters, including discrete cash PP&E
purchases. Never substitute the adjacent YTD/annual tables or divide annuals.
"""
import argparse,datetime as dt,hashlib,re
import requests
from bs4 import BeautifulSoup
from fetch_cpu_companies import ROOT,load,save,today
from equipment_global_sources import observation

CACHE=ROOT/'.cache/equipment/asml'
LABELS={'total net sales':'revenue','income from operations':'profit',
        'purchase of property, plant and equipment':'capex',
        'net system sales':'system','net service and field option sales':'service'}
MONTHS={m:i for i,m in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'),1)}
DATE=re.compile(r'\b(Jan\w*|Feb\w*|Mar\w*|Apr\w*|May|Jun\w*|Jul\w*|Aug\w*|Sep\w*|Oct\w*|Nov\w*|Dec\w*)\s+(\d{1,2}),?(?:\s+(20\d{2}))?')


def merge_history(seed):
    history=load(ROOT/'manual/asml_quarterly_history.json',{})
    rows={(r['year'],r['quarter']):r for r in history['rows']}
    rows.update({(r['year'],r['quarter']):r for r in seed['rows']})
    cohort=dict(seed,rows=sorted(rows.values(),key=lambda r:r['date']))
    cohort['checked']=cohort['fetched']=max(seed['fetched'],history['reviewed'])
    return cohort


def cells(row):
    return [' '.join(c.get_text(' ',strip=True).split()) for c in row.find_all(['td','th'],recursive=False)]


def fiscal_quarter(date):
    d=dt.date.fromisoformat(date)
    candidates=[(dt.date(d.year,m,last),q) for m,last,q in [(3,31,1),(6,30,2),(9,30,3),(12,31,4)]]
    end,q=min(candidates,key=lambda item:abs((d-item[0]).days))
    if abs((d-end).days)>7:raise ValueError('Unexpected ASML fiscal quarter end: '+date)
    return d.year,q


def parse_quarter_tables(html,url,filed):
    soup=BeautifulSoup(html,'html.parser')
    for footnote in soup.select('sup'):footnote.decompose()
    rows={}
    for table in soup.find_all('table'):
        trs=table.find_all('tr',recursive=False)
        if not trs:trs=table.find_all('tr')
        # Other statements have two-quarter + two-YTD columns. Only the
        # five distinct dated columns are an all-quarter statement.
        dates=None
        for i,tr in enumerate(trs[:10]):
            parts=[DATE.search(c) for c in cells(tr)]
            parts=[m for m in parts if m]
            if len(parts)!=5:continue
            if not all(m[3] for m in parts):
                years=[c for c in cells(trs[i+1]) if re.fullmatch(r'20\d{2}',c)]
                if len(years)!=5:raise ValueError('ASML five-quarter years changed')
            else:years=[m[3] for m in parts]
            dates=[f'{int(y):04d}-{MONTHS[m[1][:3]]:02d}-{int(m[2]):02d}' for m,y in zip(parts,years)]
            if len(set(dates))!=5:raise ValueError('ASML repeated quarter dates')
            break
        if dates is None:continue
        text=' '.join(table.get_text(' ',strip=True).split())
        if not re.search(r'in millions\s+(?:EUR|€)',text,re.I):raise ValueError('ASML units changed')
        for tr in trs:
            values=cells(tr)
            if not values:continue
            key=LABELS.get(values[0].lower())
            if not key:continue
            amounts=[]
            for value in values[1:]:
                if re.fullmatch(r'\(?-?\d[\d,]*(?:\.\d+)?\)?',value):
                    sign=-1 if '(' in value or value.startswith('-') else 1
                    amounts.append(sign*float(value.strip('()-').replace(',','')))
                elif value in ('—','–'):amounts.append(0.)
            if len(amounts)!=5:raise ValueError('ASML quarter metric columns changed: '+key)
            for date,value in zip(dates,amounts):
                if date<'2014-01-01':continue
                if date>filed:raise ValueError('Future ASML quarter')
                year,q=fiscal_quarter(date)
                row=rows.setdefault(date,observation(year,q,1,{},url,date=date))
                value=abs(value) if key=='capex' else value
                if key in row and row[key]!=value:raise ValueError('Conflicting ASML table values')
                item=observation(year,q,1,{key:value},url,'공시 5개 분기 비교표 · 개별 분기',date)
                item['refs'][key]['filed']=filed
                item['refs'][key]['components'][0]['filed']=filed
                row[key]=value;row['refs'][key]=item['refs'][key]
    result=sorted(rows.values(),key=lambda row:row['date'])
    if not result or any(any(m not in r for m in ('revenue','profit','capex')) for r in result):
        raise ValueError('ASML complete quarterly statements missing')
    return result


def collect(offline=False):
    sources=load(ROOT/'manual/asml_history_sources.json',[]);rows={};documents=[]
    CACHE.mkdir(parents=True,exist_ok=True)
    for source in sorted(sources,key=lambda s:s['filed']):
        url=source['url']
        if not url.startswith('https://www.sec.gov/Archives/edgar/data/937966/'):raise ValueError('ASML issuer mismatch')
        path=CACHE/(source['id']+'.html')
        if not offline:
            response=requests.get(url,headers={'User-Agent':'industry-dashboard personal research wkorotk@gmail.com'},timeout=40)
            response.raise_for_status();content=response.content
            parsed=parse_quarter_tables(content,url,source['filed'])
            path.write_bytes(content)
        else:
            content=path.read_bytes();parsed=parse_quarter_tables(content,url,source['filed'])
        for row in parsed:rows[row['year'],row['quarter']]=row
        documents.append(dict(source,sha256=hashlib.sha256(content).hexdigest()))
    result=sorted(rows.values(),key=lambda row:row['date'])
    expected={(y,q) for y in range(2014,2025) for q in range(1,5)}|{(2025,1)}
    if not expected<={(r['year'],r['quarter']) for r in result}:raise ValueError('ASML backfill has missing quarters')
    save(ROOT/'manual/asml_quarterly_history.json',dict(reviewed=today(),documents=documents,rows=result))
    print('ASML backfilled',len(result),'quarters',result[0]['date'],'to',result[-1]['date'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true')
    collect(parser.parse_args().offline)

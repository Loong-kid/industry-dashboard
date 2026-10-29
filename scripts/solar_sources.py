"""Solar issuer accounts: actual fiscal periods and SEC earnings exhibits."""
import calendar
import copy
import datetime as dt
import re

from bs4 import BeautifulSoup
from drone_sources import accounts, METRICS, TAGS
from drone_sources import prepare as prepare_subtotal

MONTHS = {name.lower(): i for i in range(1, 13) for name in (calendar.month_name[i], calendar.month_abbr[i])}
DATE = re.compile(r'\b(' + '|'.join(MONTHS) + r')\.?\s+(\d{1,2})\s*,?\s*(20\d{2})\b', re.I)
LABELS = {
    'revenue': re.compile(r'^(?:(?:net|total)\s+)?(?:revenues?|sales)$', re.I),
    'profit': re.compile(r'^(?:(?:income|loss|profit)(?: (?:income|loss|profit))? from operations|operating (?:income|loss|profit)(?: (?:income|loss|profit))?)$', re.I),
}


def make_period(start, end, currency, kind=None):
    n=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days+1
    kind=kind or ('quarter' if 75<=n<=105 else 'annual' if 350<=n<=380 else 'ytd')
    year=int(end[:4]);quarter=(int(end[5:7])+2)//3
    return dict(start=start,date=end,kind=kind,currency=currency,year=year,quarter=quarter if kind=='quarter' else None,
                period=f'FY{year} Q{quarter}' if kind=='quarter' else f'FY{year}' if kind=='annual' else f'{year} 누적',regime='regular',refs={})


def us_accounts(payload, submissions, meta, asof):
    spec=dict(meta, minimum_start='2013-01-01',tags=copy.deepcopy(meta.get('tags',{})))
    spec['tags']['revenue']=spec['tags'].get('revenue',TAGS['revenue']+['SalesRevenueNet'])
    prepared=prepare_subtotal(payload,dict(meta,ticker='RCAT')) if meta['ticker']=='ENPH' else payload
    if meta['ticker']=='SEDG':
        prepared=copy.deepcopy(payload)
        for fact in prepared['facts']['us-gaap'].values():
            for values in fact.get('units',{}).values():
                for f in values:
                    if f.get('form')=='10-KT':f['form']='10-K'
    rows=accounts(prepared,submissions,spec,asof)
    if meta['ticker'] in ('FSLR','SEDG'):
        # Old SalesRevenueNet and modern Revenues are both consolidated sales.
        # A second same-tag pass recovers Q4 without subtracting unlike tags.
        legacy=accounts(prepared,submissions,dict(spec,tags=dict(spec['tags'],revenue=['SalesRevenueNet'])),asof)
        occupied={(r['kind'],r['date']) for r in rows}
        rows.extend(r for r in legacy if (r['kind'],r['date']) not in occupied)
    for r in rows:
        r['currency']='USD'
        if meta['ticker']=='SEDG' and r['kind']=='quarter':
            if r['date']>='2017-01-01':
                r['year']=int(r['date'][:4]);r['quarter']=(int(r['date'][5:7])+2)//3;r['regime']='calendar'
                r['period']=f"FY{r['year']} Q{r['quarter']}"
            elif r['date']>='2016-07-01':
                r['regime']='transition';r['period']='2016 전환기 · '+('1번째' if r['date']<'2016-10-01' else '2번째')+' 3개월'
            else:r['regime']='june'
    if meta['ticker']=='SEDG':
        rows=[r for r in rows if not (r['kind']=='annual' and r['date']=='2016-12-31')]
        transition=annual_accounts(payload,meta,asof,start_end=('2016-07-01','2016-12-31'))
        for r in transition:r.update(kind='transition',period='2016 전환기 · 6개월',regime='transition')
        rows+=transition
    return sorted(rows,key=lambda r:(r['date'],r['kind']))


def annual_accounts(payload,meta,asof,start_end=None):
    if int(payload['cik'])!=meta['cik']:raise ValueError('Issuer mismatch')
    selected={}
    tags={'revenue':TAGS['revenue']+['SalesRevenueNet'],'profit':TAGS['profit'],'netincome':['NetIncomeLoss','NetIncomeLossAttributableToParentDiluted','NetIncomeLossAvailableToCommonStockholdersBasic']}
    for metric,names in tags.items():
        for priority,tag in enumerate(meta.get('tags',{}).get(metric,names)):
            for f in payload['facts']['us-gaap'].get(tag,{}).get('units',{}).get(meta['currency'],[]):
                if not f.get('start') or f['end']<'2014-01-01' or f['end']>asof or f['filed']>asof:continue
                if f['form'] not in ('20-F','20-F/A','6-K','10-K','10-KT','10-K/A'):continue
                n=(dt.date.fromisoformat(f['end'])-dt.date.fromisoformat(f['start'])).days+1
                if start_end:
                    if (f['start'],f['end'])!=start_end:continue
                elif not 350<=n<=380:continue
                rank=(-priority,f['filed'],f['accn']) if metric=='netincome' else (f['filed'],-priority,f['accn'])
                key=metric,f['end'];item=dict(f,tag=tag,rank=rank)
                if key not in selected or rank>selected[key]['rank']:selected[key]=item
    result={}
    for (metric,end),f in selected.items():
        row=result.setdefault(end,make_period(f['start'],end,meta['currency'],'annual'))
        row[metric]=f['val']/1e6;acc=f['accn']
        ref=dict(url=f'https://www.sec.gov/Archives/edgar/data/{meta["cik"]}/{acc.replace("-","")}/{acc}-index.html',filed=f['filed'],start=f['start'],end=end,tag='us-gaap:'+f['tag'],calculation='reported six-month transition' if start_end else 'reported annual')
        row['refs'][metric]=dict(ref,components=[dict(ref)])
    return sorted((r for r in result.values() if 'revenue' in r),key=lambda r:r['date'])


def expand(tr):
    result=[]
    for cell in tr.find_all(['td','th'],recursive=False):
        text=' '.join(cell.get_text(' ',strip=True).split()).replace('\xa0',' ')
        result.extend([text]*int(cell.get('colspan',1)))
    return result


def number(text):
    text=text.replace(',','').replace('−','-').strip()
    if text in ('—','–','-'):return 0.0
    if not re.fullmatch(r'\(?[-+]?\d+(?:\.\d+)?\)?',text):return None
    return -float(text.strip('()')) if text.startswith('(') else float(text.strip(')'))


def release_rows(raw, meta, url, filed, asof):
    """Read GAAP consolidated tables only; dates/currencies follow physical columns.

    Colspans preserve the association between USD convenience translations and
    original RMB columns. Unknown headers fail closed rather than guessing.
    """
    if filed>asof:return []
    soup=BeautifulSoup(raw,'html.parser');results=[]
    owner=meta['owner_match'].lower()
    for table_index,table in enumerate(soup.find_all('table')):
        trs=table.find_all('tr',recursive=False) or (table.find('tbody').find_all('tr',recursive=False) if table.find('tbody') else [])
        grid=[expand(tr) for tr in trs]
        if len(grid)<20:continue
        labels=[next((v for v in row if v),'') for row in grid]
        candidates={m:[i for i,label in enumerate(labels) if pattern.fullmatch(' '.join(re.sub(r'[^a-z ]',' ',label.lower()).split()))] for m,pattern in LABELS.items()}
        candidates['netincome']=[i for i,l in enumerate(labels) if l.lower().startswith('net ') and 'attributable to' in l.lower() and owner in l.lower() and not any(t in l.lower() for t in ('per ads','per share','diluted','basic','comprehensive'))]
        if not all(len(v)==1 for v in candidates.values()):continue
        revenue_index=candidates['revenue'][0];header=grid[:revenue_index]
        if not header:continue
        numeric=[i for i,t in enumerate(grid[revenue_index]) if i>0 and number(t) is not None]
        if not numeric:continue
        groups=[]
        for row in header:
            pos=0
            while pos<len(row):
                end=pos+1
                while end<len(row) and row[end]==row[pos]:end+=1
                text=row[pos].lower()
                if re.search(r'(?:three|six|nine|twelve)\s+months|quarter\s+ended|year\s+ended|years\s+ended',text):groups.append(((pos+end-1)/2,text))
                pos=end
        if not groups:continue
        columns=[]
        for col in numeric:
            text=' '.join(row[col] if col<len(row) else '' for row in header)
            # A year and month/day may be on separate header rows.
            hit=DATE.search(text)
            if not hit:continue
            month=MONTHS[hit[1].lower()];day=int(hit[2]);year=int(hit[3]);end=dt.date(year,month,day).isoformat()
            if end<'2014-01-01' or end>asof:continue
            currency='CNY' if 'rmb' in text.lower() else 'USD' if 'usd' in text.lower() or 'us$' in text.lower() else meta['currency']
            if currency!=meta['currency']:continue
            group=min(groups,key=lambda g:abs(g[0]-col))[1]
            months=12 if 'year' in group or 'twelve' in group else 9 if 'nine' in group else 6 if 'six' in group else 3
            if month-months+1<1:continue
            start=dt.date(year,month-months+1,1).isoformat()
            columns.append((col,start,end))
        for col,start,end in columns:
            row=make_period(start,end,meta['currency'])
            for metric,indices in candidates.items():
                cells=grid[indices[0]]
                value=number(cells[col]) if col<len(cells) else None
                if value is None:break
                if col and cells[col-1]=='(':value=-abs(value)
                if metric=='revenue' and value<0:raise ValueError('Negative revenue in statement')
                row[metric]=value/1000
                ref=dict(url=url,filed=filed,start=start,end=end,tag=labels[indices[0]],table=table_index,calculation='reported '+row['kind'])
                row['refs'][metric]=dict(ref,components=[dict(ref)])
            if all(m in row for m in METRICS):results.append(row)
    return results


def merge_rows(*cohorts):
    result={}
    for group in cohorts:
        for r in group:
            key=r['kind'],r['date'];target=result.setdefault(key,dict(r,refs=dict(r['refs'])))
            if target['currency']!=r['currency'] or target['start']!=r['start']:raise ValueError('Period/currency mismatch')
            for m in METRICS:
                if m in r and r['refs'][m]['filed']>=target['refs'].get(m,{}).get('filed',''):
                    target[m]=r[m];target['refs'][m]=r['refs'][m]
    return sorted(result.values(),key=lambda r:(r['date'],r['kind']))

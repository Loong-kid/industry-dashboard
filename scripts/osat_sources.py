"""ASE's original SEC earnings tables: actual quarters and separately defined cash flows."""
import copy,datetime as dt,re,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from fetch_cpu_companies import load,save,parse_annual

MONTHS={name:i for i,names in enumerate([['Jan','January'],['Feb','February'],['Mar','March'],['Apr','April'],['May'],['Jun','June'],['Jul','July'],['Aug','August'],['Sep','Sept','September'],['Oct','October'],['Nov','November'],['Dec','December']],1) for name in names}

def text(value):return re.sub(r'\s+',' ',value).strip()
def number(value):
    value=value.strip().replace(',','').replace('$','').strip()
    if not re.fullmatch(r'\(?-?\d+(?:\.\d+)?\)?',value):return None
    return -float(value[1:-1]) if value.startswith('(') else float(value)

def parse_ase_release(raw,filing):
    soup=BeautifulSoup(raw,'html.parser');body=soup.get_text(' ',strip=True)
    if not re.search(r'ASE\s+Technology\s+Holding',body,re.I):return []
    tables=[]
    for table in soup.find_all('table'):
        rows=[]
        for tr in table.find_all('tr'):
            if tr.find_parent('table') is not table:continue
            cells=[text(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
            cells=[c for c in cells if c and c not in ['$','NT$','US$']]
            if cells:rows.append(cells)
        label=' '.join(' '.join(r) for r in rows)
        if re.search('Total net revenues',label,re.I) and re.search('Operating income',label,re.I):
            caption=' '.join(p.get_text(' ',strip=True) for p in table.find_all_previous('p',limit=6))
            if not re.search(r'NT\$\s*million',caption,re.I):continue
            tables.append((rows,label))
    if not tables:return []
    rows,label=tables[0]
    if not re.search(r'(three|3)\s+months|quarter',label,re.I):return []
    header=' '.join(' '.join(r) for r in rows[:4])
    matches=re.findall(r'\b([A-Z][a-z]+)\.?\s+(\d{1,2})\s*,?\s*(20\d{2})',header)
    dates=[]
    for month,day,year in matches:
        if month not in MONTHS:continue
        date=dt.date(int(year),MONTHS[month],int(day)).isoformat()
        if MONTHS[month] in [3,6,9,12] and date not in dates:dates.append(date)
    if len(dates)<3:return []
    # Published tables give current quarter, prior quarter, and year-ago quarter.
    dates=dates[:3]
    if dates[0]<=dates[1] or dates[0][:4]!=filing['filed'][:4] and dates[0][5:7]!='12':return []
    result={date:dict(date=date,year=int(date[:4]),quarter=(int(date[5:7])-1)//3+1,refs={}) for date in dates}
    source=dict(url=filing['url'],filed=filing['filed'],accn=filing['accn'],basis='ASEH consolidated earnings release; TWD million')
    for r in rows:
        key='revenue' if re.fullmatch('Total net revenues',r[0],re.I) else 'profit' if re.fullmatch(r'Operating income(?:\s*\(loss\))?',r[0],re.I) else None
        if not key:continue
        values=[v for c in r[1:] if (v:=number(c)) is not None]
        if len(values)<3:raise ValueError('Incomplete ASE income columns')
        for date,value in zip(dates,values):
            if key=='revenue' and value<0:raise ValueError('Negative ASE revenue')
            result[date][key]=value;result[date]['refs'][key]=dict(source,start=date[:4]+'-'+str((result[date]['quarter']-1)*3+1).zfill(2)+'-01',end=date,tag=r[0],components=[dict(source,start=date[:4]+'-'+str((result[date]['quarter']-1)*3+1).zfill(2)+'-01',end=date)],calculation='reported three-month earnings release')
    # Earnings-release PPE cash flow is NET payments, whereas 20-F reports
    # GROSS purchases. Keep this distinct, never combine for a cash CAPEX series.
    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            cells=[text(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
            cells=[c for c in cells if c and c not in ['$','NT$','US$']]
            if cells and re.fullmatch(r'Net payments for property,? plant and equipment',cells[0],re.I):
                vals=[v for c in cells[1:] if (v:=number(c)) is not None]
                if len(vals)<3:continue
                for date,value in zip(dates,vals):
                    if value>0:raise ValueError('Unexpected net PPE payment sign')
                    result[date]['net_ppe_cash']=-value
                    result[date]['refs']['net_ppe_cash']=dict(source,start=date[:4]+'-'+str((result[date]['quarter']-1)*3+1).zfill(2)+'-01',end=date,tag=cells[0],components=[dict(source,start=date[:4]+'-'+str((result[date]['quarter']-1)*3+1).zfill(2)+'-01',end=date)],calculation='reported three-month NET PPE payments; not gross purchases')
                break
    return [r for r in result.values() if 'revenue' in r and 'profit' in r and r['date']>= '2018-01-01' and r['date']<=filing['filed']]


def ase_annual(payload,spec,asof):
    adapted=dict(payload,facts={'us-gaap':{}})
    mapping={'revenue':'Revenue','profit':'ProfitLossFromOperatingActivities','capex':'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'}
    for metric,tag in mapping.items():
        field=copy.deepcopy(payload['facts']['ifrs-full'][tag])
        for facts in field['units'].values():
            for f in facts:f['source_tag']='ifrs-full:'+tag
        adapted['facts']['us-gaap'][tag]=field
    cfg=dict(spec,tags={k:[v] for k,v in mapping.items()})
    return [r for r in parse_annual(adapted,cfg,asof) if r['date']>='2018-12-31']


def collect_ase_releases(cache,full=False):
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    response=session.get('https://data.sec.gov/submissions/CIK0001122411.json',timeout=45);response.raise_for_status();d=response.json()
    if int(d['cik'])!=1122411:raise ValueError('ASE issuer mismatch')
    filings=d['filings']['recent'];candidates=[]
    for i,form in enumerate(filings['form']):
        filed=filings['filingDate'][i];month=int(filed[5:7]);day=int(filed[8:10])
        if form!='6-K' or filed<('2018-01-01' if full else str(dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).year-1)+'-01-01'):continue
        if not (month in [1,4,7,10] and day>=18 or month in [2,5,8,11] and day<=10):continue
        accn=filings['accessionNumber'][i];doc=filings['primaryDocument'][i]
        candidates.append(dict(filed=filed,accn=accn,document=doc,url=f'https://www.sec.gov/Archives/edgar/data/1122411/{accn.replace("-","")}/{doc}'))
    directory=cache/'ase-releases';directory.mkdir(parents=True,exist_ok=True)
    def original(entry):
        path=directory/(entry['accn']+'.html')
        if not path.exists():
            own=requests.Session();own.headers.update(session.headers);r=own.get(entry['url'],timeout=40);r.raise_for_status();path.write_bytes(r.content);time.sleep(.4)
        return dict(entry,path='ase-releases/'+path.name)
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(original,candidates))
    save(cache/'ase-releases.json',rows)
    print('ASE archived',len(rows),'candidate original filings',flush=True)
    return rows

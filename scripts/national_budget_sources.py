"""Public national-budget sources. Preserve scope, units, and forecast vintages."""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import time
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/national-budget'
KR_BASE='https://www.openfiscaldata.go.kr'
GRID='/op/fa/sm/service/preview/rowSheet/gridDataLoad.do'
KR_ODT='5Y5A50K2L4CW2IRKI2J0F2C8T'
KR_SOURCE=KR_BASE+'/op/ko/sd/UOPKOSDA01?odtId='+KR_ODT
OMB_BASE='https://www.whitehouse.gov/omb/information-resources/budget/'
CBO_BASE='https://raw.githubusercontent.com/US-CBO/cbo-data/main/'
FUNCTIONS={
 '050':('국방','National Defense'),'150':('국제관계','International Affairs'),
 '250':('과학·우주·기술','General Science, Space, and Technology'),'270':('에너지','Energy'),
 '300':('자연자원·환경','Natural Resources and Environment'),'350':('농업','Agriculture'),
 '370':('상업·주택금융','Commerce and Housing Credit'),'400':('교통','Transportation'),
 '450':('지역개발','Community and Regional Development'),'500':('교육·훈련·고용·사회서비스','Education, Training, Employment, and Social Services'),
 '550':('보건','Health'),'570':('메디케어','Medicare'),'600':('소득보장','Income Security'),
 '650':('사회보장','Social Security'),'700':('보훈','Veterans Benefits and Services'),
 '750':('사법','Administration of Justice'),'800':('일반정부','General Government'),
 '900':('순이자','Net Interest'),'920':('예비조정','Allowances'),'950':('미배분 상계수입','Undistributed Offsetting Receipts')}

def today():return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
def number(value):
    if value is None or str(value).strip().lower() in ('','null','nan','na'):return None
    val=float(str(value).replace(',',''))
    if not math.isfinite(val):raise ValueError('Nonfinite source value')
    return val
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf8');tmp.replace(path)
def load(path,default=None):return json.loads(path.read_text(encoding='utf8')) if path.exists() else default

class Client:
    def __init__(self,offline=False,refresh=False):
        self.offline=offline;self.refresh=refresh;self.session=requests.Session();self.session.headers['User-Agent']='Mozilla/5.0 (Industry Dashboard public budget research)';CACHE.mkdir(parents=True,exist_ok=True)
    def get(self,name,url,params=None,body=None,refresh=False):
        path=CACHE/name
        if path.exists() and (self.offline or not (refresh or self.refresh)):return path.read_bytes()
        if self.offline:raise FileNotFoundError(name)
        for attempt in range(2):
            try:
                r=self.session.post(url,json=body,timeout=80) if body is not None else self.session.get(url,params=params,timeout=80)
                r.raise_for_status()
                if '/error.html' in r.url:raise ValueError('Public source returned an error page')
                content=r.content
                if name.endswith('.json'):json.loads(content)
                if name.endswith('.xlsx') and not content.startswith(b'PK'):raise ValueError('Not an XLSX file')
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content);time.sleep(.12);return content
            except (requests.RequestException,ValueError):
                if attempt:raise
                time.sleep(1)
    def json(self,*args,**kwargs):return json.loads(self.get(*args,**kwargs))

def kr_grid(client,year):
    """The same anonymous public JSON download used by the official Sheet UI."""
    args=dict(odtId=KR_ODT,rlsSvTyCd='S',odtSvSeq='1',dsId='VW_OPFI940',
        pageIndex='1',pageSize='10000',selectWon='1000',decimalPointLevel='0',traDataFextNm='DATA',
        BDG_FND_DIV_CD='0',ANEXP_INQ_STND_CD='1',FSCL_YY=str(year))
    rows=[];page=1
    while True:
        args['pageIndex']=str(page)
        batch=client.json(f'kr-budget-{year}-{page}.json',KR_BASE+GRID,body=args,refresh=year>=int(today()[:4])-1)
        if isinstance(batch,list) and not batch and year>int(today()[:4]):return []
        if not isinstance(batch,list) or not batch:raise ValueError('Empty Korean budget cohort')
        count=int(batch[0]['PAGE_TOT_CNT']);rows.extend(batch)
        if len(rows)>=count:break
        page+=1
        if page>20:raise ValueError('Unexpected Korean pagination')
    if len(rows)!=count or len({r['PAGE_ROW_NUM'] for r in rows})!=count:raise ValueError('Incomplete Korean public download')
    if any(str(r['FSCL_YY'])!=str(year) for r in rows):raise ValueError('Korean fiscal year mismatch')
    return rows

def kr_accounts(rows):
    result=[]
    for row in rows:
        if row.get('FIN_DE_EP_NM')!='일반지출':raise ValueError('Unexpected gross/internal transaction in total-expenditure source')
        labels=[row.get(k,'') or '' for k in ('OFFC_NM','FSCL_NM','ACCT_NM','FLD_NM','SECT_NM','PGM_NM','ACTV_NM','SACTV_NM','BZ_CLS_NM')]
        if labels[3]=='외교·통일':labels[3]='통일·외교'
        approved=number(row.get('Y_YY_DFN_MEDI_KCUR_AMT'))
        proposal=number(row.get('Y_YY_MEDI_KCUR_AMT'))
        if approved is None or proposal is None:raise ValueError('Missing Korean budget amount')
        key=hashlib.sha256('\x1f'.join(labels).encode()).hexdigest()[:20]
        result.append(dict(id=key,year=int(row['FSCL_YY']),sector=labels[3],agency=labels[0],
            account=labels[1]+(' / '+labels[2] if labels[2] else ''),program=labels[5],name=labels[7],
            approved=approved/1e9,proposal=proposal/1e9))
    return result

def omb_files(client):
    html=client.get('omb-supplemental.html',OMB_BASE+'supplemental-materials/',refresh=True).decode('utf8')
    soup=BeautifulSoup(html,'html.parser');files={}
    for a in soup.select('a[href]'):
        url=a['href'];m=re.search(r'/(budauth|outlays)_fy(20\d{2})\.xlsx',url)
        if m:files[m[1]]=dict(url=url,fy=int(m[2]))
    if set(files)!={'budauth','outlays'} or files['budauth']['fy']!=files['outlays']['fy']:raise ValueError('OMB dataset edition mismatch')
    return files

def parse_omb(content,metric):
    with io.BytesIO(content) as stream:
        workbook=load_workbook(stream,read_only=True,data_only=True);sheet=workbook.worksheets[0]
        sheet.reset_dimensions();iterator=sheet.iter_rows(values_only=True);headers=[str(v).strip() for v in next(iterator)]
        required=['Agency Code','Agency Name','Bureau Code','Bureau Name','Account Code','Account Name','Subfunction Code','BEA Category']
        if any(k not in headers for k in required):raise ValueError('OMB header changed')
        columns={h:i for i,h in enumerate(headers)};years={int(h):i for i,h in enumerate(headers) if re.fullmatch(r'20\d{2}',h) and int(h)>=2014}
        result=[]
        for raw in iterator:
            if len(raw)<len(headers):raw=(*raw,*([None]*(len(headers)-len(raw))))
            if not raw[columns['Agency Name']]:continue
            text=lambda k:str(raw[columns[k]] or '').strip()
            sub=text('Subfunction Code').zfill(3);major=sub[0]+'00' if sub[0]!='0' else '050'
            if sub.startswith('92'):major='920'
            if sub.startswith('95'):major='950'
            if sub.startswith('15'):major='150'
            if sub.startswith('25'):major='250'
            if sub.startswith('27'):major='270'
            if sub.startswith('35'):major='350'
            if sub.startswith('37'):major='370'
            if sub.startswith('45'):major='450'
            if sub.startswith('55'):major='550'
            if sub.startswith('57'):major='570'
            if sub.startswith('65'):major='650'
            if sub.startswith('75'):major='750'
            if major not in FUNCTIONS:raise ValueError('Unknown OMB budget function: '+sub)
            vals={str(y):round(number(raw[i])/1e6,9) for y,i in years.items() if number(raw[i]) is not None}
            identity=[text(k) for k in ['Agency Code','Bureau Code','Account Code','Account Name','Subfunction Code','BEA Category','On- or Off- Budget'] if k in columns]
            # Outlay database separately identifies grant/nongrant portions.
            if 'Grant/non-grant split' in columns:identity.append(text('Grant/non-grant split'))
            key=hashlib.sha256('\x1f'.join(identity).encode()).hexdigest()[:20]
            result.append(dict(id=key,sector=major,subfunction=sub,agency=text('Agency Name'),bureau=text('Bureau Name'),name=text('Account Name'),category=text('BEA Category'),values=vals))
        workbook.close()
    if len(result)<1000:raise ValueError('OMB accounts truncated')
    return result,sorted(years)

def aggregate_accounts(rows):
    totals=defaultdict(float);sectors=defaultdict(lambda:defaultdict(float))
    for row in rows:
        for year,value in row['values'].items():totals[year]+=value;sectors[row['sector']][year]+=value
    return ({y:round(v,6) for y,v in totals.items()},
        {key:{y:round(v,6) for y,v in values.items()} for key,values in sectors.items()})

def parse_mts(rows):
    head=next(r for r in rows if r['classification_desc']=='Net Outlays' and r['parent_id']=='null')
    income=next(r for r in rows if r['classification_desc']=='Receipts' and r['parent_id']=='null')
    sectors={};totals={}
    clean=lambda v:re.sub('[^a-z]','',v.lower())
    names={clean(en):code for code,(_,en) in FUNCTIONS.items()}
    for r in rows:
        val=number(r['current_fytd_rcpt_outly_amt'])
        if val is None:continue
        if r['parent_id']==head['classification_id']:
            if r['classification_desc']=='Total':totals['spending']=val/1e9
            elif clean(r['classification_desc']) in names:sectors[names[clean(r['classification_desc'])]]=val/1e9
            else:raise ValueError('Unknown Treasury function '+r['classification_desc'])
        if r['parent_id']==income['classification_id'] and r['classification_desc']=='Total':totals['revenue']=val/1e9
    if len(sectors)<18 or 'spending' not in totals or abs(sum(sectors.values())-totals['spending'])>.005:raise ValueError('Treasury function reconciliation failed')
    totals['balance']=totals['revenue']-totals['spending']
    return totals,sectors

CBO_FIELDS={'spending':'proj_outlays_total','revenue':'proj_rev_total',
 'balance':'proj_deficit_total','interest':'proj_outlays_net_interest',
 'debt':'proj_debt_held_by_public','debt_gdp':'proj_debt_held_by_public_gdp_share'}

def cbo_vintages(client):
    catalog=client.json('cbo-catalog.json',CBO_BASE+'catalog.json',refresh=True)
    dataset=next(d for d in catalog['datasets'] if d['identifier']=='ten_year_budget')
    schema=client.json('cbo-schema.json',CBO_BASE+dataset['schema_path'],refresh=True)
    # Canonical field names are checked rather than guessed from sheet positions.
    result=[]
    for distribution in sorted(dataset['distribution'],key=lambda d:d['vintage']):
        vintage=distribution['vintage']
        if vintage>today()[:7]:continue
        content=client.get('cbo-'+vintage+'.csv',CBO_BASE+distribution['downloadURL'])
        rows=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))));series={}
        for metric,field in CBO_FIELDS.items():
            if field not in schema['fields']:continue
            vals={str(int(r['date'][2:])):number(r['value']) for r in rows if r['variable']==field and re.fullmatch(r'FY20\d{2}',r['date']) and int(r['date'][2:])>=2014}
            if vals:series[metric]=vals
        if not all(k in series for k in ('spending','revenue','balance')):raise ValueError('CBO headline fields unavailable')
        result.append(dict(id=vintage,label=vintage+' CBO 기준선',publication_date=vintage,
            source_url='https://www.cbo.gov/data/budget-economic-data',series=series))
    if not result:raise ValueError('No CBO forecast vintages')
    return result

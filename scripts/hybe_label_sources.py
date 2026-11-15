"""HYBE public DART notes: legal-entity revenue, not artist revenue allocations."""
import hashlib,json,re,time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/hybe-labels'

def load(path,default=None):return json.loads(path.read_text(encoding='utf8')) if path.exists() else default
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf8');tmp.replace(path)
def compact(text):return re.sub(r'\s+','',text or '')
def entity_key(text):
    text=re.sub(r'\(주\d+\)|\(주\)|㈜|주식회사|\(유\)|유한회사','',text,flags=re.I)
    return re.sub(r'[^\w가-힣]','',text).lower()
def amount(text):
    text=compact(text).replace(',','').replace('−','-')
    if text in ('','-','—','–'):return None
    if re.fullmatch(r'\([\d.]+\)',text):text='-'+text[1:-1]
    if not re.fullmatch(r'-?\d+(?:\.\d+)?',text):raise ValueError('Unexpected financial amount')
    return float(text)

class Client:
    def __init__(self,offline=False,refresh=False):self.offline=offline;self.refresh=refresh;self.session=requests.Session();self.session.headers['User-Agent']='Mozilla/5.0';CACHE.mkdir(parents=True,exist_ok=True)
    def get(self,name,url,params=None,refresh=False):
        path=CACHE/name
        if path.exists() and (self.offline or not (self.refresh or refresh)):return path.read_text(encoding='utf8')
        if self.offline:raise FileNotFoundError(name)
        for attempt in range(2):
            try:
                r=self.session.get(url,params=params,timeout=(10,50));r.raise_for_status();r.encoding='utf-8'
                if '요청하신 문서를 찾을 수 없습니다' in r.text:raise ValueError('DART report unavailable')
                path.write_text(r.text,encoding='utf8');time.sleep(.15);return r.text
            except requests.RequestException:
                if attempt:raise ValueError('DART public report download failed') from None
                time.sleep(1)

def nodes(html):
    result=[]
    pattern=r"(node\d+)\['text'\]\s*=\s*\"([^\"]+)\";(.*?)(?=\bnode\d+\['text'\]|$)"
    for match in re.finditer(pattern,html,re.S):
        fields=dict(re.findall(r"\['(\w+)'\]\s*=\s*\"([^\"]*)\"",match[3]))
        if all(k in fields for k in ['rcpNo','dcmNo','eleId','offset','length','dtd']):result.append(dict(name=match[2],**fields))
    if not result:raise ValueError('DART document tree changed')
    return result

def section(client,receipt,kind,refresh=False):
    main=client.get(f'main-{receipt}.html','https://dart.fss.or.kr/dsaf001/main.do',{'rcpNo':receipt},refresh)
    if '하이브' not in main and '빅히트' not in main:raise ValueError('DART HYBE issuer mismatch')
    tree=nodes(main)
    if kind=='notes':
        matching=[n for n in tree if '연결회사의개요' in compact(n['name']) or ('일반사항' in n['name'] and '연결' in n['name'])]
        if not matching:matching=[n for n in tree if '연결재무제표주석' in compact(n['name'])]
    else:matching=[n for n in tree if '주요계약' in n['name']]
    if not matching:raise ValueError('HYBE note section unavailable: '+kind)
    n=matching[0];params={k:n[k] for k in ['rcpNo','dcmNo','eleId','offset','length','dtd']}
    url='https://dart.fss.or.kr/report/viewer.do'
    return client.get(f'{kind}-{receipt}.html',url,params,refresh),requests.Request('GET',url,params=params).prepare().url

def grid(table):
    """Expand rowspan/colspan so artists keep their actual label and group."""
    cells={};result=[]
    for y,tr in enumerate(table.find_all('tr')):
        x=0
        for cell in tr.find_all(['td','th'],recursive=False):
            while (y,x) in cells:x+=1
            value=cell.get_text(' ',strip=True);rs=int(cell.get('rowspan',1));cs=int(cell.get('colspan',1))
            for dy in range(rs):
                for dx in range(cs):cells[y+dy,x+dx]=value
            x+=cs
        if any(row==y for row,_ in cells):result.append([cells.get((y,col),'') for col in range(max(col for row,col in cells if row==y)+1)])
    return result

def financial_tables(html):
    soup=BeautifulSoup(html,'html.parser');tables=[]
    for table in soup.select('table'):
        if table.find('table'):continue
        text=compact(table.get_text(' ',strip=True))
        if '매출액' not in text or '자산총액' not in text or not any(x in text for x in ['순손익','순이익']):continue
        rows=grid(table);header=next((r for r in rows if any(compact(c)=='매출액' for c in r)),None)
        if not header:continue
        # A prose-containing outer table must not duplicate its leaf tables.
        if not any(any('빅히트뮤직' in c or '플레디스' in c or '쏘스뮤직' in c for c in r[:2]) for r in rows):continue
        unit=re.search(r'단위\s*[:：]\s*(천원|백만원|원)',table.get_text(' ',strip=True))
        if not unit:
            for before in list(table.previous_siblings)[::-1][:8]:
                unit=re.search(r'단위\s*[:：]\s*(천원|백만원|원)',before.get_text(' ',strip=True) if hasattr(before,'get_text') else str(before))
                if unit:break
        if not unit:
            previous=table.find_previous(string=re.compile(r'단위\s*[:：]\s*(천원|백만원|원)'))
            if previous:unit=re.search(r'단위\s*[:：]\s*(천원|백만원|원)',previous)
        if not unit:raise ValueError('HYBE subsidiary statement unit not explicit')
        scale={'천원':.001,'백만원':1,'원':.000001}[unit[1]]
        columns={}
        for metric,names in {'revenue':['매출액'],'net_income':['당기순손익','반기순손익','분기순손익','당기순이익','당반기순손익','당분기순손익'],'assets':['자산총액'],'liabilities':['부채총액']}.items():
            index=next((i for i,c in enumerate(header) if compact(c) in names),None)
            if index is None:raise ValueError('HYBE subsidiary financial column changed: '+metric)
            columns[metric]=index
        name_index=columns['assets']-1
        records=[]
        for row in rows:
            if len(row)<=max(columns.values()) or row==header or not row[0]:continue
            if any(x in compact(row[0]) for x in ['단위:','구분','회사명']):continue
            try:values={m:None if (n:=amount(row[i])) is None else round(n*scale,6) for m,i in columns.items()}
            except ValueError:continue
            records.append(dict(name=row[name_index],**values))
        if records:tables.append(records)
    if not tables:raise ValueError('HYBE subsidiary financial table unavailable')
    return tables

def ownership(html):
    result={}
    for table in BeautifulSoup(html,'html.parser').select('table'):
        if table.find('table') or '소유지분율' not in compact(table.get_text()):continue
        for row in grid(table):
            if len(row)>=6:
                try:value=amount(row[-2])
                except ValueError:continue
                if value is not None and 0<=value<=100:result[entity_key(row[max(0,len(row)-6)])]=value
    return result

def roster(html):
    groups={}
    for table in BeautifulSoup(html,'html.parser').select('table'):
        if table.find('table'):continue
        text=compact(table.get_text())
        if not all(x in text for x in ['회사명','그룹','아티스트']):continue
        for row in grid(table):
            if len(row)!=3 or '회사명' in compact(row[0]) or '아티스트' in compact(row[2]):continue
            company,name,artist=row
            if not company or not name:continue
            key=(entity_key(company),compact(name));item=groups.setdefault(key,dict(company=company,name=name,members=[]))
            if artist not in item['members']:item['members'].append(artist)
    if len(groups)<8:raise ValueError('HYBE exclusive-contract roster changed')
    return list(groups.values())

def filings(state):
    result={}
    for row in state['companies']['hybe']['annual']+state['companies']['hybe']['rows']:
        if row.get('provisional'):continue
        ref=row['refs']['revenue'];match=re.search(r'rcpNo=(\d{14})',ref['url'])
        if not match:continue
        year=row['year'];q=row.get('quarter',4)
        report=dict(receipt=match[1],year=year,quarter=q,date=row['date'],filed=ref.get('filed',match[1][:4]+'-'+match[1][4:6]+'-'+match[1][6:8]))
        key=(year,q)
        if key not in result or report['receipt']>result[key]['receipt']:result[key]=report
    return sorted(result.values(),key=lambda r:(r['year'],r['quarter']))

def annual_and_quarters(observations):
    actual={}
    for row in observations:
        key=(row['entity'],row['year'],row['quarter'])
        priority=(not row.get('comparative',False),row['filed'])
        if key not in actual or priority>actual[key][0]:actual[key]=(priority,row)
    cumulative=[v[1] for v in actual.values()];quarterly=[]
    for row in cumulative:
        q=row['quarter'];prior=actual.get((row['entity'],row['year'],q-1))
        if q>1 and not prior:continue
        prior=prior[1] if prior else None
        result=dict(row)
        for metric in ['revenue','net_income']:
            v=row[metric];previous=prior[metric] if prior else 0
            result[metric]=None if v is None or previous is None else round(v-previous,6)
        if result['revenue'] is not None and result['revenue']<-.001:continue
        result['calculation']='reported Q1 cumulative' if q==1 else 'same-entity YTD minus previous YTD'
        result['components']=[r['source_url'] for r in [row,prior] if r]
        quarterly.append(result)
    return dict(cumulative=sorted(cumulative,key=lambda r:(r['date'],r['entity'])),annual=[r for r in cumulative if r['quarter']==4],quarter=sorted(quarterly,key=lambda r:(r['date'],r['entity'])))

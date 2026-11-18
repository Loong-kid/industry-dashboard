"""Track forward CAPEX statements by announcement vintage, never cash actuals."""
import argparse,copy,datetime as dt,json,math,re
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from sec_earnings import earnings_exhibits,sec_get

ROOT=Path(__file__).resolve().parents[1]
MANUAL=ROOT/'manual/mocvd-capex-guidance.json'
STATE=ROOT/'data/semicon/mocvd_guidance_state.json'
OUT=ROOT/'data/semicon/mocvd_capex_guidance.json'
KINDS={'range','point','directional','relative_order','capacity_only','investment_priority','investment_plan','not_found','release_only','pending_review'}
TITLES={'range':'금액 범위','point':'금액 목표','directional':'CAPEX 방향','relative_order':'발주 계획','capacity_only':'생산능력 계획','investment_priority':'투자 우선순위','investment_plan':'투자 계획','not_found':'금액·방향 미확인','release_only':'컨콜 미확인','pending_review':'새 발표 · 검토 대기'}

def today():return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()

def load(path,default):return json.loads(path.read_bytes()) if path.exists() else copy.deepcopy(default)

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=1,allow_nan=False)+'\n',encoding='utf-8')

def validate(rows,companies,asof):
    ids=set()
    for row in rows:
        if row['id'] in ids:raise ValueError('Duplicate guidance vintage')
        ids.add(row['id'])
        if row['company'] not in companies or row['guidance_kind'] not in KINDS:raise ValueError('Unknown issuer/guidance type')
        dt.date.fromisoformat(row['announced_at'])
        if row['announced_at']>asof or row['reported_quarter'] not in (1,2,3,4):raise ValueError('Future/invalid report')
        if not row['source_url'].startswith('https://'):raise ValueError('Missing source')
        if len(row.get('quote','').split())>20:raise ValueError('Quote exceeds excerpt budget')
        low,high=row.get('amount_low'),row.get('amount_high')
        if row['guidance_kind'] in ('range','point'):
            if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in (low,high)) or low>high:raise ValueError('Invalid numeric budget')
            if not row.get('target_start') or not row.get('target_end') or row.get('basis') not in ('전사 현금 CAPEX','공시 CAPEX 정의','InP 전용 CAPEX','프로젝트 총투자'):raise ValueError('Numeric budget needs an exact target and scope')
            if row.get('currency')!='USD' or row.get('amount_unit')!='million':raise ValueError('Unsupported numeric budget unit')
            if row['guidance_kind']=='point' and low!=high:raise ValueError('Point estimate needs equal bounds')
        elif low is not None or high is not None:raise ValueError('Non-numeric statement must not become a dollar budget')
        if row.get('target_start') and row.get('target_end') and row['target_start']>row['target_end']:raise ValueError('Reversed target interval')
        for key in ('target_start','target_end'):
            if row.get(key):dt.date.fromisoformat(row[key])
        if row['review_status'] in ('release_only','pending') and row['guidance_kind'] in ('range','point','directional'):raise ValueError('Unreviewed statement cannot be classified as confirmed guidance')

def revision(previous,current):
    keys=('company','target_start','target_end','basis','currency','amount_unit')
    if any(not current.get(k) for k in ('target_start','target_end')) or any(previous.get(k)!=current.get(k) for k in keys):return 'not_comparable'
    a=[previous.get('amount_low'),previous.get('amount_high')];b=[current.get('amount_low'),current.get('amount_high')]
    if any(v is None for v in a+b):return 'not_comparable'
    if a==b:return 'maintained'
    if all(y>=x for x,y in zip(a,b)) and any(y>x for x,y in zip(a,b)):return 'raised'
    if all(y<=x for x,y in zip(a,b)) and any(y<x for x,y in zip(a,b)):return 'lowered'
    return 'range_changed'

def forward_sentences(html):
    soup=BeautifulSoup(html,'html.parser')
    # Ignore financial tables, which are actuals even when a future sentence
    # appears elsewhere on the same page. A candidate still needs human review.
    for tag in soup.select('table,script,style'):tag.decompose()
    text=soup.get_text(' ',strip=True)
    sentences=re.split(r'(?<=[.!?])\s+',text)
    return [s for s in sentences if re.search(r'\bcapex\b|capital expenditures|capital spending',s,re.I)
            and re.search(r'\bexpect|\bplan|\bforecast|\banticipat|\bintend|\bwill\b',s,re.I)
            and not re.search(r'forward.looking statements|risk factors|could differ',s,re.I)]

def pending(company,release,html):
    text=BeautifulSoup(html,'html.parser').get_text(' ',strip=True)
    match=re.search(r'(First|Second|Third|Fourth) Quarter(?: and Full[- ](?:Fiscal[- ])?Year)?(?: of)?(?: Fiscal)?(?: Year)? (20\d\d)',text,re.I)
    if not match:return None
    q={'first':1,'second':2,'third':3,'fourth':4}[match[1].lower()];year=int(match[2])
    if year<2025:return None
    candidates=forward_sentences(html)
    return dict(id=f'{company}-fy{year}-q{q}',company=company,reported_fy=year,reported_quarter=q,reported_end=None,
        announced_at=release['filed'],date_basis='filed',guidance_kind='pending_review',headline='새 실적 공시 · 가이던스 검토 대기',
        target_period='대상 기간 미확인',target_start=None,target_end=None,basis='미확인',currency='USD',amount_low=None,amount_high=None,amount_unit='million',
        capex_direction='not_stated',revision='not_comparable',summary='새 SEC 실적 공시를 감지했습니다. '+('미래 CAPEX 후보 문구가 있어 금액·기간·발주/현금 기준 확인이 필요합니다.' if candidates else '확인 문서에서 미래 CAPEX 후보 문구를 찾지 못했지만 컨콜 확인 전에는 가이던스 부재로 단정하지 않습니다.'),
        quote=' '.join(candidates[0].split()[:20]) if candidates else '',speaker='확인 대기',review_status='pending',source_url=release['url'],source_label='SEC 실적 공시 · 검토 대기',official_url=release['url'],reviewed=None)

def refresh(seed,old,asof,get=sec_get):
    rows={r['id']:copy.deepcopy(r) for r in old.get('rows',[])}
    rows.update({r['id']:copy.deepcopy(r) for r in seed['rows']});statuses=copy.deepcopy(old.get('companies_status',{}))
    since=f'{int(asof[:4])-1}-01-01'
    for company,spec in seed['companies'].items():
        prior=statuses.get(company,{})
        try:
            releases=[r for r in earnings_exhibits(spec['cik'],since,get=get) if r['filed']<=asof];seen=[]
            for release in releases:
                if release['filed']>asof:continue
                response=get(release['url']);row=pending(company,release,response.text)
                if row:
                    seen.append(row['id'])
                    if row['id'] not in rows:rows[row['id']]=row
            if not seen:raise ValueError('No earnings periods confirmed in SEC release list')
            statuses[company]=dict(ok=True,checked=asof,last_success=asof,latest_seen=max(releases,key=lambda r:r['filed'])['filed'])
        except (requests.RequestException,ValueError,KeyError,TypeError):
            statuses[company]=dict(prior,ok=False,checked=asof,message='공시 조회 실패 · 기존 확인 이력 유지')
    return dict(rows=sorted(rows.values(),key=lambda r:(r['announced_at'],r['company'],r['id'])),companies_status=statuses,checked=asof)

def build(seed,state):
    rows=copy.deepcopy(state['rows']);validate(rows,seed['companies'],today())
    bytarget={}
    for row in rows:
        key=(row['company'],row.get('target_start'),row.get('target_end'),row['basis'])
        prior=bytarget.get(key)
        row['revision']=revision(prior,row) if prior else 'not_comparable'
        if row['guidance_kind'] in ('range','point'):bytarget[key]=row
        row['kind_label']=TITLES[row['guidance_kind']]
    return dict(id='mocvd_capex_guidance',name='Coherent·Lumentum · 미래 CAPEX 가이던스',rows=rows,companies=seed['companies'],updated=max(r['announced_at'] for r in rows),
        fetched=seed['reviewed'],reviewed=seed['reviewed'],checked=state.get('checked'),companies_status=state.get('companies_status',{}),
        methodology=seed['methodology'],source='공식 실적 발표·SEC / 경영진 컨콜 공개 재게시',source_url='https://ir.coherent.com/financial-information/quarterly-results',
        description='발표 분기별 미래 투자 발언을 비교합니다. 금액·범위가 확인되면 그대로 기록하고, 방향성·발주 기준·생산능력 목표는 별도로 표시합니다. 실제 CAPEX 집행액과 다릅니다.')

def collect(offline=False):
    seed=load(MANUAL,{});old=load(STATE,{})
    if offline:
        rows={r['id']:r for r in old.get('rows',[])};rows.update({r['id']:r for r in seed['rows']})
        state=dict(old,rows=sorted(rows.values(),key=lambda r:(r['announced_at'],r['company'],r['id'])))
    else:state=refresh(seed,old,today())
    doc=build(seed,state);save(STATE,state);save(OUT,doc)
    print('Published',len(doc['rows']),'CAPEX guidance vintages; confirmed dollar budgets:',sum(r['guidance_kind'] in ('range','point') for r in doc['rows']))
    return state

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');args=p.parse_args();collect(args.offline)

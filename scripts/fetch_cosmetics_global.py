"""Global beauty comparators, preserving original currency, GAAP and frequency."""
import argparse,copy,datetime as dt,json,math,re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pymupdf
from fetch_cpu_companies import save
from fetch_cosmetics import read
from cosmetics_global_sources import loreal_release,shiseido_statement,shiseido_chart,quarterly_from_ytd,estee_accounts,end

ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.cache/cosmetics-global';OUT=ROOT/'data/cosmetics';STATE=OUT/'global_state.json'
META=ROOT/'manual/cosmetics/global-companies.json'
UA='industry-dashboard personal research wkorotk@gmail.com'


def merge(prior,fresh):
    rows={(r['kind'],r['date']):copy.deepcopy(r) for r in prior}
    for r in fresh:
        target=rows.setdefault((r['kind'],r['date']),copy.deepcopy(r))
        for metric,ref in r['refs'].items():
            old=target['refs'].get(metric,{})
            rank=lambda f:(f.get('basis')=='IFRS','official chart rounded' not in f.get('tag',''),f.get('filed',''))
            if rank(ref)>=rank(old):
                target[metric]=r[metric];target['refs'][metric]=ref;target['basis']=r['basis']
    return [r for _,r in sorted(rows.items())]


def validate(co,asof):
    rows=co['records']
    if not rows or len(rows)!=len({(r['kind'],r['date']) for r in rows}):raise ValueError('Missing/duplicate global reporting periods')
    for metric in ['revenue','profit','capex']:
        if not any(metric in r for r in rows):raise ValueError('Missing global metric')
    for r in rows:
        if r['date']>asof:raise ValueError('Future global period')
        for metric,ref in r['refs'].items():
            if ref['filed']>asof or not math.isfinite(r[metric]) or metric!='profit' and r[metric]<0:raise ValueError('Invalid global source/value')


def collect(old,asof,offline=False):
    CACHE.mkdir(parents=True,exist_ok=True);result={};session=requests.Session();session.headers['User-Agent']=UA
    def fetch(url,name,immutable=False):
        p=CACHE/name
        if offline or immutable and p.exists():return p.read_bytes()
        r=session.get(url,timeout=(10,45));r.raise_for_status();p.write_bytes(r.content);return r.content
    for key in ['loreal','estee','shiseido']:
        previous=old.get('companies',{}).get(key,{})
        try:
            if key=='estee':
                co=estee_accounts(json.loads(fetch('https://data.sec.gov/api/xbrl/companyfacts/CIK0001001250.json','estee.json')),asof)
                records=[]
                for kind,rows in [('quarter',co['rows']),('annual',co['annual'])]:
                    for r in rows:
                        r=dict(r,kind=kind,basis='US GAAP')
                        for f in r['refs'].values():f['basis']='US GAAP'
                        records.append(r)
            elif key=='loreal':
                if offline:manifest=read(CACHE/'loreal-manifest.json')
                else:
                    raw=fetch('https://www.loreal-finance.com/eng/results','loreal.html');soup=BeautifulSoup(raw,'html.parser');manifest=[]
                    for a in soup.select('a[href]'):
                        h=a['href'];m=re.search(r'/(20\d{2})-(annual|half-year)-results$',h)
                        q3=re.search(r'/sales-(?:at-)?30-september-(20\d{2})$',h)
                        if not m and not q3:continue
                        y=int(m[1] if m else q3[1]);kind=('annual' if m[2]=='annual' else 'half') if m else 'q3'
                        if y<int(asof[:4])-1:continue
                        manifest.append(dict(year=y,kind=kind,url=urljoin('https://www.loreal-finance.com',h),path=f'loreal-{y}-{kind}.html'))
                    if not manifest:raise ValueError('Loreal release index changed')
                    save(CACHE/'loreal-latest-manifest.json',manifest)
                records=[]
                for m in manifest:
                    fresh=loreal_release(fetch(m['url'],m['path']),m)
                    records.extend(r for r in fresh if r['date']<=asof and all(f['filed']<=asof for f in r['refs'].values()))
            else:
                records=[]
                if offline:manifest=read(CACHE/'shiseido-manifest.json')
                else:
                    raw=fetch('https://corp.shiseido.com/en/ir/library/tanshin/','shiseido-results.html');soup=BeautifulSoup(raw,'html.parser')
                    manifest=[dict(url=urljoin('https://corp.shiseido.com',a['href']),path='shiseido-'+a['href'].split('/')[-1]) for a in soup.select('a[href]') if 'Settlement' in a.get_text() and a['href'].endswith('.pdf')]
                    if not manifest:raise ValueError('Shiseido statement index changed')
                    save(CACHE/'shiseido-manifest.json',manifest)
                for m in manifest:
                    d=re.search(r'ir(\d{4})(\d{2})(\d{2})',m['path']);m=dict(m,filed='-'.join(d.groups()))
                    if m['filed']>asof:continue
                    # Existing normalized originals do not require downloading
                    # every historical PDF on each scheduled collection.
                    if not offline and any(f['url']==m['url'] for r in previous.get('records',[]) for f in r['refs'].values()):continue
                    raw=fetch(m['url'],m['path'],immutable=True)
                    with pymupdf.open(stream=raw,filetype='pdf') as pdf:text='\n\n'.join(p.get_text(sort=True) for p in pdf)
                    records+=shiseido_statement(text,m)
                for name,jgaap in [('data3_en.js',True),('data_en.js',False)]:
                    path='jgaap-'+name if jgaap else name;url='https://irpocket.com/4911/chart_ver2_hc6/'+name
                    records+=shiseido_chart(fetch(url,path).decode('utf8'),url,asof,jgaap)
            records=merge(previous.get('records',[]),records)
            co=dict(records=records,ok=True,checked=asof,fetched=asof);validate(co,asof)
            if previous.get('records') and max(r['date'] for r in records)<max(r['date'] for r in previous['records']):raise ValueError('Global history regressed')
            result[key]=co;print(key,len(records),'original periods',flush=True)
        except (ValueError,KeyError,OSError,requests.RequestException,RuntimeError) as error:
            if not previous:raise RuntimeError(key+' has no verified global history') from error
            result[key]=dict(previous,ok=False,checked=asof);print(key,'preserved prior history',type(error).__name__,flush=True)
    return dict(checked=asof,companies=result)


def label(row,kind):
    if kind=='quarter':return f"FY{row['year']} Q{row['quarter']}"
    if kind=='half':return f"{row['year']} H{row['quarter']//2}"
    if kind=='transition' or row.get('transition'):return '2015.12 · 결산 변경 9/12개월'
    return f"FY{row['year']}"+(' · 3월 결산' if row['date'][5:7]=='03' else '')


def view(rows,metric,kind,spec):
    valid=sorted([r for r in rows if metric in r],key=lambda r:r['date'])
    if not valid:return None
    actual={r['date']:r for r in valid};axis=set(actual)
    if kind=='quarter':
        for year in range(int(valid[0]['date'][:4]),int(valid[-1]['date'][:4])+1):
            for q in range(1,5):
                d=end(year,q)
                if valid[0]['date']<d<valid[-1]['date']:axis.add(d)
    labels={r['date']:label(r,kind) for r in valid};lookup={(r['year'],r.get('quarter')):r['date'] for r in valid}
    series_label={'revenue':'연결 매출','profit':'공시 영업이익','capex':'회사 공시 Investments' if spec['currency']=='EUR' else '회사 공시 CAPEX' if kind=='reported_annual' else '유형자산 취득 현금지출'}[metric]
    title={'quarter':'분기','half':'반기','annual':'연간','reported_annual':'회사 CAPEX · 연간','transition':'결산 변경 기간'}[kind]
    notes={};sources={}
    for r in valid:
        ref=r['refs'][metric];components=ref['components']
        notes[r['date']]=[labels[r['date']],ref['start']+' ~ '+ref['end'],ref.get('basis',r['basis']),ref['tag'],ref['calculation'],'공시 원통화: '+spec['currency']+' 백만']
        sources[r['date']]=dict(url=ref['url'],label=labels[r['date']],supporting_sources=[dict(url=f['url'],label=f['start']+' ~ '+f['end']) for f in components],source_separator=' − ' if len(components)==2 else ' / ')
    return dict(label=title,frequency='quarterly' if kind=='quarter' else 'yearly' if kind in ['annual','reported_annual'] else 'irregular',frequency_label='연간 · 유형·무형 투자' if kind=='reported_annual' else title+' · 공식 공시 · 원통화',
       series={series_label:[[d,actual[d][metric] if d in actual else None] for d in sorted(axis)]},default_series=[series_label],period_labels=labels,
       quarter_labels=kind=='quarter',year_labels=kind in ['annual','reported_annual'],annual_axis=kind in ['annual','reported_annual'],
       quarterly_revenue_summary=kind=='quarter' and metric!='profit',quarterly_profit_summary=kind=='quarter' and metric=='profit',
       comparison_dates={r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),(r['quarter']-2)%4+1))) for r in valid} if kind=='quarter' else {},
       point_sources=sources,point_notes=notes,updated=valid[-1]['date'],source_url=valid[-1]['refs'][metric]['url'],change_mode='none' if kind in ['half','transition'] else 'default')


def build(meta,state):
    docs={}
    for key,spec in meta['companies'].items():
        co=state['companies'][key];records=co['records'];quarters=[r for r in records if r['kind']=='quarter']
        if key=='shiseido':quarters=quarterly_from_ytd(records)
        half=[r for r in records if r['kind']=='half']
        if key=='loreal':
            index={(r['year'],r['kind']):r for r in records}
            for annual in [r for r in records if r['kind']=='annual']:
                prior=index.get((annual['year'],'half'))
                if not prior:continue
                row=dict(kind='half',year=annual['year'],quarter=4,date=annual['date'],basis=annual['basis'],refs={})
                for metric in ['revenue','profit','capex']:
                    if metric not in prior or metric not in annual:continue
                    value=annual[metric]-prior[metric]
                    if metric!='profit' and value<0:continue
                    a,b=annual['refs'][metric],prior['refs'][metric]
                    if b['filed']>a['filed']:continue
                    row[metric]=value;row['refs'][metric]=dict(a,start=f"{annual['year']}-07-01",components=[a,b],calculation='same fiscal year annual minus H1')
                if row['refs']:half.append(row)
        for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
            transitions=[r for r in records if r['kind']=='transition']
            if metric=='capex':transitions=[r for r in records if r.get('transition') and r['kind']=='reported_annual']
            groups={'quarter':quarters,'half':half,'annual':[r for r in records if r['kind']=='annual'],'reported_annual':[r for r in records if r['kind']=='reported_annual' and not r.get('transition')],'transition':transitions}
            vv={kind:v for kind,rr in groups.items() if (v:=view(rr,metric,kind,spec))}
            default=next(k for k in ['quarter','half','annual'] if k in vv);id=f'company_cosmetics_{key}_{metric}'
            note=spec['scope']+'. '+spec['note']
            doc=dict(id=id,name=spec['name']+' · '+title,unit=spec['currency']+' 백만',source='공식 IR·SEC · '+spec['name'],source_url=spec['source_url'],fetched=co['fetched'],company_kpi=True,span_gaps=False,table_limit=120,description=note,
                default_view=default,series_views=vv,basis_details=[dict(label='기업·사업 범위',value=note),dict(label='통화·결산·비교',value='공시 원통화를 유지하며 환율 변환이나 회사 간 매출 합산을 하지 않습니다. 국가·회사별 공시 빈도, 결산월, 사업 범위와 CAPEX 정의가 다릅니다. 실제 단일 분기나 반기만 표시하고 분기 이익을 나누어 추정하지 않습니다.'),dict(label='원문·공백',value='각 관측값에 원문·보고기간·회계기준·차감 근거를 표시합니다. 미확인 분기·현금흐름은 공백입니다. 시세이도는 연간 2014년부터, 유형자산 현금지출은 확인된 2020년 이후부터이며 과거 회사 CAPEX는 별도 보기입니다.' if key=='shiseido' else '공식 실제 실적만 표시하며 예측·조정 이익으로 대체하지 않습니다. 로레알의 과거 반기는 확보한 2019년부터, 매출 분기·연간과 이익·투자 연간은 2014년부터입니다.' if key=='loreal' else 'SEC 10-K·10-Q의 실제 3개월 금액과 같은 회계연도 누적 차감을 사용합니다. 연간은 완결 12개월 보고서입니다.'),dict(label='갱신 확인',value=co['checked']+' · '+('정상' if co['ok'] else '수집 확인 실패 · 마지막 성공 이력 유지'))])
            doc.update(copy.deepcopy(vv[default]));doc.pop('label',None)
            if not co['ok']:doc['collection_status']=dict(ok=False,checked=co['checked'],message='원문 확인 실패 · 마지막 성공 자료 유지')
            docs[id]=doc
    return docs


def main():
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--from-state',action='store_true');a=p.parse_args()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();old=read(STATE,dict(companies={}))
    state=old if a.from_state else collect(old,asof,offline=not a.refresh)
    for co in state['companies'].values():validate(co,asof)
    docs=build(read(META),state)
    for id,doc in docs.items():save(OUT/(id+'.json'),doc)
    save(STATE,state);print('Published',len(docs),'global beauty charts',flush=True)


if __name__=='__main__':main()

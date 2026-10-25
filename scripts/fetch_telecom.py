"""Free SEC, OpenDART and issuer IR telecom accounts; preserve original currency."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from fetch_cpu_companies import save
from fetch_game_fx import SOURCE, build_snapshot, parse_rates
from telecom_sources import (dart_accounts, dart_report, parse_kddi, parse_ntt,
                            parse_softbank, reporting_period, sec_accounts, softbank_link)

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/telecom'
CACHE=ROOT/'.cache/telecom'
META=ROOT/'manual/telecom/companies.json'
METRICS={'revenue':'매출','profit':'영업이익','capex':'CAPEX'}


def load(path,default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def collect_dart(meta,prior,session,asof,full=False):
    key=os.environ.get('DART_API_KEY')
    if not key:raise ValueError('DART key unavailable')
    reports={(r['year'],r['quarter']):r for r in prior.get('reports',[])}
    first=2020 if full or not reports else int(asof[:4])-1
    failures=0
    for year in range(int(asof[:4]),first-1,-1):
        for quarter,code in [(1,'11013'),(2,'11012'),(3,'11014'),(4,'11011')]:
            if reporting_period(year,quarter)['date']>asof:continue
            try:
                response=session.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json',params=dict(crtfc_key=key,corp_code=meta['corp_code'],bsns_year=year,reprt_code=code,fs_div='CFS'),timeout=25)
                response.raise_for_status();payload=response.json()
                if payload.get('status')=='013':continue
                if payload.get('status')!='000':raise ValueError('DART report unavailable')
                reports[year,quarter]=dart_report(payload['list'],year,quarter,meta['corp_code'])
                if 'capex' not in reports[year,quarter]['fields']:
                    candidates=[{k:r.get(k) for k in ('account_id','account_nm')} for r in payload['list'] if r.get('sj_div')=='CF' and any(t in r.get('account_nm','') for t in ('유형','취득'))]
                    print(meta['name'],year,quarter,'CAPEX mapping review:',json.dumps(candidates,ensure_ascii=False),flush=True)
                failures=0
            except (requests.RequestException,ValueError,KeyError):
                failures+=1
                if failures>=3:raise ValueError('repeated DART source errors') from None
            time.sleep(.15)
    return dict(reports=[r for _,r in sorted(reports.items())],rows=dart_accounts(list(reports.values()),asof))


def merge_rows(prior,updates):
    rows={(r['kind'],r['date']):copy.deepcopy(r) for r in prior}
    for r in updates:
        key=r['kind'],r['date'];old=rows.setdefault(key,copy.deepcopy(r))
        for metric in METRICS:
            if r.get(metric) is not None:old[metric]=r[metric];old['refs'][metric]=r['refs'][metric]
    return sorted(rows.values(),key=lambda r:(r['date'],r['kind']))


def fetch(session,url,offline=False):
    digest=hashlib.sha256(url.encode()).hexdigest()[:18]
    path=CACHE/(digest+'.bin')
    if offline:
        if not path.exists():raise ValueError('uncached issuer source')
        return path.read_bytes()
    r=session.get(url,timeout=50);r.raise_for_status()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content)
    return r.content


def links(raw,base,suffix):
    soup=BeautifulSoup(raw,'html.parser')
    return list(dict.fromkeys(urljoin(base,a['href']) for a in soup.select('a[href]') if suffix in a['href']))


def collect_japan(key,session,asof,prior,offline=False):
    rows=prior.get('rows',[]);errors=[]
    if key=='ntt':
        base='https://group.ntt/en/ir/library/results/'
        urls=links(fetch(session,base,offline),base,'.xlsx')
        urls=[u for u in urls if re.search(r'fy20\d{2}q4data',u) or re.search(r'fy'+asof[:4]+r'q[1-4]data',u)]
        parser=parse_ntt
    elif key=='kddi':
        base='https://www.kddi.com/english/corporate/ir/finance/highlight/'
        urls=[u for u in links(fetch(session,base,offline),base,'.xlsx') if 'highlight_' in u]
        if len(urls)!=1:raise ValueError('KDDI workbook discovery changed')
        parser=parse_kddi
    else:
        urls=[]
        for year in range(2020,int(asof[:4])+1):
            found=False
            for q in ([4,3,2,1] if year==int(asof[:4]) else [4]):
                url=f'https://www.softbank.jp/corp/set/common/shared/json/ir/fy{year}/fy{year}_q{q}_en.tsv'
                try:urls.append(softbank_link(fetch(session,url,offline),asof));found=True;break
                except (requests.RequestException,ValueError):continue
            if not found:
                reviewed={2023:'20240509',2024:'20250508'}
                if year in reviewed:
                    urls.append(f'https://www.softbank.jp/en/corp/set/data/ir/documents/presentations/fy{year}/results/pdf/sbkk_earnings_datasheet_excel_{reviewed[year]}.xlsx')
                else:errors.append(f'{year} published data sheet unavailable')
        parser=parse_softbank
    for url in sorted(urls):
        try:
            incoming=parser(fetch(session,url,offline),url,asof)
            if not any(r.get('revenue') is not None for r in incoming):raise ValueError('empty issuer workbook')
            rows=merge_rows(rows,incoming)
        except (requests.RequestException,ValueError,KeyError,TypeError):
            errors.append('issuer workbook unavailable or format changed')
    if key=='kddi':
        reviewed=load(ROOT/'manual/telecom/kddi-reviewed.json',dict(rows=[]))
        rows=merge_rows(rows,[r for r in reviewed['rows'] if r['date']<=asof])
    if not rows:raise ValueError('no reviewed issuer history')
    return dict(rows=rows,source_errors=errors)


def memo(value,currency,row,fx):
    lines=[f'원통화: {value:,.6f}'.rstrip('0').rstrip('.')+f' 백만 {currency}',f"실적 기간: {row['start']} ~ {row['date']}"]
    if currency=='USD':return lines+['원자료 USD 그대로 · 환산 없음']
    q=fx.get('periods',{}).get(f"{currency}|{row['start']}|{row['date']}")
    if not q:return lines+['해당 기간 평균환율 미확보 · USD 값 미표시']
    return lines+[f"기간 평균: 1 USD = {q['local_per_usd']:,.6f} {currency}",f"ECB 일별 {q['observations']}개 관측 평균 · 원통화 금액 ÷ 평균환율",f"환율 관측: {q['first']} ~ {q['last']}"]


def usd(value,currency,row,fx):
    if value is None:return None
    if currency=='USD':return value
    q=fx.get('periods',{}).get(f"{currency}|{row['start']}|{row['date']}")
    return value/q['local_per_usd'] if q else None


def document(key,metric,meta,cohort,fx):
    label=METRICS[metric];views={};currency=meta['currency']
    for kind in ['quarter','annual']:
        rows=[r for r in cohort.get('rows',[]) if r['kind']==kind]
        actual={r['date']:r for r in rows};axis=set(actual)
        # Calendar quarter placeholders preserve real gaps without adding data.
        if rows:
            for year in range(int(rows[0]['date'][:4]),int(rows[-1]['date'][:4])+1):
                for q in range(1,5):
                    d=reporting_period(year,q)['date']
                    if rows[0]['date']<d<rows[-1]['date'] and kind=='quarter':axis.add(d)
        native=[[d,actual.get(d,{}).get(metric)] for d in sorted(axis)]
        points=[[d,usd(v,currency,actual[d],fx) if v is not None else None] for d,v in native]
        last=next((r for r in reversed(rows) if r.get(metric) is not None),None)
        refs={}
        for r in rows:
            if metric not in r.get('refs',{}):continue
            ref=r['refs'][metric];components=ref.get('components',[])
            supporting=[dict(url=c['url'],label=c.get('start','')+' ~ '+c.get('end','')) for c in components if c.get('url')]
            refs[r['date']]=dict(url=ref['url'],label=r['period']+(' · '+ref['location'] if ref.get('location') else ''),**({'pdf_page':ref['pdf_page']} if ref.get('pdf_page') else {}),
                **({'supporting_sources':supporting} if supporting else {}),source_separator=' − ' if 'minus' in ref.get('calculation','') else ' / ')
        lookup={(r['year'],r.get('quarter')):r['date'] for r in rows}
        views[kind]=dict(label='분기' if kind=='quarter' else '연간',frequency='quarterly' if kind=='quarter' else 'yearly',frequency_label='분기 단독' if kind=='quarter' else '연간 · 회사 회계연도',
            quarter_labels=kind=='quarter',year_labels=kind=='annual',annual_axis=kind=='annual',
            series={label:points} if last else {},original_series={label:native},original_currency=currency,original_unit='millions',
            point_notes={r['date']:memo(r[metric],currency,r,fx) for r in rows if r.get(metric) is not None},point_sources=refs,
            period_labels={r['date']:r['period'] for r in rows},updated=last['date'] if last else '',source_url=last['refs'][metric]['url'] if last else '',
            quarterly_revenue_summary=kind=='quarter' and metric!='profit',quarterly_profit_summary=kind=='quarter' and metric=='profit',change_mode='none',
            comparison_dates={r['date']:dict(year_ago=lookup.get((r['year']-1,r.get('quarter'))),quarter_ago=lookup.get((r['year']-(r.get('quarter')==1),(r.get('quarter',1) or 1)-1 or 4))) for r in rows} if kind=='quarter' else {},
            empty_message=f"{meta['name']}의 {'분기 단독' if kind=='quarter' else '연간'} {label} 자료 미확보. 미확보 값은 0으로 채우거나 연간을 나누어 만들지 않습니다.")
    default=meta.get('default_views',{}).get(metric) or ('quarter' if any(r.get(metric) is not None for r in cohort.get('rows',[]) if r['kind']=='quarter') else 'annual')
    coverage=[r['date'] for r in cohort.get('rows',[]) if r.get(metric) is not None]
    source_note='일부 과거 원문 미확보 · 확보한 이력만 표시' if cohort.get('source_errors') else '공개 원문에서 확보한 이력'
    return dict(id=f'company_{key}_{metric}',name=meta['name']+' · '+label,unit='백만 USD',company_kpi=True,span_gaps=False,zero_baseline=True,
                fetched=cohort.get('fetched'),source='SEC 공시' if meta.get('cik') else 'OpenDART 연결 공시' if meta.get('corp_code') else '공식 IR·공시',
                description=meta['scope']+('. '+meta['capex_basis'] if metric=='capex' else '. 연결 영업이익이며 EBITDA·조정 영업이익과 구분합니다.' if metric=='profit' else ''),
                basis_details=[dict(label='CAPEX 범위',value=meta['capex_basis']),dict(label='환산·기간',value='USD 공시 금액은 그대로, 원화·엔화는 실제 실적 기간의 ECB 평균환율로 환산합니다. 연간은 회사가 공시한 완결 회계연도 실적입니다. 금액·차트에 마우스를 올리면 원통화를 확인할 수 있습니다. CAPEX에 통신망 외 건물·데이터센터·소프트웨어 등이 포함될 수 있어 통신장비 발주액과 같지 않습니다.'),dict(label='확보 범위',value=(min(coverage)+' ~ '+max(coverage)+' · ' if coverage else '')+source_note),dict(label='자료 확인',value=cohort.get('checked','미확보')+' · '+cohort.get('status','미확보'))],
                collection_status=dict(ok=cohort.get('status')=='ok',checked=cohort.get('checked',''),message=source_note if cohort.get('status')=='ok' else cohort.get('status','자료 미확보')),
                default_view=default,series_views=views,**{k:v for k,v in views[default].items() if k!='label'})


def collect(offline=False,full=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=load(META,{});state=load(OUT/'state.json',dict(companies={}))
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    def korean_job(key):
        own=requests.Session()
        return collect_dart(meta[key],state['companies'].get(key,{}),own,asof,full)
    pool=ThreadPoolExecutor(max_workers=3)
    korean={key:pool.submit(korean_job,key) for key,spec in meta.items() if spec.get('corp_code')} if not offline else {}
    for key,spec in meta.items():
        prior=state['companies'].get(key,{})
        try:
            if spec.get('cik'):
                url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json'
                fresh=dict(rows=sec_accounts(json.loads(fetch(session,url,offline)),spec,asof));time.sleep(.4)
            elif spec.get('corp_code'):
                if offline:
                    if not prior.get('rows'):raise ValueError('no cached DART accounts')
                    fresh=prior
                else:fresh=korean[key].result()
            else:fresh=collect_japan(key,session,asof,prior,offline)
            if not fresh.get('rows'):raise ValueError('no public accounts')
            state['companies'][key]=dict(prior,**fresh,checked=asof,fetched=asof,status='ok') if not offline else dict(prior,**fresh)
            print(key,len(fresh['rows']),'periods',flush=True)
        except (requests.RequestException,ValueError,KeyError,TypeError) as error:
            state['companies'][key]=dict(prior,checked=asof,status=f'최신 조회 미완료 · 기존 성공 자료 유지 ({type(error).__name__})')
            print(key,'retained previous accounts:',type(error).__name__,flush=True)
    pool.shutdown(wait=True)
    intervals=sorted({(meta[key]['currency'],r['start'],r['date']) for key,c in state['companies'].items() for r in c.get('rows',[]) if meta[key]['currency']!='USD'})
    old_fx=load(OUT/'fx.json',{});rates=None;digest=None;error=None
    try:
        raw=fetch(session,SOURCE,offline);rates=parse_rates(raw);digest=hashlib.sha256(raw).hexdigest()
    except (requests.RequestException,ValueError,KeyError):error='ECB feed unavailable; exact completed intervals retained'
    fx=build_snapshot(old_fx,intervals,rates,asof,digest,error)
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'state.json',state);save(OUT/'fx.json',fx)
    for key,spec in meta.items():
        for metric in METRICS:save(OUT/f'company_{key}_{metric}.json',document(key,metric,spec,state['companies'][key],fx))
    print('Published 27 telecom cards;',len(fx['periods']),'FX intervals;',len(fx['missing']),'missing',flush=True)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--full-history',action='store_true');a=p.parse_args();collect(a.offline,a.full_history)

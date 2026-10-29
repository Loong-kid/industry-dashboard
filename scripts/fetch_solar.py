"""Eight representative solar suppliers; public GAAP issuer accounts."""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urljoin,urldefrag

import requests
from bs4 import BeautifulSoup

from fetch_cpu_companies import load,save
from fetch_game_fx import SOURCE,parse_rates,build_snapshot
from solar_sources import METRICS,us_accounts,annual_accounts,release_rows,merge_rows

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/solar';CACHE=ROOT/'.cache/solar'


def document(key,metric,meta,cohort,fx):
    label=METRICS[metric];views={}
    missing_fx=[r['date'] for r in cohort['rows'] if r['kind'] in ('quarter','annual','transition') and r['currency']!='USD' and f"{r['currency']}|{r['start']}|{r['date']}" not in fx.get('periods',{})]
    for kind,title in [('quarter','분기'),('annual','연간'),('transition','전환기 6개월')]:
        rows=[r for r in cohort['rows'] if r['kind']==kind]
        if not rows and kind=='transition':continue
        axis={r['date']:r for r in rows}
        for a,b in zip(rows,rows[1:]):
            if kind=='quarter' and (dt.date.fromisoformat(b['start'])-dt.date.fromisoformat(a['date'])).days>40:
                axis[(dt.date.fromisoformat(a['date'])+dt.timedelta(days=1)).isoformat()]={}
        usd=[];native=[];notes={};refs={}
        for day,r in sorted(axis.items()):
            value=r.get(metric);native.append([day,value]);rate=fx.get('periods',{}).get(f"{r.get('currency')}|{r.get('start')}|{day}")
            converted=value if meta['currency']=='USD' else value/rate['local_per_usd'] if value is not None and rate else None
            usd.append([day,converted])
            if value is None:continue
            ref=r['refs'][metric]
            notes[day]=[r['period'],r['start']+' ~ '+day,f"원자료: {value:,.6f} 백만 {r['currency']}",ref['tag'],ref['calculation']]
            if ref.get('derivation'):notes[day].append('GAAP 매출총이익 − 영업비용 · 동일 공시·동일 기간')
            if meta['currency']!='USD':notes[day]+=[f"ECB 기간 평균: 1 USD = {rate['local_per_usd']:,.6f} {meta['currency']} · {rate['observations']}개 관측 · 원자료 ÷ 평균환율" if rate else '보고기간 환율 미확보 · USD 값 미표시']
            components=ref.get('components',[])
            refs[day]=dict(url=ref['url'],label=r['period']+' · SEC 원문',**(dict(supporting_sources=[dict(url=c['url'],label=c['start']+' ~ '+c['end']) for c in components],source_separator=' − ') if len(components)>1 else {}))
        last=next((r for r in reversed(rows) if metric in r),None)
        lookup={(r['regime'],r['year'],r['quarter']):r['date'] for r in rows}
        views[kind]=dict(label=title,frequency='quarterly' if kind=='quarter' else 'yearly' if kind=='annual' else 'irregular',
            frequency_label='분기 · 실제 결산일' if kind=='quarter' else '연간 · 완결 회계연도' if kind=='annual' else '2016년 7~12월 · 6개월',
            quarter_labels=kind=='quarter',year_labels=kind=='annual',annual_axis=kind=='annual',
            period_labels={r['date']:r['period'] for r in rows},series={label:usd},point_sources=refs,point_notes=notes,
            quarterly_revenue_summary=kind=='quarter' and metric=='revenue',quarterly_profit_summary=kind=='quarter' and metric!='revenue',change_mode='none',
            comparison_dates={r['date']:dict(year_ago=lookup.get((r['regime'],r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['regime'],r['year']-(r['quarter']==1),r['quarter']-1 or 4))) for r in rows} if kind=='quarter' else {},
            updated=last['date'] if last else '',source_url=last['refs'][metric]['url'] if last else meta['source_url'])
        if meta['currency']!='USD':views[kind].update(original_series={label:native},original_currency=meta['currency'],original_unit='millions')
    if meta['currency']!='USD':
        for kind,view in list(views.items()):
            views[kind+'_cny']=dict(view,label=view['label']+' CNY',unit='백만 CNY',series=view['original_series'])
    basis=[dict(label='사업·연결 범위',value=meta['note']),dict(label='집계 기준',value='회사 연결 GAAP 매출·영업손익과 지배주주 귀속 순손익을 표시합니다. 조정 EBITDA·비GAAP 이익·출하량·수주액으로 대체하지 않습니다. 직접 공시한 실제 기간을 사용하며 미국 기업의 4분기는 같은 회계연도 누적 차분으로 보완할 수 있습니다. 연간을 4로 나누지 않습니다. 회계연도 변경·연결 범위·귀속 지분 변경과 손상차손·세액공제 등은 각 회사 손익에 반영됩니다.'),dict(label='수집 확인',value=cohort['checked'])]
    basis.append(dict(label='과거 비교와 재작성',value='각 기간에서 확보한 최신 공시를 사용합니다. 사업 매각·중단사업 재분류로 연간 실적이 재작성되면 당시 분기 합계와 다를 수 있습니다. 과거 분기를 연간에 비례 배분해 맞추지 않습니다. Enphase의 과거 미제공 영업 소계는 동일 공시의 매출총이익 − 영업비용으로 보완하며 각 포인트에 계산 근거를 남깁니다.'))
    if cohort.get('errors'):basis.append(dict(label='조회·공시 검토',value=' / '.join(cohort['errors'])))
    if missing_fx:basis.append(dict(label='환율 미확보',value='USD 환산값을 표시하지 않은 기간: '+', '.join(missing_fx)+'. CNY 원자료는 원통화 보기에서 확인합니다.'))
    return dict(id=f'company_{key}_{metric}',name=meta['name']+' · '+label,unit='백만 USD',company_kpi=True,compact_ticks=True,span_gaps=False,
        source='SEC · GAAP 연결 공시',fetched=cohort['fetched'],description=meta['scope'],basis_details=basis,
        collection_status=dict(ok=cohort['ok'] and not missing_fx,checked=cohort['checked'],message='보고기간 환율 미확보 · CNY 원자료 유지' if missing_fx else '공개 공시 조회 완료' if cohort['ok'] else '조회·공시 검토 필요 · 기존 이력 유지'),
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})


def collect(offline=False,bootstrap=False,asof=None):
    asof=asof or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=load(ROOT/'manual/solar/companies.json',{})
    state=load(OUT/'state.json',dict(companies={}))
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    def fetch(url):
        path=CACHE/(hashlib.sha256(url.encode()).hexdigest()[:24]+'.bin')
        if offline:return path.read_bytes()
        if bootstrap and path.exists():return path.read_bytes()
        r=session.get(url,timeout=40);r.raise_for_status();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content);time.sleep(.12);return r.content
    for key,spec in meta.items():
        prior=state['companies'].get(key,{})
        errors=[]
        try:
            facts=json.loads(fetch(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json'))
            subs=json.loads(fetch(f'https://data.sec.gov/submissions/CIK{spec["cik"]:010d}.json'))
            if spec.get('foreign'):
                observations=copy.deepcopy(prior.get('observations',[]))
                scan_after=prior.get('checked','2025-01-01')
                recent=subs['filings']['recent'];selected=[]
                for i,(form,filed) in enumerate(zip(recent['form'],recent['filingDate'])):
                    if form!='6-K' or filed>asof:continue
                    if bootstrap:
                        if filed<'2014-01-01' or not (int(filed[:4])%2 or filed[:4]=='2026'):continue
                    elif filed<scan_after:continue
                    selected.append(i)
                print(key,'scanning',len(selected),'SEC filings',flush=True)
                for i in selected:
                    accession=recent['accessionNumber'][i].replace('-','');filed=recent['filingDate'][i]
                    base=f'https://www.sec.gov/Archives/edgar/data/{spec["cik"]}/{accession}/'
                    url=base+recent['primaryDocument'][i]
                    try:
                        raw=fetch(url);soup=BeautifulSoup(raw,'html.parser')
                        links=list(dict.fromkeys(urldefrag(urljoin(url,a['href']))[0] for a in soup.select('a[href]') if '99' in a['href'] and urldefrag(a['href'])[0].lower().endswith(('.htm','.html'))))
                        if not links and '99' in soup.get_text(' ',strip=True):
                            directory=json.loads(fetch(base+'index.json'))['directory']['item']
                            links=[base+item['name'] for item in directory if '99' in item['name'] and item['name'].lower().endswith(('.htm','.html'))]
                        candidates=[(url,raw)] if not links else [(link,fetch(link)) for link in links[:5]]
                        found=[]
                        for link,body in candidates:
                            rows=release_rows(body,spec,link,filed,asof)
                            found+=rows
                            if not rows and not bootstrap:
                                text=BeautifulSoup(body,'html.parser').get_text(' ',strip=True).lower()
                                if 'consolidated statements' in text and 'revenues' in text and 'operating' in text:errors.append('새 실적 공시 표 검토 필요: '+filed+' · '+link)
                        if found:
                            observations+=found
                            print(key,filed,len(found),'statement periods',flush=True)
                    except (requests.RequestException,ValueError,KeyError,OSError,IndexError) as error:
                        errors.append(filed+' SEC 첨부 조회 미완료 ('+type(error).__name__+')')
                # Keep filing-specific observations, so newer comparisons do not
                # erase the provenance of an earlier statement's actual values.
                unique={(r['kind'],r['date'],r['refs']['revenue']['url']):r for r in observations}
                observations=list(unique.values())
                rows=merge_rows(prior.get('rows',[]),annual_accounts(facts,spec,asof),observations)
            else:
                observations=[];rows=us_accounts(facts,subs,spec,asof)
            if not rows or any(not any(r['kind']=='quarter' and metric in r for r in rows) for metric in METRICS):raise ValueError('Incomplete quarterly accounts')
            if prior.get('rows') and max(r['date'] for r in rows)<max(r['date'] for r in prior['rows']):raise ValueError('Financial source regressed')
            if prior.get('rows') and sum(r['kind']=='quarter' for r in rows)<sum(r['kind']=='quarter' for r in prior['rows']):raise ValueError('Quarter history shortened')
            state['companies'][key]=dict(rows=rows,observations=observations,checked=prior.get('checked',asof) if offline else asof,
                fetched=prior.get('fetched',asof) if offline else asof,ok=not errors,errors=errors)
        except (requests.RequestException,ValueError,KeyError,OSError,IndexError) as error:
            if not prior.get('rows'):raise RuntimeError(key+' has no verified solar accounts') from error
            state['companies'][key]=dict(prior,checked=asof,ok=False,errors=[type(error).__name__+' · 직전 성공 이력 유지'])
        cohort=state['companies'][key]
        print(key,'published',len(cohort['rows']),'periods',max(r['date'] for r in cohort['rows']),'warnings',len(cohort['errors']),flush=True)
        save(OUT/'state.json',state)
    intervals=sorted({(r['currency'],r['start'],r['date']) for c in state['companies'].values() for r in c['rows'] if r['currency']!='USD'})
    raw=None;rates=None;error=None
    try:raw=fetch(SOURCE);rates=parse_rates(raw)
    except (requests.RequestException,ValueError,KeyError,OSError):error='ECB unavailable; exact completed intervals retained'
    fx=build_snapshot(load(OUT/'fx.json',{}),intervals,rates,asof,hashlib.sha256(raw).hexdigest() if raw else None,error)
    save(OUT/'fx.json',fx)
    for key,spec in meta.items():
        for metric in METRICS:save(OUT/f'company_{key}_{metric}.json',document(key,metric,spec,state['companies'][key],fx))
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'state.json',state)
    print('Published 24 solar financial charts;',len(fx['missing']),'missing FX intervals',flush=True)
    return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true');parser.add_argument('--bootstrap',action='store_true');parser.add_argument('--asof')
    args=parser.parse_args();collect(args.offline,args.bootstrap,args.asof)

"""Free SEC accounts and completed-session company/ETF prices for drones."""
import argparse,datetime as dt,json,time
from pathlib import Path
import requests
from fetch_cpu_companies import load,save
from drone_sources import METRICS,accounts,prices,indexed

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/drone';CACHE=ROOT/'.cache/drone'


def financial_document(key,metric,meta,cohort):
    label=METRICS[metric];views={}
    for kind,title in [('quarter','분기'),('annual','연간'),('transition','전환기 8개월')]:
        rows=[r for r in cohort['rows'] if r['kind']==kind]
        if kind=='transition' and not rows:continue
        actual={r['date']:r for r in rows};axis=set(actual)
        for a,b in zip(rows,rows[1:]):
            if kind=='quarter' and (dt.date.fromisoformat(b['start'])-dt.date.fromisoformat(a['date'])).days>40:
                axis.add((dt.date.fromisoformat(a['date'])+dt.timedelta(days=1)).isoformat())
        refs={r['date']:dict(url=r['refs'][metric]['url'],label=r['period'],
              supporting_sources=[dict(url=c['url'],label=c['start']+' ~ '+c['end']) for c in r['refs'][metric]['components']],
              source_separator=' − ' if len(r['refs'][metric]['components'])>1 else ' / ') for r in rows if metric in r}
        valid=[r for r in rows if metric in r];last=valid[-1] if valid else None
        lookup={(r['regime'],r['year'],r['quarter']):r['date'] for r in rows}
        views[kind]=dict(label=title,frequency='quarterly' if kind=='quarter' else 'yearly' if kind=='annual' else 'irregular',
            frequency_label='분기 · 실제 회사 결산일' if kind=='quarter' else '연간 · 완결 회계연도' if kind=='annual' else '회계연도 변경 · 8개월 실적',
            quarter_labels=kind=='quarter',year_labels=kind=='annual',annual_axis=kind=='annual',period_labels={r['date']:r['period'] for r in rows},
            series={label:[[date,actual.get(date,{}).get(metric)] for date in sorted(axis)]} if valid else {},point_sources=refs,
            point_notes={r['date']:[r['period'],r['start']+' ~ '+r['date'],'공시 원통화: USD 백만',r['refs'][metric]['tag'],r['refs'][metric]['calculation']] for r in valid},
            source_url=last['refs'][metric]['url'] if last else meta['source_url'],updated=last['date'] if last else '',
            quarterly_revenue_summary=kind=='quarter' and metric=='revenue',quarterly_profit_summary=kind=='quarter' and metric!='revenue',change_mode='none',
            comparison_dates={r['date']:dict(year_ago=lookup.get((r['regime'],r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['regime'],r['year']-(r['quarter']==1),r['quarter']-1 or 4))) for r in rows} if kind=='quarter' else {},
            empty_message=title+' '+label+' 공시 이력이 아직 확보되지 않았습니다.')
    return dict(id=f'company_{key}_{metric}',name=meta['name']+' · '+label,unit='USD 백만',company_kpi=True,span_gaps=False,compact_ticks=True,
        source='SEC · 연결 재무제표',fetched=cohort['fetched'],description=meta['scope'],
        basis_details=[dict(label='사업·연결 범위',value=meta['note']),dict(label='손익·기간 기준',value='매출·영업손익은 보고 연결 기준입니다. 순손익은 NetIncomeLoss(지배주주), AeroVironment는 보통주 귀속을 우선합니다. 해당 태그가 없는 기간은 ProfitLoss(비지배지분 포함) 공시를 사용하며 포인트 메모의 태그로 구분합니다. 조정 EBITDA로 대체하지 않습니다. Red Cat의 미공시 영업 소계는 동일 공시의 매출총이익−영업비용으로 계산합니다. 4분기 차분은 동일 회계연도·동일 태그 누적만 사용하고 연간을 4로 나누지 않습니다. 주식보상·인수 비용과 금융상품 평가 등 일회성 손익이 반영될 수 있습니다.'),dict(label='수집 확인',value=cohort['checked'])],
        collection_status=dict(ok=cohort['ok'],checked=cohort['checked'],message='SEC 조회 완료' if cohort['ok'] else '조회 실패 · 마지막 성공 이력 유지'),
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})


def price_document(identifier,name,ticker,rows,asof,ok,source_url,scope):
    label=ticker+' 수정종가'
    baseline=rows[0][2]
    return dict(id=identifier,name=name+' · 가격',unit='USD/주',frequency='daily',frequency_label='일별 · 완료 거래일',
        source='Yahoo Finance · '+ticker,source_url=f'https://finance.yahoo.com/quote/{ticker}/history/',updated=rows[-1][0],fetched=asof,
        series={label:[[d,round(a,6)] for d,c,a in rows]},default_series=[label],span_gaps=False,change_mode='none',
        description=scope+' 최근 완료 거래일만 표시합니다. 기본은 분할·현금 분배 등을 반영한 Yahoo 수정종가이며 거래소 실시간 체결가·운용사 NAV와 다릅니다.',
        basis_details=[dict(label='기업·운용사 원문',value=source_url),dict(label='가격 이력·조정',value='종가 보기 역시 Yahoo의 과거 분할 조정 기준을 따릅니다. 수정종가 기반 지수는 가격 제공자의 배당·분배금 조정을 반영한 비교용 지수이며 실제 계좌 수익률을 보장하지 않습니다. 역분할이 잦은 소형주는 과거 가격 수준을 함께 확인합니다.')],
        collection_status=dict(ok=ok,checked=asof,message='가격 조회 완료' if ok else '가격 조회 실패 · 마지막 성공 이력 유지'),
        default_view='adjusted',series_views={'adjusted':dict(label='수정종가'),'close':dict(label='종가',series={ticker+' 종가':[[d,round(c,6)] for d,c,a in rows]},default_series=[ticker+' 종가']),
            'indexed':dict(label='처음=100',unit='지수',series={ticker:[[d,round(a/baseline*100,6)] for d,c,a in rows]},default_series=[ticker])})


def comparison(identifier,name,histories,asof):
    baseline,series=indexed(histories)
    return dict(id=identifier,name=name,unit='지수',frequency='daily',frequency_label='일별 · 동일 기준일=100',series=series,default_series=list(series),span_gaps=False,change_mode='none',
        source='Yahoo Finance · 수정종가',source_url='https://finance.yahoo.com/',updated=max(points[-1][0] for points in series.values()),fetched=asof,
        description=f'모든 종목에 가격이 존재하는 첫 공통 거래일 {baseline}을 100으로 맞췄습니다. 공통일 이전은 개별 종목 카드에서 확인합니다. ETF 편입 범위·분배금과 기업의 사업 범위가 다르며 산업 매출 지수가 아닙니다.',baseline_date=baseline)


def collect(offline=False,asof=None):
    now=dt.datetime.now(dt.timezone.utc);asof=asof or now.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    universe=load(ROOT/'manual/drone_universe.json',{});state=load(OUT/'state.json',dict(companies={},prices={}))
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    CACHE.mkdir(parents=True,exist_ok=True)
    def fetch(url,name,params=None):
        path=CACHE/(name+'.json')
        if offline:return load(path,{})
        r=session.get(url,params=params,timeout=40);r.raise_for_status();payload=r.json();save(path,payload);return payload
    for key,meta in universe['companies'].items():
        prior=state['companies'].get(key,{})
        try:
            payload=fetch(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{meta["cik"]:010d}.json',key+'_facts')
            subs=fetch(f'https://data.sec.gov/submissions/CIK{meta["cik"]:010d}.json',key+'_submissions')
            rows=accounts(payload,subs,meta,asof)
            if prior.get('rows') and max(r['date'] for r in rows)<max(r['date'] for r in prior['rows']):raise ValueError('Financial source regressed')
            state['companies'][key]=dict(rows=rows,checked=asof,fetched=asof,ok=True)
            print(key,len(rows),'reporting periods',rows[-1]['date'],flush=True)
        except (requests.RequestException,ValueError,KeyError,OSError) as e:
            if not prior.get('rows'):raise RuntimeError(key+' has no verified accounts') from e
            state['companies'][key]=dict(prior,checked=asof,ok=False);print(key,'retained prior accounts',type(e).__name__,flush=True)
        time.sleep(.2)
    targets=[dict(meta,id=key) for key,meta in universe['companies'].items()]+universe['etfs']
    docs={};histories={}
    for meta in targets:
        ticker=meta['ticker'];prior=state['prices'].get(ticker,{})
        try:
            raw=fetch(f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}',ticker+'_price_daily',dict(period1=1388534400,period2=int(now.timestamp()),interval='1d',events='splits,div'))
            rows=prices(raw,ticker,asof,int(now.timestamp()))
            floor=meta.get('inception',max('2014-01-01',meta.get('minimum_start','2014-01-01')));rows=[r for r in rows if r[0]>=floor]
            if not rows:raise ValueError('Missing price history')
            state['prices'][ticker]=dict(rows=rows,checked=asof,fetched=asof,ok=True)
        except (requests.RequestException,ValueError,KeyError,OSError) as e:
            if not prior.get('rows'):raise RuntimeError(ticker+' has no verified prices') from e
            state['prices'][ticker]=dict(prior,checked=asof,ok=False);print(ticker,'retained prior prices',type(e).__name__,flush=True)
        history=state['prices'][ticker];histories[ticker]=history['rows']
        docs['price_'+meta['id']]=price_document('price_'+meta['id'],meta['name'],ticker,history['rows'],history['fetched'],history['ok'],meta['source_url'],meta['scope'])
        print(ticker,len(history['rows']),'daily completed sessions',history['rows'][-1][0],flush=True);time.sleep(.2)
    for key,meta in universe['companies'].items():
        for metric in METRICS:docs[f'company_{key}_{metric}']=financial_document(key,metric,meta,state['companies'][key])
    docs['etf_comparison']=comparison('etf_comparison','드론 ETF · 같은 날=100',{e['ticker']:histories[e['ticker']] for e in universe['etfs']},asof)
    docs['stock_comparison']=comparison('stock_comparison','드론 기업 · 같은 날=100',{c['ticker']:histories[c['ticker']] for c in universe['companies'].values()},asof)
    public=dict(universe,name='드론 기업·ETF',updated=asof,fetched=asof)
    public['companies']=[dict(meta,id=key,financial_end=max(r['date'] for r in state['companies'][key]['rows']),quarters=sum(r['kind']=='quarter' for r in state['companies'][key]['rows']),ok=state['companies'][key]['ok']) for key,meta in universe['companies'].items()]
    save(OUT/'universe.json',public)
    for key,doc in docs.items():save(OUT/(key+'.json'),doc)
    state['updated']=now.isoformat(timespec='seconds');save(OUT/'state.json',state)
    print('Published',len(docs),'drone charts',flush=True)
    return state


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--asof')
    args=parser.parse_args();collect(args.offline,args.asof)

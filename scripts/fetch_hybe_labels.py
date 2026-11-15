"""Publish HYBE label financials and an evidence-backed exclusive-contract roster."""
import argparse,copy,datetime as dt,hashlib,re
from hybe_label_sources import ROOT,CACHE,Client,annual_and_quarters,compact,entity_key,financial_tables,filings,load,ownership,roster,save,section

OUT=ROOT/'data/entertainment/hybe_labels.json'
META=ROOT/'manual/entertainment/hybe-labels.json'
CONTRACTS=ROOT/'manual/entertainment/hybe-contracts.json'
NOTE='종속기업 요약 재무정보의 법인별 매출입니다. 내부거래 제거 전이며 지역 연결법인과 산하 레이블이 겹칠 수 있어 합계를 하이브 연결 매출로 보지 않습니다. 특정 그룹별 매출로 배분하지 않습니다.'
def today():return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
def date_end(year,q):return f'{year}-{q*3:02d}-{31 if q in [1,4] else 30}'
def eligible(row,meta):
    formed=next((l.get('formed') for l in meta['labels'] if l['id']==row['entity']),None)
    if formed and row['date']<formed:return False
    # Before incorporation/acquisition, comparative tables can contain a
    # placeholder row of zero assets, liabilities and income. It is not an
    # observed operating history. An actual current-period zero is retained.
    return not(row.get('comparative') and all(row.get(k) in [None,0] for k in ['assets','liabilities','revenue','net_income']))

def collect(client,meta,state,old):
    reports=[r for r in filings(state) if r['year']>=2020 and r['filed']<=today()]
    aliases={entity_key(a):s['id'] for s in meta['labels'] for a in s['aliases']}
    raw=copy.deepcopy(old.get('observations',[]));roster_data=None;errors=[];successful=[];latest=reports[-1]
    report_cache=load(CACHE/'reports.json',{})
    signature=hashlib.sha256(('parser-v2'+str(meta['labels'])).encode()).hexdigest()
    for report in reports:
        key=report['receipt']
        refresh=report==latest
        try:
            cached=report_cache.get(key)
            if cached and cached.get('signature')==signature and not client.refresh and (client.offline or not refresh):
                rows=cached['rows']
            else:
                html,url=section(client,key,'notes',refresh=refresh);tables=financial_tables(html);holdings=ownership(html);rows=[]
                for offset,table in enumerate(tables[:2]):
                    year=report['year']-offset
                    for item in table:
                        label=aliases.get(entity_key(item['name']))
                        if not label:continue
                        rows.append(dict(item,entity=label,year=year,quarter=report['quarter'],date=date_end(year,report['quarter']),
                            ownership=holdings.get(entity_key(item['name'])) if offset==0 else None,
                            comparative=bool(offset),filed=report['filed'],receipt=key,source_url=url,report_date=report['date']))
                if len({r['entity'] for r in rows if not r['comparative']})<2:raise ValueError('Subsidiary note coverage unexpectedly small')
                report_cache[key]=dict(rows=rows,signature=signature)
            raw=[r for r in raw if r['receipt']!=key]+rows;successful.append(report)
            print('HYBE',report['date'],len(rows),'entity observations',flush=True)
            if report==latest:
                html,url=section(client,key,'contracts',refresh=refresh)
                roster_data=dict(report_date=report['date'],filed=report['filed'],source_url=url,groups=roster(html))
        except (ValueError,OSError,KeyError) as error:
            errors.append(dict(receipt=key,date=report['date'],error=str(error)));print('HYBE',report['date'],'retained previous disclosure:',str(error),flush=True)
    save(CACHE/'reports.json',report_cache)
    if roster_data is None:roster_data=old.get('roster')
    if not raw or not roster_data:raise ValueError('No verified HYBE label financials or roster')
    return [r for r in raw if eligible(r,meta)],roster_data,errors,successful

def contract_rows(meta,roster_data,manual):
    labels={entity_key(a):s['id'] for s in meta['labels'] for a in s['aliases']}
    records={compact(a).lower():r for r in manual['artists'] for a in [r['name']]+r['aliases']}
    rows=[]
    for item in roster_data['groups']:
        key=compact(item['name']).lower();review=records.get(key)
        row=copy.deepcopy(review) if review else dict(id='unreviewed_'+hashlib.sha256(key.encode()).hexdigest()[:12],name=item['name'],category='unreviewed',first_signed=None,expires=None)
        row.update(label=labels.get(entity_key(item['company']),entity_key(item['company'])),label_original=item['company'],members=item['members'],current=True,
            roster_date=roster_data['report_date'],roster_source=roster_data['source_url'],reviewed=manual['reviewed'],review_needed=review is None)
        row.setdefault('status','공시 명단 확인');row.setdefault('events',[])
        rows.append(row)
    for record in manual['artists']:
        if record.get('former'):rows.append(dict(copy.deepcopy(record),current=False,members=[],reviewed=manual['reviewed'],events=record.get('events',[])))
    return rows

def chart_doc(id,name,labels,views,source_url,fetched):
    charts={}
    for basis,label in [('quarter','분기'),('annual','연간'),('cumulative','누적')]:
        rows=views[basis];dates=sorted({r['date'] for r in rows});series={}
        for company in labels:
            amounts={r['date']:r['revenue'] for r in rows if r['entity']==company['id']}
            if not any(v is not None for v in amounts.values()):continue
            series[company['name']]=[[d,None if amounts.get(d) is None else round(amounts[d]/100,6)] for d in dates]
        charts[basis]=dict(label=label,frequency='yearly' if basis=='annual' else 'quarterly',quarter_labels=basis!='annual',year_labels=basis=='annual',annual_axis=basis=='annual',
            period_labels={d:(f"FY{d[:4]}" if basis=='annual' else f"{d[:4]} Q{(int(d[5:7])+2)//3}"+(' 누적' if basis=='cumulative' else '')) for d in dates},
            series=series,default_series=list(series),updated=max((d for values in series.values() for d,v in values if v is not None),default=''),source_url=source_url,
            quarterly_revenue_summary=basis=='quarter',description=NOTE+(' 누적은 해당 연도 1월~각 분기 말입니다.' if basis=='cumulative' else ' 분기는 같은 법인의 당해 연도 누적−직전 누적으로 계산하며 중간 누적이 없으면 비워 둡니다.' if basis=='quarter' else ' 설립·편입 첫해는 일부 기간만 포함될 수 있습니다.'))
    doc=dict(id=id,name=name,company_kpi=True,unit='억원',source='DART · HYBE 연결 주석',source_url=source_url,fetched=fetched,span_gaps=False,
        full_range=True,table_limit=120,default_view='quarter',series_views=charts,
        basis_details=[dict(label='공시 기준',value=NOTE),dict(label='이력·연결 범위',value='현재 법인의 실제 공시 이력만 사용합니다. 빅히트뮤직은 2021년 물적분할 후 법인이며 과거 하이브 매출과 연결하지 않습니다. HYBE America 등은 산하 회사를 포함하는 지역 수치로 레이블과 중복될 수 있습니다.'),dict(label='순손익',value='상세 표의 순손익은 공시 당기순손익입니다. 영업이익으로 대체 표시하지 않습니다.')])
    doc.update(copy.deepcopy(charts['quarter']));doc.pop('label',None)
    return doc

def build(meta,manual,raw,roster_data,old,errors,offline=False):
    views=annual_and_quarters(raw);fetched=old.get('fetched',today()) if offline else today()
    doc=dict(id='hybe_labels',name='HYBE 레이블 매출·전속계약',unit='KRW 백만',updated=max(r['date'] for r in views['cumulative']),fetched=fetched,
        checked=old.get('checked',today()) if offline else today(),ok=not errors,errors=errors,source_url=max(views['cumulative'],key=lambda r:(r['date'],r['filed']))['source_url'],
        labels=copy.deepcopy(meta['labels']),observations=raw,financial_views=views,roster=roster_data,
        contracts_reviewed=manual['reviewed'],contract_method=manual['method'],contracts=contract_rows(meta,roster_data,manual),note=NOTE)
    if offline and old:doc.update(ok=old['ok'],errors=old.get('errors',[]))
    known={l['id'] for l in doc['labels']}
    for artist in doc['contracts']:
        if artist['current'] and artist['label'] not in known:
            doc['labels'].append(dict(id=artist['label'],name=artist['label_original'],kind='unreviewed',region='공시 명단',note='새 소속 법인 · 재무 매핑 추가 검토'))
            known.add(artist['label'])
    domestic=[s for s in meta['labels'] if s['region']=='한국'];foreign=[s for s in meta['labels'] if s['region']!='한국']
    doc['charts']=[chart_doc('hybe_domestic_labels_revenue','국내 레이블별 매출',domestic,views,doc['source_url'],fetched),chart_doc('hybe_overseas_labels_revenue','해외 레이블·지역법인 매출',foreign,views,doc['source_url'],fetched)]
    return doc

def validate(doc):
    if len([c for c in doc['contracts'] if c['current']])<8:raise ValueError('Artist roster incomplete')
    for basis,rows in doc['financial_views'].items():
        keys=[(r['entity'],r['date']) for r in rows]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate entity financial period')
        if any(r['filed']>today() or r['date']>today() for r in rows):raise ValueError('Future actual in disclosure')
    for row in doc['contracts']:
        if row.get('first_signed') and not row.get('date_source'):raise ValueError('Contract signing date lacks reviewed source')
        if row.get('expires') and not(row.get('date_source') or row['events']):raise ValueError('Contract end date lacks source')
        if any(e['date']>today() for e in row['events']):raise ValueError('Unpublished contract event')
    if not all(chart['series'] for chart in doc['charts']):raise ValueError('Empty label revenue chart')

def run(offline=False,refresh=False):
    old=load(OUT,{})
    try:
        meta=load(META);manual=load(CONTRACTS);client=Client(offline,refresh)
        raw,roster_data,errors,reports=collect(client,meta,load(ROOT/'data/entertainment/state.json'),old)
        doc=build(meta,manual,raw,roster_data,old,errors,offline);validate(doc)
        if old:
            previous_views=annual_and_quarters([r for r in old['observations'] if eligible(r,meta)])
            for basis in ['annual','quarter','cumulative']:
                before={(r['entity'],r['date']) for r in previous_views[basis]};after={(r['entity'],r['date']) for r in doc['financial_views'][basis]}
                if before-after:raise ValueError('Existing HYBE label history regressed')
        save(OUT,doc);print('Published HYBE labels:',len(doc['contracts']),'artist rows;',len(raw),'observations;',len(errors),'source errors',flush=True)
    except (ValueError,OSError) as error:
        if not old:raise
        old.update(ok=False,checked=today(),errors=[dict(error=str(error))]);save(OUT,old);print('Retained last successful HYBE labels:',str(error),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--offline',action='store_true');parser.add_argument('--refresh',action='store_true');args=parser.parse_args();run(args.offline,args.refresh)

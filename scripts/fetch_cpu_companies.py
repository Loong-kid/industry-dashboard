"""Quarterly CPU-company accounts from SEC Company Facts; reviewed business mix.

Consolidated GAAP accounts are not CPU-only sales. Fiscal quarter ends and source
filings are preserved. Cash PP&E is differenced within the same fiscal year only.
"""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/semicon'
CACHE = ROOT / '.cache/cpu'
COMPANIES = {
    'intel': dict(name='Intel', cik=50863, fiscal_start=1,
                  scope='연결 전체 · CPU·파운드리 등 포함',
                  note='Intel 전체 연결 기준이며 CPU 단독 실적이 아닙니다. 사업 매각·연결 범위 변경이 포함됩니다. CAPEX는 현금흐름표의 유형자산 취득 현금지출이며 발표자료의 Gross/Net CAPEX·보조금 차감·금융리스·파트너 분담액 기준과 다릅니다.'),
    'amd': dict(name='AMD', cik=2488, fiscal_start=1,
                scope='연결 전체 · CPU·GPU·Embedded 포함',
                note='AMD 전체 연결 기준입니다. Data Center에는 EPYC CPU 외 Instinct GPU 등이 포함되며 전체 매출을 CPU 매출로 해석하지 않습니다. CAPEX는 자체 유형자산 현금취득이며 외주 파운드리의 설비투자를 포함하지 않습니다.'),
    'arm': dict(name='Arm', cik=1973239, fiscal_start=4,
                scope='현재 상장 법인 연결 · IP·로열티 등 포함',
                note='현재 상장 Arm Holdings plc의 공개 분기 실적입니다. 3월 결산이며 FY는 종료 연도입니다. IP 라이선스·로열티를 포함한 연결 실적으로 실제 CPU 판매액이나 출하량이 아닙니다. 구 상장 법인과 SoftBank 비상장 시기의 연간 실적은 분기 이력에 이어 붙이지 않습니다. CAPEX는 유형자산 현금취득이며 무형자산 취득은 제외합니다.'),
}
TAGS = {
    'revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet'],
    'profit': ['OperatingIncomeLoss'],
    'capex': ['PaymentsToAcquirePropertyPlantAndEquipment'],
}


def today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()


def days(start, end):
    return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1


def load(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    os.replace(temporary, path)


def reference(fact, cik):
    accn = fact['accn']
    return dict(url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace("-", "")}/{accn}-index.html',
                filed=fact['filed'], start=fact['start'], end=fact['end'], tag=fact['tag'])


def parse_facts(payload, company, asof):
    if int(payload['cik']) != company['cik']:
        raise ValueError('SEC company mismatch')
    selected, all_facts = {}, {}
    for metric, tags in TAGS.items():
        values, facts = {}, []
        for priority, tag in enumerate(tags):
            for fact in payload['facts'].get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', []):
                if (not fact.get('start') or fact['end'] > asof or fact['filed'] > asof
                    or fact.get('form') not in ('10-K', '10-K/A', '10-Q', '10-Q/A', '20-F', '20-F/A', '6-K')
                    or not isinstance(fact['val'], (int,float)) or not math.isfinite(fact['val'])):
                    continue
                key = fact['start'], fact['end']
                rank = fact['filed'], -priority, fact['accn']
                facts.append(dict(fact, tag='us-gaap:'+tag, rank=rank))
                if key not in values or rank > values[key]['rank']:
                    values[key] = dict(fact, tag='us-gaap:'+tag, rank=rank)
        selected[metric] = values
        all_facts[metric] = facts
    anchors = {(s,e) for values in selected.values() for s,e in values if 350 <= days(s,e) <= 380}
    # Include unfinished 52/53-week fiscal years without using comparative fy tags.
    for values in selected.values():
        for start, end in values:
            actual = dt.date.fromisoformat(start)
            for year in (actual.year, actual.year+1):
                nominal = dt.date(year, company['fiscal_start'], 1)
                if abs((actual-nominal).days) <= 10:
                    finish = dt.date(year+1, company['fiscal_start'], 1)-dt.timedelta(days=1)
                    anchors.add((start, finish.isoformat()))
    rows = {}
    for start, finish in sorted(anchors):
        fy = int(finish[:4])
        for metric, values in selected.items():
            ends = sorted({end for s,end in values if start <= s <= end <= min(finish,asof)
                           and (75 <= days(s,end) <= 105 or s == start)})
            for end in ends:
                elapsed = days(start,end)
                quarter = round(elapsed/91.25)
                if not 1 <= quarter <= 4 or abs(elapsed-quarter*91.25) > 15:
                    continue
                direct = [f for (s,e),f in values.items() if e == end and s >= start and 75 <= days(s,e) <= 105]
                if direct:
                    fact = max(direct, key=lambda f:f['rank'])
                    value, refs = fact['val'], [reference(fact,company['cik'])]
                    quarter_start = fact['start']
                elif (start,end) in values and quarter > 1:
                    # Subtract the first published YTD vintage from its available
                    # prior YTD, rather than a later restated annual from an old Q3.
                    candidates = [f for f in all_facts[metric] if f['start']==start and f['end']==end]
                    fact = min(candidates,key=lambda f:(f['filed'],-f['rank'][1],f['accn']))
                    previous = [f for f in all_facts[metric] if f['start'] == start and f['end'] < end
                                and abs(days(start,f['end'])-(quarter-1)*91.25) <= 15
                                and 75 <= days(f['end'],end)-1 <= 105 and f['tag'] == fact['tag']
                                and f['filed'] <= fact['filed']]
                    if not previous:
                        continue
                    prior = max(previous, key=lambda f:(f['end'],f['rank']))
                    value = fact['val']-prior['val']
                    refs = [reference(fact,company['cik']), reference(prior,company['cik'])]
                    quarter_start = (dt.date.fromisoformat(prior['end'])+dt.timedelta(days=1)).isoformat()
                else:
                    continue
                if end < '2014-01-01' or (metric != 'profit' and value < 0):
                    continue
                row = rows.setdefault(end, dict(date=end, start=quarter_start, year=fy, quarter=quarter, refs={}))
                if (row['year'],row['quarter']) != (fy,quarter):
                    raise ValueError('Ambiguous fiscal quarter')
                row[metric] = value/1e6
                row['refs'][metric] = dict(refs[0], components=refs,
                    calculation='reported quarter' if len(refs)==1 else 'same fiscal-year YTD minus prior YTD')
    result = [r for _,r in sorted(rows.items()) if r.get('revenue') is not None]
    if not result or not all(any(r.get(m) is not None for r in result) for m in TAGS):
        raise ValueError('Incomplete quarterly accounts')
    periods = [(r['year'],r['quarter']) for r in result]
    if len(periods) != len(set(periods)):
        raise ValueError('Duplicate fiscal period')
    return result


def build_company(key, cohort):
    company = COMPANIES[key]
    rows = cohort['rows']
    labels = {r['date']:f"FY{r['year']} Q{r['quarter']}" for r in rows}
    lookup = {(r['year'],r['quarter']):r['date'] for r in rows}
    comparison = {r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),
                    quarter_ago=lookup.get((r['year']-(r['quarter']==1),(r['quarter']-2)%4+1))) for r in rows}
    # Explicit missing fiscal quarters keep lines from bridging gaps.
    axis = {r['date'] for r in rows}
    for year in range(rows[0]['year'], rows[-1]['year']+1):
        for quarter in range(1,5):
            if (year,quarter) in lookup or not (rows[0]['year'],rows[0]['quarter']) < (year,quarter) < (rows[-1]['year'],rows[-1]['quarter']):
                continue
            month = ((company['fiscal_start']-1+quarter*3-1)%12)+1
            calendar_year = year-(company['fiscal_start']!=1 and month>=company['fiscal_start'])
            following = dt.date(calendar_year+(month==12),month%12+1,1)
            axis.add((following-dt.timedelta(days=1)).isoformat())
    by_date = {r['date']:r for r in rows}
    docs = {}
    for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
        indicator = f'company_{key}_{metric}'
        series_label = '연결 GAAP 영업이익' if metric=='profit' else '유형자산 현금취득' if metric=='capex' else '연결 매출'
        refs = {r['date']:dict(url=r['refs'][metric]['url'], label=labels[r['date']],
            supporting_sources=[dict(url=ref['url'],label=ref['start']+' ~ '+ref['end']) for ref in r['refs'][metric]['components']],
            source_separator=' − ' if len(r['refs'][metric]['components'])==2 else ' / ') for r in rows if metric in r['refs']}
        latest = next(r for r in reversed(rows) if r.get(metric) is not None)
        docs[indicator] = dict(id=indicator,name=company['name']+' · '+title,unit='USD 백만',frequency='quarterly',
            frequency_label='분기 · SEC 공시',quarter_labels=True,period_labels=labels,comparison_dates=comparison,
            updated=latest['date'],fetched=cohort['fetched'],source='SEC · '+company['name']+' 공식 공시',
            source_url=latest['refs'][metric]['url'],description=company['scope']+'. '+{
                'revenue':'회사 전체 연결 매출이며 CPU 단독 매출이 아닙니다. 인수·매각 등 연결 범위 변경을 포함합니다.',
                'profit':'회사 전체 연결 GAAP 영업이익입니다. 조정 영업이익과 구분합니다.',
                'capex':'현금흐름표의 유형자산 취득 현금지출입니다. 발표자료의 총·순 CAPEX와 기준이 다를 수 있습니다.'}[metric],
            series={series_label:[[date,by_date.get(date,{}).get(metric)] for date in sorted(axis)]},
            default_series=[series_label],span_gaps=False,point_sources=refs,table_limit=100,company_kpi=True,
            quarterly_revenue_summary=metric!='profit',quarterly_profit_summary=metric=='profit',
            basis_details=[dict(label='회사별 범위·CAPEX 정의',value=company['note']),
                dict(label='회계 분기·차분 기준',value='실제 분기 종료일을 사용합니다. 직접 공시 분기는 최신 비교 수치를 반영합니다. 차분 분기는 최초 누적 공시와 당시 확인 가능한 동일 회계연도·동일 태그의 직전 누적을 사용하며, 이후 연간 재분류를 과거 9개월 수치와 혼합하지 않습니다. 공시 시점의 기준 차이로 이후 재작성 연간 합계와 다를 수 있습니다.'),
                dict(label='갱신 확인',value=cohort['checked']+' · '+('정상' if cohort['ok'] else '확인 실패 · 마지막 성공 자료 유지'))])
        if not cohort['ok']:
            docs[indicator]['collection_status']=dict(ok=False,checked=cohort['checked'],message='원문 확인 실패 · 마지막 성공 자료와 기준일을 유지합니다.')
    return docs


def build_segments(snapshot):
    docs = {}
    for key,company in snapshot['companies'].items():
        rows = sorted(company['quarters'],key=lambda r:r['date'])
        id = f'company_{key}_business'
        # Anchor to the full observed quarter axis, retaining unreviewed gaps.
        dates = []
        current = dt.date.fromisoformat(rows[0]['date'])
        while current.isoformat() <= rows[-1]['date']:
            dates.append(current.isoformat())
            month = current.month+3
            year = current.year+(month-1)//12
            month = (month-1)%12+1
            current = dt.date(year+(month==12),month%12+1,1)-dt.timedelta(days=1)
        # Actual week-based ends replace calendar placeholders in matching quarters.
        for row in rows:
            dates = [d for d in dates if d[:4]!=row['date'][:4] or (int(d[5:7])-1)//3 != (int(row['date'][5:7])-1)//3]
            dates.append(row['date'])
        by_date = {r['date']:r for r in rows}
        for row in rows:
            if row['date'] > snapshot['reviewed'] or row['source_date'] > snapshot['reviewed']:
                raise ValueError('Future business observation')
        labels = {r['date']:r['period'] for r in rows}
        docs[id] = dict(id=id,name=COMPANIES[key]['name']+' · '+company['title'],unit='USD 백만',frequency='quarterly',
            frequency_label='분기 · 공식 IR 검토',quarter_labels=True,period_labels=labels,updated=rows[-1]['date'],
            fetched=snapshot['reviewed'],manual=True,source='기업 공식 실적 발표',source_url=rows[-1]['source_url'],
            description=company['note']+' 원문 대조한 최근 분기만 제공합니다. 미확인 기간은 채우지 않습니다.',
            series={label:[[date,by_date.get(date,{}).get(field)] for date in sorted(set(dates))] for field,label in company['fields'].items()},
            default_series=list(company['fields'].values()),span_gaps=False,change_mode='none',
            point_sources={r['date']:dict(url=r['source_url'],label=r['period'],pdf_page=r.get('pdf_page')) for r in rows},
            basis_details=[dict(label='검토 기준일',value=snapshot['reviewed'])])
    return docs


def collect(offline=False):
    asof=today()
    state=load(OUT/'cpu_state.json',dict(companies={}))
    CACHE.mkdir(parents=True,exist_ok=True)
    if not offline:
        session=requests.Session()
        session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
        for key,company in COMPANIES.items():
            prior=state['companies'].get(key,{})
            try:
                response=session.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{company["cik"]:010d}.json',timeout=45)
                response.raise_for_status()
                rows=parse_facts(response.json(),company,asof)
                if prior.get('rows') and rows[-1]['date'] < prior['rows'][-1]['date']:
                    raise ValueError('Source regressed')
                state['companies'][key]=dict(rows=rows,checked=asof,fetched=asof,ok=True)
                (CACHE/(key+'_facts.json')).write_bytes(response.content)
                print(key,len(rows),'quarters',rows[0]['date'],'to',rows[-1]['date'])
            except Exception as error:
                if not prior.get('rows'):
                    raise RuntimeError(key+': no successful data') from error
                state['companies'][key]=dict(prior,checked=asof,ok=False)
                print(key,'retained previous data:',type(error).__name__)
            time.sleep(.4)
    docs={}
    for key in COMPANIES:
        docs.update(build_company(key,state['companies'][key]))
    docs.update(build_segments(load(ROOT/'manual/cpu_segments.json',{})))
    save(OUT/'cpu_state.json',state)
    for id,doc in docs.items():
        save(OUT/(id+'.json'),doc)
    print('Published',len(docs),'CPU company charts')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--offline',action='store_true')
    collect(parser.parse_args().offline)

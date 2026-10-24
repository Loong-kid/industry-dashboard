"""CPU-company accounts and business history from public SEC disclosures.

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
from company_period_views import add_period_views
from cpu_business_history import collect_business

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
    'qualcomm': dict(name='Qualcomm', cik=804328, fiscal_start=10,
                scope='전사 연결 · Snapdragon·통신칩·특허 라이선스 포함',
                tags={'capex':['PaymentsToAcquireProductiveAssets']},capex_label='회사 공시 CAPEX',
                capex_description='회사 현금흐름표에 공시된 Capital expenditures입니다. 타사의 유형자산 취득 항목과 범위가 다를 수 있습니다.',
                note='Qualcomm 전사 연결 기준이며 Snapdragon CPU 단독 실적이 아닙니다. QCT 반도체 사업과 QTL 특허 라이선스를 포함합니다. 9월 결산의 실제 52/53주 종료일을 사용합니다. CAPEX는 현금흐름표의 Capital expenditures이며 외주 파운드리 투자를 포함하지 않습니다. Snapdragon PC 매출·이익은 별도로 추정하지 않습니다.'),
    'apple': dict(name='Apple', cik=320193, fiscal_start=10,
                scope='Apple 전사 연결 · Apple Silicon 별도 실적 미공개',
                note='Apple Silicon은 별도 공시 사업부가 아닙니다. 매출·GAAP 영업이익·CAPEX는 Apple 전사 연결 실적이며 iPhone·Mac·iPad·서비스 등을 포함합니다. 2014년부터의 전사 이력에는 Mac용 Apple Silicon 전환 이전도 포함됩니다. 9월 결산의 실제 52/53주 종료일을 보존합니다. CAPEX는 전사 유형자산 현금취득으로 Apple Silicon 설계·생산 전용 투자액이 아닙니다. Mac·iPad 제품 매출을 칩 매출로 환산하지 않습니다.'),
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
    return dict(url=fact.get('source_url') or f'https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace("-", "")}/{accn}-index.html',
                filed=fact['filed'], start=fact['start'], end=fact['end'], tag=fact.get('source_tag',fact['tag']))


def parse_facts(payload, company, asof, tags_by_metric=None):
    if int(payload['cik']) != company['cik']:
        raise ValueError('SEC company mismatch')
    selected, all_facts = {}, {}
    metrics=tags_by_metric or TAGS
    for metric, tags in metrics.items():
        tags=company.get('tags',{}).get(metric,tags)
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
                    if not previous and tags_by_metric is not None:
                        for candidate in sorted(candidates,key=lambda f:f['rank']):
                            compatible=[f for f in all_facts[metric] if f['start']==start and f['end']<end
                                and abs(days(start,f['end'])-(quarter-1)*91.25)<=15
                                and 75<=days(f['end'],end)-1<=105 and f['filed']<=candidate['filed']]
                            if compatible:
                                fact,previous=candidate,compatible;break
                    if not previous:continue
                    prior = max(previous, key=lambda f:(f['end'],f['rank']))
                    if tags_by_metric is not None:
                        # Prefer a restated business basis only when its prior YTD
                        # reconciles to all of the preceding reported quarters.
                        # This handles AMD's Client reclassification without mixing
                        # an old Client+Gaming comparative with the new Client total.
                        for candidate in sorted(candidates,key=lambda f:f['rank'],reverse=True):
                            prior_candidates=[f for f in all_facts[metric] if f['start']==start and f['end']<end
                                and abs(days(start,f['end'])-(quarter-1)*91.25)<=15
                                and 75<=days(f['end'],end)-1<=105 and f['filed']<=candidate['filed']]
                            if not prior_candidates:continue
                            prior_candidate=max(prior_candidates,key=lambda f:(f['end'],f['rank']))
                            direct_quarters={}
                            for f in all_facts[metric]:
                                if not start<=f['start']<=f['end']<=prior_candidate['end'] or f['filed']>candidate['filed'] or not 75<=days(f['start'],f['end'])<=105:continue
                                q=round(days(start,f['end'])/91.25)
                                if q not in direct_quarters or f['rank']>direct_quarters[q]['rank']:direct_quarters[q]=f
                            if set(direct_quarters)!=set(range(1,quarter)):continue
                            if abs(sum(f['val'] for f in direct_quarters.values())-prior_candidate['val'])>1:continue
                            if candidate['val']<prior_candidate['val']:continue
                            fact,prior=candidate,prior_candidate
                            break
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
    result = [r for _,r in sorted(rows.items()) if any(r.get(m) is not None for m in metrics)]
    if tags_by_metric is None:result=[r for r in result if r.get('revenue') is not None]
    if not result or (tags_by_metric is None and not all(any(r.get(m) is not None for r in result) for m in TAGS)):
        raise ValueError('Incomplete quarterly accounts')
    periods = [(r['year'],r['quarter']) for r in result]
    if len(periods) != len(set(periods)):
        raise ValueError('Duplicate fiscal period')
    return result


def parse_annual(payload,company,asof,tags_by_metric=None):
    if int(payload['cik'])!=company['cik']:raise ValueError('SEC company mismatch')
    rows={}
    for metric,tags in (tags_by_metric or TAGS).items():
        tags=company.get('tags',{}).get(metric,tags)
        candidates={}
        for priority,tag in enumerate(tags):
            for fact in payload['facts'].get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[]):
                if not fact.get('start') or fact['end']<'2014-01-01' or fact['end']>asof or fact['filed']>asof:continue
                if not 350<=days(fact['start'],fact['end'])<=380 or fact.get('form') not in ('10-K','10-K/A','20-F','20-F/A','6-K'):continue
                rank=fact['filed'],-priority,fact['accn']
                if fact['end'] not in candidates or rank>candidates[fact['end']]['rank']:
                    candidates[fact['end']]=dict(fact,tag='us-gaap:'+tag,rank=rank)
        for end,fact in candidates.items():
            row=rows.setdefault(end,dict(date=end,year=int(end[:4]),refs={}))
            row[metric]=fact['val']/1e6
            row['refs'][metric]=dict(reference(fact,company['cik']),components=[reference(fact,company['cik'])],calculation='reported annual')
    return [r for _,r in sorted(rows.items())]


def annual_view(rows,fields,note):
    dates=[r['date'] for r in rows]
    refs={}
    for r in rows:
        sources={ref['url']:ref for metric,ref in r['refs'].items() if metric in fields}
        if sources:refs[r['date']]=dict(url=next(iter(sources)),label=f"FY{r['year']}",
            supporting_sources=[dict(url=url,label=f"FY{r['year']}") for url in sources],source_separator=' / ')
    return dict(series={label:[[r['date'],r.get(field)] for r in rows] for field,label in fields.items()},
                point_sources=refs,period_labels={r['date']:f"FY{r['year']}" for r in rows},
                source_url=refs[max(refs)]['url'] if refs else '',
                updated=max(dates) if dates else '',description=note+' 연간은 회사가 공시한 완결 회계연도 실적입니다. 진행 중인 연도의 누적값은 연간 값으로 표시하지 않습니다.')


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
        series_label = '연결 GAAP 영업이익' if metric=='profit' else company.get('capex_label','유형자산 현금취득') if metric=='capex' else '연결 매출'
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
                'capex':company.get('capex_description','현금흐름표의 유형자산 취득 현금지출입니다. 발표자료의 총·순 CAPEX와 기준이 다를 수 있습니다.')}[metric],
            series={series_label:[[date,by_date.get(date,{}).get(metric)] for date in sorted(axis)]},
            default_series=[series_label],span_gaps=False,point_sources=refs,table_limit=100,company_kpi=True,
            quarterly_revenue_summary=metric!='profit',quarterly_profit_summary=metric=='profit',
            basis_details=[dict(label='회사별 범위·CAPEX 정의',value=company['note']),
                dict(label='회계 분기·차분 기준',value='실제 분기 종료일을 사용합니다. 직접 공시 분기는 최신 비교 수치를 반영합니다. 차분 분기는 최초 누적 공시와 당시 확인 가능한 동일 회계연도·동일 태그의 직전 누적을 사용하며, 이후 연간 재분류를 과거 9개월 수치와 혼합하지 않습니다. 공시 시점의 기준 차이로 이후 재작성 연간 합계와 다를 수 있습니다.'),
                dict(label='갱신 확인',value=cohort['checked']+' · '+('정상' if cohort['ok'] else '확인 실패 · 마지막 성공 자료 유지'))])
        if not cohort['ok']:
            docs[indicator]['collection_status']=dict(ok=False,checked=cohort['checked'],message='원문 확인 실패 · 마지막 성공 자료와 기준일을 유지합니다.')
        add_period_views(docs[indicator],annual_view(cohort.get('annual',[]),{metric:series_label},docs[indicator]['description']))
    return docs


def build_segments(snapshot):
    """Legacy seed renderer; automatic collection uses build_business_history."""
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


def business_payload(key,cohort):
    return dict(cik=COMPANIES[key]['cik'],facts={'us-gaap':{field:dict(units={'USD':rows}) for field,rows in cohort['facts'].items()}})


def reconcile_apple_products(rows,facts):
    """Keep a derived Q4 on one reporting vintage across all product categories."""
    base=['iphone','ipad','mac','services']
    for row in rows:
        if row.get('_total') is None:continue
        tail=['wearables'] if row.get('wearables') is not None else ['other_products'] if row.get('other_products') is not None else ['ipod','accessories']
        if any(row.get(f) is None for f in base+tail):continue
        if abs(sum(row[f] for f in base+tail)-row['_total'])<.000001:continue
        if row['quarter']!=4:raise ValueError('Apple product sum differs from consolidated sales')
        annual={}
        for field,values in facts.items():
            if field=='_total':continue
            for f in values:
                if f['end']==row['date'] and 350<=days(f['start'],f['end'])<=380:
                    annual.setdefault((f['filed'],f['accn']),{})[field]=f
        resolved=False
        for _,current in sorted(annual.items(),reverse=True):
            tail=['wearables'] if 'wearables' in current else ['other_products'] if 'other_products' in current else ['ipod','accessories']
            names=base+tail
            if any(f not in current for f in names):continue
            start=current['iphone']['start'];limit=current['iphone']['filed']
            previous={}
            for field in names:
                for f in facts[field]:
                    if f['start']==start and 260<=days(start,f['end'])<=290 and f['filed']<=limit:
                        previous.setdefault((f['filed'],f['accn']),{})[field]=f
            for _,prior in sorted(previous.items(),reverse=True):
                if any(f not in prior for f in names):continue
                values={f:(current[f]['val']-prior[f]['val'])/1e6 for f in names}
                if any(v<0 for v in values.values()) or abs(sum(values.values())-row['_total'])>.000001:continue
                for field,value in values.items():
                    components=[reference(dict(f,tag=f['source_tag']),COMPANIES['apple']['cik']) for f in (current[field],prior[field])]
                    row[field]=value
                    row['refs'][field]=dict(components[0],components=components,calculation='same reporting-basis annual minus nine months')
                resolved=True;break
            if resolved:break
        if not resolved:raise ValueError('Apple Q4 product vintages could not be reconciled')
    return rows


def build_business_history(cohorts,snapshot):
    docs={}
    for key,cohort in cohorts.items():
        meta=snapshot['companies'][key]
        fields={field:label for field,label in meta['fields'].items() if field in cohort['facts']}
        groups=[(f'company_{key}_business',meta['title'],fields,meta['note'])]
        if key=='qualcomm':
            groups.append(('company_qualcomm_royalty','QTL 라이선스·로열티 매출',{'qtl':'QTL · 라이선스 매출'},
                'QTL 특허 라이선스 사업 매출로 주로 휴대폰 판매 관련 로열티입니다. 순수 경상 로열티만 분리한 값은 아니며 계약 합의·과거기간 정산 등이 포함될 수 있습니다. QCT의 소프트웨어 관련 로열티·칩 매출과 구분합니다.'))
        for id,title,fields,note in groups:
            if not fields:continue
            payload=business_payload(key,cohort)
            metrics={field:[field] for field in fields}
            if key=='apple' and '_total' in cohort['facts']:metrics['_total']=['_total']
            rows=parse_facts(payload,COMPANIES[key],today(),metrics)
            if key=='apple':rows=reconcile_apple_products(rows,cohort['facts'])
            annual=parse_annual(payload,COMPANIES[key],today(),metrics)
            # Every fiscal quarter between first and last is explicit, even if null.
            lookup={(r['year'],r['quarter']):r['date'] for r in rows}
            bydate={r['date']:r for r in rows}
            axis=set(bydate)
            for year in range(rows[0]['year'],rows[-1]['year']+1):
                for q in range(1,5):
                    if (year,q) in lookup or not (rows[0]['year'],rows[0]['quarter'])<(year,q)<(rows[-1]['year'],rows[-1]['quarter']):continue
                    m=((COMPANIES[key]['fiscal_start']-1+q*3-1)%12)+1
                    y=year-(COMPANIES[key]['fiscal_start']!=1 and m>=COMPANIES[key]['fiscal_start'])
                    axis.add((dt.date(y+(m==12),m%12+1,1)-dt.timedelta(days=1)).isoformat())
            refs={}
            for r in rows:
                sources={}
                for field in fields:
                    for ref in r['refs'].get(field,{}).get('components',[]):sources[ref['url'],ref['start'],ref['end']]=ref
                if sources:
                    refs[r['date']]=dict(url=next(iter(sources))[0],label=f"FY{r['year']} Q{r['quarter']}",
                        supporting_sources=[dict(url=ref['url'],label=ref['start']+' ~ '+ref['end']) for ref in sources.values()],source_separator=' / ')
            doc=dict(id=id,name=COMPANIES[key]['name']+' · '+title,unit='USD 백만',frequency='quarterly',
                frequency_label='분기 · SEC 사업·제품 공시',quarter_labels=True,
                period_labels={r['date']:f"FY{r['year']} Q{r['quarter']}" for r in rows},
                updated=rows[-1]['date'],fetched=cohort['fetched'],source='SEC · 사업·제품별 공식 공시',source_url=refs[rows[-1]['date']]['url'],
                description=note,series={label:[[date,bydate.get(date,{}).get(field)] for date in sorted(axis)] for field,label in fields.items()},
                default_series=[label for field,label in fields.items() if field not in ('other_products','ipod','accessories')],
                point_sources=refs,span_gaps=False,change_mode='none',table_limit=100,
                basis_details=[dict(label='수집 범위',value='공시 원문의 사업·제품별 항목을 직접 수집합니다. 표준 API에서 빠진 세부 항목과 과거 주석 표를 포함합니다. 연간과 9개월 누적이 있는 경우 같은 회계연도 차분으로 4분기를 계산합니다.'),
                    dict(label='사업·제품 분류',value='보고서의 부문 재편·재분류를 반영한 비교 수치입니다. Apple 과거 iPod·Accessories·Other Products는 별도 시리즈로 남기며 현재 Wearables 분류와 이어 붙이지 않습니다.')])
            if not cohort['ok']:doc['collection_status']=dict(ok=False,checked=cohort['checked'],message='일부 과거 원문 확인 실패 · 확보된 공시 이력을 유지합니다.')
            docs[id]=add_period_views(doc,annual_view(annual,fields,note))
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
                annual=parse_annual(response.json(),company,asof)
                state['companies'][key]=dict(rows=rows,annual=annual,checked=asof,fetched=asof,ok=True)
                (CACHE/(key+'_facts.json')).write_bytes(response.content)
                print(key,len(rows),'quarters',rows[0]['date'],'to',rows[-1]['date'])
            except Exception as error:
                if not prior.get('rows'):
                    raise RuntimeError(key+': no successful data') from error
                state['companies'][key]=dict(prior,checked=asof,ok=False)
                print(key,'retained previous data:',type(error).__name__)
            time.sleep(.4)
        state['business']=collect_business(COMPANIES,state.get('business',{}),CACHE/'business',asof)
    docs={}
    for key in COMPANIES:
        docs.update(build_company(key,state['companies'][key]))
    docs.update(build_business_history(state['business'],load(ROOT/'manual/cpu_segments.json',{})))
    save(OUT/'cpu_state.json',state)
    for id,doc in docs.items():
        save(OUT/(id+'.json'),doc)
    print('Published',len(docs),'CPU company charts')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--offline',action='store_true')
    collect(parser.parse_args().offline)

"""Movie-company accounts with actual reporting dates and legal-entity scope."""
import calendar
import datetime as dt
import math
import xml.etree.ElementTree as ET

from fetch_cpu_companies import days, reference, build_company

SPECS = {
    'imax': dict(name='IMAX · IMAX', cik=921582, fiscal_start=1,
        scope='대형 화면 기술·콘텐츠·시스템 사업 연결',
        note='IMAX는 극장 전체를 소유하는 체인과 사업 모델이 다릅니다. 매출은 콘텐츠·시스템 판매·임대·유지보수 등을 포함하며 IMAX 박스오피스와 다릅니다. 현금 CAPEX 표시는 유형자산 현금취득이며, 별도 현금흐름 항목인 JRSA 장비 투자와 무형자산 취득은 포함하지 않습니다.'),
    'cnk': dict(name='Cinemark · CNK', cik=1385280, fiscal_start=1,
        scope='미국·중남미 극장 체인 연결',
        note='Cinemark Holdings 연결 실적입니다. 같은 공시에 함께 포함된 자회사 Cinemark USA의 수치와 합산하지 않습니다. LegalEntityAxis의 CnkMember를 원문에서 확인합니다. 매출은 입장권·매점·광고 등을 포함합니다.'),
    'amc': dict(name='AMC Entertainment · AMC', cik=1411579, fiscal_start=1,
        scope='미국·유럽 극장 체인 연결',
        tags={'capex':['PaymentsToAcquireProductiveAssets']},
        note='AMC Entertainment 연결 실적이며 방송사 AMC Networks와 다릅니다. 입장권·매점·기타 극장 매출을 포함하고, Carmike·Odeon 인수 등 연결 범위 변화가 있습니다. CAPEX는 현금흐름표 Capital expenditures로 표시된 PaymentsToAcquireProductiveAssets입니다.'),
    'mcs': dict(name='Marcus · MCS', cik=62234, fiscal_start=1,
        scope='극장·호텔/리조트 전사 연결',
        note='Marcus는 극장 외 호텔·리조트 사업을 포함합니다. 2015년 결산기 변경 전 5월 결산과 이후 12월 결산의 실제 분기를 구분합니다. 2015년 7개월 전환기는 비교 가능한 분기·연간 차트에 섞지 않습니다. 2025년은 370일의 전환 회계연도입니다.'),
    'ncmi': dict(name='National CineMedia · NCMI', cik=1377630, fiscal_start=1,
        scope='극장 내 스크린 광고 사업 연결',
        note='극장 스크린 광고 중심이며 배급사·극장 체인과 다릅니다. 2026년 9월 Captivate 인수 이후 사무실·주거용 광고도 포함합니다. 2023년 4월 11일~8월 7일 NCM LLC가 연결에서 제외됐다가 재편입돼 2023년 실적의 연결 범위가 다른 연도와 다릅니다. 공시 GAAP 수치를 그대로 표시하며 이를 정상화 실적으로 추정하지 않습니다.'),
}
TAGS = {
    'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet','SalesRevenueServicesNet'],
    'profit':['OperatingIncomeLoss'],
    'capex':['PaymentsToAcquirePropertyPlantAndEquipment'],
}
for key,spec in SPECS.items():
    spec.update(revenue_description='입장권·매점·광고·기술 서비스 등 해당 회사 전체 연결 매출입니다. 작품별 박스오피스와 구분합니다.',
        profit_description='회사 전체 연결 GAAP 영업이익이며 순이익·조정 EBITDA와 구분합니다.',
        capex_label='유형자산 현금취득' if key!='amc' else '회사 공시 현금 CAPEX',
        capex_description='현금흐름표의 유형자산 취득 현금지출입니다. 기업 인수·비현금 리스와 회사별 발표 총 투자액을 포함한 수치와 범위가 다를 수 있습니다.')
    if key=='imax':spec['capex_description']+=' IMAX의 JRSA 장비 투자와 무형자산 취득은 별도 항목으로 이 차트에 포함하지 않습니다.'


def fiscal_period(key,end):
    date=dt.date.fromisoformat(end)
    if key=='mcs' and '2015-05-29'<=end<='2015-12-31':return None
    candidates=[]
    for year in range(date.year-1,date.year+2):
        for q in range(1,5):
            if key=='mcs' and end<='2015-05-28':
                month=[8,11,2,5][q-1];calendar_year=year-(q<3)
            else:month=q*3;calendar_year=year
            nominal=dt.date(calendar_year,month,calendar.monthrange(calendar_year,month)[1])
            candidates.append((abs((date-nominal).days),year,q))
    distance,year,q=min(candidates)
    return (year,q) if distance<=15 else None


def facts_from_company(payload,key):
    spec=SPECS[key]
    if int(payload['cik'])!=spec['cik']:raise ValueError('Movie issuer identity mismatch')
    result=[]
    for metric,tags in TAGS.items():
        for priority,tag in enumerate(spec.get('tags',{}).get(metric,tags)):
            for row in payload['facts'].get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[]):
                if row.get('start'):
                    result.append(dict(row,metric=metric,tag='us-gaap:'+tag,priority=priority))
    return result


def cnk_instance(raw,filing):
    """Joint filer: only parent CnkMember, never the Cinemark USA member."""
    root=ET.fromstring(raw);contexts={};units={}
    for c in root.findall('{*}context'):
        ident=c.find('./{*}entity/{*}identifier')
        if ident is None or int(ident.text)!=SPECS['cnk']['cik']:continue
        members=[m.text.split(':')[-1] for m in c.findall('.//{*}explicitMember')]
        if members and set(members)!={'CnkMember'}:continue
        period={x.tag.rsplit('}',1)[-1]:x.text for x in c.findall('./{*}period/*')}
        if period.get('startDate'):contexts[c.get('id')]=period
    for u in root.findall('{*}unit'):
        units[u.get('id')]=[m.text.split(':')[-1] for m in u.findall('.//{*}measure')]
    names={tag:metric for metric,tags in TAGS.items() for tag in tags}
    result={}
    for f in root:
        tag=f.tag.rsplit('}',1)[-1];metric=names.get(tag);period=contexts.get(f.get('contextRef'))
        if not metric or not period or units.get(f.get('unitRef'))!=['USD']:continue
        try:value=float(f.text)
        except (ValueError,TypeError):continue
        if not math.isfinite(value):continue
        row=dict(start=period['startDate'],end=period['endDate'],val=value,
            metric=metric,tag='us-gaap:'+tag,source_tag=tag+' · Cinemark Holdings consolidated / CnkMember',
            source_url=filing['url'],accn=filing['accessionNumber'],filed=filing['filingDate'],form=filing['form'],priority=0)
        identity=(metric,row['start'],row['end'],tag)
        if identity in result and result[identity]['val']!=value:raise ValueError('Conflicting parent financial facts')
        result[identity]=row
    if not all(any(f['metric']==m for f in result.values()) for m in TAGS):raise ValueError('Missing parent financial statements')
    return list(result.values())


def accounts(key,facts,filings,asof):
    """Reported full quarters or actual same-start cumulative differences only."""
    spec=SPECS[key]
    valid=[f for f in facts if f.get('start') and f['end']<=asof and f['filed']<=asof
        and f['form'] in ('10-K','10-K/A','10-Q','10-Q/A') and isinstance(f['val'],(float,int)) and math.isfinite(f['val'])]
    ends={f['reportDate'] for f in filings if f['form'] in ('10-K','10-Q') and f['reportDate']>='2014-01-01' and f['filingDate']<=asof}
    rank=lambda f:(f['filed'],-f.get('priority',0),f['accn'])
    rows=[];annual=[]
    for end in sorted(ends):
        period=fiscal_period(key,end)
        if not period:continue
        fy,q=period;row=dict(date=end,year=fy,quarter=q,refs={});year=dict(date=end,year=fy,refs={})
        for metric in TAGS:
            fs=[f for f in valid if f['metric']==metric and f['end']==end]
            whole=[f for f in fs if 350<=days(f['start'],end)<=380 and f['form'].startswith('10-K')]
            if whole:
                f=max(whole,key=rank);ref=reference(f,spec['cik'])
                year[metric]=f['val']/1e6;year['refs'][metric]=dict(ref,components=[ref],calculation='reported complete fiscal year')
            direct=[f for f in fs if 75<=days(f['start'],end)<=110]
            parts=[]
            if direct:
                current=max(direct,key=rank);value=current['val'];parts=[current]
            else:
                for current in sorted(fs,key=lambda f:(f['filed'],f.get('priority',0),f['accn'])):
                    previous=[f for f in valid if f['metric']==metric and f['start']==current['start'] and f['tag']==current['tag']
                        and f['filed']<=current['filed'] and f['end']<end and 75<=days(f['end'],end)-1<=110
                        and fiscal_period(key,f['end'])==(fy,q-1)]
                    if previous:
                        prior=max(previous,key=rank);value=current['val']-prior['val'];parts=[current,prior];break
            if not parts or (metric!='profit' and value<0):continue
            refs=[reference(f,spec['cik']) for f in parts]
            row[metric]=value/1e6
            row.setdefault('start',parts[0]['start'] if len(parts)==1 else (dt.date.fromisoformat(parts[1]['end'])+dt.timedelta(days=1)).isoformat())
            row['refs'][metric]=dict(refs[0],components=refs,calculation='reported full fiscal quarter' if len(parts)==1 else 'same reporting start and taxonomy: cumulative minus prior cumulative')
        if row.get('revenue') is not None:rows.append(row)
        if year.get('revenue') is not None:annual.append(year)
    if len({(r['year'],r['quarter']) for r in rows})!=len(rows):raise ValueError('Duplicate movie fiscal quarter')
    if not rows or not annual or not all(any(m in r for r in rows) for m in TAGS):raise ValueError('Incomplete movie financial history')
    return rows,annual


def documents(key,cohort):
    docs=build_company(key,cohort,SPECS[key])
    for doc in docs.values():
        doc['basis_details'][1]['value']='실제 공시 분기 종료일과 회사 회계연도를 보존합니다. 직접 공시 분기 또는 동일 시작일·동일 태그·당시 공시 누적값의 차분만 사용합니다. 전환기의 짧은 기간을 정상 분기로 확대하거나 연간 실적을 4등분하지 않습니다.'
        if key=='imax' and doc['id'].endswith('_capex'):doc['name']='IMAX · 유형자산 현금취득 (JRSA 제외)'
        for date,comparison in doc['comparison_dates'].items():
            for field,bounds in [('year_ago',(340,385)),('quarter_ago',(65,115))]:
                previous=comparison.get(field)
                if previous and not bounds[0]<=days(previous,date)-1<=bounds[1]:comparison[field]=None
        if key=='mcs':
            for series in doc['series'].values():
                series.append(['2015-12-31',None]);series.sort(key=lambda p:p[0])
            doc['period_labels']['2015-12-31']='결산기 전환 · 7개월 기간 제외'
    return docs

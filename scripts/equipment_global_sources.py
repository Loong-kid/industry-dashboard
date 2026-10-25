"""Read issuer workbooks/reports into comparable fiscal accounts; never annual / 4."""
import calendar,io,re
from fetch_cpu_companies import ROOT,today,annual_view
from company_period_views import add_period_views

CACHE=ROOT/'.cache/equipment'
METADATA={
 'asml':dict(name='ASML',currency='EUR',fiscal_start=1,field='frontend',cik=937966,
     source='SEC · ASML US GAAP 공시',note='US GAAP 연결 기준이며 IFRS 손익과 혼합하지 않습니다. 분기는 공식 Q3 2026 금융제표의 실제 52/53주 종료일입니다. 연간은 SEC 20-F에서 자동 갱신하고 이미지형 분기 공시는 검토 스냅샷으로 보완합니다.'),
 'tel':dict(name='Tokyo Electron · TEL',currency='JPY',fiscal_start=4,field='frontend',
     source='Tokyo Electron 공식 결산자료·데이터북',note='일본 회계기준 연결 실적이며 FY는 종료 연도입니다. 손익 누적을 같은 회계연도 안에서 차분합니다. CAPEX는 연간 현금흐름표 유형자산 취득으로 연간 기본 표시합니다.'),
 'asm':dict(name='ASM International',currency='EUR',fiscal_start=1,field='frontend',
     source='ASM 공식 분기 보고서',note='IFRS 보고 영업이익(Operating result)을 사용하며 Adjusted operating result와 구분합니다. CAPEX는 유형자산 취득 현금지출로 자산화 개발비·무형자산 취득을 제외합니다. 연간은 같은 기준의 4개 분기를 모두 확보한 경우만 합산합니다.'),
 'screen':dict(name='SCREEN Holdings',currency='JPY',fiscal_start=4,field='frontend',
     source='SCREEN 공식 IR·발행사 결산자료 보존본',capex_label='회사 공시 설비투자액',
     note='일본 회계기준 연결 실적이며 인쇄·디스플레이 등 다른 사업도 포함합니다. SPE 부문 매출은 별도 지표입니다. 연간 설비투자액은 회사 정의이며 현금흐름표 유형자산 취득과 동일하게 취급하지 않습니다. 공식 홈페이지 접근 제한 구간은 발행사 결산자료 보존본과 확인한 IR 스냅샷을 사용합니다.'),
 'disco':dict(name='DISCO',currency='JPY',fiscal_start=4,field='packaging',fiscal_label_start=True,capex_label='회사 공시 CAPEX',
     source='DISCO 공식 분기 데이터북',note='일본 회계기준 연결 실적입니다. 회사의 FY는 시작 연도이므로 FY2026은 2027년 3월 결산입니다. CAPEX는 회사 데이터북 정의의 설비투자액입니다. 별도 출하액·매출은 연결 실적과 범위를 구분합니다.'),
 'besi':dict(name='Besi',currency='EUR',fiscal_start=1,field='packaging',
     source='Besi 공식 분기 실적',note='IFRS 보고 영업이익을 사용하고 조정 이익과 구분합니다. CAPEX는 Capital expenditures이며 별도 기재된 자산화 개발비와 투자부동산 취득을 제외합니다. 분기별 부속 표의 반올림 값과 상세 천 유로 금액을 구분합니다.'),
 'hanmi':dict(name='한미반도체',currency='KRW',fiscal_start=1,field='packaging',
     source='OpenDART · 한미반도체 연결 공시',note='K-IFRS 연결 매출·영업이익과 유형자산 취득 현금지출입니다. 연결 자료가 확인되는 보고서부터 표시하며 별도재무제표를 섞지 않습니다. 4분기는 연간−9개월, CAPEX는 같은 회계연도 누적 차분입니다.'),
 'camtek':dict(name='Camtek',currency='USD',fiscal_start=1,field='inspection',cik=1109138,
     source='Camtek 공식 분기 실적·SEC 20-F',note='US GAAP 연결 실적이며 non-GAAP 영업이익과 구분합니다. 분기 손익은 공식 발표 본문의 백만 달러 반올림 값입니다. CAPEX는 SEC 20-F 유형자산 현금취득으로 연간 기본 표시합니다.'),
 'advantest':dict(name='Advantest',currency='JPY',fiscal_start=4,field='testing',fiscal_label_start=True,
     source='Advantest 공식 IR·공식 내장 재무표',note='IFRS 연결 실적입니다. 회사의 FY는 시작 연도입니다. 누적 손익·CAPEX는 같은 회계연도 안에서 차분하고 4분기는 연간−9개월로 계산합니다. 전사 실적과 테스트 부문 실적을 구분합니다.'),
}


def numeric(text):
    text=str(text).replace(',','').replace('△','-').strip()
    if text in ('','—','–','-','None'):return None
    if text.startswith('(') and text.endswith(')'):text='-'+text[1:-1]
    return float(text)


def numbers(line):
    return [numeric(m) for m in re.findall(r'\(?-?\d[\d,]*(?:\.\d+)?\)?',line)]


def quarter_end(year,q,start=1):
    month=(start-1+q*3-1)%12+1
    calendar_year=year-(start!=1 and month>=start)
    return f'{calendar_year}-{month:02d}-{calendar.monthrange(calendar_year,month)[1]}'


def observation(year,q,start,values,url,note='보고된 분기',date=None):
    end=date or quarter_end(year,q,start)
    refs={k:dict(url=url,start=end,end=end,reviewed=today(),tag='issuer:'+k,calculation=note,
        components=[dict(url=url,start=end,end=end,label='종료일 '+end,tag='issuer:'+k)]) for k,v in values.items() if v is not None}
    return dict(date=end,year=year,quarter=q,refs=refs,**{k:v for k,v in values.items() if v is not None})


def annualize(rows,metrics=('revenue','profit','capex','orders')):
    result=[]
    for year in sorted({r['year'] for r in rows}):
        quarters={r['quarter']:r for r in rows if r['year']==year}
        if set(quarters)!={1,2,3,4}:continue
        annual=dict(date=quarters[4]['date'],year=year,refs={})
        for metric in metrics:
            if all(metric in quarters[q] for q in quarters):
                annual[metric]=sum(quarters[q][metric] for q in quarters)
                components=[c for q in sorted(quarters) for c in quarters[q]['refs'][metric]['components']]
                annual['refs'][metric]=dict(quarters[4]['refs'][metric],components=components,calculation='동일 회계연도 4개 분기 합계')
        if annual['refs']:result.append(annual)
    return result


def difference_cumulative(reports):
    """Amounts passed here are YTD, unlike already discrete workbook quarters."""
    by={(r['year'],r['quarter']):r for r in reports};rows=[];annual=[]
    for key,report in sorted(by.items()):
        year,q=key
        if q==4:annual.append(dict(report))
        row=dict(report,refs={});row={k:v for k,v in row.items() if k not in ('revenue','profit','capex')}
        for metric in ('revenue','profit','capex'):
            if metric not in report:continue
            prior=by.get((year,q-1),{})
            if q==1:row[metric]=report[metric];row['refs'][metric]=report['refs'][metric]
            elif metric in prior:
                row[metric]=report[metric]-prior[metric]
                row['refs'][metric]=dict(report['refs'][metric],calculation='동일 회계연도 누적−직전 누적',
                    components=report['refs'][metric]['components']+prior['refs'][metric]['components'])
        if any(k in row for k in ('revenue','profit','capex')):rows.append(row)
    return rows,annual


def parse_hanmi(raw):
    reports=[]
    for report in raw['reports']:
        fields=report['fields'];values={k:c['ytd'] for k,c in fields.items() if c['ytd'] is not None}
        row=observation(report['year'],report['quarter'],1,values,next(iter(fields.values()))['url'],date=report['date'])
        for k,c in fields.items():
            if k in row:row['refs'][k]=dict(c,start=report['date'],end=report['date'],components=[dict(c,start=report['date'],end=report['date'])])
        reports.append(row)
    rows,annual=difference_cumulative(reports)
    return dict(rows=rows,annual=annual,checked=raw['checked'],fetched=raw['checked'],ok=True)


def parse_disco(content,url):
    import openpyxl
    wb=openpyxl.load_workbook(io.BytesIO(content),read_only=True,data_only=True)
    qdata=list(wb['Quarterly'].values);adata=list(wb['Yearly'].values);rows=[];annual=[];fy=None
    if qdata[2][0]!='Net Sales' or qdata[5][0]!='Operating Income' or qdata[34][0]!='CAPEX':raise ValueError('DISCO source layout changed')
    for col in range(1,len(qdata[0])):
        if qdata[0][col]:fy=int(re.search(r'\d{4}',str(qdata[0][col]))[0])+1
        q=(col-1)%4+1;end=quarter_end(fy,q,4)
        if end<'2014-01-01' or end>today() or not isinstance(qdata[2][col],(int,float)):continue
        values={key:numeric(qdata[row][col]) for key,row in [('revenue',2),('profit',5),('capex',34),('shipments',28)]}
        rows.append(observation(fy,q,4,values,url))
    for col in range(1,len(adata[1])):
        if not adata[1][col]:continue
        fy=int(re.search(r'\d{4}',str(adata[1][col]))[0])+1
        if fy<2014:continue
        values={key:numeric(adata[row][col]) for key,row in [('revenue',2),('profit',5),('capex',15)]}
        if values['revenue'] is not None:annual.append(observation(fy,4,4,values,url,'공시 연간'))
    return rows,annual


def parse_asm(text,year,q,url):
    # Early reports order prior-year, prior-quarter, current; new reports current first.
    header=re.search(r'(?:EUR|€) million[^\n]*Q[1-4][^\n]*',text)
    if not header:raise ValueError('ASM financial table header missing')
    periods=re.findall(r'Q([1-4])\s+(20\d{2})',header[0])
    index=periods.index((str(q),str(year)))
    block=text[header.end():]
    values={}
    for key,label in [('revenue','Revenue'),('profit','Operating result'),('orders','New orders')]:
        match=re.search(r'^\s*'+label+r'\s+([^\n]+)',block,re.M)
        if match:
            nums=numbers(match[1])
            if ',' in match[1] and '.' not in match[1]:
                # In 2023 the headline has normalized profit only: use the
                # annex's reported operating result (prior/current quarter).
                values[key]=nums[1]/1000
            elif len(nums)>index:values[key]=nums[index]
    # Annex CF is expressly a three-month statement, current first in modern reports.
    match=re.search(r'^\s*Capital expenditures(?: of property, plant and equipment)?\s+([^\n]+)',text,re.M)
    if match:
        # First pair is discrete quarter; later pair is YTD. Pre-2025 annexes
        # use thousands even though the headline income table uses millions.
        nums=numbers(match[1]);value=nums[1] if index==len(periods)-1 else nums[0]
        unit_headers=re.findall(r'(?:€|EUR)\s*(thousand|million)',text[:match.start()],re.I)
        scale=1000 if unit_headers and unit_headers[-1].lower()=='thousand' else 1
        values['capex']=abs(value)/scale
    if not all(k in values for k in ('revenue','profit')):raise ValueError('ASM reported income missing')
    return observation(year,q,1,values,url)


def parse_besi(text,year,q,url):
    anchor=text.find('Consolidated Statements of Operations')
    if anchor<0:raise ValueError('Besi statement missing')
    block=text[anchor:];values={}
    for key,label in [('revenue','Revenue'),('profit','Operating income'),('capex','Capital expenditures')]:
        match=re.search(r'^\s*'+label+r'\s+([^\n]+)',block,re.M)
        if match:
            amount=numbers(match[1])[0]
            values[key]=(abs(amount) if key=='capex' else amount)/1000
    match=re.search(r'^\s*Orders\s+([^\n]+)',text,re.M)
    if match:values['orders']=numbers(match[1])[0]
    if not all(k in values for k in ('revenue','profit','capex')):raise ValueError('Besi metric missing')
    return observation(year,q,1,values,url)


def parse_tel(text,year,q,url):
    # Income statement section is before outlook and uses prior YTD, YoY, current YTD, YoY.
    first=text[:text.find('Consolidated Financial Position') if 'Consolidated Financial Position' in text else 6500]
    values={}
    for key,label in [('revenue','Net sales'),('profit','Operating income')]:
        m=re.search(r'^\s*'+label+r'\s*(?:\(Millions of yen\))?\s+([^\n]+)',first,re.M|re.I)
        if not m:raise ValueError('TEL summary row missing')
        nums=numbers(m[1])
        if len(nums)<4:raise ValueError('TEL summary columns changed')
        values[key]=nums[2]
    if q==4:
        m=re.search(r'^\s*Purchase of property, plant and equipment\s+([^\n]+)',text,re.M)
        if m:values['capex']=abs(numbers(m[1])[-1])
    return observation(year,q,4,values,url,'공시 누적')


def parse_advantest(items,url,annual=False):
    rows={}
    for top in items:
        for block in top['Data']:
            for series in block['Series']:
                key={'Net sales':'revenue','Operating income':'profit','Purchases of property, plant and equipment':'capex'}.get(series['name'].strip())
                if not key:continue
                for label,cell in zip(block['Columns'],series['Data']):
                    year=int(re.search(r'FY(\d{4})',label)[1])+1
                    q=4 if annual else int(re.search(r'([1-4])Q',label)[1])
                    values=rows.setdefault((year,q),{})
                    values[key]=abs(cell['nr']) if key=='capex' else cell['nr']
    return [observation(y,q,4,v,url,'공식 내장 재무표 · 공시 연간' if annual else '공식 내장 재무표 · 분기') for (y,q),v in sorted(rows.items())]


def parse_adv_report(text,year,q,url):
    """IFRS statement rows put previous YTD first and current YTD last."""
    block=text
    values={}
    for key,label in [('revenue','Net sales'),('profit','Operating income'),('capex','Purchases of property, plant and equipment')]:
        # Full statements have integer JPY-million columns. Exclude the earlier
        # narrative summary, which is in billions and adds a percentage column.
        match=re.search(r'^\s*'+label+r'[ \t]+([\d,() \t-]+)\s*$',block,re.M)
        if match:
            nums=numbers(match[1])
            if len(nums)>=2:values[key]=abs(nums[-1]) if key=='capex' else nums[-1]
    if not all(k in values for k in ('revenue','profit')):raise ValueError('Advantest statement columns missing')
    return observation(year+1,q,4,values,url,'공시 누적')


def build_global_company(key,cohort,meta):
    docs={};rows=cohort['rows'];annual=cohort['annual']
    label_year=lambda row:row['year']-bool(meta.get('fiscal_label_start'))
    labels={r['date']:f"FY{label_year(r)} Q{r['quarter']}" for r in rows}
    lookup={(r['year'],r['quarter']):r['date'] for r in rows}
    axis={r['date'] for r in rows}
    if rows:
        for year in range(min(r['year'] for r in rows),max(r['year'] for r in rows)+1):
            for q in range(1,5):
                end=quarter_end(year,q,meta['fiscal_start'])
                if rows[0]['date']<end<rows[-1]['date'] and (year,q) not in lookup:axis.add(end)
    bydate={r['date']:r for r in rows}
    for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
        series_name=meta.get('capex_label','유형자산 현금취득') if metric=='capex' else '연결 영업이익 · 보고 기준' if metric=='profit' else '연결 매출'
        qrows=[r for r in rows if metric in r];arows=[r for r in annual if metric in r]
        if not qrows and not arows:raise ValueError(key+': no '+metric+' observations')
        latest=qrows[-1] if qrows else arows[-1]
        refs={r['date']:dict(url=r['refs'][metric]['url'],label=labels.get(r['date'],'FY'+str(label_year(r))),
            supporting_sources=[dict(url=c['url'],label=c.get('label') or ('종료일 '+c.get('end','') if c.get('start')==c.get('end') else c.get('start','')+' ~ '+c.get('end',''))) for c in r['refs'][metric].get('components',[])]) for r in qrows}
        note=meta['note']+' '+('CAPEX는 회사 자신의 투자이며 고객 설비투자나 장비 수주가 아닙니다.' if metric=='capex' else '전사 연결 실적이며 개별 장비·공정 매출과 다릅니다.')
        doc=dict(id=f'company_{key}_{metric}',name=meta['name']+' · '+title,unit=meta['currency']+' 백만',frequency='quarterly',frequency_label='분기 · 공식 공시·IR',
            company_kpi=True,quarter_labels=True,period_labels=labels,comparison_dates={r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),(r['quarter']-2)%4+1))) for r in rows},
            series={series_name:[[d,bydate.get(d,{}).get(metric)] for d in sorted(axis)]},default_series=[series_name],span_gaps=False,
            source=meta['source'],source_url=latest['refs'][metric]['url'],updated=latest['date'],fetched=cohort['fetched'],point_sources=refs,description=note,
            quarterly_revenue_summary=metric!='profit',quarterly_profit_summary=metric=='profit',table_limit=100,
            basis_details=[dict(label='범위·결산·투자 정의',value=note),dict(label='이력·누락',value='원문에서 확보한 실제 기간부터 표시합니다. 미확보 분기는 빈 값이며 연간을 4로 나누지 않습니다. 통화는 원통화 백만 단위입니다.')])
        av=annual_view(arows,{metric:series_name},note)
        av['fetched']=cohort.get('annual_checked',cohort['fetched'])
        av['period_labels']={r['date']:'FY'+str(label_year(r)) for r in arows}
        av['description']=note+' 연간은 공시된 완결 회계연도 또는 동일 기준 4개 분기의 합계입니다. 미완료 회계연도는 제외합니다.'
        if arows:
            years={r['year']:r for r in arows}
            av['series']={series_name:[[years[y]['date'] if y in years else quarter_end(y,4,meta['fiscal_start']),years[y][metric] if y in years else None]
                for y in range(min(years),max(years)+1)]}
        doc['basis_details'].append(dict(label='갱신 방식',value=('SEC 연간 자동 갱신 · 분기는 공식 IR 검토 자료' if meta.get('cik') else
            'OpenDART 연결 공시 자동 갱신' if key=='hanmi' else '공식 IR 원문 검토 자료 · 새 분기 자료 확인 후 반영')+' · 확인 '+cohort['checked']))
        add_period_views(doc,av)
        if not arows:doc['series_views'].pop('annual')
        if not qrows:
            doc.update(series=av['series'],point_sources=av['point_sources'],period_labels=av['period_labels'],frequency='yearly',frequency_label='연간 · 분기 미공개·미확보',
                quarter_labels=False,year_labels=True,default_view='annual',annual_axis=True,fetched=av['fetched'],quarterly_revenue_summary=False,quarterly_profit_summary=False)
            doc['series_views']={'annual':doc['series_views']['annual']}
            doc['description']+=' 이 항목은 연간 자료만 확보되어 연간으로 표시합니다.'
        if not cohort.get('ok',True):
            doc['collection_status']=dict(ok=False,checked=cohort['checked'],message='원문 확인 실패 · 마지막 성공 자료를 유지합니다.')
        docs[doc['id']]=doc
    return docs

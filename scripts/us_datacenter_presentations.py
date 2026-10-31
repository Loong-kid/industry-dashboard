"""One metric per chart, multiple companies; retain the actual fiscal periods."""
import calendar,copy

METRICS={'revenue':'클라우드 매출','profit':'클라우드 영업이익','margin':'클라우드 영업이익률','capex':'클라우드 CAPEX · 투자 대리지표'}
COMPANIES=[('amzn','Amazon · AWS'),('msft','Microsoft Cloud'),('googl','Google Cloud'),('orcl','Oracle Cloud'),('meta','Meta'),('xai','xAI · AI/SI')]
COLORS=['#2a78d6','#1baf7a','#eda100','#9085e9','#e34948','#008c95']


def axis_date(row,kind):
    if kind=='annual':return f"{row['year']}-12-31"
    year,month=int(row['date'][:4]),int(row['date'][5:7]);month=((month+2)//3)*3
    return f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]}'


def comparison_document(metric,specs,cohorts):
    views={};unit='%' if metric=='margin' else 'USD 백만'
    labels={key:(specs[key].get('short_name',specs[key]['name'])+' · 전사' if metric=='capex' and key!='xai' else name) for key,name in COMPANIES}
    unavailable={}
    for key,name in COMPANIES:
        if key=='meta' and metric!='capex':unavailable[labels[key]]='외부 퍼블릭 클라우드 판매 사업 해당 없음'
        elif metric in ('profit','margin') and specs[key].get('cloud_profit_note'):unavailable[labels[key]]=specs[key]['cloud_profit_note']
    for kind,caption in [('rows','분기'),('annual','연간')]:
        series={};refs={};memos={};point_sources={};dates=set()
        for key,_ in COMPANIES:
            name=labels[key];values={};refs[name]={};memos[name]={}
            for r in cohorts[key][kind]:
                prefix='segment' if key=='xai' else 'cloud'
                field='segment_capex' if metric=='capex' and key=='xai' else 'capex' if metric=='capex' else prefix+('_profit' if metric in ('profit','margin') else '_revenue')
                value=r.get(field)
                if name in unavailable:continue
                if metric=='margin':
                    revenue=r.get(prefix+'_revenue')
                    value=value/revenue*100 if value is not None and revenue is not None and revenue>0 else None
                if value is None:continue
                date=axis_date(r,kind)
                if date in values:raise ValueError('Two fiscal periods map to the same comparison period')
                values[date]=value;dates.add(date)
                ref=copy.deepcopy(r['refs'][field]);period=f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '')
                if metric=='margin':ref.update(components=[r['refs'][field],r['refs'][prefix+'_revenue']],calculation='same-scope operating profit / revenue × 100')
                ref.update(period=period,observed_date=r['date'],period_start=r['start'])
                refs[name][date]=ref
                scope=('AI/SI 사업부 · Grok·X·Cursor 등 포함' if key=='xai' else '전사 현금 PP&E · 클라우드 전용 CAPEX 미공개' if metric=='capex' else specs[key]['scope'])
                memos[name][date]=[name+' · '+period,r['start']+' ~ '+r['date'],scope,ref['calculation'],f'{value:,.4f} {unit}']
                if metric=='margin':memos[name][date].append(f"{r[field]:,.3f} / {r[prefix+'_revenue']:,.3f} × 100")
                source=point_sources.setdefault(date,dict(url=ref['url'],supporting_sources=[],source_separator=' / '))
                for part in [ref,*ref.get('components',[])]:
                    link=dict(url=part['url'],label=name+' · '+period)
                    if link not in source['supporting_sources']:source['supporting_sources'].append(link)
            series[name]=values
        if dates:
            first,last=min(dates),max(dates);years=range(int(first[:4]),int(last[:4])+1)
            axis=[f'{y}-12-31' for y in years] if kind=='annual' else [f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]}' for y in years for m in (3,6,9,12)]
            axis=[d for d in axis if first<=d<=last]
        else:axis=[]
        # Internal gaps stay null. Trim before/after actual coverage per company
        # so the headline remains its latest real disclosure.
        series={name:[[date,values.get(date)] for date in axis if min(values,default='9999')<=date<=max(values,default='')] for name,values in series.items()}
        defaults=[labels[k] for k,_ in COMPANIES if k!='xai' and any(v is not None for _,v in series[labels[k]])]
        actual=[ref['observed_date'] for by_date in refs.values() for ref in by_date.values()]
        views['quarter' if kind=='rows' else 'annual']=dict(label=caption,frequency='quarterly' if kind=='rows' else 'yearly',
            frequency_label=caption+' · 기업 비교',quarter_labels=kind=='rows',year_labels=kind=='annual',annual_axis=kind=='annual',
            period_labels={d:(d[:4]+' Q'+str((int(d[5:7])+2)//3) if kind=='rows' else 'FY'+d[:4]) for d in axis},
            series=series,series_sources=refs,series_point_notes=memos,point_sources=point_sources,default_series=defaults,
            updated=max(actual,default=''),source_url=next((ref['url'] for by_date in refs.values() for ref in reversed(list(by_date.values()))),specs['amzn']['source_url']),
            quarterly_revenue_summary=kind=='rows' and metric in ('revenue','capex'),quarterly_profit_summary=kind=='rows' and metric=='profit',change_mode='none')
    note=('클라우드 전용 CAPEX가 별도 공시되지 않아 Amazon·Microsoft·Alphabet·Oracle·Meta는 전사 현금 PP&E를 대리지표로 표시합니다. xAI는 실제 AI/SI 사업부 CAPEX로 범위가 다릅니다. 리스 반영 보충 지표는 아래 개별 카드에서 확인할 수 있습니다.' if metric=='capex' else 'Microsoft Cloud는 Azure 외 서비스도 포함합니다. xAI는 Grok·X·Cursor 등을 포함한 AI/SI 전체이며 순수 클라우드와 범위가 달라 기본 선택에서 제외했습니다. 미공개·해당 없음은 0으로 채우지 않습니다.')
    checked=min(c['checked'] for c in cohorts.values());healthy=all(c['core_ok'] and (metric=='capex' or c['cloud_ok']) for c in cohorts.values())
    return dict(id='us_dc_compare_'+metric,name=METRICS[metric]+' (기업별)',comparison_metric=metric,company_comparison=True,
        unit=unit,company_kpi=True,compact_ticks=True,span_gaps=False,table_scroll=True,table_limit=1000,
        series_colors={labels[key]:color for (key,_),color in zip(COMPANIES,COLORS)},series_unavailable=unavailable,
        source='SEC · 기업 공식 공시',fetched=min(c['fetched'] for c in cohorts.values()),
        collection_status=dict(ok=healthy,checked=checked,message='공시 조회 완료' if healthy else '일부 조회·새 공시 검토 필요 · 기존 이력 유지'),
        description='기업 이름을 클릭하면 해당 회사의 선을 켜거나 끌 수 있습니다. 여러 회사를 동시에 선택할 수 있습니다.',note=note,
        basis_details=[dict(label='기간 비교',value='분기는 실제 결산 종료일이 속한 달력 분기에, 연간은 결산연도 FY에 맞춰 표시합니다. Microsoft는 6월, Oracle은 5월 결산으로 같은 FY라도 실제 시작·종료일이 다릅니다. 숫자·차트 메모·표에 각 회사의 실제 회계기간을 보존합니다.'),
            dict(label='영업이익률',value='같은 회사·같은 사업 범위·같은 실제 기간의 영업이익 / 매출 × 100입니다. 연간은 연간 공시끼리 계산하며 분기 비율을 평균하지 않습니다.')],
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})

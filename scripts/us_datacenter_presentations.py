"""Metric comparisons with explicit issuer, segment and snapshot scope."""
import calendar,copy
from us_datacenter_contracts import RPO_SCOPES,SEGMENTS

METRICS={'revenue':'클라우드 매출','profit':'클라우드 영업이익','margin':'클라우드 영업이익률','capex':'클라우드 CAPEX · 투자 대리지표','rpo':'클라우드 수주잔고 · RPO'}
COMPANIES=[('amzn','Amazon · AWS'),('msft','Microsoft Cloud'),('googl','Google Cloud'),('orcl','Oracle Cloud'),('meta','Meta'),('xai','xAI · AI/SI')]
COLORS=['#2a78d6','#1baf7a','#eda100','#9085e9','#e34948','#008c95']


def definitions(metric,specs):
    result=[]
    for (key,label),color in zip(COMPANIES,COLORS):
        d=dict(key=key,source=key,label=label,color=color,default=key!='xai')
        if metric=='capex' and key!='xai':d['label']=specs[key].get('short_name',specs[key]['name'])+' · 전사'
        if metric=='margin' and key=='msft':d.update(label='Microsoft · IC(대리)',segment='ic')
        if metric=='rpo':
            d.update(rpo_field='rpo',label={'amzn':'AWS 중심 RPO','msft':'Microsoft Commercial RPO','googl':'Google Cloud RPO','orcl':'Oracle 전사 RPO'}.get(key,label))
        result.append(d)
        if metric=='margin' and key=='msft':result.append(dict(key='msft_ai',source='msft',label='Microsoft · Agents & Infra(대리)',segment='ai',color=color,dash=[5,3],default=True))
        if metric=='rpo' and key=='googl':result.append(dict(key='googl_total',source='googl',label='Alphabet 전사 RPO',rpo_field='rpo_total',color='#777777',dash=[5,3],default=False))
    return result


def axis_date(row,kind):
    if kind=='annual':return f"{row['year']}-12-31"
    year,month=int(row['date'][:4]),int(row['date'][5:7]);month=((month+2)//3)*3
    return f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]}'


def comparison_document(metric,specs,cohorts):
    defs=definitions(metric,specs);views={};unit='%' if metric=='margin' else 'USD 백만';unavailable={}
    for d in defs:
        key=d['source']
        if key=='meta' and metric!='capex':unavailable[d['label']]='외부 퍼블릭 클라우드 판매 사업 해당 없음'
        elif metric=='rpo' and key=='xai':unavailable[d['label']]='AI/SI 단독 RPO 미공개 · 우주·Starlink를 포함한 SpaceX 전사 RPO로 대체하지 않음'
        elif metric in ('profit','margin') and not d.get('segment') and specs[key].get('cloud_profit_note'):unavailable[d['label']]=specs[key]['cloud_profit_note']
    for kind,caption in [('rows','분기'),('annual','연간')]:
        series={};refs={};memos={};point_sources={};dates=set()
        for d in defs:
            key,name=d['source'],d['label'];values={};refs[name]={};memos[name]={};cohort=cohorts[key]
            if metric=='rpo':rows=cohort.get('contracts',{}).get(d['rpo_field'],{}).get(kind,[])
            elif d.get('segment'):rows=cohort.get('contracts',{}).get('segments',{}).get(d['segment'],{}).get(kind,[])
            else:rows=cohort[kind]
            for r in rows:
                if name in unavailable:continue
                prefix='segment' if key=='xai' else 'cloud'
                field='rpo' if metric=='rpo' else 'margin' if d.get('segment') else 'segment_capex' if metric=='capex' and key=='xai' else 'capex' if metric=='capex' else prefix+('_profit' if metric in ('profit','margin') else '_revenue')
                value=r.get(field)
                if metric=='margin' and not d.get('segment'):
                    revenue=r.get(prefix+'_revenue');value=value/revenue*100 if value is not None and revenue is not None and revenue>0 else None
                if value is None:continue
                date=axis_date(r,kind)
                if date in values:raise ValueError('Two fiscal periods map to one comparison period')
                values[date]=value;dates.add(date)
                ref=copy.deepcopy(r['refs'][field]);period=f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '')
                if metric=='margin' and not d.get('segment'):ref.update(components=[r['refs'][field],r['refs'][prefix+'_revenue']],calculation='same-scope operating profit / revenue × 100')
                ref.update(period=period,observed_date=r['date'],period_start=r['start'])
                refs[name][date]=ref
                if metric=='rpo':scope=RPO_SCOPES[key] if d['rpo_field']=='rpo' else 'Alphabet 전사 RPO · Cloud 단독과 다른 범위'
                elif d.get('segment'):scope=SEGMENTS[d['segment']]+' 부문 자체 이익률 · Azure/Microsoft Cloud 수익성 대리치'
                else:scope='AI/SI 사업부 · Grok·X·Cursor 등 포함' if key=='xai' else '전사 현금 PP&E · 클라우드 전용 CAPEX 미공개' if metric=='capex' else specs[key]['scope']
                duration=r['date']+' 기준 잔액 · 매출 흐름 아님' if metric=='rpo' else r['start']+' ~ '+r['date']
                memos[name][date]=[name+' · '+period,duration,scope,ref['calculation'],f'{value:,.4f} {unit}']
                if metric=='margin':memos[name][date].append(f"{r['profit'] if d.get('segment') else r[field]:,.3f} / {r['revenue'] if d.get('segment') else r[prefix+'_revenue']:,.3f} × 100")
                if metric=='rpo' and key=='googl':memos[name][date].append('2026년 1분기부터 원래 계약기간 1년 이하 포함 · 전사/Cloud 계열 구분')
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
        series={name:[[date,values.get(date)] for date in axis if min(values,default='9999')<=date<=max(values,default='')] for name,values in series.items()}
        defaults=[d['label'] for d in defs if d['default'] and any(v is not None for _,v in series[d['label']])]
        if metric=='rpo' and not series['Google Cloud RPO'] and series['Alphabet 전사 RPO']:defaults.append('Alphabet 전사 RPO')
        actual=[ref['observed_date'] for by_date in refs.values() for ref in by_date.values()]
        views['quarter' if kind=='rows' else 'annual']=dict(label=caption,frequency='quarterly' if kind=='rows' else 'yearly',
            frequency_label=('분기 말 잔액 · 기업 비교' if kind=='rows' else '결산일 잔액 · 기업 비교') if metric=='rpo' else caption+' · 기업 비교',quarter_labels=kind=='rows',year_labels=kind=='annual',annual_axis=kind=='annual',
            period_labels={d:(d[:4]+' Q'+str((int(d[5:7])+2)//3) if kind=='rows' else 'FY'+d[:4]) for d in axis},
            series=series,series_sources=refs,series_point_notes=memos,point_sources=point_sources,default_series=defaults,
            updated=max(actual,default=''),source_url=next((ref['url'] for by_date in refs.values() for ref in reversed(list(by_date.values()))),specs['amzn']['source_url']),
            quarterly_revenue_summary=kind=='rows' and metric in ('revenue','capex','rpo'),quarterly_profit_summary=kind=='rows' and metric=='profit',change_mode='none')
    if metric=='rpo':note='RPO는 기말 미이행 계약 잔액이며 분기 매출·신규 수주가 아닙니다. AWS 중심 장기계약, Microsoft Commercial, Google Cloud, Oracle 전사 범위를 구분합니다. Google Cloud 단독 RPO는 2026년부터 별도 공시하며 과거 Alphabet 전사 RPO는 별도 점선입니다. 2026년 1분기부터 Google은 1년 이하 계약도 포함합니다. 연간은 결산일 잔액이고 분기 잔액을 합산하지 않습니다.'
    elif metric=='capex':note='클라우드 전용 CAPEX가 별도 공시되지 않아 Amazon·Microsoft·Alphabet·Oracle·Meta는 전사 현금 PP&E를 대리지표로 표시합니다. xAI는 실제 AI/SI 사업부 CAPEX로 범위가 다릅니다. 리스 반영 보충 지표는 아래 개별 카드에서 확인할 수 있습니다.'
    elif metric=='margin':note='Microsoft IC는 Intelligent Cloud 부문 영업이익 / 같은 부문 매출로 계산한 대리치입니다. FY2027 개편 후 Agents and Infra는 별도 점선 계열로 표시하며 IC와 연결하거나 이전 값을 이월하지 않습니다. 둘 다 Azure·Microsoft Cloud 단독 이익률과 다릅니다. xAI는 AI/SI 범위입니다.'
    else:note='Microsoft Cloud는 Azure 외 서비스도 포함합니다. xAI는 Grok·X·Cursor 등을 포함한 AI/SI 전체이며 순수 클라우드와 범위가 달라 기본 선택에서 제외했습니다. 미공개·해당 없음은 0으로 채우지 않습니다.'
    checked=min(c['checked'] for c in cohorts.values());healthy=all(c['core_ok'] and (metric=='capex' or c['cloud_ok']) for c in cohorts.values())
    if metric in ('margin','rpo'):healthy=healthy and all(cohorts[k].get('contracts',{}).get('ok',False) for k in (('amzn','msft','googl','orcl') if metric=='rpo' else ('msft',)))
    return dict(id='us_dc_compare_'+metric,name=METRICS[metric]+' (기업별)',comparison_metric=metric,company_comparison=True,
        unit=unit,company_kpi=True,compact_ticks=True,span_gaps=False,table_scroll=True,table_limit=1000,chart_type='bar' if metric=='capex' else 'line',
        series_colors={d['label']:d['color'] for d in defs},series_dashes={d['label']:d['dash'] for d in defs if d.get('dash')},series_unavailable=unavailable,
        source='SEC · 기업 공식 공시',fetched=min(c['fetched'] for c in cohorts.values()),collection_status=dict(ok=healthy,checked=checked,message='공시 조회 완료' if healthy else '일부 조회·새 공시 검토 필요 · 기존 이력 유지'),
        description='기업 이름을 클릭하면 해당 회사의 '+('막대를' if metric=='capex' else '선을')+' 켜거나 끌 수 있습니다. 여러 회사를 동시에 선택할 수 있습니다.',note=note,
        basis_details=[dict(label='기간 비교',value='분기는 실제 결산 종료일이 속한 달력 분기에, 연간은 FY 결산연도에 맞춥니다. Microsoft 6월·Oracle 5월 결산으로 같은 FY라도 실제 기간은 다릅니다. 메모·표의 원래 회계기간을 확인하세요. RPO의 연간 값은 결산일 잔액이며 합산하지 않습니다.'),dict(label='이익률',value='같은 사업 범위·같은 실제 기간의 영업이익 / 매출 × 100입니다. 연간 비율은 연간 공시끼리 나누며 분기 이익률을 평균하지 않습니다. Microsoft의 서로 다른 부문은 별도 계열입니다.')],
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})

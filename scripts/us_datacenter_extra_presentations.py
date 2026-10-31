"""Additional RPO balances and explicitly labelled Microsoft profit proxies."""
from us_datacenter_contracts import RPO_SCOPES,SEGMENTS


def rpo_document(key,spec,cohort):
    c=cohort['contracts'];name=spec.get('short_name',spec['name'])
    labels=[('rpo',RPO_SCOPES[key].split(' · ')[0])]
    if key=='googl':labels.append(('rpo_total','Alphabet 전사 RPO · Cloud 중심'))
    views={}
    for kind,caption in [('rows','분기'),('annual','연간')]:
        series={};sources={};notes={};periods={};aggregate={};actual=[];lookup={};period_rows={}
        for field,label in labels:
            rows=c[field][kind];series[label]=[[r['date'],r['rpo']] for r in rows];sources[label]={};notes[label]={}
            for r in rows:
                date=r['date'];period=f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '')
                ref=dict(r['refs']['rpo'],period=period,observed_date=date,period_start=date)
                sources[label][date]=ref;periods[date]=period;actual.append(date)
                lookup[(r['year'],r['quarter'])]=date;period_rows[date]=r
                notes[label][date]=[name+' · '+label,date+' 기준 잔액 · 분기 흐름이나 신규 수주가 아님',f"{r['rpo']:,.3f} 백만 USD",ref['tag']]
                if key=='googl':notes[label][date].append('Google은 2026년 1분기부터 원래 계약기간 1년 이하도 포함 · 전사와 Cloud 범위 구분')
                a=aggregate.setdefault(date,dict(url=ref['url'],supporting_sources=[],source_separator=' / '))
                a['supporting_sources'].append(dict(url=ref['url'],label=label+' · '+date))
        default=next((label for _,label in labels if series[label]),labels[0][1])
        views['quarter' if kind=='rows' else 'annual']=dict(label=caption,frequency='quarterly' if kind=='rows' else 'yearly',
            frequency_label='분기 말 잔액' if kind=='rows' else '회계연도 결산일 잔액',quarter_labels=kind=='rows',year_labels=kind=='annual',
            period_labels=periods,series=series,series_sources=sources,series_point_notes=notes,point_sources=aggregate,
            default_series=[default],updated=max(actual,default=''),source_url=next((r['url'] for refs in sources.values() for r in reversed(list(refs.values()))),spec['source_url']),
            comparison_dates={date:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),r['quarter']-1 or 4))) for date,r in period_rows.items()} if kind=='rows' else {},
            quarterly_revenue_summary=kind=='rows',change_mode='none')
    return dict(id=f'us_dc_{key}_rpo',name=name+' · RPO',unit='USD 백만',company_kpi=True,compact_ticks=True,span_gaps=False,
        company_comparison=True,comparison_metric='rpo_'+key,comparison_compact=True,series_unavailable={},
        fetched=c['fetched'],source='SEC · 계약 잔액 공시',collection_status=dict(ok=c['ok'],checked=c['checked'],message='공시 조회 완료' if c['ok'] else 'RPO 공시 검토 필요 · 기존 이력 유지'),
        description=RPO_SCOPES[key],note='기말 미이행 계약 잔액입니다. 분기·연간 값을 합산하거나 누적 차분하지 않습니다. 연간은 각 회사의 실제 결산일 잔액만 표시합니다.'+(' Cloud 단독 RPO는 2026년부터 별도 공시되어, 이전 전사 이력은 별도 항목으로 구분했습니다.' if key=='googl' else ''),
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})


def proxy_margin_document(segment,cohort):
    c=cohort['contracts'];title=SEGMENTS[segment];history=c['segments'][segment];views={}
    for kind,caption in [('rows','분기'),('annual','연간')]:
        rows=[r for r in history[kind] if r.get('margin') is not None];refs={};notes={}
        for r in rows:
            ref=r['refs']['margin']
            refs[r['date']]=dict(url=ref['url'],label=title,supporting_sources=[dict(url=x['url'],label=x['tag']) for x in ref['components']],source_separator=' / ')
            notes[r['date']]=[title+' 사업부 · 클라우드 수익성 대리지표',r['start']+' ~ '+r['date'],
                f"영업이익 {r['profit']:,.3f} / 같은 사업부 매출 {r['revenue']:,.3f} × 100 = {r['margin']:,.4f}%",
                'Azure·Microsoft Cloud 단독 이익률이 아님 · 서로 다른 보고 부문을 연결하지 않음']
        views['quarter' if kind=='rows' else 'annual']=dict(label=caption,frequency='quarterly' if kind=='rows' else 'yearly',frequency_label=caption+' · 부문 이익률 대리치',
            quarter_labels=kind=='rows',year_labels=kind=='annual',annual_axis=kind=='annual',series={title:[[r['date'],r['margin']] for r in rows]},
            period_labels={r['date']:f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '') for r in rows},
            point_sources=refs,point_notes=notes,updated=rows[-1]['date'] if rows else '',source_url=rows[-1]['refs']['margin']['url'] if rows else 'https://www.microsoft.com/en-us/investor/',
            change_mode='none',empty_message=title+'의 완결 연간 공시를 아직 확보하지 못했습니다. 분기 이익률을 평균하거나 다른 부문을 대입하지 않습니다.')
    return dict(id='us_dc_msft_'+segment+'_margin',name='Microsoft · '+('IC' if segment=='ic' else '개편 부문')+' 이익률(대리)',unit='%',company_kpi=True,compact_ticks=True,span_gaps=False,
        source='SEC · 공시 부문 매출·영업이익',fetched=c['fetched'],collection_status=dict(ok=c['ok'],checked=c['checked'],message='공시 조회 완료' if c['ok'] else '부문 공시 검토 필요 · 기존 이력 유지'),
        description=title+' 영업이익 / '+title+' 매출 × 100',
        note='공시된 부문 자체의 이익률이며 Azure·Microsoft Cloud 수익성의 근사 지표입니다. Intelligent Cloud와 FY2027의 Agents and Infra는 포함 사업이 달라 별도 그래프로 구분합니다. IC의 마지막 값을 현재 분기로 이월하지 않습니다. 연간은 연간 공시끼리 나누며 분기 이익률을 평균하지 않습니다.',
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})

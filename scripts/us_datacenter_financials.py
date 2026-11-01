"""One selectable revenue/profit chart per issuer; keep all source scopes."""
import copy


def financial_document(key,spec,cohort):
    if key=='xai':
        metrics=[('revenue','SpaceX 전사 매출'),('profit','SpaceX 전사 영업이익'),('segment_revenue','AI/SI 매출'),('segment_profit','AI/SI 영업이익')]
    else:metrics=[('revenue','전사 매출'),('profit','전사 영업이익'),('cloud_revenue','클라우드 매출'),('cloud_profit','클라우드 영업이익')]
    unavailable={};statuses={};views={}
    for metric,label in metrics:
        if key=='meta' and metric.startswith('cloud_'):
            unavailable[label]='외부 퍼블릭 클라우드 판매 사업이 없어 해당 없음';statuses[label]='해당 없음'
        elif metric=='cloud_profit' and spec.get('cloud_profit_note'):
            unavailable[label]=spec['cloud_profit_note'];statuses[label]='미공개'
    for kind,caption in [('rows','분기'),('annual','연간')]:
        rows=cohort[kind];series={};sources={};notes={};aggregate={}
        for metric,label in metrics:
            valid=[r for r in rows if r.get(metric) is not None and label not in unavailable]
            first=valid[0]['date'] if valid else '9999';last=valid[-1]['date'] if valid else ''
            series[label]=[[r['date'],r.get(metric)] for r in rows if first<=r['date']<=last]
            sources[label]={};notes[label]={}
            for r in valid:
                date=r['date'];period=f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '')
                ref=copy.deepcopy(r['refs'][metric]);ref.update(period=period,observed_date=date,period_start=r['start'])
                sources[label][date]=ref
                scope='AI/SI 사업부 · Grok·X·Cursor 등 포함' if key=='xai' and metric.startswith('segment_') else spec.get('cloud_name','') if metric.startswith('cloud_') else '전사 연결 전체'
                notes[label][date]=[label+' · '+period,r['start']+' ~ '+date,scope,f"{r[metric]:,.3f} 백만 USD",ref['calculation'],ref['tag']]
                a=aggregate.setdefault(date,dict(url=ref['url'],supporting_sources=[],source_separator=' / '))
                for part in [ref,*ref.get('components',[])]:
                    source=dict(url=part['url'],label=label+' · '+period)
                    if source not in a['supporting_sources']:a['supporting_sources'].append(source)
        lookup={(r['year'],r.get('quarter')):r['date'] for r in rows}
        views['quarter' if kind=='rows' else 'annual']=dict(label=caption,frequency='quarterly' if kind=='rows' else 'yearly',
            frequency_label=caption+' · 매출·영업이익',quarter_labels=kind=='rows',year_labels=kind=='annual',annual_axis=kind=='annual',
            series=series,series_sources=sources,series_point_notes=notes,point_sources=aggregate,
            default_series=[label for _,label in metrics if series[label]],
            period_labels={r['date']:f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '') for r in rows},
            comparison_dates={r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),r['quarter']-1 or 4))) for r in rows} if kind=='rows' else {},
            quarterly_profit_summary=kind=='rows',change_mode='none',updated=rows[-1]['date'],source_url=rows[-1]['refs']['revenue']['url'])
    healthy=cohort['core_ok'] and cohort.get('cloud_ok',True)
    name=spec.get('short_name',spec['name'])
    return dict(id=f'us_dc_{key}_financials',name=name+' · 매출·영업이익',unit='USD 백만',company_kpi=True,compact_ticks=True,span_gaps=False,
        company_comparison=True,comparison_metric='financials_'+key,financial_metric_selector=True,series_unavailable=unavailable,series_status=statuses,
        series_colors={label:color for (_,label),color in zip(metrics,['#2a78d6','#1baf7a','#eda100','#9085e9'])},
        source='SEC · 공식 연결·사업 공시',fetched=cohort['fetched'],collection_status=dict(ok=healthy,checked=cohort['checked'],message='공시 조회 완료' if healthy else '일부 공시 검토 필요 · 기존 이력 유지'),
        description='지표 이름을 클릭해 전사·클라우드 매출과 영업이익을 함께 보거나 필요한 항목만 선택하세요.',
        note='미공개·해당 없음은 0으로 표시하지 않습니다. 숫자나 표의 값을 클릭하면 실제 기간과 출처를 확인할 수 있습니다.',
        basis_details=[dict(label='사업 범위',value=spec['note']),dict(label='분기·연간',value='실제 회사 회계기간의 공시값입니다. 미공개 이력은 빈값이며 분기·연간 전환에도 선택 항목을 유지합니다. 영업이익률·CAPEX·RPO는 별도 카드에서 확인합니다.'),dict(label='확인 방법',value='차트 호버는 기간·수치·단위만 표시합니다. 숫자 클릭과 표에서는 집계 근거·원문을, 이 펼침 영역에서는 공시 범위를 확인할 수 있습니다.')],
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})

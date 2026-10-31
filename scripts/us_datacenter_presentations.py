"""Same-scope revenue, operating profit and margin in one financial chart."""
import copy


def combo_document(key,meta,cohort):
    xai=key=='xai';prefix='segment' if xai else 'cloud'
    revenue,profit=prefix+'_revenue',prefix+'_profit'
    scope='AI/SI' if xai else '클라우드'
    title=('xAI' if xai else meta.get('short_name',meta['name']))+' · '+scope+' 실적 함께 보기'
    labels=[scope+' 매출',scope+' 영업이익',scope+' 영업이익률']
    missing=meta.get('cloud_profit_note','') if not xai else ''
    views={}
    for kind,label in [('rows','분기'),('annual','연간')]:
        available=[r for r in cohort[kind] if r.get(revenue) is not None]
        rows=[r for r in cohort[kind] if available and available[0]['date']<=r['date']<=available[-1]['date']]
        values=[[],[],[]];sources={name:{} for name in labels}
        for r in rows:
            rev=r.get(revenue);op=r.get(profit)
            # All ratios use the actual same period and same business scope.
            margin=op/rev*100 if op is not None and rev is not None and rev>0 else None
            for i,value in enumerate((rev,op,margin)):
                values[i].append([r['date'],value])
                field=revenue if i==0 else profit
                if value is not None:
                    ref=copy.deepcopy(r['refs'][field])
                    if i==2:ref.update(components=[r['refs'][profit],r['refs'][revenue]],calculation='same-period operating profit / revenue × 100')
                    sources[labels[i]][r['date']]=ref
        views['quarter' if kind=='rows' else 'annual']=dict(label=label,frequency='quarterly' if kind=='rows' else 'yearly',
            frequency_label=label+' · 동일 사업 범위',quarter_labels=kind=='rows',year_labels=kind=='annual',
            series=dict(zip(labels,values)),series_sources=sources,
            period_labels={r['date']:f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '') for r in rows},
            updated=available[-1]['date'] if available else '',
            source_url=available[-1]['refs'][revenue]['url'] if available else meta['source_url'])
    return dict(id=f'us_dc_{key}_{prefix}_summary',name=title,financial_combo=True,
        unit='USD 백만',margin_series=labels[2],missing_profit_note=missing,
        series_units={labels[0]:'USD 백만',labels[1]:'USD 백만',labels[2]:'%'},
        span_gaps=False,source='SEC · 공식 사업 공시',fetched=cohort['fetched'],
        collection_status=dict(ok=cohort['core_ok'] and cohort['cloud_ok'],checked=cohort['checked'],
            message='공시 조회 완료' if cohort['core_ok'] and cohort['cloud_ok'] else '일부 공시 검토 필요 · 기존 이력 유지'),
        note=('Grok·X·Cursor·클라우드 서비스 등을 포함한 AI/SI 사업부입니다. 순수 클라우드 실적과 다릅니다. ' if xai else meta['scope']+'. ')
            +'매출·영업이익은 왼쪽 금액 축, 영업이익률은 오른쪽 % 축입니다. 연간 이익률은 연간 영업이익 / 연간 매출로 계산합니다.',
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})

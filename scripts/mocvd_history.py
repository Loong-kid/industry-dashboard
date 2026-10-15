"""Display reviewed MOCVD histories without mixing annual and quarterly flows."""
import copy
import re


def extend_history(docs,history,chart):
    companies=history['companies']
    merger_note='6월 결산. FY2014–2022는 현재 Coherent Corp.로 이어지는 II-VI 이력입니다. 2019년 9월 Finisar, 2022년 7월 옛 Coherent 인수로 연결 범위가 확대됐습니다. 인수 대상의 과거 실적을 소급 합산하지 않았습니다.'

    def financial(id,name,unit,rows,fields,note,annual=False,profit=False):
        rows=[r for r in rows if any(k in r for k in fields)]
        doc=chart(id,name,unit,rows,fields,note,manual=True)
        doc['period_labels']={r['date']:r['period'] for r in rows}
        doc['frequency_label']='연간 · 공시/계산' if annual else '분기 · 공시/누적 차분'
        doc['quarterly_profit_summary']=profit and not annual
        doc['quarterly_revenue_summary']=not profit and not annual
        if annual:
            doc.update(frequency='yearly',quarter_labels=False,year_labels=True)
            lookup={r['year']:r['date'] for r in rows}
            doc['comparison_dates']={r['date']:dict(year_ago=lookup.get(r['year']-1),quarter_ago=None) for r in rows}
        else:
            lookup={(r['year'],r['quarter']):r['date'] for r in rows}
            doc['fiscal_comparison_dates']={r['date']:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),
                quarter_ago=lookup.get((r['year']-(r['quarter']==1),(r['quarter']-2)%4+1))) for r in rows}
            doc['comparison_dates']=copy.deepcopy(doc['fiscal_comparison_dates'])
        return doc

    def views(quarter,annual,default='quarter'):
        result=copy.deepcopy(annual if default=='annual' else quarter)
        result['default_view']=default
        result['series_views']={'quarter':dict(quarter,label='분기'),'annual':dict(annual,label='연간 · 2014년부터')}
        return result

    for metric,korean in [('revenue','매출'),('profit','영업이익')]:
        id=f'mocvd_coherent_{metric}'
        fields={metric:'연결 매출' if metric=='revenue' else '영업이익 · 공시/계산'}
        note=merger_note+' 회사 전체 실적이며 InP 단독 수치가 아닙니다.'
        if metric=='profit':
            note+=' 영업이익 소계 공시가 중단된 FY2025 이후는 세전손익 + 이자비용 − 기타순수익으로 계산했습니다. 구조조정·손상차손을 제외하지 않으며 FY2026 사업매각이익 124.133백만 USD를 포함합니다. 조정 EBITDA가 아닙니다.'
        quarter=financial(id,'Coherent · '+korean,'백만 USD',companies['coherent']['quarters'],fields,note,profit=metric=='profit')
        annual=financial(id,'Coherent · '+korean,'백만 USD',companies['coherent']['annuals'],fields,note,True,metric=='profit')
        quarter['point_annotations']={'2019-09-30':'Finisar 연결 편입','2022-09-30':'옛 Coherent 인수 · 연결 범위 확대'}
        docs[id]=views(quarter,annual)

    for company in ['coherent','lumentum']:
        id=f'mocvd_{company}_capex'
        note=(merger_note if company=='coherent' else '6월 말 기준 52/53주 회계연도. 2015년 8월 JDSU에서 분사했으며 FY2014–2015는 해당 사업의 분사 전 결합재무 공시입니다. ')
        note+=' 회사 전체 유형자산 취득 현금지출입니다. 건물·조립·기타 제품 투자를 포함하며 InP/MOCVD 전용 금액이 아닙니다. 분기는 누적 차분, Q4는 연간−9개월 누적입니다.'
        if company=='lumentum':note+=' FY2014는 연간 공시만 확보되어 연간 보기에서 확인할 수 있습니다. 분기 값을 추정하지 않았습니다.'
        fields={'capex':'유형자산 취득 현금지출'}
        quarter=financial(id,company.capitalize()+' · 회사 전체 현금 CAPEX','백만 USD',companies[company]['quarters'],fields,note)
        # Preserve later dates from the daily collector when the reviewed
        # archive has not yet been extended. Existing archive precision wins.
        current=docs[id]
        olddates={d for d,_ in quarter['series'][fields['capex']]}
        for point in current['series'][fields['capex']]:
            if point[0] not in olddates:
                quarter['series'][fields['capex']].append(point)
                quarter['point_sources'][point[0]]=current['point_sources'][point[0]]
                quarter['period_labels'][point[0]]=current['period_labels'][point[0]]
        quarter['series'][fields['capex']].sort()
        quarter['updated']=quarter['series'][fields['capex']][-1][0]
        fiscal={tuple(map(int,re.fullmatch(r'FY(\d+) Q(\d)',label).groups())):date
                for date,label in quarter['period_labels'].items()}
        quarter['comparison_dates']={date:dict(year_ago=fiscal.get((fy-1,q)),
            quarter_ago=fiscal.get((fy-(q==1),(q-2)%4+1))) for (fy,q),date in fiscal.items()}
        quarter['fiscal_comparison_dates']=copy.deepcopy(quarter['comparison_dates'])
        if quarter['updated']>companies[company]['quarters'][-1]['date']:
            quarter['fetched']=current['fetched']
            quarter['source_url']=current['source_url']
        annual=financial(id,quarter['name'],'백만 USD',companies[company]['annuals'],fields,note,True)
        docs[id]=views(quarter,annual)

    id='mocvd_veeco_revenue'
    old=docs[id]
    field=next(iter(old['series']))
    combined=dict(old['series'][field])
    combined.update({r['date']:r['revenue'] for r in companies['veeco']['quarters'] if 'revenue' in r})
    old['series'][field]=sorted(combined.items())
    for r in companies['veeco']['quarters']:
        date=r['date'];ref=r['refs']['revenue']
        previous=old['point_sources'].get(date)
        old['point_sources'][date]=dict(ref,label=r['period'],supporting_sources=[ref]+([previous] if previous else []))
    old['description']+=' 연결 매출은 2014년부터 SEC 공시 이력, Compound Semiconductor와 비중은 동일 분류가 확보된 2023년부터입니다. 과거 LED·전력·RF 분류를 임의로 같은 부문으로 합치지 않았습니다.'
    old['updated']=old['series'][field][-1][0]
    if old['updated']<=companies['veeco']['quarters'][-1]['date']:old['fetched']=history['reviewed']
    revenue=dict(old['series'][field])
    compound=old['series']['Compound Semiconductor']
    share=docs['mocvd_veeco_share']
    share['series']['Compound Semiconductor / 연결']=[[date,round(value/revenue[date]*100,3)] for date,value in compound]
    share['point_sources']={date:copy.deepcopy(old['point_sources'][date]) for date,_ in compound}
    share['fetched']=history['reviewed']
    share['description']+=' 분모는 장기 그래프와 같은 SEC 연결 매출이며 부문 매출은 원 발표의 반올림 정밀도를 유지합니다.'

    id='mocvd_infineon_capex'
    note='9월 결산. 회사 전체 투자입니다. Investments는 현금 유형자산 + 무형자산·자산화 개발비 등의 합계이며 GaN 전용 금액이 아닙니다. 연간 값은 FY2014–2025 공시, 분기 값은 별도로 확인한 FY2026 Q2·Q3만 표시합니다. 과거 연간 값을 분기로 나누지 않았습니다.'
    quarter=docs[id]
    quarter.update(description=note,frequency_label='분기 · FY2026 Q2·Q3',quarterly_revenue_summary=True)
    annual=financial(id,'Infineon · 회사 전체 투자','백만 EUR',companies['infineon']['annuals'],
        {'capex':'유형자산 취득 현금지출','investments':'Investments · 무형자산·개발비 포함'},note,True)
    docs[id]=views(quarter,annual,'annual')

    coverage=copy.deepcopy(docs['mocvd_coverage'])
    for row in coverage['rows']:
        if row['company']=='AIXTRON':
            row['metric']='2014~2026 Q2 매출·EBIT·장비잔고·선수금·장비/서비스; 총수주 2015~ / 2014 장비수주 별도'
        elif row['company']=='Veeco':
            row['metric']='연결 매출 2014~2026 Q2; Compound Semiconductor 2023~2026 Q2'
    coverage['note']='장기 이력은 2026-10-16 검토 공시 원문과 공개 SEC 보관본 기준입니다. Coherent 매출·영업이익과 과거 이력, Infineon 연간 수치는 검토 후 갱신하며 자동 갱신으로 검토일을 바꾸지 않습니다. AIXTRON·Coherent CAPEX의 기존 최신 발표 확인은 유지합니다. 용도별 매출·부문 비중·출하대수는 확인된 기간만 표시합니다.'
    coverage['fetched']=coverage['updated']=history['reviewed']
    docs['mocvd_coverage']=coverage

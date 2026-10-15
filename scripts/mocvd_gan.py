"""GaN customer financials: preserve company scope and reporting frequency."""
import copy
import math


def validate_gan(snapshot):
    for company,meta in snapshot['companies'].items():
        for key in ['annuals','quarters','halfyears']:
            seen=set()
            for row in meta.get(key,[]):
                if row['date'] in seen:raise ValueError(f'{company}: duplicate {key} period')
                seen.add(row['date'])
                for metric in ['revenue','profit','capex']:
                    if metric not in row:continue
                    if not isinstance(row[metric],(int,float)) or not math.isfinite(row[metric]):
                        raise ValueError(f'{company}: invalid {metric}')
                    if metric!='profit' and row[metric]<0:raise ValueError(f'{company}: negative {metric}')
                    if not row['refs'][metric]['url'].startswith('https://'):raise ValueError('Source missing')


def extend_gan(docs,snapshot,chart):
    validate_gan(snapshot)
    companies=snapshot['companies']
    labels={'revenue':'연결 매출','profit':'연결 영업이익','capex':'유형자산 취득 현금지출'}
    names={'revenue':'매출','profit':'영업이익','capex':'현금 CAPEX'}

    def make(id,meta,rows,metric,note,frequency):
        fields={metric:'유형·무형자산 취득 현금지출' if metric=='capex' and id.startswith('mocvd_innoscience') else labels[metric]}
        d=chart(id,meta['name']+' · '+names[metric],meta['unit'],rows,fields,note,manual=True)
        d.update(frequency=frequency,quarter_labels=frequency=='quarterly',year_labels=frequency=='yearly',
                 period_labels={r['date']:r['period'] for r in rows},
                 quarterly_profit_summary=frequency=='quarterly' and metric=='profit',
                 quarterly_revenue_summary=frequency=='quarterly' and metric!='profit',
                 frequency_label={'quarterly':'분기 · 공시/누적 차분','yearly':'연간 · 공시','semiannual':'반기 · 공시/연간−상반기'}[frequency])
        periodkey='quarter' if frequency=='quarterly' else 'half' if frequency=='semiannual' else None
        lookup={(r['year'],r.get(periodkey)):r['date'] for r in rows}
        comparisons={}
        for row in rows:
            y,p=row['year'],row.get(periodkey)
            prev=(y-(p==1),(p-2)%(4 if periodkey=='quarter' else 2)+1) if periodkey else None
            comparisons[row['date']]=dict(year_ago=lookup.get((y-1,p)),quarter_ago=lookup.get(prev))
        d['comparison_dates']=comparisons
        if frequency=='quarterly':d['fiscal_comparison_dates']=copy.deepcopy(comparisons)
        # Generic percentage deltas invert the meaning of losses. Keep the
        # reported annual/half-year profit visible without that calculation.
        if metric=='profit' and frequency!='quarterly':d['change_mode']='none'
        return d

    for company in ['innoscience','infineon','powi']:
        meta=companies[company]
        for metric in names:
            id=f'mocvd_{company}_{metric}'
            if company=='infineon' and metric=='capex':continue # Existing ID and both cash series remain stable.
            note=meta['scope']
            if company=='innoscience':
                note+=' 2017년 7월 설립, 공개 재무자료는 2021년부터입니다. 분기 공시는 없으며 2023년부터 반기 비교가 가능합니다. 하반기는 연간−상반기로 계산했습니다. 영업손익은 공시의 Loss from operations이며 순손실·조정 EBITDA가 아닙니다.'
                if metric=='capex':note+=' 무형자산을 포함하는 합산 공시로 다른 회사의 유형자산만의 CAPEX와 범위가 다릅니다.'
                freq,rows,viewkey,viewlabel='semiannual',meta['halfyears'],'half','반기 · 2023년부터'
            elif company=='infineon':
                note+=' 9월 결산. 연간 FY2014–2025, 별도로 확인한 분기 FY2026 Q2·Q3를 제공합니다. 연간 수치를 분기로 배분하지 않았습니다. International Rectifier·Cypress 등 인수 전후 연결 범위가 다릅니다.'
                freq,rows,viewkey,viewlabel='quarterly',meta['quarters'],'quarter','분기 · 최근 공시'
            else:
                note+=' 12월 결산. 분기 2014 Q1–2026 Q2. Q4 및 현금 CAPEX는 필요한 경우 연간/누적 차분입니다.'
                if metric=='revenue':note+=' 2015년 최신 연간 공시와 과거 분기 합계는 기준 재작성으로 0.620백만 USD 차이가 있으며 원문 수치를 임의 조정하지 않았습니다.'
                if metric=='profit':note+=' 2019년 손익에는 ON Semiconductor와의 특허소송 합의 효과가 포함됩니다.'
                freq,rows,viewkey,viewlabel='quarterly',meta['quarters'],'quarter','분기'
            annual=make(id,meta,meta['annuals'],metric,note,'yearly')
            periodic=make(id,meta,rows,metric,note,freq)
            start=meta['annuals'][0]['year']
            default='quarter' if company=='powi' else 'annual'
            doc=copy.deepcopy(periodic if default==viewkey else annual)
            doc['default_view']=default
            doc['series_views']={viewkey:dict(periodic,label=viewlabel),'annual':dict(annual,label=f'연간 · {start}년부터')}
            docs[id]=doc

    coverage=docs['mocvd_coverage']
    coverage['note']+=' GaN 비교 기업: Innoscience 2021년부터 연간·2023년부터 반기, Infineon 2014년부터 연간, Power Integrations 2014년부터 분기 실적. 세 기업은 회사 전체 매출·영업이익·현금 CAPEX를 표시하며 GaN 사업 단독 수익성을 추정하지 않습니다.'

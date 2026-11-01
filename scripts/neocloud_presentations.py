"""Standard-size selectable neocloud charts, with exact periods and sources."""
import calendar,copy
from us_datacenter_financials import financial_document
from us_datacenter_presentations import axis_date

COLORS=['#2a78d6','#1baf7a','#eda100']
COMPARISONS={'revenue':('AI 클라우드 매출','cloud_revenue'),'profit':('전사 GAAP 영업이익','profit'),
             'margin':('전사 GAAP 영업이익률','margin'),'capex':('전사 현금 CAPEX','capex'),'rpo':('미이행 계약 잔액 · RPO','rpo')}
INDIVIDUAL={'cloud_share':('AI 클라우드 매출 비중','cloud_share'),'margin':('전사 GAAP 영업이익률','margin'),
            'capex':('전사 현금 CAPEX','capex'),'rpo':('RPO','rpo')}


def chart(identifier,title,field,keys,specs,cohorts,compare=False):
    views={};unit='%' if field in ('margin','cloud_share') else 'USD 백만'
    for kind,caption in [('rows','분기'),('annual','연간')]:
        series={};sources={};notes={};aggregate={};periods={};actual=[];lookup={};period_rows={}
        for key in keys:
            spec=specs[key];name=spec['name'];c=cohorts[key]
            rows=c['rpo'][kind] if field=='rpo' else c[kind]
            sources[name]={};notes[name]={};values={}
            valid=[r for r in rows if r.get(field) is not None]
            for r in valid:
                date=axis_date(r,kind) if compare else r['date'];value=r[field]
                if date in values:raise ValueError('Duplicate comparison period')
                values[date]=value;actual.append(r['date'])
                period=f"FY{r['year']}"+(f" Q{r['quarter']}" if kind=='rows' else '')
                ref=copy.deepcopy(r['refs'][field]);ref.update(period=period,observed_date=r['date'],period_start=r['start'])
                sources[name][date]=ref;periods[date]=(date[:4]+' Q'+str((int(date[5:7])+2)//3) if compare and kind=='rows' else 'FY'+date[:4] if compare else period)
                scope=spec['rpo_scope'] if field=='rpo' else spec['capex_scope'] if field=='capex' else spec['scope']
                notes[name][date]=[name+' · '+period,r['date']+' 기준 잔액' if field=='rpo' else r['start']+' ~ '+r['date'],scope,ref['calculation'],f'{value:,.4f} {unit}']
                a=aggregate.setdefault(date,dict(url=ref['url'],supporting_sources=[],source_separator=' / '))
                for part in [ref,*ref.get('components',[])]:
                    item=dict(url=part['url'],label=name+' · '+period)
                    if item not in a['supporting_sources']:a['supporting_sources'].append(item)
                lookup[(r['year'],r.get('quarter'))]=date;period_rows[date]=r
            if values:
                first,last=min(values),max(values);years=range(int(first[:4]),int(last[:4])+1)
                # Explicit nulls prevent a line from bridging undisclosed quarters.
                axis=([f'{y}-12-31' for y in years] if kind=='annual' else [f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]}' for y in years for m in (3,6,9,12)])
                if kind=='annual' and not compare:axis=sorted({r['date'] for r in rows})
                series[name]=[[d,values.get(d)] for d in axis if first<=d<=last]
            else:series[name]=[]
        views['quarter' if kind=='rows' else 'annual']=dict(label=caption,frequency='quarterly' if kind=='rows' else 'yearly',
            frequency_label=('분기 말 잔액' if kind=='rows' else '결산일 잔액') if field=='rpo' else caption+' · '+('기업 비교' if compare else '실제 회계기간'),
            quarter_labels=kind=='rows',year_labels=kind=='annual',annual_axis=kind=='annual',period_labels=periods,
            series=series,series_sources=sources,series_point_notes=notes,point_sources=aggregate,default_series=[n for n,s in series.items() if s],
            updated=max(actual,default=''),source_url=next((r['url'] for refs in sources.values() for r in reversed(list(refs.values()))),specs[keys[0]]['source_url']),
            comparison_dates={date:dict(year_ago=lookup.get((r['year']-1,r['quarter'])),quarter_ago=lookup.get((r['year']-(r['quarter']==1),r['quarter']-1 or 4))) for date,r in period_rows.items()} if not compare and kind=='rows' else {},
            quarterly_profit_summary=kind=='rows' and field=='profit',quarterly_revenue_summary=kind=='rows' and field in ('cloud_revenue','capex','rpo'),change_mode='none',
            empty_message='이 기간의 실제 공시값을 아직 확보하지 못했습니다. 미공개를 0으로 채우지 않습니다.')
    checked=min(cohorts[k]['checked'] for k in keys);healthy=all(cohorts[k]['core_ok'] and cohorts[k]['cloud_ok'] for k in keys)
    note={'rpo':'ASC 606 기말 미이행 계약 잔액입니다. 연간은 각 회사 결산일 잔액이며 합산·차분·이월하지 않습니다. CoreWeave Revenue backlog, IREN 리스 계약, Nebius 계약 총액·ARR과 구분합니다.',
          'capex':'실제 현금 투자액입니다. Nebius는 회사 공시의 유형·무형자산 취득, CoreWeave·IREN은 유형자산 취득입니다. 비현금 리스·미래 투자계획·가이던스는 합산하지 않습니다.',
          'profit':'클라우드 단독이 아닌 전사 GAAP 영업이익입니다. Nebius의 다른 사업과 IREN의 채굴·손상차손도 포함합니다. Adjusted EBITDA·순이익과 다릅니다.',
          'margin':'전사 GAAP 영업이익 / 같은 기간 전사 매출 × 100입니다. 클라우드 단독 이익률이 아니며 연간 비율은 연간 공시값으로 계산합니다.',
          'cloud_share':'실제 AI 클라우드 매출 / 같은 기간 연결 매출 × 100입니다. 연간은 연간 매출끼리 나누며 분기 비중을 평균하지 않습니다.',
          'cloud_revenue':'공시 AI 클라우드 매출입니다. Nebius·IREN의 다른 사업 매출과 ARR·계약 금액을 포함하지 않습니다. CoreWeave는 단일 AI 클라우드 보고 부문의 연결 매출입니다.'}[field]
    details=[dict(label=specs[k]['name']+' 범위',value=specs[k]['note']) for k in keys]
    details+=[dict(label='기간·지역',value='미국 상장 기업의 글로벌 실적입니다. Nebius는 네덜란드, IREN은 호주 본사입니다. IREN은 6월, 나머지는 12월 결산이며 비교 차트는 실제 종료일이 속한 달력 분기·FY 결산연도로 정렬합니다. 표에서 실제 기간을 확인하세요.'),dict(label='참고',value=note)]
    return dict(id=identifier,name=title,unit=unit,company_kpi=True,compact_ticks=True,compact_tooltip=True,span_gaps=False,
        company_comparison=True,comparison_metric=identifier.removeprefix('us_nc_'),series_unavailable={},
        series_colors={specs[k]['name']:COLORS[list(specs).index(k)] for k in keys},chart_type='bar' if field=='capex' and compare else 'line',
        description='기업 이름을 클릭해 동시에 비교할 항목을 선택하세요.' if compare else specs[keys[0]]['scope'],basis_details=details,
        source='SEC · 기업 공식 공시',fetched=min(cohorts[k]['fetched'] for k in keys),
        collection_status=dict(ok=healthy,checked=checked,message='공시 조회 완료' if healthy else '일부 공시 검토 필요 · 기존 이력 유지'),
        default_view='quarter',series_views=views,**{k:v for k,v in views['quarter'].items() if k!='label'})


def documents(specs,cohorts):
    result=[]
    for metric,(title,field) in COMPARISONS.items():
        result.append(chart('us_nc_compare_'+metric,title+' (기업별)',field,list(specs),specs,cohorts,True))
    for key,spec in specs.items():
        d=financial_document(key,spec,cohorts[key]);d.update(id=f'us_nc_{key}_financials',comparison_metric='neo_financials_'+key,compact_tooltip=True)
        result.append(d)
        for metric,(title,field) in INDIVIDUAL.items():result.append(chart(f'us_nc_{key}_{metric}',spec['name']+' · '+title,field,[key],specs,cohorts))
    return result

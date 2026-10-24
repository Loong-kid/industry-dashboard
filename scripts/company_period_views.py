"""Quarter/annual display choices without annualizing incomplete fiscal years."""
import re


def complete_years(doc):
    labels=doc.get('period_labels',{})
    periods={}
    for date,label in labels.items():
        match=re.search(r'(20\d{2})\s+Q([1-4])',label)
        if match:periods[date]=(int(match[1]),int(match[2]))
    dates={}
    for date,(year,quarter) in periods.items():
        if quarter==4:dates[year]=max(dates.get(year,''),date)
    values={}
    for name,points in doc['series'].items():
        buckets={}
        for date,value in points:
            if date not in periods or value is None:continue
            year,quarter=periods[date]
            buckets.setdefault(year,{}).setdefault(quarter,[]).append(value)
        values[name]={year:sum(q[0] for q in quarters.values()) for year,quarters in buckets.items()
                      if set(quarters)=={1,2,3,4} and all(len(q)==1 for q in quarters.values())}
    known=sorted({year for years in values.values() for year in years})
    axis={year:dates.get(year,f'{year}-12-31') for year in range(known[0],known[-1]+1)} if known else {}
    refs={}
    for year,date in axis.items():
        components=[]
        for qdate,(qyear,quarter) in sorted(periods.items()):
            if qyear!=year:continue
            ref=doc.get('point_sources',{}).get(qdate)
            if ref:
                components.append(dict(url=ref['url'],label=labels[qdate],**({'pdf_page':ref['pdf_page']} if ref.get('pdf_page') else {})))
        if components:refs[date]=dict(url=components[-1]['url'],label=f'FY{year} · 4개 분기 합계',supporting_sources=components,source_separator=' + ')
    return dict(series={name:[[date,years.get(year)] for year,date in axis.items()] for name,years in values.items()},
                period_labels={date:f'FY{year}' for year,date in axis.items()},point_sources=refs,
                source_url=refs[max(refs)]['url'] if refs else doc.get('source_url',''),
                updated=max(axis.values()) if axis else '',
                description=doc.get('description','')+' 연간은 동일한 회사 회계연도의 4개 분기를 모두 확보한 항목만 합산합니다. 미완료·미확보 연도는 연환산하거나 0으로 채우지 않습니다.')


def add_period_views(doc,annual=None):
    annual=annual if annual is not None else complete_years(doc)
    doc['default_view']='quarter'
    doc['series_views']={
        'quarter':dict(label='분기'),
        'annual':dict(label='연간',frequency='yearly',frequency_label='연간 · 회사 회계연도',quarter_labels=False,
                      year_labels=True,annual_axis=True,quarterly_revenue_summary=False,quarterly_profit_summary=False,
                      comparison_dates={},change_mode='none',**annual)}
    return doc

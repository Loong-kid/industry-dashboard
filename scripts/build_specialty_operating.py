"""Publish explicitly reviewed operating observations; never imply auto-refresh."""
import calendar
from fetch_cpu_companies import ROOT, load, save

SOURCE=ROOT/'manual/specialty-minerals/operating.json'

def build():
    snapshot=load(SOURCE,{})
    for chart in snapshot['charts']:
        actual={d for points in chart['series'].values() for d,v in points if v is not None}
        first,last=min(actual),max(actual)
        years=range(int(first[:4]),int(last[:4])+1)
        axis=[f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]}' for y in years for m in (3,6,9,12)]
        axis=[d for d in axis if first<=d<=last]
        series={name:[[d,dict(points).get(d)] for d in axis] for name,points in chart['series'].items()}
        labels={d:f'FY{d[:4]} Q{int(d[5:7])//3}' for d in axis}
        doc=dict(id=chart['id'],name=chart['name'],unit=chart['unit'],frequency='quarterly',frequency_label='분기 · 원문 검토 스냅샷',
            updated=last,fetched=snapshot['reviewed'],source='회사 공식 운영 공시 · 수동 검토',source_url=chart['source_url'],
            description=chart['description'],series=series,default_series=list(series),span_gaps=False,quarter_labels=True,
            period_labels=labels,company_kpi=True,change_mode='none',table_limit=100,
            point_sources={d:dict(url=chart.get('date_sources',{}).get(d,chart['source_url']),label=labels[d]) for d in actual},
            basis_details=[dict(label='갱신 방식',value=snapshot['note']+' 검토일: '+snapshot['reviewed'])])
        # Annual averages/prices/AISC must never be summed. Production snapshots
        # also stay quarterly until a complete, reviewed annual source exists.
        save(ROOT/'data/commodities'/(doc['id']+'.json'),doc)

if __name__=='__main__':build()

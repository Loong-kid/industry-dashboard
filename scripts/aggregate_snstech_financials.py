"""Offline S&S Tech quarterly financial charts, including reviewed 2014 history.

Run after aggregate_snstech.py: it preserves the trade comparison charts while
building the revenue, operating-profit and cash PP&E acquisition cards together.
Reviewed normalized source facts are data/_snstech/financial_quarters.json.
"""
import csv
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'data/_snstech/financial_quarters.json'

def build(raw, trade):
    rows=sorted(raw['quarters'],key=lambda r:r['date'])
    if len(rows)!=len({(r['year'],r['quarter']) for r in rows}):raise ValueError('Duplicate fiscal quarter')
    periods={(r['year'],r['quarter']):r['date'] for r in rows}
    for r in rows:
        for metric in ['revenue','profit','capex']:
            if not isinstance(r[metric],(float,int)) or not math.isfinite(r[metric]) or not r['sources'][metric]:raise ValueError('Missing financial fact or source')
        if r['date']>raw['checked']:raise ValueError('Future financial fact')
    docs={}
    for metric,label in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
        id_='snstech_'+('operating_profit' if metric=='profit' else metric)
        series={label:[[r['date'],round(r[metric]/1_000_000,6)] for r in rows]}
        if metric=='revenue':
            for field in ['내수','수출']:
                points=[[r['date'],float(r[field])] for r in trade if r.get(field)]
                if points:series[field]=points
        refs={}
        for r in rows:
            sources=r['sources'][metric]
            refs[r['date']]={**sources[0],'label':f"{r['year']} Q{r['quarter']} · "+sources[0]['label'],'supporting_sources':sources,'source_separator':' / '}
        docs[id_]=dict(id=id_,name='에스앤에스텍 · '+label,unit='₩백만',frequency='quarterly',frequency_label='분기 · DART 공시',source='DART · 에스앤에스텍 연결 재무제표',source_url=refs[rows[-1]['date']]['url'],updated=rows[-1]['date'],fetched=raw['checked'],manual=True,span_gaps=False,quarter_labels=True,company_kpi=True,quarterly_revenue_summary=metric!='profit',quarterly_profit_summary=metric=='profit',series=series,default_series=[label],period_labels={r['date']:f"{r['year']} Q{r['quarter']}" for r in rows},comparison_dates={r['date']:dict(year_ago=periods.get((r['year']-1,r['quarter'])),quarter_ago=periods.get((r['year']-(r['quarter']==1),(r['quarter']-2)%4+1))) for r in rows},point_sources=refs,table_limit=100,description='연결 공시 기준의 분기 '+label+'입니다. '+('현금흐름표 유형자산 취득 지출이며 무형자산·장부잔액·투자계획은 포함하지 않습니다.' if metric=='capex' else '회사 전체 기준이며 블랭크마스크·EUV 제품별 실적과 구분합니다.'),note='2014년부터 확정 분기값을 제공합니다. 영업이익·매출은 공시 3개월 금액, 4분기는 연간−3분기 누적입니다. CAPEX는 누적 현금 지출의 차분입니다. 2014년 상반기 손익은 후속 보고서의 계속영업 재분류 비교값을 적용했습니다.'+(' 내수·수출은 기존 사업 내용의 매출 구성으로 연결 매출과 범위가 다를 수 있습니다.' if metric=='revenue' else ''))
        docs[id_]['note']+=' 2015~2024년은 완료된 다음 회계연도 비교표를 우선 적용했습니다. 공시된 3개월 금액을 보존했으며, 누적 금액과 차이가 있는 연도는 임의 보정하지 않았습니다.'
        differences=[c for c in raw['annual_checks'] if c['metric']==metric and c['difference']]
        if differences:
            docs[id_]['note']+=' 분기 합계−연간 공시 차이: '+', '.join(f"{c['year']}년 {c['difference']/1_000_000:+.6f}백만 원" for c in differences)+'.'
        docs[id_]['annual_reconciliation']=[c for c in raw['annual_checks'] if c['metric']==metric]
    return docs

def main():
    raw=json.loads(INPUT.read_text(encoding='utf-8'))
    with (ROOT/'manual/snstech.csv').open(encoding='utf-8-sig',newline='') as f:trade=list(csv.DictReader(f))
    for id_,doc in build(raw,trade).items():(ROOT/'data/semicon'/f'{id_}.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built S&S Tech revenue, operating profit and cash CAPEX charts.')

if __name__=='__main__':main()

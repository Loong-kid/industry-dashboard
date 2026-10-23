"""Build the wafer macro dashboard; automatically check public GWC monthly sales.

SEMI and company financials are reviewed snapshots. No credentials, price
estimates, fabricated quarters, FX aggregation or chart-axis digitization.
"""
import argparse
import calendar
import copy
import datetime as dt
import json
import math
from pathlib import Path

import requests
from import_wafer_financials import gw_monthly

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOT=ROOT/'manual/silicon_wafer.json'
CACHE=ROOT/'data/_wafer/gw_monthly.json'
GWC='https://www.sas-globalwafers.com/en/investor/financial-information_en/'


def merge_monthly(previous,current):
    if current[-1][0]<previous[-1][0]:raise ValueError('Monthly source regressed')
    return [[d,v] for d,v in sorted({**dict(previous),**dict(current)}.items())]


def write(path,doc):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')


def validate(snapshot):
    asof=snapshot['reviewed']
    for company,meta in snapshot['companies'].items():
        for key in ['annuals','quarters']:
            rows=meta.get(key,[]);dates=set()
            for r in rows:
                dt.date.fromisoformat(r['date'])
                if r['date'] in dates or r['date']>asof:raise ValueError('Duplicate/future observation')
                dates.add(r['date'])
                for metric in ['revenue','profit','capex','cash_capex','acceptance_capex','ebitda']:
                    if metric not in r:continue
                    if not isinstance(r[metric],(int,float)) or not math.isfinite(r[metric]):raise ValueError('Invalid financial fact')
                    if metric not in ['profit','ebitda'] and r[metric]<0:raise ValueError('Negative spending/revenue')
                    if not r['refs'][metric]['url'].startswith('https://'):raise ValueError('Missing source')
    for key in ['quarters','annuals']:
        dates=[r['date'] for r in snapshot['semi'][key]]
        if dates!=sorted(set(dates)):raise ValueError('SEMI duplicate/unsorted period')


def chart(id,name,unit,rows,fields,note,fetched,frequency='quarterly'):
    points={label:[[r['date'],r[k]] for r in rows if k in r] for k,label in fields.items()}
    points={k:v for k,v in points.items() if v}
    dates=sorted({d for s in points.values() for d,v in s})
    refs={}
    for r in rows:
        sources=[r['refs'][k] for k in fields if k in r and k in r['refs']]
        if sources:refs[r['date']]=dict(sources[0],supporting_sources=sources)
    # Explicit null quarters keep an uncollected interval from appearing as
    # a continuous straight line. They carry no financial fact/source.
    if frequency=='quarterly':
        slots={}
        for y in range(int(dates[0][:4]),int(dates[-1][:4])+1):
            for q in range(1,5):
                m=q*3;d=f'{y}-{m:02}-{calendar.monthrange(y,m)[1]}'
                if dates[0]<=d<=dates[-1]:slots[d]=None
        points={label:sorted({**slots,**dict(series)}.items()) for label,series in points.items()}
    doc=dict(id=id,name=name,unit=unit,frequency=frequency,manual=True,
             fetched=fetched,updated=dates[-1],source='공식 산업 통계·기업 IR·공시',source_url=refs[dates[-1]]['url'],
             description=note,series=points,default_series=list(points),point_sources=refs,
             period_labels={r['date']:r['period'] for r in rows},quarter_labels=frequency=='quarterly',year_labels=frequency=='yearly',
             span_gaps=False,change_mode='none')
    if frequency=='quarterly' and unit!='%':
        doc['quarterly_profit_summary']=id.endswith('_profit')
        doc['quarterly_revenue_summary']=not doc['quarterly_profit_summary']
    return doc


def alternate(annual,quarter,default='quarter',annual_label='연간 · 2014년부터',quarter_label='분기'):
    doc=copy.deepcopy(quarter if default=='quarter' else annual)
    doc.update(default_view=default,series_views={'quarter':dict(quarter,label=quarter_label),'annual':dict(annual,label=annual_label)})
    return doc


def build(snapshot,monthly=None):
    validate(snapshot);fetched=snapshot['reviewed'];docs={};semi=snapshot['semi']
    note='SEMI SMG 공표 출하면적입니다. 반도체용 실리콘 웨이퍼이며 태양광용은 제외합니다. 웨이퍼 제조사의 고객 출하량으로 팹의 실제 투입량·칩 생산량과 다릅니다. 2015 Q2는 공개9개월 합계−Q1−Q3 차분. 일부 연간 합계와 분기 합계는1 MSI 반올림 차이가 있습니다. 옛 발표의 범위·정정과 최신 통계 정의는 원문을 함께 확인하세요.'
    id='wafer_global_shipments'
    a=chart(id,'글로벌 실리콘 웨이퍼 출하면적','MSI · 백만 제곱인치',semi['annuals'],{'value':'연간 출하면적'},note,fetched,'yearly')
    q=chart(id,a['name'],a['unit'],semi['quarters'],{'value':'분기 출하면적'},note,fetched)
    docs[id]=alternate(a,q)
    growth=[];values={r['date']:r for r in semi['quarters']}
    for i,r in enumerate(semi['quarters']):
        previous=semi['quarters'][i-1] if i else None;prior=values.get(str(r['year']-1)+r['date'][4:])
        v=dict(r,refs={})
        for metric,base in [('yoy',prior),('qoq',previous)]:
            if base:
                v[metric]=round((r['value']/base['value']-1)*100,3)
                v['refs'][metric]=dict(r['refs']['value'],calculation='(current/prior -1)*100',supporting_sources=[r['refs']['value'],base['refs']['value']])
        growth.append(v)
    docs['wafer_global_growth']=chart('wafer_global_growth','글로벌 출하면적 증가율','%',growth,{'yoy':'YoY','qoq':'QoQ'},'분기 출하면적으로 계산합니다. QoQ는 계절성의 영향을 받으므로 YoY와 함께 읽습니다.',fetched)
    docs['wafer_global_revenue']=chart('wafer_global_revenue','글로벌 웨이퍼 시장 매출','십억 USD',semi['annuals'],{'revenue':'연간 매출'},'SEMI 연간 시장 매출, 공표 표의0.1십억 USD 단위 반올림값입니다. 분기 매출로 배분하지 않습니다. 매출÷면적은 구경·제품 구성·환율 변화가 섞이므로 웨이퍼 가격 지표로 만들지 않습니다.',fetched,'yearly')
    for company in ['sumco','siltronic','globalwafers']:
        meta=snapshot['companies'][company]
        for metric,title in [('revenue','매출'),('profit','영업이익'),('capex','CAPEX')]:
            id=f'wafer_{company}_{metric}';fields={metric:'연결 매출' if metric=='revenue' else '연결 영업이익' if metric=='profit' else '현금 CAPEX'}
            note=meta['scope']
            if company=='siltronic' and metric=='capex':
                fields={'capex':'유형·무형자산 투자액 · 발생 기준','cash_capex':'현금 지급액 · 별도 공시'}
                note+=' FY2017 분기표의 투자액 합계가 연간과 불일치하여 해당 분기 투자액은 표시하지 않고 연간123.2백만 EUR를 유지합니다.'
            a=chart(id,meta['name']+' · '+title,meta['unit'],meta['annuals'],fields,note,fetched,'yearly')
            qfields={metric:next(iter(fields.values()))}
            if company=='sumco' and metric=='capex':qfields={'acceptance_capex':'검수 기준 CAPEX · 현금 지출 아님'}
            q=chart(id,a['name'],a['unit'],meta['quarters'],qfields,note+(' 분기 IR 금액은0.1십억 JPY 단위에서 백만 JPY로 환산한 반올림값입니다.' if company=='sumco' else ''),fetched)
            if company=='sumco' and metric=='capex':q['name']='SUMCO · CAPEX · 검수 기준'
            default='annual' if company=='sumco' else 'quarter'
            docs[id]=alternate(a,q,default=default,annual_label='연간 · 현금 지출' if company=='sumco' and metric=='capex' else '연간 · 2016년부터' if company=='globalwafers' and metric=='capex' else '연간 · 2014년부터',quarter_label='분기 · 검수 기준' if company=='sumco' and metric=='capex' else '분기 · 확보 구간')
    meta=snapshot['companies']['siltronic']
    docs['wafer_siltronic_ebitda']=alternate(
        chart('wafer_siltronic_ebitda','Siltronic · EBITDA','백만 EUR',meta['annuals'],{'ebitda':'EBITDA'},'회사 공표 EBITDA입니다. 영업이익(EBIT)·현금흐름과 구분합니다.',fetched,'yearly'),
        chart('wafer_siltronic_ebitda','Siltronic · EBITDA','백만 EUR',meta['quarters'],{'ebitda':'EBITDA'},'회사 공표 EBITDA입니다. 영업이익(EBIT)·현금흐름과 구분합니다.',fetched))
    monthly=monthly or snapshot['gw_monthly'];rows=[];lookup=dict(monthly['points'])
    for i,(date,value) in enumerate(monthly['points']):
        r=dict(date=date,period=date[:7],value=value,refs={'value':dict(url=GWC,label=date[:7])})
        month=int(date[:4])*12+int(date[5:7]);window=[(d,v) for d,v in monthly['points'] if month-2<=int(d[:4])*12+int(d[5:7])<=month]
        if len(window)==3:r.update(ma3=round(sum(v for d,v in window)/3,3));r['refs']['ma3']=dict(url=GWC,label=date[:7],calculation='mean of3 consecutive observed calendar months')
        year_ago=next((v for d,v in monthly['points'] if int(d[:4])==int(date[:4])-1 and d[5:7]==date[5:7]),None)
        if year_ago:r['yoy']=round((value/year_ago-1)*100,3);r['refs']['yoy']=dict(url=GWC,label=date[:7],calculation='(current/prior year same month -1)*100')
        rows.append(r)
    docs['wafer_globalwafers_monthly']=chart('wafer_globalwafers_monthly','GlobalWafers · 월 매출','백만 TWD',rows,{'value':'월 매출','ma3':'3개월 이동평균'},'회사 자체 연결 월 매출입니다. 공시 표의 백만 TWD 반올림값이며 분기 재무제표와 소액 차이가 날 수 있습니다. 모회사 SAS 매출을 합산하지 않습니다. 2016년 인수 전후 연결 범위가 다릅니다.',monthly['fetched'],'monthly')
    docs['wafer_globalwafers_monthly_yoy']=chart('wafer_globalwafers_monthly_yoy','GlobalWafers · 월 매출 증가율','%',rows,{'yoy':'전년 동월 대비'},'월 매출 공표값으로 계산한 YoY입니다. 명절·출하 일정·환율·제품 구성이 영향을 줄 수 있으며 글로벌 출하면적을 대신하지 않습니다.',monthly['fetched'],'monthly')
    for id in ['wafer_globalwafers_monthly','wafer_globalwafers_monthly_yoy']:docs[id]['manual']=False
    shin=json.loads((ROOT/'data/semicon/shinetsu_materials_revenue.json').read_text(encoding='utf-8'))
    shin.update(id='wafer_shinetsu_reference',name='참고 · 신에츠 전자재료 매출',description='웨이퍼 외 포토레지스트·블랭크마스크·희토류 자석 등을 포함하는 상위 사업부입니다. 웨이퍼 단독 매출·이익·시장점유율로 해석하지 않습니다.')
    shin['note']=shin['note'].replace('블랭크마스크','실리콘 웨이퍼');docs[shin['id']]=shin
    docs['wafer_customer_evidence']=dict(id='wafer_customer_evidence',name='구경별 수요와 고객 재고 · SUMCO 원문 그래프',description='SUMCO의 추정이며 업계 전체 확정 통계가 아닙니다. 재고 그래프에 수치 축이 없어 절대 수치를 추출하지 않고 원문을 제공합니다. 상단 기간 선택은 아래 원문 이미지에 적용되지 않습니다.',figures=snapshot['figures'],updated=max(f['date'] for f in snapshot['figures']),fetched=fetched)
    docs['wafer_supply_events']=dict(id='wafer_supply_events',name='공급·증설·가동 기록',description='공표일 당시 확인된 사실·회사 전망을 구분합니다. 개장·고객 인증·완전가동은 다른 단계입니다.',columns=[['company','기업'],['date','공표일'],['project','대상'],['stage','단계'],['detail','공표 내용'],['timing','실적·목표 시점']],rows=snapshot['events'],note='계획·전망은 목표일이 지났다는 이유로 완료 처리하지 않습니다. 숫자가 없는 가동률·생산능력은 임의 추정하지 않습니다.',updated=max(r['date'] for r in snapshot['events']),fetched=fetched)
    return docs


def main():
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--as-of',default=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat())
    a=p.parse_args();snapshot=json.loads(SNAPSHOT.read_text(encoding='utf-8'));monthly=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else snapshot['gw_monthly'];error=None
    if not a.offline:
        try:
            r=requests.get(GWC,timeout=(10,30));r.raise_for_status();points=gw_monthly(r.text,a.as_of)
            points=merge_monthly(monthly['points'],points)
            monthly=dict(url=GWC,fetched=a.as_of,points=points);write(CACHE,monthly)
        except Exception as exc:error=exc
    docs=build(snapshot,monthly)
    for id,doc in docs.items():write(ROOT/'data/semicon'/f'{id}.json',doc)
    print(len(docs),'wafer documents built')
    if error:raise RuntimeError('Monthly collector failed; cached observations preserved') from error


if __name__=='__main__':main()

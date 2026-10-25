"""SEC financial history and original-report compressor operating statistics."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path

from bs4 import BeautifulSoup

from collect_midstream_sources import CACHE,collect as download
from fetch_cpu_companies import TAGS,build_company,parse_facts,parse_annual,reference,save,today
from midstream_sources import SPECS,HP_NOTES,archrock_operating_facts,horsepower_tables,quarter_date,ipo_revenue_rows

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/natgas'
STATE=OUT/'midstream_state.json'
METRICS=['revenue','profit','capex']

def load(path,default):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else default

def reconcile_quarters(payload,spec,rows,annual,asof):
    """Only calculate Q4 when the earlier quarters reconcile to a real 9M.

    Restated annuals and incompatible predecessor quarters are never silently
    spliced. Retain the annual and show explicit gaps in the affected metric.
    """
    issues=[]
    for y in annual:
        qs=[r for r in rows if r['year']==y['year']]
        if not {1,2,3}.issubset({r['quarter'] for r in qs}):continue
        for metric in METRICS:
            first=[r for r in qs if r['quarter']<=3]
            if metric not in y or not all(metric in r for r in first):continue
            if len(first)!=3:continue
            tags=spec.get('tags',{}).get(metric,TAGS[metric]);candidates=[]
            for priority,tag in enumerate(tags):
                for f in payload['facts']['us-gaap'].get(tag,{}).get('units',{}).get('USD',[]):
                    if f.get('start')!=f"{y['year']}-01-01" or f['end']!=f"{y['year']}-09-30" or f['filed']>min(asof,y['refs'][metric]['filed']):continue
                    if f.get('form') not in ['10-K','10-Q','10-K/A','10-Q/A']:continue
                    candidates.append(dict(f,tag='us-gaap:'+tag,rank=(f['filed'],-priority)))
            previous=max(candidates,key=lambda f:f['rank']) if candidates else None
            tolerance=max(.005,abs(y[metric])*.00005)  # report rounding only
            earlier=sum(r[metric] for r in first)
            consistent=previous and abs(earlier-previous['val']/1e6)<=tolerance
            q4=next((r for r in qs if r['quarter']==4),None)
            if consistent:
                value=y[metric]-previous['val']/1e6
                if metric!='profit' and value<0:consistent=False
                else:
                    if q4 is None:
                        q4=dict(date=y['date'],start=f"{y['year']}-10-01",year=y['year'],quarter=4,refs={});rows.append(q4);qs.append(q4)
                    q4[metric]=value
                    q4['refs'][metric]=dict(y['refs'][metric],components=[y['refs'][metric],reference(previous,spec['cik'])],calculation='reported annual minus reconciled same-year 9M')
            if not consistent and (q4 is None or metric not in q4 or abs(sum(r.get(metric,0) for r in qs)-y[metric])>tolerance):
                for r in qs:r.pop(metric,None);r['refs'].pop(metric,None)
                issues.append(dict(year=y['year'],metric=metric,reason='분기 합계·9개월·재작성 연간의 범위 또는 공시 빈티지 불일치. 해당 분기 지표는 보류하고 공표 연간을 유지'))
    return sorted(rows,key=lambda r:r['date']),issues

def merge_hp(previous,updates,asof):
    rows={r['date']:copy.deepcopy(r) for r in previous}
    for update in updates:
        if update['date']>asof or update['ref']['filed']>asof:continue
        row=rows.setdefault(update['date'],dict(date=update['date'],refs={}))
        for field in ['available','operating','utilization']:
            if field not in update:continue
            ref=update['ref'];prior=row['refs'].get(field,{})
            if ref['filed']>=prior.get('filed',''):
                row[field]=update[field];row['refs'][field]=ref
    return [r for _,r in sorted(rows.items())]

def hp_documents(key,cohort):
    rows=cohort['hp'];bydate={r['date']:r for r in rows};axis=set(bydate)
    for year in range(int(rows[0]['date'][:4]),int(rows[-1]['date'][:4])+1):
        for q in range(1,5):
            date=quarter_date(year,q)
            if rows[0]['date']<date<rows[-1]['date']:axis.add(date)
    docs={}
    for suffix,fields,unit,title in [('horsepower',{'available':'가용 마력 · Total available HP' if key!='kgs' else 'Fleet horsepower · 압축기 보유 마력','operating':'가동 마력 · Total operating HP' if key=='aroc' else 'Revenue-generating HP · 수익 발생 마력'},'천 HP','압축기 가용·가동 마력'),('utilization',{'utilization':'회사 공표 기말 가동률'},'%','압축기 가동률')]:
        labels={r['date']:f"{r['date'][:4]} Q{(int(r['date'][5:7])-1)//3+1} · 기말" for r in rows}
        refs={}
        for r in rows:
            sources=[r['refs'][field] for field in fields if field in r.get('refs',{})]
            if sources:refs[r['date']]=dict(url=sources[0]['url'],label=labels[r['date']],supporting_sources=[dict(url=s['url'],label=s['location']) for s in sources])
        if not refs:continue
        id=f'compressor_{key}_{suffix}'
        docs[id]=dict(id=id,name=SPECS[key]['name']+' · '+title,unit=unit,frequency='quarterly',frequency_label='분기 말 잔량 · 합산하지 않음',quarter_labels=True,period_labels=labels,
            fetched=cohort['fetched'],updated=max(refs),source='SEC 정기보고서 · 기업 원문',source_url=refs[max(refs)]['url'],
            description=HP_NOTES[key],series={label:[[d,bydate.get(d,{}).get(field)] for d in sorted(axis)] for field,label in fields.items()},default_series=list(fields.values()),
            point_sources=refs,span_gaps=False,change_mode='none',table_limit=100,
            basis_details=[dict(label='지표 정의',value=HP_NOTES[key]),dict(label='분기·단위',value='기말 시점의 잔량입니다. 연간 합산·분기 평균·완제품 출하량이 아닙니다. 1천 HP = 1,000 horsepower. 미공개 값은 0으로 채우거나 반올림 가동률로 역산하지 않습니다.')])
        if not cohort.get('ok',True):docs[id]['collection_status']=dict(ok=False,checked=cohort['checked'],message='새 공시 확인 실패 · 기존 이력 보존')
    return docs

def collect(offline=False,full=False):
    asof=today();state=load(STATE,dict(companies={}))
    failed=False
    statuses={}
    if not offline:
        try:statuses=download(full)
        except Exception as error:failed=True;print('Source download incomplete:',type(error).__name__)
    docs={}
    for key,spec0 in SPECS.items():
        prior=state['companies'].get(key,{})
        try:
            if not offline and (failed or not statuses.get(key,{}).get('ok')):raise ValueError('Latest source check failed')
            payload=load(CACHE/f'{key}-facts.json',None)
            if payload is None:raise ValueError('No original company facts')
            hp_updates=[];operating=prior.get('operating_facts',[]);ipo=prior.get('ipo_rows',[])
            if key in HP_NOTES:
                for meta in load(CACHE/f'{key}-filings.json',{}).values():
                    if meta['filed']>asof:continue
                    soup=BeautifulSoup((CACHE/meta['path']).read_bytes(),'html.parser')
                    hp_updates += horsepower_tables(soup,key,meta)
                    if key=='aroc':operating += archrock_operating_facts(soup,meta,payload)
                    if key=='kgs' and meta['form'].startswith('S-1'):ipo += ipo_revenue_rows(soup,meta)
            if key=='aroc':
                operating=list({(f['start'],f['end'],f['accn']):f for f in operating}.values())
                payload['facts']['us-gaap']['OperatingIncomeLoss']=dict(units={'USD':operating})
            rows=parse_facts(payload,spec0,asof);annual=parse_annual(payload,spec0,asof)
            scope_issues=[]
            if key=='aroc':
                # A pre-spin income statement may have world-wide costs while
                # later revenue comparatives show continuing US operations.
                # Reject that mix before considering an annual/9M difference.
                for row in rows:
                    ref=row.get('refs',{}).get('profit',{})
                    inputs=ref.get('components',[])
                    if 'profit' not in row or not inputs:continue
                    if all('inputs' in item for item in inputs):
                        implied=inputs[0]['inputs']['revenue']-sum(item['inputs']['revenue'] for item in inputs[1:])
                        if abs(implied/1e6-row['revenue'])>max(.005,abs(row['revenue'])*.00005):
                            row.pop('profit');row['refs'].pop('profit')
                            scope_issues.append(dict(year=row['year'],metric='profit',reason='분할 이전 원가 범위와 재작성 계속사업 매출 범위 불일치'))
            if key=='kgs':
                bydate={r['date']:r for r in rows}
                for row in ipo:
                    if row['date'] not in bydate:bydate[row['date']]=row
                rows=sorted(bydate.values(),key=lambda r:r['date'])
            rows,issues=reconcile_quarters(payload,spec0,rows,annual,asof)
            issues=list({(item['year'],item['metric']):item for item in issues+scope_issues}.values())
            if prior.get('rows') and rows[-1]['date']<prior['rows'][-1]['date']:raise ValueError('Regressing source')
            cohort=dict(rows=rows,annual=annual,fetched=asof,checked=asof,ok=not failed,issues=issues)
            if key in HP_NOTES:
                hp_updates+=load(ROOT/'manual/midstream_hp_supplement.json',{}).get('companies',{}).get(key,[])
                cohort['hp']=merge_hp([] if full else prior.get('hp',[]),hp_updates,asof)
            if key=='aroc':cohort['operating_facts']=operating
            if key=='kgs':cohort['ipo_rows']=list({r['date']:r for r in ipo}.values())
        except Exception as error:
            if not prior:raise
            cohort=dict(prior,checked=asof,ok=False);print(key,'retained:',type(error).__name__)
        state['companies'][key]=cohort
        spec=copy.deepcopy(spec0)
        spec['revenue_description']='회사 전체 연결 매출이며 상품 매매·인수·매각·연결 범위 변경을 포함합니다. 천연가스 운송 수수료 매출만의 수치가 아닙니다.'
        spec['capex_label']='현금 CAPEX · 회사 공시 기준'
        spec['capex_description']='현금흐름표의 자본적 지출(유형·생산자산 취득)입니다. 기업 인수 대금·JV 투자·순매각대금·비현금 리스는 별도이며 회사 발표의 growth / sustaining / net CAPEX와 다를 수 있습니다.'
        if key=='aroc':spec['profit_description']='회사에 공표 영업이익 소계가 없어 매출에서 원가·판관비·감가상각·손상·구조조정·재작성·거래 비용을 차감한 계산 영업손익입니다. 자산매각손익·기타손익·금융손익은 제외합니다. 공표 GAAP 영업이익 또는 조정 EBITDA로 표시하지 않습니다.'
        spec['note']=spec['scope']+'. '+spec['capex_description']
        group=build_company(key,cohort,spec)
        for id,doc in group.items():
            doc['basis_details'][1]['value']='공표 연간과 분기를 각각 보존합니다. Q4는 앞선 3개 분기가 공표 9개월 누적과 일치할 때만 연간 − 9개월로 계산합니다. 비교 범위가 맞지 않는 과거 분기는 공백으로 남기며 카드 아래에 보류 연도를 표시합니다.'
            metric=id.rsplit('_',1)[-1]
            years=[str(item['year']) for item in cohort['issues'] if item['metric']==metric]
            if years:doc['note']='분기 자료 보류: '+', '.join(years)+'년. 합계·누적·연간의 공시 범위가 일치하지 않아 분기를 표시하지 않습니다. 연간 버튼에서 공표 실적을 볼 수 있습니다.'
            if key=='kgs':doc['description']+=' 2023년 IPO 자료의 공개 비교 이력까지만 제공하며 2014년까지 비상장 실적을 추정하지 않습니다.'
            if metric=='profit' and key=='aroc':doc['name']=spec['name']+' · 영업손익(계산)'
        docs.update(group)
        if key in HP_NOTES:docs.update(hp_documents(key,cohort))
        print(key,len(cohort['rows']),'financial quarters;',len(cohort.get('hp',[])),'HP dates;',len(cohort['issues']),'withheld metrics',flush=True)
    save(STATE,state)
    for id,doc in docs.items():save(OUT/(id+'.json'),doc)
    print('Published',len(docs),'midstream/compressor charts')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--full',action='store_true')
    args=parser.parse_args();collect(args.offline,args.full)

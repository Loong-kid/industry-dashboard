"""National budgets: anonymous official downloads, OMB and Treasury, CBO vintages."""
import argparse
import datetime as dt
import hashlib
from collections import defaultdict
import requests

from national_budget_sources import (ROOT,CACHE,Client,FUNCTIONS,KR_BASE,GRID,KR_ODT,KR_SOURCE,
    OMB_BASE,CBO_BASE,aggregate_accounts,cbo_vintages,kr_grid,kr_accounts,load,number,omb_files,
    parse_mts,parse_omb,save,today)

OUT=ROOT/'data/national-budget'
LABELS={'spending':'총지출','revenue':'총수입','balance':'재정수지','managed_balance':'관리재정수지',
        'mandatory':'의무지출','discretionary':'재량지출','interest':'순이자','debt':'국가채무·공공보유 연방채무','debt_gdp':'채무 / GDP'}

def public_rows(client,name,odt,ds,conditions,refresh=True):
    args=dict(odtId=odt,dsId=ds,rlsSvTyCd='S',odtSvSeq='1',pageIndex='1',pageSize='10000',selectWon='',decimalPointLevel='3',traDataFextNm='DATA',**conditions)
    rows=client.json(name,KR_BASE+GRID,body=args,refresh=refresh)
    if not isinstance(rows,list):raise ValueError('Unexpected Korean public sheet response')
    if rows and len(rows)!=int(rows[0]['PAGE_TOT_CNT']):raise ValueError('Incomplete Korean public sheet')
    return rows

def collect_kr(client):
    asof=today();current=int(asof[:4]);sectors={};programs={};totals={'approved':{},'proposal':{}}
    counts={}
    for year in range(2014,current+2):
        raw=kr_grid(client,year)
        if not raw:continue # Next year's proposal has not been published yet.
        rows=kr_accounts(raw);counts[str(year)]=len(rows)
        sums={b:sum(r[b] for r in rows) for b in totals}
        if max(sums.values())<100:raise ValueError('Korean annual download is not a complete national budget')
        for b,total in sums.items():
            # A future unvoted column is filled with zero by the source. Do not
            # turn an unavailable national budget into thousands of real zeros.
            if total>0:totals[b][str(year)]=round(total,6)
        for row in rows:
            sid=row['sector'];sector=sectors.setdefault(sid,dict(id=sid,name=sid,values={'approved':{},'proposal':{},'actual':{}}))
            p=programs.setdefault(row['id'],dict(id=row['id'],sector=sid,agency=row['agency'],account=row['account'],program=row['program'],name=row['name'],values={'approved':{},'proposal':{}}))
            for b in totals:
                if str(year) not in totals[b]:continue
                p['values'][b][str(year)]=round(p['values'][b].get(str(year),0)+row[b],9)
                sector['values'][b][str(year)]=sector['values'][b].get(str(year),0)+row[b]
        print('KR',year,len(rows),'program rows', {b:round(v,1) for b,v in sums.items()},flush=True)
    # Official fiscal balance sheet: cumulative monthly cash totals. Only the
    # December observation is an annual actual; incomplete years stay separate.
    balances=public_rows(client,'kr-balances.json','45DHAZ24H7WWJ0VG03Q666V46','TB_OPFI172',{'OJ_YY':f'2014,{current}'})
    macro={m:{} for m in ['spending','revenue','balance','managed_balance']};progress=None
    for r in sorted(balances,key=lambda r:(r['OJ_YY'],r['OJ_M'])):
        vals={m:number(r.get(k)) for m,k in [('spending','TOT_EP_SUM_AMT'),('revenue','TOT_RV_SUM_AMT'),('balance','ITG_PFIN_RAD_AMT'),('managed_balance','MG_PFIN_RAD_AMT')]}
        if r['OJ_M']=='12':
            for m,v in vals.items():
                if v is not None:macro[m][r['OJ_YY']]=v
        else:progress=dict(year=r['OJ_YY'],month=r['OJ_M'],values=vals)
    # Published 16-sector statistics retain explicit budget/settlement labels.
    # Archive editions can lag the current budget: never substitute one basis.
    actual_source=KR_BASE+'/op/ko/sd/UOPKOSDA01?odtId=5JVB22KUDE71A1SMR67O50R63'
    meta=client.json('kr-sector-metadata.json',KR_BASE+'/op/ko/sm/preview/rowSheet/getPreviewInfo.do',body={'odtId':'5JVB22KUDE71A1SMR67O50R63','rlsSvTyCd':'S','odtSvSeq':'1'},refresh=True)
    edition=int(next(x['fltColBasVal'] for x in meta['rowSheetCond'] if x['dsColId']=='ACNT_YR'))
    stats=[]
    for book in range(2014,edition+1):
        stats.extend(public_rows(client,f'kr-sector-actuals-{book}.json','5JVB22KUDE71A1SMR67O50R63','VW_OPFI165',{'ACNT_YR':f'{book},{book}'},refresh=book>=current-1))
    chosen={}
    import re
    for row in stats:
        if '결산' not in (row.get('DIV_NM') or ''):continue
        match=re.search(r'20\d{2}',row.get('ALY_YR_NM') or str(row.get('ACNT_YR','')))
        if not match:continue
        year=match[0];name=row['FLD_NM'];name='통일·외교' if name=='외교·통일' else name;key=(name,year);edition=str(row['ACNT_YR'])
        if int(year)<2014 or int(year)>=current:continue
        if key not in chosen or edition>chosen[key][0]:chosen[key]=(edition,number(row['SUM_AMT']))
    for (name,year),(edition,value) in chosen.items():
        if name in sectors and value is not None:sectors[name]['values']['actual'][year]=value
    actual_totals={}
    for sector in sectors.values():
        for basis,values in sector['values'].items():
            sector['values'][basis]={y:round(v,6) for y,v in sorted(values.items())}
        for y,v in sector['values']['actual'].items():actual_totals[y]=actual_totals.get(y,0)+v
    totals['actual']={y:round(v,6) for y,v in actual_totals.items()}
    macro['spending'].update(totals['actual'])
    bases=[dict(id='approved',label='국회확정 본예산',note='예산·기금의 총지출 기준. 추경 및 결산과 구분합니다.'),
        dict(id='proposal',label='정부 제출안',note='각 연도 정부안입니다. 국회 심의로 달라질 수 있으며 확정 예산이 아닙니다.')]
    if actual_totals:bases.append(dict(id='actual',label='결산 · 공개 분야통계',note='공개된 16대 분야 결산만 표시합니다. 총괄 결산의 최신 연도와 다를 수 있습니다.'))
    plans=[load(p) for p in sorted((ROOT/'manual/national-budget').glob('kr_plan_*.json'))]
    plans=[p for p in plans if p['publication_date']<=asof]
    doc=dict(id='kr',name='한국',scope='중앙정부 · 예산과 기금 · 총지출 기준',unit='조원',currency='KRW',
        fiscal_note='1월 1일~12월 31일',default_basis='approved',basis=bases,totals=totals,sectors=list(sectors.values()),
        macro=macro,progress=progress,outlooks=plans,counts=counts,
        sources=[dict(id='budget',label='열린재정 · 세부사업 예산편성현황(총지출)',url=KR_SOURCE),
            dict(id='actual',label='열린재정 · 16대 분야별 재원배분',url=actual_source),
            dict(id='macro',label='열린재정 · 월간 재정동향 재정수지',url=KR_BASE+'/op/ko/sd/UOPKOSDA01?odtId=45DHAZ24H7WWJ0VG03Q666V46')],
        notes=['16대 공식 분야를 사용합니다. 중복을 포함하는 12대 정책분야와 R&D 홍보 집계를 총지출에 더하지 않습니다.',
            '외교·통일/통일·외교 분야 명칭을 통일·외교로 연결합니다. 세부사업 명칭·부처의 조직개편으로 시계열이 끊길 수 있으며 처음 관측된 사업이 반드시 신규 정책인 것은 아닙니다.',
            '국회 확정 본예산·정부안·결산의 동일 기준끼리 증감률을 계산합니다. 총괄 실적은 12월 누적이며 당해 연도 누적은 별도 표시합니다.',
            '중기계획은 수동 검토한 공식 발표본이며 발표 이후 수정은 새 빈티지로 추가합니다. 세부사업별 미래 금액은 공개된 연도까지만 표시합니다.'])
    accounts=dict(id='kr_accounts',source_url=KR_SOURCE,unit='조원',programs=list(programs.values()))
    return doc,accounts

def collect_us(client):
    files=omb_files(client);fy=files['budauth']['fy'];last_actual=fy-2
    totals={};sectors={};accounts=[]
    for metric,key in [('ba','budauth'),('outlays','outlays')]:
        spec=files[key];rows,years=parse_omb(client.get(f'omb-{key}-{fy}.xlsx',spec['url'],refresh=True),metric)
        total,by_sector=aggregate_accounts(rows);totals[metric]=total
        for code,vals in by_sector.items():
            sector=sectors.setdefault(code,dict(id=code,name=FUNCTIONS[code][0],english=FUNCTIONS[code][1],values={}))
            sector['values'][metric]=vals
        for r in rows:r['basis']=metric
        accounts.extend(rows)
        print('US OMB',metric,len(rows),'accounts',min(years),max(years),flush=True)
    # Treasury's completed-year actuals replace OMB's old current-year estimate.
    fiscal_year=int(today()[:4])+(int(today()[5:7])>=10);latest_completed=fiscal_year-1
    macro={'spending':{},'revenue':{},'balance':{}}
    for year in range(last_actual+1,latest_completed+1):
        rows=treasury_rows(client,year)
        t,fields=parse_mts(rows)
        for m,v in t.items():macro[m][str(year)]=round(v,6)
        totals['outlays'][str(year)]=round(t['spending'],6)
        # An absent Treasury function is unavailable, not a zero-filled estimate.
        for code,sector in sectors.items():
            sector['values']['outlays'].pop(str(year),None)
            if code in fields:sector['values']['outlays'][str(year)]=round(fields[code],6)
    vintages=cbo_vintages(client)
    # Historical cash macro data from the CBO's separate actual-history series.
    catalog=client.json('cbo-catalog.json',CBO_BASE+'catalog.json')
    dataset=next(d for d in catalog['datasets'] if d['identifier']=='historical_budget')
    distribution=max(dataset['distribution'],key=lambda d:d['vintage'])
    import csv,io
    historical=list(csv.DictReader(io.StringIO(client.get('cbo-historical.csv',CBO_BASE+distribution['downloadURL'],refresh=True).decode('utf-8-sig'))))
    # The schema explicitly identifies the headline field names.
    schema=client.json('cbo-historical-schema.json',CBO_BASE+dataset['schema_path'])
    for metric,field in [('spending','outlays_total'),('revenue','rev_total'),('balance','deficit_total')]:
        if field not in schema['fields']:continue
        for row in historical:
            if row['variable']==field and row['date'].startswith('FY') and 2014<=int(row['date'][2:])<=last_actual:
                macro[metric][row['date'][2:]]=number(row['value'])
    doc=dict(id='us',name='미국',scope='연방정부 · 주·지방정부의 자체 지출 제외',unit='USD 십억',currency='USD',
        fiscal_note='FY는 전년 10월 1일~해당 연도 9월 30일',default_basis='outlays',
        basis=[dict(id='outlays',label='지출 · Outlays',note='OMB 과거 실적·정부 추계와 재무부 최근 결산. 실제 지급된 지출입니다.'),
            dict(id='ba',label='예산권한 · Budget Authority',note='지출 의무를 부담할 수 있는 권한입니다. 실제 지급액·계약액과 다르며 정부 요청·추계는 확정 의회 예산이 아닙니다.')],
        totals=totals,sectors=list(sectors.values()),macro=macro,outlooks=vintages,
        actual_through={'outlays':latest_completed,'ba':last_actual},account_actual_through=last_actual,omb_edition=fy,
        sources=[dict(id='omb',label=f'OMB FY{fy} Public Budget Database',url=OMB_BASE+'supplemental-materials/'),
            dict(id='treasury',label='미 재무부 Monthly Treasury Statement',url='https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/'),
            dict(id='cbo',label='CBO 기준선 전망 · 발표본별',url='https://www.cbo.gov/data/budget-economic-data')],
        notes=['Budget Authority·Obligations·Outlays는 다른 지표입니다. 정부 예산안과 CBO 현행법 기준선 전망을 합치지 않습니다.',
            f'OMB FY{fy}의 {last_actual+1}년 이후는 해당 발표 당시 추계입니다. 최근 완료 연도 총괄·분야별 지출은 재무부 결산으로 갱신합니다. 계정별 상세는 OMB 발표 기준을 유지합니다.',
            '상계수입·상환 등 음수 금액도 포함하므로 분야별 비중이 음수가 될 수 있습니다. 양수만 더하면 순지출 총계와 달라집니다.',
            'OMB는 과거 기관·계정 분류를 현재 예산체계에 맞춰 재작성합니다. CBO 전망은 발표 빈티지를 선택해 당시 전망을 비교합니다.'])
    return doc,dict(id='us_accounts',unit='USD 십억',source_url=OMB_BASE+'supplemental-materials/',programs=accounts,actual_through=last_actual)

def treasury_rows(client,year):
    url='https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_9'
    params={'filter':f'record_date:eq:{year}-09-30','page[number]':1,'page[size]':1000}
    try:
        response=client.json(f'mts9-{year}.json',url,params=params,refresh=True)
    except requests.RequestException:
        # FiscalData occasionally returns a gateway error for an exact date
        # query. Its documented inclusive range selects the same one day.
        params['filter']=f'record_date:gte:{year}-09-30,record_date:lte:{year}-09-30'
        response=client.json(f'mts9-{year}.json',url,params=params,refresh=True)
    rows=response['data']
    if not rows or any(r['record_date']!=f'{year}-09-30' for r in rows):raise ValueError('Treasury fiscal date mismatch')
    return rows


def validate(doc,accounts):
    if not doc['sectors'] or not doc['outlooks']:raise ValueError('Incomplete budget dashboard')
    for basis,values in doc['totals'].items():
        if not values or min(map(int,values))>2014:raise ValueError('Missing annual budget history')
        for year,total in values.items():
            subtotal=sum(s['values'].get(basis,{}).get(year,0) for s in doc['sectors'])
            if abs(subtotal-total)>.001:raise ValueError('Budget sector total does not reconcile')
    if doc['id']=='kr':
        if len(doc['sectors'])!=16:raise ValueError('Korean function classification changed')
        if max(map(int,doc['totals']['actual']))>=int(today()[:4]):raise ValueError('Incomplete Korean year marked actual')
    else:
        if len(doc['sectors'])!=20:raise ValueError('US function classification changed')
    for metric in ['spending','revenue','balance']:
        if not doc['macro'].get(metric):raise ValueError('Missing historical fiscal headline')
    # Detail accounts must reconcile with the same source and basis. Treasury
    # cash actuals supersede OMB at function level only, never inside accounts.
    for basis in doc['totals']:
        rows=[dict(r,values=r['values'][basis]) for r in accounts['programs']] if doc['id']=='kr' and basis!='actual' else [r for r in accounts['programs'] if r.get('basis')==basis]
        if not rows:continue
        totals,_=aggregate_accounts(rows)
        for year,total in totals.items():
            if doc['id']=='us' and basis=='outlays' and int(year)>doc['account_actual_through'] and int(year)<=doc['actual_through']['outlays']:continue
            if abs(total-doc['totals'][basis][year])>.001:raise ValueError('Budget account totals do not reconcile')


def run(offline=False,refresh=False):
    client=Client(offline,refresh);index=[]
    for country,collector in [('kr',collect_kr),('us',collect_us)]:
        try:
            doc,accounts=collector(client)
            validate(doc,accounts)
            old=load(OUT/(country+'.json'))
            doc.update(fetched=old['fetched'] if offline and old else today(),checked=old['checked'] if offline and old else today(),ok=True,metric_labels=LABELS)
            if offline and old:
                doc['ok']=old['ok']
                if 'error' in old:doc['error']=old['error']
            if old:
                for basis,vals in old['totals'].items():
                    if basis in doc['totals'] and set(vals)-set(doc['totals'][basis]):raise ValueError('Budget history regressed')
            # Detail downloads are limited to the chosen sector, not every
            # country's 5–12 MB account history on first entry.
            grouped=defaultdict(list)
            for row in accounts['programs']:grouped[row['sector']].append(row)
            doc['account_files']={}
            for sector,rows in grouped.items():
                filename=country+'-accounts/'+hashlib.sha256(sector.encode()).hexdigest()[:16]+'.json'
                doc['account_files'][sector]=filename
                save(OUT/filename,dict(id=sector,unit=doc['unit'],source_url=accounts['source_url'],programs=rows))
            save(OUT/(country+'.json'),doc)
        except Exception as error:
            doc=load(OUT/(country+'.json'))
            if doc is None:raise
            doc.update(checked=today(),ok=False,error=str(error));save(OUT/(country+'.json'),doc)
            print(country,'retained last successful history:',str(error),flush=True)
        index.append(dict(id=country,name=doc['name'],fetched=doc['fetched'],checked=doc['checked'],ok=doc['ok']))
    previous=load(OUT/'index.json',{})
    stamp=previous.get('updated',today()) if offline else dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'index.json',dict(id='national_budget_index',countries=index,checked=today(),updated=stamp))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');p.add_argument('--refresh',action='store_true');a=p.parse_args();run(a.offline,a.refresh)

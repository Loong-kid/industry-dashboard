"""OpenDART income quarters and cash PP&E, preserving CFS/OFS and source vintage."""
import copy
import re
from shipbuilding_equipment_sources import number,end

METRICS=('revenue','profit','capex')
# Pre-IPO CMTX H1 contains a six-month income column only. The API repeats it
# in both amount/add_amount; 2026 H1 explicitly discloses the actual 2025 Q2.
CUMULATIVE_ONLY_RECEIPTS={'20250822000416'}
TAGS={
 'revenue':('ifrs-full_Revenue','ifrs_Revenue','ifrs-full_RevenueFromContractsWithCustomers'),
 'profit':('dart_OperatingIncomeLoss','ifrs-full_ProfitLossFromOperatingActivities','ifrs_ProfitLossFromOperatingActivities'),
 'capex':('ifrs-full_PurchaseOfPropertyPlantAndEquipment','ifrs_PurchaseOfPropertyPlantAndEquipment','ifrs-full_PaymentsToAcquirePropertyPlantAndEquipment','dart_PurchaseOfPropertyPlantAndEquipment','ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities','ifrs_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'),
}
NAMES={
 'revenue':('매출액','영업수익','수익(매출액)','매출'),
 'profit':('영업이익','영업이익(손실)','영업손실','영업손익'),
 'capex':('유형자산의취득','유형자산취득','유형자산의취득으로인한현금유출','유형자산취득으로인한현금유출'),
}


def compact(value):return re.sub(r'\s+','',value or '')

PPE_COMPONENTS=('Land','Buildings','Structure','Machinery','Vehicles','FixturesAndFittings','OfficeEquipment','ConstructionInProgress','OtherPropertyPlantAndEquipment','Facilities')
PPE_NAMES=('토지의취득','건물의취득','구축물의취득','기계장치의취득','차량운반구의취득','공구와기구의취득','공구와비품의취득','비품의취득','건설중인자산의취득','기타유형자산의취득','시설장치의취득')


def source_amount(item,metric,q,lag):
    if lag==0:return 'thstrm_amount'
    if lag==2:return 'bfefrmtrm_amount'
    if q==4:return 'frmtrm_amount'
    if metric=='capex' and number(item.get('frmtrm_q_amount')) is None:return 'frmtrm_amount'
    return 'frmtrm_q_amount'


def cash_components(items,q):
    parts=[r for r in items if r.get('sj_div')=='CF' and (r.get('account_id') in ['dart_PurchaseOf'+s for s in PPE_COMPONENTS] or compact(r.get('account_nm')) in PPE_NAMES)]
    if not parts:return None
    if len({compact(r.get('account_nm')) for r in parts})!=len(parts):raise ValueError('duplicate PP&E cash component')
    synthetic=dict(parts[0],account_id='calculated_PPE_cash_components',account_nm='공시 유형자산 취득 현금지출 세부항목 합계',inputs=parts)
    for lag in ([0,1,2] if q==4 else [0,1]):
        field='thstrm_amount' if lag==0 else 'bfefrmtrm_amount' if lag==2 else 'frmtrm_amount' if q==4 else 'frmtrm_q_amount'
        values=[number(p.get(source_amount(p,'capex',q,lag))) for p in parts]
        # Empty individual cells in an expressly itemized cash-flow block are
        # dashes/no transaction, not a missing company-level CAPEX observation.
        synthetic[field]=str(sum(v for v in values if v is not None)) if any(v is not None for v in values) else ''
    return synthetic


def choose(items,metric):
    candidates=[]
    for item in items:
        if item.get('sj_div') not in (('CF',) if metric=='capex' else ('IS','CIS')):continue
        name=re.sub(r'^(?:(?:[IVX]+|[Ⅰ-Ⅹ]+|\d+)[.．]|\(\d+\))','',compact(item.get('account_nm')))
        if item.get('account_id') in TAGS[metric] or name in NAMES[metric]:
            candidates.append((0 if item.get('account_id') in TAGS[metric] else 1,0 if item.get('sj_div')=='IS' else 1,item))
    if not candidates:return None
    best=min(candidates,key=lambda c:c[:2]);peers=[c[2] for c in candidates if c[:2]==best[:2]]
    if len({tuple(p.get(k) for k in ['thstrm_amount','thstrm_add_amount','frmtrm_amount']) for p in peers})>1:raise ValueError('ambiguous total statement row')
    return best[2]


def parse_report(items,year,q,corp,fs):
    fields={};comparatives={1:{},2:{}}
    for item in items:
        if item.get('corp_code',corp)!=corp or item.get('fs_div',fs)!=fs:raise ValueError('issuer or CFS/OFS mismatch')
        if item.get('currency','KRW')!='KRW':raise ValueError('unexpected reporting currency')
    for metric in METRICS:
        item=choose(items,metric)
        if item is None and metric=='capex':item=cash_components(items,q)
        if item is None:continue
        receipt=item['rcept_no'];filed=f'{receipt[:4]}-{receipt[4:6]}-{receipt[6:8]}'
        def fact(lag):
            direct_field=source_amount(item,metric,q,lag)
            ytd_field=direct_field if q in (1,4) or metric=='capex' else 'thstrm_add_amount' if lag==0 else 'frmtrm_add_amount'
            if lag==2:direct_field=ytd_field='bfefrmtrm_amount'
            value=number(item.get(direct_field));ytd=number(item.get(ytd_field))
            if value is None and ytd is None:return None
            if metric=='capex':
                value=None
                if ytd is not None and not item.get('inputs'):ytd=abs(ytd)
            elif q in (2,3) and receipt in CUMULATIVE_ONLY_RECEIPTS:value=None
            # A reported operating-loss row may be a positive loss magnitude.
            if metric=='profit' and compact(item.get('account_nm'))=='영업손실':
                value=-abs(value) if value is not None else None;ytd=-abs(ytd) if ytd is not None else None
            y=year-lag
            return dict(value=value/1e6 if value is not None else None,ytd=ytd/1e6 if ytd is not None else None,
                url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+receipt,filed=filed,
                tag=item['account_id'],account_name=item.get('account_nm'),fs_div=fs,statement=item['sj_div'],
                source_field=direct_field,ytd_source_field=ytd_field,start=f'{y}-01-01',end=end(y,q),
                comparative=lag>0,basis='ppe_cash' if metric=='capex' else 'reported_income',
                inputs=[dict(account_id=p['account_id'],account_name=p['account_nm'],value=number(p.get(source_amount(p,metric,q,lag)))) for p in item.get('inputs',[])])
        current=fact(0)
        if current:fields[metric]=current
        for lag in ([1,2] if q==4 else [1]):
            if year-lag<2014:continue
            f=fact(lag)
            if f:comparatives[lag][metric]=f
    if not all(m in fields for m in ('revenue','profit')):raise ValueError('missing total income statement')
    return dict(year=year,quarter=q,fs_div=fs,fields=fields,
        comparatives=[dict(year=year-lag,quarter=q,fs_div=fs,fields=f,comparative=True) for lag,f in comparatives.items() if f])


def accounts(reports,asof):
    index={(r['year'],r['quarter']):copy.deepcopy(r) for r in reports}
    candidates={}
    for report in reports:
        for r in [report]+report.get('comparatives',[]):
            for m,f in r['fields'].items():candidates.setdefault((r['year'],r['quarter'],m),[]).append(f)
    # Comparison columns fill only unreported historical metrics. Current-period
    # filings keep precedence, avoiding arbitrary switches in discontinued scope.
    for r in sorted(reports,key=lambda r:(r['year'],r['quarter'])):
        for prior in r.get('comparatives',[]):
            target=index.setdefault((prior['year'],prior['quarter']),copy.deepcopy(prior))
            if target['fs_div']!=prior['fs_div']:continue
            for m,f in prior['fields'].items():target['fields'].setdefault(m,copy.deepcopy(f))
    quarters=[];annual=[]
    for (year,q),r in sorted(index.items()):
        if end(year,q)>asof:continue
        fields={m:f for m,f in r['fields'].items() if f['filed']<=asof}
        if q==4:
            a=dict(date=end(year,4),year=year,refs={},fs_div=r['fs_div'])
            for m,f in fields.items():
                if f.get('ytd') is not None:a[m]=f['ytd'];a['refs'][m]=dict(f,components=[f],calculation='reported annual')
            if a['refs']:annual.append(a)
        row=dict(date=end(year,q),year=year,quarter=q,fs_div=r['fs_div'],refs={})
        previous=index.get((year,q-1),{})
        for m,f in fields.items():
            if m!='capex' and q<4 and f.get('value') is None:
                direct=[a for a in candidates.get((year,q,m),[]) if a.get('value') is not None and a['fs_div']==r['fs_div'] and a['filed']<=asof]
                if direct:f=max(direct,key=lambda a:a['filed'])
            if m!='capex' and q<4 and f.get('value') is not None:
                row[m]=f['value'];ref=dict(f,start=f'{year}-{q*3-2:02d}-01')
                row['refs'][m]=dict(ref,components=[ref],calculation='reported three-month income')
            elif q==1 and f.get('ytd') is not None:
                row[m]=f['ytd'];row['refs'][m]=dict(f,components=[f],calculation='reported first-quarter cash flow')
            elif q>1 and previous.get('fs_div')==r['fs_div']:
                p=previous['fields'].get(m,{})
                def compatible(a,b):return a.get('ytd') is not None and b.get('ytd') is not None and a['filed']<=asof and b['filed']<=a['filed'] and a['comparative']==b['comparative'] and a['basis']==b['basis'] and a['fs_div']==b['fs_div']==r['fs_div']
                if not compatible(f,p):
                    pairs=[(a,b) for a in candidates.get((year,q,m),[]) for b in candidates.get((year,q-1,m),[]) if compatible(a,b)]
                    if not pairs:continue
                    f,p=max(pairs,key=lambda pair:(pair[0]['filed'],pair[1]['filed']))
                value=f['ytd']-p['ytd']
                if m!='profit' and value<0:continue
                row[m]=value;row['refs'][m]=dict(f,components=[f,p],calculation='same fiscal-year and CFS/OFS YTD minus prior YTD')
        if row['refs']:quarters.append(row)
    # Recover Q1 income from a single H1 filing if the standalone Q1 is absent.
    for (year,q),r in index.items():
        if q!=2 or end(year,q)>asof:continue
        row=next((p for p in quarters if p['year']==year and p['quarter']==1),None)
        if row and row['fs_div']!=r['fs_div']:continue
        first=row or dict(date=end(year,1),year=year,quarter=1,fs_div=r['fs_div'],refs={})
        for m,f in r['fields'].items():
            if m=='capex' or m in first or f['filed']>asof or f.get('ytd') is None or f.get('value') is None:continue
            value=f['ytd']-f['value']
            if m=='revenue' and value<0:continue
            first[m]=value;first['refs'][m]=dict(f,components=[dict(f,source_field=f['ytd_source_field']),dict(f,start=f'{year}-04-01')],calculation='same H1 reported YTD minus reported Q2')
        if not row and first['refs']:quarters.append(first)
    return dict(rows=sorted(quarters,key=lambda r:r['date']),annual=sorted(annual,key=lambda r:r['date']))

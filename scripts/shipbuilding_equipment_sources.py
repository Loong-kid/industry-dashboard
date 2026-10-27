"""Native KRW income statements; preserve entity, reporting basis and periods."""
import datetime as dt
import math
import re

from bs4 import BeautifulSoup
from quantum_sources import period, METRICS


TAGS = {
    'revenue': ('ifrs-full_Revenue', 'ifrs-full_RevenueFromContractsWithCustomers', 'ifrs_Revenue'),
    'profit': ('dart_OperatingIncomeLoss', 'ifrs-full_ProfitLossFromOperatingActivities', 'ifrs_ProfitLossFromOperatingActivities'),
    'netincome': ('ifrs-full_ProfitLoss', 'ifrs_ProfitLoss'),
}


def number(value):
    s=str(value or '').replace(',', '').replace(' ', '').replace('−', '-')
    if s.startswith('(') and s.endswith(')'):s='-'+s[1:-1]
    try:
        n=float(s)
        return n if math.isfinite(n) else None
    except ValueError:return None


def end(year, q):
    return f'{year}-{q*3:02d}-{30 if q in (2,3) else 31}'


def report(items, year, q, corp, fs):
    fields={};comparative_fields={1:{},2:{}}
    for metric,tags in TAGS.items():
        matches=[]
        for item in items:
            if item.get('corp_code',corp)!=corp or item.get('fs_div',fs)!=fs:
                raise ValueError('issuer/reporting basis mismatch')
            if (item.get('currency') or 'KRW')!='KRW':raise ValueError('unexpected source currency')
            if item.get('sj_div') not in ('IS','CIS'):continue
            name=re.sub(r'^(?:[IVX]+|[Ⅰ-Ⅹ]+|\d+)[.．]','',item.get('account_nm','').replace(' ',''))
            # Exclude parent attribution, comprehensive income, EPS and tax.
            named=(name in ('매출액','영업수익','수익(매출액)','매출') if metric=='revenue' else
                   name in ('영업이익','영업이익(손실)','영업손실','영업손익') if metric=='profit' else
                   bool(re.fullmatch(r'(?:연결)?(?:당기|분기|반기)순(?:이익|손실|손익)(?:\(손실\)|\(이익\))?',name)))
            if item.get('account_id') in tags or named:
                matches.append((0 if item.get('account_id') in tags else 1, 0 if item['sj_div']=='IS' else 1,item))
        if not matches:raise ValueError('missing total income statement metric: '+metric)
        item=min(matches,key=lambda t:t[:2])[2]
        value=number(item.get('thstrm_amount'))
        ytd=value if q in (1,4) else number(item.get('thstrm_add_amount'))
        if value is None and ytd is None:raise ValueError('missing numeric financial amount')
        receipt=item['rcept_no']
        fields[metric]=dict(value=value/1e6 if value is not None else None,ytd=ytd/1e6 if ytd is not None else None,
            url=f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}',filed=f'{receipt[:4]}-{receipt[4:6]}-{receipt[6:8]}',
            tag=item['account_id'],account_name=item.get('account_nm'),fs_div=fs,location='연결 손익계산서' if fs=='CFS' else '별도 손익계산서',
            start=f'{year}-01-01',end=end(year,q))
        for lag in ([1,2] if q==4 else [1]):
            val=number(item.get('frmtrm_amount' if lag==1 and q==4 else 'bfefrmtrm_amount' if lag==2 else 'frmtrm_q_amount'))
            cumulative=val if q in (1,4) else number(item.get('frmtrm_add_amount'))
            if val is not None or cumulative is not None:
                comparative_fields[lag][metric]=dict(fields[metric],value=val/1e6 if val is not None else None,
                    ytd=cumulative/1e6 if cumulative is not None else None,start=f'{year-lag}-01-01',end=end(year-lag,q),comparative=True)
    comparatives=[dict(year=year-lag,quarter=q,fs_div=fs,fields=f) for lag,f in comparative_fields.items() if set(f)==set(TAGS) and year-lag>=2014]
    return dict(year=year,quarter=q,fs_div=fs,fields=fields,comparatives=comparatives)


def accounts(reports, asof):
    index={(r['year'],r['quarter']):r for r in reports};rows=[]
    for (year,q),r in sorted(index.items()):
        if end(year,q)>asof:continue
        if q==4:
            a=period(f'{year}-01-01',end(year,4),'KRW');a['fs_div']=r['fs_div']
            for metric,f in r['fields'].items():
                if f['filed']<=asof and f.get('ytd') is not None:
                    a[metric]=f['ytd'];a['refs'][metric]=dict(f,calculation='reported annual')
            if a['refs']:rows.append(a)
        row=period(f'{year}-{q*3-2:02d}-01',end(year,q),'KRW');row['fs_div']=r['fs_div']
        prior=index.get((year,q-1))
        for metric,f in r['fields'].items():
            if f['filed']>asof:continue
            if q<4 and f.get('value') is not None:
                row[metric]=f['value'];row['refs'][metric]=dict(f,start=row['start'],calculation='reported quarter')
            elif q>1 and prior and prior['fs_div']==r['fs_div']:
                p=prior['fields'].get(metric,{})
                if p.get('ytd') is None or f.get('ytd') is None or p['filed']>f['filed']:continue
                if bool(f.get('comparative'))!=bool(p.get('comparative')):continue
                value=f['ytd']-p['ytd']
                if metric=='revenue' and value<0:continue
                row[metric]=value;row['refs'][metric]=dict(f,calculation='same fiscal-year YTD minus prior YTD',components=[f,p])
        if row['refs']:rows.append(row)
    # A missing Q1 can be recovered from the same half-year statement's H1
    # cumulative and actual Q2. Do not overwrite an existing reporting basis.
    for (year,q),r in index.items():
        if q!=2 or end(year,q)>asof:continue
        existing=next((x for x in rows if x['kind']=='quarter' and x['year']==year and x['quarter']==1),None)
        if existing and existing['fs_div']!=r['fs_div']:continue
        first=existing or dict(period(f'{year}-01-01',f'{year}-03-31','KRW'),fs_div=r['fs_div'])
        for metric,f in r['fields'].items():
            if metric in first or f['filed']>asof or f.get('ytd') is None or f.get('value') is None:continue
            value=f['ytd']-f['value']
            if metric=='revenue' and value<0:continue
            first[metric]=value
            first['refs'][metric]=dict(f,calculation='same fiscal-year H1 minus Q2',
                components=[dict(f,source_field='thstrm_add_amount'),dict(f,start=f'{year}-04-01',source_field='thstrm_amount')])
        if not existing and first['refs']:rows.append(first)
    return sorted(rows,key=lambda r:(r['date'],r['kind']))


def provisional(raw, receipt, fs, asof):
    """Only actual single-quarter results, never cumulative/guidance/parent net."""
    soup=BeautifulSoup(raw,'html.parser');text=soup.get_text(' ',strip=True)
    actual_fs='CFS' if '1. 연결실적내용' in text or '연결재무제표 기준' in text else 'OFS'
    if actual_fs!=fs:raise ValueError('provisional reporting basis mismatch')
    scale=100 if re.search(r'단위\s*:\s*억원',text) else 1 if re.search(r'단위\s*:\s*백만원',text) else None
    if scale is None:raise ValueError('unreviewed provisional unit')
    dates=None
    for tr in soup.select('tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.find_all('td',recursive=False)]
        if cells and cells[0]=='당기실적':
            found=re.findall(r'20\d{2}-\d{2}-\d{2}',' '.join(cells[1:]))
            if len(found)==2:dates=found;break
    if not dates:raise ValueError('provisional reporting interval missing')
    row=period(*dates,'KRW')
    if row['kind']!='quarter' or row['date']>asof:raise ValueError('not a completed single quarter')
    row.update(fs_div=fs,provisional=True,period=row['period']+' · 잠정')
    labels={'매출액':'revenue','영업이익':'profit','당기순이익':'netincome'}
    for tr in soup.select('tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.find_all('td',recursive=False)]
        if len(cells)<3 or cells[0] not in labels or cells[1]!='당해실적':continue
        metric=labels[cells[0]];value=number(cells[2])
        if value is None:continue
        row[metric]=value*scale
        row['refs'][metric]=dict(url=f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}',filed=f'{receipt[:4]}-{receipt[4:6]}-{receipt[6:8]}',
            start=row['start'],end=row['date'],tag=cells[0],fs_div=fs,location='연결 잠정실적' if fs=='CFS' else '별도 잠정실적',calculation='reported provisional quarter')
    if set(row['refs'])!=set(METRICS):raise ValueError('incomplete provisional income statement')
    return row

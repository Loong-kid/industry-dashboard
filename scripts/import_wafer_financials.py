"""Import original wafer-company financial statements; never split annuals by four.

Inputs are reviewed PDF downloads and registries, not provider price estimates.
Quarterly cash flows are cumulative differences only when the prior YTD exists.
"""
import argparse
import calendar
import hashlib
import json
import re
from contextlib import contextmanager
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]


class TextPage:
    def __init__(self,text):self.text=text
    def get_text(self,**kwargs):return self.text


@contextmanager
def reviewed_pdf(folder,meta):
    path=folder/meta['name']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Source hash mismatch')
    cache=path.with_suffix('.txt')
    if cache.exists():
        yield [TextPage(t) for t in re.split(r'\n=== PAGE \d+ ===\n',cache.read_text(encoding='utf-8'))[1:]]
    else:
        with pymupdf.open(path) as pdf:yield pdf


def clean(text):
    return text.replace('\u2009','').replace('\u202f','').replace('\u00a0',' ').replace('−','-').replace('–','-').replace('△','-')


def decimal_numbers(text):
    values=re.findall(r'\(?-?\s*\d[\d,]*\.\d+\)?',clean(text))
    return [float(v.replace(',','').replace(' ','').replace('(','-').replace(')','')) for v in values]


def integer_numbers(text):
    # Large NT$/JPY-thousand financial values; excludes note IDs and percentages.
    values=re.findall(r'\(?-?\d{1,3}(?:,\d{3})+\)?',clean(text))
    return [int(v.replace(',','').replace('(','-').replace(')','')) for v in values]


def end(year,quarter=4):
    m=quarter*3
    return f'{year}-{m:02}-{calendar.monthrange(year,m)[1]}'


def registry(folder):
    records={}
    for filename in ['downloads.json','archive-downloads.json','more-downloads.json','sumco-final-downloads.json','sumco-statement-sources.json']:
        path=folder/filename
        if not path.exists():continue
        for row in json.loads(path.read_text(encoding='utf-8')):
            if row.get('ok') and row['name'].endswith('.pdf'):records[row['name']]=row
    return records


def source(meta,page,label,calculation='reported'):
    return dict(url=meta['url'],pdf_page=page,label=label,pdf_sha256=meta['sha256'],calculation=calculation)


def row(year,quarter=None):
    return dict(date=end(year,quarter or 4),year=year,**({'quarter':quarter} if quarter else {}),
                period=f'{year} Q{quarter}' if quarter else str(year),refs={})


def siltronic(folder,records):
    annuals={};quarters={}
    reports=[m for n,m in records.items() if n.startswith('sil-') and ('annual_report' in n.lower())]
    for meta in sorted(reports,key=lambda r:r['name']):
        with reviewed_pdf(folder,meta) as pdf:
            text=clean(pdf[1].get_text(sort=True))
            years=[int(y) for y in re.findall(r'\b20\d{2}\b',text.split('Statement of profit')[0])]
            if not years:
                years=[int(y) for y in re.findall(r'\b20\d{2}\b',text)][:5]
            years=list(dict.fromkeys(years))
            if not years:continue
            year=years[0]
            if year<2015:continue
            for i,y in enumerate(years):
                if y<2014 or (y!=year and y!=2014):continue
                r=annuals.setdefault(y,row(y))
                for metric,pattern in [('revenue',r'^Sales\s+([^\n]+)'),('profit',r'^EBIT\s+([^\n]+)'),('ebitda',r'^EBITDA\s+([^\n]+)'),('capex',r'Capital expenditure in property, plant[^\n]*(?:\n[^\n]*)?')]:
                    match=re.search(pattern,text,re.M)
                    if not match:continue
                    values=decimal_numbers(match[1] if match.lastindex else match[0])
                    if len(values)>i:
                        r[metric]=abs(values[i]) if metric=='capex' else values[i]
                        r['refs'][metric]=source(meta,2,r['period'])
            # Cash paid differs from accrued capital expenditure. Keep separate.
            for p,page in enumerate(pdf):
                t=clean(page.get_text(sort=True))
                match=re.search(r'^(?:Payments for capital expenditures|Payments for investments|Payments for property|Cash payments for capital)[^\n]*',t,re.M|re.I)
                if match:
                    values=decimal_numbers(match[0])
                    if len(values)>=2:
                        for i,y in enumerate([year,year-1]):
                            if y in annuals:
                                annuals[y]['cash_capex']=abs(values[i]);annuals[y]['refs']['cash_capex']=source(meta,p+1,str(y))
                        break
            for p,page in enumerate(pdf):
                t=clean(page.get_text(sort=True))
                if not (('Quarterly overview' in t or 'Quarterly development' in t) and re.search(r'^Sales\s',t,re.M)):continue
                headers=re.findall(r'Q([1-4])\s*(20\d{2})',t)
                if len(headers)<4:continue
                fields={}
                for metric,pattern in [('revenue',r'^Sales[^\n]*'),('profit',r'^EBIT\s[^\n]*'),('ebitda',r'^EBITDA\s[^\n]*'),('capex',r'Capital expenditure (?:including|on property|in property)[\s\S]*?(?=Net cash flow|Free cash flow)')]:
                    match=re.search(pattern,t,re.M)
                    if match:
                        values=decimal_numbers(match[0]);fields[metric]=values[:4]
                for i,(q,y) in enumerate(headers[:4]):
                    y,q=int(y),int(q);r=quarters.setdefault((y,q),row(y,q))
                    for metric,values in fields.items():
                        if len(values)==4:
                            r[metric]=abs(values[i]) if metric=='capex' else values[i];r['refs'][metric]=source(meta,p+1,r['period'])
    meta=records['sil-20260730_Siltronic_Half_Year_Financial_Report_2026.pdf']
    with reviewed_pdf(folder,meta) as pdf:
        t=clean(pdf[1].get_text(sort=True))
        for metric,pattern in [('revenue',r'^Sales[^\n]*'),('profit',r'^EBIT\s[^\n]*'),('ebitda',r'^EBITDA\s[^\n]*'),('capex',r'^intangible assets[^\n]*')]:
            values=decimal_numbers(re.search(pattern,t,re.M)[0])
            for i,q in enumerate([2,1]):
                r=quarters.setdefault((2026,q),row(2026,q));r[metric]=values[i];r['refs'][metric]=source(meta,2,r['period'])
    # The FY2017 quarterly-overview CAPEX cells sum to167.9 versus123.2
    # in its annual key figures. Preserve the annual disclosure; do not
    # repair an unexplained quarterly discrepancy by changing a quarter.
    for (year,q),r in quarters.items():
        if year==2017:r.pop('capex',None);r['refs'].pop('capex',None)
    return dict(name='Siltronic',unit='백만 EUR',annuals=sorted(annuals.values(),key=lambda r:r['date']),quarters=sorted(quarters.values(),key=lambda r:r['date']),
                scope='회사 전체 연결. CAPEX는 유형·무형자산 투자액(발생 기준)이며 현금 지급액과 다릅니다. 별도 확인한 현금 지출은 연간 보기에 구분합니다. 2014년은 상장 전 연결 비교 수치이며 2014년 조정 실적과 구분합니다.')


def gw_monthly(html,asof):
    soup=BeautifulSoup(html,'html.parser');observations={}
    for table in soup.select('table'):
        rows=table.select('tr')
        if not rows:continue
        header=rows[0].get_text(' ',strip=True)
        if not re.search(r'month',header,re.I):continue
        years=[int(y) for y in re.findall(r'20\d{2}',header)]
        if len(years)!=2:continue
        for tr in rows[1:]:
            cells=[td.get_text(' ',strip=True) for td in tr.select('td')]
            if len(cells)<3:continue
            months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
            mon=cells[0][:3].lower()
            if mon not in months:continue
            month=months.index(mon)+1
            for i,year in enumerate(years):
                value=cells[i+1].replace(',','')
                if not value:continue
                # Known website typo: 2019-Nov "4.344"; the following table
                # repeats that same observation correctly as "4,344".
                if re.fullmatch(r'\d\.\d{3}',value):continue
                if not value.isdigit():raise ValueError('Unexpected monthly revenue cell '+value)
                date=f'{year}-{month:02}-{calendar.monthrange(year,month)[1]}'
                if date>asof:continue
                # Prefer current-year column over the comparative copy.
                if i==0 or date not in observations:observations[date]=int(value)
    if len(observations)<100:raise ValueError('GlobalWafers monthly table incomplete')
    return [[d,v] for d,v in sorted(observations.items())]


def globalwafers(folder,records):
    annual_files={
        2017:'gw-GWC-Consolidated-FS_2017-1.pdf',2019:'gw-108_Q4-環球英文合併.pdf',
        2020:'gw-2020-Q4-Financial-Report-Consolidated-English.pdf',
        2021:'gw-GWC-2021-financial-statement_consolidated-EN.pdf',
        2022:'gw-GWC-2022-financial-statement_consolidated.pdf',
        2023:'gw-GlobalWafers-consolidated-financial-statements_FY2023.pdf',
        2024:'gw-FY2024_GlobalWafers-Financial-Statement_consolidated-EN.pdf',
        2025:'gw-FY2025_GlobalWafers-Financial-Statement_consolidated-EN.pdf'}
    quarters={};annuals={};ytd={}
    patterns={'revenue':r'(?:Total operating revenue|Operating revenue \(|Net operating revenues)',
              'profit':r'(?:Net operating income|Income from operations)',
              'capex':r'Acquisition of property, plant and equipment'}

    def read_values(meta):
        found={}
        with reviewed_pdf(folder,meta) as pages:
            for i,page in enumerate(pages[:22]):
                text=page.get_text(sort=True)
                for metric,pattern in patterns.items():
                    if metric in found:continue
                    match=re.search(r'^.*?'+pattern+r'[^\n]*',text,re.M|re.I)
                    if match:
                        values=integer_numbers(match[0])
                        if len(values)>=2:found[metric]=(values,i+1,text)
        return found

    for year,name in sorted(annual_files.items()):
        meta=records[name];found=read_values(meta)
        for metric,(values,page,_) in found.items():
            for i,y in enumerate([year,year-1]):
                r=annuals.setdefault(y,row(y));r[metric]=round((abs(values[i]) if metric=='capex' else values[i])/1000,3)
                r['refs'][metric]=source(meta,page,r['period'])
                if metric=='capex':
                    ytd[(y,4)]=dict(value=r[metric],ref=r['refs'][metric])
        if year==2017:
            # Scanned statement p.8 omits a readable operating-income label.
            # Visually reviewed subtotal: gross profit minus operating expenses.
            for y,value in [(2017,7413.542),(2016,1378.347)]:
                annuals[y]['profit']=value;annuals[y]['refs']['profit']=source(meta,8,str(y),'gross profit minus operating expenses; visually checked scan')

    # Official IR highlights: only revenue/profit are public here for 2014/15.
    url='https://www.sas-globalwafers.com/en/investor/financial-information_en/'
    for year,revenue,profit in [(2014,15922,2336),(2015,15310,2685)]:
        r=annuals.setdefault(year,row(year));r.update(revenue=revenue,profit=profit)
        r['refs'].update({m:dict(url=url,label=str(year),calculation='official annual highlights; NT$ million rounded') for m in ['revenue','profit']})

    for name,meta in sorted(records.items()):
        if not name.startswith('gw-') or name in annual_files.values():continue
        m=re.search(r'(20\d{2})Q([1-3])',name,re.I)
        if not m:
            m=re.search(r'(20\d{2}).*?Q([1-3])',name,re.I)
        if not m:
            special={'gw-GWC-1H22-Financial-Statement.pdf':(2022,2),'gw-GWC-2020Q2-Financial-Statement.pdf':(2020,2),
                     'gw-GWC-20Q3-Financial-Statement.pdf':(2020,3)}
            if name not in special:continue
            year,q=special[name]
        else:year,q=map(int,m.groups())
        found=read_values(meta)
        if 'revenue' not in found or 'profit' not in found:continue
        income=found['revenue'][2]
        month=['March','June','September'][q-1]
        expected=f'{year}/{q*3:02}'
        if expected not in income and not (month in income and str(year) in income):
            # Website's 2017Q3 link actually contains the Q2 document.
            continue
        for metric in ['revenue','profit']:
            values,page,_=found[metric]
            if len(values) not in [2,4]:continue
            for i,y in enumerate([year,year-1]):
                if y<2014:continue
                r=quarters.setdefault((y,q),row(y,q));r[metric]=round(values[i]/1000,3);r['refs'][metric]=source(meta,page,r['period'])
        if 'capex' in found:
            values,page,_=found['capex']
            for i,y in enumerate([year,year-1]):
                ytd[(y,q)]=dict(value=round(abs(values[i])/1000,3),ref=source(meta,page,f'{y} {q*3}M'))
    for (y,q),value in sorted(ytd.items()):
        prior=ytd.get((y,q-1)) if q>1 else dict(value=0)
        if prior is None:continue
        r=quarters.setdefault((y,q),row(y,q));r['capex']=round(value['value']-prior['value'],3)
        r['refs']['capex']=dict(value['ref'],calculation='reported Q1 cash' if q==1 else 'current YTD minus previous YTD',
                               supporting_sources=[value['ref']]+([prior['ref']] if 'ref' in prior else []))
    for y,a in annuals.items():
        qs=[quarters.get((y,q)) for q in [1,2,3]]
        if not all(qs):continue
        r=quarters.setdefault((y,4),row(y,4))
        for metric in ['revenue','profit']:
            if metric not in a or any(metric not in q for q in qs):continue
            r[metric]=round(a[metric]-sum(q[metric] for q in qs),3)
            r['refs'][metric]=dict(a['refs'][metric],calculation='FY minus Q1-Q3',supporting_sources=[a['refs'][metric]]+[q['refs'][metric] for q in qs])
    quarters=[r for r in quarters.values() if any(m in r for m in ['revenue','profit'])]
    return dict(name='GlobalWafers · 글로벌웨이퍼스',unit='백만 TWD',annuals=sorted(annuals.values(),key=lambda r:r['date']),quarters=sorted(quarters,key=lambda r:r['date']),
        scope='GlobalWafers 자체 연결 실적이며 모회사 SAS를 합산하지 않습니다. 2016년 SunEdison Semiconductor 인수 전후 연결 범위가 다릅니다. 현금 CAPEX는 유형자산 취득이며 최근 공시에는 장비 선급금이 합산됩니다. 2014·2015 CAPEX 미확보. 오래된 링크의 실제 문서 기간을 검증하며 빠진 분기는 공백입니다. 2018 영업이익은 IR 요약표의 15,578 대신 원본 연결 재무제표 비교열의 17,578.051백만 TWD를 사용합니다.')


def sumco(folder,records):
    annuals={};quarters={}
    def save(year,metric,value,ref,q=None):
        target=quarters if q else annuals;key=(year,q) if q else year
        r=target.setdefault(key,row(year,q));r[metric]=value;r['refs'][metric]=ref
    # Two older original annual filings read through the public filing-text
    # archive after the PDF host failed. Values are the consolidated tables.
    for years,values,url in [
        ([2014,2015],[(225319,25642,9962),(236826,29447,12656)],'https://financialfilings.com/filings/sumco-corporation/annual-report/2016/7847025/'),
        ([2018,2019],[(325059,85165,50295),(299460,50636,62165)],'https://financialfilings.com/filings/sumco-corporation/annual-report/2020/7691862/')]:
        for y,vals in zip(years,values):
            for metric,value in zip(['revenue','profit','capex'],vals):
                save(y,metric,value,dict(url=url,label=str(y),calculation='consolidated original filing table, JPY million; reviewed cached filing text'))
    for name,years in [('sumco-stat2017.pdf',[2016,2017]),('sumco-stat2021.pdf',[2020,2021]),('sumco-20260209552272.pdf',[2024,2025])]:
        meta=records[name];found={}
        with reviewed_pdf(folder,meta) as pages:
            for p,page in enumerate(pages):
                t=page.get_text(sort=True)
                for metric,pattern in [('revenue',r'^\s*(?:売上高|Net sales)\s+(?=[\d(])[^\n]*'),('profit',r'^\s*(?:営業利益|Operating profit(?: \(loss\))?)\s+(?=[\d(])[^\n]*'),('capex',r'^\s*(?:有形及び無形固定資産の取得による支出|Purchase of property, plant and equipment and)[^\n]*')]:
                    if metric in found:continue
                    m=re.search(pattern,t,re.M|re.I)
                    if not m:continue
                    nums=integer_numbers(m[0])
                    if len(nums)!=2:continue
                    for y,value in zip(years,nums):save(y,metric,abs(value) if metric=='capex' else value,source(meta,p+1,str(y)))
                    found[metric]=True
        if len(found)!=3:raise ValueError(f'{name}: missing annual metrics {found}')
    # FY2023 EDINET original filing text (HTML mirror). First consolidated
    # income/cash-flow tables precede the parent's standalone statements.
    meta=records.get('sumco-stat2023.html')
    if meta is None:
        meta=next(r for r in json.loads((folder/'sumco-statement-sources.json').read_text(encoding='utf-8')) if r['name']=='sumco-stat2023.html')
    soup=BeautifulSoup((folder/meta['name']).read_bytes(),'html.parser');found={}
    for tr in soup.select('tr'):
        cells=[c.get_text(' ',strip=True) for c in tr.select('td')]
        while cells and not cells[0]:cells.pop(0)
        if len(cells)<3:continue
        for metric,label in [('revenue','売上高'),('profit','営業利益'),('capex','有形及び無形固定資産の取得による支出')]:
            if metric in found or cells[0]!=label:continue
            nums=integer_numbers(' '.join(cells[1:]))
            if len(nums)!=2:continue
            for y,value in zip([2022,2023],nums):save(y,metric,abs(value) if metric=='capex' else value,dict(url=meta['url'],label=str(y),calculation='original consolidated EDINET filing text, JPY million'))
            found[metric]=True
    if len(found)!=3:raise ValueError('FY2023 consolidated statement parse incomplete '+str(found))
    # Separate acceptance-basis equipment spending in quarterly IR tables.
    # Only current-year Actual columns are admitted; forecast sections ignored.
    for name,year in [('sumco-2017-pres.pdf',2017),('sumco-2021-pres.pdf',2021),('sumco-2022-pres.pdf',2022),('sumco-fy2023.pdf',2023),('sumco-fy2024.pdf',2024),('sumco-20260209552301.pdf',2025),('sumco-20260805509660.pdf',2026)]:
        meta=records[name]
        with reviewed_pdf(folder,meta) as pages:
            for p,page in enumerate(pages):
                t=page.get_text(sort=True)
                if 'Summary of Consolidated Business Result' not in t or 'Net sales' not in t and 'Net Sales' not in t:continue
                if 'Forecast' in t or 'Forecasts' in t:continue
                fields={}
                for metric,label in [('revenue',r'Net [sS]ales'),('profit',r'Operating (?:profit|income|Income)'),('acceptance_capex',r'Capital [eE]xpenditure \(Acceptance basis\)')]:
                    match=re.search(r'^\s*'+label+r'[^\n]*',t,re.M)
                    if match:fields[metric]=decimal_numbers(match[0])
                n=2 if year==2026 else 4
                if not all(len(v)>=n+2 for v in fields.values()) or len(fields)!=3:continue
                for metric,values in fields.items():
                    for q,value in enumerate(values[1:1+n],1):save(year,metric,round(value*1000,3),source(meta,p+1,f'{year} Q{q}'),q)
                break
    return dict(name='SUMCO',unit='백만 JPY',annuals=sorted(annuals.values(),key=lambda r:r['date']),quarters=sorted(quarters.values(),key=lambda r:r['date']),
                scope='회사 전체 연결. 연간 CAPEX는 유형·무형자산 취득 현금지출입니다. 별도 분기 투자액은 회사 IR의 검수 기준(Acceptance basis)이므로 현금 지출과 혼합하지 않습니다. 미확보 분기는 공백으로 남깁니다.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-dir',required=True,type=Path);p.add_argument('--as-of',required=True)
    args=p.parse_args();records=registry(args.source_dir)
    dest=ROOT/'manual/silicon_wafer.json'
    snapshot=json.loads(dest.read_text(encoding='utf-8')) if dest.exists() else dict(companies={})
    snapshot['reviewed']=args.as_of
    snapshot['companies']['siltronic']=siltronic(args.source_dir,records)
    snapshot['companies']['globalwafers']=globalwafers(args.source_dir,records)
    snapshot['companies']['sumco']=sumco(args.source_dir,records)
    snapshot['gw_monthly']=dict(url='https://www.sas-globalwafers.com/en/investor/financial-information_en/',fetched=args.as_of,
                                points=gw_monthly((args.source_dir/'gw.html').read_text(encoding='utf-8'),args.as_of))
    dest.write_text(json.dumps(snapshot,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    s=snapshot['companies']['siltronic'];print('Siltronic',len(s['annuals']),'annuals',len(s['quarters']),'quarters; GlobalWafers',len(snapshot['gw_monthly']['points']),'months')


if __name__=='__main__':main()

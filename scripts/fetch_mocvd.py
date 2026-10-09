"""MOCVD indicators from official AIXTRON PDFs and Coherent releases.

Reviewed disclosures live in manual/mocvd.json. --backfill fetches the archive;
normal runs fetch the latest year. --offline rebuilds charts without network.
Source failures retain prior observations and fail the scheduled run visibly.
"""
import argparse
import calendar
import datetime as dt
import json
import math
import re
from pathlib import Path
from urllib.parse import urljoin

import pymupdf
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/_mocvd/facts.json'
MANUAL = ROOT / 'manual/mocvd.json'
AIX = 'https://www.aixtron.com/en/investors/publications'
COHR = 'https://ir.coherent.com/financial-information/quarterly-results'
VECO = 'https://s1.q4cdn.com/522285864/files/doc_presentations/2026/May/Investor-Presentation-May-2026-FINAl.pdf'


def get(url):
    r = requests.get(url, timeout=(10, 25))
    r.raise_for_status()
    return r


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')


def end_date(year, quarter):
    month = quarter*3
    return f'{year}-{month:02}-{calendar.monthrange(year,month)[1]}'


def number(s):
    m = re.match(r'\s*([+-]?[\d,]+(?:\.\d+)?)', s or '')
    if not m:
        raise ValueError(f'Missing numeric cell: {s!r}')
    n = float(m[1].replace(',', ''))
    if not math.isfinite(n):
        raise ValueError('Nonfinite observation')
    return n


def extract_aix(data, url, year, quarter):
    """Quarter totals, YTD equipment sales and point-in-time balances, separately."""
    result = dict(date=end_date(year, quarter), year=year, quarter=quarter, url=url,
                  refs={}, fetched=dt.date.today().isoformat())
    with pymupdf.open(stream=data, filetype='pdf') as pdf:
        page = pdf[1]
        text = page.get_text()
        if 'Key Quarterly Financials' not in text or not re.search(r'EUR\s+million', text):
            raise ValueError('AIXTRON financial header/unit changed')
        financial = next((t.extract() for t in page.find_tables().tables
                          if 'Order intake' in str(t.extract()) and 'Gross profit' in str(t.extract())), None)
        if not financial or (quarter != 1 and len(financial[0]) != 7):
            raise ValueError('AIXTRON quarterly column layout changed')
        headers = ' '.join(str(r) for r in financial[:2])
        if not (re.search(fr'(?:Q{quarter}\s+{year}|{year}\s+Q{quarter})', headers)):
            raise ValueError('Quarter identity not confirmed')
        labels = {'order intake':'orders', 'order backlog':'backlog', 'revenue':'revenue',
                  'gross profit':'gross_profit', 'ebit':'ebit', 'free cash flow':'fcf'}
        for row in financial:
            label = (row[0] or '').lower().replace('\n', ' ')
            for match, key in labels.items():
                if match in label:
                    result[key] = number(row[1 if quarter==1 else 4])
                    result[key+'_ytd'] = number(row[1])
                    result['refs'][key] = 2
        if not all(k in result for k in ['orders','backlog','revenue','ebit']):
            raise ValueError('AIXTRON incomplete quarterly financials')
        m = re.search(r'Contract liabilities for advance payments\s+([\d.]+)',text)
        if m:
            result['advances'] = float(m[1]); result['refs']['advances'] = 2
        for i,p in enumerate(pdf):
            t = p.get_text()
            if 'Revenues by Equipment, Spares & Service' not in t:
                continue
            m = re.search(r'Equipment revenues\s+([\d.]+)', t)
            if m:
                result['equipment_ytd'] = float(m[1]); result['refs']['equipment_ytd'] = i+1
            break
    if 'equipment_ytd' not in result:
        raise ValueError('AIXTRON equipment revenue scope not confirmed')
    return result


def extract_veeco(data, url):
    with pymupdf.open(stream=data, filetype='pdf') as pdf:
        for i,p in enumerate(pdf):
            t = p.get_text()
            if 'Historical Revenue by End-Market' not in t:
                continue
            # Official May 2026 table: FY22, four quarters/FY23, FY24,
            # FY25, Q1/26. Annual columns are never treated as quarters.
            layout = [(2022,None)]+[(y,q) for y in [2023,2024,2025] for q in [1,2,3,4,None]]+[(2026,1)]
            def values(start, stop):
                block = t.split(start,1)[1].split(stop,1)[0]
                vals = [float(v) for v in re.findall(r'^\s*(\d+\.\d+)\s*$',block,re.M)]
                if len(vals)!=len(layout): raise ValueError('Veeco historical table layout changed')
                return vals
            compound=values('Compound', 'Data Storage')
            total=values('Total', 'Historical Revenue')
            return [dict(date=end_date(y,q), revenue=total[j],compound=compound[j],
                         url=url,pdf_page=i+1,precision='0.1 million USD',fetched=dt.date.today().isoformat())
                    for j,(y,q) in enumerate(layout) if q]
    raise ValueError('Veeco end-market table missing')


def extract_coherent(html, url, fy, quarter):
    soup=BeautifulSoup(html,'html.parser')
    text=soup.get_text(' ',strip=True)
    expected_month={1:'September',2:'December',3:'March',4:'June'}[quarter]
    year=fy-1 if quarter<3 else fy
    if not re.search(fr'{expected_month}\s+\d+,?\s+{year}',text,re.I):
        raise ValueError('Coherent fiscal period not confirmed')
    for table in soup.select('table'):
        tt=table.get_text(' ',strip=True)
        if 'Additions to property, plant' not in tt or 'Cash Flows' not in tt:
            continue
        if 'Millions' not in tt: raise ValueError('Coherent unit missing')
        for row in table.select('tr'):
            cells=[c.get_text(' ',strip=True) for c in row.find_all(['td','th'],recursive=False)]
            if not cells or not cells[0].startswith('Additions to property, plant'): continue
            nums=[float(v.replace(',','')) for c in cells[1:] for v in re.findall(r'\d[\d,]*\.\d+',c)]
            if len(nums)!=2: raise ValueError('Coherent CAPEX value layout changed')
            return [dict(date=end_date(y,{1:3,2:4,3:1,4:2}[quarter]),year=f,quarter=quarter,
                         capex_ytd=v,url=url,fetched=dt.date.today().isoformat())
                    for f,y,v in [(fy,year,nums[0]),(fy-1,year-1,nums[1])]]
    raise ValueError('Coherent cash CAPEX table missing')


def extract_coherent_pdf(data,url,fy,quarter):
    with pymupdf.open(stream=data,filetype='pdf') as pdf:
        alltext=' '.join(p.get_text() for p in pdf)
        month={1:'September',2:'December',3:'March',4:'June'}[quarter]
        year=fy-1 if quarter<3 else fy
        if not re.search(fr'{month}\s+\d+,?\s+{year}',alltext,re.I):
            raise ValueError('Coherent PDF fiscal period not confirmed')
        for i,p in enumerate(pdf):
            t=p.get_text()
            if 'Statements of Cash Flows' not in t or 'Millions' not in t:continue
            m=re.search(r'Additions to property,\s*plant\s*&\s*equipment\s+\(([\d,.]+)\)\s+\(([\d,.]+)\)',t)
            if not m:continue
            return [dict(date=end_date(y,{1:3,2:4,3:1,4:2}[quarter]),year=f,quarter=quarter,
                         capex_ytd=float(v.replace(',','')),url=url,pdf_page=i+1,
                         fetched=dt.date.today().isoformat())
                    for f,y,v in [(fy,year,m[1]),(fy-1,year-1,m[2])]]
    raise ValueError('Coherent PDF cash CAPEX row missing')


def fetch_coherent(url,fy,q):
    html=get(url).text
    try:return extract_coherent(html,url,fy,q)
    except ValueError as original:
        soup=BeautifulSoup(html,'html.parser')
        for a in soup.select('a[href]'):
            if '/static-files/' not in a['href']:continue
            pdfurl=urljoin(url,a['href'])
            return extract_coherent_pdf(get(pdfurl).content,pdfurl,fy,q)
        raise original


def merge(old,new):
    result={r['date']:r for r in old}
    result.update({r['date']:r for r in new})
    return sorted(result.values(),key=lambda r:r['date'])


def difference(rows, key, year_key='year'):
    lookup={(r[year_key],r['quarter']):r for r in rows}
    result=[]
    for row in sorted(rows,key=lambda r:r['date']):
        if key not in row: continue
        prev=lookup.get((row[year_key],row['quarter']-1))
        if row['quarter']!=1 and (not prev or key not in prev): continue
        value=round(row[key]-(prev[key] if row['quarter']>1 else 0),3)
        refs=[dict(url=row['url'],label=f"누적 {row['quarter']}개 분기",pdf_page=row.get('pdf_page') or row.get('refs',{}).get(key))]
        if row['quarter']>1:
            refs.append(dict(url=prev['url'],label=f"이전 누적 {prev['quarter']}개 분기",pdf_page=prev.get('pdf_page') or prev.get('refs',{}).get(key)))
        result.append(dict(row,value=value,supporting_sources=refs))
    return result


def chart(id,name,unit,rows,fields,description,**extra):
    series={label:[[r['date'],r[key]] for r in rows if key in r] for key,label in fields.items()}
    refs={r['date']:dict(url=r['url'],label=r.get('period',r['date']),
                         pdf_page=r.get('pdf_page'),**({'supporting_sources':r['supporting_sources']} if r.get('supporting_sources') else {})) for r in rows}
    dates=[d for points in series.values() for d,v in points]
    latest=max(dates)
    fetched=min((r.get('fetched','2026-10-09') for r in rows if r['date']==latest),default='2026-10-09')
    return dict(id=id,name=name,unit=unit,frequency='quarterly',quarter_labels=True,
                updated=max(dates),fetched=fetched,source='기업 공식 IR·공시',source_url=rows[-1]['url'],
                description=description,span_gaps=False,series=series,point_sources=refs,
                default_series=list(series),change_mode='yoy',**extra)


def build(facts,manual):
    aix=merge(facts.get('aix',[]),manual['aix_annual'])
    # Annual values supply Q4 balances and YTD equipment totals. Flow metrics
    # for Q4 are calculated from annual minus 9M; no balance differencing.
    for key in ['orders','revenue','ebit']:
        qs={r['date']:r for r in difference(aix,key+'_ytd')}
        for r in aix:
            if r['quarter']==4 and r['date'] in qs:
                r[key]=qs[r['date']]['value'];r['supporting_sources']=qs[r['date']]['supporting_sources']
    docs={}
    def add(*args,**kwargs):
        d=chart(*args,**kwargs);docs[d['id']]=d
    add('mocvd_aix_orders','AIXTRON · 총수주액·총매출','백만 EUR',aix,{'orders':'총수주액','revenue':'연결 매출'},
        '장비와 서비스·부품을 포함한 같은 범위의 수주액·매출입니다. Q4는 연간−9개월 누적 계산으로 원표 반올림 차이가 있을 수 있습니다.')
    add('mocvd_aix_backlog','AIXTRON · 장비 수주잔고','백만 EUR',aix,{'backlog':'장비 수주잔고'},
        '분기 말 장비 주문 잔액입니다. 서비스·부품 제외. 총수주액과 범위가 달라 잔고 증감을 총수주액으로 간주할 수 없습니다. 예산환율·취소·인식 기준 변화가 반영됩니다.')
    equip=difference(aix,'equipment_ytd')
    for r in equip:
        r['equipment']=r['value'];r['service']=round(r['revenue']-r['value'],3)
    add('mocvd_aix_revenue','AIXTRON · 장비·서비스 매출','백만 EUR',equip,{'equipment':'장비 매출','service':'서비스·부품 등'},
        '장비 매출은 공식 누적값을 차분한 분기 금액입니다. 서비스·부품 등은 연결 매출−장비 매출. InP/GaN MOCVD 외 SiC CVD도 포함합니다.')
    add('mocvd_aix_profit','AIXTRON · 영업이익 EBIT','백만 EUR',aix,{'ebit':'EBIT'},'연결 영업이익. Q4는 연간−9개월 누적 계산입니다.')
    add('mocvd_aix_advances','AIXTRON · 고객 선수금','백만 EUR',aix,{'advances':'선수금 계약부채'},
        '장비 발주 이후 고객이 선지급한 금액의 분기 말 잔액입니다. 현금 유입의 단서이며 신규 수주액·연간 CAPEX가 아닙니다.')
    ratios=[]
    for i,r in enumerate(aix):
        if 'orders' not in r or not r.get('revenue'):continue
        out=dict(r,ratio=round(r['orders']/r['revenue'],4))
        window=aix[max(0,i-3):i+1]
        if len(window)==4 and all('orders' in x and 'revenue' in x for x in window):
            expected=[end_date(int(r['date'][:4])-(r['quarter']<=k),((r['quarter']-1-k)%4)+1) for k in range(4)]
            if {x['date'] for x in window}==set(expected):
                out['ttm']=round(sum(x['orders'] for x in window)/sum(x['revenue'] for x in window),4)
        ratios.append(out)
    add('mocvd_aix_btb','AIXTRON · Book-to-bill','배',ratios,{'ratio':'분기 수주/매출','ttm':'최근 4분기 수주/매출'},
        '총수주액÷연결 매출입니다. 양쪽에 서비스·부품을 포함합니다. 1보다 높으면 해당 기간 수주가 매출을 초과합니다. 장비 잔고와 다른 범위입니다.',change_mode_override='none')
    add('mocvd_aix_order_mix','AIXTRON · 광전자 장비 수주 비중 · 최근 공시','%',manual['aix_order_mix'],{'opto':'광전자 / 장비 수주'},
        '동일 분모로 확인한 첫 값은 2026 Q2 약 75%입니다. 분모는 장비 수주이며 총수주액이 아닙니다. 레이저·광전자 전체로 InP 단독 비중이 아닙니다.',manual=True,chart_type='bar',change_mode_override='none')
    add('mocvd_aix_applications','AIXTRON · 장비 용도별 연간 매출','백만 EUR',manual['aix_applications'],
        {'opto':'광전자·통신','power':'GaN·SiC 전력','led':'LED·Micro LED','other':'기타'},
        '2025 공식 금액. 이전 연도는 공시 장비 매출×반올림된 용도 비중으로 계산한 근사치입니다. 광전자에는 레이저·태양광·통신 등이 포함되어 InP 단독 매출이 아닙니다.',
        frequency_override='yearly',year_labels=True,quarter_labels_override=False,manual=True,
        point_annotations={r['date']:'공시 장비 매출×반올림 비중' for r in manual['aix_applications'] if r.get('estimate')},chart_type='bar')
    veeco=merge(facts.get('veeco',[]),manual['veeco_quarters'])
    add('mocvd_veeco_revenue','Veeco · 연결·Compound Semiconductor 매출','백만 USD',veeco,
        {'revenue':'연결 매출','compound':'Compound Semiconductor'},
        'Compound Semiconductor는 광전자·전력·RF·태양광 대상 MOCVD·식각·습식·IBD 등을 포함합니다. MOCVD 단독 매출이 아닙니다. 과거 발표표는 0.1백만 USD 반올림입니다.')
    for r in veeco:r['share']=round(r['compound']/r['revenue']*100,3)
    add('mocvd_veeco_share','Veeco · Compound Semiconductor 비중','%',veeco,{'share':'Compound Semiconductor / 연결'},
        '공식 금액에서 계산한 매출 비중. MOCVD 비중이나 시장점유율이 아닙니다.')
    for company in ['lumentum','coherent']:
        rows=manual['lumentum_ytd'] if company=='lumentum' else facts.get('coherent',[])
        quarters=difference(rows,'capex_ytd')
        for r in quarters:r['capex']=r['value'];r['period']=f"FY{r['year']} Q{r['quarter']}"
        add('mocvd_'+company+'_capex',company.capitalize()+' · 회사 전체 현금 CAPEX','백만 USD',quarters,{'capex':'유형자산 취득 현금지출'},
            '6월 결산. 누적 현금흐름표 차분으로 계산한 분기 유형자산 취득 지출입니다. 건물·모듈·기타 제품 포함, InP/MOCVD 투자만의 금액이 아닙니다. 장비 발주보다 늦게 발생할 수 있습니다.',
            period_labels={r['date']:r['period'] for r in quarters},manual=company=='lumentum')
    add('mocvd_infineon_capex','Infineon · 회사 전체 투자 · 최근 공시','백만 EUR',manual['infineon_quarters'],
        {'capex':'유형자산 취득 현금지출','investments':'Investments · 무형자산·개발비 포함'},
        '9월 결산. 첫 구축은 FY2026 Q2·Q3입니다. Investments는 유형자산·기타 무형자산 투자·개발비 자산화의 합입니다. 두 계열 모두 회사 전체로 GaN 전용 금액이 아닙니다. 현금 유형자산은 PDF p.13, Investments는 p.3.',
        period_labels={r['date']:r['period'] for r in manual['infineon_quarters']},manual=True)
    # Manual tables retain their actual review date, never today's run timestamp.
    for id in ['mocvd_inp_projects','mocvd_gan_projects','mocvd_equipment_events','mocvd_coverage']:
        docs[id]=dict(manual[id],id=id,manual=True,fetched=manual['reviewed'],updated=manual['reviewed'])
    for d in docs.values():
        if d.pop('frequency_override',None)=='yearly':d['frequency']='yearly'
        if 'quarter_labels_override' in d:d['quarter_labels']=d.pop('quarter_labels_override')
        if 'change_mode_override' in d:d['change_mode']=d.pop('change_mode_override')
        if d.get('unit')=='%':d['change_mode']='percentage_points' if d['id']!='mocvd_aix_order_mix' else 'none'
        if d.get('frequency')=='quarterly' and d.get('unit','').startswith('백만'):
            d['quarterly_profit_summary']=d['id']=='mocvd_aix_profit'
            d['quarterly_revenue_summary']=d['id']!='mocvd_aix_profit'
            dates=sorted({p[0] for points in d['series'].values() for p in points})
            buckets={(int(date[:4]),(int(date[5:7])-1)//3+1):date for date in dates}
            d['comparison_dates']={date:dict(year_ago=buckets.get((int(date[:4])-1,(int(date[5:7])-1)//3+1)),
                                            quarter_ago=buckets.get((int(date[:4])-(int(date[5:7])<=3),((int(date[5:7])-1)//3-1)%4+1))) for date in dates}
    return docs


def collect(facts,backfill=False):
    errors=[]
    try:
        soup=BeautifulSoup(get(AIX).text,'html.parser')
        links=[]
        for a in soup.select('a[href]'):
            title=a.get_text(' ',strip=True)
            m=re.fullmatch(r'([369])-MONTHS-REPORT (20\d\d)',title)
            if m and '/en' in a['href']:
                year=int(m[2]);quarter=int(m[1])//3
                links.append((urljoin(AIX,a['href']),year,quarter))
        if not links:raise ValueError('No AIXTRON reports discovered')
        newest=max(y for _,y,_ in links)
        for url,year,quarter in links:
            if year<2022 or (not backfill and year<newest):continue
            try:
                row=extract_aix(get(url).content,url,year,quarter)
                facts['aix']=merge(facts.get('aix',[]),[row])
                print('AIXTRON',row['date'])
            except Exception as e:errors.append(f'AIXTRON {year}Q{quarter}: {e}')
    except Exception as e:errors.append(f'AIXTRON archive: {e}')
    if backfill:
        try:facts['veeco']=merge(facts.get('veeco',[]),extract_veeco(get(VECO).content,VECO))
        except Exception as e:errors.append(f'Veeco: {e}')
    try:
        soup=BeautifulSoup(get(COHR).text,'html.parser')
        urls=[]
        ordinal={'first':1,'second':2,'third':3,'fourth':4}
        for a in soup.select('a[href]'):
            h=a['href']
            m=re.search(r'coherent-corp-(?:reports|releases)-(first|second|third|fourth)-quarter-(?:and-full-(?:fiscal-)?year-)?(?:fiscal-(?:year-)?)?(20\d\d)',h)
            if m:urls.append((urljoin(COHR,h),int(m[2]),ordinal[m[1]]))
        # The current quarterly archive can lag the financial releases page.
        releases=BeautifulSoup(get('https://ir.coherent.com/news-events/financial-releases').text,'html.parser')
        for a in releases.select('a[href]'):
            m=re.search(r'coherent-corp-reports-(first|second|third|fourth)-quarter-(?:and-full-year-)?fiscal-(20\d\d)',a['href'])
            if m:urls.append((urljoin(COHR,a['href']),int(m[2]),ordinal[m[1]]))
        if not urls:raise ValueError('No Coherent quarterly releases discovered')
        newest=max(y for _,y,_ in urls)
        for url,fy,q in sorted(set(urls),key=lambda x:(x[1],x[2])):
            if fy<2025 or (not backfill and fy<newest):continue
            try:
                rows=fetch_coherent(url,fy,q)
                facts['coherent']=merge(facts.get('coherent',[]),rows)
                print('Coherent',fy,q)
            except Exception as e:errors.append(f'Coherent FY{fy}Q{q}: {e}')
    except Exception as e:errors.append(f'Coherent archive: {e}')
    return errors


def main():
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--backfill',action='store_true')
    args=p.parse_args()
    facts=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    manual=json.loads(MANUAL.read_text(encoding='utf-8'))
    errors=[] if args.offline else collect(facts,args.backfill)
    for e in errors:print('ERROR:',e)
    write(CACHE,facts)
    docs=build(facts,manual)
    for d in docs.values():
        for points in d.get('series',{}).values():
            if any(not math.isfinite(v) for _,v in points):raise ValueError('Invalid chart value')
    write(CACHE,facts)
    for id,d in docs.items():write(ROOT/f'data/semicon/{id}.json',d)
    print(f'{len(docs)} MOCVD documents built')
    return bool(errors)


if __name__=='__main__':raise SystemExit(main())

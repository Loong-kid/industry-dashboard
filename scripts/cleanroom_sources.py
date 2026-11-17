"""Credential-free MOPS consolidated statements, in original thousand TWD."""
import calendar
import re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/cleanroom/taiwan'
BASE='https://mopsov.twse.com.tw/mops/web/'
NAMES={'2404':'漢唐','6139':'亞翔','5536':'聖暉'}

def end(year,q):
    month=q*3
    return f'{year}-{month:02}-{calendar.monthrange(year,month)[1]}'

def number(value):
    value=re.sub(r'\s+','',value).replace(',','').replace('−','-')
    if value in ('','--','-','－'):return None
    if value.startswith('(') and value.endswith(')'):value='-'+value[1:-1]
    return float(value)

def parse_statement(text,ticker,year,q,cash=False):
    soup=BeautifulSoup(text,'html.parser');body=soup.get_text(' ',strip=True)
    if NAMES[ticker] not in body or f'民國{year-1911}年第{q}季' not in body or '新台幣仟元' not in body:
        raise ValueError('MOPS issuer/period/unit mismatch')
    if '合併' not in body:raise ValueError('MOPS consolidated statement absent')
    result={}
    for tr in soup.select('tr'):
        cells=[td.get_text('',strip=True) for td in tr.find_all(['td','th'],recursive=False)]
        if len(cells)<2:continue
        name=re.sub(r'\s+','',cells[0])
        metric=('capex' if name in ('取得不動產、廠房及設備','購置不動產、廠房及設備') else None) if cash else (
            'revenue' if name in ('營業收入合計','營業收入') else 'profit' if name in ('營業利益（損失）','營業利益(損失)','營業利益','營業損失') else None)
        if not metric:continue
        if metric in result:raise ValueError('Duplicate statement total')
        current=number(cells[1]);position=5 if not cash and q in (2,3) else 1
        if position>=len(cells):raise ValueError('MOPS income columns changed')
        ytd=number(cells[position])
        if cash:
            if current is not None and current>0:raise ValueError('Unexpected PP&E cash sign')
            current=None;ytd=-ytd if ytd is not None else 0.0
        if name=='營業損失':current=-abs(current) if current is not None else None;ytd=-abs(ytd) if ytd is not None else None
        result[metric]=dict(value=current/1000 if current is not None and q<4 else None,
            ytd=ytd/1000 if ytd is not None else None,account_name=name)
    if not cash and not all(m in result for m in ('revenue','profit')):raise ValueError('Missing MOPS income totals')
    if cash and 'capex' not in result:raise ValueError('Missing cash PP&E acquisition row')
    return result

def accounts(reports):
    index={(r['year'],r['quarter']):r for r in reports};rows=[];annual=[]
    for (year,q),r in sorted(index.items()):
        row=dict(date=end(year,q),year=year,quarter=q,refs={})
        a=dict(date=end(year,4),year=year,refs={})
        for m,f in r['fields'].items():
            if q==4 and f['ytd'] is not None:
                a[m]=f['ytd'];a['refs'][m]=dict(f,calculation='reported annual',components=[f])
            value=f.get('value');components=[f];calculation='reported three months'
            if m=='capex' or q==4:
                previous=index.get((year,q-1),{}).get('fields',{}).get(m)
                if q==1:value=f['ytd'];calculation='reported first quarter cash flow'
                elif previous and f['ytd'] is not None and previous['ytd'] is not None:
                    value=round(f['ytd']-previous['ytd'],6);components=[f,previous];calculation='same-year consolidated YTD minus prior YTD'
                else:value=None
                if m=='capex' and value is not None and value<0:value=None
            if value is not None:row[m]=value;row['refs'][m]=dict(f,components=components,calculation=calculation)
        if row['refs']:rows.append(row)
        if q==4 and a['refs']:annual.append(a)
    return dict(rows=rows,annual=annual,reports=reports)


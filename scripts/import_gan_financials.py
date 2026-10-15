"""Import reviewed GaN manufacturer financials from original public disclosures.

Reads a hash-checked SEC companyfacts snapshot for Power Integrations and
original Innoscience PDFs downloaded from its public IR pages. Infineon
reviewed annual data is retained separately; no annual/half-year amount is
divided into imaginary quarters. All amounts retain original currencies.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import pymupdf

from import_mocvd_history import sec_history

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'manual/mocvd_gan_financials.json'


def inno_history(folder,asof):
    registry={r['name']:r for r in json.loads((folder/'pdf-registry.json').read_text(encoding='utf-8')) if r.get('ok')}
    specs=[('inno-ipo',503,508,[(2021,0),(2022,0),(2023,0),(2023,1),(2024,1)]),
           ('inno-2024',82,86,[(2024,0),(2023,0)]),
           ('inno-2025',88,92,[(2025,0),(2024,0)]),
           ('inno-2025h1',39,44,[(2025,1),(2024,1)]),
           ('inno-2026h1',20,23,[(2026,1),(2025,1)])]
    patterns={'revenue':r'Revenue\s+(?:4\s+)?', 'profit':r'Loss from operations\s+',
              'capex':r'Payment for the purchase of\s+property, plant and\s+equipment\s+and\s+intangible assets\s+'}
    facts={}
    for name,income,cash,periods in specs:
        source=registry[name];path=folder/(name+'.pdf')
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        with pymupdf.open(path) as pdf:
            for metric,pattern in patterns.items():
                page=cash if metric=='capex' else income
                text=pdf[page-1].get_text(sort=True)
                if "RMB’000" not in text:raise ValueError(f'{name}: currency/scale missing')
                match=re.search(r'^\s*'+pattern+r'([^\n]+)',text,re.M)
                if not match:raise ValueError(f'{name}: {metric} row missing')
                values=re.findall(r'\(?\d{1,3}(?:,\d{3})+\)?',match[1])
                if len(values)!=len(periods):raise ValueError(f'{name}: unexpected {metric} columns {values}')
                for (year,half),value in zip(periods,values):
                    date=f'{year}-06-30' if half else f'{year}-12-31'
                    row=facts.setdefault((year,half),dict(date=date,year=year,half=half,
                        period=f'{year} H{half}' if half else f'FY{year}',fetched=asof,refs={}))
                    number=int(value.replace('(','').replace(')','').replace(',',''))
                    if value.startswith('(') and metric!='capex':number=-number
                    row[metric]=number/1000
                    row['refs'][metric]=dict(url=source['url'],pdf_page=page,label=row['period'],
                        original_currency='CNY',original_scale='RMB thousands',pdf_sha256=sha,
                        calculation='reported half-year' if half else 'reported annual')
    annuals=[];halves=[]
    for (year,half),row in sorted(facts.items()):
        row['url']=row['refs']['revenue']['url']
        (halves if half else annuals).append(row)
        if half or (year,1) not in facts:continue
        h1=facts[(year,1)]
        h2=dict(date=f'{year}-12-31',year=year,half=2,period=f'{year} H2',url=row['url'],fetched=asof,refs={})
        for metric in patterns:
            h2[metric]=round(row[metric]-h1[metric],3)
            h2['refs'][metric]=dict(row['refs'][metric],label=h2['period'],calculation='FY minus H1',
                supporting_sources=[row['refs'][metric],h1['refs'][metric]])
        halves.append(h2)
    return dict(name='Innoscience · 이노사이언스',unit='백만 CNY',annuals=annuals,halfyears=sorted(halves,key=lambda r:r['date']),
        founded='2017-07-21',first_public_financial_year=2021,
        scope='GaN 사업 중심 연결 전체. GaN 웨이퍼·개별 칩·IC·모듈·관련 서비스 포함. CAPEX는 공시가 묶어서 제시하는 유형·무형자산 취득 현금지출.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--as-of',required=True)
    a=p.parse_args();dt.date.fromisoformat(a.as_of)
    existing=json.loads(DEST.read_text(encoding='utf-8')) if DEST.exists() else {'companies':{}}
    powi=sec_history(a.source_dir,'powi',a.as_of)
    powi.update(name='Power Integrations',unit='백만 USD',scope='회사 전체 연결. GaN 제품 외 실리콘 전원 IC·게이트 드라이버 등 포함. CAPEX는 유형자산 취득 현금지출.')
    existing['companies'].update(powi=powi,innoscience=inno_history(a.source_dir,a.as_of))
    existing['reviewed']=a.as_of
    DEST.write_text(json.dumps(existing,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print('Power Integrations',len(powi['quarters']),'quarters;',len(powi['annuals']),'annuals')
    inno=existing['companies']['innoscience'];print('Innoscience',len(inno['annuals']),'annuals;',len(inno['halfyears']),'half-years')


if __name__=='__main__':main()

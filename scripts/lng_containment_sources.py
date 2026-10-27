"""Reviewed original GTT rows, with actual quarters and half years."""
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from quantum_sources import period
from shipbuilding_equipment_sources import end

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/lng-containment'
MANUAL=ROOT/'manual/lng-containment'
IR='https://www.gtt.fr/finance/investor-relations/investors-pack'


def reviewed_rows(sources,asof):
    cumulative={}
    for source in sorted(sources,key=lambda s:s['filed']):
        if source['filed']>asof:continue
        for metric,f in source['fields'].items():
            for year,value in zip(f['columns'],f['values']):
                if year<2014:continue
                # Actual comparative restatements take precedence, including
                # IFRS 15 pro-forma prior-year comparatives in the issuer report.
                ref=dict(url=source['url'],filed=source['filed'],start=f'{year}-01-01',end=end(year,source['quarter']),
                    location='GTT 연결 손익계산서' if source['quarter'] in [2,4] else 'GTT 연결 매출 공시',
                    tag=f['anchor'].split(' '+str(f['values'][0]))[0],comparative=year!=source['year'],
                    source_sha256=source['sha256'],calculation='reported cumulative')
                cumulative[year,source['quarter'],metric]=(value/(1000 if f['unit']=='thousands' else 1),ref)
    rows=[]
    for year in sorted({k[0] for k in cumulative}):
        for q in range(1,5):
            revenue=cumulative.get((year,q,'revenue'));prior=cumulative.get((year,q-1,'revenue'))
            if revenue and (q==1 or prior):
                row=period(f'{year}-{q*3-2:02d}-01',end(year,q),'EUR')
                row['revenue']=revenue[0]-(prior[0] if prior else 0)
                row['refs']['revenue']=dict(revenue[1],calculation='same fiscal-year cumulative minus prior cumulative' if prior else 'reported quarter',
                    **(dict(components=[revenue[1],prior[1]]) if prior else {}))
                if row['revenue']>=0 and row['date']<=asof:rows.append(row)
        for kind,start,q in [('annual',1,4),('half',1,2),('half',7,4)]:
            row=period(f'{year}-{start:02d}-01',end(year,q),'EUR')
            if row['date']>asof:continue
            for metric in ['revenue','profit','netincome']:
                current=cumulative.get((year,q,metric));prior=cumulative.get((year,2,metric)) if start==7 else None
                if not current or (start==7 and not prior):continue
                row[metric]=current[0]-(prior[0] if prior else 0)
                row['refs'][metric]=dict(current[1],calculation='reported annual minus same-year half-year' if prior else 'reported actual period',
                    **(dict(components=[current[1],prior[1]]) if prior else {}))
            if row['refs']:rows.append(row)
    return sorted(rows,key=lambda r:(r['date'],r['kind']))


def verify_pdf(raw,source):
    if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('reviewed source changed')
    text=re.sub(r'\s+',' ',' '.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages))
    if any(f['anchor'] not in text for f in source['fields'].values()):raise ValueError('reviewed statement row changed')


def collect_gtt(previous,asof,offline=False):
    sources=json.loads((MANUAL/'gtt-reviewed.json').read_text(encoding='utf8'))
    errors=[];verified=set(previous.get('verified_sources',[]));known={s['url'] for s in sources}
    latest=max(s['filed'] for s in sources)
    if not offline:
        try:
            response=requests.get(IR,timeout=(8,25));response.raise_for_status()
            soup=BeautifulSoup(response.content,'html.parser')
            for a in soup.select('a[href]'):
                title=a.get_text(' ',strip=True).lower();url=urljoin(IR,a['href'])
                date=a.parent.parent.select_one('.date')
                found=re.search(r'20\d{2}-\d{2}-\d{2}',date.get_text() if date else '')
                if found and latest<found[0]<=asof and url.lower().endswith('.pdf') and any(t in title for t in ['results','revenue']) and not any(t in title for t in ['presentation','webcast','registration','transcript']):
                    if url not in known:errors.append('새 GTT 실적 원문 수치 검토 필요: '+found[0]+' · '+url)
            for source in sources:
                if source['sha256'] in verified and source['filed']<latest:continue
                path=CACHE/source['file']
                if not path.exists() or source['filed']==latest:
                    response=requests.get(source['url'],timeout=(8,30));response.raise_for_status();path.write_bytes(response.content)
                verify_pdf(path.read_bytes(),source);verified.add(source['sha256'])
        except (requests.RequestException,ValueError,OSError) as exc:errors.append('GTT 원문 조회 미완료 ('+type(exc).__name__+')')
    rows=reviewed_rows(sources,asof)
    return dict(rows=rows,checked=previous.get('checked',asof) if offline else asof,
        fetched=previous.get('fetched',asof) if offline else asof if not errors else previous.get('fetched'),
        status='partial' if errors else 'ok',source_errors=errors,verified_sources=sorted(verified))

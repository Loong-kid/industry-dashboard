"""Only officially disclosed actual quarter results; no forecasts or CAPEX estimates."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import requests
from collect_ring_sources import api
from fetch_cpu_companies import save
from shipbuilding_equipment_sources import provisional


def public_get(session,url):
    try:r=session.get(url,timeout=(10,25))
    except requests.exceptions.SSLError:
        bundle=Path('/etc/ssl/certs/ca-certificates.crt')
        if not bundle.exists():raise
        r=session.get(url,timeout=(10,25),verify=str(bundle))
    r.raise_for_status();return r.content


def collect(cache,meta):
    key=os.environ.get('DART_API_KEY')
    if not key:raise ValueError('DART_API_KEY not configured')
    entities=json.loads((cache/'entities.json').read_bytes());session=requests.Session()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    for company,spec in meta['companies'].items():
        rows=[];errors=[];entity=entities[company]
        try:
            payload=api(session,'list.json',key,corp_code=entity['corp_code'],bgn_de=asof[:4]+'0101',end_de=asof.replace('-',''),last_reprt_at='Y',page_count=100).json()
            if payload.get('status') not in ['000','013']:raise ValueError('Official preliminary list unavailable')
            entries=[r for r in payload.get('list',[]) if '영업(잠정)실적' in r['report_nm'] and '연결재무제표' in r['report_nm']][:3]
            for entry in entries:
                receipt=entry['rcept_no']
                if entry['rcept_dt']>asof.replace('-',''):continue
                try:
                    main=public_get(session,'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+receipt)
                    (cache/f'{company}-prelim-{receipt}-main.html').write_bytes(main)
                    text=main.decode('utf8')
                    if not any(n in text for n in [spec['name']]+spec.get('aliases',[])):raise ValueError('Issuer mismatch')
                    targets=set(re.findall(r'viewDoc\("'+receipt+r'",\s*"(\d+)",\s*"(\d+)",\s*"(\d+)",\s*"(\d+)",\s*"([A-Z]+)"',text))
                    if len(targets)!=1:raise ValueError('Preliminary viewer mapping changed')
                    dcm,ele,offset,length,dtd=next(iter(targets))
                    url=f'https://dart.fss.or.kr/report/viewer.do?rcpNo={receipt}&dcmNo={dcm}&eleId={ele}&offset={offset}&length={length}&dtd={dtd}'
                    raw=public_get(session,url);(cache/f'{company}-prelim-{receipt}.html').write_bytes(raw)
                    row=provisional(raw,receipt,'CFS',asof,required_metrics=('revenue','profit'))
                    for metric,f in row['refs'].items():
                        f.update(account_name=f['tag'],comparative=False,basis='reported_income')
                        f['components']=[dict(f)]
                    rows.append(row)
                except (ValueError,requests.RequestException,UnicodeError) as error:
                    errors.append(dict(receipt=receipt,error=type(error).__name__))
            save(cache/(company+'-preliminaries.json'),dict(checked=asof,rows=rows,errors=errors))
            print(company,len(rows),'official preliminary quarters',len(errors),'review items',flush=True)
        except (ValueError,requests.RequestException):
            save(cache/(company+'-preliminaries.json'),dict(checked=asof,rows=[],errors=[dict(error='Official preliminary list unavailable')]))

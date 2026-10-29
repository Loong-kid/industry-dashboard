"""Archive credential-free original OpenDART statements for Si/SiC parts issuers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import io
import json
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET
import zipfile

import requests
from fetch_cpu_companies import save

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/rings'
META=ROOT/'manual/rings/companies.json'


def api(session,name,key,**params):
    try:
        r=session.get('https://opendart.fss.or.kr/api/'+name,params=dict(crtfc_key=key,**params),timeout=(10,40))
        r.raise_for_status();return r
    except requests.RequestException:
        raise ValueError('OpenDART original unavailable') from None


def collect(full=False):
    key=os.environ.get('DART_API_KEY')
    if not key:raise ValueError('DART_API_KEY not configured')
    CACHE.mkdir(parents=True,exist_ok=True)
    meta=json.loads(META.read_bytes())['companies'];session=requests.Session()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    raw=api(session,'corpCode.xml',key).content
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:tree=ET.fromstring(z.read('CORPCODE.xml'))
        entities={}
        for company,spec in meta.items():
            matches=[r for r in tree.findall('list') if r.findtext('stock_code','').strip()==spec['ticker']]
            if len(matches)!=1:raise ValueError('ambiguous stock code')
            r=matches[0];name=r.findtext('corp_name')
            if name not in [spec['name']]+spec.get('aliases',[]):raise ValueError('issuer name changed')
            entities[company]=dict(corp_code=r.findtext('corp_code'),name=name,ticker=spec['ticker'])
    except (ET.ParseError,zipfile.BadZipFile,KeyError,ValueError):
        raise ValueError('OpenDART issuer mapping needs review') from None
    save(CACHE/'entities.json',entities)
    def issuer(item):
        company,entity=item;own=requests.Session();status=dict(checked=asof,ok=True,reports=[]);errors=[];fails=0
        first=2015 if full else int(asof[:4])-1
        for year in range(first,int(asof[:4])+1):
            for q,code in [(1,'11013'),(2,'11012'),(3,'11014'),(4,'11011')]:
                end=f'{year}-{q*3:02d}-{30 if q in (2,3) else 31}'
                if end>asof:continue
                try:
                    for fs in ['CFS','OFS']:
                        filename=f'{company}-{year}-q{q}-{fs}.json'
                        payload=api(own,'fnlttSinglAcntAll.json',key,corp_code=entity['corp_code'],bsns_year=year,reprt_code=code,fs_div=fs).json()
                        code_status=payload.get('status')
                        if code_status not in ['000','013']:raise ValueError('OpenDART report check failed')
                        if any(r.get('corp_code',entity['corp_code'])!=entity['corp_code'] for r in payload.get('list',[])):raise ValueError('issuer mismatch')
                        save(CACHE/filename,dict(status=code_status,list=payload.get('list',[])))
                        if code_status=='000':
                            status['reports'].append(dict(year=year,quarter=q,fs_div=fs,path=filename));break
                        time.sleep(.15)
                    fails=0
                except (ValueError,KeyError):
                    errors.append(dict(year=year,quarter=q,message='Original source check failed'))
                    fails+=1
                    if fails>=3:break
                time.sleep(.15)
            print(company,year,'checked',flush=True)
            if fails>=3:break
        status.update(ok=not errors,errors=errors)
        save(CACHE/(company+'-status.json'),status)
        print(company,len(status['reports']),'statement reports',len(errors),'source failures',flush=True)
        return company,status
    with ThreadPoolExecutor(max_workers=3) as pool:status=dict(pool.map(issuer,entities.items()))
    save(CACHE/'status.json',status)
    if not all(s['ok'] for s in status.values()):print('Some source checks failed; retained history must be preserved.',flush=True)
    return status


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full-history',action='store_true');args=p.parse_args()
    collect(args.full_history)

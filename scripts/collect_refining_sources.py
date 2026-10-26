"""Archive public refiner statements; DART credentials never enter saved files."""
import argparse
import datetime as dt
import io
import json
import os
from pathlib import Path
import time
import zipfile
import xml.etree.ElementTree as ET

import requests
import collect_oil_sources as sec

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/refining'
CIKS={'vlo':1035002,'mpc':1510295,'psx':1534701}


def collect(full=False):
    sec.CACHE=CACHE;sec.CIKS=CIKS
    status=sec.collect(full)
    key=os.environ.get('DART_API_KEY')
    if not key:
        status['soil']={'ok':False,'error':'DART credential unavailable'}
    else:
        session=requests.Session()
        try:
            response=session.get('https://opendart.fss.or.kr/api/corpCode.xml',params={'crtfc_key':key},timeout=45)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                tree=ET.fromstring(archive.read('CORPCODE.xml'))
            matches=[row for row in tree.findall('list') if row.findtext('stock_code','').strip()=='010950']
            if len(matches)!=1:raise ValueError('S-Oil stock code mapping changed')
            corp=matches[0].findtext('corp_code')
            (CACHE/'soil-entity.json').write_text(json.dumps(dict(corp_code=corp,stock_code='010950',name=matches[0].findtext('corp_name')),ensure_ascii=False),encoding='utf8')
            asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
            first=2015 if full else int(asof[:4])-1
            count=0
            for year in range(first,int(asof[:4])+1):
                for q,code in [(1,'11013'),(2,'11012'),(3,'11014'),(4,'11011')]:
                    end=f'{year}-{q*3:02d}-'+('30' if q in (2,3) else '31')
                    if end>asof:continue
                    path=CACHE/f'soil-{year}-q{q}.json'
                    if full and path.exists() and year<int(asof[:4])-1:continue
                    response=session.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json',params=dict(crtfc_key=key,corp_code=corp,bsns_year=year,reprt_code=code,fs_div='CFS'),timeout=35)
                    # Never print request exceptions: their URLs contain the API key.
                    if response.status_code!=200:raise ValueError('DART HTTP error')
                    payload=response.json()
                    if payload.get('status')=='013':continue
                    if payload.get('status')!='000':raise ValueError('DART report unavailable')
                    if any(r.get('corp_code')!=corp for r in payload['list']):raise ValueError('DART entity mismatch')
                    path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8');count+=1
                    time.sleep(.15)
                print('S-Oil',year,'public statements collected',flush=True)
            status['soil']=dict(ok=True,reports=count)
        except Exception:
            status['soil']=dict(ok=False,error='DART collection failed')
            print('S-Oil public statement collection failed; retain prior snapshot',flush=True)
    (CACHE/'collection-status.json').write_text(json.dumps(status),encoding='utf8')
    return status


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true')
    collect(parser.parse_args().full)

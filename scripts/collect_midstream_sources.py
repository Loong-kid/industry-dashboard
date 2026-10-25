"""Download public SEC accounts and compressor filings at SEC's normal rate.

Raw originals remain in .cache for review/artifacts, never in the public site.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import time

import requests

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/midstream'
COMPANIES={'kmi':1506307,'wmb':107263,'et':1276187,'epd':1061219,'trgp':1389170,'aroc':1389050,'kgs':1767042,'usac':1522727}

def collect(full=False):
    CACHE.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    def get(url,path):
        if path.exists():return path.read_bytes()
        response=session.get(url,timeout=45);response.raise_for_status()
        path.write_bytes(response.content);time.sleep(.25)
        return response.content
    for key,cik in COMPANIES.items():
        # Structured facts and submission indexes must refresh on every run.
        for kind,url in [('facts',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'),('sub',f'https://data.sec.gov/submissions/CIK{cik:010d}.json')]:
            response=session.get(url,timeout=45);response.raise_for_status()
            (CACHE/f'{key}-{kind}.json').write_bytes(response.content);time.sleep(.25)
        if key not in ['aroc','kgs','usac','trgp']:continue
        sub=json.loads((CACHE/f'{key}-sub.json').read_bytes())
        groups=[sub['filings']['recent']]
        for archive in sub['filings'].get('files',[]):
            if archive['filingTo']<'2014-01-01':continue
            groups.append(json.loads(get('https://data.sec.gov/submissions/'+archive['name'],CACHE/archive['name'])))
        registry={}
        for group in groups:
            for i,form in enumerate(group['form']):
                if form not in ['10-K','10-K/A','10-Q','10-Q/A','S-1','S-1/A']:continue
                if group['filingDate'][i]<'2014-01-01' or group['filingDate'][i]>asof:continue
                if not full and group['filingDate'][i]<'2024-01-01':continue
                accession=group['accessionNumber'][i];document=group['primaryDocument'][i]
                url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-","")}/{document}'
                path=CACHE/f'{key}-{accession}.html'
                try:
                    get(url,path)
                    registry[accession]=dict(url=url,form=form,filed=group['filingDate'][i],date=group.get('reportDate',['']*len(group['form']))[i],path=path.name)
                except requests.HTTPError as error:
                    print(key,accession,'unavailable',error.response.status_code)
        (CACHE/f'{key}-filings.json').write_text(json.dumps(registry,indent=1),encoding='utf8')
        print(key,'filings',len(registry),flush=True)
    print('Public sources collected',asof)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true')
    collect(parser.parse_args().full)

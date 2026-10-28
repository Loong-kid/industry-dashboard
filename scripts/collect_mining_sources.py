"""Collect public SEC mining issuer facts and annual statement originals."""
import datetime as dt
import json
from pathlib import Path
import time
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/mining'
CIKS={'bhp':811809,'scco':1001838,'rio':863064,'nem':1164727,
      'fcx':831259,'aem':2809,'barrick':756894,'ero':1853860}


def collect(only=None):
    CACHE.mkdir(parents=True,exist_ok=True)
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();status={}
    for key,cik in CIKS.items():
        if only and key!=only:continue
        try:
            for kind,url in [('facts',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'),('sub',f'https://data.sec.gov/submissions/CIK{cik:010d}.json')]:
                r=session.get(url,timeout=45);r.raise_for_status();(CACHE/f'{key}-{kind}.json').write_bytes(r.content);time.sleep(.25)
            sub=json.loads((CACHE/f'{key}-sub.json').read_bytes());groups=[sub['filings']['recent']]
            for arc in sub['filings'].get('files',[]):
                if arc['filingTo']<'2014-01-01':continue
                path=CACHE/arc['name']
                if not path.exists():
                    r=session.get('https://data.sec.gov/submissions/'+arc['name'],timeout=45);r.raise_for_status();path.write_bytes(r.content);time.sleep(.25)
                groups.append(json.loads(path.read_bytes()))
            registry={}
            for group in groups:
                for i,form in enumerate(group['form']):
                    report=group.get('reportDate',['']*len(group['form']))[i];filed=group['filingDate'][i]
                    if filed>asof or filed<'2014-01-01':continue
                    interim=(key=='ero' and form=='6-K' and report[5:] in ['03-31','06-30','09-30','12-31'])
                    if form not in ['10-K','10-K/A','20-F','20-F/A','40-F','40-F/A','10-Q'] and not interim:continue
                    if form=='10-Q' and report<'2024-01-01':continue
                    if report and report<'2014-01-01':continue
                    accn=group['accessionNumber'][i];doc=group['primaryDocument'][i]
                    url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace("-","")}/{doc}'
                    path=CACHE/f'{key}-{accn}.html'
                    if not path.exists():
                        r=session.get(url,timeout=45);r.raise_for_status();path.write_bytes(r.content);time.sleep(.25)
                    registry[accn]=dict(url=url,form=form,filed=filed,date=report,path=path.name)
                    if form.startswith('40-F') or interim:
                        soup=BeautifulSoup(path.read_bytes(),'html.parser')
                        for a in soup.select('a[href]'):
                            text=a.get_text(' ',strip=True).lower();href=a['href']
                            if not ('financial statements' in text or 'annual report' in text or 'discussion and analysis' in text):continue
                            if not href.lower().endswith(('.htm','.html','.pdf')):continue
                            target=urljoin(url,href)
                            if not target.startswith('https://www.sec.gov/Archives/'):continue
                            filename=f'{key}-{accn}-'+target.rsplit('/',1)[-1];extra=CACHE/filename
                            if not extra.exists():
                                response=session.get(target,timeout=45);response.raise_for_status();extra.write_bytes(response.content);time.sleep(.25)
                            registry[accn+'-'+filename]=dict(url=target,form=form,filed=filed,date=report,path=filename)
            (CACHE/f'{key}-filings.json').write_text(json.dumps(registry,indent=1),encoding='utf8')
            status[key]=dict(ok=True,checked=asof);print(key,len(registry),'public statement originals',flush=True)
        except Exception as error:
            status[key]=dict(ok=False,checked=asof,error=type(error).__name__)
            print(key,'public source unavailable:',type(error).__name__,flush=True)
    (CACHE/'collection-status.json').write_text(json.dumps(status),encoding='utf8')
    return status


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--company',choices=list(CIKS))
    collect(parser.parse_args().company)

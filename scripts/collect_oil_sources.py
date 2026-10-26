"""Download public issuer SEC facts and reviewed original statement filings."""
import datetime as dt
import json
from pathlib import Path
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/oil'
CIKS={'xom':34088,'xom_successor':2115436,'cvx':93410,'cop':1163165,'shell':1306965,'bp':313807,'tte':879764,'equinor':1140625}

def collect():
    CACHE.mkdir(parents=True,exist_ok=True)
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();status={}
    for key,cik in CIKS.items():
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
                    filed=group['filingDate'][i];report=group.get('reportDate',['']*len(group['form']))[i]
                    # Annual statements supply the original accounting definitions;
                    # quarterly structured facts are fetched above in one request.
                    if form not in ['10-K','10-K/A','20-F','20-F/A','10-Q','8-K12B','6-K']:continue
                    if filed>asof or filed<'2014-01-01':continue
                    if form=='6-K' and (not report or report[5:] not in ['03-31','06-30','09-30','12-31']):continue
                    if form.startswith('10-K') or form.startswith('20-F'):
                        if report and report<'2014-12-31':continue
                    acc=group['accessionNumber'][i];doc=group['primaryDocument'][i]
                    url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace("-","")}/{doc}'
                    path=CACHE/f'{key}-{acc}.html'
                    if not path.exists():
                        r=session.get(url,timeout=45);r.raise_for_status();path.write_bytes(r.content);time.sleep(.25)
                    registry[acc]=dict(url=url,form=form,filed=filed,date=report,path=path.name)
            (CACHE/f'{key}-filings.json').write_text(json.dumps(registry,indent=1),encoding='utf8')
            status[key]=dict(ok=True,checked=asof)
            print(key,len(registry),'originals',flush=True)
        except Exception as error:
            status[key]=dict(ok=False,checked=asof,error=type(error).__name__)
            print(key,'unavailable',type(error).__name__,flush=True)
    (CACHE/'collection-status.json').write_text(json.dumps(status),encoding='utf8')
    return status

if __name__=='__main__':collect()

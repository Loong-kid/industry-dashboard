"""Archive original Sapien supply-contract disclosures and all amendments."""
import datetime as dt,json,os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from collect_ring_sources import api
from dart_extractor import fetch_document_html
from fetch_cpu_companies import load,save

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/vrar/contracts'
STATE=ROOT/'data/vrar/contract_source_state.json'
CORP='01676642';TICKER='452430'


def collect():
    key=os.environ.get('DART_API_KEY')
    if not key:raise ValueError('DART_API_KEY not configured')
    CACHE.mkdir(parents=True,exist_ok=True);session=requests.Session()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat();entries=[];page=1
    while True:
        payload=api(session,'list.json',key,corp_code=CORP,bgn_de='20240101',end_de=asof.replace('-',''),pblntf_ty='I',page_count=100,page_no=page).json()
        if payload.get('status')=='013':break
        if payload.get('status')!='000':raise ValueError('Contract list unavailable')
        for row in payload['list']:
            if row.get('corp_code')!=CORP or row.get('stock_code')!=TICKER:raise ValueError('Contract issuer mismatch')
            if '단일판매' in row['report_nm'] or '공급계약' in row['report_nm']:entries.append(row)
        if page>=int(payload.get('total_page',1)):break
        page+=1
    if not entries:raise ValueError('Contract list unexpectedly empty')
    save(CACHE/'list.json',dict(checked=asof,corp_code=CORP,stock_code=TICKER,entries=entries))
    existing=load(STATE,dict(disclosures=[]));prior={r['receipt']:r for r in existing.get('disclosures',[])}
    def original(entry):
        receipt=entry['rcept_no'];path=CACHE/(receipt+'.html')
        try:
            if not path.exists():
                if receipt in prior and prior[receipt].get('raw_html'):path.write_text(prior[receipt]['raw_html'],encoding='utf8')
                else:path.write_text(fetch_document_html(requests.Session(),key,receipt),encoding='utf8')
            return dict(receipt=receipt,path=path.name,entry=entry),None
        except Exception as error:return None,dict(receipt=receipt,error=type(error).__name__)
    reports=[];errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result,error in pool.map(original,entries):
            if error:errors.append(error)
            else:reports.append(result)
    save(CACHE/'status.json',dict(checked=asof,corp_code=CORP,ticker=TICKER,ok=not errors,reports=reports,errors=errors))
    print('Sapien contract originals:',len(reports),'disclosures;',len(errors),'review items',flush=True)
    return dict(checked=asof,ok=not errors,reports=reports,errors=errors)


if __name__=='__main__':collect()

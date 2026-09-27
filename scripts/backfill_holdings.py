"""One-off institution history backfill; credentials stay in the CI environment."""
import argparse
import csv
import datetime as dt
import io
import json
import os
from pathlib import Path
import time
import zipfile
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import random
import threading
from holding_document import parse_holding_document, HoldingParseError

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'work' / 'holdings-backfill'
FIELDS = ['rcept_no','rcept_dt','corp_cls','corp_name','stock_code','report_nm','flr_nm','corp_code']
DETAIL_FIELDS = ['rcept_no','rcept_dt','corp_code','corp_name','report_tp','repror','stkqy','stkqy_irds','stkrt','stkrt_irds','report_resn']
STOP = threading.Event()

def load_rows(path):
    if not path.exists(): return {}
    with path.open(encoding='utf-8-sig',newline='') as f:
        return {r['rcept_no']:r for r in csv.DictReader(f)}

def save_rows(path, rows, fields):
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(sorted(rows.values(),key=lambda r:(r['rcept_dt'],r['rcept_no']),reverse=True))
    tmp.replace(path)

def fetch_document(row):
    if STOP.is_set(): return row, None, 'quota_stopped', None
    try:
        with requests.Session() as session:
            raw=request(session,'document.xml',rcept_no=row['rcept_no']).content
        if not zipfile.is_zipfile(io.BytesIO(raw)):
            import re
            match=re.search(rb'<status>(\d+)</status>',raw)
            code=match.group(1).decode() if match else 'invalid_response'
            if code=='020': STOP.set()
            return row, None, 'api_'+code, None
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name=next((n for n in z.namelist() if n.lower().endswith('.xml')),z.namelist()[0])
            xml=z.read(name)
        try:
            result=parse_holding_document(xml,row)
            return row, result, None, hashlib.sha256(xml).hexdigest()
        except (HoldingParseError,UnicodeDecodeError) as e:
            (OUT/'rejected').mkdir(exist_ok=True)
            (OUT/'rejected'/(row['rcept_no']+'.xml')).write_bytes(xml)
            return row, None, str(e), None
    except Exception as e:
        return row, None, type(e).__name__, None

def details(limit, validation=False):
    listing=load_rows(OUT/'holdings.csv')
    existing=load_rows(ROOT/'data/_dart/대량보유상세DB.csv')
    added=load_rows(OUT/'details.csv')
    audit_path=OUT/'audit.json'
    audit=json.loads(audit_path.read_text(encoding='utf-8')) if audit_path.exists() else {'success':{},'errors':{}}
    if audit.get('quota_stopped') and audit.get('quota_day') == dt.date.today().isoformat():
        print('Quota reached earlier in this run; checkpoint preserved.',flush=True)
        return
    if validation:
        candidates=[r for n,r in listing.items() if n in existing]
        random.Random(2022).shuffle(candidates)
        targets=candidates[:160]
    else:
        targets=sorted((r for n,r in listing.items() if n not in existing and n not in added and n not in audit['errors']),key=lambda r:r['rcept_no'])[:limit]
    print(json.dumps({'phase':'validation' if validation else 'documents','targets':len(targets),'already_added':len(added)}),flush=True)
    checked, mismatches, failures = 0, [], []
    def checkpoint():
        save_rows(OUT/'details.csv',added,DETAIL_FIELDS)
        audit['quota_stopped']=STOP.is_set()
        audit['quota_day']=dt.date.today().isoformat() if STOP.is_set() else None
        audit['remaining']=len(set(listing)-set(existing)-set(added))
        audit['added']=len(added)
        audit_path.write_text(json.dumps(audit,ensure_ascii=False),encoding='utf-8')
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures=[executor.submit(fetch_document,r) for r in targets]
        for future in as_completed(futures):
            row,result,error,digest=future.result()
            checked+=1
            no=row['rcept_no']
            if validation:
                if error:
                    failures.append({'rcept_no':no,'error':error})
                else:
                    old=existing[no]
                    for field in ('stkrt','stkrt_irds','stkqy','stkqy_irds'):
                        try: a=float(result[field].replace(',','')); b=float(old[field].replace(',',''))
                        except (ValueError,KeyError): continue
                        tolerance=.021 if 'rt' in field else .01
                        if abs(a-b)>tolerance:
                            mismatches.append({'rcept_no':no,'field':field,'parsed':result[field],'api':old[field]})
            elif result:
                added[no]=result
                audit['success'][no]={'source':'document.xml','sha256':digest,'parser_version':1}
            elif error not in ('quota_stopped','api_020'):
                audit['errors'][no]=error
            if checked%200==0 and not validation:
                checkpoint()
                print(json.dumps({'processed':checked,'added':len(added),'errors':len(audit['errors']),'remaining':audit['remaining'],'quota':STOP.is_set()}),flush=True)
    if validation:
        report={'checked':checked,'failures':failures,'mismatches':mismatches}
        (OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
        if mismatches or len(failures)>len(targets)*.1:
            raise RuntimeError('Document/API validation requires review')
    else:
        checkpoint()
        print(json.dumps({'added':len(added),'errors':len(audit['errors']),'remaining':audit['remaining'],'quota':audit['quota_stopped']}),flush=True)

def request(session, endpoint, **params):
    for attempt in range(4):
        try:
            response = session.get('https://opendart.fss.or.kr/api/'+endpoint,
                params={'crtfc_key': os.environ['DART_API_KEY'], **params}, timeout=60)
            if response.status_code == 200: return response
        except requests.RequestException: pass
        time.sleep(2 ** attempt)
    raise RuntimeError('DART request failed: '+endpoint)

def write_csv(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/'holdings.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows.values(),key=lambda r:(r['rcept_dt'],r['rcept_no']),reverse=True))

def scan(start):
    OUT.mkdir(parents=True,exist_ok=True)
    rows={r['rcept_no']:dict(r,corp_code=r.get('corp_code','')) for r in csv.DictReader((ROOT/'data/_dart/대량보유DB.csv').open(encoding='utf-8-sig'))}
    session=requests.Session()
    today=dt.date.today()
    for market,label in [('Y','코스피'),('K','코스닥')]:
        begin=dt.datetime.strptime(start,'%Y%m%d').date()
        while begin<=today:
            end=min(begin+dt.timedelta(days=88),today)
            page=1
            while True:
                d=request(session,'list.json',bgn_de=begin.strftime('%Y%m%d'),end_de=end.strftime('%Y%m%d'),corp_cls=market,pblntf_detail_ty='D001',page_count=100,page_no=page).json()
                if d.get('status')=='013': break
                if d.get('status')!='000': raise RuntimeError('DART status '+str(d.get('status')))
                for item in d.get('list',[]):
                    if '대량보유' not in item.get('report_nm',''): continue
                    row={key:(item.get(key) or '').strip() for key in FIELDS}
                    row['corp_cls']=label
                    rows[row['rcept_no']]=row
                if page>=int(d.get('total_page',1)): break
                page+=1
                time.sleep(.12)
            write_csv(rows)
            print(json.dumps({'market':label,'through':end.isoformat(),'rows':len(rows)},ensure_ascii=False),flush=True)
            begin=end+dt.timedelta(days=1)
    detail={r['rcept_no'] for r in csv.DictReader((ROOT/'data/_dart/대량보유상세DB.csv').open(encoding='utf-8-sig'))}
    missing=[r for r in rows.values() if r['rcept_no'] not in detail]
    summary={'rows':len(rows),'missing_detail':len(missing),'oldest':min(r['rcept_dt'] for r in rows.values()),'by_year':{str(y):sum(r['rcept_dt'].startswith(str(y)) for r in rows.values()) for y in range(2022,today.year+1)}}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    samples=[]
    for year in ['2022','2023','2024']:
        for kind in ['일반','약식']:
            candidates=sorted((r for r in missing if r['rcept_dt'].startswith(year) and kind in r['report_nm']),key=lambda r:r['rcept_no'])
            for row in candidates[:2]:
                raw=request(session,'document.xml',rcept_no=row['rcept_no']).content
                with zipfile.ZipFile(io.BytesIO(raw)) as z: xml=z.read(z.namelist()[0])
                (OUT/(row['rcept_no']+'.xml')).write_bytes(xml)
                samples.append(row)
    (OUT/'samples.json').write_text(json.dumps(samples,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--from',dest='start',default='20220101')
    ap.add_argument('--mode',choices=['scan','validate','details'],default='scan')
    ap.add_argument('--limit',type=int,default=4000)
    args=ap.parse_args()
    if args.mode=='scan': scan(args.start)
    else: details(args.limit,validation=args.mode=='validate')

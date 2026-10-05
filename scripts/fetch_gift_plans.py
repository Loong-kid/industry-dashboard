"""Collect DART trading-plan stock gifts with correction/withdrawal receipt lineage."""
import argparse
import datetime as dt
import io
import json
import os
from pathlib import Path
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from fetch_gifts import date_chunks, CLS
from gift_plan_document import parse_plan_document, PARSER_VERSION

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT/'data/_dart/gift_plan_reports.json'
START = '20240724'
KST = dt.timezone(dt.timedelta(hours=9))
LIST_FIELDS = ('rcept_no','rcept_dt','corp_name','corp_code','stock_code','corp_cls','report_nm','flr_nm','rm')


def today():
    return dt.datetime.now(KST).date()


def load_db(path=DB_PATH):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version':1,'reports':{}}


def save_db(db, path=DB_PATH):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(db,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    tmp.replace(path)


def request(session, url, **params):
    for attempt in range(3):
        try:
            response=session.get(url,params=params,timeout=40)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 2:
                # Request exceptions can include crtfc_key in their URL. Never log them.
                raise RuntimeError('DART transport failed') from None
            time.sleep(2**attempt)


def scan_reports(api_key,bgn,end):
    def scan_chunk(market,begin,finish):
        out=[]
        with requests.Session() as session:
            page=1
            while True:
                data=request(session,'https://opendart.fss.or.kr/api/list.json',crtfc_key=api_key,
                             bgn_de=begin,end_de=finish,pblntf_detail_ty='D005',corp_cls=market,
                             page_count=100,page_no=page).json()
                status=data.get('status')
                if status == '013': break
                if status != '000': raise RuntimeError('DART list status '+str(status))
                for row in data.get('list',[]):
                    title=(row.get('report_nm') or '').replace(' ','')
                    if '거래계획' in title and '특정증권' in title:
                        out.append({key:(row.get(key) or '').strip() for key in LIST_FIELDS})
                if page >= int(data.get('total_page',1)): break
                page+=1
                time.sleep(.08)
        return out
    result={}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(scan_chunk,market,b,e) for market in CLS for b,e in date_chunks(bgn,end)]
        for future in as_completed(futures):
            for row in future.result(): result[row['rcept_no']]=row
    return list(result.values())


def fetch_report(api_key,listing):
    no=listing['rcept_no']
    with requests.Session() as session:
        response=request(session,'https://opendart.fss.or.kr/api/document.xml',crtfc_key=api_key,rcept_no=no)
        if not zipfile.is_zipfile(io.BytesIO(response.content)):
            # Parse status only; API error bodies contain no usable filing.
            import re
            match=re.search(rb'<status>(\d+)</status>',response.content)
            raise RuntimeError('DART document status '+(match.group(1).decode() if match else 'invalid'))
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names=[n for n in archive.namelist() if n.lower().endswith('.xml')]
            if len(names)!=1: raise RuntimeError('unexpected document archive')
            raw=archive.read(names[0])
        withdrawn='철회' in listing['report_nm'] or '철' in listing.get('rm','')
        parsed={'events':[],'parser_version':PARSER_VERSION} if '철회' in listing['report_nm'] else parse_plan_document(raw,listing)
        family=[{'rcept_no':no,'report_nm':listing['report_nm'],'withdrawn':withdrawn}]
        # Official rm='정' means a subsequent correction, rm='철' means withdrawn.
        # Refresh the full inexpensive D005 listing daily, so cached older receipts
        # get their current flags even when their document itself is unchanged.
        family_status='api_flags'
        return dict(listing=listing,**parsed,family=family,family_status=family_status,withdrawn=withdrawn,
                    status='ok',checked=today().isoformat())


def run(api_key,bgn,end,reports=None):
    db=load_db()
    rows=reports if reports is not None else scan_reports(api_key,bgn,end)
    records=db['reports']
    for row in rows:
        no=row['rcept_no']
        records.setdefault(no,{'listing':{key:row.get(key,'') for key in LIST_FIELDS},'status':'pending'})
        records[no]['listing'].update({key:row.get(key,'') for key in LIST_FIELDS})
    # An entire successful listing scan advances this checkpoint, including days without gifts.
    # Failed documents remain pending/error and are retried independent of the next date range.
    db['scanned_from']=min(db.get('scanned_from',bgn),bgn)
    db['scanned_through']=max(db.get('scanned_through',end),end)
    targets=[r['listing'] for r in records.values() if r.get('status')!='ok' or r.get('parser_version')!=PARSER_VERSION or r.get('family_status')=='error']
    print(f'Trading plans: {len(rows)} listed; {len(targets)} documents to validate',flush=True)
    save_db(db)
    errors=0
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(fetch_report,api_key,row):row for row in targets}
        for index,future in enumerate(as_completed(futures),1):
            row=futures[future]; no=row['rcept_no']
            try:
                result=future.result()
                # Preserve previously verified DART receipt lineage where available.
                if len(records[no].get('family',[]))>1: result['family']=records[no]['family']
                records[no]=result
            except Exception as exc:
                errors+=1
                records[no]['status']='error'
                records[no]['error_type']=type(exc).__name__
                print(f'Receipt {no}: {type(exc).__name__}; preserved for retry',flush=True)
            if index%100==0:
                save_db(db)
                print(f'Validated {index}/{len(targets)} documents',flush=True)
    db['fetched']=today().isoformat()
    save_db(db)
    family_errors=sum(r.get('family_status')=='error' for r in records.values())
    gifts=sum(len(r.get('events',[])) for r in records.values() if r.get('status')=='ok')
    print(f'Collected {gifts} stock-gift plan rows; {errors} failures',flush=True)
    if errors or family_errors: raise RuntimeError('Some trading plan documents or revision links require retry/review')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from',dest='bgn')
    parser.add_argument('--to',dest='end')
    parser.add_argument('--days',type=int)
    args=parser.parse_args()
    api_key=os.environ.get('DART_API_KEY','')
    if not api_key: raise SystemExit('DART_API_KEY is required')
    db=load_db()
    end=args.end or today().strftime('%Y%m%d')
    if args.bgn: bgn=args.bgn
    elif args.days: bgn=(today()-dt.timedelta(days=args.days)).strftime('%Y%m%d')
    else: bgn=START  # Refresh API correction/withdrawal flags for all cached receipts.
    if not START<=bgn<=end<=today().strftime('%Y%m%d'): raise SystemExit('Invalid scan date range')
    run(api_key,bgn,end)


if __name__=='__main__': main()

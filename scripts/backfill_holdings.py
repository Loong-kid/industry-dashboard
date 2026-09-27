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

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'work' / 'holdings-backfill'
FIELDS = ['rcept_no','rcept_dt','corp_cls','corp_name','stock_code','report_nm','flr_nm','corp_code']

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
    args=ap.parse_args()
    scan(args.start)

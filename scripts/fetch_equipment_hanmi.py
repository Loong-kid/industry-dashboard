"""Refresh Hanmi's public consolidated accounts without exporting API credentials."""
import calendar,json,os,time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'manual/equipment_hanmi.json'


def number(value):
    text=str(value or '').replace(',','').strip()
    return float(text) if text and text not in ('-','—') else None


def collect(full=False):
    key=os.environ.get('DART_API_KEY')
    if not key:raise RuntimeError('DART_API_KEY is not configured')
    import datetime
    asof=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
    prior=json.loads(PATH.read_text(encoding='utf8')) if PATH.exists() else dict(reports=[])
    reports={(r['year'],r['quarter']):r for r in prior['reports']}
    first=2015 if full or not reports else int(asof[:4])-1
    session=requests.Session();failures=0
    for year in range(int(asof[:4]),first-1,-1):
        for q,code in [(1,'11013'),(2,'11012'),(3,'11014'),(4,'11011')]:
            end=f'{year}-{q*3:02d}-{calendar.monthrange(year,q*3)[1]}'
            if end>asof:continue
            try:
                response=session.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json',params=dict(crtfc_key=key,corp_code='00161383',bsns_year=year,reprt_code=code,fs_div='CFS'),timeout=20)
                response.raise_for_status();payload=response.json()
                if payload.get('status')=='013':continue
                if payload.get('status')!='000':raise ValueError('DART report unavailable')
                items=payload['list']
                if any(r.get('corp_code','00161383')!='00161383' for r in items):raise ValueError('Entity mismatch')
                chosen={}
                for metric,tags,names,divisions in [
                    ('revenue',('ifrs-full_Revenue','ifrs-full_RevenueFromContractsWithCustomers'),('매출액','수익(매출액)','매출'),('IS','CIS')),
                    ('profit',('dart_OperatingIncomeLoss','ifrs-full_ProfitLossFromOperatingActivities'),('영업이익','영업이익(손실)'),('IS','CIS')),
                    ('capex',('ifrs-full_PurchaseOfPropertyPlantAndEquipment','ifrs-full_PaymentsToAcquirePropertyPlantAndEquipment'),('유형자산의취득','유형자산취득'),('CF',))]:
                    candidates=[r for r in items if r.get('sj_div') in divisions and (r.get('account_id') in tags or r.get('account_nm','').replace(' ','') in names)]
                    if not candidates:continue
                    r=min(candidates,key=lambda r:0 if r.get('account_id') in tags else 1)
                    amount=number(r.get('thstrm_amount'));ytd=amount if q in (1,4) or metric=='capex' else number(r.get('thstrm_add_amount'))
                    acc=r['rcept_no']
                    if f'{acc[:4]}-{acc[4:6]}-{acc[6:8]}'>asof:continue
                    chosen[metric]=dict(value=amount/1e6 if amount is not None else None,ytd=ytd/1e6 if ytd is not None else None,
                        url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+acc,filed=f'{acc[:4]}-{acc[4:6]}-{acc[6:8]}',tag=r['account_id'])
                if not all(m in chosen for m in ('revenue','profit')):raise ValueError('Missing consolidated income statement')
                reports[year,q]=dict(year=year,quarter=q,date=end,fields=chosen)
                failures=0
            except Exception:
                failures+=1
                if failures>=3:raise RuntimeError('Repeated DART source failures; existing snapshot unchanged') from None
            time.sleep(.15)
        print('Hanmi',year,'reports',sum(y==year for y,q in reports),flush=True)
    result=dict(checked=asof,source='OpenDART · 한미반도체 연결',corp_code='00161383',reports=[r for _,r in sorted(reports.items())])
    PATH.parent.mkdir(parents=True,exist_ok=True);PATH.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--full-history',action='store_true')
    collect(parser.parse_args().full_history)

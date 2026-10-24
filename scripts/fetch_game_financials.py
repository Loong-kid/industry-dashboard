"""Free SEC/OpenDART company accounts and reviewed public game revenue reports.

Amounts in company output are original currency millions. Never annual / 4.
Failures retain successful company snapshots, with a separate check status.
"""
import argparse
import calendar
import io
import json
import os
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/games'
MANUAL = ROOT / 'manual/games'
UA = 'industry-dashboard personal research wkorotk@gmail.com'
COMPANIES = [
    dict(id='ea', name='Electronic Arts', currency='USD', cik=712515, fiscal_start=4, brands='EA Sports · The Sims · Apex Legends'),
    dict(id='take_two', name='Take-Two', currency='USD', cik=946581, fiscal_start=4, brands='Rockstar · 2K · Zynga'),
    dict(id='roblox', name='Roblox', currency='USD', cik=1315098, fiscal_start=1, brands='Roblox 플랫폼 · 개별 경험 개발자 수익과 다름'),
    dict(id='playtika', name='Playtika', currency='USD', cik=1828016, fiscal_start=1, brands='Slotomania · Bingo Blitz'),
    dict(id='netease', name='NetEase', currency='CNY', cik=1110646, fiscal_start=1, brands='게임·교육·음악 등 연결 전체'),
    dict(id='gravity', name='Gravity', currency='KRW', cik=1313310, fiscal_start=1, brands='Ragnarok IP · SEC 구조화 공시가 최신 IR보다 늦을 수 있음'),
    dict(id='krafton', name='크래프톤', currency='KRW', stock='259960', fiscal_start=1, brands='PUBG · inZOI · Subnautica'),
    dict(id='netmarble', name='넷마블', currency='KRW', stock='251270', fiscal_start=1, brands='Seven Knights · Solo Leveling · Kabam'),
    dict(id='ncsoft', name='NC', currency='KRW', stock='036570', fiscal_start=1, brands='Lineage · AION · Guild Wars'),
    dict(id='pearl_abyss', name='펄어비스', currency='KRW', stock='263750', fiscal_start=1, brands='Black Desert · EVE'),
    dict(id='com2us', name='컴투스', currency='KRW', stock='078340', fiscal_start=1, brands='Summoners War · 야구 게임'),
]
SEC_TAGS = {
    'revenue': [('us-gaap', 'RevenueFromContractWithCustomerExcludingAssessedTax'), ('us-gaap', 'Revenues'), ('us-gaap', 'SalesRevenueNet'), ('ifrs-full', 'RevenueFromContractsWithCustomers'), ('ifrs-full', 'Revenue')],
    'operating_profit': [('us-gaap', 'OperatingIncomeLoss'), ('ifrs-full', 'ProfitLossFromOperatingActivities')],
    'net_income': [('us-gaap', 'ProfitLoss'), ('us-gaap', 'NetIncomeLoss'), ('ifrs-full', 'ProfitLoss')],
}


def load(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def length(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def sec_ref(item, cik):
    accn = item['accn']
    return {k: item[k] for k in ('start', 'end', 'filed', 'tag')} | {
        'url': f'https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace("-", "")}/{accn}-index.html'}


def parse_sec(doc, company, asof):
    if int(doc['cik']) != company['cik']:
        raise ValueError('SEC entity mismatch')
    selected = {}
    for metric, tags in SEC_TAGS.items():
        values = {}
        for priority, (namespace, tag) in enumerate(tags):
            for r in doc['facts'].get(namespace, {}).get(tag, {}).get('units', {}).get(company['currency'], []):
                if not r.get('start') or r['end'] > asof or r['filed'] > asof or r.get('form') not in ('10-K', '10-K/A', '10-Q', '10-Q/A', '20-F', '20-F/A', '40-F'):
                    continue
                key = r['start'], r['end']
                rank = r['filed'], -priority, r['accn']
                if key not in values or rank > values[key]['rank']:
                    values[key] = dict(r, tag=f'{namespace}:{tag}', rank=rank)
        selected[metric] = values
    # Actual annual anchors plus an unfinished fiscal year. March year ends are
    # labelled by the end year, independent of the filing's misleading fy field.
    anchors = {(s, e) for vals in selected.values() for s, e in vals if 350 <= length(s, e) <= 380}
    for vals in selected.values():
        for s, e in vals:
            if s[5:] == f'{company["fiscal_start"]:02d}-01':
                end_year = int(s[:4]) + (company['fiscal_start'] != 1)
                m = (company['fiscal_start'] - 2) % 12 + 1
                anchors.add((s, f'{end_year}-{m:02d}-{calendar.monthrange(end_year,m)[1]}'))
    rows = {}
    for start, end in sorted(anchors):
        if end < '2020-01-01':
            continue
        fy = int(end[:4])
        for metric, vals in selected.items():
            annual = vals.get((start, end))
            if annual:
                row = rows.setdefault(('annual', end), dict(kind='annual', date=end, start=start, period=f'FY{fy}', refs={}))
                row[metric] = annual['val'] / 1e6
                row['refs'][metric] = dict(sec_ref(annual, company['cik']), calculation='reported annual')
            # Direct 3-month statements are preferred. Derive only from two
            # cumulative statements anchored to the exact same fiscal start.
            ends = sorted({e for s, e in vals if start <= s <= e <= min(end, asof) and (75 <= length(s,e) <= 105 or s == start)})
            for e in ends:
                elapsed = length(start, e)
                q = round(elapsed / 91.25)
                if not 1 <= q <= 4 or abs(elapsed - q * 91.25) > 15:
                    continue
                direct = [v for (s, ee), v in vals.items() if ee == e and s >= start and 75 <= length(s,e) <= 105]
                if direct:
                    fact = max(direct, key=lambda v:v['rank'])
                    value, sources, quarter_start = fact['val'], [sec_ref(fact, company['cik'])], fact['start']
                elif (start, e) in vals and q > 1:
                    previous = [v for (s, ee), v in vals.items() if s == start and ee < e and abs(length(start,ee) - (q-1)*91.25) <= 15]
                    if not previous:
                        continue
                    prev = max(previous, key=lambda v:v['end'])
                    fact = vals[start, e]
                    # Different accounting taxonomies must not be subtracted.
                    if fact['tag'].split(':')[0] != prev['tag'].split(':')[0]:
                        continue
                    value = fact['val'] - prev['val']
                    sources = [sec_ref(fact,company['cik']), sec_ref(prev,company['cik'])]
                    quarter_start = date.fromordinal(date.fromisoformat(prev['end']).toordinal()+1).isoformat()
                else:
                    continue
                row = rows.setdefault(('quarter',e), dict(kind='quarter', date=e, start=quarter_start, period=f'FY{fy} Q{q}', refs={}))
                row[metric] = value / 1e6
                row['refs'][metric] = dict(sources[0], calculation='reported quarter' if len(sources)==1 else 'YTD minus previous YTD', components=sources)
    result = sorted(rows.values(), key=lambda r:(r['date'],r['kind']))
    if not any(r.get('revenue',0)>0 for r in result):
        raise ValueError('No valid revenue facts')
    return result


DART_IDS = {'revenue': ('ifrs-full_Revenue','ifrs_Revenue','ifrs-full_RevenueFromContractsWithCustomers'),
            'operating_profit': ('dart_OperatingIncomeLoss','ifrs-full_ProfitLossFromOperatingActivities'),
            'net_income': ('ifrs-full_ProfitLoss','ifrs_ProfitLoss')}
DART_NAMES = {'revenue': ('매출액','영업수익','수익(매출액)','매출'), 'operating_profit': ('영업이익','영업이익(손실)','영업손익'),
              'net_income': ('당기순이익','당기순이익(손실)','분기순이익','분기순이익(손실)','반기순이익','반기순이익(손실)','당기순손익')}


def dart_number(value):
    s = str(value or '').strip().replace(',','').replace(' ','')
    if not s or s in ('-', '—'):
        return None
    return float('-'+s[1:-1] if s.startswith('(') and s.endswith(')') else s)


def parse_dart(items, year, q):
    result, cumulative, refs = {}, {}, {}
    for metric, tags in DART_IDS.items():
        candidates = [r for r in items if r.get('sj_div') in ('IS','CIS') and r.get('currency') == 'KRW' and
                      (r.get('account_id') in tags or r.get('account_nm','').replace(' ','') in DART_NAMES[metric])]
        if not candidates:
            continue
        r = min(candidates, key=lambda r:(0 if r.get('account_id') in tags else 1, 0 if r['sj_div']=='IS' else 1))
        direct = dart_number(r.get('thstrm_amount'))
        ytd = direct if q in (1,4) else dart_number(r.get('thstrm_add_amount'))
        if direct is not None:
            result[metric] = direct / 1e6
        if ytd is not None:
            cumulative[metric] = ytd / 1e6
        acc = r['rcept_no']
        refs[metric] = dict(url=f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={acc}', filed=f'{acc[:4]}-{acc[4:6]}-{acc[6:8]}', tag=r['account_id'], calculation='reported annual' if q==4 else 'reported quarter')
    if 'revenue' not in result:
        raise ValueError('Missing consolidated KRW income statement')
    end = f'{year}-{q*3:02d}-{calendar.monthrange(year,q*3)[1]}'
    return dict(kind='annual' if q==4 else 'quarter', start=f'{year}-{1 if q==4 else (q-1)*3+1:02d}-01', date=end,
                period=f'FY{year}'+('' if q==4 else f' Q{q}'), refs=refs, **result), cumulative


def dart_company(session, key, corp, company, asof, prior, full=False):
    rows = {(r['kind'],r['date']):r for r in prior}
    failures = []
    # Bootstrap history once; routine refresh revisits two fiscal years.
    first = 2020 if full or not any(r.get('source')=='OpenDART' for r in prior) else int(asof[:4])-1
    consecutive_failures=0
    for year in range(int(asof[:4]), first-1, -1):
        year_rows = {}
        for q, code in [(1,'11013'),(2,'11012'),(3,'11014'),(4,'11011')]:
            end = f'{year}-{q*3:02d}-{calendar.monthrange(year,q*3)[1]}'
            if end > asof:
                continue
            try:
                response = session.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json', params={
                    'crtfc_key':key,'corp_code':corp,'bsns_year':year,'reprt_code':code,'fs_div':'CFS'}, timeout=30)
                response.raise_for_status()
                doc=response.json()
                if doc.get('status')=='013':
                    consecutive_failures=0
                    continue
                if doc.get('status')!='000':
                    raise ValueError('OpenDART status '+str(doc.get('status')))
                row, ytd = parse_dart(doc['list'],year,q)
                if any(ref['filed'] > asof for ref in row['refs'].values()):
                    continue
                row['source']='OpenDART'
                consecutive_failures=0
                year_rows[q]=(row,ytd)
                rows[row['kind'],end]=row
            except Exception as exc:
                # URLs can contain the secret: never print exception text.
                failures.append(f'{year} Q{q}: {type(exc).__name__}')
                consecutive_failures+=1
                if consecutive_failures>=3:
                    return sorted(rows.values(),key=lambda r:(r['date'],r['kind'])),failures
        if 4 in year_rows and 3 in year_rows:
            annual,_=year_rows[4]; nine,cumulative=year_rows[3]
            q4=dict(kind='quarter',start=f'{year}-10-01',date=f'{year}-12-31',period=f'FY{year} Q4',source='OpenDART',refs={})
            for metric in DART_IDS:
                if metric in annual and metric in cumulative:
                    q4[metric]=annual[metric]-cumulative[metric]
                    q4['refs'][metric]=dict(annual['refs'][metric],calculation='annual minus nine months',components=[annual['refs'][metric],nine['refs'][metric]])
            if 'revenue' in q4:
                rows['quarter',q4['date']]=q4
    return sorted(rows.values(),key=lambda r:(r['date'],r['kind'])), failures


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sec-cache', type=Path, help='Use already downloaded original SEC responses')
    parser.add_argument('--full-history', action='store_true')
    args=parser.parse_args()
    today=datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    previous=load(OUT/'companies.json', {'companies':[]})
    manual=load(MANUAL/'company-financials.json', {'companies':[]})
    old={c['id']:c for c in previous['companies']}
    seeds={c['id']:c for c in manual['companies']}
    session=requests.Session();session.headers['User-Agent']=UA
    key=os.environ.get('DART_API_KEY')
    corp_codes={}
    if key:
        try:
            r=session.get('https://opendart.fss.or.kr/api/corpCode.xml', params={'crtfc_key':key},timeout=45);r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
                xml=ET.fromstring(archive.read('CORPCODE.xml'))
            corp_codes={c.findtext('stock_code','').strip():c.findtext('corp_code') for c in xml.findall('list')}
        except Exception as exc:
            print('OpenDART company index: '+type(exc).__name__,flush=True)
    def collect_company(spec):
        company_session=requests.Session();company_session.headers['User-Agent']=UA
        cid=spec['id'];prior=old.get(cid,{});seed=seeds.get(cid,{})
        company={k:v for k,v in spec.items() if k not in ('rows','checked','status')}
        existing={(r['kind'],r['date']):r for r in prior.get('rows',[])}
        for row in seed.get('rows',[]):
            key_row=row['kind'],row['date']
            # A newly reviewed manual IR may revise earlier manual values;
            # retain the more precise automated OpenDART accounts when present.
            if existing.get(key_row,{}).get('source')!='OpenDART':
                existing[key_row]=row
        rows=list(existing.values());status='reviewed public IR · manual updates';fetched=max(filter(None,[prior.get('fetched'),seed.get('reviewed')]),default=None)
        try:
            if spec.get('cik'):
                if args.sec_cache:
                    doc=load(args.sec_cache/f'{cid}-facts.json', {})
                else:
                    r=company_session.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',timeout=45);r.raise_for_status();doc=r.json()
                rows=parse_sec(doc,spec,today);status='ok';fetched=today
            elif spec.get('stock'):
                if not key or spec['stock'] not in corp_codes:
                    status='OpenDART key/index unavailable · previous observations retained'
                else:
                    before=rows
                    rows,failures=dart_company(company_session,key,corp_codes[spec['stock']],spec,today,rows,args.full_history)
                    status='ok' if not failures else '; '.join(failures)
                    has_accounts=any(r.get('source')=='OpenDART' for r in rows)
                    if not has_accounts:
                        status='No consolidated OpenDART observations · previous observations retained'
                    if has_accounts and (rows!=before or not failures):
                        fetched=today
        except Exception as exc:
            status=type(exc).__name__+' · previous observations retained'
        company.update(rows=sorted(rows,key=lambda r:(r['date'],r['kind'])),checked=today,fetched=fetched,status=status)
        company_session.close()
        print(f'{cid}: {len(rows)} periods · {status}',flush=True)
        return company
    specs=COMPANIES+[c for c in manual['companies'] if c['id'] not in {s['id'] for s in COMPANIES}]
    # Each worker owns its HTTP session. At most three company requests run at
    # once; SEC has only six requests in total, below its 10 requests/sec limit.
    with ThreadPoolExecutor(max_workers=3) as pool:
        companies=list(pool.map(collect_company,specs))
    save(OUT/'companies.json',dict(checked=today,unit='original currency millions',companies=companies))
    # Reviewed report dates are never rewritten by the scheduled collection.
    revenue=load(MANUAL/'revenue-reports.json', {})
    if not revenue.get('reports'):
        raise ValueError('No reviewed public revenue reports')
    save(OUT/'revenue.json',revenue)


if __name__=='__main__':
    main()

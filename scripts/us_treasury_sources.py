"""Official Treasury sources. Units: USD billions, yields percent, allocations percent.

Keep announcement vintages; a CUSIP alone cannot identify a reopening auction.
"""
import datetime as dt
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache/us-treasury'
HOME = 'https://home.treasury.gov'
QRA = HOME + '/policy-issues/financing-the-government/quarterly-refunding'
API = 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/'
AUCTIONS = 'https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/'
YIELDS = HOME + '/resource-center/data-chart-center/interest-rates/pages/xml'
MONTHS = {name.lower(): i for i, name in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'], 1)}
TERMS = ['2-Year','3-Year','5-Year','7-Year','10-Year','20-Year','30-Year']


def today():
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def number(v):
    if v is None or str(v).strip().lower() in ('', 'null', 'n/a', 'n.a.', '-', '—'):
        return None
    return float(str(v).replace(',', '').replace('$', '').strip())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


class Client:
    def get(self, url, *, params=None, refresh=False):
        key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
        path = CACHE / (key + '.txt')
        if path.exists() and not refresh:
            return path.read_text(encoding='utf-8')
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=(15, 55), headers={'User-Agent':'IndustryDashboard/1.0 (public Treasury data)'})
                r.raise_for_status()
                text = r.content.decode('utf-8-sig')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
                return text
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)

    def api(self, endpoint, params):
        result = []
        page = 1
        while True:
            p = dict(params, **{'page[number]':page, 'page[size]':1000})
            doc = json.loads(self.get(API + endpoint, params=p, refresh=True))
            result.extend(doc['data'])
            if page >= int(doc['meta']['total-pages']):
                return result
            page += 1


def news_body(html):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('.field--name-field-news-body')
    if body is None:
        raise ValueError('Treasury news body is missing')
    date_node = soup.select_one('time')
    raw = (date_node.get('datetime') or date_node.get_text(' ', strip=True)) if date_node else ''
    try:
        published = dt.datetime.fromisoformat(raw.replace('Z','+00:00')).date().isoformat()
    except ValueError:
        match = re.search(r'(' + '|'.join(x.title() for x in MONTHS) + r')\s+(\d{1,2}),\s*(20\d{2})', soup.get_text(' ', strip=True))
        if not match:
            raise ValueError('Treasury publication date missing')
        published = f'{match[3]}-{MONTHS[match[1].lower()]:02d}-{int(match[2]):02d}'
    return published, body


def money(amount, unit):
    return float(amount.replace(',', '')) * (1000 if unit.lower() == 'trillion' else 1)


def parse_borrowing(html, url):
    published, body = news_body(html)
    rows = []
    text = re.sub(r'\s+', ' ', body.get_text(' ', strip=True)).replace('\u2011','-')
    # Stop each match at the next quarter's lead sentence so numbers in revision
    # explanations cannot be mistaken for the next quarter's forecast.
    pattern = r'During the\s+([A-Za-z]+)\s*[-–—]\s*([A-Za-z]+)\s+(20\d{2})\s+quarter,\s*(.*?)(?=During the|Additional financing|###|$)'
    for m in re.finditer(pattern, text, re.I):
        month = MONTHS.get(m[1].lower())
        if month not in (1,4,7,10):
            continue
        tail = m[4]
        amount = re.search(r'(?:borrow(?:ed)?|issue(?:d)?|pay\s+down|paid\s+down|payed\s+down)\s+\$?([\d,.]+)\s+(billion|trillion)', tail, re.I)
        if not amount:
            continue
        actual = bool(re.search(r'^Treasury\s+(?:borrowed|issued|paid\s+down|payed\s+down)', tail, re.I))
        val = money(amount[1], amount[2]) * (-1 if re.search(r'pa(?:y|id|yed)\s+down', amount[0], re.I) else 1)
        cash = re.search(r'(?:cash balance of|cash balance with|cash balance at)\s+\$?([\d,.]+)\s+(billion|trillion)', tail, re.I)
        rows.append(dict(quarter=f'{m[3]} Q{(month-1)//3+1}', status='actual' if actual else 'estimate', borrowing=val,
                         cash=money(cash[1],cash[2]) if cash else None))
    if len(rows) < 2:
        raise ValueError('Borrowing estimates could not be parsed: ' + url)
    return dict(publication_date=published, source_url=url, rows=rows)


def parse_statement(html, url):
    published, body = news_body(html)
    monthly = []
    for table in body.select('table'):
        grid = [[re.sub(r'\s+', ' ', c.get_text(' ', strip=True)).strip() for c in tr.find_all(['th','td'], recursive=False)] for tr in table.select('tr')]
        head = next((r for r in grid if any(re.fullmatch(r'10\s*[-–]?\s*[Yy]ear', c) for c in r)), None)
        if not head:
            continue
        cols = {i:re.sub(r'\s*[-–]\s*', '-', c) for i,c in enumerate(head) if re.fullmatch(r'(?:2|3|5|7|10|20|30)\s*[-–]\s*[Yy]ear|FRN', c)}
        for cells in grid:
            if not cells:
                continue
            match = re.fullmatch(r'([A-Za-z]{3,9})\s*[-– /]\s*(\d{2}|20\d{2})', cells[0].strip())
            if not match:
                continue
            month = next((i for name,i in MONTHS.items() if name.startswith(match[1].lower()[:3])), None)
            year = int(match[2]);year = year + 2000 if year < 100 else year
            if month is None:
                continue
            ym = f'{year}-{month:02d}'
            for index,term in cols.items():
                if index >= len(cells):
                    raise ValueError('Incomplete QRA maturity table')
                raw = re.sub(r'[^\d.,-]', '', cells[index])
                value = number(raw)
                if value is not None:
                    monthly.append(dict(month=ym, term=term, amount=value, status='plan' if ym >= published[:7] else 'reported_actual'))
    # Older statements may have no structured maturity table. Preserve the link
    # and publication date instead of inventing a flat issuance path.
    return dict(publication_date=published, source_url=url, monthly=monthly)


def normalize_auction(row, updated=False):
    if row.get('original_security_term') not in TERMS or row.get('security_type') not in ('Note','Bond'):
        return None
    if row.get('inflation_protected' if updated else 'inflation_index_security') != 'No' or row.get('floating_rate') not in ('No',None,'null',''):
        return None
    date = (row.get('comp_auction_close_date') if updated else row.get('auction_date'))
    if not date or date == 'null':
        return None
    get = lambda key: number(row.get(key))
    if updated:
        awards = [get(k) for k in ['dir_bid_comp_par_awarded','indir_bid_comp_par_awarded','prim_deal_comp_par_awarded']]
    else:
        awards = [get(k) for k in ['direct_bidder_accepted','indirect_bidder_accepted','primary_dealer_accepted']]
    denom = sum(awards) if all(v is not None for v in awards) else None
    high = get('high_yield');btc = get('bid_to_cover_ratio')
    completed = high is not None and btc is not None
    # A regular 2Y auction can be converted into an additional issue of an old
    # 5Y/7Y CUSIP with identical coupon/maturity. Use the explicitly announced
    # auction term in this case; retain original term for normal 10Y reopenings.
    term=row.get('security_term') if row.get('security_term') in TERMS else row['original_security_term']
    amount=get('offering_amt')
    return dict(date=date[:10], issue_date=row.get('issue_date'), cusip=row['cusip'], term=term,
                original_term=row['original_security_term'],security_term=row.get('security_term'),
                small_value=amount is not None and amount<1e9,
                reopening=row.get('reopening')=='Yes', amount=get('offering_amt') / 1e9 if get('offering_amt') is not None else None,
                high_yield=high if completed else None, bid_to_cover=btc if completed else None,
                direct=round(awards[0]/denom*100,6) if completed and denom else None,
                indirect=round(awards[1]/denom*100,6) if completed and denom else None,
                dealer=round(awards[2]/denom*100,6) if completed and denom else None,
                completed=completed, source_url=AUCTIONS, schema='updated' if updated else 'legacy')


def merge_auctions(legacy, updated):
    merged = {}
    for rows, newer in [(legacy,False),(updated,True)]:
        for raw in rows:
            row = normalize_auction(raw, newer)
            if not row:
                continue
            key = (row['cusip'], row['date'])
            if key in merged and merged[key]['completed'] and not row['completed']:
                continue
            merged[key] = row
    return sorted(merged.values(), key=lambda r:(r['date'],r['term'],r['cusip']))


def parse_yields(xml):
    root = ET.fromstring(xml)
    rows = []
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        props = entry.find('.//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties')
        if props is None:
            continue
        values = {n.tag.rsplit('}',1)[-1]:n.text for n in props}
        if not values.get('NEW_DATE'):
            continue
        row = dict(date=values['NEW_DATE'][:10])
        for term in [2,5,10,30]:
            row[str(term)] = number(values.get(f'BC_{term}YEAR'))
        row['spread'] = round((row['10']-row['2'])*100,6) if row['10'] is not None and row['2'] is not None else None
        rows.append(row)
    if not rows:
        raise ValueError('Empty Treasury yield XML feed')
    return rows


def parse_calendar(xml):
    root=ET.fromstring(xml);rows=[]
    for node in root.iter():
        if node.tag.rsplit('}',1)[-1]!='AuctionCalendarDate':
            continue
        v={n.tag.rsplit('}',1)[-1]:n.text for n in node}
        if v.get('SecurityType') not in ('NOTE','BOND') or v.get('TIPS')!='N' or v.get('FloatingRate')!='N':
            continue
        term=v.get('SecurityTermWeekYear')
        if term not in TERMS or not v.get('AuctionDate'):
            continue
        dt.date.fromisoformat(v['AuctionDate'])
        rows.append(dict(date=v['AuctionDate'],announcement_date=v.get('AnnouncementDate'),
                         issue_date=v.get('SettlementDate'),term=term,reopening=v.get('ReOpeningIndicator')=='Y'))
    if not rows:
        raise ValueError('Empty tentative nominal auction calendar')
    return sorted(rows,key=lambda r:(r['date'],r['term']))

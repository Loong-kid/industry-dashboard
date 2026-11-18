"""Original US-GAAP statements missing from SEC companyfacts (USD millions).

Only consolidated income/cash-flow tables are accepted. Adjusted summaries,
segment tables, IFRS reports, and net CAPEX reconciliations are excluded.
"""
import datetime as dt
import re
from bs4 import BeautifulSoup

MONTHS = {name.lower(): i for i, name in enumerate(
    ['January','February','March','April','May','June','July','August','September','October','November','December'], 1)}
MONTH = '('+'|'.join(MONTHS)+r'|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
LABELS = {
    'revenue': re.compile(r'^(net revenues|revenue|revenues)$', re.I),
    'profit': re.compile(r'^(operating (income|loss)( \((income|loss)\))?|income \(loss\) from operations)$', re.I),
    'capex': re.compile(r'^(payments? for purchase of tangible assets|capital expenditures on property, plant and equipment|purchases? of property, plant and equipment)$', re.I),
}


def clean(value):
    return ' '.join(value.replace('\xa0', ' ').split())


def numbers(value):
    # Accounting parentheses can occupy separate HTML cells.
    value=re.sub('−(?=\\d)','-',value)
    return [(-1 if a else 1)*float(b.replace(',', '')) if b else 0.0
            for a,b,z in re.findall(r'(\()?\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*\)?|([—–−-])(?=\s|$)', value)]


def first_end(header):
    text = header.lower()
    date = re.search(MONTH+r'\.?\s+(\d{1,2})\s*,?\s*(20\d{2})', text, re.I)
    if date:
        month, day, year = date.groups()
    else:
        short = re.search(MONTH+r'\.?\s+(\d{1,2})\s*,?', text, re.I)
        year_match = re.search(r'\b20\d{2}\b', text)
        if not short or not year_match:
            raise ValueError('Statement period end missing')
        month, day = short.groups(); year = year_match.group()
    month = next(v for k,v in MONTHS.items() if k.startswith(month[:3].lower()))
    return dt.date(int(year), month, int(day))


def statement_facts(html, url, filed, accn, form='6-K'):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for table in soup.find_all('table'):
        text = clean(table.get_text(' ', strip=True))
        lower = text.lower()
        if len(text)>24000 or '% of net revenues' in lower or '% variation' in lower:
            continue
        income = ('cost of sales' in lower or 'cost of revenue' in lower) and 'gross profit' in lower
        cash = 'cash flows from operating activities' in lower and 'investing activities' in lower
        if not income and not cash:
            continue
        rows = table.find_all('tr')
        header=[]; found=[]
        for row in rows:
            cells=[clean(c.get_text(' ',strip=True)) for c in row.find_all(['td','th'], recursive=False)]
            nonempty=[c for c in cells if c and c!='$']
            if not nonempty:continue
            match=next((metric for metric,pattern in LABELS.items() if pattern.fullmatch(nonempty[0])),None)
            if match and (cash == (match=='capex')):
                values=numbers(' '.join(nonempty[1:]))
                if values:found.append((match, nonempty[0], values[0]))
            if not found:header.append(' '.join(cells))
        if not found or income and {f[0] for f in found}!={'revenue','profit'}:continue
        heading=clean(' '.join(header))
        # A detailed statement has an explicit duration; summaries are rejected.
        duration=re.search(r'\b(three|six|nine|twelve)\s+months?\s+ended',heading,re.I)
        annual=bool(re.search(r'\byears?\s+ended',heading,re.I))
        if not duration and not annual:continue
        end=first_end(heading)
        months={'three':3,'six':6,'nine':9,'twelve':12}[duration[1].lower()] if duration else 12
        quarter=round((end-dt.date(end.year,1,1)).days/91.25)
        if months==12:
            start=dt.date(end.year,1,1)
        elif months==3 and quarter>1:
            # Provisional start; combined_payload replaces it with the day
            # after the previous actual quarter end when that is available.
            start=dt.date(end.year, (quarter-1)*3+1, 1)
        else:start=dt.date(end.year,1,1)
        for metric,label,value in found:
            if end.year<2014:continue
            result.append(dict(metric=metric,val=abs(value)*1e6 if metric=='capex' else value*1e6,
                start=start.isoformat(),end=end.isoformat(),filed=filed,accn=accn,form=form,
                source_url=url,source_tag='consolidated statement: '+label))
    # Multiple copies of the same statement are allowed only if they agree.
    unique={}
    for f in result:
        key=f['metric'],f['start'],f['end']
        if key in unique and unique[key]['val']!=f['val']:
            raise ValueError('Conflicting consolidated statements: '+str(key))
        unique[key]=f
    return list(unique.values())

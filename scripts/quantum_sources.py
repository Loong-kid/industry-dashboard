"""Calendar-period quantum accounts from SEC facts and reviewed issuer tables.

Amounts are native-currency millions. SPAC shells, convenience translations,
pro forma statements and guidance are not operating-company history.
"""
import calendar
import datetime as dt
import math
import re

from bs4 import BeautifulSoup


METRICS = {'revenue': '매출', 'profit': '영업이익', 'netincome': '순이익'}


def period(start, end, currency):
    begin, finish = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if begin.year != finish.year or begin.day != 1 or finish.day != calendar.monthrange(finish.year, finish.month)[1]:
        raise ValueError('non-calendar reporting period')
    months = finish.month - begin.month + 1
    if months == 3 and begin.month in (1, 4, 7, 10):
        kind, q = 'quarter', (finish.month + 2) // 3
        label = f'FY{finish.year} Q{q}'
    elif months == 6 and begin.month in (1, 7):
        kind, q = 'half', None
        label = f'FY{finish.year} H{1 if begin.month == 1 else 2}'
    elif months == 12 and begin.month == 1:
        kind, q, label = 'annual', None, f'FY{finish.year}'
    else:
        raise ValueError('unsupported reporting period')
    return dict(kind=kind, year=finish.year, quarter=q, start=start, date=end,
                currency=currency, period=label, refs={})


def sec_rows(payload, meta, asof):
    if int(payload['cik']) != meta['cik']:
        raise ValueError('SEC issuer mismatch')
    selected = {}
    for metric, tags in meta['tags'].items():
        values = {}
        for priority, tag in enumerate(tags):
            for f in payload['facts'].get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', []):
                if (not f.get('start') or not meta.get('minimum_start', '2020-01-01') <= f['start'] <= f['end'] <= asof
                        or not meta.get('filing_floor', '2000-01-01') <= f['filed'] <= asof
                        or f.get('form') not in ('10-Q', '10-Q/A', '10-K', '10-K/A')
                        or not isinstance(f['val'], (int, float)) or not math.isfinite(f['val'])):
                    continue
                # Use reviewed consolidated tags only. No substring matching to
                # RPOs, segment sales, acquired entities or SPAC interest income.
                rank = (f['filed'], -priority, f['accn'])
                key = f['start'], f['end']
                if key not in values or rank > values[key]['rank']:
                    values[key] = dict(f, tag='us-gaap:' + tag, rank=rank)
        selected[metric] = values
    rows = {}
    for metric, values in selected.items():
        def ref(f):
            acc = f['accn']
            return dict(url=f'https://www.sec.gov/Archives/edgar/data/{meta["cik"]}/{acc.replace("-", "")}/{acc}-index.html',
                        filed=f['filed'], start=f['start'], end=f['end'], tag=f['tag'])
        for (start, end), fact in sorted(values.items()):
            try:
                row = period(start, end, 'USD')
            except ValueError:
                row = None
            if row and row['kind'] in ('quarter', 'half', 'annual'):
                key = row['kind'], end
                row = rows.setdefault(key, row)
                row[metric] = fact['val'] / 1e6
                row['refs'][metric] = dict(ref(fact), calculation='reported ' + row['kind'])
        # Derive only a single quarter from adjacent YTDs of the same year,
        # currency and reviewed tag. Prefer a prior YTD in the same filing.
        for (start, end), fact in sorted(values.items()):
            year = int(end[:4]); month = int(end[5:7])
            if start != f'{year}-01-01' or month not in (6, 9, 12):
                continue
            quarter_start = f'{year}-{month-2:02d}-01'
            try:
                row = period(quarter_start, end, 'USD')
            except ValueError:
                continue
            if metric in rows.get(('quarter', end), {}):
                continue
            prior_end = (dt.date.fromisoformat(quarter_start) - dt.timedelta(days=1)).isoformat()
            previous = values.get((start, prior_end))
            if not previous or previous['tag'] != fact['tag'] or previous['filed'] > fact['filed']:
                continue
            value = (fact['val'] - previous['val']) / 1e6
            if metric == 'revenue' and value < 0:
                continue
            row = rows.setdefault(('quarter', end), row)
            row[metric] = value
            row['refs'][metric] = dict(ref(fact), calculation='same fiscal-year YTD minus prior YTD',
                                      components=[ref(fact), ref(previous)])
    # A financial history cannot be made out of a former SPAC's expenses alone.
    return sorted((r for r in rows.values() if r.get('revenue') is not None), key=lambda r: (r['date'], r['kind']))


def numeric_cells(text):
    tokens = re.findall(r'\(\s*\d[\d,]*(?:\.\d+)?\s*\)|[-−]?\d[\d,]*(?:\.\d+)?|[—–-]', text)
    return [0.0 if t in ('—', '–', '-') else -float(t.strip('() ').replace(',', '')) if '(' in t
            else float(t.replace(',', '').replace('−', '-')) for t in tokens]


def reviewed_table(raw, source, asof):
    """Explicit table/column mapping, checked against header and source rows.

    Unknown layouts fail closed, retaining the last successful publication.
    Keeping the mapping public makes initial/manual extraction reproducible.
    """
    if source['filed'] > asof:
        return []
    soup = BeautifulSoup(raw, 'html.parser')
    tables = soup.find_all('table')
    table = tables[source['table']]
    text = table.get_text(' ', strip=True)
    for token in source['guards']:
        if token not in text:
            raise ValueError('reviewed table header changed: ' + token)
    rows = {}
    for metric, label in source['labels'].items():
        candidates = []
        for tr in table.find_all('tr'):
            tx = tr.get_text(' ', strip=True).replace('\xa0', ' ')
            if not tx.startswith(label):
                continue
            remainder = tx[len(label):].lstrip()
            if remainder and (remainder[0].isalpha() or remainder[0] == '—' and metric != 'revenue'):
                continue
            values = numeric_cells(remainder)
            n = source['numeric_columns']
            if len(values) < n:
                continue
            candidates.append(values[-n:])  # leading note numbers are not values
        if not candidates or any(v != candidates[0] for v in candidates):
            raise ValueError('missing or ambiguous statement row: ' + label)
        for col in source['columns']:
            row = period(col['start'], col['end'], col['currency'])
            row = rows.setdefault((row['kind'], row['date']), row)
            value = candidates[0][col['index']] * source['scale_to_millions']
            if metric == 'revenue' and value < 0:
                raise ValueError('negative revenue')
            row[metric] = value
            row['refs'][metric] = dict(url=source['url'], filed=source['filed'], start=row['start'], end=row['date'],
                                      tag=label, location=source['location'], calculation='reported ' + row['kind'])
    return list(rows.values())


def merge_rows(*groups):
    result = {}
    for group in groups:
        for fresh in group:
            key = fresh['kind'], fresh['date']
            row = result.setdefault(key, dict(fresh, refs=dict(fresh['refs'])))
            if row['currency'] != fresh['currency'] or row['start'] != fresh['start']:
                raise ValueError('incompatible period/currency')
            for metric in METRICS:
                if fresh.get(metric) is not None:
                    row[metric] = fresh[metric]
                    row['refs'][metric] = fresh['refs'][metric]
    return sorted(result.values(), key=lambda r: (r['date'], r['kind']))


def derive_first_quarters(rows):
    # Same statement's H1 minus Q2; never split a half or annual into equal parts.
    updates = []
    index = {(r['kind'], r['date']): r for r in rows}
    for half in rows:
        if half['kind'] != 'half' or not half['date'].endswith('06-30'):
            continue
        second = index.get(('quarter', half['date']))
        if not second:
            continue
        first = period(half['start'], half['date'][:4] + '-03-31', half['currency'])
        for metric in METRICS:
            if half.get(metric) is None or second.get(metric) is None:
                continue
            a, b = half['refs'][metric], second['refs'][metric]
            if a['url'] != b['url'] or a['filed'] != b['filed']:
                continue
            existing = index.get(('quarter', first['date']), {}).get('refs', {}).get(metric)
            if existing and existing['filed'] > a['filed']:
                continue
            first[metric] = half[metric] - second[metric]
            first['refs'][metric] = dict(a, calculation='same fiscal-year H1 minus Q2', components=[a, b])
        if first['refs']:
            updates.append(first)
    return merge_rows(rows, updates)


def holdings(raw, asof):
    soup = BeautifulSoup(raw, 'html.parser')
    match = re.search(r'Data as of\s+(\d{2}/\d{2}/\d{4})', soup.get_text(' ', strip=True))
    if not match:
        raise ValueError('holdings date missing')
    date = dt.datetime.strptime(match[1], '%m/%d/%Y').date().isoformat()
    if date > asof:
        raise ValueError('future holdings snapshot')
    output = []
    for tr in soup.select('table tr'):
        cells = [td.get_text(' ', strip=True) for td in tr.select('td')]
        if len(cells) != 5 or not cells[3].endswith('%'):
            continue
        ticker, name, cusip, weight, shares = cells
        output.append(dict(ticker=ticker, name=name, cusip=cusip, weight=float(weight.rstrip('%')),
                           kind='derivative' if '-TRS-' in ticker else 'cash' if ticker in ('Cash&Other', 'FGXXX', 'USD', 'EUR', 'TWD') else 'equity'))
    if len(output) < 5 or len({r['ticker'] for r in output}) != len(output):
        raise ValueError('incomplete/duplicate holdings')
    return dict(asof=date, positions=output)

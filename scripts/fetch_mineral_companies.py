"""Six mineral-exposed companies: exchange closes, consolidated earnings and
actual operating volumes. Public SEC/issuer sources; no estimates or guidance.
Each validated card cohort preserves its previous publication on failure.
"""
import argparse
import calendar
import datetime as dt
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import fitz
import requests
from bs4 import BeautifulSoup

from fetch_mineral_prices import korea_today
from fetch_mineral_supply import atomic_json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/commodities'
CACHE = ROOT / 'data/_mineral_companies/observations.json'
SEC_UA = {'User-Agent': 'industry-dashboard (personal research) wkorotk@gmail.com'}
WEB_UA = {'User-Agent': 'Mozilla/5.0'}
QUARTERS = {'First Quarter': 1, 'Second Quarter': 2, 'Third Quarter': 3, 'Fourth Quarter': 4}
COMPANIES = {
    'fcx': {'ticker': 'FCX', 'cik': 831259, 'name': '프리포트 맥모란', 'mineral': '구리',
            'ir': 'https://investors.fcx.com', 'currency': 'USD',
            'volumes': {'copper': '구리 생산량 · 연결 회수가능량'}, 'volume_unit': '백만 lb',
            'volume_note': '연결 광산의 회수가능 구리 생산량입니다. FCX 귀속 지분량으로 환산하지 않았습니다.'},
    'scco': {'ticker': 'SCCO', 'cik': 1001838, 'name': '서던코퍼', 'mineral': '구리',
             'ir': 'https://southerncoppercorp.com/eng/', 'currency': 'USD',
             'volumes': {'copper': '구리 광산 생산량'}, 'volume_unit': '백만 lb',
             'volume_note': 'Mined 자체 광산 생산량입니다. 외부 정광 처리분·제련량·정련량·판매량을 더하지 않습니다.'},
    'alb': {'ticker': 'ALB', 'cik': 915913, 'name': '알버말', 'mineral': '리튬',
            'ir': 'https://investors.albemarle.com', 'currency': 'USD',
            'volumes': {'lce_sales': '리튬 판매량 · LCE'}, 'volume_unit': '천 톤 LCE',
            'volume_note': 'Energy Storage 리튬염·스포듀민 판매량을 탄산리튬환산(LCE)으로 집계합니다. 생산량이 아니며 금속 Li 중량과 다릅니다.'},
    'mp': {'ticker': 'MP', 'cik': 1801368, 'name': 'MP Materials', 'mineral': '희토류',
           'ir': 'https://investors.mpmaterials.com', 'currency': 'USD',
           'volumes': {'reo': 'REO 정광 생산량', 'ndpr': '분리 NdPr 생산량'}, 'volume_unit': '톤',
           'volume_note': 'REO는 정광에 포함된 희토류 산화물량, NdPr는 분리 제품량입니다. 두 시리즈를 합산하거나 Nd·Pr 개별 생산량으로 나누지 않습니다.'},
    'ccj': {'ticker': 'CCJ', 'cik': 1009001, 'name': 'Cameco', 'mineral': '우라늄',
            'ir': 'https://www.cameco.com/invest/financial-information/quarterly-reports', 'currency': 'CAD',
            'volumes': {'uranium': 'U₃O₈ 생산량 · 회사 지분'}, 'volume_unit': '백만 lb U₃O₈',
            'volume_note': '우라늄 부문 회사 지분 기준 실제 생산량입니다. Inkai 지분 물량은 매입으로 회계 처리되어 이 생산량에 더하지 않습니다. 인도량·연료 kgU와 다릅니다.'},
    'aa': {'ticker': 'AA', 'cik': 1675149, 'name': 'Alcoa', 'mineral': '알루미늄',
           'ir': 'https://investors.alcoa.com', 'currency': 'USD',
           'volumes': {'aluminum': '알루미늄 생산량', 'alumina': '알루미나 생산량'}, 'volume_unit': '천 톤',
           'volume_note': 'Aluminum/Alumina 부문 공표 생산량입니다. 제품이 달라 두 시리즈를 합산하지 않으며 출하량·보크사이트 생산량과 구분합니다.'},
}


def numeric(raw, *, signed=True):
    if isinstance(raw, bool) or raw is None:
        raise ValueError('Missing or boolean observation')
    value = str(raw).strip().replace(',', '').replace(' ', '').replace('\u00a0', '')
    if value in ('—', '–', '-'):
        value = '0'
    if value.startswith('(') and value.endswith(')'):
        value = '-' + value[1:-1]
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError(f'Invalid observation: {raw!r}')
    result = float(value)
    if not math.isfinite(result) or (not signed and result < 0):
        raise ValueError('Invalid signed/finite observation')
    return int(result) if result.is_integer() else result


def quarter_end(year, quarter):
    month = quarter * 3
    return dt.date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def request(url, params=None, *, sec=False, raw_dir=None, refresh=True):
    if not url.startswith('https://'):
        raise ValueError('Source must use HTTPS')
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    file = raw_dir / key if raw_dir else None
    if file and file.exists() and not refresh:
        return file.read_bytes()
    for attempt in range(3):
        try:
            result = requests.get(url, params=params, headers=SEC_UA if sec else WEB_UA, timeout=45)
            result.raise_for_status()
            content = result.content
            if file:
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(content)
            return content
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def source_text(content):
    if content.startswith(b'%PDF'):
        with fitz.open(stream=content, filetype='pdf') as doc:
            return '\n'.join(page.get_text(sort=True) for page in doc)
    soup = BeautifulSoup(content, 'html.parser')
    return '\n'.join(' '.join(row.stripped_strings) for row in soup.select('tr')) + '\n' + soup.get_text(' ', strip=True)


def q4_reports(company_id, raw_dir=None, reuse=False):
    company = COMPANIES[company_id]
    url = company['ir'] + '/feed/FinancialReport.svc/GetFinancialReportList'
    params = {'LanguageId': 1, 'year': -1, 'pageSize': -1, 'reportTypes': '|'.join(QUARTERS)}
    rows = json.loads(request(url, params, raw_dir=raw_dir, refresh=not reuse))['GetFinancialReportListResult']
    result = []
    for row in rows:
        year, quarter = row['ReportYear'], QUARTERS.get(row['ReportSubType'])
        if not quarter or year < 2024 or quarter_end(year, quarter) > korea_today().isoformat():
            continue
        category = 'presentation' if company_id == 'alb' else 'news'
        docs = [doc for doc in row['Documents'] if doc['DocumentCategory'] == category]
        if not docs:
            continue
        if len(docs) != 1:
            raise ValueError('Ambiguous issuer financial document')
        doc = docs[0]
        result.append({'year': year, 'quarter': quarter, 'url': doc['DocumentPath'],
                       'version': str(doc['RevisionNumber']), 'period': quarter_end(year, quarter)})
    if not result:
        raise ValueError('Missing financial report catalogue')
    return result


def mp_reports(raw_dir=None, reuse=False):
    host = COMPANIES['mp']['ir']
    result = []
    for year in range(2024, korea_today().year + 1):
        params = {'LanguageId': 1, 'year': year, 'pageSize': -1, 'bodyType': 1, 'pressReleaseDateFilter': 3}
        rows = json.loads(request(host + '/feed/PressRelease.svc/GetPressReleaseList', params,
                                  raw_dir=raw_dir, refresh=not reuse))['GetPressReleaseListResult']
        for row in rows:
            match = re.fullmatch(r'MP Materials Reports (First|Second|Third|Fourth) Quarter (?:and Full Year )?(\d{4}) Results', row['Headline'])
            if not match:
                continue
            quarter, period_year = QUARTERS[match[1] + ' Quarter'], int(match[2])
            if period_year < 2024 or quarter_end(period_year, quarter) > korea_today().isoformat():
                continue
            result.append({'year': period_year, 'quarter': quarter, 'period': quarter_end(period_year, quarter),
                           'url': urljoin(host, row['LinkToDetailPage']), '_body': row['Body'], 'version': str(row.get('RevisionNumber', row['PressReleaseDate']))})
    if not result:
        raise ValueError('Missing MP actual results catalogue')
    return result


def scco_reports(raw_dir=None, reuse=False):
    company = COMPANIES['scco']
    url = f"https://data.sec.gov/submissions/CIK{company['cik']:010d}.json"
    payload = json.loads(request(url, sec=True, raw_dir=raw_dir, refresh=not reuse))
    if int(payload['cik']) != company['cik']:
        raise ValueError('SEC production issuer mismatch')
    recent = payload['filings']['recent']
    result = []
    for i, form in enumerate(recent['form']):
        period = recent['reportDate'][i]
        if form not in ('10-K', '10-Q') or period < '2024-01-01' or period > korea_today().isoformat():
            continue
        year, month = int(period[:4]), int(period[5:7])
        acc = recent['accessionNumber'][i]
        result.append({'year': year, 'quarter': month // 3, 'period': period,
                       'url': f"https://www.sec.gov/Archives/edgar/data/{company['cik']}/{acc.replace('-', '')}/{recent['primaryDocument'][i]}",
                       'version': acc, 'sec': True})
    if not result:
        raise ValueError('Missing SCCO production filings')
    return result


def ccj_reports(raw_dir=None, reuse=False):
    host = 'https://www.cameco.com'
    index = host + '/invest/financial-information/quarterly-reports'
    root = BeautifulSoup(request(index, raw_dir=raw_dir, refresh=not reuse), 'html.parser')
    years = {int(m[1]) for a in root.select('a[href]')
             if (m := re.fullmatch(r'/invest/financial-information/quarterly-reports/(\d{4})(?:/q[1-4])?', a['href'])) and int(m[1]) >= 2024}
    result = []
    for year in sorted(years):
        quarters = {int(m[1]) for a in root.select('a[href]')
                    if (m := re.fullmatch(rf'/invest/financial-information/quarterly-reports/{year}/q([1-4])', a['href']))}
        if year < korea_today().year or not quarters:
            page = BeautifulSoup(request(index + '/' + str(year), raw_dir=raw_dir, refresh=not reuse), 'html.parser')
            quarters |= {int(m[1]) for a in page.select('a[href]')
                        if (m := re.fullmatch(rf'/invest/financial-information/quarterly-reports/{year}/q([1-4])', a['href']))}
        for quarter in sorted(quarters):
            period = quarter_end(year, quarter)
            if period > korea_today().isoformat():
                continue
            address = index + f'/{year}/q{quarter}'
            quarterly = BeautifulSoup(request(address, raw_dir=raw_dir, refresh=not reuse), 'html.parser')
            links = {urljoin(host, a['href'].split('#')[0]) for a in quarterly.select('a[href]')
                     if 'pdf' in a['href'].lower() and re.search(r'financial (?:statements)|financials and notes', a.get_text(' ', strip=True), re.I)}
            if len(links) != 1:
                raise ValueError(f'Missing or ambiguous Cameco statements: {year} Q{quarter}')
            result.append({'year': year, 'quarter': quarter, 'period': period,
                           'url': links.pop(), 'version': address})
    if not result:
        raise ValueError('Missing Cameco quarterly reports')
    return result


def row_values(text, label, *, required=True):
    match = re.search(r'^[ \t]*' + label + r'[ \t]+([^\n]+)', text, re.I | re.M)
    if not match:
        if not required:
            return []
        raise ValueError('Missing actual operating row: ' + label)
    tokens = re.findall(r'\(?-?\d[\d,]*(?:\.\d+)?[ \t]*\)?|[—–]', match[1])
    return [numeric(token) for token in tokens]


def paired_points(year, quarter, values, key, source, *, annual=False):
    if len(values) < 2 or any(value < 0 for value in values[:2]):
        raise ValueError('Missing/negative actual production pair')
    kind = 'annual' if annual else 'quarter'
    return [{'kind': kind, 'date': quarter_end(y, 4 if annual else quarter), key: value, '_source': source}
            for y, value in zip((year, year - 1), values[:2])]


def parse_fcx(text, report):
    block = text.split('SUMMARY OPERATING DATA', 1)[1]
    block = block.split('Gold (', 1)[0]
    if 'millions of recoverable pounds' not in block or str(report['year']) not in block:
        raise ValueError('FCX production unit/year mismatch')
    values = row_values(block, r'Production[a-z]?')
    points = paired_points(report['year'], report['quarter'], values, 'copper', report)
    if report['quarter'] == 4:
        if len(values) != 4:
            raise ValueError('FCX Q4/annual production columns changed')
        points += paired_points(report['year'], 4, values[2:], 'copper', report, annual=True)
    return points


def parse_mp(text, report):
    points = []
    for key, label in [('reo', r'REO Production Volume\s*\(MTs\)'), ('ndpr', r'NdPr Production Volume\s*\(MTs\)')]:
        match = re.search(r'^[ \t]*' + label + r'[ \t]+([^\n]+)', text, re.I | re.M)
        if not match:
            if key == 'reo':
                raise ValueError('Missing MP REO production row')
            continue
        tokens = re.findall(r'N/A|\(?-?\d[\d,]*(?:\.\d+)?[ \t]*\)?|[—–]', match[1])
        if len(tokens) < 2:
            raise ValueError('MP production columns changed')
        for year, token in zip((report['year'], report['year'] - 1), tokens[:2]):
            value = None if token == 'N/A' else numeric(token, signed=False)
            points.append({'kind': 'quarter', 'date': quarter_end(year, report['quarter']), key: value, '_source': report})
    return points


def parse_alb(text, report):
    year, quarter = report['year'], report['quarter']
    flat = re.sub(r'\s+', ' ', text)
    pattern = rf'Q{quarter}(?:\s+{year})?\s+sales volumes?\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*k[tT]\s*LCE'
    match = re.search(pattern, flat, re.I)
    points = []
    if 'Energy Storage Quarterly Sales Metrics' in text:
        block = text.split('Energy Storage Quarterly Sales Metrics', 1)[1]
        header = re.search(r'^.*Q[1-4]\s+20\d{2}.*$', block, re.M)
        columns = re.findall(r'Q([1-4])\s+(20\d{2})', header[0]) if header else []
        values = row_values(block, r'Energy Storage Sales Volume[\d,]*', required=False)
        if not columns or len(values) != len(columns):
            raise ValueError('Albemarle sales metric columns changed')
        points = [{'kind': 'quarter', 'date': quarter_end(int(y), int(q)), 'lce_sales': value, '_source': report}
                  for (q, y), value in zip(columns, values)]
    elif match:
        points = [{'kind': 'quarter', 'date': report['period'], 'lce_sales': numeric(match[1], signed=False), '_source': report}]
    else:
        # Some earlier presentations disclose growth but no absolute volume.
        return [{'kind': 'quarter', 'date': report['period'], 'lce_sales': None, '_source': report}]
    annual = re.search(rf'FY\s*{year}\s+sales volumes?\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*k[tT]\s*LCE', flat, re.I)
    if annual:
        points.append({'kind': 'annual', 'date': quarter_end(year, 4), 'lce_sales': numeric(annual[1], signed=False), '_source': report})
    return points


def alcoa_period_columns(block):
    header = re.search(r'^.*\b[1-4]Q\d{2}\b.*$', block, re.M)
    if not header:
        raise ValueError('Alcoa operating period header missing')
    tokens = re.findall(r'([1-4])Q(\d{2})|\b(20\d{2})\b', header[0])
    periods = [('quarter', quarter_end(2000 + int(y), int(q))) if q else ('annual', f'{annual}-12-31')
               for q, y, annual in tokens]
    if len(periods) < 3 or len(set(periods)) != len(periods):
        raise ValueError('Alcoa ambiguous period columns')
    return periods


def parse_aa(text, report):
    block = text.split('Segment Information', 1)[1]
    periods = alcoa_period_columns(block)
    points = []
    for key, label in [('aluminum', r'Aluminum production\s*\(kmt\)'), ('alumina', r'Alumina production\s*\(kmt\)')]:
        values = row_values(block, label)
        if len(values) != len(periods):
            raise ValueError('Alcoa production/header column mismatch')
        for (kind, date), value in zip(periods, values):
            if value < 0:
                raise ValueError('Negative Alcoa production')
            points.append({'kind': kind, 'date': date, key: value, '_source': report})
    # This is a transparent reconstruction, not a reported OperatingIncomeLoss
    # subtotal or adjusted EBITDA. Includes restructuring and goodwill charges.
    income = row_values(block, r'Consolidated (?:income|loss|income\s*\(loss\)|\(loss\) income) before income taxes')
    interest = row_values(block, r'Interest expense')
    other = row_values(block, r'Other(?: income\s*\(expenses\)|\s*\(expenses\) income),\s*net')
    if not len(income) == len(interest) == len(other) == len(periods):
        raise ValueError('Alcoa financial/header column mismatch')
    for (kind, date), pretax, interest_reconciliation, other_income in zip(periods, income, interest, other):
        # Reconciliation expenses have minus signs; other income is positive.
        value = pretax - interest_reconciliation - other_income
        points.append({'kind': kind, 'date': date, 'profit': value, '_source': {
            **report, 'derivation': {'pretax': pretax, 'interest': -interest_reconciliation,
                                   'other_expense': -other_income}, 'label': '공식 손익 항목 재구성'}})
    return points


def parse_scco(content, report):
    soup = BeautifulSoup(content, 'html.parser')
    selected = []
    for table in soup.find_all('table'):
        text = ' '.join(table.stripped_strings).replace('\u200b', '')
        if 'Total mined copper' in text and ('in million pounds' in text or 'in millions of pounds' in text):
            selected.append(table)
    if len(selected) != 1:
        raise ValueError('SCCO mined copper table missing/ambiguous')
    text = '\n'.join(' '.join(row.stripped_strings).replace('\u200b', '').strip() for row in selected[0].select('tr'))
    values = row_values(text, r'Total mined copper')
    year, quarter = report['year'], report['quarter']
    if quarter == 4:
        return paired_points(year, 4, values, 'copper', report, annual=True)
    points = paired_points(year, quarter, values, 'copper', report)
    if quarter == 3:
        # Columns: current, prior, variance, %, then the matching YTD quartet.
        if len(values) != 8:
            raise ValueError('SCCO quarter/YTD columns changed')
        points += [{'kind': 'cumulative', 'date': quarter_end(y, 3), 'copper': value, '_source': report}
                   for y, value in zip((year, year - 1), values[4:6])]
    return points


def parse_ccj(text, report):
    values = row_values(text, r'Production volume\s*\(million lbs?\)')
    if report['quarter'] == 4:
        # Annual MD&A lists annual and Q4 tables separately, not six columns.
        points = paired_points(report['year'], 4, values, 'uranium', report, annual=True)
        quarter_block = text.split('Fourth quarter financial results by segment', 1)[1]
        quarter_values = row_values(quarter_block, r'Production volume\s*\(million lbs?\)')
        points += paired_points(report['year'], 4, quarter_values, 'uranium', report)
    else:
        points = paired_points(report['year'], report['quarter'], values, 'uranium', report)
    block = text.split('Consolidated statements of earnings', 1)[1]
    profits = row_values(block, r'Earnings from operations')
    if report['quarter'] != 4:
        if len(profits) != (2 if report['quarter'] == 1 else 4):
            raise ValueError('Cameco quarter/YTD financial columns changed')
        for year, value in zip((report['year'], report['year'] - 1), profits[:2]):
            points.append({'kind': 'quarter', 'date': quarter_end(year, report['quarter']), 'profit': value / 1000, '_source': report})
        if report['quarter'] == 3:
            for year, value in zip((report['year'], report['year'] - 1), profits[2:]):
                points.append({'kind': 'cumulative', 'date': quarter_end(year, 3), 'profit': value / 1000, '_source': report})
    return points


def sec_rows(payload, cik, namespace, tag, currency, today):
    if payload.get('cik') != cik:
        raise ValueError('SEC issuer identity mismatch')
    facts = payload['facts'][namespace][tag]
    rows = facts['units'][currency]
    result = {}
    for row in rows:
        if row.get('form') not in ('10-K', '10-K/A', '10-Q', '10-Q/A', '20-F', '20-F/A', '40-F', '40-F/A'):
            continue
        start, end, filed = row.get('start', ''), row['end'], row['filed']
        if not start or start < '2015-01-01' or end > today or filed > today:
            continue
        dt.date.fromisoformat(start); dt.date.fromisoformat(end); dt.date.fromisoformat(filed)
        if start > end or not re.fullmatch(r'\d{10}-\d{2}-\d{6}', row['accn']):
            raise ValueError('Invalid SEC period/accession')
        value = numeric(row['val'])
        key = (start, end)
        previous = result.get(key)
        if previous and previous['filed'] == filed and previous['accn'] == row['accn'] and previous['value'] != value:
            raise ValueError('Conflicting SEC consolidated fact')
        if previous is None or (filed, row['accn']) >= (previous['filed'], previous['accn']):
            result[key] = {'value': value, 'filed': filed, 'accn': row['accn'],
                           'url': f"https://www.sec.gov/Archives/edgar/data/{cik}/{row['accn'].replace('-', '')}/",
                           'label': row['form'], 'tag': namespace + ':' + tag, 'unit': currency}
    if not result:
        raise ValueError('No usable SEC earnings periods')
    return result


def earnings_periods(records, today):
    annual, quarters = {}, {}
    for (start, end), row in records.items():
        year = int(end[:4])
        if start == f'{year}-01-01' and end == f'{year}-12-31':
            annual[end] = row
        for quarter in range(1, 5):
            if end == quarter_end(year, quarter) and start == f'{year}-{quarter * 3 - 2:02d}-01':
                quarters[end] = row
    for end, year_row in annual.items():
        year = int(end[:4])
        nine = records.get((f'{year}-01-01', f'{year}-09-30'))
        if end not in quarters and nine:
            quarters[end] = {**year_row, 'value': year_row['value'] - nine['value'],
                             'label': 'Q4 = 연간 − 9개월', 'supporting_url': nine['url'],
                             'derivation': {'annual': year_row['value'], 'nine_months': nine['value']}}
    for date in [*annual, *quarters]:
        if date > today:
            raise ValueError('Future financial period')
    return quarters, annual


def price_series(payload, ticker, now):
    chart = payload.get('chart', {})
    if chart.get('error') or not chart.get('result'):
        raise ValueError('Missing Yahoo chart result')
    data = chart['result'][0]
    meta = data['meta']
    if meta.get('symbol') != ticker or meta.get('currency') != 'USD' or meta.get('instrumentType') != 'EQUITY':
        raise ValueError('Wrong stock identity/currency/type')
    timestamps, closes = data['timestamp'], data['indicators']['quote'][0]['close']
    if len(timestamps) != len(closes):
        raise ValueError('Price timestamp/value length mismatch')
    regular_end = meta['currentTradingPeriod']['regular']['end']
    current_day = dt.datetime.fromtimestamp(regular_end, dt.timezone.utc).date().isoformat()
    values = {}
    for timestamp, close in zip(timestamps, closes):
        date = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).date().isoformat()
        if timestamp > now or (date == current_day and now < regular_end) or close is None:
            continue
        value = numeric(close, signed=False)
        if value <= 0 or (date in values and values[date] != value):
            raise ValueError('Invalid/duplicate equity close')
        values[date] = round(value, 4)
    if len(values) < 100 or (dt.datetime.fromtimestamp(now, dt.timezone.utc).date() - dt.date.fromisoformat(max(values))).days > 10:
        raise ValueError('Insufficient or stale completed-session closes')
    return [[date, value] for date, value in sorted(values.items())]


def preserve_history(before, after):
    """A revised value is allowed; a previously published observation is not lost."""
    for name, points in before.get('series', {}).items():
        values = dict(after.get('series', {}).get(name, []))
        if any(date not in values or (value is not None and values[date] is None) for date, value in points):
            raise ValueError('Previously published company history disappeared')
    if before.get('updated', '') > after['updated']:
        raise ValueError('Company observation date regressed')
    for key, view in before.get('series_views', {}).items():
        if key not in after.get('series_views', {}):
            raise ValueError('Previously published company view disappeared')
        preserve_history({**view, 'updated': ''}, {**after['series_views'][key], 'updated': after['updated']})


def period_card(company_id, metric, quarters, annual, *, source_url, fetched, note, unit, series_names):
    company = COMPANIES[company_id]
    def references(rows):
        return {date: {**row['_source'], 'label': row['_source'].get('label') or
                       f"{company['ticker']} {row['_source'].get('year', date[:4])} Q{row['_source'].get('quarter', math.ceil(int(date[5:7]) / 3))} 실적발표"}
                for date, row in rows.items()}
    def view(rows, yearly=False):
        dates = sorted(rows)
        if not dates:
            raise ValueError('No company period observations')
        first, last = dates[0], dates[-1]
        if yearly:
            dates = [f'{year}-12-31' for year in range(int(first[:4]), int(last[:4]) + 1)]
        else:
            dates = [quarter_end(year, q) for year in range(int(first[:4]), int(last[:4]) + 1)
                     for q in range(1, 5) if first <= quarter_end(year, q) <= last]
        return {label: [[date, rows.get(date, {}).get(key, None)] for date in dates] for key, label in series_names.items()}
    quarterly = view(quarters)
    yearly = view(annual, True) if annual else None
    label = '연결 영업이익' if metric == 'profit' else ('리튬 판매량' if company_id == 'alb' else '생산량')
    if metric == 'profit' and company_id == 'aa':
        label = '영업이익 · 재구성'
    doc = {'id': f'comm_company_{company_id}_{metric}', 'name': f"{company['name']} ({company['ticker']}) · {label}",
           'unit': unit, 'frequency': 'quarterly', 'source': f"{company['ticker']} 공식 공시", 'source_url': source_url,
           'updated': max(quarters), 'fetched': fetched, 'span_gaps': False, 'quarter_labels': True,
           'quarterly_revenue_summary': metric != 'profit', 'quarterly_profit_summary': metric == 'profit',
           'company_kpi': True, 'change_mode': 'none', 'full_range': False, 'default_series': [next(iter(series_names.values()))],
           'table_limit': 1000, 'series': quarterly, 'note': note,
           'basis_details': [{'label': '기업·광물', 'value': f"NYSE {company['ticker']} · {company['mineral']}"},
                             {'label': '기준', 'value': note}],
           'period_sources': references(quarters),
           'default_view': 'quarter', 'series_views': {
               'quarter': {'label': '분기', 'frequency': 'quarterly', 'quarter_labels': True, 'year_labels': False,
                           'full_range': False, 'series': quarterly},
           }}
    if yearly:
        doc['series_views']['annual'] = {'label': '연간', 'frequency': 'yearly', 'quarter_labels': False,
                                        'quarterly_revenue_summary': False, 'year_labels': True, 'annual_axis': True,
                                        'quarterly_profit_summary': False,
                                        'full_range': True, 'series': yearly,
                                        'period_sources': references(annual)}
    return doc


def publish(doc):
    path = OUT / (doc['id'] + '.json')
    if path.exists():
        preserve_history(json.loads(path.read_text(encoding='utf-8')), doc)
    atomic_json(path, doc)
    print(f"Published {doc['id']} through {doc['updated']}", flush=True)


def earnings_doc(company_id, raw_dir=None, reuse=False):
    company = COMPANIES[company_id]
    today = korea_today().isoformat()
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{company['cik']:010d}.json"
    data = json.loads(request(url, sec=True, raw_dir=raw_dir, refresh=not reuse))
    rows = sec_rows(data, company['cik'], 'us-gaap', 'OperatingIncomeLoss', 'USD', today)
    quarters, annual = earnings_periods(rows, today)
    def display(points):
        return {date: {'profit': row['value'] / 1e6, '_source': row} for date, row in points.items()}
    return period_card(company_id, 'profit', display(quarters), display(annual), source_url=url, fetched=today,
                       unit='백만 USD', series_names={'profit': '연결 영업이익'},
                       note='US GAAP 연결 OperatingIncomeLoss입니다. 해당 광물만의 이익·EBITDA·순이익이 아닙니다. 단독 분기를 우선하며 Q4 미공표 시 같은 회계연도 연간−9개월로 계산합니다. 비교 공시의 과거 정정은 반영하며 사업 매각·회계 범위 변경에 유의하세요.')


def stock_doc(company_id, raw_dir=None, reuse=False):
    company = COMPANIES[company_id]
    now = int(time.time())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{company['ticker']}"
    params = {'period1': 1420070400, 'period2': now // 86400 * 86400 + 86400, 'interval': '1d'}
    payload = json.loads(request(url, params, raw_dir=raw_dir, refresh=not reuse))
    points = price_series(payload, company['ticker'], now)
    start = {'aa': '2016-11-01', 'mp': '2020-11-18'}.get(company_id, '2015-01-01')
    points = [point for point in points if point[0] >= start]
    return {'id': f'comm_company_{company_id}_price', 'name': f"{company['name']} ({company['ticker']}) · 주가",
            'unit': 'USD/주', 'frequency': 'daily', 'source': f"Yahoo Finance · NYSE {company['ticker']}",
            'source_url': f"https://finance.yahoo.com/quote/{company['ticker']}/history/",
            'updated': points[-1][0], 'fetched': korea_today().isoformat(), 'history_start': start, 'series': {company['ticker']: points},
            'note': 'NYSE 완료 거래일 종가입니다. 분할 반영·배당 미조정이며 배당 재투자 수익률이 아닙니다. 기업 전체 주가이므로 해당 광물 가격과 동일하게 움직이지 않습니다.',
            'basis_details': [{'label': '상장·통화', 'value': f"NYSE {company['ticker']} · USD/주"},
                              {'label': '조회 시작', 'value': start + (' · 독립 Alcoa Corporation 상장 이후' if company_id == 'aa' else ' · MP 합병 완료 후 MP 티커 거래 이후' if company_id == 'mp' else '')}]}


def operating_docs(company_id, cache, raw_dir=None, reuse=False):
    company = COMPANIES[company_id]
    if company_id in ('fcx', 'alb', 'aa'):
        reports = q4_reports(company_id, raw_dir, reuse)
    elif company_id == 'mp':
        reports = mp_reports(raw_dir, reuse)
    elif company_id == 'scco':
        reports = scco_reports(raw_dir, reuse)
    else:
        reports = ccj_reports(raw_dir, reuse)
    previous = cache.get(company_id, {})
    sources = {}
    if set(previous) - {report['url'] for report in reports}:
        raise ValueError('Previously published operating report disappeared from issuer catalogue')
    parsers = {'fcx': parse_fcx, 'alb': parse_alb, 'mp': parse_mp, 'aa': parse_aa, 'ccj': parse_ccj}
    for report in sorted(reports, key=lambda row: (row['period'], row['url'])):
        embedded_body = report.pop('_body', None)
        url = report['url']
        before = previous.get(url)
        refresh = report['year'] >= korea_today().year - 1 or not before or before['version'] != report['version']
        if refresh:
            content = embedded_body.encode('utf-8') if embedded_body else request(url, sec=report.get('sec', False), raw_dir=raw_dir, refresh=not reuse)
            points = parse_scco(content, report) if company_id == 'scco' else parsers[company_id](source_text(content), report)
            for point in points:
                if point['date'] > korea_today().isoformat():
                    raise ValueError('Future operating observation')
            sources[url] = {'version': report['version'], 'period': report['period'], 'points': points}
        else:
            sources[url] = before
        print(f"  {company['ticker']} actual report {report['year']} Q{report['quarter']}", flush=True)
    datasets = {'quarter': {}, 'annual': {}, 'cumulative': {}}
    for source in sorted(sources.values(), key=lambda row: row['period']):
        for point in source['points']:
            kind, date = point['kind'], point['date']
            target = datasets[kind].setdefault(date, {})
            for key, value in point.items():
                if key in ('kind', 'date'):
                    continue
                if value is not None or key not in target:
                    target[key] = value
    quarterly, annual, cumulative = (datasets[key] for key in ('quarter', 'annual', 'cumulative'))
    for date, row in list(annual.items()):
        year = date[:4]
        nine = cumulative.get(year + '-09-30', {})
        for key in [*company['volumes'], 'profit']:
            if row.get(key) is not None and nine.get(key) is not None and quarterly.get(date, {}).get(key) is None:
                quarterly.setdefault(date, {})[key] = round(row[key] - nine[key], 9)
                quarterly[date]['_source'] = {**row['_source'], 'label': 'Q4 = 연간 − 9개월', 'supporting_url': nine['_source']['url']}
    # MP reports REO and NdPr independently; annual totals require all four
    # actual quarters. An absent pre-start NdPr observation is never zero.
    for year in sorted({int(date[:4]) for date in quarterly}):
        end = quarter_end(year, 4)
        rows = [quarterly.get(quarter_end(year, q), {}) for q in range(1, 5)]
        for key in company['volumes']:
            if any(row.get(key) is None for row in rows):
                continue
            total = sum(row[key] for row in rows)
            observed = annual.get(end, {}).get(key)
            if observed is None:
                annual.setdefault(end, {})[key] = round(total, 9)
                annual[end]['_source'] = {**rows[-1]['_source'], 'label': '공개 4분기 합계',
                                        'supporting_urls': [row['_source']['url'] for row in rows]}
            else:
                tolerance = {'fcx': 2.5, 'scco': .25, 'alb': 2.5, 'mp': 3, 'ccj': .25, 'aa': 2.5}[company_id]
                if abs(total - observed) > tolerance:
                    raise ValueError(f'{company_id} {key} {year}: operating quarters disagree with annual total')
    active = {date: row for date, row in quarterly.items() if any(row.get(key) is not None for key in company['volumes'])}
    if not active or max(active) < max(report['period'] for report in reports):
        raise ValueError('Latest actual volume unavailable; retain previous publication')
    volume_note = company['volume_note'] + ' 연간은 공표값을 우선하고 없으면 공개된 4개 분기만 합산합니다. Q4 직접 공시가 없으면 같은 해 연간−9개월로 계산합니다. 미공개 분기는 공백으로 보존합니다.'
    production = period_card(company_id, 'production', quarterly, annual, source_url=company['ir'],
                             fetched=korea_today().isoformat(), note=volume_note,
                             unit=company['volume_unit'], series_names=company['volumes'])
    docs = [production]
    if company_id == 'aa':
        note = '연결 손익계산서에 영업이익 소계가 없어 세전이익 + 이자비용 + 기타비용(수익), net으로 재구성했습니다. 기타비용·수익 전부를 영업외로 분류한 계산값이며 GAAP 공표 소계·조정 EBITDA가 아닙니다. 구조조정·영업권 손상은 포함합니다. 회사 전체 손익이지 알루미늄만의 이익이 아닙니다.'
        docs.append(period_card(company_id, 'profit', quarterly, annual, source_url=company['ir'],
                                fetched=korea_today().isoformat(), note=note, unit='백만 USD', series_names={'profit': '영업이익 · 재구성'}))
    if company_id == 'ccj':
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{company['cik']:010d}.json"
        payload = json.loads(request(url, sec=True, raw_dir=raw_dir, refresh=not reuse))
        records = sec_rows(payload, company['cik'], 'ifrs-full', 'ProfitLossFromOperatingActivities', 'CAD', korea_today().isoformat())
        _, yearly = earnings_periods(records, korea_today().isoformat())
        financial_annual = {date: {'profit': row['value'] / 1e6, '_source': row} for date, row in yearly.items()}
        financial_quarters = {date: row.copy() for date, row in quarterly.items() if row.get('profit') is not None}
        for date, row in financial_annual.items():
            nine = cumulative.get(date[:4] + '-09-30')
            if nine and nine.get('profit') is not None and date not in financial_quarters:
                financial_quarters[date] = {'profit': round(row['profit'] - nine['profit'], 9), '_source': {
                    **row['_source'], 'label': 'Q4 = 연간 − 9개월', 'supporting_url': nine['_source']['url']}}
        note = 'IFRS 연결 Earnings from operations / ProfitLossFromOperatingActivities입니다. 단위는 백만 CAD이며 NYSE 주가 USD와 다릅니다. 세전이익·EBITDA·순이익을 대신 쓰지 않았습니다. Westinghouse 등 지분법 투자손익은 공시상 이 영업소계 아래에 포함되므로 회사 순이익과 차이가 납니다. Q4는 연간−9개월로 계산합니다.'
        docs.append(period_card(company_id, 'profit', financial_quarters, financial_annual, source_url=company['ir'],
                                fetched=korea_today().isoformat(), note=note, unit='백만 CAD', series_names={'profit': '연결 영업이익'}))
    # Check all outgoing docs before advancing the shared normalized cache.
    for doc in docs:
        path = OUT / (doc['id'] + '.json')
        if path.exists():
            preserve_history(json.loads(path.read_text(encoding='utf-8')), doc)
    for doc in docs:
        publish(doc)
    cache[company_id] = sources
    atomic_json(CACHE, {'companies': cache})


def collect(raw_dir=None, reuse=False, only=None):
    failures = []
    cache = json.loads(CACHE.read_text(encoding='utf-8'))['companies'] if CACHE.exists() else {}
    for company_id in only or COMPANIES:
        for metric, collector in [('price', stock_doc), ('profit', earnings_doc)]:
            if metric == 'profit' and company_id in ('aa', 'ccj'):
                continue
            try:
                publish(collector(company_id, raw_dir, reuse))
            except Exception as error:
                failures.append(f'{company_id} {metric}: {error}')
                print(f'Retained previous company {metric}: {company_id}: {error}', flush=True)
        try:
            operating_docs(company_id, cache, raw_dir, reuse)
        except Exception as error:
            failures.append(f'{company_id} actual operations: {error}')
            print(f'Retained previous company operations: {company_id}: {error}', flush=True)
    if failures:
        raise RuntimeError('\n'.join(failures))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-dir', type=Path, help='Optional local-only source scratch cache')
    parser.add_argument('--reuse-raw', action='store_true', help='Local parser development only; never scheduled')
    parser.add_argument('--only', nargs='+', choices=list(COMPANIES))
    args = parser.parse_args()
    collect(args.raw_dir, args.reuse_raw, args.only)

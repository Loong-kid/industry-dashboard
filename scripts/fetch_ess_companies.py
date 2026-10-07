"""Issuer-reported ESS metrics. Never equate shipments, revenue GWh and deployed GWh.

Historical reports are cached as normalized observations, not as source binaries.
New Tesla financial releases are discovered through its SEC catalogue;
Fluence through issuer RSS; Sungrow through CNINFO disclosures. A failed company
refresh preserves its last validated publication and does not block the others.
"""
import argparse
import calendar
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import pymupdf
import requests
from bs4 import BeautifulSoup

from fetch_mineral_prices import korea_today
from fetch_mineral_supply import atomic_json
from fetch_mineral_companies import preserve_history

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'data/_ess_companies/observations.json'
REGISTRY = ROOT / 'scripts/ess_company_sources.json'
OUT = ROOT / 'data/ess'
NAMES = {'tesla': '테슬라 에너지', 'sungrow': '선그로우', 'fluence': '플루언스 에너지'}
NUM = r'\(?\s*-?\d[\d,]*(?:\.\d+)?\s*\)?'
MONTHS = {name: i for i, name in enumerate(calendar.month_name) if name}


def number(raw):
    value = re.sub(r'\s+', '', str(raw)).replace(',', '')
    if value in ('—', '–', '-'):
        return 0.0
    if value.startswith('(') and value.endswith(')'):
        value = '-' + value[1:-1]
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('Invalid numeric observation: ' + repr(raw))
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite observation')
    return result


def quarter_end(year, quarter):
    month = quarter * 3
    return dt.date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def previous_quarter(date):
    year, month = int(date[:4]), int(date[5:7])
    return quarter_end(year - (month == 3), 4 if month == 3 else month // 3 - 1)


def download(url, raw_dir=None, reuse=False):
    if not url.startswith('https://'):
        raise ValueError('HTTPS sources only')
    path = raw_dir / hashlib.sha256(url.encode()).hexdigest() if raw_dir else None
    if reuse and path and path.exists():
        return path.read_bytes()
    headers = {'User-Agent': 'industry-dashboard (personal research) wkorotk@gmail.com'} if url.startswith('https://data.sec.gov/') else None
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    return response.content


def blocks(content):
    if content.startswith(b'%PDF'):
        with pymupdf.open(stream=content, filetype='pdf') as doc:
            return [(i + 1, re.sub(r'\s+', ' ', page.get_text(sort=True))) for i, page in enumerate(doc)]
    soup = BeautifulSoup(content, 'html.parser')
    return [(None, re.sub(r'\s+', ' ', table.get_text(' ', strip=True))) for table in soup.select('table')]


def point(metric, kind, date, value, source, **extra):
    if date > korea_today().isoformat():
        raise ValueError('Future observation')
    dt.date.fromisoformat(date)
    return {'metric': metric, 'kind': kind, 'date': date, 'value': round(number(value), 9),
            'source': source, **extra}


def source_ref(report, page=None, label=None):
    return {'url': report['url'], 'label': label or report.get('label', report['period']),
            **({'pdf_page': page} if page else {})}


def parse_tesla(content, report):
    result = []
    if report['parser'] == 'tesla_rpo':
        text_blocks = blocks(content)
        text = ' '.join(text for _, text in text_blocks)
        heading = re.search(r'Energy\s*Generation\s*and\s*Storage\s*Segment\s*Energy\s*Generation\s*and\s*Storage\s*Sales', text, re.I)
        if not heading:
            raise ValueError('Tesla energy RPO section missing')
        # Anchor on the energy revenue note, not automotive credits or total RPO.
        text = text[heading.end():]
        text = re.split(r'Energy\s*Generation\s*and\s*Storage\s*Leasing|Income\s*Taxes', text, maxsplit=1, flags=re.I)[0]
        match = re.search(r'contracts with an original expected length of more than one year was\s*\$([\d.]+)\s*(billion|million)', text, re.I)
        if not match:
            raise ValueError('Tesla long-duration energy performance obligations missing')
        return [point('rpo', 'quarter', report['period'], number(match[1]) * (1000 if match[2].lower() == 'billion' else 1), source_ref(report))]
    if report['parser'] == 'tesla_deployment':
        text = ' '.join(text for _, text in blocks(content)) if content.startswith(b'%PDF') else BeautifulSoup(content, 'html.parser').get_text(' ', strip=True)
        matches = re.findall(r'deployed\s+([\d.]+)\s*GWh\s+of\s+energy storage', text, re.I)
        if not matches or len(set(matches)) != 1:
            raise ValueError('Missing/ambiguous actual quarterly Tesla deployment')
        return [point('deployment', 'quarter', report['period'], matches[0], source_ref(report))]
    for page, text in blocks(content):
        quarters = re.findall(r'Q([1-4])[-\s]+(20\d{2})', text)
        # Five-quarter summary tables; older statements with annual columns are
        # deliberately excluded rather than assigning annual revenue to Q4.
        if len(quarters) < 5:
            continue
        dates = [quarter_end(int(year), int(q)) for q, year in quarters[:5]]
        if len(set(dates)) != 5 or dates != sorted(dates):
            continue
        patterns = [('revenue', r'Energy generation and storage(?: revenue)?\s+'),
                    ('deployment', r'(?:Energy )?Storage deployed\s*\((?:in )?(MWh|GWh)\)\s+')]
        for metric, pattern in patterns:
            match = re.search(pattern + r'((?:[\d,.]+\s+){4}[\d,.]+)', text, re.I)
            if not match:
                continue
            if metric == 'revenue' and not re.search(r'in millions', text, re.I):
                raise ValueError('Tesla revenue unit missing')
            values = re.findall(r'[\d,.]+', match[2] if metric == 'deployment' else match[1])
            scale = .001 if metric == 'deployment' and match[1].lower() == 'mwh' else 1
            for date, value in zip(dates, values):
                if date >= ('2019-01-01' if metric == 'deployment' else '2020-01-01'):
                    result.append(point(metric, 'quarter', date, number(value) * scale, source_ref(report, page)))
    required = {'deployment'} if report['period'] == '2019-12-31' else {'revenue', 'deployment'}
    if not required.issubset({row['metric'] for row in result}):
        raise ValueError('Tesla actual summary table missing')
    return result


def clean_row(row):
    return re.sub(r'\s+', ' ', row.get_text(' ', strip=True).replace('\u200b', '')).strip()


def parse_fluence(content, report):
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if 'Fluence Energy' not in text or 'results' not in text.lower():
        raise ValueError('Wrong Fluence document')
    end, fiscal_quarter = report['period'], report['quarter']
    result = []
    financials = [table for table in soup.select('table')
                  if all(label in table.get_text() for label in ['Total revenue', 'Research and development', 'General and administrative'])]
    if not financials:
        raise ValueError('Fluence financial statement missing')
    if not re.search('thousands', text, re.I):
        raise ValueError('Fluence statement currency scale missing')
    labels = {'revenue': r'Total revenue', 'gross': r'Gross(?: \(loss\))? profit(?: \(loss\))?', 'rd': r'Research and development',
              'sales': 'Sales and marketing', 'admin': 'General and administrative',
              'da': 'Depreciation and amortization'}
    for financial in financials:
        financial_text = financial.get_text(' ', strip=True)
        is_quarter = bool(re.search(r'Three Months', financial_text, re.I))
        values = {}
        for tr in financial.select('tr'):
            line = clean_row(tr)
            for metric, label in labels.items():
                if re.match(label + r'\s', line, re.I):
                    tail = re.sub(r'^' + label, '', line, flags=re.I).replace('$', '')
                    values[metric] = [number(value) / 1000 for value in re.findall(NUM, tail)]
        if set(values) != set(labels) or len({len(v) for v in values.values()}) != 1:
            raise ValueError('Incomplete Fluence operating expense components')
        n = len(values['revenue'])
        if n not in ((2, 3, 4) if is_quarter else (2, 3)):
            raise ValueError('Unexpected Fluence statement columns')
        values['profit'] = [round(values['gross'][i] - sum(values[key][i] for key in ['rd', 'sales', 'admin', 'da']), 9)
                            for i in range(n)]
        for metric in ['revenue', 'profit']:
            for i in range((2 if n == 4 else n) if is_quarter else n):
                date = str(int(end[:4]) - i) + end[4:]
                result.append(point(metric, 'quarter' if is_quarter else 'annual', date, values[metric][i], source_ref(report)))
                if is_quarter and n == 4:
                    kind = 'annual' if fiscal_quarter == 4 else 'ytd'
                    result.append(point(metric, kind, date, values[metric][i + 2], source_ref(report)))
    # Only the physical energy-storage table. Service/digital AUM and their
    # pipelines are never counted as deployed batteries.
    for table in soup.select('table'):
        table_text = re.sub(r'\s+', ' ', table.get_text(' ', strip=True))
        if 'Energy Storage Products and Solutions' not in table_text or 'Deployed' not in table_text:
            continue
        raw_dates = re.findall(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(20\d{2})', table_text)
        dates = [dt.date(int(year), MONTHS[month], int(day)).isoformat() for month, day, year in raw_dates[:2]]
        if len(dates) != 2 or dates[0] != end:
            raise ValueError('Fluence physical table date mismatch')
        row_labels = {'cumulative': 'Deployed (GWh)', 'cumulative_gw': 'Deployed (GW)',
                      'backlog_gw': 'Contracted Backlog (GW)', 'pipeline_gw': 'Pipeline (GW)',
                      'pipeline': 'Pipeline (GWh)'}
        for tr in table.select('tr'):
            line = clean_row(tr)
            for metric, label in row_labels.items():
                if line.startswith(label):
                    nums = re.findall(NUM, line[len(label):])
                    for date, value in zip(dates, nums[:2]):
                        result.append(point(metric, 'quarter', date, value, source_ref(report)))
        break
    # Narrative monetary backlog is a stock at period-end, not annual sales.
    match = re.search(r'(?:Contracted )?Backlog\s*(?:\d)?\s*(?:increased to|as of|of)[^.]{0,90}?\$([\d,.]+)\s*billion', text, re.I)
    if not match:
        match = re.search(r'(?:Contracted )?Backlog[^.]{0,100}?\$([\d,.]+)\s*billion\s*(?:as of|\d*\s*,?\s*(?:a record|the highest))', text, re.I)
    if match:
        result.append(point('backlog', 'quarter', end, number(match[1]) * 1000, source_ref(report), precision='approximate'))
    # Some releases disclose through-publication-date intake; do not assign it
    # to the quarter. Explicit quarterly language is required here.
    match = re.search(r'(?:Quarterly order intake|Order intake)\s+of\s+(approximately |more than )?\$([\d,.]+)\s*(million|billion)\s*(?:for the fiscal quarter ended|for the quarter|,|compared|bringing)', text, re.I)
    if match:
        result.append(point('order_intake', 'quarter', end, number(match[2]) * (1000 if match[3].lower() == 'billion' else 1),
                            source_ref(report), precision='lower_bound' if match[1] and 'more' in match[1] else 'approximate'))
    return result


def parse_sungrow(content, report):
    pages = blocks(content)
    text = ' '.join(text for _, text in pages)
    if not ('Sungrow Power Supply' in text or '阳光电源' in text):
        raise ValueError('Wrong Sungrow issuer')
    result = []
    amount = r'([\d,]+\.\d{2})'
    for page, text in pages:
        if report['kind'] == 'annual' and 'Sungrow Power Supply' in text:
            match = re.search(r'Energy\s+storage(?:\s+systems?)?\s+' + amount + r'\s+[\d.]+%\s+' + amount + r'\s+[\d.]+%', text, re.I)
        else:
            match = re.search(r'储能行业\s+' + amount + r'\s+[\d.]+%\s+' + amount + r'\s+[\d.]+%', text)
        if match:
            for year, value in zip([int(report['period'][:4]), int(report['period'][:4]) - 1], match.groups()):
                result.append(point('revenue', report['kind'], str(year) + report['period'][4:], number(value) / 1e6, source_ref(report, page)))
            break
    if not result:
        raise ValueError('Sungrow ESS-specific revenue composition missing')
    for page, text in pages:
        match = re.search(r'(?:global shipments of energy storage systems reached|energy storage systems achieved global shipments of|shipped)\s*([\d.]+)\s*GWh(?:\s+of energy storage systems)?', text, re.I)
        if match and report['kind'] == 'annual':
            result.append(point('shipments', 'annual', report['period'], match[1], source_ref(report, page)))
            break
    return result


def rss_reports(company, raw_dir=None, reuse=False):
    url = 'https://ir.fluenceenergy.com/rss/news-releases.xml' if company == 'fluence' else 'https://ir.tesla.com/rss.xml'
    root = ET.fromstring(download(url, raw_dir, reuse))
    reports = []
    for item in root.findall('.//item'):
        title, link = item.findtext('title', ''), item.findtext('link', '')
        if company == 'fluence':
            match = re.search(r'Reports (First|Second|Third|Fourth)(?: Fiscal)? Quarter(?: Fiscal)? (20\d{2}) Results', title, re.I)
            if not match:
                annual = re.search(r'Reports (?:Record Performance in |(?:Fourth Quarter and Full Fiscal Year )?)(20\d{2}).*(?:Results|Initiates)', title, re.I)
                if annual:
                    reports.append({'company': company, 'url': link, 'period': f'{annual[1]}-09-30',
                                    'quarter': 4, 'parser': company, 'label': title})
                continue
            q = ['first', 'second', 'third', 'fourth'].index(match[1].lower()) + 1
            fy = int(match[2]); date = quarter_end(fy - (q == 1), 4 if q == 1 else q - 1)
            reports.append({'company': company, 'url': link, 'period': date, 'quarter': q, 'parser': company, 'label': title})
        else:
            match = re.search(r'(First|Second|Third|Fourth) Quarter (20\d{2}) Production', title, re.I)
            if match:
                q = ['first', 'second', 'third', 'fourth'].index(match[1].lower()) + 1
                reports.append({'company': company, 'url': link, 'period': quarter_end(int(match[2]), q),
                                'parser': 'tesla_deployment', 'label': title})
    return reports


def latest_tesla(existing, raw_dir=None, reuse=False):
    today = korea_today()
    submissions = json.loads(download('https://data.sec.gov/submissions/CIK0001318605.json', raw_dir, reuse))
    if int(submissions.get('cik', 0)) != 1318605:
        raise ValueError('Wrong Tesla SEC catalogue')
    recent = submissions['filings']['recent']
    reports = []
    for i, form in enumerate(recent['form']):
        period = recent['reportDate'][i]
        if form not in ('10-Q', '10-K') or period < '2025-01-01' or period > today.isoformat() or recent['filingDate'][i] > today.isoformat():
            continue
        accession = recent['accessionNumber'][i].replace('-', '')
        reports.append({'company': 'tesla', 'url': f'https://ir.tesla.com/_flysystem/s3/sec/{accession}/tsla-{period.replace("-", "")}-gen.pdf',
                        'period': period, 'parser': 'tesla_rpo', 'label': 'Tesla ' + form + ' energy RPO'})
    # A quarter closing is not evidence that financials have been published.
    # Require a filed 10-Q/K before probing the official financial deck path.
    published_period = max((row['period'] for row in reports), default='1900-01-01')
    start = max(row['period'] for row in existing.values() if row.get('parser') == 'tesla') if existing else '2026-06-30'
    for year in range(int(start[:4]), today.year + 1):
        for q in range(1, 5):
            period = quarter_end(year, q)
            if not start < period <= published_period:
                continue
            url = f'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q{q}-{year}-Update.pdf'
            report = {'company': 'tesla', 'url': url, 'period': period, 'parser': 'tesla', 'label': f'Tesla Q{q} {year} Update'}
            if url not in existing:
                try:
                    report['_content'] = download(url, raw_dir, reuse)
                except requests.HTTPError as error:
                    if error.response.status_code == 404:
                        continue
                    raise
            reports.append(report)
    return reports


def latest_sungrow(raw_dir=None, reuse=False):
    # CNINFO's official public disclosure catalogue (company registry ID).
    today = korea_today()
    response = requests.post('https://www.cninfo.com.cn/new/hisAnnouncement/query',
        data={'pageNum': 1, 'pageSize': 30, 'tabName': 'fulltext', 'column': 'szse',
              'stock': '300274,9900021300', 'searchkey': '', 'category': 'category_ndbg_szsh;category_bndbg_szsh;',
              'seDate': f'{today.year - 1}-01-01~{today.isoformat()}', 'sortName': 'time', 'sortType': 'desc', 'isHLtitle': 'true'},
        headers={'Referer': 'https://www.cninfo.com.cn/'}, timeout=30)
    response.raise_for_status()
    rows = response.json().get('announcements')
    if rows is None:
        raise ValueError('Sungrow official report catalogue missing')
    result = []
    for row in rows:
        title = BeautifulSoup(row['announcementTitle'], 'html.parser').get_text()
        match = re.fullmatch(r'(20\d{2})年(半年度|年度)报告', title)
        if not match:
            continue
        year, kind = int(match[1]), 'half' if match[2] == '半年度' else 'annual'
        # Chinese annuals use the same product table with Chinese labels.
        result.append({'company': 'sungrow', 'url': urljoin('https://static.cninfo.com.cn/', row['adjunctUrl']),
                       'period': f'{year}-06-30' if kind == 'half' else f'{year}-12-31', 'kind': kind,
                       'parser': 'sungrow', 'label': title})
    return result


def merge_points(reports):
    data = {}
    # Newer reports supersede older comparative values; never overwrite a
    # present observation with an absent row.
    for report in sorted(reports.values(), key=lambda r: (r['period'], r.get('priority', 0), r.get('checked', ''))):
        for row in report['points']:
            data[(row['metric'], row['kind'], row['date'])] = row
    return data


def metric_rows(data, metric, kind):
    return {date: row for (m, k, date), row in data.items() if m == metric and k == kind}


def quarterly_difference(rows):
    result = {}
    for date, row in sorted(rows.items()):
        prev = rows.get(previous_quarter(date))
        if prev:
            value = round(row['value'] - prev['value'], 9)
            result[date] = {**row, 'value': value, 'source': {**row['source'], 'label': '누적 배치량의 분기 순증',
                            'supporting_url': prev['source']['url']}}
    return result


def cumulative_sum(rows, start):
    result, running = {}, 0
    latest = max(rows)
    for year in range(int(start[:4]), int(latest[:4]) + 1):
        for q in range(1, 5):
            date = quarter_end(year, q)
            if not start <= date <= latest:
                continue
            if date not in rows:
                raise ValueError('Cannot sum across a missing deployment quarter')
            running += rows[date]['value']
            result[date] = {**rows[date], 'value': round(running, 9), 'source': {**rows[date]['source'],
                            'label': start + ' 이후 공개 분기 배치량 합계 · 회사 전체 누적 아님'}}
    return result


def annual_sum(rows):
    result = {}
    for year in sorted({int(date[:4]) for date in rows}):
        points = [rows.get(quarter_end(year, q)) for q in range(1, 5)]
        if all(points):
            end = quarter_end(year, 4)
            result[end] = {**points[-1], 'value': round(sum(p['value'] for p in points), 9),
                           'source': {**points[-1]['source'], 'label': '공개 4분기 합계',
                                      'supporting_urls': [p['source']['url'] for p in points]}}
    return result


def view(rows, label, frequency, *, fiscal=False):
    dates = sorted(rows)
    if not dates:
        raise ValueError('Empty series must use explicit disclosure status')
    if frequency == 'quarterly':
        dates = [quarter_end(y, q) for y in range(int(dates[0][:4]), int(dates[-1][:4]) + 1)
                 for q in range(1, 5) if dates[0] <= quarter_end(y, q) <= dates[-1]]
    return {'label': label, 'frequency': frequency, 'quarter_labels': frequency == 'quarterly',
            'year_labels': frequency == 'yearly', 'series': {label: [[date, rows.get(date, {}).get('value')] for date in dates]},
            'period_sources': {date: row['source'] for date, row in rows.items()},
            'updated': max(rows), 'source_url': rows[max(rows)]['source']['url'],
            'fiscal_year_end_month': 9 if fiscal else 12,
            'value_qualifiers': {date: row['precision'] for date, row in rows.items() if row.get('precision') == 'lower_bound'}}


def card(company, metric, title, rows, unit, note, *, frequency='quarterly', annual=None, fiscal=False):
    shown = view(rows, title, frequency, fiscal=fiscal)
    dates = sorted(rows)
    doc = {'id': f'ess_{company}_{metric}', 'name': NAMES[company] + ' · ' + title, 'unit': unit,
           'source': NAMES[company] + ' 공식 공시', 'source_url': rows[dates[-1]]['source']['url'],
           'updated': dates[-1], 'fetched': korea_today().isoformat(), 'span_gaps': False,
           'company_kpi': True, 'change_mode': 'none', 'table_limit': 1000, 'strict_range': True,
           'note': note, **shown}
    if annual:
        doc['series_views'] = {'quarter': shown, 'annual': view(annual, '연간', 'yearly', fiscal=fiscal)}
        doc['series_views']['quarter']['label'] = '분기' if frequency == 'quarterly' else '반기'
        doc['default_view'] = 'quarter'
    return doc


def unavailable(company, metric, title, explanation, report):
    return {'id': f'ess_{company}_{metric}', 'name': NAMES[company] + ' · ' + title,
            'series': {}, 'disclosure_status': 'not_disclosed', 'note': explanation,
            'source': NAMES[company] + ' 공식 공시', 'source_url': report['url'],
            'updated': report['period'], 'fetched': korea_today().isoformat()}


def build_cards(company, reports):
    data = merge_points(reports)
    latest = max(reports.values(), key=lambda row: row['period'])
    rows = lambda metric, kind='quarter': metric_rows(data, metric, kind)
    if company == 'tesla':
        rev, deployed = rows('revenue'), rows('deployment')
        financial = max((row for row in reports.values() if row.get('parser') in ('tesla', 'tesla_rpo')), key=lambda row: row['period'])
        docs = [card(company, 'revenue', '에너지 부문 매출', rev, '백만 USD',
                     'Energy generation and storage 부문입니다. 태양광·에너지저장 사업을 포함하며 ESS만의 매출은 아닙니다.', annual=annual_sum(rev)),
                unavailable(company, 'profit', '에너지 부문 영업이익', '부문 영업이익 미공개. 회사 전체 영업이익이나 부문 매출총이익을 ESS 영업이익으로 대체하지 않습니다.', financial),
                card(company, 'deployment', '분기 신규 배치량', deployed, 'GWh', '회사 공표 Storage deployed입니다. Megapack·Powerwall 등을 포함하며 생산능력·수주량이 아닙니다.', annual=annual_sum(deployed)),
                card(company, 'cumulative', '공개 배치량 누계 · 2019년 이후', cumulative_sum(deployed, '2019-03-31'), 'GWh',
                     '2019 Q1 이후 공개 분기 배치량을 더한 계산값입니다. 2018년 이전 물량·폐기·용량 저하를 반영하지 않으므로 창사 이후 누적 설치량이나 현재 가동 용량이 아닙니다. 기간 필터를 바꿔도 누계의 시작점은 같습니다.')]
        if rows('rpo'):
            docs.append(card(company, 'rpo', '에너지 부문 장기 미이행 계약금액 · RPO', rows('rpo'), '백만 USD',
                             '태양광 포함 에너지 부문에서 최초 계약기간 1년 초과 계약의 미이행·일부 미이행 수행의무 금액입니다. 1년 이하 계약 등 공시 면제 항목을 제외해 ESS 전체 수주잔고와 같지 않습니다. 미계약 파이프라인·신규수주·고객 선수금이 아닙니다.'))
        return docs
    if company == 'sungrow':
        half, annual = rows('revenue', 'half'), rows('revenue', 'annual')
        # A complete annual and H1 pair permits an H2 flow; no quarterly split.
        for date, row in annual.items():
            first = half.get(date[:4] + '-06-30')
            if first:
                half[date] = {**row, 'value': round(row['value'] - first['value'], 9),
                              'source': {**row['source'], 'label': '하반기 = 연간 − 상반기', 'supporting_url': first['source']['url']}}
        ship = rows('shipments', 'annual')
        return [card(company, 'revenue', 'ESS 부문 매출', half, '백만 CNY',
                     '储能系统 / Energy storage 사업 매출입니다. 반기는 상·하반기 각각의 매출이고 하반기는 연간−상반기로 계산합니다. 분기별 부문 매출은 미공개입니다. 영문 Operating income은 여기서 매출(营业收入)을 의미합니다.', frequency='semiannual', annual=annual),
                unavailable(company, 'profit', 'ESS 부문 영업이익', '부문 영업이익 미공개. 매출−매출원가는 매출총이익이며 영업이익이 아닙니다. 전사 순이익·영업이익을 대신 넣지 않습니다.', latest),
                unavailable(company, 'deployment', '분기 신규 배치량', '전 세계 ESS의 분기별 준공·배치량 시계열 미공개. 반기·연간 출하량을 2·4로 나누거나 출하량을 설치량으로 바꾸지 않습니다. 아래 연간 출하량을 별도로 확인하세요.', latest),
                unavailable(company, 'cumulative', '누적 배치량', '기준일이 명확한 전 세계 ESS 누적 배치량 시계열을 공식 정기공시에서 확인하지 못했습니다. 인버터·컨버터 누적 GW와 ESS GWh, 누적 계약량을 구분합니다.', latest),
                card(company, 'shipments', 'ESS 연간 출하량', ship, 'GWh', '공식 연차보고서의 글로벌 ESS 출하량입니다. 출하 이후 실제 설치·계통 연결까지 시차가 있어 신규 배치량·누적 설치량과 같지 않습니다.', frequency='yearly')]
    rev, profit, cum = rows('revenue'), rows('profit'), rows('cumulative')
    for metric, quarters in [('revenue', rev), ('profit', profit)]:
        for date, row in rows(metric, 'annual').items():
            nine = rows(metric, 'ytd').get(date[:4] + '-06-30')
            if nine and date not in quarters:
                quarters[date] = {**row, 'value': round(row['value'] - nine['value'], 9),
                                  'source': {**row['source'], 'label': 'FY Q4 = 연간 − 9개월', 'supporting_url': nine['source']['url']}}
    docs = [card(company, 'revenue', '매출 · ESS 솔루션 / 연결', rev, '백만 USD', 'ESS 솔루션 매출과 서비스·디지털 사업까지 포함한 연결 매출을 보기로 구분합니다. ESS 솔루션 보기의 과거 자료는 공식 보충자료 이미지표를 대조한 값으로 백만 달러 소수점 1자리입니다. Fluence는 9월 결산이며 FY2026 Q3는 2026년 4~6월입니다.', fiscal=True, annual=rows('revenue', 'annual')),
            card(company, 'profit', '연결 영업손익 · 계산', profit, '백만 USD',
                 '공시 손익계산서의 매출총이익−연구개발비−판매마케팅비−일반관리비−영업 감가상각비로 계산했습니다. 이자·기타손익·법인세 전 계산 소계이며 회사가 직접 공표한 영업이익 소계가 아닙니다. ESS 하드웨어만의 영업이익은 미공개입니다. 조정 EBITDA·순이익과 다릅니다. FY Q4 직접값이 없으면 연간−9개월로 계산합니다.', fiscal=True, annual=rows('profit', 'annual')),
            card(company, 'deployment', '분기 배치량 순증 · 누적 차이', quarterly_difference(cum), 'GWh',
                 '인접한 분기말 누적 Deployed(GWh)의 차이입니다. 누적은 실질 준공(Substantial completion) 후 폐기되지 않은 설비를 뜻하므로 폐기·정정이 반영된 순증이며 총 신규 설치량과 다를 수 있습니다. 매출 인식 기준 GWh나 서비스·디지털 AUM을 사용하지 않습니다.', fiscal=True),
            card(company, 'cumulative', '누적 배치량', cum, 'GWh', '회사 공표 Energy Storage Products and Solutions Deployed(GWh)입니다. 실질 준공 후 폐기되지 않은 ESS만 포함합니다. 서비스·디지털 AUM·계약 잔고를 더하지 않습니다.', fiscal=True)]
    docs[0]['series_views'] = {'solutions': view(rows('solutions_revenue'), 'ESS 솔루션 · 분기', 'quarterly', fiscal=True),
                                'solutions_annual': view(rows('solutions_revenue', 'annual'), 'ESS 솔루션 · 연간', 'yearly', fiscal=True),
                                'consolidated': view(rev, '연결 · 분기', 'quarterly', fiscal=True),
                                'consolidated_annual': view(rows('revenue', 'annual'), '연결 · 연간', 'yearly', fiscal=True)}
    docs[0]['default_view'] = 'solutions'
    docs[0]['series'] = docs[0]['series_views']['solutions']['series']
    for key in ['solutions', 'solutions_annual']:
        docs[0]['series_views'][key]['collection_status'] = {
            'checked': '2026-10-07', 'ok': max(rows('solutions_revenue')) >= max(rev),
            'message': '공식 보충자료 이미지표 대조·전사값입니다.' + (' 새 분기의 부문별 매출 원문 확인이 필요합니다.' if max(rows('solutions_revenue')) < max(rev) else '')}
    order_specs = [('backlog', '수주잔고 · 금액', '백만 USD', '기말 미이행 계약 금액입니다. ESS 솔루션·서비스·디지털 전체를 포함하며 매출이나 신규수주와 다릅니다. 원문 반올림 기준.'),
                   ('order_intake', '분기 신규수주 · 금액', '백만 USD', '해당 분기에 신규 계약한 금액입니다. 누적 수주잔고·미계약 파이프라인과 다릅니다. 공시일 현재 연중 누계를 분기값으로 사용하지 않습니다.'),
                   ('backlog_gw', 'ESS 계약 잔고 · 출력', 'GW', 'Energy Storage Products and Solutions만의 계약 잔고입니다. 저장 에너지 GWh가 아니며 계약별 지속시간이 달라 4시간 등을 임의로 곱하지 않습니다.'),
                   ('pipeline', 'ESS 미계약 파이프라인', 'GWh', '아직 계약되지 않은 잠재 ESS 사업 물량입니다. 계약 체결 가능성을 회사가 평가한 영업 기회로 확정 수주잔고·신규수주·배치량이 아닙니다.')]
    for metric, title, unit, note in order_specs:
        if rows(metric):
            doc = card(company, metric, title, rows(metric), unit, note, fiscal=True)
            if metric == 'order_intake':
                doc['series_views'] = {'usd': {**view(rows(metric), '전체 금액', 'quarterly', fiscal=True), 'unit': '백만 USD'},
                                       'gwh': {**view(rows('order_gwh'), 'ESS 에너지', 'quarterly', fiscal=True), 'unit': 'GWh'},
                                       'gw': {**view(rows('order_gw'), 'ESS 출력', 'quarterly', fiscal=True), 'unit': 'GW'}}
                doc['default_view'] = 'usd'
            if metric == 'pipeline':
                doc['series_views'] = {'gwh': {**view(rows(metric), '저장 에너지', 'quarterly', fiscal=True), 'unit': 'GWh'},
                                       'gw': {**view(rows('pipeline_gw'), '출력', 'quarterly', fiscal=True), 'unit': 'GW'}}
                doc['default_view'] = 'gwh'
            docs.append(doc)
    return docs


def publish(company, reports):
    docs = build_cards(company, reports)
    for doc in docs:
        if not doc.get('disclosure_status'):
            for points in doc['series'].values():
                if not points or not any(value is not None for _, value in points):
                    raise ValueError('No actual observations')
        path = OUT / (doc['id'] + '.json')
        if path.exists():
            before = json.loads(path.read_text(encoding='utf-8'))
            if not before.get('disclosure_status') and not doc.get('disclosure_status'):
                preserve_history(before, doc)
    # Validate the whole company before replacing any of its cards.
    for doc in docs:
        atomic_json(OUT / (doc['id'] + '.json'), doc)
    return docs


def collect(raw_dir=None, reuse=False, offline=False, only=None):
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'companies': {}}
    failures = []
    for company in only or NAMES:
        before = cache['companies'].get(company, {})
        reports = {url: dict(row) for url, row in before.items()}
        candidates = [row for row in registry['reports'] if row['company'] == company]
        discovery_error = None
        if not offline:
            try:
                discovered = latest_sungrow(raw_dir, reuse) if company == 'sungrow' else latest_tesla(before, raw_dir, reuse) if company == 'tesla' else rss_reports(company, raw_dir, reuse)
                candidates.extend(discovered)
            except Exception as error:
                failures.append(f'{company} discovery: {error}')
                discovery_error = str(error)
                print(f'{company}: discovery failed; checking registered sources: {error}', flush=True)
        try:
            latest = max(row['period'] for row in candidates)
            for report in sorted(candidates, key=lambda row: row['period']):
                url = report['url']
                parser_version = 2 if report['parser'] == 'tesla_rpo' else 1
                if url in reports and reports[url].get('parser_version', 1) == parser_version and (offline or report['period'] < latest):
                    continue
                content = report.pop('_content', None) or download(url, raw_dir, reuse)
                parser = parse_sungrow if company == 'sungrow' else parse_fluence if company == 'fluence' else parse_tesla
                points = parser(content, report)
                reports[url] = {**report, 'points': points, 'parser_version': parser_version, 'checked': korea_today().isoformat(),
                                'sha256': hashlib.sha256(content).hexdigest()}
                print(company, report['period'], len(points), 'observations', flush=True)
            for audited in registry.get('audited', []):
                if audited['company'] == company:
                    reports[audited['url']] = audited
            docs = publish(company, reports)
            if discovery_error:
                for doc in docs:
                    doc['collection_status'] = {'checked': korea_today().isoformat(), 'ok': False,
                                                'message': '새 공시 목록 확인 실패 · 등록된 공식 자료만 재확인했습니다. 최신 공시 누락 가능성이 있습니다.'}
                    atomic_json(OUT / (doc['id'] + '.json'), doc)
            cache['companies'][company] = reports
            atomic_json(CACHE, cache)
            print(company, len(docs), 'cards published', flush=True)
        except Exception as error:
            failures.append(f'{company}: {error}')
            print(f'{company}: retained previous publication: {error}', flush=True)
    if failures:
        raise RuntimeError('\n'.join(failures))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-dir', type=Path)
    parser.add_argument('--reuse-raw', action='store_true')
    parser.add_argument('--offline', action='store_true', help='Rebuild from registered/cached sources; development only')
    parser.add_argument('--only', nargs='+', choices=list(NAMES))
    args = parser.parse_args()
    collect(args.raw_dir, args.reuse_raw, args.offline, args.only)

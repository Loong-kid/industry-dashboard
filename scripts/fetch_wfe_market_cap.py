# -*- coding: utf-8 -*-
"""WFE Focus 공개 월보의 국내기업 시총. 원자료 USD millions, 월별 원문 출처 보존."""
import calendar
import copy
import datetime as dt
import hashlib
import json
import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import fetch_market_size as market

BASE = 'https://focus.world-exchanges.org'
INDEX = BASE + '/'
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTHS['sept'] = 9
ALIASES = {
    'nyse': ['NYSE'], 'nasdaq': ['Nasdaq - US'],
    'shanghai': ['Shanghai Stock Exchange'], 'shenzhen': ['Shenzhen Stock Exchange'],
    'jpx': ['Japan Exchange Group', 'Japan Exchange Group Inc.'],
    'hkex': ['Hong Kong Exchanges and Clearing'],
    'euronext': ['Euronext'], 'deutsche': ['Deutsche Boerse AG'],
    'six': ['SIX Swiss Exchange'], 'bme': ['BME Spanish Exchanges'],
    'nordic': ['Nasdaq Nordic and Baltics', 'Nasdaq Nordic Exchanges'],
    'london': ['LSE Group', 'LSE Group London Stock Exchange', 'London Stock Exchange'],
}
REGIONS = {'americas': 'americas', 'apac': 'apac', 'asia - pacific': 'apac',
           'emea': 'emea', 'europe - africa - middle east': 'emea'}


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def issue_date(url):
    path = urlparse(url).path
    match = re.fullmatch(r'/issue/([a-z]+)-(20\d{2})/market-statistics/?', path)
    if urlparse(url).hostname != 'focus.world-exchanges.org' or not match or match[1] not in MONTHS:
        raise ValueError('WFE: unexpected issue URL')
    return f'{match[2]}-{MONTHS[match[1]]:02}'


def discover_issues(html, today=None):
    today = today or dt.date.today()
    urls = set()
    for link in BeautifulSoup(html, 'html.parser').find_all('a', href=True):
        url = urljoin(BASE, link['href']).split('#')[0].rstrip('/')
        try:
            issue = issue_date(url)
        except ValueError:
            continue
        if '2018-01' <= issue <= today.strftime('%Y-%m'):
            urls.add(url)
    if not urls:
        raise ValueError('WFE: no official archive issues discovered')
    return sorted(urls, key=issue_date)


def table_grid(table):
    """Expand the real rowspan/colspan headers; never infer months from column positions."""
    grid = []
    occupied = {}
    for row_index, row in enumerate(table.find_all('tr')):
        column = 0
        for cell in row.find_all(['th', 'td'], recursive=False):
            while (row_index, column) in occupied:
                column += 1
            rows, columns = int(cell.get('rowspan', 1)), int(cell.get('colspan', 1))
            if not (1 <= rows <= 10 and 1 <= columns <= 30):
                raise ValueError('WFE: unexpected table span')
            for dy in range(rows):
                for dx in range(columns):
                    occupied[row_index + dy, column + dx] = clean(cell.get_text(' ', strip=True))
            column += columns
        width = max((col for ri, col in occupied if ri == row_index), default=-1) + 1
        grid.append([occupied.get((row_index, col), '') for col in range(width)])
    return grid


def month_label(text):
    match = re.fullmatch(r"([A-Za-z]+)\s*['’\-]\s*(\d{2}|20\d{2})", text)
    if not match or match[1].lower() not in MONTHS:
        return None
    year = int(match[2]) + (2000 if len(match[2]) == 2 else 0)
    return f'{year}-{MONTHS[match[1].lower()]:02}'


def parse_report(html, url, today=None):
    today = today or dt.date.today()
    soup = BeautifulSoup(html, 'html.parser')
    heading = next((h for h in soup.find_all(['h2', 'h3', 'h4'])
                    if clean(h.get_text()).lower() == 'equity - domestic market capitalisation (usd millions)'), None)
    if heading is None or heading.find_next('table') is None:
        raise ValueError('WFE: domestic market cap table/units missing')
    grid = table_grid(heading.find_next('table'))
    if not grid or grid[0][0].lower() not in ['exchange', 'exchange name']:
        raise ValueError('WFE: unexpected capitalization headers')
    headers = grid[0]
    columns = {i: month_label(text) for i, text in enumerate(headers) if month_label(text)}
    body_start = 1
    if not columns and len(grid) > 1 and any(re.fullmatch(r'20\d{2}', h) for h in headers):
        # 2018/early 2019: explicitly labelled years above explicitly labelled full month names.
        columns = {i: f'{headers[i]}-{MONTHS[text.lower()]:02}' for i, text in enumerate(grid[1])
                   if text.lower() in MONTHS and i < len(headers) and re.fullmatch(r'20\d{2}', headers[i])}
        body_start = 2
    if not columns:
        # 2019: bare month names with the observation year in the change-column heading.
        bare = {i: MONTHS[text.lower()] for i, text in enumerate(headers) if text.lower() in MONTHS}
        comparison_dates = [month_label(m.group()) for h in headers if '%' in h
                            for m in re.finditer(r"[A-Za-z]+\s*['’\-]\s*\d{2}", h)]
        comparison_dates = [date for date in comparison_dates if date]
        latest = max(comparison_dates, default='')
        if bare and latest and list(bare.values()) == list(range(1, int(latest[5:]) + 1)):
            columns = {i: f'{latest[:4]}-{month:02}' for i, month in bare.items()}
    if not columns:
        raise ValueError('WFE: no unambiguous observation months')
    duplicate = {date for date, count in Counter(columns.values()).items() if count > 1}
    skipped = [f'duplicate month label {date}' for date in sorted(duplicate)]
    columns = {i: date for i, date in columns.items() if date not in duplicate}
    periods = list(columns.values())
    if not periods or periods != sorted(periods):
        raise ValueError('WFE: unordered observation months')
    end_month = (today.replace(day=1) - dt.timedelta(days=1)).strftime('%Y-%m')
    if periods[-1] > end_month:
        raise ValueError('WFE: unfinished/future observation month')
    lookup = {clean(alias).lower(): key for key, names in ALIASES.items() for alias in names}
    values = {date: {} for date in periods}
    region = None
    seen = set()
    for row in grid[body_start:]:
        if not row:
            continue
        name = row[0].lower()
        if name in REGIONS:
            region = REGIONS[name]
            continue
        key = lookup.get(name)
        if name in ['total region', 'total for region']:
            key = region
        elif name.startswith('total for ') and name[10:] in REGIONS:
            key = REGIONS[name[10:]]
        elif name == 'total':
            key = 'published_world'
        if key is None:
            continue
        if key in seen or len(row) <= max(columns):
            raise ValueError('WFE: duplicate/truncated selected row')
        seen.add(key)
        for column, date in columns.items():
            raw = re.sub(r'\s+', '', row[column]).replace(',', '')
            if raw in ['', '-', '–', '—', 'n/a', 'NA', '..', '0', '0.0', '0.00']:
                continue
            if not re.fullmatch(r'\d+(?:\.\d+)?', raw):
                raise ValueError('WFE: invalid capitalization cell')
            value = float(raw)
            if not math.isfinite(value) or value <= 0:
                raise ValueError('WFE: invalid capitalization value')
            values[date][key] = value
    if not {'americas', 'apac', 'emea'} <= seen:
        raise ValueError('WFE: three regional totals missing')
    for date, observation in values.items():
        if all(key in observation for key in ['americas', 'apac', 'emea']):
            world = sum(observation[key] for key in ['americas', 'apac', 'emea'])
            if 'published_world' in observation and abs(world - observation['published_world']) > 1:
                raise ValueError('WFE: published world total disagrees with regional totals')
            observation['world'] = world
        observation.pop('published_world', None)
    if not any('world' in row for row in values.values()):
        raise ValueError('WFE: no complete world observation')
    revision = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    return {'issue': issue_date(url), 'url': url, 'values': values, 'skipped_headers': skipped, 'revision': revision}


def merge_reports(previous, reports):
    merged = copy.deepcopy(previous)
    for report in sorted(reports, key=lambda r: r['issue']):
        for period, values in report['values'].items():
            target = merged.setdefault(period, {})
            # World and all three regions must come from the same complete report vintage.
            if 'world' not in values:
                values = {key: value for key, value in values.items() if key not in ['americas', 'apac', 'emea']}
            for key, value in values.items():
                old = target.get(key)
                if not old or report['issue'] >= old['issue']:
                    target[key] = {'value': value, 'issue': report['issue'], 'url': report['url'], 'revision': report['revision']}
    return merged


def points_for(observations, keys):
    output, sources = [], {}
    for period, row in sorted(observations.items()):
        if period < '2018-01' or not all(key in row for key in keys):
            continue
        # Aggregate only jointly reported components, never mix vintages or fabricate gaps.
        if len(keys) > 1 and len({(row[key]['issue'], row[key].get('revision')) for key in keys}) != 1:
            continue
        year, month = map(int, period.split('-'))
        date = f'{period}-{calendar.monthrange(year, month)[1]}'
        output.append([date, round(sum(row[key]['value'] for key in keys) / 1e6, 4)])
        sources[date] = {'url': row[keys[0]]['url'], 'issue': row[keys[0]]['issue']}
    return output, sources


def documents(observations):
    specs = [
        ('market_equity_global_wfe_m', '세계 주식시장 시가총액 (월말)',
         {'세계 합계': ['world']}, ['세계 합계'],
         'WFE가 보고한 Americas + APAC + EMEA 지역 합계를 더한 세계 국내기업 시총. 세계의 모든 기업·모든 거래소를 망라한 보장값은 아니며 보고 범위가 변할 수 있다.'),
        ('market_equity_regions_wfe_m', '지역별 주식시장 시가총액 (월말)',
         {'미주': ['americas'], '아시아·태평양': ['apac'], '유럽·중동·아프리카': ['emea']}, ['미주', '아시아·태평양', '유럽·중동·아프리카'],
         'WFE 공표 지역 합계. 미주는 미국 외 캐나다·중남미 등을 포함하고, EMEA는 유럽 외 중동·아프리카도 포함한다. 지역 합계와 하위 거래소를 다시 더하면 중복된다.'),
        ('market_equity_us_wfe_m', '미국 주요거래소 시가총액 (월말)',
         {'NYSE + Nasdaq': ['nyse', 'nasdaq'], 'NYSE': ['nyse'], 'Nasdaq 미국': ['nasdaq']}, ['NYSE + Nasdaq'],
         'NYSE와 Nasdaq - US의 국내기업 시총, 양쪽 공통 월·동일 월보 빈티지만 합산. 미국 전체 주식시장과 완전히 동일하다고 단정하지 않으며 S&P 500·Nasdaq Composite/100 지수 시총이 아니다.'),
        ('market_equity_cn_wfe_m', '중국 주요거래소 시가총액 (월말)',
         {'상하이 + 선전': ['shanghai', 'shenzhen'], '상하이': ['shanghai'], '선전': ['shenzhen']}, ['상하이 + 선전'],
         '상하이·선전 거래소 국내기업 시총의 공통 월·동일 빈티지 합계. 베이징 거래소·NEEQ·홍콩을 포함하지 않으므로 중국 전체라는 이름을 붙이지 않는다. 홍콩은 별도 카드로 표시한다.'),
        ('market_equity_jp_wfe_m', '일본 JPX 시가총액 (월말)',
         {'일본 JPX': ['jpx']}, ['일본 JPX'],
         'Japan Exchange Group 국내기업 시총. 도쿄 중심의 JPX 범위이며 지역 거래소까지 포함한 일본 전체 합계나 Nikkei 225·TOPIX 지수 시총이 아니다.'),
        ('market_equity_hk_wfe_m', '홍콩 HKEX 시가총액 (월말)',
         {'홍콩 HKEX': ['hkex']}, ['홍콩 HKEX'],
         'Hong Kong Exchanges and Clearing 국내기업 시총. WFE 거래소 분류를 따르며 중국 본토 합계에 더하지 않는다. 홍콩의 기업 분류와 중국 본토·다른 시장의 중복 상장 범위에 유의한다.'),
        ('market_equity_europe_wfe_m', '유럽 주요거래소 시가총액 (월말)',
         {'Euronext': ['euronext'], '독일 Deutsche Börse': ['deutsche'], '스위스 SIX': ['six'],
          '스페인 BME': ['bme'], '북유럽·발트 Nasdaq': ['nordic'], '런던 LSE': ['london']},
         ['Euronext', '독일 Deutsche Börse', '스위스 SIX'],
         '거래소별 비교이며 국가별 전체 시총이 아니다. Euronext·Nasdaq Nordic은 여러 국가를 포함하고 인수·통합으로 범위가 달라질 수 있다. LSE Group 과거 범위도 이탈리아 편입 여부 등에 따라 달라지며, 최근 미공표 월은 공백으로 남긴다. EU 합계로 더하지 않는다.'),
    ]
    docs = []
    for cid, name, groups, default, scope in specs:
        series, references = {}, {}
        for label, keys in groups.items():
            series[label], references[label] = points_for(observations, keys)
            if len(series[label]) < 3 or any(not math.isfinite(value) or value <= 0 for _, value in series[label]):
                raise ValueError(f'WFE: insufficient history for {cid}/{label}')
        main = default[0]
        old = market.OUT / f'{cid}.json'
        if old.exists():
            old_doc = json.loads(old.read_text(encoding='utf-8'))
            for label, history in old_doc['series'].items():
                incoming = dict(series.get(label, []))
                if history[-1][0] > series[label][-1][0] or not set(dict(history)) <= set(incoming):
                    raise ValueError(f'WFE: existing history regressed for {cid}/{label}')
        docs.append((cid, name, series, references, default, scope))
    return docs


def run():
    today = dt.date.today()
    home_issues = discover_issues(market.get(INDEX).content, today)
    # The homepage can lag the archive's newest issue; the linked table exposes the archive list.
    archive = market.get(home_issues[-1])
    issues = discover_issues(archive.content, today)
    old = market.read_cache('wfe_monthly')
    previous = old.get('observations', {})
    if previous:
        # Latest 3 reports daily; year-end archive reports monthly for older corrections.
        refresh = issues[-3:]
        if today.day == 1:
            refresh = sorted(set(refresh + [u for u in issues if issue_date(u)[5:] in ['01', '02', '12']]), key=issue_date)
    else:
        refresh = issues
    reports, failures = [], []
    def fetch(url):
        try:
            return parse_report(market.get(url).content, url, today)
        except Exception as exc:
            return {'failed': url, 'reason': str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for report in pool.map(fetch, refresh):
            if 'failed' in report:
                failures.append(report)
            else:
                reports.append(report)
    if not reports or not any(r['url'] == issues[-1] for r in reports):
        raise ValueError('WFE: latest public report failed validation; published cards preserved')
    observations = merge_reports(previous, reports)
    docs = documents(observations)  # Validate all seven cards before publishing any.
    global_points = docs[0][2]['세계 합계']
    if len(global_points) < 36:
        raise ValueError('WFE: world monthly history unexpectedly short')
    skipped = [{'issue': r['issue'], 'reason': reason} for r in reports for reason in r['skipped_headers']]
    for cid, name, series, references, default, scope in docs:
        main = default[0]
        latest_ref = references[main][series[main][-1][0]]
        last_dates = ' / '.join(f'{label}: {history[-1][0][:7]}' for label, history in series.items())
        first_month = int(series[main][0][0][:4]) * 12 + int(series[main][0][0][5:7]) - 1
        last_month = int(series[main][-1][0][:4]) * 12 + int(series[main][-1][0][5:7]) - 1
        present = {date[:7] for date, _ in series[main]}
        gaps = [f'{offset // 12}-{offset % 12 + 1:02}' for offset in range(first_month, last_month + 1)
                if f'{offset // 12}-{offset % 12 + 1:02}' not in present]
        gap_note = ' 대표 계열 미확보 월: ' + ', '.join(gaps) + '.' if gaps else ''
        market.save(cid, name, series[main], 'WFE · Focus 월간 통계', latest_ref['url'],
                    '월말 국내기업 상장주식 시총. 원자료 USD millions를 조 달러로 환산한다.',
                    scope + gap_note + ' 명목 달러 기준으로 환율의 영향을 받는다. WFE는 일부 거래소의 두 달 이하 연속 누락을 보간했다고 밝힌다. 보고 거래소·지역 분류의 변경도 포함될 수 있다. 원문에서 확정할 수 없는 월은 자체 추정하지 않으며 World Bank 연간값과 이어 붙이지 않는다.',
                    [{'label': '집계 범위', 'value': scope},
                     {'label': '시점·단위', 'value': '월말 잔액. USD millions ÷ 1,000,000 = 조 달러. 날짜는 관측월의 달력 말일이며 월보 발행월과 다르다. 물가 조정 없음.'},
                     {'label': '원자료·추정', 'value': 'WFE Focus의 Equity - Domestic market capitalisation 표. 거래대금·상장기업 수·지수 포인트가 아니다. WFE 자체 누락 보간이 포함될 수 있고 해당 셀은 원문에서 개별 표식을 제공하지 않는다. 거래소별 보고 범위·기업 분류가 서로 다를 수 있다.'},
                     {'label': '자료 가용성', 'value': last_dates + '.' + gap_note + ' 최근 미공표 거래소는 마지막 확보 월을 유지한다. 차트의 빈 월은 선을 끊는다.'},
                     {'label': '원문 검증', 'value': '중복·잘못된 월 머리글은 값을 재배정하지 않고 해당 열을 제외한다. 최초 수집 때는 2026-10 월보의 중복 Mar 머리글을 제외하고 2026-09의 명확한 3월·5월을 사용했다. 이후 명확한 월을 공표하면 정정을 반영한다. 세 지역 합계는 동일 월보 빈티지를 유지하며 누락분을 임의 추정하지 않는다.'},
                     {'label': '자동 갱신·출처', 'value': '매일 최신 공개 월보 3개를 확인하고 매월 1일 연말 관련 과거 원문도 재확인한다. 새 공표·확인된 정정을 반영하며 실패 시 기존 자료를 유지한다. 표의 원문 링크는 각 대표 계열 관측월의 월보를 가리킨다.'}],
                    frequency='monthly', full_range=False, table_limit=1000, series=series,
                    span_gaps=False, monthly_axis=True, month_labels=True, default_series=default, data_stale_days=180,
                    period_sources=references[main], series_sources=references, source_issue=latest_ref['issue'])
    market.write_json(market.CACHE / 'wfe_monthly.json', {'observations': observations,
                      'checked': market.TODAY, 'latest_issue': issue_date(issues[-1]),
                      'skipped_headers': skipped, 'archive_failures': failures})
    for item in failures:
        print(f"WFE archive skipped {issue_date(item['failed'])}: {item['reason']}")
    for item in skipped:
        print(f"WFE header skipped {item['issue']}: {item['reason']}")


if __name__ == '__main__':
    run()

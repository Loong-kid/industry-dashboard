# -*- coding: utf-8 -*-
"""공개 시장규모: World Bank API, SIFMA Fact Book, S&P 공식 분기 보도자료.

매일 실행해 새 발표·정정치를 확인한다. 데이터 주기는 연간/분기이며 보간하지 않는다.
다운로드/표 검증 실패 시 해당 소스의 공개 JSON을 교체하지 않는다.
"""
import calendar
import datetime as dt
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import fitz
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'macro'
CACHE = ROOT / 'data' / '_market_size'
TODAY = dt.date.today().isoformat()
SIFMA = 'https://www.sifma.org/research/statistics/fact-book'
WB_COUNTRIES = {
    'USA': ('us', '미국'), 'WLD': ('global', '글로벌'),
    'KOR': ('kr', '한국'), 'CHN': ('cn', '중국'), 'JPN': ('jp', '일본'),
    'GBR': ('uk', '영국'), 'DEU': ('de', '독일'), 'FRA': ('fr', '프랑스'),
    'ITA': ('it', '이탈리아'), 'ESP': ('es', '스페인'),
    'NLD': ('nl', '네덜란드'), 'CHE': ('ch', '스위스'),
}
WB = 'https://api.worldbank.org/v2/country/' + ';'.join(WB_COUNTRIES) + '/indicator/CM.MKT.LCAP.CD?format=json&per_page=2000'
WB_PAGE = 'https://data.worldbank.org/indicator/CM.MKT.LCAP.CD'
ECOS_PAGE = 'https://ecos.bok.or.kr/#/SearchStat'
ESMA_PAGE = 'https://www.esma.europa.eu/document/market-capitalisation-figures-under-faster-directive'
ESMA_METHOD = 'https://eur-lex.europa.eu/eli/reg_del/2026/110/oj'
ESMA_COUNTRIES = {'FR': '프랑스', 'DE': '독일', 'NL': '네덜란드', 'IT': '이탈리아',
                  'ES': '스페인', 'SE': '스웨덴', 'DK': '덴마크', 'BE': '벨기에'}
SP_ARCHIVE = 'https://press.spglobal.com/index.php?s=2429&keywords=buybacks&l=100'
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'industry-dashboard public-data collector'


def get(url, **kwargs):
    response = SESSION.get(url, timeout=(10, 60), **kwargs)
    response.raise_for_status()
    return response


def read_cache(name):
    path = CACHE / f'{name}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False) + '\n', encoding='utf-8')


def save(cid, name, points, source, url, description, note, details, unit='조 달러', min_points=3, series=None, **extra):
    histories = series if series is not None else {'시장규모': points}
    for history in histories.values():
        if len(history) < min_points or history != sorted(history) or len({p[0] for p in history}) != len(history):
            raise ValueError(f'{cid}: invalid or insufficient history')
        if any(not math.isfinite(p[1]) or p[1] <= 0 for p in history):
            raise ValueError(f'{cid}: invalid market size')
    doc = dict(name=name, unit=unit, frequency='yearly', full_range=True,
               year_labels=True, zero_baseline=True, table_limit=200, series=histories,
               source=source, source_url=url, description=description, note=note,
               basis_details=details, fetched=TODAY, updated=points[-1][0], **extra)
    write_json(OUT / f'{cid}.json', doc)
    print(f'{cid}: {len(points)} observations, latest {points[-1]}')


def annual_points(values):
    return [[f'{year}-12-31', round(value / 1000, 4)] for year, value in sorted(values.items())]


def parse_world_bank(payload, countries=('USA', 'WLD')):
    if len(payload) != 2 or payload[0].get('pages') != 1:
        raise ValueError('World Bank: unexpected response or pagination')
    output = {country: {} for country in countries}
    for row in payload[1]:
        country, value = row.get('countryiso3code'), row.get('value')
        if country in output and value is not None:
            if row['indicator']['id'] != 'CM.MKT.LCAP.CD' or not math.isfinite(value) or value <= 0:
                raise ValueError('World Bank: invalid indicator/value')
            output[country][int(row['date'])] = value / 1e9  # USD -> billions
    if any(len(values) < (30 if country in ('USA', 'WLD') else 3) for country, values in output.items()):
        raise ValueError('World Bank: history unexpectedly truncated')
    return output


def collect_world_bank():
    payload = get(WB).json()
    values = parse_world_bank(payload, WB_COUNTRIES)
    for country, (suffix, _) in WB_COUNTRIES.items():
        cid = f'market_equity_{suffix}'
        old = OUT / f'{cid}.json'
        if old.exists() and f'{max(values[country])}-12-31' < json.loads(old.read_text(encoding='utf-8'))['updated']:
            raise ValueError('World Bank: latest observation regressed')
    for country, (suffix, name) in WB_COUNTRIES.items():
        cid, title = f'market_equity_{suffix}', f'{name} 전체 주식시장 시가총액'
        points = annual_points(values[country])
        latest = max(values[country])
        gaps = [year for year in range(min(values[country]), latest + 1) if year not in values[country]]
        availability = f'공개 API에서 확보한 마지막 관측연도는 {latest}년이다.'
        if latest < dt.date.today().year - 2:
            availability += ' 이후 연말 시총은 이 계열에 미공표되어 과거 이력으로 표시한다.'
        if gaps:
            availability += ' 미공표 연도(' + ', '.join(map(str, gaps)) + ')는 차트의 선을 끊으며 보간하지 않는다.'
        scope = 'World Bank 세계 합계(WLD), 보고된 국가·거래소 자료 기준' if country == 'WLD' else f'{name}({country})의 국내 상장기업 · 거래소 소재 국가 기준'
        if country == 'CHN':
            scope += '. 홍콩(HKG) 계열은 별도이므로 이 카드에 합산하지 않는다.'
        save(cid, title, points, 'World Bank WDI · WFE', WB_PAGE + '?locations=' + country,
             '연말 상장 국내기업의 주가 × 발행주식수. 명목 달러 기준의 주식시장 규모다.',
             availability + ' 비상장기업·외국법인·ETF/펀드 자산규모는 포함하지 않는다. 국가별 자료 범위와 공표 시점이 달라 세계 합계가 SIFMA 집계와 다를 수 있다. 다른 출처를 이어 붙이지 않는다.',
             [{'label': '집계 범위', 'value': scope},
              {'label': '원자료', 'value': 'CM.MKT.LCAP.CD · current US$ · World Federation of Exchanges database'},
              {'label': '시점과 환산', 'value': '연말 기준. 달러 원값 ÷ 1조. 물가 조정 없음; 국가 간 비교와 세계 합계는 환율 영향도 받는다.'},
              {'label': '자료 가용성', 'value': availability},
              {'label': '자동 갱신', 'value': '매일 공개 API를 확인하며 새 연간 관측값과 과거 수정치를 반영한다. 발표 전 연도를 만들지 않는다.'}],
             source_updated=payload[0].get('lastupdated'), methodology_url=WB_PAGE,
             annual_axis=True, span_gaps=False, data_stale_days=730,
             license='CC BY 4.0', license_url='https://creativecommons.org/licenses/by/4.0/')


def parse_ecos_cap(payload, item):
    block = payload.get('StatisticSearch', {})
    rows = block.get('row', [])
    if not rows or block.get('list_total_count') != len(rows):
        raise ValueError('ECOS: missing or truncated market capitalization response')
    output = {}
    for row in rows:
        if row.get('STAT_CODE') != '901Y014' or row.get('ITEM_CODE1') != item or row.get('UNIT_NAME') != '천원':
            raise ValueError('ECOS: unexpected table, item or unit')
        year, value = row['TIME'], float(row['DATA_VALUE'])
        if not re.fullmatch(r'\d{4}', year) or not math.isfinite(value) or value <= 0 or year in output:
            raise ValueError('ECOS: invalid annual observation')
        output[year] = value / 1e9  # thousand KRW -> trillion KRW
    return output


def collect_korea_boards():
    key = os.environ.get('ECOS_API_KEY', '').strip() or 'sample'
    histories = {}
    last_year = dt.date.today().year - 1
    for item, start in [('1040000', 1984), ('2040000', 2004)]:
        values = {}
        # Public sample requests allow ten observations; CI uses the existing ECOS secret.
        width = 10 if key == 'sample' else 100
        for year in range(start, last_year + 1, width):
            end = min(year + width - 1, last_year)
            url = f'https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/{width}/901Y014/A/{year}/{end}/{item}'
            try:
                payload = get(url).json()
            except requests.RequestException as exc:
                # ECOS keys are part of request URLs; do not expose them in failure logs.
                raise RuntimeError(f'ECOS request failed ({type(exc).__name__})') from None
            if payload.get('RESULT', {}).get('CODE') == 'INFO-200' and year > start:
                break  # no annual release yet, keep last real observation
            values.update(parse_ecos_cap(payload, item))
        if len(values) < 15:
            raise ValueError('ECOS: annual market history unexpectedly truncated')
        histories[item] = values
    shared = set(histories['1040000']) & set(histories['2040000'])
    total = {year: histories['1040000'][year] + histories['2040000'][year] for year in shared}
    specs = [('market_kospi', '코스피 시장 시가총액', histories['1040000'], '1040000 · KOSPI_시가총액 · 1984년부터'),
             ('market_kosdaq', '코스닥 시장 시가총액', histories['2040000'], '2040000 · KOSDAQ_시가총액 · 2004년부터'),
             ('market_equity_kr_krw', '한국 주요시장 시가총액 (코스피 + 코스닥)', total, '1040000 + 2040000 · 두 항목이 모두 있는 연도만 합산')]
    for cid, _, values, _ in specs:
        old = OUT / f'{cid}.json'
        if old.exists() and f'{max(values)}-12-31' < json.loads(old.read_text(encoding='utf-8'))['updated']:
            raise ValueError('ECOS: latest annual observation regressed')
    for cid, title, values, items in specs:
        points = [[f'{year}-12-31', round(value, 4)] for year, value in sorted(values.items())]
        save(cid, title, points, '한국거래소 · 한국은행 ECOS', ECOS_PAGE,
             '해당 시장에 상장된 주식의 연말 시가총액. 원화 명목 금액이다.',
             '단위는 조 원이며 달러 국가 비교 카드와 단위가 다르다. 코스피·코스닥은 각 시장 전체로 200·150 지수의 시총이 아니다. 합계는 코스피 + 코스닥으로 코넥스를 제외한다. 국내 집계와 WFE 국제 비교용 국내기업 시총은 외국법인·투자회사 등의 포함 범위가 달라 직접 일치하지 않는다.',
             [{'label': '원자료 항목', 'value': 'ECOS 901Y014 · 주식시장(월,년) · 연간(A) · ' + items},
              {'label': '시점·단위', 'value': '연말 잔액. 원자료 천원 ÷ 10억 = 조 원. 환율 환산·물가 조정 없음.'},
              {'label': '집계 범위', 'value': '한국거래소 시장별 상장주식 합계. 국내 통계는 외국법인·부동산투자회사·선박투자회사·증권투자회사 등을 포함한다. ETF/ETN 자산 규모는 별도다.'},
              {'label': '자동 갱신', 'value': '매일 ECOS 연간 API에서 새 연말값과 과거 정정치를 확인한다. 반기값을 연말값으로 사용하지 않는다.'}],
             unit='조 원', annual_axis=True, span_gaps=False, methodology_url='https://www.index.go.kr/unity/potal/main/EachDtlPageDetail.do?idx_cd=1079')


def parse_esma_pdf(content):
    output = {}
    with fitz.open(stream=content, filetype='pdf') as book:
        for page in book:
            text = page.get_text()
            match = re.search(r'Table\s+\d+\s+Market capitalisation and market capitalisation ratios of Member States\s*\((20\d{2})\)', text)
            if not match:
                continue
            if 'EUR bn' not in text:
                raise ValueError('ESMA: unexpected currency/unit')
            rows = re.findall(r'(?m)^([A-Z]{2})\s+([\d.]+)\s+([\d.]+)\s*$', text)
            values = {country: float(value) for country, value, ratio in rows}
            if len(rows) != 27 or len(values) != 27 or any(not math.isfinite(v) or v <= 0 for v in values.values()):
                raise ValueError('ESMA: incomplete or invalid Member State table')
            if abs(sum(float(ratio) for _, _, ratio in rows) - 100) > .01:
                raise ValueError('ESMA: country ratios do not sum to 100%')
            output[match[1]] = values
    if len(output) < 2 or any(not set(ESMA_COUNTRIES) <= set(v) for v in output.values()):
        raise ValueError('ESMA: insufficient annual history')
    return output


def collect_esma():
    soup = BeautifulSoup(get(ESMA_PAGE).content, 'html.parser')
    links = [urljoin(ESMA_PAGE, a['href']) for a in soup.select('a[href]')
             if '.pdf' in a['href'] and 'market_capitalisation' in a['href'].lower()]
    if not links:
        raise ValueError('ESMA: official report link missing')
    url = sorted(set(links))[-1]
    values = parse_esma_pdf(get(url).content)
    old = read_cache('esma')
    if old and max(values) < max(old['annual']):
        raise ValueError('ESMA: latest report regressed')
    merged = dict(old.get('annual', {}))
    merged.update({year: {'countries': countries, 'url': url} for year, countries in values.items()})
    series = {name: [[f'{year}-12-31', round(row['countries'][country] / 1000, 4)]
                     for year, row in sorted(merged.items())] for country, name in ESMA_COUNTRIES.items()}
    cid = 'market_equity_eu_recent'
    save(cid, '유럽 주요국 시가총액 · 최근 연말 비교', next(iter(series.values())), 'ESMA · MiFIR / FITRS', url,
         'EU 회원국에 법적 주소를 둔 기업의 연말 상장주식 시총. ESMA 공표의 유로 기준이다.',
         '조 유로 기준. 최초 공개 이력은 2024·2025년 두 해다. 장기 World Bank 달러 계열과 연결하지 않는다. 국가별 법적 주소 기준으로 거래소 소재 국가 기준과 다르다. 영국·스위스는 EU 회원국에 해당하지 않아 이 차트에서 제외하며 아래 달러 장기 이력에 표시한다.',
         [{'label': '집계 방법', 'value': '연말 주가 × 발행주식수. EU 규제시장·다자간거래시설(MTF)의 주식을 기업 법적 주소가 있는 회원국에 배정한다. 중복 거래소 상장은 주식을 중복 합산하지 않는다.'},
          {'label': '가격·주식수', 'value': 'EU 내 해당 주식의 가장 유동적인 시장에서 연중 마지막 거래 전 5분의 최근 최대 100건 평균가격 × FITRS 연말 발행주식수. 유로로 환산하며 1,000주 미만 발행 증권은 원문 집계에서 제외한다.'},
          {'label': '단위와 이력', 'value': '원자료 십억 유로 ÷ 1,000 = 조 유로. 2026년 첫 공표에서 2024·2025년 이력을 확보했다.'},
          {'label': '자동 갱신', 'value': '매일 ESMA 공식 보고서 페이지의 PDF를 확인한다. 새 보고서에 추가 연도가 공표되면 이력을 누적한다.'}],
         unit='조 유로', min_points=2, series=series, annual_axis=True, span_gaps=False,
         default_series=['프랑스', '독일', '네덜란드', '이탈리아', '스페인'], methodology_url=ESMA_METHOD,
         source_dates={f'{year}-12-31': {'ESMA 기준일': f'{year}-12-31'} for year in merged})
    write_json(CACHE / 'esma.json', {'annual': merged})


def parse_pdf_rows(text, expected_columns):
    """PDF 표: 한 줄씩 추출된 셀. 증감률 열·각주·차트 숫자는 제외한다."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if 'Average' in lines:
        lines = lines[:lines.index('Average')]
    marker = lines.index('($B)')
    first = next(i for i in range(marker + 1, len(lines)) if re.fullmatch(r'(?:19|20)\d{2}', lines[i]))
    headers = lines[marker + 1:first]
    if '(Y/Y)' in headers:
        headers = headers[:headers.index('(Y/Y)')]
    if len(headers) != expected_columns or headers[-1] != 'Total':
        raise ValueError(f'SIFMA: unexpected columns {headers}')
    rows = {}
    i = first
    while i + expected_columns < len(lines):
        year = lines[i]
        cells = lines[i + 1:i + 1 + expected_columns]
        if re.fullmatch(r'(?:19|20)\d{2}', year) and all(re.fullmatch(r'\d[\d,]*(?:\.\d+)?', c) for c in cells):
            values = [float(c.replace(',', '')) for c in cells]
            if abs(sum(values[:-1]) - values[-1]) > max(2, values[-1] * .00005):
                raise ValueError(f'SIFMA: total mismatch for {year}')
            rows[int(year)] = dict(zip(headers, values))
            i += expected_columns + 1
        else:
            i += 1
    if len(rows) < 10:
        raise ValueError('SIFMA: insufficient annual rows')
    return rows


def parse_sifma_pdf(content):
    output = {}
    with fitz.open(stream=content, filetype='pdf') as book:
        specs = [('bonds', 'Global Fixed Income Markets Outstanding', 13),
                 ('nasdaq', 'U.S. Stock Market Capitalization', 3)]
        for key, title, width in specs:
            for page in book:
                text = page.get_text()
                if title in text and '($B)' in text and (key != 'nasdaq' or 'Nasdaq' in text):
                    output[key] = {'rows': parse_pdf_rows(text, width), 'page': page.number + 1}
                    break
            if key not in output:
                raise ValueError(f'SIFMA: table missing: {title}')
    return output


def collect_sifma():
    soup = BeautifulSoup(get(SIFMA).content, 'html.parser')
    links = {}
    for a in soup.find_all('a', href=True):
        url = urljoin(SIFMA, a['href'])
        if url.endswith('.pdf') and re.search(r'fact.?book', url, re.I):
            years = re.findall(r'20\d{2}', a.get_text(' ', strip=True) + url)
            if years:
                links[max(map(int, years))] = url
    if not links:
        raise ValueError('SIFMA: cannot discover current edition')
    cache = read_cache('sifma')
    latest = max(links)
    editions = [latest]
    for edition in editions:
        url = links[edition]
        parsed = parse_sifma_pdf(get(url).content)
        for key, table in parsed.items():
            saved = cache.setdefault(key, {})
            for year, values in table['rows'].items():
                old = saved.get(str(year), {})
                if edition >= old.get('edition', 0):
                    saved[str(year)] = {'values': values, 'edition': edition, 'url': url, 'page': table['page']}
    if latest < max(row['edition'] for row in cache['bonds'].values()):
        raise ValueError('SIFMA: edition regressed')
    write_json(CACHE / 'sifma.json', cache)
    for field, cid, title in [('US', 'market_bonds_us', '미국 전체 채권시장 발행잔액'),
                               ('Total', 'market_bonds_global', '글로벌 전체 채권시장 발행잔액')]:
        values = {int(year): row['values'][field] for year, row in cache['bonds'].items()}
        last = cache['bonds'][str(max(values))]
        save(cid, title, annual_points(values), 'SIFMA Fact Book · BIS', last['url'] + f"#page={last['page']}",
             '금융회사·비금융기업·정부가 발행한 채무증권의 연말 잔액. 은행대출을 합친 전체 부채와는 범위가 다르다.',
             '시가로 평가한 채권 포트폴리오 가치가 아니라 원자료의 outstanding 기준이다. 단기 채무증권도 포함된다. 2018년 일부 국가의 통계 편입으로 세계 합계에 단절이 있다.',
             [{'label': '시장 범위', 'value': '미국 거주 발행자(US)' if field == 'US' else 'SIFMA가 BIS 국가별 자료로 집계한 세계 합계(Total)'},
              {'label': '포함·제외', 'value': '정부·금융·비금융 부문의 채무증권. 금융부문 발행증권 포함; 국채만의 합계나 은행대출 포함 총부채가 아니다. MBS·ABS 제외인 별도 SIFMA 최신 요약값을 대신 사용하지 않는다.'},
              {'label': '가치 기준', 'value': 'SIFMA/BIS 발행잔액 원값(십억 달러) ÷ 1,000. 국가별 평가 관행이 달라 주식 시총과 동일한 시가평가 합계로 해석하지 않는다.'},
              {'label': '갱신과 통계 단절', 'value': f'{latest}년판 Fact Book. 매일 최신판 링크를 찾아 발표된 연간값·정정을 반영한다. 2018년 통계 편입국 증가에 따른 단절이 있다.'}],
             methodology_url=SIFMA, source_edition=latest)
    values = {int(year): row['values']['Nasdaq'] for year, row in cache['nasdaq'].items()}
    last = cache['nasdaq'][str(max(values))]
    save('market_nasdaq', '나스닥 거래소 시가총액 (미국 국내기업)', annual_points(values),
         'SIFMA Fact Book · WFE', last['url'] + f"#page={last['page']}",
         '나스닥 거래소에 상장된 미국 국내기업의 연말 시가총액 합계.',
         '나스닥 종합지수 또는 나스닥 100의 구성종목 시총과 다르다. 외국기업·ETF 자산을 합친 거래소 전체 상장자산 규모가 아니다.',
         [{'label': '집계 범위', 'value': 'WFE 국내기업(domestic companies) 기준의 Nasdaq 거래소 시총'},
          {'label': '지수와의 차이', 'value': 'Nasdaq Composite/100의 가격지수·구성종목 시총으로 대체하거나 환산하지 않는다.'},
          {'label': '환산·갱신', 'value': f'연말 십억 달러 ÷ 1,000. {latest}년판 SIFMA Fact Book; 매일 최신 연간 보고서와 정정치를 확인한다.'}],
         methodology_url=SIFMA, source_edition=latest)


def parse_sp_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    annual, quarterly = {}, {}
    for table in soup.find_all('table'):
        if not re.search(r'MARKET\b.*?\bVALUE', table.get_text(' ', strip=True), re.I | re.S):
            continue
        for tr in table.find_all('tr'):
            cells = [td.get_text(' ', strip=True) for td in tr.find_all(['td', 'th'], recursive=False)]
            if len(cells) < 2:
                continue
            label, raw = cells[:2]
            if not re.fullmatch(r'\$?\s*\d[\d,]*(?:\.\d+)?', raw):
                continue
            value = float(raw.replace('$', '').replace(',', '').strip())
            if value <= 0:
                raise ValueError('S&P: invalid market value')
            if re.fullmatch(r'(?:19|20)\d{2}', label):
                annual[label + '-12-31'] = value
            else:
                match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s|$)', label)
                if match:
                    month, day, year = map(int, match.groups())
                    observed = dt.date(year, month, day)
                    # Last trading day can precede the calendar quarter-end.
                    if month not in (3, 6, 9, 12) or day < 25:
                        raise ValueError(f'S&P: unexpected quarter date {label}')
                    end = f'{year}-{month:02}-{calendar.monthrange(year, month)[1]}'
                    quarterly[end] = {'value': value, 'observed': observed.isoformat(), 'preliminary': 'prelim' in label.lower()}
    if not annual and not quarterly:
        raise ValueError('S&P: market-value table missing')
    return annual, quarterly


def collect_sp():
    soup = BeautifulSoup(get(SP_ARCHIVE).content, 'html.parser')
    links = sorted({urljoin(SP_ARCHIVE, a['href']) for a in soup.find_all('a', href=True)
                    if 'S&P 500' in a.get_text() and 'buyback' in a.get_text().lower()
                    and urlparse(urljoin(SP_ARCHIVE, a['href'])).hostname == 'press.spglobal.com'
                    and re.match(r'/20\d{2}-\d{2}-\d{2}-', urlparse(urljoin(SP_ARCHIVE, a['href'])).path)}, reverse=True)
    if not links:
        raise ValueError('S&P: release discovery failed')
    cache = read_cache('sp500')
    # A recent table carries about three years of quarterly data. Bootstrap spaced releases.
    selected = sorted(set(links[:3] + (links[::8] + links[-1:] if not cache else [])))
    succeeded = 0
    for url in selected:
        published = urlparse(url).path[1:11]
        try:
            annual, quarters = parse_sp_html(get(url).content)
        except ValueError:
            if url == links[0]:
                raise
            print(f'S&P older release without a supported market-value table: {published}')
            continue
        for key, rows in [('annual', annual), ('quarterly', quarters)]:
            saved = cache.setdefault(key, {})
            for date, row in rows.items():
                value = {'value': row} if key == 'annual' else row
                if published >= saved.get(date, {}).get('published', ''):
                    saved[date] = dict(value, url=url, published=published)
        succeeded += 1
    if not succeeded:
        raise ValueError('S&P: no releases collected')
    # A real Q4 closing observation is also a year-end value, without interpolation.
    for date, row in cache['quarterly'].items():
        if date.endswith('-12-31') and row['published'] > cache['annual'].get(date, {}).get('published', ''):
            cache['annual'][date] = dict(row)
    write_json(CACHE / 'sp500.json', cache)
    for key, cid, title in [('annual', 'market_sp500', 'S&P 500 시장가치 (연말)'),
                             ('quarterly', 'market_sp500_q', 'S&P 500 시장가치 (분기 말)')]:
        rows = cache[key]
        last = rows[max(rows)]
        points = [[date, round(row['value'] / 1000, 4)] for date, row in sorted(rows.items())]
        extra = {}
        if key == 'quarterly':
            extra = {'source_dates': {date: {'원문 거래일': row['observed']} for date, row in rows.items()}}
        save(cid, title, points, 'S&P Dow Jones Indices · 공식 Buybacks 보고서', last['url'],
             'S&P 공식 보고서의 MARKET VALUE 열을 추출한 시장가치. 지수 포인트나 ETF 순자산이 아니다.',
             '원문 Market Value 기준을 그대로 사용한다. 구성기업 전체 시총 합계와 유동주식 조정 지수 시총은 구분해야 하며 다른 기준의 값으로 이어 붙이지 않는다. 공개 표에 없는 기간은 추정하지 않는다.',
             [{'label': '집계값', 'value': 'S&P 500 Buybacks 보고서의 S&P 500, $ U.S. BILLIONS 표 중 MARKET VALUE. 매출·자사주 매입액·12개월 누적 행을 사용하지 않는다.'},
              {'label': '기준일', 'value': '연도 행 또는 실제 Q4 날짜 행의 연말 값. 중간 분기 값으로 연말을 추정하지 않는다.' if key == 'annual' else '실제 날짜 행의 분기 말 마지막 거래일 값. 휴일인 경우 달력 분기 말로 묶으며 툴팁에 원문 거래일도 표시한다. 잠정값은 후속 보고서에서 수정될 수 있다.'},
              {'label': '환산', 'value': '십억 달러 ÷ 1,000. 지수 가격을 고정 배수로 환산한 추정치가 아니다.'},
              {'label': '자동 갱신', 'value': '매일 공식 보도자료 목록을 확인하고 최신 표의 과거 정정치도 반영한다. 후속 발표가 없으면 마지막 확인된 관측값을 유지한다.'}],
             source_published=last['published'], methodology_url=SP_ARCHIVE, **extra)
        if key == 'quarterly':
            path = OUT / f'{cid}.json'
            doc = json.loads(path.read_text(encoding='utf-8'))
            doc.update(frequency='quarterly', year_labels=False, quarter_labels=True)
            write_json(path, doc)


def run():
    failures = []
    for collect in [collect_world_bank, collect_korea_boards, collect_esma, collect_sifma, collect_sp]:
        try:
            collect()
        except Exception as exc:
            failures.append(collect.__name__)
            print(f'ERROR {collect.__name__}: {exc} (published data preserved)')
    if failures:
        raise SystemExit('Source failures: ' + ', '.join(failures))


if __name__ == '__main__':
    run()

"""Small daily public-page refresh. Preserve history; never bypass access blocks."""
import copy
import datetime as dt
import json
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from import_yangshan import OUT, GRADES, CONTRACTS, validate

LIST_URL = 'https://list1.mysteel.com/article/p-2409----0201---------1.html'
SMM_URL = 'https://www.smm.com.cn/price'
KINDS = {'仓单': 'warehouse_warrant', '提单': 'bill_of_lading'}
CHINESE_GRADES = {'火法': 'pyrometallurgical', '湿法': 'hydrometallurgical'}


def get(url):
    # One attempt, no proxy/cookie/login or automatic retry on access restrictions.
    response = requests.get(url, timeout=(8, 25))
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return BeautifulSoup(response.text, 'html.parser')


def date_check(date, today):
    if dt.date.fromisoformat(date).isoformat() != date or date > today:
        raise ValueError('Invalid/future observation date')


def article_links(soup, today):
    if '安全验证' in soup.get_text():
        raise ValueError('Mysteel security verification page; no bypass attempted')
    found = {}
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=14)).isoformat()
    for a in soup.find_all('a'):
        if '上海美金铜市场升贴水' not in a.get_text():
            continue
        url = urljoin(LIST_URL, a.get('href', ''))
        match = re.fullmatch(r'https://youse\.mysteel\.com/a/(\d{2})(\d{2})(\d{2})\d{2}/[A-Za-z0-9]+\.html', url)
        if match:
            date = f'20{match[1]}-{match[2]}-{match[3]}'
            date_check(date, today)
            if date >= cutoff:
                found[url] = date
    if not found:
        raise ValueError('No recent public article links')
    return sorted(found, key=lambda u: (found[u], u), reverse=True)


def parse_mysteel(soup, url, today):
    title, meta = soup.find('h1'), soup.find('meta', attrs={'name': 'publish'})
    if not title or '上海美金铜市场升贴水' not in title.get_text() or not meta:
        raise ValueError('Missing article identity')
    match = re.search(r'\d{4}-\d{2}-\d{2}', meta.get('content', ''))
    if not match:
        raise ValueError('Missing publication date')
    date = match[0]
    date_check(date, today)
    stamp = re.search(r'(\d+)月(\d+)日', title.get_text())
    url_date = re.search(r'/a/(\d{6})\d{2}/', url)
    if not stamp or (int(stamp[1]), int(stamp[2])) != (int(date[5:7]), int(date[8:10])) or not url_date or url_date[1] != date[2:].replace('-', ''):
        raise ValueError('Article/title/URL dates disagree')
    tables = [t for t in soup.find_all('table') if all(k in t.get_text() for k in ('仓单', '提单', '最低价', '最高价', '中间价'))]
    if len(tables) != 1 or '美元/吨' not in soup.get_text():
        raise ValueError('Missing unique USD/tonne price table')
    rows, kind = [], None
    for tr in tables[0].find_all('tr'):
        cells = [c.get_text('', strip=True) for c in tr.find_all(['td', 'th'])]
        if not cells or '最低价' in cells:
            continue
        if cells[0] in KINDS:
            kind = KINDS[cells.pop(0)]
        if not kind or len(cells) != 6 or cells[0] not in CHINESE_GRADES:
            raise ValueError('Unexpected premium table columns')
        low, high, mid = [float(c.replace('−', '-')) for c in cells[1:4]]
        row = dict(date=date, provider='Mysteel', contract=kind, grade=CHINESE_GRADES[cells[0]],
                   low=low, high=high, midpoint=mid, unit='USD/metric tonne',
                   reported_change=cells[4], delivery_pricing_terms=cells[5], source_url=url)
        if not validate(row):
            raise ValueError('Premium range/midpoint mismatch')
        rows.append(row)
    if len(rows) != 4 or len({(r['contract'], r['grade']) for r in rows}) != 4:
        raise ValueError('Missing/duplicate contract or grade')
    return rows


def parse_smm(soup, today):
    rows = []
    for tr in soup.find_all('tr'):
        cells = [c.get_text('', strip=True) for c in tr.find_all(['td', 'th'])]
        if not cells or cells[0] not in ('洋山铜溢价(仓单)', '洋山铜溢价(提单)'):
            continue
        if len(cells) != 6 or cells[4] != '美元/吨':
            raise ValueError('SMM unit/columns changed')
        lo, hi = map(float, cells[1].split('~'))
        row = dict(date=cells[5], provider='SMM', contract=KINDS[cells[0][-3:-1]],
                   low=lo, high=hi, midpoint=float(cells[2]), unit='USD/metric tonne', source_url=SMM_URL)
        date_check(row['date'], today)
        if not validate(row):
            raise ValueError('Invalid SMM range/midpoint')
        rows.append(row)
    if len(rows) != 2 or len({r['contract'] for r in rows}) != 2 or len({r['date'] for r in rows}) != 1:
        raise ValueError('Missing, duplicate or misaligned SMM rows')
    return rows


def merge(doc, rows, today):
    result = copy.deepcopy(doc)
    if doc['unit'] != 'USD/톤':
        raise ValueError('Existing unit mismatch')
    values = {k: dict(v) for k, v in doc['series'].items()}
    old_records = {(r['date'], r['contract'], r.get('grade')): r for r in doc['source_records']}
    for row in rows:
        date_check(row['date'], today)
        if not validate(row):
            raise ValueError('Invalid incoming premium')
        key = (row['date'], row['contract'], row.get('grade'))
        old = old_records.get(key)
        if old and any(old[k] != row[k] for k in ('low', 'high', 'midpoint')):
            raise ValueError('Source revision conflicts with saved value; review required')
        name = GRADES[row['grade']] if 'grade' in row else CONTRACTS[row['contract']]
        if name not in values:
            raise ValueError('Unknown series')
        if row['date'] in values[name] and values[name][row['date']] != row['midpoint']:
            raise ValueError('Existing series conflict')
        values[name][row['date']] = row['midpoint']
        old_records[key] = row
    result['series'] = {k: sorted(v.items()) for k, v in values.items()}
    result['source_records'] = [old_records[k] for k in sorted(old_records)]
    result['updated'] = max(p[0] for points in result['series'].values() for p in points)
    result['fetched'] = today
    result['gaps'] = [dict(series=name, **{'from': a, 'to': b})
                      for name, points in result['series'].items()
                      for (a, _), (b, _) in zip(points, points[1:])
                      if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days > 7]
    result['highlight_gaps'] = True
    result['snapshot_history'] = True
    first = min(p[0] for points in result['series'].values() for p in points)
    result['history_note'] = (f'{first}부터 확인된 Mysteel 과거 관측값을 포함합니다.'
                            if any('grade' in row for row in rows) else
                            f'SMM의 수집 시작일은 {first}입니다. 그 이전 과거 이력은 확보하지 못했습니다.')
    result['note'] = ('공개 일일 가격표를 매일 KST 07:30 자동 확인합니다. 새 기준일이 없으면 기존 값을 유지합니다. '
                      '제공처별 시계열을 분리하며, 누락 날짜의 값은 생성하지 않습니다. 7일 초과 관측 간격은 점선입니다. '
                      '날짜·단위·가격 범위 불일치 및 기존 값과 충돌하는 수정치는 검토 전 반영하지 않습니다.')
    return result


def save(doc):
    path = OUT / (doc['id'] + '.json')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def run(today=None):
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    failures = []
    for provider, keys in [('Mysteel', list(CONTRACTS)), ('SMM', ['smm'])]:
        docs = [json.loads((OUT / f'comm_copper_yangshan_{key}.json').read_text(encoding='utf-8')) for key in keys]
        for doc in docs:
            doc['note'] = doc['note'].replace('일회 수집 자료이며 자동 갱신은 아직 설정하지 않았습니다.',
                '매일 KST 07:30 공개 자료를 확인합니다. 접근 제한 또는 검증 실패 시 기존 관측값을 보존합니다.')
        try:
            if provider == 'Mysteel':
                links = article_links(get(LIST_URL), today)
                known = {r['source_url'] for doc in docs for r in doc['source_records']}
                # Recheck the latest two for revisions; fill new/recent missing articles, capped at 8.
                last_stamp = min(doc['updated'] for doc in docs).replace('-', '')[2:]
                chosen = [url for i, url in enumerate(links)
                          if i < 2 or (url not in known and re.search(r'/a/(\d{6})', url)[1] >= last_stamp)][:8]
                rows = []
                for url in chosen:
                    time.sleep(1)
                    rows.extend(parse_mysteel(get(url), url, today))
            else:
                rows = parse_smm(get(SMM_URL), today)
            prepared = []
            for doc, key in zip(docs, keys):
                selected = rows if key == 'smm' else [r for r in rows if r['contract'] == key]
                if not selected:
                    raise ValueError('No validated observations')
                if max(r['date'] for r in selected) < doc['updated']:
                    raise ValueError('Provider latest date regressed')
                updated = merge(doc, selected, today)
                if key == 'smm':
                    updated['name'] = '양산 프리미엄 · SMM 최신값 누적'
                    updated['description'] = 'SMM 창고증권·선하증권 평균값을 수집한 날짜부터 누적합니다. 과거 이력은 미확보이며, Mysteel 과거 그래프와는 별도 자료입니다.'
                updated['collection_status'] = dict(checked=today, ok=True, message='공개 자료 확인 완료 · 자료 기준일 ' + updated['updated'])
                prepared.append(updated)
            for doc in prepared:
                save(doc)
            print(provider, 'OK', prepared[0]['updated'])
        except Exception as error:
            for doc in docs:
                doc['collection_status'] = dict(checked=today, ok=False, message='자동 확인 실패 · 기존 관측값 유지')
                save(doc)
            failures.append(f'{provider}: {error}')
    if failures:
        raise RuntimeError('; '.join(failures))


if __name__ == '__main__':
    run()

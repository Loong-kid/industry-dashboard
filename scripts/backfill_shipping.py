"""명시적으로 실행하는 해운 과거 자료 보강. 기존 관측값을 덮어쓰지 않는다.

python scripts/backfill_shipping.py
원문은 작업 공간의 shipping-history-cache에 저장하며, 날짜별 출처와 감사 결과를 기록한다.
"""
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from common import ROOT, UA, collection_date, load_indicator, merge_points, save_indicator
from fetchers import kcla

CACHE = ROOT.parent / 'shipping-history-cache'


def get(url, params):
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = CACHE / (key + '.html')
    CACHE.mkdir(exist_ok=True)
    if not path.exists():
        r = requests.get(url, params=params, headers=UA, timeout=30)
        r.raise_for_status()
        path.write_bytes(r.content)
        time.sleep(0.25)
    content = path.read_bytes()
    return content, hashlib.sha256(content).hexdigest()


def extend(ind_id, points, sources):
    doc = load_indicator('shipping', ind_id)
    name = ind_id.upper()
    existing = dict(doc['series'].get(name, []))
    conflicts = [[d, existing[d], v] for d, v in points.items() if d in existing and existing[d] != v]
    added = merge_points(doc, name, [(d, v) for d, v in points.items() if d not in existing])
    # 백필은 현재 갱신 실패 상태를 해제하거나 마지막 성공 수집일을 바꾸지 않는다.
    previous_status, fetched = doc.get('collection_status'), doc.get('fetched')
    save_indicator('shipping', doc, data_date=True)
    if previous_status:
        doc['collection_status'] = previous_status
    if fetched:
        doc['fetched'] = fetched
    (ROOT / 'data' / 'shipping' / (ind_id + '.json')).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    audit = {'added': added, 'start': doc['series'][name][0][0], 'end': doc['series'][name][-1][0],
             'count': len(doc['series'][name]), 'overlap_conflicts_preserved': conflicts, 'sources': sources}
    print(ind_id, audit['start'], audit['end'], 'added', added, 'conflicts', len(conflicts), flush=True)
    return audit


def main():
    audit = {'checked': collection_date(), 'policy': '기존 관측치 보존, 신규 날짜만 추가. 결측/휴일 보간 없음.', 'indicators': {}}
    points = {name: {} for name in ['scfi', 'ccfi', 'bdi']}
    sources = {name: [] for name in points}
    for start in range(2014, date.today().year + 1, 3):
        end = min(start + 2, date.today().year)
        for group, ids in [('CFI', ['scfi', 'ccfi']), ('BDI', ['bdi'])]:
            params = {'command': 'LIST', 'S_TRANSIN_SE': group, 'S_YEAR': str(start), 'F_YEAR': str(end)}
            html, key = get(kcla.NLIC_URL, params)
            for identifier in ids:
                parsed = kcla.parse_nlic(html, identifier)
                if any(not start <= int(d[:4]) <= end for d, _ in parsed):
                    raise ValueError('NLIC 요청 기간과 반환 날짜 불일치')
                points[identifier].update(parsed)
                sources[identifier].append({'url': kcla.NLIC_URL, 'params': params, 'sha256': key, 'count': len(parsed)})
            print('NLIC', group, start, end, len(parsed), flush=True)
    for identifier in points:
        audit['indicators'][identifier] = extend(identifier, points[identifier], sources[identifier])
    html, key = get(kcla.KSG_HRCI_URL, {})
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    match = re.search(r'전체\s*(\d+)\s*페이지', text)
    if not match or not 1 <= int(match[1]) <= 500:
        raise ValueError('KSG 과거 페이지 개수 확인 불가')
    total = int(match[1])
    historical = dict(kcla.parse_ksg_hrci(html))
    src = [{'url': kcla.KSG_HRCI_URL, 'params': {}, 'sha256': key}]
    for page in range(2, total + 1):
        params = {'pageNum': str(page), 'schEDate': date.today().isoformat()}
        html, key = get(kcla.KSG_HRCI_URL, params)
        page_points = kcla.parse_ksg_hrci(html)
        if any(d in historical for d, _ in page_points):
            raise ValueError('KSG 페이지 중복: 요청한 페이지 미반영')
        historical.update(page_points)
        src.append({'url': kcla.KSG_HRCI_URL, 'params': params, 'sha256': key})
        if page % 10 == 0:
            print('HRCI page', page, '/', total, 'oldest', min(historical), flush=True)
    audit['indicators']['hrci'] = extend('hrci', historical, src)
    (ROOT / 'data' / 'shipping' / 'history_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()

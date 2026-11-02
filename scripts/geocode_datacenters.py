# -*- coding: utf-8 -*-
"""국내 데이터센터 주소 → 좌표 (data/sites/dc_coords.json). 지구본 탭의 데이터센터 레이어에 쓴다.

OpenStreetMap Nominatim으로 주소를 찾는다. 번지까지 찾히는 경우가 드물어 읍·면·동, 시·군·구 순으로
범위를 넓히고, 실제로 찾은 범위를 accuracy에 남긴다. 이미 찾은 주소는 다시 묻지 않으며 한 번에
MAX_NEW건만 묻는다(Nominatim 사용 정책: 초당 1건 이하).

    python scripts/geocode_datacenters.py
"""
import datetime as dt
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FACILITIES = ROOT / 'data/datacenter/dc_facilities.json'
COORDS = ROOT / 'data/sites/dc_coords.json'
API = 'https://nominatim.openstreetmap.org/search'
HEADERS = {'User-Agent': 'industry-dashboard personal research (github.com/Loong-kid/industry-dashboard)'}
MAX_NEW = 200
# 2026 개편 이름은 OSM에 아직 없을 수 있다. 위치를 찾는 용도로만 옛 이름으로 바꾼다.
OLD_NAMES = {'전남광주통합특별시': '전라남도', '서해구': '서구', '제물포구': '중구', '영종구': '중구', '검단구': '서구'}
SHORT_SIDO = {'경기': '경기도', '강원': '강원도', '충북': '충청북도', '충남': '충청남도', '전북': '전라북도', '전남': '전라남도',
              '경북': '경상북도', '경남': '경상남도', '서울시': '서울특별시', '인천시': '인천광역시', '부산시': '부산광역시',
              '대구시': '대구광역시', '광주시': '광주광역시', '대전시': '대전광역시', '울산시': '울산광역시', '세종시': '세종특별자치시',
              '강원특별자치도': '강원도', '전북특별자치도': '전라북도'}


def tokens(location):
    parts = re.sub(r'[\s\xa0]+', ' ', location).strip()
    parts = re.sub(r'(?<=[가-힣]시)(?=[가-힣]+구(?: |$))', ' ', parts).split(' ')  # 고양시덕양구 → 고양시 덕양구
    return [OLD_NAMES.get(part, part) for part in ([SHORT_SIDO.get(parts[0], parts[0])] + parts[1:])]


def is_lot(token):
    return bool(re.fullmatch(r'(?:산\s*)?\d+(?:-\d+)?(?:번지)?', token))


def queries(location):
    """넓어지는 순서의 (검색어, 범위). 번지 → 읍·면·동·리 → 시·군·구."""
    parts = tokens(location)
    rest = [part for part in parts if not is_lot(part)]
    steps = []
    if len(rest) != len(parts):
        steps.append((' '.join(parts), 'lot'))
    steps.append((' '.join(rest), 'town'))
    # 리·가·로 단위를 하나씩 떼며 넓힌다.
    trimmed = rest[:]
    while len(trimmed) > 1 and not re.search(r'(?:시|군|구)$', trimmed[-1]):
        trimmed = trimmed[:-1]
        steps.append((' '.join(trimmed), 'town' if re.search(r'(?:읍|면|동|리|가)$', trimmed[-1]) else 'county'))
    if trimmed:
        steps.append((' '.join(trimmed), 'county'))
    # OSM이 새 이름을 쓰거나 원장 시·도가 틀린 경우(전남광주통합특별시, 부산시 오정구) 시·도 없이 찾는다.
    if len(rest) > 2:
        steps.append((' '.join(rest[1:]), 'town'))
        steps.append((' '.join(rest[1:2]), 'county'))
    seen, unique = set(), []
    for query, level in steps:
        if query and query not in seen:
            seen.add(query)
            unique.append((query, level))
    return unique


def accuracy_of(level, hit):
    if level == 'lot' and hit.get('class') in ('building', 'place') and hit.get('type') in ('house', 'building', 'yes', 'plot'):
        return 'facility'
    return 'county' if level == 'county' else 'town'


def lookup(session, location):
    for query, level in queries(location):
        time.sleep(1.1)
        response = session.get(API, params={'format': 'jsonv2', 'limit': 1, 'countrycodes': 'kr', 'q': query}, timeout=30)
        response.raise_for_status()
        rows = response.json()
        if rows:
            return {'lat': round(float(rows[0]['lat']), 5), 'lon': round(float(rows[0]['lon']), 5),
                    'accuracy': accuracy_of(level, rows[0]), 'query': query}
    return None


def coord_key(record):
    return record.get('address_key') or re.sub(r'[\s\xa0]+', '', record['location'])


def save(doc):
    doc['geocoded'] = dt.date.today().isoformat()
    doc['coords'] = dict(sorted(doc['coords'].items()))
    COORDS.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def run():
    records = json.loads(FACILITIES.read_text(encoding='utf-8'))['records']
    doc = json.loads(COORDS.read_text(encoding='utf-8')) if COORDS.exists() else {
        'description': '지구본 탭에 국내 데이터센터를 찍기 위한 좌표. 원장 주소를 OpenStreetMap Nominatim으로 찾았다. accuracy가 town·county면 시설 위치가 아니라 그 지역 중심이다. 정확한 좌표를 알게 되면 lat·lon을 고치고 accuracy를 facility로 바꾼다.',
        'source': 'OpenStreetMap Nominatim (© OpenStreetMap contributors, ODbL)', 'coords': {}}
    wanted = {}
    for record in records:
        wanted.setdefault(coord_key(record), record['location'])
    todo = [(key, location) for key, location in wanted.items() if key not in doc['coords']][:MAX_NEW]
    session = requests.Session()
    session.headers.update(HEADERS)
    failed = []
    for index, (key, location) in enumerate(todo, 1):
        hit = lookup(session, location)
        if hit:
            doc['coords'][key] = hit
        else:
            failed.append(location)
        if index % 25 == 0:
            save(doc)
    if todo:
        save(doc)
    print(f'Data centre coordinates: {len(doc["coords"])} known, {len(todo)} looked up, {len(failed)} not found')
    for location in failed:
        print('  not found:', location)


if __name__ == '__main__':
    run()

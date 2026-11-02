# -*- coding: utf-8 -*-
"""한국 행정구역 경계 → data/sites/korea_sido.json, korea_sigungu.json (지구본 확대 시 표시).

원자료: southkorea/southkorea-maps, 통계청 센서스 경계 2018 (TopoJSON). 경계는 거의 바뀌지 않아
수집에 넣지 않고 필요할 때만 다시 돌린다. 2018 이후 개편(2023 군위군 대구 편입, 2026 인천 구 개편 등)은
경계에 반영돼 있지 않아 화면 출처에 그대로 밝힌다.

    python scripts/build_korea_admin.py
"""
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/sites'
BASE = 'https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2018/json/'
SOURCE = '통계청 센서스 경계 2018 · southkorea-maps'
SOURCE_URL = 'https://github.com/southkorea/southkorea-maps'
# 지구본 라벨은 짧게 쓴다. 긴 이름은 겹쳐서 빠지기 쉽다. full은 현재 공식 이름.
SIDO = {'서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구', '인천광역시': '인천', '광주광역시': '광주', '대전광역시': '대전',
        '울산광역시': '울산', '세종특별자치시': '세종', '경기도': '경기', '강원도': '강원', '충청북도': '충북', '충청남도': '충남',
        '전라북도': '전북', '전라남도': '전남', '경상북도': '경북', '경상남도': '경남', '제주특별자치도': '제주'}
FULL = {'강원도': '강원특별자치도', '전라북도': '전북특별자치도'}


def short_name(name):
    """시·도는 약칭, 일반구는 구 이름만(성남시분당구 → 분당구)."""
    if name in SIDO:
        return SIDO[name]
    match = re.fullmatch(r'.+시(.+구)', name)
    return match[1] if match else name


def decode_arcs(topo):
    sx, sy = topo['transform']['scale']
    tx, ty = topo['transform']['translate']
    arcs = []
    for arc in topo['arcs']:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x * sx + tx, y * sy + ty))
        arcs.append(points)
    return arcs


def ring_points(ring, arcs):
    points = []
    for index in ring:
        arc = arcs[index] if index >= 0 else arcs[~index][::-1]
        points.extend(arc[1:] if points else arc)
    return points


def label_point(geometry, arcs):
    """가장 넓은 고리의 넓이 중심. 섬이 많은 시·군에서도 본토 위에 놓인다."""
    polygons = geometry['arcs'] if geometry['type'] == 'MultiPolygon' else [geometry['arcs']]
    best, best_area = None, -1.0
    for polygon in polygons:
        points = ring_points(polygon[0], arcs)
        twice, cx, cy = 0.0, 0.0, 0.0
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            cross = x0 * y1 - x1 * y0
            twice += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        if twice and abs(twice) > best_area:
            best_area = abs(twice)
            best = (cx / (3 * twice), cy / (3 * twice))
    return best


def build(filename, out_name):
    response = requests.get(BASE + filename, timeout=60)
    response.raise_for_status()
    topo = response.json()
    arcs = decode_arcs(topo)
    labels = []
    geometries = next(iter(topo['objects'].values()))['geometries']
    for geometry in geometries:
        lon, lat = label_point(geometry, arcs)
        name = geometry['properties']['name']
        labels.append({'n': short_name(name), 'full': FULL.get(name, name), 'code': geometry['properties']['code'], 'lat': round(lat, 4), 'lon': round(lon, 4)})
    doc = {'source': SOURCE, 'source_url': SOURCE_URL, 'base_year': 2018, 'labels': labels, 'topology': topo}
    (OUT / out_name).write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(out_name, len(labels), 'areas')


if __name__ == '__main__':
    build('skorea-provinces-2018-topo-simple.json', 'korea_sido.json')
    build('skorea-municipalities-2018-topo-simple.json', 'korea_sigungu.json')

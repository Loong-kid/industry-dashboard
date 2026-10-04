"""Harper Petersen의 공개 HARPEX 차트. HRCI와 별도 지수로 보관한다."""
import json
import math
from datetime import date

import requests
from bs4 import BeautifulSoup

from common import UA, load_indicator, merge_points, save_indicator

URL = "https://www.harperpetersen.com/container"


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    charts = soup.select('.chart_harpex[data-json]')
    if not charts:
        raise ValueError("HARPEX 공개 차트 없음")
    points = {}
    for chart in charts:
        data = json.loads(chart['data-json'])
        if not data.get('harpex'):
            raise ValueError("HARPEX 차트 자료 없음")
        for row in data['harpex']:
            d = date.fromisoformat(row['date'].split('T')[0]).isoformat()
            v = row['value']
            if not isinstance(v, (float, int)) or not math.isfinite(v) or v <= 0 or d > date.today().isoformat():
                raise ValueError("HARPEX 날짜/값 비정상")
            if d in points and points[d] != v:
                raise ValueError("HARPEX 공개 차트 간 값 불일치")
            points[d] = v
    return sorted(points.items())


def run():
    r = requests.get(URL, headers=UA, timeout=30)
    r.raise_for_status()
    points = parse_page(r.content)
    doc = load_indicator('shipping', 'harpex')
    doc.update(name="HARPEX (컨테이너선 용선료 지수)", unit="pt", frequency="weekly",
               source="Harper Petersen", source_url=URL + '#harpex', default_series=['HARPEX'],
               data_stale_days=21, latest_source_date=points[-1][0],
               note="컨테이너선의 6~12개월 용선료를 주간 평가하는 지수입니다. HRCI와 계산 방식이 다른 별도 지수이며, 과거 HRCI와 연결하지 않습니다. 발표사의 공개 24개월 차트를 매일 누적합니다. 전체 과거 시계열은 발표사 구독 자료입니다.")
    merge_points(doc, 'HARPEX', points)
    save_indicator('shipping', doc, data_date=True)

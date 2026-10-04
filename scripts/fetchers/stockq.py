# -*- coding: utf-8 -*-
"""StockQ 공개 발틱 지수: 현재값과 최근 20거래일을 발표일별 누적한다."""
import base64
import math
import re
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import UA, load_indicator, merge_points, save_indicator, to_float

INDICES = {
    "bdi": ("BDI.php", "BDI (발틱 건화물 운임지수)"),
    "bdti": ("BDTI.php", "BDTI (발틱 더티탱커 운임지수)"),
    "bcti": ("BCTI.php", "BCTI (발틱 클린탱커 운임지수)"),
}


def infer_year(mm: int, dd: int = 1) -> int:
    """MM/DD에 연도가 없으므로 오늘 기준으로 추정 (연말·연초 경계 처리)."""
    today = date.today()
    year = today.year
    if date(year, mm, dd) > today:  # 미래 날짜라면 직전 연도
        year -= 1
    return year


def render_value(payload):
    """StockQ 공개 sq-obfuscate.js의 화면 숫자 표시 방식. 코드를 실행하지 않고 값만 읽는다."""
    try:
        fields = base64.b64decode(payload, validate=True).decode("ascii").split("|")
        if len(fields) != 6:
            raise ValueError("필드 개수 변경")
        seed = int(fields.pop(0))
        if not 0 < seed < 2147483647:
            raise ValueError("seed 범위")
        def random():
            nonlocal seed
            seed = seed * 48271 % 2147483647
            return seed / 2147483647
        random(); random()
        order = [0, 1, 2]
        for i in [2, 1]:
            j = math.floor(random() * (i + 1))
            order[i], order[j] = order[j], order[i]
        random()
        fake1 = math.floor(random() * 4)
        random()
        fake2 = math.floor(random() * 5)
        fields.pop(fake2)
        fields.pop(fake1)
        value = ["", "", ""]
        for i in range(3):
            value[order[i]] = fields[i]
        return "".join(value)
    except (ValueError, IndexError, UnicodeError) as exc:
        raise ValueError("StockQ 표시 숫자 형식 변경") from exc


def cell_value(cell):
    node = cell.select_one("[data-sq]")
    text = render_value(node["data-sq"]) if node else cell.get_text(strip=True)
    value = to_float(text)
    if value is None or not math.isfinite(value) or value <= 0:
        raise ValueError("StockQ 지수값 없음/비정상")
    return value


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    points = {}
    for table in soup.select("table.indexpagetable"):
        for row in table.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            for i, cell in enumerate(cells[:-1]):
                text = cell.get_text(strip=True)
                if re.fullmatch(r"\d{4}/\d{2}/\d{2}", text):
                    d = date.fromisoformat(text.replace("/", "-")).isoformat()
                    points[d] = cell_value(cells[i + 1])
    quote = soup.select_one(".stockq-desktop-quote")
    if quote:
        price = quote.select_one(".stockq-desktop-quote__price")
        timestamp = quote.select_one(".stockq-desktop-quote__time")
        match = re.search(r"(\d{2})/(\d{2})", timestamp.get_text()) if timestamp else None
        if not price or not match:
            raise ValueError("StockQ 최신값/발표일 구조 변경")
        mm, dd = map(int, match.groups())
        d = date(infer_year(mm, dd), mm, dd).isoformat()
        value = cell_value(price)
        if d in points and points[d] != value:
            raise ValueError("StockQ 최신값과 날짜별 표 값 불일치")
        points[d] = value
    if not points:
        raise ValueError("StockQ 날짜별 지수 0건 파싱됨")
    return sorted(points.items())


def fetch_one(ind_id: str, page: str, name: str):
    url = f"https://en.stockq.org/index/{page}"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    points = parse_page(r.content)

    doc = load_indicator("shipping", ind_id)
    doc.update({
        "name": name,
        "unit": "pt",
        "frequency": "daily",
        "source": "Baltic Exchange (StockQ 게시)",
        "source_url": url,
        "default_series": [ind_id.upper()],
        "data_stale_days": 10,
        "latest_source_date": points[-1][0],
        "highlight_gaps": True,
        "note": "최근 20거래일 공개 자료를 매일 누적합니다. 장기 수집 중단으로 남은 과거 공백은 보간하지 않으며, 7일을 넘는 관측 간격은 점선으로 표시합니다.",
    })
    added = merge_points(doc, ind_id.upper(), points)
    save_indicator("shipping", doc, data_date=True)
    print(f"  {ind_id.upper()} {points[-1][0]} = {points[-1][1]} ({added} new points)")


def run():
    for ind_id, (page, name) in INDICES.items():
        fetch_one(ind_id, page, name)


if __name__ == "__main__":
    run()

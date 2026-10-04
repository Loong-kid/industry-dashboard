# -*- coding: utf-8 -*-
"""StockQ 공개 발틱 지수: 5년 차트와 최근 20거래일을 발표일별 누적한다."""
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


def parse_chart(script):
    """공개 5년 차트의 Price 열만 읽는다. MA 열이나 JS 코드는 실행하지 않는다."""
    if not re.search(r"\['Time',\s*'Price',\s*'MA20'", script):
        raise ValueError("StockQ 과거 차트 열 구조 변경")
    rows = re.findall(r"\[new Date\('([^']+)'\),\s*([^,\]]+),[^\]]*\]", script)
    if not rows or len(rows) != script.count("new Date("):
        raise ValueError("StockQ 과거 차트 날짜/값 파싱 불일치")
    points = {}
    months = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
    for timestamp, raw in rows:
        match = re.fullmatch(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", timestamp)
        if not match or match[1] not in months:
            raise ValueError("StockQ 과거 차트 날짜 형식 변경")
        d = date(int(match[3]), months[match[1]], int(match[2])).isoformat()
        value = to_float(raw)
        if value is None or not math.isfinite(value) or value <= 0 or d > date.today().isoformat() or d in points:
            raise ValueError("StockQ 과거 차트 날짜/값 비정상")
        points[d] = value
    return sorted(points.items())


def fetch_history(ind_id):
    url = f"https://www.stockq.org/index/js/{ind_id.upper()}_sma.js"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    match = re.search(r'"5y":"(https://www\.stockq\.org/index/chart-data\.php\?[^"\s]+)"', r.text)
    if not match or f"id={ind_id.upper()}&type=sma&range=5y&" not in match[1]:
        raise ValueError("StockQ 공개 차트 링크 변경")
    # 공개 페이지가 안내하는 버전 포함 URL과 Referer를 그대로 사용한다.
    r = requests.get(match[1], headers={**UA, "Referer": f"https://www.stockq.org/index/{ind_id.upper()}.php"}, timeout=30)
    r.raise_for_status()
    return parse_chart(r.text), match[1]


def fetch_one(ind_id: str, page: str, name: str):
    url = f"https://en.stockq.org/index/{page}"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    points = parse_page(r.content)
    history, history_url = fetch_history(ind_id)
    overlap = dict(history)
    if any(d in overlap and overlap[d] != v for d, v in points):
        raise ValueError("StockQ 날짜별 표와 과거 차트 값 불일치: 저장 취소")

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
        "history_source": "StockQ 공개 5년 차트 (Price 원자료)",
        "history_source_url": history_url,
        "note": "공개 5년 차트의 실제 지수값과 최근 20거래일을 날짜별 검증 후 누적합니다. 이동평균은 사용하지 않습니다. 이미 저장한 과거 이력은 보존하며, 7일을 넘는 관측 간격은 점선으로 표시합니다.",
    })
    added_history = merge_points(doc, ind_id.upper(), history)
    added = merge_points(doc, ind_id.upper(), points)
    save_indicator("shipping", doc, data_date=True)
    print(f"  {ind_id.upper()} {points[-1][0]} = {points[-1][1]} ({added + added_history} new points)")


def run():
    for ind_id, (page, name) in INDICES.items():
        fetch_one(ind_id, page, name)


if __name__ == "__main__":
    run()

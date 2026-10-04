# -*- coding: utf-8 -*-
"""한국관세물류협회(KCLA) 지수 — SCFI / CCFI / HRCI (주간), BDI (일간).

페이지에 올해 치 주간 테이블(1행: 날짜, 2행: 지수)이 있어 크롤링 후 누적 머지.
"""
import re
import math
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import UA, load_indicator, merge_points, norm_date, save_indicator, to_float

PAGES = {
    "ccfi": ("4-1_2.asp", "CCFI (중국 수출컨테이너 운임지수)", "Shanghai Shipping Exchange"),
    "scfi": ("4-1_3.asp", "SCFI (상하이 컨테이너 운임지수)", "Shanghai Shipping Exchange"),
    "hrci": ("4-1_4.asp", "HRCI (하우로빈슨 컨테이너선 용선지수)", "Howe Robinson"),
    "bdi": ("4-1_5.asp", "BDI (발틱 건화물 운임지수)", "Baltic Exchange"),
}
NLIC_URL = "https://www.nlic.go.kr/nlic/transInPortCt.action"
KSG_HRCI_URL = "https://www.ksg.co.kr/shippingGraph/hrci_graph.jsp"


def parse_table(html, identifier):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", attrs={"summary": re.compile(rf"^{re.escape(identifier)}$", re.I)})
    if not table:
        raise ValueError(f"{identifier}: 해당 지수 테이블 없음")
    rows = table.find_all("tr")
    if len(rows) != 2:
        raise ValueError(f"{identifier}: 날짜/값 행 구조 변경")
    dates = [cell.get_text(strip=True) for cell in rows[0].find_all("td") if cell.get("rowspan") is None]
    values = [cell.get_text(strip=True) for cell in rows[1].find_all("td")]
    if not dates or len(dates) != len(values):
        raise ValueError(f"{identifier}: 날짜/값 개수 불일치")
    points = []
    for d, value in zip(dates, values):
        if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", d):
            raise ValueError(f"{identifier}: 잘못된 발표일 {d}")
        parsed = to_float(value)
        if parsed is None or not math.isfinite(parsed) or parsed <= 0:
            raise ValueError(f"{identifier}: 잘못된 지수값 {value}")
        points.append((norm_date(d), parsed))
    return points


def parse_nlic(html, identifier):
    """공식 NLIC의 SCFI/CCFI 또는 BDI 자료. 날짜/지수 블록의 정렬을 검증한다."""
    expected = ["BDI"] if identifier == "bdi" else ["SCFI", "CCFI"]
    if identifier not in {"scfi", "ccfi", "bdi"}:
        raise ValueError("NLIC 지원 지수 아님")
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("div.box.W_m_1000px")
    if not box:
        raise ValueError("NLIC 운임 표 없음")
    headers = [li.get_text(strip=True) for li in soup.select(".con_list_2")]
    if headers != expected:
        raise ValueError("NLIC 지수 열 순서 변경")
    values = [li.get_text(strip=True) for li in box.select("li")]
    count = sum(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) for value in values)
    if not count or len(values) != count * (len(expected) + 1) or not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in values[:count]):
        raise ValueError("NLIC 날짜/지수 블록 개수 불일치")
    offset = count if identifier in {"scfi", "bdi"} else count * 2
    points = [(d, to_float(v)) for d, v in zip(values[:count], values[offset:offset + count])]
    if any(v is None or not math.isfinite(v) or v <= 0 for _, v in points):
        raise ValueError("NLIC 지수값 결측/비정상")
    return points


def parse_ksg_hrci(html):
    soup = BeautifulSoup(html, "html.parser")
    table = next((t for t in soup.find_all("table") if t.find("caption") and t.caption.get_text(strip=True) == "hrci 그래프"), None)
    if not table or [t.get_text(strip=True) for t in table.select("thead th")][:2] != ["날짜", "Index"]:
        raise ValueError("KSG HRCI 표 구조 변경")
    points = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 16 or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", cells[0].get_text(strip=True)):
            raise ValueError("KSG HRCI 날짜/열 구조 변경")
        value = to_float(cells[1].get_text(strip=True))
        if value is None or not math.isfinite(value) or value <= 0:
            raise ValueError("KSG HRCI 값 비정상")
        points.append((norm_date(cells[0].get_text(strip=True)), value))
    if not points:
        raise ValueError("KSG HRCI 자료 없음")
    return points


def fetch_one(ind_id: str, page: str, name: str, publisher: str):
    url = f"https://www.kcla.kr/web/inc/html/{page}"
    fallback = False
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        points = parse_table(r.content, ind_id.upper())
    except (requests.RequestException, ValueError):
        if ind_id == "hrci":
            r = requests.get(KSG_HRCI_URL, headers=UA, timeout=30)
            r.raise_for_status()
            points = parse_ksg_hrci(r.content)
        elif ind_id in {"scfi", "ccfi", "bdi"}:
            r = requests.get(NLIC_URL, params={"S_TRANSIN_SE": "BDI" if ind_id == "bdi" else "CFI"}, headers=UA, timeout=30)
            r.raise_for_status()
            points = parse_nlic(r.content, ind_id)
            fallback = True
            print(f"  {ind_id.upper()}: KCLA 직접 조회 실패 → 국가물류통합정보센터 보완")
        else:
            raise

    doc = load_indicator("shipping", ind_id)
    doc.update({
        "name": name,
        "unit": "pt",
        "frequency": "daily" if ind_id == "bdi" else "weekly",
        "source": f"{publisher} (KCLA·국가물류통합정보센터 게시)" if fallback else f"{publisher} (한국관세물류협회 게시)",
        "source_url": NLIC_URL if fallback else url,
        "default_series": [ind_id.upper()],
        "data_stale_days": 10 if ind_id == "bdi" else 21,
        "latest_source_date": max(d for d, _ in points),
    })
    if fallback:
        doc["note"] = "KCLA 직접 조회가 어려울 때 국가물류통합정보센터의 동일 지수로 보완합니다. 보완 자료 발표일: " + doc["latest_source_date"] + ". 기존 누적 자료는 보존합니다."
    elif ind_id in {"scfi", "ccfi"}:
        doc.pop("note", None)
    if ind_id == "hrci":
        doc.update(source="Howe Robinson (KCLA·코리아쉬핑가제트 게시)", source_url=KSG_HRCI_URL,
                   note="컨테이너선의 용선료(선박 임대료)를 나타내는 지수입니다. 화물 운송 운임인 SCFI·CCFI와 구분됩니다. 국내 공개 게시 자료의 최신 발표일은 " + doc['latest_source_date'] + ". 자료가 오래됐다는 경고가 표시되면 현재 용선시장 추적에는 별도 HARPEX 지표를 참고하세요.")
    merge_points(doc, ind_id.upper(), points)
    save_indicator("shipping", doc, data_date=True)


def run():
    for ind_id, (page, name, publisher) in PAGES.items():
        fetch_one(ind_id, page, name, publisher)


if __name__ == "__main__":
    run()

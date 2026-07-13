# -*- coding: utf-8 -*-
"""한국관세물류협회(KCLA) 운임지수 페처 — SCFI / CCFI / KCFI (주간).

페이지에 올해 치 주간 테이블(1행: 날짜, 2행: 지수)이 있어 크롤링 후 누적 머지.
"""
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import UA, load_indicator, merge_points, norm_date, save_indicator, to_float

PAGES = {
    "ccfi": ("4-1_2.asp", "CCFI (중국 수출컨테이너 운임지수)", "Shanghai Shipping Exchange"),
    "scfi": ("4-1_3.asp", "SCFI (상하이 컨테이너 운임지수)", "Shanghai Shipping Exchange"),
    "hrci": ("4-1_4.asp", "HRCI (하우로빈슨 컨테이너선 용선지수)", "Howe Robinson"),
    "bdi": ("4-1_5.asp", "BDI (발틱 건화물 운임지수)", "Baltic Exchange"),
}


def fetch_one(ind_id: str, page: str, name: str, publisher: str):
    url = f"https://www.kcla.kr/web/inc/html/{page}"
    r = requests.get(url, headers=UA, timeout=30, verify=True)
    r.raise_for_status()
    html = r.text

    # 지수 테이블: <td rowspan="2">지수</td> 다음 1행이 날짜, 다음 행이 값
    m = re.search(r'<table[^>]*summary="[^"]*"[^>]*>(.*?)</table>', html, re.S)
    if not m:
        raise RuntimeError(f"{ind_id}: 테이블을 찾지 못함 (페이지 구조 변경?)")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S)
    dates, vals = [], []
    for row in rows:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        for c in cells:
            if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", c):
                dates.append(norm_date(c))
            elif re.fullmatch(r"[\d,]+\.?\d*", c) and to_float(c) is not None:
                vals.append(to_float(c))
    n = min(len(dates), len(vals))
    if n == 0:
        raise RuntimeError(f"{ind_id}: 데이터 0건 파싱됨")

    doc = load_indicator("shipping", ind_id)
    doc.update({
        "name": name,
        "unit": "pt",
        "frequency": "weekly",
        "source": f"{publisher} (한국관세물류협회 게시)",
        "source_url": url,
        "default_series": [ind_id.upper()],
    })
    merge_points(doc, ind_id.upper(), list(zip(dates[:n], vals[:n])))
    save_indicator("shipping", doc)


def run():
    for ind_id, (page, name, publisher) in PAGES.items():
        fetch_one(ind_id, page, name, publisher)


if __name__ == "__main__":
    run()

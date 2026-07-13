# -*- coding: utf-8 -*-
"""StockQ 발틱 지수 페처 — BDI / BDTI / BCTI (일간 최신값 1개씩 누적).

히스토리를 주지 않으므로 매일 실행해서 쌓는 방식. (Baltic Exchange 원본은 유료)
"""
import re
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import UA, load_indicator, merge_points, save_indicator, to_float

INDICES = {
    "bdi": ("BDI.php", "BDI (발틱 건화물 운임지수)"),
    "bdti": ("BDTI.php", "BDTI (발틱 더티탱커 운임지수)"),
    "bcti": ("BCTI.php", "BCTI (발틱 클린탱커 운임지수)"),
}


def infer_year(mm: int) -> int:
    """MM/DD에 연도가 없으므로 오늘 기준으로 추정 (연말·연초 경계 처리)."""
    today = date.today()
    year = today.year
    if mm > today.month + 1:  # 예: 오늘 1월인데 12월 데이터면 작년
        year -= 1
    return year


def fetch_one(ind_id: str, page: str, name: str):
    url = f"https://en.stockq.org/index/{page}"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    html = r.text

    val_m = re.search(r"align=center>([\d,]+\.\d+)</td>", html)
    date_m = re.search(r">(\d{2}/\d{2})</td>", html)
    if not (val_m and date_m):
        raise RuntimeError(f"{ind_id}: 값/날짜 파싱 실패 (페이지 구조 변경?)")
    value = to_float(val_m.group(1))
    mm, dd = map(int, date_m.group(1).split("/"))
    d = f"{infer_year(mm)}-{mm:02d}-{dd:02d}"

    doc = load_indicator("shipping", ind_id)
    doc.update({
        "name": name,
        "unit": "pt",
        "frequency": "daily",
        "source": "Baltic Exchange (StockQ 게시)",
        "source_url": url,
        "default_series": [ind_id.upper()],
    })
    added = merge_points(doc, ind_id.upper(), [(d, value)])
    save_indicator("shipping", doc)
    print(f"  {ind_id.upper()} {d} = {value} ({'new' if added else 'update'})")


def run():
    for ind_id, (page, name) in INDICES.items():
        fetch_one(ind_id, page, name)


if __name__ == "__main__":
    run()

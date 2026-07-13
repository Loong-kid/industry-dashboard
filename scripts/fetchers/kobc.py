# -*- coding: utf-8 -*-
"""KOBC(한국해양진흥공사) 해양정보서비스 페처.

- KCCI: 컨테이너 운임 종합지수(주간). timeseries 엑셀 다운로드(POST, 세션 쿠키 필요) — 전체 히스토리 제공.
- KDCI: 건화물선 운임지수(일간, USD/day 기반 지수). gridList 페이지의 인라인 JS에서 최근 값 파싱 → 매일 누적.
"""
import io
import re
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import UA, load_indicator, merge_points, norm_date, save_indicator, to_float

BASE = "https://www.kobc.or.kr"


def fetch_kcci():
    s = requests.Session()
    grid_url = f"{BASE}/ebz/shippinginfo/timeseries/gridList.do?mId=0304000000"
    s.get(grid_url, headers=UA, timeout=30)  # 세션 쿠키 확보
    r = s.post(
        f"{BASE}/ebz/shippinginfo/timeseries/excel/download.do?mId=0304000000",
        data={"sDay": "2022-11-01", "eDay": pd.Timestamp.today().strftime("%Y-%m-%d"),
              "mId": "0304000000", "siteCode": "shippinginfo"},
        headers={**UA, "Referer": grid_url},
        timeout=60,
    )
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), header=None, skiprows=2)
    # 컬럼: 번호, DATE, KCCI, KUWI, KUEI, KNEI, KMDI, KMEI, KAUI, KLEI, KLWI, KSAI, KWAI, KCI, KJI, KSEI
    cols = ["no", "DATE", "KCCI", "미서안(KUWI)", "미동안(KUEI)", "북유럽(KNEI)", "지중해(KMDI)",
            "중동(KMEI)", "호주(KAUI)", "남미동안(KLEI)", "남미서안(KLWI)", "남아프리카(KSAI)",
            "서아프리카(KWAI)", "중국(KCI)", "일본(KJI)", "동남아(KSEI)"]
    df.columns = cols[: len(df.columns)]

    doc = load_indicator("shipping", "kcci")
    doc.update({
        "name": "KCCI (KOBC 컨테이너 운임 종합지수)",
        "unit": "pt",
        "frequency": "weekly",
        "source": "한국해양진흥공사",
        "source_url": "https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do?mId=0304000000",
        "default_series": ["KCCI"],
    })
    for col in cols[2:]:
        if col not in df.columns:
            continue
        pts = [(norm_date(row["DATE"]), to_float(row[col])) for _, row in df.iterrows()]
        merge_points(doc, col, pts)
    save_indicator("shipping", doc)


def fetch_kdci():
    s = requests.Session()
    r = s.get(f"{BASE}/ebz/shippinginfo/kdci/gridList.do?mId=0301000000", headers=UA, timeout=30)
    r.raise_for_status()
    html = r.text
    # 인라인 JS: categories.unshift("20260713"); series[i].data.unshift(parseFloat(unComma("27,823")));
    dates = re.findall(r'categories\.unshift\("(\d{8})"\)', html)
    names = re.findall(r"\{name:'([^']+)'", html)
    values: dict[int, list] = {}
    # 날짜 블록 단위로 잘라 series[i] 값을 매칭
    blocks = re.split(r'categories\.unshift\("\d{8}"\);', html)[1:]
    for bi, block in enumerate(blocks):
        for si, val in re.findall(r'series\[(\d+)\]\.data\.unshift\(parseFloat\(unComma\("([\d,\.]+)"\)\)\)', block):
            values.setdefault(int(si), []).append((bi, to_float(val)))

    doc = load_indicator("shipping", "kdci")
    doc.update({
        "name": "KDCI (KOBC 건화물선 운임지수)",
        "unit": "USD/day",
        "frequency": "daily",
        "source": "한국해양진흥공사",
        "source_url": "https://www.kobc.or.kr/ebz/shippinginfo/kdci/gridList.do?mId=0301000000",
        "default_series": ["KDCI"],
    })
    for si, pairs in values.items():
        name = names[si] if si < len(names) else f"S{si}"
        pts = [(norm_date(dates[bi]), v) for bi, v in pairs if bi < len(dates)]
        merge_points(doc, name, pts)
    save_indicator("shipping", doc)


def run():
    fetch_kcci()
    fetch_kdci()


if __name__ == "__main__":
    run()

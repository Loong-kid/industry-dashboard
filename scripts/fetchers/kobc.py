# -*- coding: utf-8 -*-
"""KOBC(한국해양진흥공사) 해양정보서비스 페처.

- KCCI: 컨테이너 운임 종합지수(주간). timeseries 엑셀 다운로드(POST, 세션 쿠키 필요) — 전체 히스토리 제공.
- KDCI: 건화물선 운임지수(일간, USD/day 기반 지수). 공식 기간 지정 엑셀의 전체 과거 자료 → 누적.
"""
import io
import math
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
    doc["data_stale_days"] = 21
    save_indicator("shipping", doc, data_date=True)


def parse_kdci_excel(content):
    df = pd.read_excel(io.BytesIO(content), header=None)
    expected = ["번호", "DATE", "KDCI", "CAPE", "PANAMAX", "SUPRAMAX", "HANDY"]
    if list(df.iloc[1].fillna("")) != expected:
        raise ValueError("KDCI 과거 엑셀 열 구조 변경")
    series = {name: [] for name in expected[2:]}
    dates = set()
    for row in df.iloc[2:].itertuples(index=False, name=None):
        d = pd.Timestamp(row[1]).date().isoformat()
        if d in dates or d > pd.Timestamp.today().date().isoformat():
            raise ValueError("KDCI 날짜 중복/미래 날짜")
        dates.add(d)
        for name, raw in zip(expected[2:], row[2:]):
            v = to_float(raw)
            if v is None or not pd.notna(v) or not math.isfinite(v) or v < 0:
                raise ValueError("KDCI 과거 엑셀 지수값 비정상")
            # 과거 파일의 미제공 선형은 0으로 표시됨. 0달러 운임으로 그리지 않는다.
            if v > 0:
                series[name].append((d, v))
    if not dates or any(not points for points in series.values()):
        raise ValueError("KDCI 과거 엑셀 자료 없음")
    return series


def fetch_kdci():
    s = requests.Session()
    url = f"{BASE}/ebz/shippinginfo/kdci/gridList.do?mId=0301000000"
    r = s.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    r = s.post(f"{BASE}/ebz/shippinginfo/kdci/excel/download.do?mId=0301000000",
               data={"sDay": "2010-01-01", "eDay": pd.Timestamp.today().strftime("%Y-%m-%d"),
                     "mId": "0301000000", "siteCode": "shippinginfo"},
               headers={**UA, "Referer": url}, timeout=60)
    r.raise_for_status()
    series = parse_kdci_excel(r.content)
    doc = load_indicator("shipping", "kdci")
    doc.update(name="KDCI (KOBC 건화물선 운임지수)", unit="USD/day", frequency="daily",
               source="한국해양진흥공사", source_url=url, default_series=["KDCI"], data_stale_days=10,
               note="KOBC의 기간 지정 엑셀에 게시된 과거 자료까지 누적합니다. 초기 자료는 선형별 제공 시점과 관측 주기가 다릅니다. 미제공 선형의 0 표시는 결측으로 처리하며 보간하지 않습니다.")
    for name, points in series.items():
        merge_points(doc, name, points)
    save_indicator("shipping", doc, data_date=True)


def run():
    fetch_kcci()
    fetch_kdci()


if __name__ == "__main__":
    run()

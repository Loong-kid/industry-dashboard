# -*- coding: utf-8 -*-
"""FRED 매크로 지표 → data/macro/*.json (일반 시계열 카드).

수집: FRED JSON API(api.stlouisfed.org) 우선 — 빠르고 안정적. 키는 env FRED_API_KEY.
키가 없으면 keyless fredgraph.csv 로 폴백(=CI는 Secret 없이도 동작).
units=pc1 로 전년동기비 서버계산. 관련 시리즈를 한 카드(다중)로 묶어 기존 카드/차트 재사용.

    FRED_API_KEY=... python scripts/fetch_fred.py   # API(권장)
    python scripts/fetch_fred.py                     # CSV 폴백
"""
import json
import os
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "macro"
API_URL = "https://api.stlouisfed.org/fred/series/observations"
CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
API_KEY = os.environ.get("FRED_API_KEY", "").strip()
START = os.environ.get("FRED_START", "2010-01-01")  # CI는 전체 이력

# 카드별: id, 이름, 단위, 빈도, [(시리즈명, FRED_id, 변환)], 기본표시 시리즈
# 변환: "pc1"=전년동기비%, "lin"=원값
CARDS = [
    {
        "id": "inflation_yoy", "name": "물가 (전년동월비)", "unit": "%", "freq": "monthly",
        "series": [
            ("CPI", "CPIAUCSL", "pc1"),
            ("근원 CPI", "CPILFESL", "pc1"),
            ("PCE", "PCEPI", "pc1"),
            ("근원 PCE", "PCEPILFE", "pc1"),
            ("PPI(최종수요)", "PPIFIS", "pc1"),
        ],
        "default": ["CPI", "근원 PCE"],
    },
    {
        "id": "inflation_exp", "name": "기대 인플레이션 (시장·BEI)", "unit": "%", "freq": "daily",
        "series": [
            ("5년 BEI", "T5YIE", "lin"),
            ("10년 BEI", "T10YIE", "lin"),
            ("5년후 5년", "T5YIFR", "lin"),
        ],
        "default": ["5년 BEI", "10년 BEI"],
    },
    {
        "id": "rates_curve", "name": "미 국채 금리 · 커브", "unit": "%", "freq": "daily",
        "series": [
            ("연방기금(실효)", "DFF", "lin"),
            ("국채 2년", "DGS2", "lin"),
            ("국채 10년", "DGS10", "lin"),
            ("국채 30년", "DGS30", "lin"),
            ("장단기차(10Y-2Y)", "T10Y2Y", "lin"),
        ],
        "default": ["국채 10년", "국채 30년"],
    },
]


def _fetch_api(session, fred_id, transform):
    r = session.get(API_URL, params={
        "series_id": fred_id, "api_key": API_KEY, "file_type": "json",
        "observation_start": START, "units": transform or "lin",
    }, timeout=(5, 30))
    r.raise_for_status()
    pts = []
    for o in r.json().get("observations", []):
        v = (o.get("value") or "").strip()
        if v and v != ".":
            try:
                pts.append([o["date"], round(float(v), 3)])
            except ValueError:
                pass
    return pts


def _fetch_csv(session, fred_id, transform):
    q = f"?id={fred_id}&cosd={START}"
    if transform and transform != "lin":
        q += f"&transformation={transform}"
    r = session.get(CSV_URL + q, timeout=(8, 60))
    r.raise_for_status()
    pts = []
    for line in r.text.splitlines()[1:]:
        d, _, v = line.partition(",")
        v = v.strip()
        if d and v and v != ".":
            try:
                pts.append([d, round(float(v), 3)])
            except ValueError:
                pass
    return pts


def fetch_series(session, fred_id, transform):
    last_err = None
    for _ in range(5):
        try:
            return _fetch_api(session, fred_id, transform) if API_KEY else _fetch_csv(session, fred_id, transform)
        except Exception as e:  # noqa
            last_err = e
            time.sleep(1.2)
    # API가 계속 실패하면 CSV로 마지막 시도
    if API_KEY:
        try:
            return _fetch_csv(session, fred_id, transform)
        except Exception as e:  # noqa
            last_err = e
    raise RuntimeError(f"{fred_id} 실패: {last_err}")


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    today = date.today().isoformat()

    for card in CARDS:
        series = {}
        last_dt = ""
        for name, fid, tr in card["series"]:
            pts = fetch_series(session, fid, tr)
            series[name] = pts
            if pts:
                last_dt = max(last_dt, pts[-1][0])
            time.sleep(0.15)
        doc = {
            "id": card["id"],
            "name": card["name"],
            "unit": card["unit"],
            "frequency": card["freq"],
            "source": "FRED (세인트루이스 연은)",
            "source_url": "https://fred.stlouisfed.org/",
            "updated": last_dt or today,
            "fetched": today,
            "default_series": card["default"],
            "series": series,
        }
        out = OUT_DIR / f"{card['id']}.json"
        # 일간 시계열이 커서 compact(무들여쓰기)로 저장
        out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n = sum(len(v) for v in series.values())
        print(f"  {card['id']}: {len(series)}시리즈 {n:,}점 (~{last_dt}) → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    run()

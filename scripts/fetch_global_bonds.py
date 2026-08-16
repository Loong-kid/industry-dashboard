# -*- coding: utf-8 -*-
"""글로벌 국채 금리(10년/30년) → data/macro/bond_10y.json, bond_30y.json.

3개 소스 결합(각 카드 = 미국·한국·일본 오버레이):
  - 미국: FRED DGS10/DGS30 (env FRED_API_KEY)
  - 한국: 한국은행 ECOS 817Y002(시장금리 일별) 국고채 10년/30년 (env ECOS_API_KEY)
  - 일본: 재무성(MOF) jgbcm_all.csv (키 없음, Shift-JIS, 일본 연호 날짜)

    FRED_API_KEY=... ECOS_API_KEY=... python scripts/fetch_global_bonds.py
"""
import json
import os
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "macro"
START = "2010-01-01"
START_YMD = START.replace("-", "")

FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()
ECOS_KEY = os.environ.get("ECOS_API_KEY", "").strip()

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
ECOS_URL = "https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/20000/817Y002/D/{s}/{e}/{item}"
MOF_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"

# 카드: (id, 이름, FRED시리즈, ECOS항목, MOF컬럼인덱스)
CARDS = [
    ("bond_10y", "국채 10년 (미·한·일)", "DGS10", "010210000", 10),
    ("bond_30y", "국채 30년 (미·한·일)", "DGS30", "010230000", 14),
]

_ERA = {"M": 1867, "T": 1911, "S": 1925, "H": 1988, "R": 2018}


def _retry(fn, what):
    err = None
    for _ in range(5):
        try:
            return fn()
        except Exception as e:  # noqa
            err = e
            time.sleep(1.2)
    raise RuntimeError(f"{what} 실패: {err}")


def fetch_fred(session, sid):
    def go():
        r = session.get(FRED_URL, params={"series_id": sid, "api_key": FRED_KEY, "file_type": "json",
                                          "observation_start": START}, timeout=(5, 30))
        r.raise_for_status()
        return [[o["date"], round(float(o["value"]), 3)]
                for o in r.json().get("observations", []) if o["value"] not in (".", "", None)]
    return _retry(go, f"FRED {sid}")


def fetch_ecos(session, item):
    def go():
        url = ECOS_URL.format(key=ECOS_KEY, s=START_YMD, e=date.today().strftime("%Y%m%d"), item=item)
        r = session.get(url, timeout=(5, 30))
        r.raise_for_status()
        d = r.json()
        if "StatisticSearch" not in d:
            raise RuntimeError(str(d)[:200])  # RESULT 에러 등
        pts = []
        for row in d["StatisticSearch"].get("row", []):
            t, v = row.get("TIME", ""), row.get("DATA_VALUE", "")
            if len(t) == 8 and v not in ("", None):
                try:
                    pts.append([f"{t[:4]}-{t[4:6]}-{t[6:8]}", round(float(v), 3)])
                except ValueError:
                    pass
        pts.sort()
        return pts
    return _retry(go, f"ECOS {item}")


def reiwa_to_iso(s):
    p = s.strip().split(".")
    if len(p) == 3 and p[0] and p[0][0] in _ERA:
        try:
            return f"{_ERA[p[0][0]] + int(p[0][1:]):04d}-{int(p[1]):02d}-{int(p[2]):02d}"
        except ValueError:
            return None
    return None


def fetch_mof(session):
    """MOF CSV 1회 파싱 → {컬럼인덱스: [[iso날짜, 값]]}."""
    def go():
        r = session.get(MOF_URL, timeout=(8, 40))
        r.raise_for_status()
        return r.content.decode("shift_jis", "replace")
    txt = _retry(go, "MOF")
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    cols = {i: [] for _, _, _, _, i in CARDS}
    for ln in lines[2:]:  # 0=제목, 1=헤더
        c = ln.split(",")
        iso = reiwa_to_iso(c[0]) if c else None
        if not iso or iso < START:
            continue
        for i in cols:
            if i < len(c):
                v = c[i].strip()
                try:
                    cols[i].append([iso, round(float(v), 3)])
                except ValueError:
                    pass  # '-' 등 결측
    for i in cols:
        cols[i].sort()
    return cols


def run():
    if not FRED_KEY or not ECOS_KEY:
        raise SystemExit("FRED_API_KEY / ECOS_API_KEY 필요 (env 또는 CI Secret)")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    today = date.today().isoformat()

    jp = fetch_mof(session)
    for cid, name, fred_id, ecos_item, mof_col in CARDS:
        series = {
            "미국": fetch_fred(session, fred_id),
            "한국": fetch_ecos(session, ecos_item),
            "일본": jp.get(mof_col, []),
        }
        last = max((s[-1][0] for s in series.values() if s), default=today)
        doc = {
            "id": cid, "name": name, "unit": "%", "frequency": "daily",
            "source": "미 FRED · 한 ECOS · 일 MOF",
            "updated": last, "fetched": today,
            "default_series": ["미국", "한국", "일본"],
            "series": series,
        }
        out = OUT_DIR / f"{cid}.json"
        out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n = {k: len(v) for k, v in series.items()}
        print(f"  {cid}: {n} (~{last}) → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    run()

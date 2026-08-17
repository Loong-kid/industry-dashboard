# -*- coding: utf-8 -*-
"""원자재 가격 → data/commodities/comm_*.json (일반 시계열 카드, 종목별 1개씩).

금·은·구리: Yahoo Finance 일봉 선물(키 없음). GC=F/SI=F/HG=F.
(리튬은 중국 소스 CI 도달 불안정으로 수기입력 방식 — manual/lithium.csv + import_manual.py)

    python scripts/fetch_commodities.py
"""
import datetime as dt
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "commodities"  # 탭 id=commodities → app.js가 이 폴더에서 로드
YH = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
P1 = int(time.mktime((2015, 1, 1, 0, 0, 0, 0, 0, 0)))

# (id, 이름, 단위, Yahoo티커)
YAHOO_CARDS = [
    ("comm_gold", "금 (Gold)", "$/oz", "GC=F"),
    ("comm_silver", "은 (Silver)", "$/oz", "SI=F"),
    ("comm_copper", "구리 (Copper)", "$/lb", "HG=F"),
]


def _retry(fn, what, n=5):
    err = None
    for _ in range(n):
        try:
            return fn()
        except Exception as e:  # noqa
            err = e
            time.sleep(1.3)
    raise RuntimeError(f"{what}: {err}")


def fetch_yahoo(session, ticker):
    def go():
        r = session.get(YH.format(t=ticker), params={"period1": P1, "period2": int(time.time()), "interval": "1d"},
                        timeout=(5, 25))
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        ts = res["timestamp"]
        cl = res["indicators"]["quote"][0]["close"]
        pts = []
        for t, c in zip(ts, cl):
            if c is not None:
                pts.append([dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), round(c, 3)])
        # 같은 날짜 중복 제거(마지막 값 우선)
        d = dict(pts)
        return [[k, d[k]] for k in sorted(d)]
    return _retry(go, f"Yahoo {ticker}")


def save(cid, name, unit, freq, series, source, today):
    doc = {"id": cid, "name": name, "unit": unit, "frequency": freq,
           "source": source, "updated": series[-1][0] if series else today, "fetched": today,
           "series": {name: series}}
    (OUT_DIR / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {cid}: {len(series)}점 (~{doc['updated']})")


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    today = dt.date.today().isoformat()

    for cid, name, unit, ticker in YAHOO_CARDS:
        save(cid, name, unit, "daily", fetch_yahoo(session, ticker), "Yahoo Finance", today)


if __name__ == "__main__":
    run()

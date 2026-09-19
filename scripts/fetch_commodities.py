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
    ("comm_palladium", "팔라듐 (Palladium)", "$/oz", "PA=F"),
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


def save(cid, name, unit, freq, series, source, today, **extra):
    doc = {"id": cid, "name": name, "unit": unit, "frequency": freq,
           "source": source, "updated": series[-1][0] if series else today, "fetched": today,
           "series": {name: series}}
    doc.update(extra)
    (OUT_DIR / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {cid}: {len(series)}점 (~{doc['updated']})")


def gold_silver_ratio(gold, silver):
    """금/은 비율 = 금 1온스로 살 수 있는 은의 온스 수. 두 선물의 거래일이 어긋나는 날이
    있어(결측·휴장 차이) 양쪽 다 값이 있는 날짜만 계산한다."""
    sd = dict(silver)
    return [[d, round(v / sd[d], 2)] for d, v in gold if sd.get(d)]


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    today = dt.date.today().isoformat()

    fetched = {}
    for cid, name, unit, ticker in YAHOO_CARDS:
        pts = fetch_yahoo(session, ticker)
        fetched[cid] = pts
        save(cid, name, unit, "daily", pts, "Yahoo Finance", today)

    # 파생 카드: 금/은 비율 (새로 수집하지 않고 위에서 받은 두 시리즈로 계산)
    ratio = gold_silver_ratio(fetched["comm_gold"], fetched["comm_silver"])
    save("comm_gold_silver_ratio", "금/은 비율 (Gold-Silver Ratio)", "배", "daily", ratio,
         "Yahoo Finance (GC=F ÷ SI=F)", today,
         description=(
             "금 1온스 가격 ÷ 은 1온스 가격. 금 한 덩이를 은 몇 온스와 바꿀 수 있는지를 뜻한다. "
             "비율이 높을수록 은이 금보다 싸다는 의미라 귀금속 안에서의 상대 가치를 볼 때 쓴다. "
             "은은 산업 수요 비중이 커서 경기가 살아나면 비율이 내려가고, 위험 회피 국면에서는 "
             "금으로 돈이 몰려 비율이 올라가는 경향이 있다."
         ),
         note="두 선물의 종가로 계산하며, 양쪽 다 거래된 날만 값이 있다.")


if __name__ == "__main__":
    run()

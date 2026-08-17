# -*- coding: utf-8 -*-
"""원자재 가격 → data/macro/comm_*.json (일반 시계열 카드, 종목별 1개씩).

금·은·구리: Yahoo Finance 일봉 선물(키 없음). GC=F/SI=F/HG=F.
리튬(탄산리튬): 东方财富 GFEX 선물 주련(중국 소스 — CI 도달 불안정 가능, best-effort).

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
EM = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
P1 = int(time.mktime((2015, 1, 1, 0, 0, 0, 0, 0, 0)))

# (id, 이름, 단위, Yahoo티커)
YAHOO_CARDS = [
    ("comm_gold", "금 (Gold)", "$/oz", "GC=F"),
    ("comm_silver", "은 (Silver)", "$/oz", "SI=F"),
    ("comm_copper", "구리 (Copper)", "$/lb", "HG=F"),
]
LITHIUM = ("comm_lithium", "탄산리튬 (GFEX)", "¥/톤", "225.lcm")  # 东财 GFEX 碳酸锂主连


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


def fetch_eastmoney(session, secid):
    def go():
        r = session.get(EM, params={"secid": secid, "fields1": "f1,f2", "fields2": "f51,f53",
                                    "klt": "101", "fqt": "0", "beg": "0", "end": "20500101"},
                        timeout=(8, 25), headers={"Referer": "https://quote.eastmoney.com/"})
        r.raise_for_status()
        d = r.json().get("data")
        if not d or not d.get("klines"):
            raise RuntimeError("no klines")
        pts = []
        for ln in d["klines"]:
            p = ln.split(",")  # f51=날짜, f53=종가
            try:
                pts.append([p[0], round(float(p[1]), 2)])
            except (ValueError, IndexError):
                pass
        return pts
    return _retry(go, f"东财 {secid}", n=3)


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

    # 리튬: 중국 소스라 실패해도 나머지에 지장 없게 best-effort
    cid, name, unit, secid = LITHIUM
    try:
        save(cid, name, unit, "daily", fetch_eastmoney(session, secid), "东方财富 (GFEX)", today)
    except Exception:  # noqa
        print(f"  {cid}: 리튬 수집 실패(중국 소스 도달 불가) - 스킵")


if __name__ == "__main__":
    run()

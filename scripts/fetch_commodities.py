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


def save(cid, name, unit, freq, series, source, today, updated=None, **extra):
    doc = {"id": cid, "name": name, "unit": unit, "frequency": freq,
           "source": source, "updated": updated or (series[-1][0] if series else today), "fetched": today,
           "series": {name: series}}
    doc.update(extra)
    (OUT_DIR / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {cid}: {len(series)}점 (~{doc['updated']})")


def gold_silver_ratio(gold, silver):
    """금/은 비율 = 금 1온스로 살 수 있는 은의 온스 수. 두 선물의 거래일이 어긋나는 날이
    있어(결측·휴장 차이) 양쪽 다 값이 있는 날짜만 계산한다."""
    sd = dict(silver)
    return [[d, round(v / sd[d], 2)] for d, v in gold if sd.get(d)]


# COMEX 구리는 3·5·7·9·12월물이 주력이다(나머지 달은 거래가 거의 없어 값이 튄다).
COPPER_MONTHS = {3: "H", 5: "K", 7: "N", 9: "U", 12: "Z"}


def copper_contracts(n=6):
    """다음 주력 월물부터 n개. (라벨, 만기월 1일, 야후 티커)."""
    today = dt.date.today()
    y, m, out = today.year, today.month, []
    while len(out) < n:
        m += 1
        if m > 12:
            m, y = 1, y + 1
        if m in COPPER_MONTHS:
            out.append((f"{y % 100:02d}년 {m}월물", f"{y}-{m:02d}-01", f"HG{COPPER_MONTHS[m]}{y % 100:02d}.CMX"))
    return out


def build_copper_curve(session, today):
    curve, hist = [], {}
    asof = ""
    fetched = []
    for label, expiry, ticker in copper_contracts():
        try:
            pts = fetch_yahoo(session, ticker)
        except Exception:  # noqa - 상장 범위 밖이면 404
            continue
        if pts:
            fetched.append((label, expiry, pts))
            asof = max(asof, pts[-1][0])
    for label, expiry, pts in fetched:
        # 커브는 같은 날 종가만 이어야 한다(먼 월물은 거래가 뜸해 값이 묵을 수 있다)
        if pts[-1][0] == asof:
            curve.append([expiry, pts[-1][1]])
        hist[label] = pts

    save("comm_copper_curve", f"구리 선물 커브 ({asof} 종가 기준)", "$/lb", "daily", curve,
         "Yahoo Finance (COMEX 월물)", today,
         updated=today,
         description=(
             "가로축이 거래일이 아니라 계약의 만기월이다. 점 하나하나가 서로 다른 계약(3·5·7·9·12월물)의 "
             "같은 날 종가다. 뒤로 갈수록 비싸지는 우상향(콘탱고)이 보관비를 반영한 평시 모습이고, "
             "앞쪽이 더 비싸지면(백워데이션) 지금 당장 현물이 부족하다는 뜻이다."
         ),
         note=("거래소 재고(LME·COMEX·SHFE)는 로그인·구독·약관 제한으로 무료 수집이 불가능하다. "
               "이 커브와 아래 스프레드가 재고 타이트함을 대신 읽는 지표다."))

    # 근월 − 원월: 한 줄로 백워데이션 전환 시점을 본다
    if len(fetched) >= 2:
        near, far = fetched[0][2], fetched[-1][2]
        far_map = dict(far)
        spread = [[d, round(v - far_map[d], 4)] for d, v in near if d in far_map]
        save("comm_copper_spread", f"구리 근월−원월 스프레드 ({fetched[0][0]} − {fetched[-1][0]})",
             "$/lb", "daily", spread, "Yahoo Finance (COMEX 월물, 계산)", today,
             description=(
                 "가장 가까운 주력 월물에서 1년쯤 뒤 월물을 뺀 값. 0보다 크면 백워데이션으로, 지금 실물을 "
                 "쥐려는 수요가 강해 재고가 빠듯하다는 신호다. 0보다 작으면 콘탱고로, 창고에 넣어둘 여유가 "
                 "있다는 뜻이다. 실제 재고 수치를 못 구하는 대신 이 부호와 방향으로 판단한다."
             ),
             note="월물이 만기로 굴러가면 비교 대상 계약이 바뀐다 — 값이 튀는 날은 롤 시점일 수 있다.")


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

    # 구리 기간구조: 거래소 재고(LME·COMEX·SHFE)는 전부 로그인·구독·약관 금지라 무료로 못 받는다.
    # 대신 근월이 원월보다 비싸지는지(백워데이션)로 현물 타이트함을 읽는다 — 재고가 빠르게 줄 때 그렇게 된다.
    build_copper_curve(session, today)

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

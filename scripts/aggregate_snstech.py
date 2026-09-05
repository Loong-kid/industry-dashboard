# -*- coding: utf-8 -*-
"""에스앤에스텍 분기 실적 ↔ 전국 블랭크마스크 수출 비교 → data/semicon/snstech_*.json.

에스앤에스텍은 국내에서 블랭크마스크를 제조·판매하는 사실상 유일한 상장사라,
관세청 전국 블랭크마스크 수출액이 이 회사 수출 실적의 대리지표가 된다.
얼마나 잘 따라가는지(상관계수)와 실제 금액 차이를 같이 보여준다.

입력:
  - manual/snstech.csv            분기 매출·내수·수출 (₩백만, 공시 기준 수기입력)
  - data/semicon/blank_*_amount.json  월별 전국 수출액 (백만$) — fetch_customs.py 산출물
  - Yahoo Finance KRW=X           원달러 (키 없음)

    python scripts/aggregate_snstech.py   # fetch_customs.py 다음에 실행

주의: 전국 수출액은 **3개월이 모두 채워진 분기만** 집계한다(진행 중인 분기 제외).
환율은 월평균을 그 달 금액에 적용한 뒤 분기 합산한다(분기 단순평균보다 정확).
"""
import csv
import datetime as dt
import json
import statistics
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SEMI_DIR = ROOT / "data" / "semicon"
CSV_PATH = ROOT / "manual" / "snstech.csv"
YH = "https://query1.finance.yahoo.com/v8/finance/chart/KRW=X"
NATIONAL = ["blank_semi_amount", "blank_disp_amount"]  # 반도체용 + 디스플레이용
SOURCE = "관세청 수출입무역통계 · DART 공시(수기입력) · Yahoo Finance"
SOURCE_URL = "https://www.data.go.kr/data/15100475/openapi.do"


def quarter_end(day):
    """'2026-06-15' → '2026-06-30' (그 날짜가 속한 분기의 말일)."""
    y, m = int(day[:4]), int(day[5:7])
    q = (m - 1) // 3 + 1
    return f"{y}-{q * 3:02d}-{[31, 30, 30, 31][q - 1]}"


def load_snstech():
    """{분기말: {항목: ₩백만}}"""
    out = {}
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    head = [h.strip() for h in rows[0]]
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        for col, name in enumerate(head[1:], start=1):
            if col < len(r) and r[col].strip():
                out.setdefault(r[0].strip(), {})[name] = float(r[col])
    return out


def load_national():
    """{월: 수출액 백만$} — 반도체용 + 디스플레이용 합산."""
    monthly = {}
    for cid in NATIONAL:
        p = SEMI_DIR / f"{cid}.json"
        if not p.exists():
            raise SystemExit(f"{p} 없음 — fetch_customs.py를 먼저 실행하세요.")
        doc = json.loads(p.read_text(encoding="utf-8"))
        for m, v in doc["series"]["수출액"]:
            monthly[m] = monthly.get(m, 0.0) + v
    return monthly


def fetch_fx(session):
    """{월: 원달러 월평균}. Yahoo KRW=X 일봉."""
    p1 = int(time.mktime((2015, 1, 1, 0, 0, 0, 0, 0, 0)))
    err = None
    for _ in range(5):
        try:
            r = session.get(YH, params={"period1": p1, "period2": int(time.time()),
                                        "interval": "1d"}, timeout=(5, 30))
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            buckets = {}
            for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
                if c is None:
                    continue
                d = dt.datetime.utcfromtimestamp(t)
                buckets.setdefault(f"{d.year}-{d.month:02d}-01", []).append(c)
            return {k: statistics.mean(v) for k, v in buckets.items()}
        except Exception as e:  # noqa
            err = e
            time.sleep(1.3)
    raise RuntimeError(f"Yahoo KRW=X 실패: {err}")


def national_quarterly(monthly, fx):
    """{분기말: ₩백만}. 3개월이 다 있고 환율도 있는 분기만."""
    q = {}
    for m, usd_m in monthly.items():
        if m not in fx:
            continue
        q.setdefault(quarter_end(m), []).append(usd_m * fx[m])
    return {k: round(sum(v), 1) for k, v in q.items() if len(v) == 3}


def pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return round(num / den, 4) if den else None


def save(cid, name, unit, series, default, updated, note=None):
    doc = {"id": cid, "name": name, "unit": unit, "frequency": "quarterly",
           "source": SOURCE, "source_url": SOURCE_URL,
           "updated": updated, "fetched": dt.date.today().isoformat(),
           "default_series": default, "series": series}
    if note:
        doc["note"] = note
    (SEMI_DIR / f"{cid}.json").write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {cid}: {len(series)}시리즈 {sum(len(v) for v in series.values())}점 (~{updated})")


def run():
    sns = load_snstech()
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    nat = national_quarterly(load_national(), fetch_fx(session))

    # 1) 에스앤에스텍 실적
    series = {}
    for name in ("매출", "내수", "수출"):
        pts = [[d, sns[d][name]] for d in sorted(sns) if name in sns[d]]
        if pts:
            series[name] = pts
    last = max(max(p[0] for p in v) for v in series.values())
    save("snstech_revenue", "에스앤에스텍 분기 실적", "₩백만", series,
         ["매출", "수출"], last,
         "DART 분기보고서 매출 구성(수기입력). 내수+수출 합이 매출과 정확히 일치하지 않는 "
         "분기가 있다(기타 매출 등)")

    # 2) 수출 실적 vs 전국 블랭크마스크 수출
    common = sorted(d for d in sns if "수출" in sns[d] and d in nat)
    if not common:
        print("  겹치는 분기 없음 — 비교 카드 생략")
        return
    a = [sns[d]["수출"] for d in common]
    b = [nat[d] for d in common]
    save("snstech_vs_national", "에스앤에스텍 수출 vs 전국 블랭크마스크 수출", "₩백만", {
        "에스앤에스텍 수출": [[d, sns[d]["수출"]] for d in common],
        "전국 블랭크마스크 수출": [[d, nat[d]] for d in common],
        "차이(전국-회사)": [[d, round(nat[d] - sns[d]["수출"], 1)] for d in common],
    }, ["에스앤에스텍 수출", "전국 블랭크마스크 수출"], common[-1],
        f"전국 = 반도체용(HS 3701991000) + 디스플레이용(3701304000) 수출액을 월평균 원달러로 "
        f"환산해 합산. 상관계수 r={pearson(a, b)} (n={len(common)}분기). "
        f"3개월이 다 채워진 분기만 표시")

    # 3) 전국 대비 비중
    rev = [d for d in common if "매출" in sns[d]]
    corr_rev = pearson([sns[d]["매출"] for d in rev], [nat[d] for d in rev]) if rev else None
    save("snstech_share", "에스앤에스텍 수출의 전국 대비 비중", "%", {
        "전국 대비 비중": [[d, round(sns[d]["수출"] / nat[d] * 100, 1)] for d in common],
    }, ["전국 대비 비중"], common[-1],
        f"회사 공시 수출 ÷ 전국 블랭크마스크 수출. 100%를 크게 밑도는 차이는 간접수출(상사 경유)이나 "
        f"회계 인식 시점 차이로 추정된다. 참고: 전국 수출액과 회사 '매출' 상관계수 r={corr_rev}")

    # 콘솔이 cp949일 수 있어 진단 출력에는 ASCII 기호만 쓴다.
    print(f"  correlation: 수출 {pearson(a, b)} / 매출 {corr_rev} "
          f"(n={len(common)}분기, {common[0]}~{common[-1]})")
    gap = [nat[d] - sns[d]["수출"] for d in common]
    print(f"  gap(전국-회사): 평균 {statistics.mean(gap):,.0f} / 최근 {gap[-1]:,.0f} (백만원)")

if __name__ == "__main__":
    run()

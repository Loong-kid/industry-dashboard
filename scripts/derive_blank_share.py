# -*- coding: utf-8 -*-
"""한국·일본 블랭크마스크 수출을 달러로 맞춰 분기별로 비교한다 (소부장 → 블랭크마스크 탭).

한국 data/semicon/blank_semi_amount.json(백만 달러)과 일본 jp_blank_amount.json(백만 엔)을 읽는다.
일본은 월별로 그달 평균 환율(ECB 기준율, Frankfurter)로 바꾼 뒤 합친다. 석 달이 다 있는 분기만 쓴다.

    python scripts/derive_blank_share.py
"""
import calendar
import datetime as dt
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SEMICON = ROOT / "data" / "semicon"
FX_CACHE = ROOT / "data" / "_japan_customs" / "usd_jpy_monthly.json"
FX_URL = "https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=JPY"
FX_SOURCE = "ECB 기준율 (Frankfurter)"
KR_SERIES, JP_SERIES = "수출액", "세계 수출액"
KOREA, JAPAN, GAP = "한국", "일본", "점유율 차이 (일본−한국, %p)"
COLORS = {KOREA: "#2a78d6", JAPAN: "#eb6834", GAP: "#52514e"}
SCOPE = ("한국은 반도체 제조용 HS 3701991000, 일본은 HS 370199000(비컬러, 각 변 255mm 이하 중 기타)이다. "
         "일본 코드가 더 넓어 블랭크마스크 외 품목이 섞일 수 있고, 그만큼 한국 비중이 낮게 나올 수 있다. "
         "두 나라에서 통관한 수출만 합친 비중이라 세계 시장 점유율이 아니며, 회사별 매출·해외 생산과도 다르다. "
         "한국 디스플레이용(HS 3701304000, 각 변 255mm 초과)은 호가 달라 뺐다.")


def month_series(doc, name):
    return {date[:7]: value for date, value in doc["series"][name] if value is not None}


def monthly_average(daily_rates):
    """{'2026-09-01': {'JPY': 160.0}, ...} → {'2026-09': 평균}"""
    months = {}
    for date, rate in daily_rates.items():
        months.setdefault(date[:7], []).append(rate["JPY"])
    return {month: round(sum(values) / len(values), 4) for month, values in months.items()}


def load_fx(through):
    """받아 둔 월평균에 빠진 달과 진행 중이던 달만 새로 받는다. 실패하면 받아 둔 값으로 계속한다."""
    cached = json.loads(FX_CACHE.read_text(encoding="utf-8")) if FX_CACHE.exists() else {}
    start = max(cached, default="2021-01")
    try:
        url = FX_URL.format(start=f"{start}-01", end=f"{through}-{calendar.monthrange(*map(int, through.split('-')))[1]:02d}")
        response = requests.get(url, headers={"User-Agent": "industry-dashboard research"}, timeout=30)
        response.raise_for_status()
        cached.update(monthly_average(response.json()["rates"]))
        FX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        FX_CACHE.write_text(json.dumps(dict(sorted(cached.items())), indent=1) + "\n", encoding="utf-8")
    except (requests.RequestException, ValueError, KeyError) as error:
        print(f"  환율 갱신 실패, 받아 둔 값 사용: {type(error).__name__}")
    return cached


def quarter_rows(korea, japan_jpy, fx):
    """석 달이 모두 있는 분기만 달러로 합친다."""
    quarters = {}
    for month in sorted(set(korea) & set(japan_jpy) & set(fx)):
        year, mm = map(int, month.split("-"))
        row = quarters.setdefault((year, (mm + 2) // 3), dict(months=0, korea=0.0, japan=0.0))
        row["months"] += 1
        row["korea"] += korea[month]
        row["japan"] += japan_jpy[month] / fx[month]
    rows = []
    for (year, quarter), row in sorted(quarters.items()):
        total = row["korea"] + row["japan"]
        if row["months"] != 3 or total <= 0:
            continue
        end_month = quarter * 3
        share = row["korea"] / total * 100
        rows.append(dict(date=f"{year}-{end_month:02d}-{calendar.monthrange(year, end_month)[1]:02d}",
                         korea=round(row["korea"], 2), japan=round(row["japan"], 2),
                         korea_share=round(share, 1), japan_share=round(100 - share, 1)))
    return rows


def label(date):
    return f"{date[:4]} Q{int(date[5:7]) // 3}"


def build_docs(rows, fetched):
    latest = rows[-1]
    gap = round(latest["japan_share"] - latest["korea_share"], 1)
    summary = (f"{label(latest['date'])}: 한국 {latest['korea']:,.1f} · 일본 {latest['japan']:,.1f} 백만 달러, "
               f"점유율 한국 {latest['korea_share']}% · 일본 {latest['japan_share']}% (차이 {gap}%p).")
    base = dict(frequency="quarterly", quarter_labels=True, full_range=True, updated=latest["date"], fetched=fetched,
                source=f"관세청 수출입무역통계 · 일본 재무성 무역통계 · {FX_SOURCE}",
                source_url="https://www.data.go.kr/data/15100475/openapi.do", series_colors=COLORS, wide_card=True)
    amount = dict(base, id="blank_kr_jp_export", name="한국 vs 일본 · 블랭크마스크 분기 수출액", unit="백만$", chart_type="bar",
                  default_series=[KOREA, JAPAN], description=f"같은 분기 수출액을 달러로 맞춰 나란히 본다. {summary}",
                  note="일본 수출액은 월별 평균 환율로 달러로 바꿨고, 석 달이 모두 집계된 분기만 표시한다. 품목 범위 차이는 아래 점유율 카드에 적었다.",
                  series={KOREA: [[r["date"], r["korea"]] for r in rows], JAPAN: [[r["date"], r["japan"]] for r in rows]})
    share = dict(base, id="blank_kr_jp_share", name="한국 vs 일본 · 블랭크마스크 수출 점유율", unit="%", stacked_series=[KOREA, JAPAN],
                 bar_value_labels=True, bar_value_digits=1, bar_value_suffix="%", bar_value_thin=True, default_series=[KOREA, JAPAN], note=SCOPE,
                 description=f"두 나라 수출액 합계를 100%로 본 비중이다. {summary}",
                 series={KOREA: [[r["date"], r["korea_share"]] for r in rows], JAPAN: [[r["date"], r["japan_share"]] for r in rows],
                         GAP: [[r["date"], round(r["japan_share"] - r["korea_share"], 1)] for r in rows]})
    return amount, share


def main():
    load = lambda name: json.loads((SEMICON / f"{name}.json").read_text(encoding="utf-8"))
    korea, japan = month_series(load("blank_semi_amount"), KR_SERIES), month_series(load("jp_blank_amount"), JP_SERIES)
    if not korea or not japan:
        sys.exit("수출 자료 없음")
    fx = load_fx(max(japan))
    rows = quarter_rows(korea, japan, fx)
    if not rows:
        sys.exit("겹치는 분기 없음")
    for doc in build_docs(rows, dt.date.today().isoformat()):
        (SEMICON / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  {len(rows)}개 분기 {rows[0]['date']}~{rows[-1]['date']} · 최신 한국 {rows[-1]['korea_share']}% 일본 {rows[-1]['japan_share']}%")


if __name__ == "__main__":
    main()

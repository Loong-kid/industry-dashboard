# -*- coding: utf-8 -*-
"""글로벌 신조 오더북(asiasis_orders.json) → 선종별 발주·인도 시계열 카드.

만드는 것:
- 조선 탭: 선종별 연도별 **발주** 척수 / 선종별 연도별 **인도(예정)** 척수

인도 시점은 납기 텍스트('2025~2026년', '2028년 8월-2030년 10월', 'Q2 2016', '2027년까지')에서
뽑는다. **구간이면 그 척수를 구간 안에 고르게 나눠 담는다** — 6척을 '2028년 8월~2030년 10월'에
인도하면 2028년에 몰아넣지 않고 월 단위로 펴서 연도별로 합친다. 한 해 인도량이 계약 구간 안에서
실제로 분산되기 때문이다.

수집이 아니라 이미 받은 JSON을 변환만 하므로 네트워크를 쓰지 않는다.
    python scripts/derive_orderbook_stats.py
"""
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "shipbuilding" / "asiasis_orders.json"
OUT_SHIP = ROOT / "data" / "shipbuilding"

SOURCE = "일간조선해양(asiasis) 신조 발주 보도 집계"
DEFAULT = ["LNG운반선", "컨테이너선", "벌커", "VLCC(초대형원유운반선)"]
# 분기·반기 표기 → 그 구간의 시작·끝 월
QUARTER = {"Q1": (1, 3), "Q2": (4, 6), "Q3": (7, 9), "Q4": (10, 12),
           "1Q": (1, 3), "2Q": (4, 6), "3Q": (7, 9), "4Q": (10, 12),
           "1H": (1, 6), "2H": (7, 12), "상반기": (1, 6), "하반기": (7, 12)}


def delivery_span(text):
    """납기 텍스트 → (시작 (연,월), 끝 (연,월)) 또는 None. 월을 모르면 그 해 전체(1~12월)로 본다."""
    s = text or ""
    years = [int(y) for y in re.findall(r"(20\d{2})", s)]
    if not years:
        return None
    # '2028년 8월', '8월 2028' 같이 연-월이 붙은 쌍을 먼저 찾는다
    pairs = [(int(y), int(m)) for y, m in re.findall(r"(20\d{2})\s*년\s*(\d{1,2})\s*월", s)]
    months_en = {m: i + 1 for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
    pairs += [(int(y), months_en[m.lower()[:3]]) for m, y in re.findall(r"([A-Za-z]{3})[a-z]*\.?\s+(20\d{2})", s)
              if m.lower()[:3] in months_en]
    lo_y, hi_y = min(years), max(years)
    lo_m, hi_m = 1, 12
    q = next((v for k, v in QUARTER.items() if k in s), None)
    if pairs:
        lo = min(pairs)
        hi = max(pairs)
        if lo[0] == lo_y:
            lo_m = lo[1]
        if hi[0] == hi_y:
            hi_m = hi[1]
    elif q and lo_y == hi_y:
        lo_m, hi_m = q
    return (lo_y, lo_m), (hi_y, hi_m)


def spread(count, span):
    """척수를 구간 안 월 수로 고르게 나눠 연도별로 합친다."""
    (ly, lm), (hy, hm) = span
    months = []
    y, m = ly, lm
    while (y, m) <= (hy, hm) and len(months) < 240:
        months.append(y)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    if not months:
        return {}
    per = count / len(months)
    out = defaultdict(float)
    for yy in months:
        out[yy] += per
    return out


def month_range(first, last):
    y, m = int(first[:4]), int(first[5:7])
    ly, lm = int(last[:4]), int(last[5:7])
    while (y, m) <= (ly, lm):
        yield f"{y}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def to_monthly_series(table, cats, last_month):
    first = min(k for c in cats for k in table[c])
    months = list(month_range(first, last_month))
    return {c: [[f"{ym}-01", table[c].get(ym, 0)] for ym in months] for c in cats if table[c]}


def to_series(table, cats):
    return {c: [[f"{y}-01-01", round(v, 1)] for y, v in sorted(table[c].items())] for c in cats if table[c]}


def run():
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    orders = doc["orders"]
    today = dt.date.today()
    fetched = today.isoformat()

    ordered = defaultdict(lambda: defaultdict(float))            # 연도별(LNG 발주 vs 인도 카드용)
    ordered_m = defaultdict(lambda: defaultdict(float))          # 월별(선종별 발주 카드용)
    delivered = defaultdict(lambda: defaultdict(float))
    no_count = no_deliv = 0
    for o in orders:
        cat, n = o.get("category") or "기타", o.get("count")
        if not n:
            no_count += 1
            continue
        ordered[cat][int(o["report_date"][:4])] += n
        ordered_m[cat][o["report_date"][:7]] += n
        span = delivery_span(o.get("delivery"))
        if not span:
            no_deliv += n
            continue
        for y, v in spread(n, span).items():
            delivered[cat][y] += v

    cats = sorted(ordered, key=lambda c: -sum(ordered[c].values()))
    total_ships = sum(sum(v.values()) for v in ordered.values())
    ytd = f"{today.year}년은 {today.month}월까지의 부분 연도다"

    OUT_SHIP.mkdir(parents=True, exist_ok=True)
    common = {"unit": "척", "frequency": "yearly", "full_range": True, "source": SOURCE,
              "source_url": doc.get("source_url", ""), "updated": doc.get("updated"), "fetched": fetched,
              "default_series": [c for c in DEFAULT if c in cats]}

    (OUT_SHIP / "orderbook_orders_by_type.json").write_text(json.dumps({
        **common, "id": "orderbook_orders_by_type", "name": "선종별 발주 척수 (연도별)",
        "description": (
            "아래 오더북 표에 쌓인 전세계 신조 발주 보도를 선종·연도별로 척수 합계한 것. 어느 선종이 어느 해에 "
            "몰려 발주됐는지 큰 사이클을 본다. 발주 붐은 보통 2~4년 뒤 인도 붐이 되어 운임을 누른다 — 옆 인도 "
            "카드와 같이 보고, 시기를 더 잘게 보려면 아래 월별 카드를 본다."
        ),
        "note": (f"언론 보도 기준 집계라 전수(클락슨 오더북)가 아니다. 총 {total_ships:,.0f}척, "
                 f"척수 미기재 {no_count}건 제외. {ytd}."),
        "series": to_series(ordered, cats),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (OUT_SHIP / "orderbook_orders_monthly.json").write_text(json.dumps({
        **common, "id": "orderbook_orders_monthly", "name": "선종별 발주 척수 (월별)",
        # 월별은 전역 기간 버튼(1년·3년)이 의미가 있어 전체기간 고정을 푼다
        "frequency": "monthly", "full_range": False,
        "description": (
            "아래 오더북 표에 쌓인 전세계 신조 발주 보도를 선종·월별로 척수 합계한 것. 어느 선종이 어느 시기에 "
            "몰려 발주됐는지를 본다. 발주 붐은 보통 2~4년 뒤 인도 붐이 되어 운임을 누른다 — 옆 인도 카드와 "
            "같이 본다. 칩으로 선종을 켜고 끄고, 기간 버튼으로 최근만 확대한다."
        ),
        "note": (f"언론 보도일 기준 집계라 전수(클락슨 오더북)가 아니고, 계약일과 보도일이 며칠~몇 주 어긋날 수 있다. "
                 f"총 {total_ships:,.0f}척, 척수 미기재 {no_count}건 제외. 발주가 없던 달은 0으로 채웠다. "
                 f"마지막 달({today.strftime('%Y-%m')})은 진행 중인 부분 월이라 위 숫자가 작게 나온다. "
                 f"대형 일괄 발주 한 건이 그달을 크게 튀게 하므로 월 단위 요동보다 몇 달 묶음의 흐름을 본다."),
        "series": to_monthly_series(ordered_m, cats, today.strftime("%Y-%m")),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (OUT_SHIP / "orderbook_deliveries_by_type.json").write_text(json.dumps({
        **common, "id": "orderbook_deliveries_by_type", "name": "선종별 인도(예정) 척수 (연도별)",
        "description": (
            "각 발주 보도의 납기를 읽어 선종·연도별로 몇 척이 인도되는지(될지)를 합친 것. 납기가 구간이면 "
            "(예: 2028년 8월~2030년 10월) 척수를 그 기간 안에 월 단위로 고르게 나눠 담았다. 올해 이후는 "
            "계약상 인도 예정이며, 선박 공급이 한꺼번에 풀리는 해를 미리 보여준다."
        ),
        "note": (f"납기 표기가 없는 보도(약 {no_deliv:,.0f}척)는 빠져 있어 실제 인도량보다 작다. "
                 "지연·취소는 반영되지 않는다(계약 당시 납기 기준)."),
        "series": to_series(delivered, cats),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # (천연가스 탭 LNG선 인도 카드는 GEM 선박 단위 데이터로 옮겼다 — scripts/aggregate_gem_lng.py)

    print(f"  선종 {len(cats)}개 · 총 {total_ships:,.0f}척 · 척수 미기재 {no_count}건 · 납기 미기재 {no_deliv:,.0f}척")


if __name__ == "__main__":
    run()

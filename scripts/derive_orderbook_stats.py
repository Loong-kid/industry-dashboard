# -*- coding: utf-8 -*-
"""글로벌 신조 오더북(asiasis_orders.json) → 선종별 발주·인도 시계열 카드.

만드는 것:
- 조선 탭: 선종별 연도별 **발주** 척수 / 선종별 연도별 **인도(예정)** 척수
- 천연가스 탭: LNG선만 떼어 발주 vs 인도 한 카드 — LNG 운임과 나란히 보려고

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
OUT_GAS = ROOT / "data" / "natgas"

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


def to_series(table, cats):
    return {c: [[f"{y}-01-01", round(v, 1)] for y, v in sorted(table[c].items())] for c in cats if table[c]}


def run():
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    orders = doc["orders"]
    today = dt.date.today()
    fetched = today.isoformat()

    ordered = defaultdict(lambda: defaultdict(float))
    delivered = defaultdict(lambda: defaultdict(float))
    no_count = no_deliv = 0
    for o in orders:
        cat, n = o.get("category") or "기타", o.get("count")
        if not n:
            no_count += 1
            continue
        ordered[cat][int(o["report_date"][:4])] += n
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
            "몰려 발주됐는지를 본다. 발주 붐은 보통 2~4년 뒤 인도 붐이 되어 운임을 누른다 — 옆 인도 카드와 "
            "같이 본다. 칩으로 선종을 켜고 끈다."
        ),
        "note": (f"언론 보도 기준 집계라 전수(클락슨 오더북)가 아니다. 총 {total_ships:,.0f}척, "
                 f"척수 미기재 {no_count}건 제외. {ytd}."),
        "series": to_series(ordered, cats),
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

    # 천연가스 탭: LNG선 발주 vs 인도 — 인도 피크가 운임에 주는 압력을 운임 카드 옆에서 본다
    lng = "LNG운반선"
    if ordered[lng]:
        OUT_GAS.mkdir(parents=True, exist_ok=True)
        peak_y, peak_v = max(delivered[lng].items(), key=lambda kv: kv[1]) if delivered[lng] else (None, 0)
        (OUT_GAS / "lng_fleet_supply.json").write_text(json.dumps({
            **common, "id": "lng_fleet_supply", "name": "LNG선 발주 vs 인도(예정)",
            "default_series": ["발주", "인도(예정)"],
            "description": (
                "LNG 운반선이 해마다 몇 척 발주됐고 몇 척이 인도되는지(될지). 발주 붐 몇 년 뒤 인도가 몰리면 "
                "배가 한꺼번에 시장에 풀려 위 'LNG선 운임'을 누르기 쉽다 — 반대로 앞의 'JKM − TTF'가 벌어져 "
                "화물이 멀리 돌면 그 공급을 흡수한다. 두 힘의 줄다리기를 이 카드와 운임 카드로 같이 본다."
            ),
            "note": (f"이 카드의 인도 정점은 {peak_y}년 약 {peak_v:,.0f}척(보도 기준)이다. 업계 전망(Poten·Drewry·"
                     "클락슨 계열)은 2025년 79척 → 2026·2027년 연 90~100척으로 2026~27년이 정점이다 — 이 카드가 "
                     "2026~27년을 낮게, 2028년을 높게 잡는 건 보도 누락(2023년 발주분 약 1/3이 납기 미기재)과 "
                     "'2027~2028년' 같은 구간을 고르게 나눈 탓으로 보인다. 절대 수준보다 흐름을 보는 용도다."),
            "series": {"발주": [[f"{y}-01-01", round(v, 1)] for y, v in sorted(ordered[lng].items())],
                       "인도(예정)": [[f"{y}-01-01", round(v, 1)] for y, v in sorted(delivered[lng].items())]},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  LNG선: 발주 {sum(ordered[lng].values()):,.0f}척 · 인도 정점 {peak_y}년 {peak_v:,.1f}척")

    print(f"  선종 {len(cats)}개 · 총 {total_ships:,.0f}척 · 척수 미기재 {no_count}건 · 납기 미기재 {no_deliv:,.0f}척")


if __name__ == "__main__":
    run()

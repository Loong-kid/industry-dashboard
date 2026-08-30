# -*- coding: utf-8 -*-
"""EIA-930 월별 저장소 → 수요 지표 JSON.

입력: data/_eia930/monthly.csv.gz  (fetch_eia930.py 산출)
출력: data/power/demand_*.json

수요는 계절성이 워낙 커서 월별 원계열로는 추세가 안 보인다(여름 피크가 겨울의 1.5배).
그래서 전부 **12개월 누적(TTM)** 으로 낸다. YoY도 TTM 대비 TTM이라 계절성이 상쇄된다.

주의
  - 930의 발전원 구분은 860M보다 거칠다(가스 복합/단순 미구분, 풍력 육상/해상 미구분).
    발전량이지 설비가 아니라서다. 860M 차트와 같은 축에 놓고 비교하지 말 것.
  - BA가 중간에 신설·통합된 경우가 있어 계열이 끊기거나 튈 수 있다.
"""
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D930 = ROOT / "data" / "_eia930"
OUT = ROOT / "data" / "power"

SOURCE = "EIA-930 Hourly Electric Grid Monitor"
SOURCE_URL = "https://www.eia.gov/electricity/gridmonitor/"

TOP_N = 10
BA_NAME = {
    "PJM": "PJM (동부 13개주)", "MISO": "MISO (중서부)", "ERCO": "ERCOT (텍사스)",
    "SWPP": "SPP (중부 평원)", "CISO": "CAISO (캘리포니아)", "SOCO": "Southern (조지아·앨라배마)",
    "NYIS": "NYISO (뉴욕)", "TVA": "TVA (테네시)", "FPL": "Florida P&L (플로리다)",
    "ISNE": "ISO-NE (뉴잉글랜드)", "DUK": "Duke (캐롤라이나)", "BPAT": "Bonneville (북서부)",
    "AZPS": "Arizona PS (애리조나)", "PACE": "PacifiCorp East (유타·와이오밍)",
    "PACW": "PacifiCorp West (오리건)", "NEVP": "NV Energy (네바다)",
    "PSCO": "Xcel (콜로라도)", "LDWP": "LA DWP (로스앤젤레스)",
    "SRP": "Salt River (애리조나)", "IPCO": "Idaho Power (아이다호)",
    "SCEG": "Dominion SC (사우스캐롤라이나)", "AECI": "Associated Electric (미주리)",
}


def ba_label(c):
    c = str(c).strip()
    return BA_NAME.get(c, c)


def save(doc):
    OUT.mkdir(parents=True, exist_ok=True)
    doc["updated"] = date.today().isoformat()
    doc.setdefault("source", SOURCE)
    doc.setdefault("source_url", SOURCE_URL)
    p = OUT / f"{doc['id']}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                 encoding="utf-8")
    n = sum(len(v) for v in doc.get("series", {}).values())
    print(f"  saved {p.relative_to(ROOT)}  ({n:,} pts, {p.stat().st_size/1e3:.0f} KB)")


def iter_months(lo, hi):
    y, m = int(lo[:4]), int(lo[5:7])
    ey, em = int(hi[:4]), int(hi[5:7])
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def ttm(per_month: dict, lo: str, hi: str, min_hours: dict | None = None):
    """12개월 이동합. 결측월은 0이 아니라 **건너뛴다** — BA 신설 전 구간까지
    0으로 채우면 합계가 실제보다 낮게 나온다. 12개월이 다 차야 값을 낸다."""
    out, win = {}, []
    for x in iter_months(lo, hi):
        win.append(per_month.get(x))
        if len(win) > 12:
            win.pop(0)
        # pandas 결측은 None이 아니라 float NaN이라 is-not-None을 통과한다
        if len(win) == 12 and all(v is not None and v == v for v in win):
            out[x + "-01"] = sum(win)
    return out


def main() -> int:
    p = D930 / "monthly.csv.gz"
    if not p.exists():
        raise SystemExit(f"!! {p} 없음. 먼저 scripts/fetch_eia930.py --backfill 실행.")
    df = pd.read_csv(p, dtype={"ba": str, "month": str})
    # 관측 시간이 크게 빈 달은 제외(월 최소 600시간 ≈ 25일). 부분월이 저점으로 튄다.
    df = df[df["hours"] >= 600]
    lo, hi = df["month"].min(), df["month"].max()
    print(f"EIA-930 집계: {df['ba'].nunique()}개 구역 / {lo}~{hi}")

    tot = df.groupby("ba")["demand_mwh"].sum().sort_values(ascending=False)
    tops = [b for b in tot.index if isinstance(b, str) and b][:TOP_N]

    # 1) 구역별 수요 (TTM TWh)
    dem = {}
    for b in tops:
        sub = df[df["ba"] == b].set_index("month")["demand_mwh"].to_dict()
        s = ttm(sub, lo, hi)
        if s:
            dem[ba_label(b)] = {x: v / 1e6 for x, v in s.items()}
    save({
        "id": "demand_ttm", "name": "전력구역별 수요 (12개월 누적)", "unit": "TWh",
        "frequency": "monthly",
        "series": {k: [[x, round(v, 1)] for x, v in sorted(vv.items())] for k, vv in dem.items()},
        "default_series": [ba_label(b) for b in tops[:5]],
        "note": "12개월 누적이라 계절성이 상쇄된다. 12개월이 다 차야 값을 내므로 시작 1년은 비어 있다.",
        "description": "설비(860M)가 공급이라면 이건 수요다. 같은 BA 코드로 붙는다. "
                       "데이터센터 부하 증가를 관측할 수 있는 거의 유일한 공개 소스.",
    })

    # 2) 수요 증가율 (TTM 전년동월 대비)
    yoy = {}
    for k, vv in dem.items():
        ser = {}
        for x, v in vv.items():
            prev = vv.get(f"{int(x[:4])-1}{x[4:]}")
            if prev and prev > 0:
                ser[x] = (v / prev - 1) * 100
        if ser:
            yoy[k] = ser
    save({
        "id": "demand_yoy", "name": "전력구역별 수요 증가율 (12개월 누적 YoY)", "unit": "%",
        "frequency": "monthly",
        "series": {k: [[x, round(v, 2)] for x, v in sorted(vv.items())] for k, vv in yoy.items()},
        "default_series": [ba_label(b) for b in tops[:5]],
        "description": "이 증가율을 같은 구역의 '증설 비율'과 나란히 보는 게 핵심이다. "
                       "수요는 느는데 파이프라인이 얇은 구역이 곧 가격이 튀는 구역이다.",
    })

    # 3) 최대수요 (연간 최댓값)
    df["y"] = df["month"].str[:4]
    peak = {}
    for b in tops:
        sub = df[df["ba"] == b]
        ser = {}
        for y, g in sub.groupby("y"):
            if len(g) >= 11:  # 연중 대부분이 있어야 연 최대로 인정
                ser[f"{y}-01-01"] = g["peak_mw"].max() / 1000
        if ser:
            peak[ba_label(b)] = ser
    save({
        "id": "demand_peak", "name": "전력구역별 연간 최대수요", "unit": "GW",
        "frequency": "yearly",
        "series": {k: [[x, round(v, 1)] for x, v in sorted(vv.items())] for k, vv in peak.items()},
        "default_series": [ba_label(b) for b in tops[:5]],
        "note": "관측월이 11개월 미만인 해는 제외. 원본에 시간 단위 오류가 섞여 있어"
                "(PJM 2020-07에 224/192/176GW가 세 시간 찍혀 있다) 월별 99.5분위"
                "(약 4번째로 높은 시간)를 최대수요로 쓴다. 정상 월에서는 진짜 최댓값과 1% 안쪽 차이다.",
        "description": "설비 적정성은 연간 전력량이 아니라 이 한 시간의 최댓값이 결정한다. "
                       "예비율 논쟁이 벌어지는 지점.",
    })

    # 4) 미국 전체 발전 믹스 (TTM TWh) — 실제로 무엇이 발전했나(설비가 아니라)
    gencols = [c for c in df.columns if c.startswith("gen::")]
    mix = {}
    for c in gencols:
        sub = df.groupby("month")[c].sum(min_count=1).to_dict()
        s = ttm(sub, lo, hi)
        if s and any(v for v in s.values()):
            mix[c.split("::", 1)[1]] = {x: v / 1e6 for x, v in s.items()}
    save({
        "id": "genmix_ttm", "name": "미국 발전 믹스 (12개월 누적)", "unit": "TWh",
        "frequency": "monthly",
        "series": {k: [[x, round(v, 1)] for x, v in sorted(vv.items())] for k, vv in mix.items()},
        "default_series": ["가스", "석탄", "원자력", "풍력", "태양광"],
        "note": "연료별 발전량은 2018년 하반기부터 제공된다(그 이전은 연료 구분이 없음). "
                "930의 구분은 860M보다 거칠다(가스 복합/단순 미구분, 풍력 육상/해상 미구분). "
                "지열·배터리 ESS·양수는 2024년 하반기부터 별도 집계돼 그 전에는 '기타'에 섞여 있다.",
        "description": "설비 규모가 아니라 **실제 발전량**이다. 설비는 늘었는데 발전량이 안 늘면 "
                       "이용률이 떨어지고 있다는 뜻.",
    })
    print("완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

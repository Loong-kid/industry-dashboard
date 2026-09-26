# -*- coding: utf-8 -*-
"""GEM 가스·석유 발전소 트래커(GOGPT) → 전력 탭 '전세계 가스발전 파이프라인' 카드·표.

입력: manual/gem/gogpt.xlsx (GEM Global Oil and Gas Plant Tracker, 사용자가 폼으로 받아 넣음, CC BY 4.0)
가스를 쓰는 유닛만(연료에 'fossil gas'가 들어간 것 — 가스·석유 겸용 포함) 본다.

제조사 칸은 표기가 제각각이다('GE Vernova' / 'GE Power' / 'GE', 'Mitsubishi Power' / 'Mitsubishi Heavy
Industries'). 회사 단위로 합치고, 제조사가 'not found'인데 모델명만 있으면(예: 'not found: 9F')
모델 계열로 제조사를 추정한다 — 추정분은 비중을 카드에 밝힌다.

    python scripts/aggregate_gem_gas_power.py
"""
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "manual" / "gem" / "gogpt.xlsx"
OUT = ROOT / "data" / "power"
REL = "Global Oil and Gas Plant Tracker, 2026-08"
GEM_URL = "https://globalenergymonitor.org/"
TODAY = dt.date.today().isoformat()

PIPE = ["construction", "pre-construction", "announced"]
STATUS_KO = {"construction": "건설중", "pre-construction": "착공전", "announced": "발표"}

# 제조사 원문(콜론 앞) → 회사
MAKER_ALIAS = [
    (r"^ge\b|general electric|ge vernova|ge power", "GE Vernova"),
    (r"siemens", "Siemens Energy"),
    (r"mitsubishi|^mhi", "Mitsubishi Power"),
    (r"doosan", "Doosan Enerbility"),
    (r"ansaldo", "Ansaldo Energia"),
    (r"shanghai electric", "Shanghai Electric(中)"),
    (r"dongfang", "Dongfang Electric(中)"),
    (r"harbin", "Harbin Electric(中)"),
    (r"baker hughes|nuovo pignone", "Baker Hughes"),
    (r"solar turbines|caterpillar|jenbacher|innio|w[aä]rtsil[aä]|man energy|man diesel|cummins|rolls|mtu|hyundai",
     "가스엔진·소형(기타)"),
]
# 제조사가 없을 때 모델 계열로 추정
MODEL_HINT = [
    (r"^(6|7|9)(ha|f|fa|e|ea|b)\b|^(6|7|9)(ha|f)\.|^lm\d|^lms|^9f|^9h|^7f", "GE Vernova"),
    (r"^sgt|^hl-class|^v94|^v64", "Siemens Energy"),
    (r"^m\d{3}|^h-25|^h-100|^j-class", "Mitsubishi Power"),
    (r"^ae\d|^gt26|^gt36", "Ansaldo Energia"),
]


def maker_of(raw):
    """→ (회사, 추정여부). 여러 설비가 적혀 있으면 첫 번째를 쓴다."""
    s = str(raw or "").strip()
    if not s or s.lower() == "nan":
        return "미상", False
    first = s.split(",")[0].strip()
    name, _, model = first.partition(":")
    name, model = name.strip().lower(), model.strip().lower()
    if name and name != "not found":
        for pat, canon in MAKER_ALIAS:
            if re.search(pat, name):
                return canon, False
        return "기타", False
    for pat, canon in MODEL_HINT:
        if model and re.search(pat, model):
            return canon, True
    return "미상", False


def gw(x):
    return round(float(x) / 1000, 1)


def write(cid, doc):
    OUT.mkdir(parents=True, exist_ok=True)
    doc.setdefault("fetched", TODAY)
    (OUT / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")


def run():
    g = pd.read_excel(SRC, sheet_name="Gas & Oil Units")
    g = g[g["Fuel"].astype(str).str.contains("fossil gas")].copy()
    g["mw"] = pd.to_numeric(g["Capacity (MW)"], errors="coerce").fillna(0)
    g["yr"] = pd.to_numeric(g["Start year"], errors="coerce")
    mk = g["Equipment Manufacturer/Model"].map(maker_of)
    g["maker"] = mk.map(lambda t: t[0])
    g["inferred"] = mk.map(lambda t: t[1])
    pipe = g[g["Status"].isin(PIPE)]
    firm = pipe[pipe["Status"].isin(["construction", "pre-construction"])]  # 발표는 불확실해 따로 센다

    # ① 연도별 신규 가스발전 — 실적 vs 계획
    def yearly(df):
        s_ = df[df["yr"].between(2000, 2035)].groupby("yr")["mw"].sum()
        return [[f"{int(y)}-01-01", gw(v)] for y, v in s_.items() if v]
    # 릴리스 연도(2026)는 반년치 실적만 있어 선이 곤두박질친 것처럼 보인다 → 실적은 전년까지만,
    # 올해 이미 가동한 물량은 건설중 계획과 합쳐 '올해 이후'로 이어 붙인다(LNG선 카드와 같은 처리).
    rel_year = 2026
    op = g[g["Status"] == "operating"]
    series = {
        "가동 개시(실적)": yearly(op[op["yr"] < rel_year]),
        "건설중(계획, 올해 가동분 포함)": yearly(pd.concat([pipe[pipe["Status"] == "construction"],
                                                     op[op["yr"] >= rel_year]])),
        "착공전(계획)": yearly(pipe[pipe["Status"] == "pre-construction"]),
        "발표(불확실)": yearly(pipe[pipe["Status"] == "announced"]),
    }
    us = pipe[pipe["Country/Area"] == "United States"]["mw"].sum()
    write("gas_power_additions", {
        "id": "gas_power_additions", "name": "전세계 가스발전 — 연도별 신규 용량",
        "unit": "GW", "frequency": "yearly", "full_range": True,
        "source": f"Global Energy Monitor, {REL} (CC BY 4.0)", "source_url": GEM_URL, "updated": "2026-08-01",
        "default_series": ["가동 개시(실적)", "건설중(계획, 올해 가동분 포함)", "착공전(계획)"],
        "description": (
            "전 세계 가스발전 유닛이 해마다 얼마나 새로 돌기 시작했고, 짓고 있거나 착공을 앞둔 물량이 언제 들어올 "
            "계획인지. 데이터센터·전력망 부족으로 가스발전 수요가 다시 늘면서, 가스터빈·HRSG(배열회수보일러)·"
            "변압기 수주와 가스 소비가 이 곡선을 따라간다. '발표'는 부지·계약이 불분명한 초기 계획이라 기본으로 끄고 둔다."
        ),
        "note": (f"건설중+착공전+발표 파이프라인 {gw(pipe['mw'].sum()):,.0f}GW 중 미국이 {gw(us):,.0f}GW"
                 f"({us / pipe['mw'].sum() * 100:.0f}%)다. 계획 연도는 사업자 발표 기준이라 밀리기 쉽다. "
                 "가스·석유 겸용 유닛 포함, 석유 전용 제외."),
        "series": series,
    })

    # ② 국가별 파이프라인 표
    ct = defaultdict(Counter)
    for _, r in g.iterrows():
        ct[r["Country/Area"]][r["Status"]] += r["mw"]
    rows = []
    for c, v in ct.items():
        p_ = sum(v[s] for s in PIPE)
        if p_ < 500:  # 0.5GW 미만 국가는 표를 길게 만들 뿐이라 뺀다
            continue
        rows.append({"country": c, "cons": gw(v["construction"]), "pre": gw(v["pre-construction"]),
                     "ann": gw(v["announced"]), "pipe": gw(p_), "op": gw(v["operating"]),
                     "ratio": round(p_ / v["operating"] * 100) if v["operating"] else None})
    rows.sort(key=lambda r: -r["pipe"])
    write("gas_power_by_country", {
        "id": "gas_power_by_country", "name": f"가스발전 파이프라인 — 국가별 ({len(rows)}개국)",
        "source": f"Global Energy Monitor, {REL}", "source_url": GEM_URL, "updated": "2026-08-01",
        "note": ("단위 GW. '파이프라인'은 건설중+착공전+발표 합계, '가동 대비'는 파이프라인 ÷ 현재 가동 용량으로 "
                 "그 나라 가스발전이 얼마나 더 불어날 수 있는지를 본다. 파이프라인 0.5GW 미만 국가는 뺐다."),
        "cols": [
            {"key": "country", "label": "국가"},
            {"key": "cons", "label": "건설중", "align": "right", "fmt": "num"},
            {"key": "pre", "label": "착공전", "align": "right", "fmt": "num"},
            {"key": "ann", "label": "발표", "align": "right", "fmt": "num"},
            {"key": "pipe", "label": "파이프라인 합계", "align": "right", "fmt": "num"},
            {"key": "op", "label": "현재 가동", "align": "right", "fmt": "num"},
            {"key": "ratio", "label": "가동 대비(%)", "align": "right", "fmt": "int"},
        ],
        "rows": rows,
    })

    # ③ 터빈 제조사별 파이프라인 — 확정에 가까운(건설중+착공전) 물량 기준
    known = firm[~firm["maker"].isin(["미상"])]
    known_mw = known["mw"].sum()
    mrows = []
    for m, df in firm.groupby("maker"):
        if m == "미상":
            continue
        tops = df.groupby("Country/Area")["mw"].sum().sort_values(ascending=False).head(3)
        models = Counter()
        for raw in df["Equipment Manufacturer/Model"].astype(str):
            mod = raw.split(",")[0].partition(":")[2].strip()
            if mod and mod.lower() != "not found":
                models[mod] += 1
        mrows.append({
            "maker": m,
            "cons": gw(df.loc[df["Status"] == "construction", "mw"].sum()),
            "pre": gw(df.loc[df["Status"] == "pre-construction", "mw"].sum()),
            "firm": gw(df["mw"].sum()),
            "share": round(df["mw"].sum() / known_mw * 100, 1) if known_mw else None,
            "ann": gw(pipe[(pipe["maker"] == m) & (pipe["Status"] == "announced")]["mw"].sum()),
            "units": int(len(df)),
            "countries": ", ".join(f"{c} {gw(v)}" for c, v in tops.items()),
            "models": ", ".join(k for k, _ in models.most_common(3)),
        })
    mrows.sort(key=lambda r: -r["firm"])
    unknown = firm.loc[firm["maker"] == "미상", "mw"].sum()
    inferred = firm.loc[firm["inferred"], "mw"].sum()
    write("gas_turbine_makers", {
        "id": "gas_turbine_makers", "name": "가스발전 파이프라인 — 터빈 제조사별",
        "source": f"Global Energy Monitor, {REL}", "source_url": GEM_URL, "updated": "2026-08-01",
        "note": (f"단위 GW, 건설중+착공전 기준(발표는 따로). 확정에 가까운 {gw(firm['mw'].sum()):,.0f}GW 중 "
                 f"제조사를 알 수 있는 건 {gw(known_mw):,.0f}GW({known_mw / firm['mw'].sum() * 100:.0f}%)이고, "
                 f"점유율은 그 안에서의 비중이다. 제조사 칸이 비고 모델명만 있는 {gw(inferred):,.0f}GW는 모델 계열"
                 f"(7HA·9F→GE, SGT→지멘스, M501J→미쓰비시)로 추정했다. 중국 업체는 해외 라이선스 모델(예: 동방전기 "
                 f"M701J)이 많다. 가스엔진·소형은 왕복동 엔진과 소형 터빈을 묶은 것이다."),
        "cols": [
            {"key": "maker", "label": "제조사"},
            {"key": "cons", "label": "건설중", "align": "right", "fmt": "num"},
            {"key": "pre", "label": "착공전", "align": "right", "fmt": "num"},
            {"key": "firm", "label": "합계", "align": "right", "fmt": "num"},
            {"key": "share", "label": "점유율(%)", "align": "right", "fmt": "num"},
            {"key": "ann", "label": "발표(별도)", "align": "right", "fmt": "num"},
            {"key": "units", "label": "유닛 수", "align": "right", "fmt": "int"},
            {"key": "countries", "label": "주요 국가(GW)"},
            {"key": "models", "label": "주력 모델"},
        ],
        "rows": mrows,
    })

    # ④ 제조사별 연도별 인도(가동 예정) — 누구의 수주가 언제 매출로 넘어가는지
    top = [r["maker"] for r in mrows if r["maker"] not in ("기타", "가스엔진·소형(기타)")][:6]
    ms = {}
    for m in top:
        s_ = firm[(firm["maker"] == m) & firm["yr"].between(2024, 2035)].groupby("yr")["mw"].sum()
        ms[m] = [[f"{int(y)}-01-01", gw(v)] for y, v in s_.items() if v]
    write("gas_turbine_makers_by_year", {
        "id": "gas_turbine_makers_by_year", "name": "제조사별 가스발전 가동 예정 (건설중+착공전)",
        "unit": "GW", "frequency": "yearly", "full_range": True,
        "source": f"Global Energy Monitor, {REL}", "source_url": GEM_URL, "updated": "2026-08-01",
        # 기본 표시는 빅3 + 두산(국내 투자 관점에서 가장 궁금한 곳)
        "default_series": [m for m in ["GE Vernova", "Siemens Energy", "Mitsubishi Power", "Doosan Enerbility"] if m in ms],
        "description": (
            "제조사가 확인된 건설중·착공전 가스발전 물량을 계획 가동연도별로 나눴다. 터빈은 보통 가동 1~3년 전에 "
            "납품되므로, 이 곡선보다 조금 앞서 해당 제조사의 매출이 잡힌다고 보면 된다."
        ),
        "note": (f"제조사를 모르는 물량({gw(unknown):,.0f}GW, 건설중+착공전의 {unknown / firm['mw'].sum() * 100:.0f}%)은 "
                 "빠져 있어 절대량은 과소다. 제조사 간 상대 크기와 시기를 보는 용도다."),
        "series": ms,
    })
    print(f"  가스 유닛 {len(g):,} · 파이프라인 {gw(pipe['mw'].sum()):,.0f}GW · 제조사 확인 "
          f"{known_mw / firm['mw'].sum() * 100:.0f}% (추정 {gw(inferred)}GW) · 국가 {len(rows)} · 제조사 {len(mrows)}")
    for r in mrows[:8]:
        print(f"    {r['maker']:24} 건설 {r['cons']:6} 착공전 {r['pre']:6} 합계 {r['firm']:6} ({r['share']}%)")


if __name__ == "__main__":
    run()

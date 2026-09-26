# -*- coding: utf-8 -*-
"""GEM(Global Energy Monitor) LNG 트래커 → 천연가스 탭 카드·표.

입력(manual/gem/, 사용자가 GEM 폼으로 받아 넣는다 — 직접 링크·API가 없어 자동 수집 불가):
  lng_carriers.xlsx   GEM LNG Carrier Tracker (선박 단위: 선주·조선소·용량·추진·인도연도)
  lng_terminals.xlsx  GEM Global Gas Infrastructure Tracker — LNG Terminals (유닛 단위, FID·지연 내장)
  gas_finance.xlsx    GEM Gas Finance Tracker (더 최신 FID 상태·EPC 업체 보강용)
**라이선스 CC BY 4.0** — 가공 게시 가능, 카드마다 출처와 릴리스를 적는다.
새 판을 받으면 같은 파일명으로 덮어쓰고 이 스크립트만 다시 돌린다.

    python scripts/aggregate_gem_lng.py
"""
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "manual" / "gem"
OUT = ROOT / "data" / "natgas"
TODAY = dt.date.today().isoformat()

# 릴리스 표기는 파일 안 저작권 문구에서 읽는 게 정석이지만 형식이 트래커마다 달라, 받을 때 여기만 고친다.
REL_CARRIER = "LNG Carrier Tracker, 2026-06"
REL_TERMINAL = "Global Gas Infrastructure Tracker — LNG Terminals, 2025-09"
REL_FINANCE = "Gas Finance Tracker, 2026-07"
GEM_URL = "https://globalenergymonitor.org/"

STATUS_KO = {"operating": "가동", "construction": "건설중", "proposed": "제안", "shelved": "보류",
             "mothballed": "가동중단", "idled": "유휴", "cancelled": "취소", "retired": "폐쇄"}
CARRIER_STATUS_KO = {"active": "운항중", "on order": "발주잔량", "proposed": "발주 추진"}
# FSRU/FSU는 떠 있는 저장·재기화 설비라 운송 선복과 성격이 다르다 — 인도 스케줄(운임 압력)에서는 뺀다
NON_CARRIER = {"FSRU", "FSU"}
KR_BUILDERS_CANON = {"Samsung Heavy Industries": "삼성중공업", "Hanwha Ocean": "한화오션",
                     "HD Hyundai Heavy Industries": "HD현대중공업", "HD Hyundai Samho": "HD현대삼호",
                     "Hudong-Zhonghua Shipbuilding": "후동중화"}


def num(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
        return float(m.group()) if m else None


def year(v):
    n = num(v)
    return int(n) if n and 1950 <= n <= 2060 else None


def iy(v):
    """판다스 열에서 꺼낸 연도(NaN 섞인 float) → int 또는 None. NaN이 JSON에 들어가면 브라우저가 파일을 못 읽는다."""
    return None if v is None or pd.isna(v) else int(v)


def nz(v):
    return None if v is None or pd.isna(v) else float(v)


def s(v):
    v = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()
    return "" if v in ("nan", "--", "unknown", "Unknown") else v


def write(cid, doc):
    OUT.mkdir(parents=True, exist_ok=True)
    doc.setdefault("fetched", TODAY)
    (OUT / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")


# ── ① LNG 운반선 ───────────────────────────────────────────────────
def carriers():
    df = pd.read_excel(SRC / "lng_carriers.xlsx", sheet_name="data")
    df["yr"] = df["Delivery year"].map(year)
    df["cap"] = df["Capacity"].map(num)
    ship = df[~df["Vessel type"].astype(str).isin(NON_CARRIER)]

    # 인도 스케줄: 실적(운항중) + 예정(발주잔량)을 조선소 국적별로 — 한국·중국 중 누가 이 파도를 만드는지
    def cnt(mask):
        return {int(y): int(n) for y, n in ship[mask].groupby("yr").size().items() if y}

    bcountry = ship["Shipbuilder yard country/area"].astype(str)
    # 릴리스 연도(2026)부터는 실적/예정을 가르지 않는다 — GEM은 올해 인도된 배도 한동안 'on order'로 두어,
    # 갈라 놓으면 올해 실적이 1척으로 보이며 선이 곤두박질친다(착시). 그 해부터는 둘을 합쳐 '인도(예정)'으로.
    rel_year = 2026
    past = (ship["Status"] == "active") & (ship["yr"] < rel_year)
    ahead = ship["Status"].isin(["active", "on order"]) & (ship["yr"] >= rel_year)
    series_raw = {
        "인도 완료(실적)": cnt(past),
        "인도 예정(합계)": cnt(ahead),
        "예정 · 한국 조선소": cnt(ahead & (bcountry == "South Korea")),
        "예정 · 중국 조선소": cnt(ahead & (bcountry == "China")),
        "예정 · 기타": cnt(ahead & ~bcountry.isin(["South Korea", "China"])),
    }
    series = {k: [[f"{y}-01-01", v] for y, v in sorted(d.items()) if y >= 2000] for k, d in series_raw.items() if d}
    this_year = dt.date.today().year
    mixed = sum(1 for _, r in ship[(ship["yr"] == this_year)].iterrows())
    peak_y, peak_v = max(series_raw["인도 예정(합계)"].items(), key=lambda kv: kv[1])
    write("lng_carrier_deliveries", {
        "id": "lng_carrier_deliveries", "name": "LNG선 인도 스케줄 (선박 단위)",
        "unit": "척", "frequency": "yearly", "full_range": True,
        "source": f"Global Energy Monitor, {REL_CARRIER} (CC BY 4.0)", "source_url": GEM_URL,
        "updated": "2026-06-01",
        "default_series": ["인도 완료(실적)", "인도 예정(합계)", "예정 · 한국 조선소", "예정 · 중국 조선소"],
        "description": (
            "전 세계 LNG 운반선을 한 척씩 추적한 목록에서 인도연도별 척수를 셌다. 이미 인도돼 운항 중인 배와 "
            "아직 건조 중인 발주잔량을 나누고, 발주잔량은 조선소 국적별로 다시 쪼갰다. 인도가 몰리는 해에는 배가 "
            "한꺼번에 시장에 풀려 위 'LNG선 운임'을 누르기 쉽다 — 반대로 'JKM − TTF'가 벌어져 화물이 멀리 돌면 "
            "그 공급을 흡수한다."
        ),
        "note": (f"인도 예정 정점은 {peak_y}년 {peak_v}척이다. 릴리스(2026-06) 연도부터는 이미 인도된 배와 건조 중인 "
                 f"배를 합쳐 '예정'으로 셌다. 건조 중인 물량은 일부가 이듬해로 밀리기 쉬워 실제 곡선은 더 완만해질 수 "
                 f"있다. FSRU·FSU(부유식 저장·재기화 설비)는 운송 선복이 아니라서 뺐다."),
        "series": series,
    })

    # 발주잔량 선박 목록(+발주 추진)
    ob = df[df["Status"].isin(["on order", "proposed"])].sort_values(["yr", "Shipbuilder"])
    rows = [{
        "name": s(r["Name"]) or s(r["Hull number"]),
        "owner": s(r["Shipowner"]), "owner_country": s(r["Shipowner country/area"]),
        "builder": s(r["Shipbuilder"]), "builder_country": s(r["Shipbuilder yard country/area"]),
        "cap": round(nz(r["cap"]) / 1000, 1) if nz(r["cap"]) else None,
        "type": s(r["Vessel type"]), "prop": s(r["Propulsion type"]),
        "year": iy(r["yr"]), "status": CARRIER_STATUS_KO.get(r["Status"], r["Status"]),
    } for _, r in ob.iterrows()]
    write("lng_carrier_orderbook", {
        "id": "lng_carrier_orderbook", "name": f"LNG선 발주잔량 목록 ({len(rows)}척)",
        "source": f"Global Energy Monitor, {REL_CARRIER}", "source_url": GEM_URL, "updated": "2026-06-01",
        "note": ("건조 중인 배(발주잔량)와 발주가 추진 중인 배. 용량은 천 입방미터(174 = 17.4만 m³급). "
                 "추진방식 X-DF·ME-GA·ME-GI는 저압·고압 이중연료 엔진으로, 최근 발주는 대부분 이 방식이다. "
                 "컬럼을 눌러 정렬한다."),
        "cols": [
            {"key": "year", "label": "인도연도", "align": "right"},
            {"key": "name", "label": "선박"},
            {"key": "builder", "label": "조선소"},
            {"key": "builder_country", "label": "조선소 국적"},
            {"key": "owner", "label": "선주"},
            {"key": "owner_country", "label": "선주 국적"},
            {"key": "cap", "label": "용량(천m³)", "align": "right", "fmt": "num"},
            {"key": "type", "label": "선형"},
            {"key": "prop", "label": "추진"},
            {"key": "status", "label": "상태"},
        ],
        "rows": rows,
    })

    # 조선소별 요약 — 발주잔량을 누가 쥐고 있고 언제 내보내는지
    oo = df[df["Status"] == "on order"]
    agg = defaultdict(lambda: Counter())
    for _, r in oo.iterrows():
        k = (s(r["Shipbuilder"]), s(r["Shipbuilder yard country/area"]))
        agg[k]["n"] += 1
        y = iy(r["yr"]) or 0
        agg[k][str(y) if y <= this_year + 2 else "later"] += 1
        agg[k]["cap"] += nz(r["cap"]) or 0
    yrs = [str(this_year), str(this_year + 1), str(this_year + 2)]
    brows = [{"builder": b, "country": c, "n": v["n"], **{f"y{y}": v.get(y, 0) for y in yrs},
              "later": v.get("later", 0), "cap": round(v["cap"] / 1e6, 2)}
             for (b, c), v in sorted(agg.items(), key=lambda kv: -kv[1]["n"])]
    total = sum(r["n"] for r in brows)
    by_country = Counter()
    for r in brows:
        by_country[r["country"]] += r["n"]
    write("lng_orderbook_by_builder", {
        "id": "lng_orderbook_by_builder", "name": f"LNG선 발주잔량 — 조선소별 ({total}척)",
        "source": f"Global Energy Monitor, {REL_CARRIER}", "source_url": GEM_URL, "updated": "2026-06-01",
        "note": ("국적별 " + " · ".join(f"{c} {n}척" for c, n in by_country.most_common(4)) +
                 ". 연도 칸은 그 해 인도 예정 척수, '이후'는 그 뒤. 용량은 백만 m³."),
        "cols": [
            {"key": "builder", "label": "조선소"},
            {"key": "country", "label": "국적"},
            {"key": "n", "label": "발주잔량(척)", "align": "right", "fmt": "int"},
            *[{"key": f"y{y}", "label": f"{y}", "align": "right", "fmt": "int"} for y in yrs],
            {"key": "later", "label": "이후", "align": "right", "fmt": "int"},
            {"key": "cap", "label": "용량(백만m³)", "align": "right", "fmt": "num"},
        ],
        "rows": brows,
    })
    print(f"  LNG선: 운송선 {len(ship)}척 · 발주잔량 {len(oo)}척 · 예정 정점 {peak_y}년 {peak_v}척")


# ── ② LNG 액화(수출) 터미널 ────────────────────────────────────────
def terminals():
    t = pd.read_excel(SRC / "lng_terminals.xlsx", sheet_name="LNG Terminals")
    ex = t[t["FacilityType"].astype(str).str.lower() == "export"].copy()
    ex["cap"] = ex["CapacityinMtpa"].map(num)
    ex["orig"] = ex["OriginalPlannedStartYear"].map(year)
    ex["latest"] = ex["LatestPlannedStartYear"].map(year)
    ex["actual"] = ex["ActualStartYear"].map(year)

    # Gas Finance(2026-07)가 더 최신이라 FID·EPC는 그쪽을 우선한다. 유닛 ID(Combo)로만 매칭된다(약 1/4).
    f = pd.read_excel(SRC / "gas_finance.xlsx", sheet_name="LNG Terminals")
    fin = {}
    for _, r in f.iterrows():
        k = s(r["GEM Combo ID"])
        if not k:
            continue
        cur = fin.setdefault(k, {"fid": "", "fid_year": None, "epc": set()})
        cur["fid"] = cur["fid"] or s(r["FID Status"])
        cur["fid_year"] = cur["fid_year"] or year(r["FID Date"])
        if s(r["EPC Contractor"]):
            cur["epc"].add(s(r["EPC Contractor"]))

    keep = ex[~ex["Status"].isin(["cancelled", "retired"])]
    rows = []
    for _, r in keep.iterrows():
        fx = fin.get(s(r["UnitID"]), {})
        fid = fx.get("fid") or s(r["FIDStatus"])
        fid_y = fx.get("fid_year") or year(r["FIDYear"])
        orig, latest, actual = iy(r["orig"]), iy(r["latest"]), iy(r["actual"])
        delay = (latest - orig) if latest and orig and r["Status"] in ("construction", "proposed", "shelved") else None
        cost = nz(num(r["CostUSD"]))
        rows.append({
            "terminal": s(r["TerminalName"]).replace(" LNG Terminal", " LNG"),
            "unit": s(r["UnitName"]),
            "country": s(r["Country/Area"]),
            "status": STATUS_KO.get(s(r["Status"]), s(r["Status"])),
            "mtpa": round(nz(r["cap"]), 2) if nz(r["cap"]) else None,
            "orig": orig, "latest": latest, "delay": delay, "actual": actual,
            "fid": (f"{fid} {fid_y}" if fid_y else fid).strip(),
            "cost_bn": round(cost / 1e9, 1) if cost else None,
            "parent": s(r["Parent"])[:80],
            "epc": ", ".join(sorted(fx.get("epc", [])))[:60],
            "floating": "부유식" if s(r["Floating"]).lower() in ("yes", "true", "1") else "",
        })
    order = {"건설중": 0, "제안": 1, "보류": 2, "가동": 3}
    rows.sort(key=lambda r: (order.get(r["status"], 9), -(r["mtpa"] or 0)))

    def capsum(st):
        return ex.loc[ex["Status"] == st, "cap"].sum()
    dl = [r["delay"] for r in rows if r["delay"] is not None]
    late = sum(1 for d in dl if d >= 1)
    write("lng_global", {
        "id": "lng_global", "name": f"전세계 LNG 액화 프로젝트 ({len(rows)}개 유닛)",
        "source": f"Global Energy Monitor, {REL_TERMINAL} · {REL_FINANCE} (CC BY 4.0)", "source_url": GEM_URL,
        "updated": "2025-09-01",
        "note": (f"액화(수출) 용량 — 가동 {capsum('operating'):,.0f} · 건설중 {capsum('construction'):,.0f} · "
                 f"제안 {capsum('proposed'):,.0f} MTPA. '지연'은 최신 계획 가동연도 − 최초 계획 가동연도로, "
                 f"건설중·제안·보류 {len(dl)}개 유닛 중 {late}개가 1년 이상 밀렸다(평균 {sum(dl)/max(len(dl),1):.1f}년). "
                 f"FID·EPC는 더 최신인 Gas Finance(2026-07)를 우선하고, 없으면 터미널 트래커 값을 쓴다. "
                 f"터미널 트래커가 2025-09 판이라 그 뒤 FID·가동은 반영이 늦을 수 있다. 취소·폐쇄 유닛은 뺐다."),
        "cols": [
            {"key": "terminal", "label": "터미널"},
            {"key": "unit", "label": "유닛"},
            {"key": "country", "label": "국가"},
            {"key": "status", "label": "상태"},
            {"key": "mtpa", "label": "용량(MTPA)", "align": "right", "fmt": "num"},
            {"key": "orig", "label": "최초 계획", "align": "right"},
            {"key": "latest", "label": "최신 계획", "align": "right"},
            {"key": "delay", "label": "지연(년)", "align": "right", "fmt": "int"},
            {"key": "actual", "label": "실제 가동", "align": "right"},
            {"key": "fid", "label": "FID"},
            {"key": "cost_bn", "label": "사업비($bn)", "align": "right", "fmt": "num"},
            {"key": "parent", "label": "모회사(지분)"},
            {"key": "epc", "label": "EPC"},
            {"key": "floating", "label": "형태"},
        ],
        "rows": rows,
    })

    # 연도별 신규 액화용량(전 세계, 미국 포함) — 실적과 계획을 갈라서
    def by_year(mask, col):
        g = ex[mask].groupby(col)["cap"].sum()
        return [[f"{int(y)}-01-01", round(v, 1)] for y, v in g.items() if y and v and y >= 2000]
    series = {
        "가동 개시(실적)": by_year(ex["actual"].notna(), "actual"),
        "건설중(계획)": by_year((ex["Status"] == "construction") & ex["latest"].notna(), "latest"),
        "제안(계획, 불확실)": by_year((ex["Status"] == "proposed") & ex["latest"].notna(), "latest"),
    }
    write("lng_global_timeline", {
        "id": "lng_global_timeline", "name": "전세계 액화용량 — 연도별 신규",
        "unit": "MTPA", "frequency": "yearly", "full_range": True,
        "source": f"Global Energy Monitor, {REL_TERMINAL} (CC BY 4.0)", "source_url": GEM_URL,
        "updated": "2025-09-01",
        "default_series": ["가동 개시(실적)", "건설중(계획)"],
        "description": (
            "전 세계(미국 포함) 액화 유닛이 해마다 얼마나 새로 돌기 시작했고, 짓고 있는 물량이 언제 들어올 "
            "계획인지. 실적은 실제 가동연도, 건설중은 최신 계획 가동연도 기준이다. 제안 단계는 FID 전이라 "
            "상당수가 취소·보류되므로 기본으로는 꺼 두었다(칩으로 켠다)."
        ),
        "note": ("계획선은 지연되면 오른쪽으로 밀린다 — 아래 표의 '지연(년)' 컬럼이 그 크기다. "
                 "미국 train 단위 상세는 위 EIA 카드에 있다."),
        "series": series,
    })
    print(f"  액화: 유닛 {len(rows)}개 · 건설중 {capsum('construction'):,.0f} MTPA · 지연 {late}/{len(dl)}")


if __name__ == "__main__":
    carriers()
    terminals()

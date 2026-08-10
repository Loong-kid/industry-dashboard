# -*- coding: utf-8 -*-
"""EIA-860M 빈티지 저장소 → 대시보드 지표 JSON.

입력: data/_eia/{vintages,dim,operating,retired,canceled}.csv.gz  (fetch_eia860m.py 산출)
출력: data/power/*.json

핵심 아이디어
  EIA-860M의 값어치는 "지금 설비용량"이 아니라 **파이프라인의 상태 사다리와 그 월별 변화**에 있다.
  빈티지(발행월)를 쌓아두면 다음이 계산된다:
    - COD 지연: 같은 발전기의 준공예정일이 빈티지마다 얼마나 뒤로 밀렸는가
    - 신규 진입: 이번 달 파이프라인에 새로 들어온 MW (수주 선행지표)
    - 이탈: 파이프라인에서 사라진 건이 준공된 건지 취소된 건지

주의
  - Planned 시트에는 MWh(배터리 지속시간)·DC(태양광) 컬럼이 없다. 준공 후 Operating에서만 붙는다.
  - DC Net Capacity는 최근 빈티지일수록 미기입이 많다 → DC/AC 비율은 최근연도 신뢰 불가라 지표화하지 않음.
  - 1MW 미만(주택용·소규모 상업용)은 이 데이터에 아예 없다. 유틸리티 규모 시장만 본다.
"""
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
EIA_DIR = ROOT / "data" / "_eia"
OUT_DIR = ROOT / "data" / "power"

SOURCE = "EIA Form 860M (Preliminary Monthly Electric Generator Inventory)"
SOURCE_URL = "https://www.eia.gov/electricity/data/eia860m/"

# ── 기술 분류 ────────────────────────────────────────────────────
TECH_GROUP = {
    "Solar Photovoltaic": "태양광",
    "Solar Thermal with Energy Storage": "태양열",
    "Solar Thermal without Energy Storage": "태양열",
    "Batteries": "배터리 ESS",
    "Natural Gas Fired Combined Cycle": "가스 복합",
    "Natural Gas Fired Combustion Turbine": "가스 단순",
    "Natural Gas Internal Combustion Engine": "가스 기타",
    "Natural Gas Steam Turbine": "가스 기타",
    "Other Natural Gas": "가스 기타",
    "Natural Gas with Compressed Air Storage": "가스 기타",
    "Onshore Wind Turbine": "육상풍력",
    "Offshore Wind Turbine": "해상풍력",
    "Nuclear": "원자력",
    "Conventional Steam Coal": "석탄",
    "Coal Integrated Gasification Combined Cycle": "석탄",
    "Petroleum Coke": "석탄",
    "Conventional Hydroelectric": "수력",
    "Hydroelectric Pumped Storage": "양수",
    "Geothermal": "지열",
    "Landfill Gas": "바이오·폐기물",
    "Municipal Solid Waste": "바이오·폐기물",
    "Other Waste Biomass": "바이오·폐기물",
    "Wood/Wood Waste Biomass": "바이오·폐기물",
    "Petroleum Liquids": "석유",
}
# 차트 시리즈 표시 순서(=색 슬롯 고정). 미매핑 기술은 '기타'.
TECH_ORDER = ["태양광", "배터리 ESS", "가스 복합", "가스 단순", "육상풍력", "해상풍력",
              "원자력", "양수", "가스 기타", "석탄", "수력", "지열", "태양열",
              "바이오·폐기물", "석유", "기타"]
TECH_DEFAULT = ["태양광", "배터리 ESS", "가스 복합", "가스 단순", "육상풍력"]

# ── 상태 사다리 ──────────────────────────────────────────────────
# 아래로 갈수록 준공에 가깝다. U/V/TS = 실제로 삽을 뜬 물량.
STATUS_LABEL = {
    "P": "① 계획 (인허가 전)",
    "L": "② 인허가 심사중",
    "T": "③ 인허가 완료·착공 전",
    "U": "④ 건설중 (50% 이하)",
    "V": "⑤ 건설중 (50% 초과)",
    "TS": "⑥ 시운전 대기",
}
STATUS_ORDER = ["TS", "V", "U", "T", "L", "P"]
UNDER_CONSTRUCTION = {"U", "V", "TS"}


def tech_group(t: str) -> str:
    return TECH_GROUP.get(str(t).strip(), "기타")


def ym_to_idx(ym: str):
    """'2027-06' -> 월 인덱스. 월이 없는 'YYYY-00'은 계산에서 제외(None)."""
    if not isinstance(ym, str) or len(ym) != 7:
        return None
    y, m = ym[:4], ym[5:]
    if not (y.isdigit() and m.isdigit()) or m == "00":
        return None
    return int(y) * 12 + int(m)


def nz(v, default=0):
    """NaN/None을 기본값으로. 파이썬에서 `NaN or 0`은 NaN을 그대로 돌려준다(NaN이 truthy).
    그 NaN이 JSON에 실리면 `JSON.parse`가 파일 전체를 거부해 카드가 통째로 빈다."""
    if v is None:
        return default
    if isinstance(v, float) and v != v:
        return default
    return v


def _load(name: str) -> pd.DataFrame:
    path = EIA_DIR / f"{name}.csv.gz"
    if not path.exists():
        raise SystemExit(f"!! {path} 없음. 먼저 scripts/fetch_eia860m.py --backfill 실행.")
    df = pd.read_csv(path, dtype={"gen_id": str, "cod": str, "vintage": str,
                                  "op_ym": str, "ret_ym": str})
    # 빈 문자열로 저장된 gen_id가 다시 읽으면 NaN이 된다. 그대로 두면 키가 깨져
    # (NaN != NaN) 조인·인덱싱이 조용히 어긋난다.
    for c in ("gen_id", "cod", "vintage", "op_ym", "ret_ym"):
        if c in df.columns:
            df[c] = df[c].fillna("")
    return df


def save(doc: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc["updated"] = date.today().isoformat()
    doc.setdefault("source", SOURCE)
    doc.setdefault("source_url", SOURCE_URL)
    path = OUT_DIR / f"{doc['id']}.json"
    # allow_nan=False: NaN이 섞이면 조용히 나가는 대신 여기서 터지게 한다.
    # 파이썬은 NaN을 그대로 쓰지만 JS JSON.parse는 거부해서, 나가면 카드가 통째로 빈다.
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                    encoding="utf-8")
    n = sum(len(v) for v in doc.get("series", {}).values()) or len(doc.get("rows", []))
    print(f"  saved {path.relative_to(ROOT)}  ({n:,} pts, {path.stat().st_size/1e3:.0f} KB)")


def series_doc(ind_id, name, unit, freq, series, default=None, note=None, desc=None):
    """series: {이름: {x: 값}} → 정렬된 [[x, 값]] 리스트로 변환."""
    out = {}
    for k in sorted(series, key=lambda s: (TECH_ORDER + list(series)).index(s)
                    if s in TECH_ORDER else 999):
        # 0은 살린다 — 지연 개월수처럼 0이 의미 있는 계열이 있다. 대신 전부 0인 계열만 통째로 뺀다.
        pts = [[x, round(nz(v), 2)] for x, v in sorted(series[k].items())]
        if any(p[1] for p in pts):
            out[k] = pts
    doc = {"id": ind_id, "name": name, "unit": unit, "frequency": freq, "series": out}
    if default:
        doc["default_series"] = [d for d in default if d in out] or list(out)[:3]
    if note:
        doc["note"] = note
    if desc:
        doc["description"] = desc
    return doc


# ── 파이프라인 시계열 (빈티지 기반) ───────────────────────────────
def build_pipeline_series(v: pd.DataFrame):
    v = v.copy()
    v["g"] = v["tech"].map(tech_group)
    v["gw"] = v["mw"].fillna(0) / 1000.0
    v["x"] = v["vintage"] + "-01"

    # 1) 상태 사다리별 파이프라인
    st = defaultdict(lambda: defaultdict(float))
    for code in STATUS_ORDER:
        sub = v[v["status"] == code]
        for x, gw in sub.groupby("x")["gw"].sum().items():
            st[STATUS_LABEL[code]][x] = gw
    save(series_doc(
        "pipeline_status", "파이프라인 상태 사다리 (전 발전원)", "GW", "monthly", st,
        default=[STATUS_LABEL[c] for c in STATUS_ORDER],
        desc="EIA-860M Planned 시트의 Status 코드별 누적 용량. ④⑤⑥이 실제 착공 물량, ①②③은 아직 서류 단계."))

    # 2) 착공 이상(U/V/TS) = 확정 물량, 기술별
    uc = v[v["status"].isin(UNDER_CONSTRUCTION)]
    d = defaultdict(lambda: defaultdict(float))
    for (x, g), gw in uc.groupby(["x", "g"])["gw"].sum().items():
        d[g][x] = gw
    save(series_doc(
        "pipeline_construction", "착공 물량 (건설중+시운전대기)", "GW", "monthly", d,
        default=TECH_DEFAULT,
        desc="Status U/V/TS만 합산. 인허가 단계(P/L/T)를 제외한 '삽을 뜬' 용량이라 준공 가시성이 높다."))

    # 3) 전체 파이프라인, 기술별
    d = defaultdict(lambda: defaultdict(float))
    for (x, g), gw in v.groupby(["x", "g"])["gw"].sum().items():
        d[g][x] = gw
    save(series_doc(
        "pipeline_total", "전체 파이프라인 (인허가 단계 포함)", "GW", "monthly", d,
        default=TECH_DEFAULT,
        desc="Planned 시트 전체. 인허가 전 단계까지 포함하므로 실제 준공량보다 크게 잡힌다."))
    return v


def build_flow_series(v: pd.DataFrame, op: pd.DataFrame):
    """빈티지 간 diff: 신규 진입 / 이탈(준공 vs 취소) / COD 지연."""
    v = v.sort_values("vintage")
    vintages = sorted(v["vintage"].unique())
    key = ["plant_id", "gen_id"]

    snap = {}   # vintage -> {(plant,gen): (cod, mw, group, status)}
    for vt, sub in v.groupby("vintage"):
        snap[vt] = {(r.plant_id, r.gen_id): (nz(r.cod, ""), nz(r.mw), tech_group(r.tech), r.status)
                    for r in sub.itertuples()}

    # 준공 여부 판정용: 현재 가동중 발전기 집합
    built = set(zip(op["plant_id"], op["gen_id"]))

    entries = defaultdict(lambda: defaultdict(float))
    exits_built = defaultdict(lambda: defaultdict(float))
    exits_dropped = defaultdict(lambda: defaultdict(float))
    slip_mw = defaultdict(lambda: defaultdict(float))

    for prev, cur in zip(vintages, vintages[1:]):
        a, b = snap[prev], snap[cur]
        x = cur + "-01"
        for k, (cod, mw, g, _) in b.items():
            if k not in a:
                entries[g][x] += mw / 1000.0
        for k, (cod, mw, g, _) in a.items():
            if k in b:
                # COD 지연: 이번 달에 준공예정일이 뒤로 밀린 물량
                i0, i1 = ym_to_idx(cod), ym_to_idx(b[k][0])
                if i0 is not None and i1 is not None and i1 > i0:
                    slip_mw[g][x] += mw / 1000.0
            elif k in built:
                exits_built[g][x] += mw / 1000.0
            else:
                exits_dropped[g][x] += mw / 1000.0

    def ttm(d):
        """12개월 롤링 합계 (월별 원계열은 들쭉날쭉해서 추세가 안 보임)."""
        out = defaultdict(lambda: defaultdict(float))
        for g, pts in d.items():
            xs = sorted(pts)
            for i, x in enumerate(xs):
                lo = max(0, i - 11)
                out[g][x] = sum(pts[y] for y in xs[lo:i + 1])
        return out

    save(series_doc(
        "pipeline_entries", "파이프라인 신규 진입 (12개월 누적)", "GW", "monthly", ttm(entries),
        default=TECH_DEFAULT,
        desc="직전 발행월에 없던 발전기가 새로 등재된 용량. 개발 파이프라인의 선행지표."))
    save(series_doc(
        "pipeline_dropped", "파이프라인 이탈 — 취소·보류 (12개월 누적)", "GW", "monthly", ttm(exits_dropped),
        default=TECH_DEFAULT,
        desc="Planned에서 사라졌는데 가동 목록에도 없는 건. 취소·무기한 보류로 본다."))
    save(series_doc(
        "cod_slip", "준공 지연 발생 물량 (12개월 누적)", "GW", "monthly", ttm(slip_mw),
        default=TECH_DEFAULT,
        desc="직전 발행월 대비 준공예정일이 뒤로 밀린 발전기의 용량 합계. 인터커넥션·기자재 병목의 실물 신호."))

    # 누적 지연 개월: 현재 파이프라인 건들이 '최초 등재 시 COD' 대비 몇 개월 밀렸나 (MW 가중)
    first_cod, first_seen = {}, {}
    for vt in vintages:
        for k, (cod, mw, g, _) in snap[vt].items():
            if k not in first_cod:
                first_cod[k], first_seen[k] = cod, vt
    slipm = defaultdict(lambda: defaultdict(float))
    wsum = defaultdict(lambda: defaultdict(float))
    for vt in vintages:
        x = vt + "-01"
        for k, (cod, mw, g, _) in snap[vt].items():
            i0, i1 = ym_to_idx(first_cod[k]), ym_to_idx(cod)
            if i0 is None or i1 is None or not mw:
                continue
            slipm[g][x] += (i1 - i0) * mw
            wsum[g][x] += mw
    avg = {g: {x: slipm[g][x] / wsum[g][x] for x in slipm[g] if wsum[g][x]} for g in slipm}
    save(series_doc(
        "cod_slip_months", "누적 준공 지연 (최초 등재 대비, MW 가중 평균)", "개월", "monthly", avg,
        default=TECH_DEFAULT,
        note="신규 진입 건은 지연 0이라 평균을 낮추는 방향으로 희석한다. 절대값보다 추세를 볼 것.",
        desc="파이프라인에 남아있는 각 발전기의 현재 준공예정일과 최초 등재 시 준공예정일의 차이."))
    return first_cod, first_seen


# ── 스냅샷 기반 시계열 (실적·전망) ────────────────────────────────
def build_snapshot_series(op: pd.DataFrame, rt: pd.DataFrame, v: pd.DataFrame):
    today = date.today().strftime("%Y-%m")

    def ttm_by_month(df, ycol, since="2015-01"):
        df = df[df[ycol].notna() & (df[ycol] >= since) & (df[ycol] <= today)]
        d = defaultdict(lambda: defaultdict(float))
        for (ym, g), mw in df.groupby([ycol, df["tech"].map(tech_group)])["mw"].sum().items():
            if len(str(ym)) == 7 and str(ym)[5:] != "00":
                d[g][str(ym) + "-01"] = mw / 1000.0
        out = defaultdict(lambda: defaultdict(float))
        for g, pts in d.items():
            xs = sorted(pts)
            for i, x in enumerate(xs):
                out[g][x] = sum(pts[y] for y in xs[max(0, i - 11):i + 1])
        return out

    save(series_doc(
        "additions_ttm", "실제 준공 용량 (12개월 누적)", "GW", "monthly",
        ttm_by_month(op, "op_ym"), default=TECH_DEFAULT,
        desc="가동중 발전기의 상업운전 개시월 기준 집계. 계획이 아니라 실제로 들어온 물량."))
    save(series_doc(
        "retirements_ttm", "은퇴 용량 (12개월 누적)", "GW", "monthly",
        ttm_by_month(rt, "ret_ym"), default=["석탄", "가스 복합", "가스 단순", "원자력", "석유"],
        desc="Retired 시트의 은퇴월 기준. 대체 발전원 수요의 근거."))

    # 준공 예정 연도별 전망 (현재 빈티지 기준)
    latest = v["vintage"].max()
    cur = v[v["vintage"] == latest].copy()
    cur["g"] = cur["tech"].map(tech_group)
    cur["y"] = cur["cod"].fillna("").astype(str).str[:4]
    d = defaultdict(lambda: defaultdict(float))
    for (y, g), mw in cur[cur["y"].str.isdigit()].groupby(["y", "g"])["mw"].sum().items():
        if 2020 <= int(y) <= 2040:
            d[g][f"{y}-01-01"] = mw / 1000.0
    save(series_doc(
        "cod_outlook", f"준공 예정 연도별 파이프라인 ({latest} 기준)", "GW", "yearly", d,
        default=TECH_DEFAULT,
        note=f"{latest} 발행분 기준. 인허가 단계 포함 전체 파이프라인이라 실제 준공량은 이보다 작다.",
        desc="가스 복합이 특정 연도로 몰려 있다면 그게 곧 터빈 리드타임이다."))

    # 은퇴 예정 (가동중 발전기의 planned retirement)
    fut = op[op["ret_ym"].notna() & (op["ret_ym"].astype(str) >= today)].copy()
    fut["g"] = fut["tech"].map(tech_group)
    fut["y"] = fut["ret_ym"].astype(str).str[:4]
    d = defaultdict(lambda: defaultdict(float))
    for (y, g), mw in fut[fut["y"].str.isdigit()].groupby(["y", "g"])["mw"].sum().items():
        if 2020 <= int(y) <= 2050:
            d[g][f"{y}-01-01"] = mw / 1000.0
    save(series_doc(
        "retire_outlook", "은퇴 예정 연도별 용량", "GW", "yearly", d,
        default=["석탄", "가스 복합", "가스 단순", "원자력", "석유"],
        desc="가동중 발전기가 신고한 은퇴 예정일. 규제·경제성 변화로 자주 바뀐다."))

    # 배터리 지속시간 (MWh/MW) — Operating에만 MWh가 있다
    b = op[(op["tech"] == "Batteries") & op["mwh"].notna() & (op["mw"] > 0)].copy()
    b["y"] = b["op_ym"].astype(str).str[:4]
    dur, cap = {}, {}
    for y, sub in b[b["y"].str.isdigit()].groupby("y"):
        if not (2015 <= int(y) <= 2030):
            continue
        mw, mwh = sub["mw"].sum(), sub["mwh"].sum()
        if mw > 0:
            dur[f"{y}-01-01"] = mwh / mw
            cap[f"{y}-01-01"] = mwh / 1000.0
    save(series_doc(
        "battery_duration", "배터리 ESS 지속시간 · 준공 에너지용량", "h / GWh", "yearly",
        {"평균 지속시간 (h)": dur, "준공 에너지용량 (GWh)": cap},
        default=["평균 지속시간 (h)"],
        note="Planned 시트에는 MWh 컬럼이 없다. 계획 단계 물량의 에너지용량은 알 수 없어 준공분만 집계한다.",
        desc="MWh ÷ MW. 셀 수요는 MW가 아니라 MWh를 따라간다."))


# ── 프로젝트 테이블 ──────────────────────────────────────────────
def build_table(v: pd.DataFrame, dim: pd.DataFrame, first_cod: dict, first_seen: dict):
    latest = v["vintage"].max()
    cur = v[v["vintage"] == latest].copy()
    dimx = (dim.drop_duplicates(subset=["plant_id", "gen_id"], keep="last")
               .set_index(["plant_id", "gen_id"]).to_dict("index"))

    rows = []
    for r in cur.itertuples():
        k = (r.plant_id, r.gen_id)
        d = dimx.get(k, {})
        i0, i1 = ym_to_idx(first_cod.get(k, "")), ym_to_idx(r.cod)
        slip = (i1 - i0) if (i0 is not None and i1 is not None) else None
        rows.append({
            "entity": str(nz(d.get("entity"), ""))[:60],
            "plant": str(nz(d.get("plant"), ""))[:50],
            "state": str(nz(d.get("state"), "")),
            "ba": str(nz(d.get("ba"), "")),
            "tech": tech_group(r.tech),
            "mw": round(r.mw, 1) if pd.notna(r.mw) else None,
            "status": r.status,
            "status_label": STATUS_LABEL.get(r.status, r.status),
            "cod": str(nz(r.cod, "")),
            "first_cod": str(nz(first_cod.get(k), "")),
            "slip": slip,
            "since": str(nz(first_seen.get(k), "")),
        })

    # 칩 순서: 빈도 높은 순 (기존 테이블 규약 — 첫 항목만 기본 ON)
    def by_freq(field):
        c = defaultdict(float)
        for x in rows:
            c[x[field]] += x["mw"] or 0
        return [k for k, _ in sorted(c.items(), key=lambda kv: -kv[1]) if k]

    total = sum(x["mw"] or 0 for x in rows) / 1000.0
    uc = sum(x["mw"] or 0 for x in rows if x["status"] in UNDER_CONSTRUCTION) / 1000.0
    save({
        "id": "pipeline_table",
        "name": f"발전 프로젝트 파이프라인 ({latest} 발행분)",
        "note": f"총 {len(rows):,}건 · {total:,.1f} GW (이 중 착공 이상 {uc:,.1f} GW). "
                f"'지연'은 최초 등재 시 준공예정일 대비 밀린 개월 수.",
        "techs": by_freq("tech"),
        "statuses": [STATUS_LABEL[c] for c in STATUS_ORDER],
        "rows": rows,
    })


def main() -> int:
    print("EIA-860M 집계")
    v = _load("vintages")
    dim = _load("dim")
    op = _load("operating")
    rt = _load("retired")
    print(f"  빈티지 {v['vintage'].nunique()}개월 ({v['vintage'].min()}~{v['vintage'].max()}), "
          f"{len(v):,} rows / 가동중 {len(op):,} / 은퇴 {len(rt):,}")

    v = build_pipeline_series(v)
    first_cod, first_seen = build_flow_series(v, op)
    build_snapshot_series(op, rt, v)
    build_table(v, dim, first_cod, first_seen)
    print("완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

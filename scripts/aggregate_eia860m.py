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

# 준공·은퇴 시계열의 시작월.
#  - 은퇴: Retired 시트가 2002년부터라 **하드 한계**. 그 이전은 데이터 자체가 없다.
#  - 준공: Operating 시트는 1900년까지 있지만, 이미 은퇴한 설비가 빠져 과거로 갈수록
#    과소집계된다(가동중만 세면 1970년대는 28%, 2000년대는 3%, 2010년대는 1% 누락).
#    Retired를 합치면 2000년 이후는 사실상 전수라 여기를 시작점으로 잡는다.
ADD_SINCE = "2000-01"
RET_SINCE = "2002-01"


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


def iter_months(lo: str, hi: str):
    """'2000-01'~'2026-07'을 한 달씩. 빠진 달을 0으로 메워야 하는 계산에 쓴다."""
    y, m = int(lo[:4]), int(lo[5:7])
    ey, em = int(hi[:4]), int(hi[5:7])
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


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
    doc["fetched"] = date.today().isoformat()  # 수집 실행일 (대시보드 stale 판정용)
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

    def ttm_by_month(df, ycol, since):
        """진짜 12개월 이동합.

        예전 구현은 **값이 있는 달만 골라 12개를 더했다.** 태양광처럼 매달 준공이 있으면
        우연히 맞지만, 원자력·해상풍력처럼 드문 계열에서는 수십 년치가 한 창에 합쳐진다.
        빠진 달을 0으로 메운 뒤 굴려야 한다.
        또 창을 `since`보다 앞에서부터 굴려야 첫 표시점이 온전한 12개월 합이 된다."""
        ym = df[ycol].astype(str)
        sub = df[ym.str.len().eq(7) & ~ym.str.endswith("-00") & (ym <= today)]
        raw = defaultdict(lambda: defaultdict(float))
        for (x, g), mw in sub.groupby([ycol, sub["tech"].map(tech_group)])["mw"].sum().items():
            raw[g][str(x)] += nz(mw) / 1000.0
        hi = max((x for pts in raw.values() for x in pts), default=None)
        out = defaultdict(lambda: defaultdict(float))
        for g, pts in raw.items():
            win = []
            for x in iter_months(min(min(pts), since), hi):
                win.append(pts.get(x, 0.0))
                if len(win) > 12:
                    win.pop(0)
                if x >= since:
                    out[g][x + "-01"] = sum(win)
        return out

    save(series_doc(
        "additions_ttm", "실제 준공 용량 (12개월 누적)", "GW", "monthly",
        ttm_by_month(pd.concat([op, rt], ignore_index=True), "op_ym", ADD_SINCE),
        default=TECH_DEFAULT,
        note="이미 은퇴한 설비까지 합산한다(Retired 시트가 2002년부터라 그 이전 은퇴분은 빠짐). "
             f"{ADD_SINCE[:4]}년 이후 구간은 누락이 3% 미만이다.",
        desc="상업운전 개시월 기준 실제 준공량. 계획이 아니라 실제로 들어온 물량이다."))
    save(series_doc(
        "retirements_ttm", "은퇴 용량 (12개월 누적)", "GW", "monthly",
        ttm_by_month(rt, "ret_ym", RET_SINCE), default=["석탄", "가스 복합", "가스 단순", "원자력", "석유"],
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

    # 배터리는 **월 단위**로 뽑는다. 연 단위로 묶으면 진행중인 마지막 해가 반토막처럼
    # 보인다(2025년 46.7 GWh → 2026년 24.9 GWh는 7개월치일 뿐이었다).
    # 원본 op_ym이 월 단위라 연 집계는 순전히 우리 선택이었고, 그럴 이유가 없다.
    b = op[(op["tech"] == "Batteries") & op["mwh"].notna() & (op["mw"] > 0)].copy()
    bym = b["op_ym"].astype(str)
    b = b[bym.str.len().eq(7) & ~bym.str.endswith("-00") & (bym <= today)]
    mo_mwh, mo_mw = defaultdict(float), defaultdict(float)
    for x, sub in b.groupby(b["op_ym"].astype(str)):
        mo_mwh[x] += nz(sub["mwh"].sum())
        mo_mw[x] += nz(sub["mw"].sum())

    ttm_gwh, cum_gwh, dur = {}, {}, {}
    we, wp, run = [], [], 0.0
    for x in iter_months(min(mo_mwh), max(mo_mwh)):
        e, w = mo_mwh.get(x, 0.0), mo_mw.get(x, 0.0)
        we.append(e)
        wp.append(w)
        if len(we) > 12:
            we.pop(0)
            wp.pop(0)
        run += e
        k = x + "-01"
        ttm_gwh[k] = sum(we) / 1000.0
        cum_gwh[k] = run / 1000.0
        if sum(wp) > 0:
            dur[k] = sum(we) / sum(wp)
    save(series_doc(
        "battery_duration", "배터리 ESS 평균 지속시간 (12개월 이동)", "시간", "monthly",
        {"준공 배터리 평균 지속시간": dur},
        note="평균값이라 실제 분포를 가린다. 가동중 물량은 1시간급(MW의 26%)과 "
             "4시간급(46%)으로 양분돼 있고, 정작 평균에 해당하는 2~3시간급은 얼마 없다.",
        desc="배터리가 정격 출력으로 몇 시간 버티는지(MWh ÷ MW). 100MW·2.7시간이면 270MWh를 담는다. "
             "최근 12개월 준공분의 용량가중 평균이다. "
             "셀·리튬 수요는 출력(MW)이 아니라 여기에 지속시간을 곱한 MWh를 따라간다."))
    save(series_doc(
        "battery_energy", "배터리 ESS 에너지용량 (GWh)", "GWh", "monthly",
        {"12개월 누적 준공": ttm_gwh, "누적": cum_gwh},
        default=["12개월 누적 준공", "누적"],
        note="가동중 배터리의 99.6%(용량 기준)에 MWh가 기입돼 있어 사실상 전수다. "
             "다만 Planned 시트에는 MWh 컬럼이 아예 없어 계획 물량의 GWh는 알 수 없다.",
        desc="GW(출력)가 아니라 GWh(저장량). 셀·리튬 수요에 직접 연결되는 건 이쪽이다."))

    # 지속시간 구성비 — 평균 하나로는 시장을 못 읽는다. 실제 분포가 양봉이라
    # (1시간급과 4시간급으로 갈림) 평균값 근처 제품은 거의 없다.
    # 기당 MW·MWh가 나란히 공시되므로 발전기 단위로 지속시간을 내고 구간에 담는다.
    DUR_BUCKETS = [(0.75, "1시간 미만"), (1.75, "1시간급"), (2.75, "2시간급"),
                   (3.75, "3시간급"), (5.0, "4시간급"), (float("inf"), "5시간 이상")]

    def dur_bucket(d):
        for hi, nm in DUR_BUCKETS:
            if d < hi:
                return nm
        return DUR_BUCKETS[-1][1]

    b["bk"] = (b["mwh"] / b["mw"]).map(dur_bucket)
    mo_bk = {nm: defaultdict(float) for _, nm in DUR_BUCKETS}
    for (x, bk), w in b.groupby([b["op_ym"].astype(str), "bk"])["mw"].sum().items():
        mo_bk[bk][str(x)] += nz(w)

    mix = {nm: {} for _, nm in DUR_BUCKETS}
    mix_cum = {nm: {} for _, nm in DUR_BUCKETS}
    share = {nm: {} for _, nm in DUR_BUCKETS}
    wins = {nm: [] for _, nm in DUR_BUCKETS}
    runs = {nm: 0.0 for _, nm in DUR_BUCKETS}
    for x in iter_months(min(mo_mwh), max(mo_mwh)):
        for nm in wins:
            wins[nm].append(mo_bk[nm].get(x, 0.0))
            if len(wins[nm]) > 12:
                wins[nm].pop(0)
            runs[nm] += mo_bk[nm].get(x, 0.0)
        k = x + "-01"
        tot = sum(sum(w) for w in wins.values())
        for nm in wins:
            mix[nm][k] = sum(wins[nm]) / 1000.0
            mix_cum[nm][k] = runs[nm] / 1000.0
            # 비중은 물량이 너무 적으면 한 프로젝트로 100%가 튄다 → 200MW 미만 구간은 생략
            if tot >= 200:
                share[nm][k] = sum(wins[nm]) / tot * 100
    save(series_doc(
        "battery_duration_mix", "지속시간대별 준공 물량 (12개월 누적)", "GW", "monthly", mix,
        default=["1시간급", "2시간급", "4시간급"],
        desc="같은 GW라도 4시간급은 1시간급보다 셀이 4배 든다. 물량이 어느 구간에 쌓이는지가 "
             "셀·리튬 수요를 좌우한다."))
    save(series_doc(
        "battery_duration_mix_cum", "지속시간대별 누적 준공 물량", "GW", "monthly", mix_cum,
        default=["1시간급", "2시간급", "4시간급"],
        desc="12개월 누적이 '요즘 어느 구간을 짓느냐'라면, 이건 '그동안 쌓인 구간별 총량'이다. "
             "마지막 값의 합이 곧 현재 가동중 배터리 53GW다."))
    save(series_doc(
        "battery_duration_share", "지속시간대별 비중 (12개월 누적 MW 기준)", "%", "monthly", share,
        default=["1시간급", "2시간급", "4시간급"],
        note="합이 100%다. 물량이 적던 초기 구간(12개월 누적 200MW 미만)은 한 프로젝트로 "
             "비중이 튀어서 생략했다.",
        desc="'ESS가 4시간으로 길어진다'는 통설을 직접 검증하는 지표. 실제로는 반대다 — "
             "4시간급 비중은 2021년 중반 70%까지 갔다가 40% 초반으로 내려왔고, "
             "그 자리를 2시간급이 메우고 있다."))



# ── 누적 준공 · 순설비 추이 ──────────────────────────────────────
def build_cumulative_series(op: pd.DataFrame, rt: pd.DataFrame):
    """TTM(12개월 롤링)과 짝을 이루는 누적 계열 두 종류.

    - additions_cumulative: 2015년 이후 준공분을 계속 더해간 것(플로우 누적).
    - fleet_by_tech: 가동개시 − 은퇴로 복원한 실제 설비 규모(스톡).
      **Retired 시트가 2002년부터 시작**하므로 2002년 이후 구간은 정확하다
      (어느 시점 t≥2002에 돌던 발전기는 '지금도 가동중'이거나 't 이후 은퇴'라
      반드시 둘 중 하나에 잡힌다). 그 이전은 누락분이 있어 출력하지 않는다.
    """
    today = date.today().strftime("%Y-%m")

    def monthly(df, ymcol, since=None, until=today):
        """{기술: {YYYY-MM: MW}} — 해당 월에 발생한 용량."""
        d = defaultdict(lambda: defaultdict(float))
        sub = df[df[ymcol].astype(str).str.len().eq(7) & ~df[ymcol].astype(str).str.endswith("-00")]
        sub = sub[sub[ymcol] <= until]
        if since:
            sub = sub[sub[ymcol] >= since]
        for (ym, g), mw in sub.groupby([ymcol, sub["tech"].map(tech_group)])["mw"].sum().items():
            d[g][str(ym)] += nz(mw)
        return d

    def cumulate(d, start=None):
        """누적은 **매월 값을 채워야** 한다. 변동이 있던 달만 찍으면 계열이 중간에 끊겨,
        '그 뒤로 데이터가 없다'처럼 보인다(석탄은 은퇴가 멈추면 선이 거기서 끝나버린다)."""
        end = max((x for pts in d.values() for x in pts), default=None)
        out = defaultdict(lambda: defaultdict(float))
        for g, pts in d.items():
            if not pts:
                continue
            lo = start or min(pts)
            run = sum(v for x, v in pts.items() if x < lo)  # 시작월 이전 잔액을 초기값으로
            for x in iter_months(lo, end):
                run += pts.get(x, 0.0)
                out[g][x + "-01"] = run / 1000.0
        return out

    # 1) 2015년 이후 누적 준공 (TTM 차트와 같은 원천·같은 시작점)
    save(series_doc(
        "additions_cumulative", f"누적 준공 용량 ({ADD_SINCE[:4]}년 이후 합산)", "GW", "monthly",
        cumulate(monthly(pd.concat([op, rt], ignore_index=True), "op_ym", since=ADD_SINCE)),
        default=TECH_DEFAULT,
        note="이미 은퇴한 설비까지 합산한다(Retired 시트가 2002년부터라 그 이전 은퇴분은 빠짐). "
             f"{ADD_SINCE[:4]}년 이후 구간은 누락이 3% 미만이다.",
        desc="12개월 롤링(TTM)이 '요즘 속도'라면, 이건 '그동안 깔린 총량'이다."))

    save(series_doc(
        "retirements_cumulative", f"누적 은퇴 용량 ({RET_SINCE[:4]}년 이후 합산)", "GW", "monthly",
        cumulate(monthly(rt, "ret_ym", since=RET_SINCE)),
        default=["석탄", "가스 복합", "가스 단순", "원자력", "석유"],
        desc="은퇴도 TTM은 '요즘 속도'만 보여준다. 그동안 사라진 총량은 이쪽이다."))

    # 2) 순설비 추이 = 가동개시 누적 − 은퇴 누적
    ins = monthly(pd.concat([op, rt], ignore_index=True), "op_ym")
    outs = monthly(rt, "ret_ym")
    net = defaultdict(lambda: defaultdict(float))
    for g in set(ins) | set(outs):
        for x, mw in ins.get(g, {}).items():
            net[g][x] += mw
        for x, mw in outs.get(g, {}).items():
            net[g][x] -= mw
    fleet = cumulate(net, start="2002-01")
    # 합계 계열. 기본 표시에서는 빼둔다 — 1,400GW짜리 선이 켜져 있으면 나머지가 눌린다.
    tot = defaultdict(float)
    for pts in fleet.values():
        for x, gw in pts.items():
            tot[x] += gw
    fleet["전체 합계"] = tot
    save(series_doc(
        "fleet_by_tech", "가동중 설비 규모 추이 (준공 − 은퇴)", "GW", "monthly", fleet,
        default=["가스 복합", "석탄", "육상풍력", "태양광", "원자력"],
        note="Retired 시트가 2002년부터라 2002년 이후만 표시한다. 그 구간은 준공·은퇴가 모두 잡혀 정확하다.",
        desc="각 시점에 실제로 돌고 있던 설비 용량. 마지막 값이 곧 현재 설비 규모다."))


# ── 현재 설비 구성표 ─────────────────────────────────────────────
def build_fleet_table(op: pd.DataFrame):
    """지금 미국에서 돌고 있는 발전설비를 발전원별로 정리한 스냅샷."""
    op = op.copy()
    op["g"] = op["tech"].map(tech_group)
    op["oy"] = op["op_ym"].astype(str).str[:4]
    total_mw = op["mw"].sum()
    valid = op[op["oy"].str.isdigit()]

    rows = []
    for g, sub in op.groupby("g"):
        v = valid[valid["g"] == g]
        vmw = v["mw"].sum()
        recent = v[v["oy"].astype(int) >= 2020]["mw"].sum()
        rows.append({
            "tech": g,
            "n": int(len(sub)),
            "gw": round(nz(sub["mw"].sum()) / 1000, 1),
            "summer_gw": round(nz(sub["mw_summer"].sum()) / 1000, 1),
            "share": round(nz(sub["mw"].sum()) / total_mw * 100, 1),
            "avg_year": round((v["oy"].astype(int) * v["mw"]).sum() / vmw, 1) if vmw else None,
            "recent_share": round(recent / vmw * 100, 1) if vmw else None,
        })
    rows.sort(key=lambda r: -r["gw"])

    latest_op = max((x for x in op["op_ym"].astype(str) if len(x) == 7), default="")
    save({
        "id": "fleet_table",
        "name": "현재 가동중 발전설비 구성",
        "note": f"총 {total_mw/1000:,.1f} GW · {len(op):,}기 (1MW 이상 유틸리티 규모만). "
                f"'평균 준공'은 용량 가중 평균 연도. 최신 준공 반영: {latest_op}.",
        "total_gw": round(total_mw / 1000, 1),
        "total_n": int(len(op)),
        "rows": rows,
    })


# ── 전력구역(Balancing Authority) ────────────────────────────────
# BA = 계통 수급을 실시간으로 맞추는 운영 주체. 시장 단위라 투자 관점의 기본 구획이다.
# 코드만 보면 뭔지 모르니 주요 BA는 한글 이름을 붙인다(65개 중 상위 10개가 설비의 77%).
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
BA_TOP_N = 10  # 나머지는 '기타'로 묶는다


def ba_label(code: str) -> str:
    c = str(code).strip()
    return BA_NAME.get(c, c or "미상")


def load_demand_930():
    """EIA-930 월별 저장소에서 구역별 수요(TTM TWh)와 증가율(YoY %)을 뽑는다.
    930이 아직 없으면 None — 860M만으로도 대시보드는 그대로 돌아가야 한다."""
    p = ROOT / "data" / "_eia930" / "monthly.csv.gz"
    if not p.exists():
        return None
    df = pd.read_csv(p, dtype={"ba": str, "month": str})
    df = df[df["hours"] >= 600]          # 부분월 제외
    if df.empty:
        return None
    out = {}
    for b, sub in df.groupby("ba"):
        s = sub.set_index("month")["demand_mwh"].to_dict()
        months = sorted(s)
        if len(months) < 24:
            continue
        last = months[-1]

        def ttm_at(end):
            i = months.index(end)
            win = months[max(0, i - 11):i + 1]
            return sum(s[m] for m in win) / 1e6 if len(win) == 12 else None

        cur = ttm_at(last)
        prev_key = f"{int(last[:4])-1}{last[4:]}"
        prev = ttm_at(prev_key) if prev_key in months else None
        if cur is None:
            continue
        out[b] = {
            "demand_twh": round(cur, 1),
            "demand_yoy": round((cur / prev - 1) * 100, 1) if prev else None,
            "asof": last,
        }
    return out or None


def build_ba_series(v: pd.DataFrame, dim: pd.DataFrame, op: pd.DataFrame):
    """전력구역별 파이프라인 추이 + 현황표.

    가동중 설비 대비 파이프라인 비율이 핵심이다. 절대 규모가 커도 파이프라인이
    얇으면 그 구역은 공급이 못 따라간다는 뜻이고, 그게 용량가격으로 나타난다.
    """
    bamap = dim.drop_duplicates(subset=["plant_id", "gen_id"], keep="last") \
               .set_index(["plant_id", "gen_id"])["ba"].to_dict()
    v = v.copy()
    v["ba"] = [str(nz(bamap.get((p, g)), "")).strip()
               for p, g in zip(v["plant_id"], v["gen_id"])]

    latest = v["vintage"].max()
    cur = v[v["vintage"] == latest]
    order = (cur.groupby("ba")["mw"].sum().sort_values(ascending=False).index.tolist())
    top = [b for b in order if b][:BA_TOP_N]

    def bucket(b):
        return ba_label(b) if b in top else "기타"

    # 파이프라인 추이 (전체 단계)
    d = defaultdict(lambda: defaultdict(float))
    for (x, b), mw in v.groupby([v["vintage"] + "-01", v["ba"].map(bucket)])["mw"].sum().items():
        d[b][x] = nz(mw) / 1000.0
    save(series_doc(
        "pipeline_by_ba", "전력구역별 파이프라인", "GW", "monthly", d,
        default=[ba_label(b) for b in top[:5]],
        note=f"상위 {BA_TOP_N}개 구역 외에는 '기타'로 묶었다. 전체 65개 구역 중 상위 10개가 가동중 설비의 77%.",
        desc="BA(Balancing Authority)는 계통 수급을 실시간으로 맞추는 운영 주체이자 시장 단위다. "
             "같은 물량이라도 어느 구역에 들어오느냐에 따라 가격 영향이 전혀 다르다."))

    # 현황표: 가동중 / 파이프라인 / 착공 / 증설 비율
    opb = op.copy()
    opb["ba"] = opb["ba"].astype(str).str.strip()
    live = opb.groupby("ba")["mw"].sum() / 1000
    n_live = opb.groupby("ba")["mw"].size()
    pipe = cur.groupby("ba")["mw"].sum() / 1000
    uc = cur[cur["status"].isin(UNDER_CONSTRUCTION)].groupby("ba")["mw"].sum() / 1000

    demand = load_demand_930()
    rows = []
    for b in sorted(set(live.index) | set(pipe.index)):
        if not b:
            continue
        lv, pp = float(live.get(b, 0)), float(pipe.get(b, 0))
        if lv < 1 and pp < 1:  # 1GW 미만 소규모 구역은 표에서 생략
            continue
        row = {
            "ba": ba_label(b),
            "code": b,
            "live_gw": round(lv, 1),
            "n": int(n_live.get(b, 0)),
            "pipe_gw": round(pp, 1),
            "uc_gw": round(float(uc.get(b, 0)), 1),
            "ratio": round(pp / lv * 100, 1) if lv > 0 else None,
            "uc_ratio": round(float(uc.get(b, 0)) / lv * 100, 1) if lv > 0 else None,
        }
        if demand and b in demand:
            row["demand_twh"] = demand[b]["demand_twh"]
            row["demand_yoy"] = demand[b]["demand_yoy"]
        rows.append(row)
    rows.sort(key=lambda r: -r["live_gw"])
    save({
        "id": "ba_table",
        "name": f"전력구역별 설비 · 파이프라인 ({latest} 발행분)",
        "note": "'증설 비율'은 파이프라인 ÷ 가동중. 수요(EIA-930, 12개월 누적)와 그 증가율을 "
                "나란히 놓고 본다 — 수요는 느는데 증설 비율이 낮은 구역이 곧 가격이 튀는 구역이다. "
                "1GW 미만 구역은 생략.",
        "cols": [
            {"key": "ba", "label": "전력구역"},
            {"key": "live_gw", "label": "가동중(GW)", "align": "right", "fmt": "num"},
            {"key": "pipe_gw", "label": "파이프라인(GW)", "align": "right", "fmt": "num"},
            {"key": "uc_gw", "label": "착공(GW)", "align": "right", "fmt": "num"},
            {"key": "ratio", "label": "증설 비율", "align": "right", "fmt": "pct"},
            {"key": "demand_twh", "label": "수요(TWh)", "align": "right", "fmt": "num"},
            {"key": "demand_yoy", "label": "수요 증가율", "align": "right", "fmt": "pct"},
            {"key": "uc_ratio", "label": "착공 비율", "align": "right", "fmt": "pct"},
            {"key": "n", "label": "기수", "align": "right", "fmt": "int"},
        ],
        "rows": rows,
    })


BA_DETAIL_N = 20  # 상세를 제공할 구역 수 (가동중 용량 상위)


def load_930_series():
    """구역별 (수요 TTM, 발전원별 TTM)을 돌려준다. 930이 없으면 None."""
    p = ROOT / "data" / "_eia930" / "monthly.csv.gz"
    if not p.exists():
        return None
    df = pd.read_csv(p, dtype={"ba": str, "month": str})
    df = df[df["hours"] >= 600]
    if df.empty:
        return None
    gencols = [c for c in df.columns if c.startswith("gen::")]

    def ttm(seq):
        """12개월이 다 찬 구간만. 결측을 0으로 메우면 신설 구역이 낮게 나온다."""
        out, win, keys = {}, [], sorted(seq)
        if not keys:
            return out
        for x in iter_months(keys[0], keys[-1]):
            win.append(seq.get(x))
            if len(win) > 12:
                win.pop(0)
            # pandas 결측은 None이 아니라 float NaN이라 is-not-None을 통과한다(v == v로 걸러야 함)
            if len(win) == 12 and all(v is not None and v == v for v in win):
                out[x + "-01"] = sum(win) / 1e6
        return out

    res = {}
    for b, sub in df.groupby("ba"):
        d = ttm(sub.set_index("month")["demand_mwh"].to_dict())
        if not d:
            continue
        gen = {}
        for c in gencols:
            g = ttm(sub.set_index("month")[c].to_dict())
            if g and any(v > 0.05 for v in g.values()):
                gen[c.split("::", 1)[1]] = g
        res[b] = {
            "dem": {"수요": [[x, round(v, 1)] for x, v in sorted(d.items())]},
            "gen": {k: [[x, round(v, 1)] for x, v in sorted(vv.items())] for k, vv in gen.items()},
        }
    return res or None


def build_ba_detail(v: pd.DataFrame, dim: pd.DataFrame, op: pd.DataFrame, rt: pd.DataFrame):
    """구역 하나를 골라 그 안의 발전원 구성을 보는 뷰.

    파일 하나에 전 구역을 담으므로 해상도를 아낀다 — 파이프라인은 발행월 단위(67개월)로
    두고, 느리게 움직이는 설비·누적 계열은 **연 단위**로 낮춘다. 월 단위로 다 담으면
    3MB가 넘어가는데 그만큼의 정보가 더 있지도 않다.
    """
    bamap = dim.drop_duplicates(subset=["plant_id", "gen_id"], keep="last") \
               .set_index(["plant_id", "gen_id"])["ba"].to_dict()
    v = v.copy()
    v["ba"] = [str(nz(bamap.get((p, g)), "")).strip() for p, g in zip(v["plant_id"], v["gen_id"])]
    for df in (op, rt):
        df["ba"] = df["ba"].astype(str).str.strip()

    live = op.groupby("ba")["mw"].sum().sort_values(ascending=False)
    tops = [b for b in live.index if b and b != "nan"][:BA_DETAIL_N]
    built = pd.concat([op, rt], ignore_index=True)
    today = date.today().strftime("%Y-%m")

    def yearly_cum(df, ymcol, since, sign=1, base=None):
        """연말 기준 누적. base가 있으면 거기서 이어 더한다(설비 규모용)."""
        ym = df[ymcol].astype(str)
        sub = df[ym.str.len().eq(7) & ~ym.str.endswith("-00") & (ym <= today)]
        per = defaultdict(lambda: defaultdict(float))
        for (x, g), mw in sub.groupby([ymcol, sub["tech"].map(tech_group)])["mw"].sum().items():
            if str(x) >= since:
                per[g][str(x)[:4]] += nz(mw) * sign / 1000.0
        out = {}
        y0, y1 = int(since[:4]), int(today[:4])
        # base에만 있는 기술(2002년 이전에만 지어진 것 — 예: PJM 원자력)을 빠뜨리면
        # 그 잔액이 통째로 사라진다. 반드시 합집합으로 돌 것.
        for g in set(per) | set(base or {}):
            pts = per.get(g, {})
            run = float(base.get(g, 0.0)) if base else 0.0
            ser = []
            for y in range(y0, y1 + 1):
                run += pts.get(str(y), 0.0)
                ser.append([f"{y}-01-01", round(run, 2)])
            out[g] = ser
        return out

    dem930 = load_930_series()
    data, bas = {}, []
    for b in tops:
        vb, ob, rb, bb = (v[v["ba"] == b], op[op["ba"] == b],
                          rt[rt["ba"] == b], built[built["ba"] == b])

        # 파이프라인 (발행월 단위)
        pipe = defaultdict(list)
        tmp = defaultdict(lambda: defaultdict(float))
        for (x, g), mw in vb.groupby([vb["vintage"] + "-01", vb["tech"].map(tech_group)])["mw"].sum().items():
            tmp[g][x] = nz(mw) / 1000.0
        for g, pts in tmp.items():
            pipe[g] = [[x, round(val, 2)] for x, val in sorted(pts.items())]

        # 설비 규모 = 2002년 이전 잔액 + 이후 (준공 − 은퇴)
        pre = defaultdict(float)
        pym = bb["op_ym"].astype(str)
        for g, mw in bb[pym.str.len().eq(7) & (pym < "2002-01")].groupby(
                bb["tech"].map(tech_group))["mw"].sum().items():
            pre[g] += nz(mw) / 1000.0
        fleet = yearly_cum(bb, "op_ym", "2002-01", base=pre)
        for g, ser in yearly_cum(rb, "ret_ym", "2002-01", sign=-1).items():
            if g in fleet:
                fleet[g] = [[x, round(a[1] + c[1], 2)] for x, a, c in
                            zip([p[0] for p in fleet[g]], fleet[g], ser)]

        entry = {
            "pipe": {g: s for g, s in pipe.items() if any(p[1] for p in s)},
            "fleet": {g: s for g, s in fleet.items() if any(p[1] for p in s)},
            "add": yearly_cum(bb, "op_ym", ADD_SINCE),
            "ret": yearly_cum(rb, "ret_ym", RET_SINCE),
        }
        entry = {k: {g: s for g, s in vv.items() if any(p[1] for p in s)} for k, vv in entry.items()}
        if dem930 and b in dem930:      # 수요·실제 발전량 (EIA-930)
            entry["dem"] = dem930[b]["dem"]
            entry["gen"] = dem930[b]["gen"]
        data[b] = entry
        bas.append({"code": b, "label": ba_label(b), "live_gw": round(float(live[b]) / 1000, 1)})

    save({
        "id": "ba_detail",
        "name": "전력구역별 발전원 구성",
        "note": f"가동중 용량 상위 {BA_DETAIL_N}개 구역. 설비는 GW(용량), 수요·발전량은 "
                "TWh(전력량)라 축이 다르다. 파이프라인은 발행월 단위, 설비·누적은 연 단위.",
        "metrics": [
            {"key": "pipe", "label": "파이프라인 (계획+착공)", "unit": "GW"},
            {"key": "fleet", "label": "가동중 설비 규모", "unit": "GW"},
            {"key": "add", "label": f"누적 준공 ({ADD_SINCE[:4]}년~)", "unit": "GW"},
            {"key": "ret", "label": f"누적 은퇴 ({RET_SINCE[:4]}년~)", "unit": "GW"},
            {"key": "dem", "label": "전력 수요 (12개월 누적)", "unit": "TWh"},
            {"key": "gen", "label": "실제 발전량 (12개월 누적)", "unit": "TWh"},
        ],
        "bas": bas,
        "data": data,
    })


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
    build_cumulative_series(op, rt)
    build_fleet_table(op)
    build_ba_series(v, dim, op)
    build_ba_detail(v, dim, op, rt)
    build_table(v, dim, first_cod, first_seen)
    print("완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""ASML 노광기 기술별 판매 대수(분기) → 반도체 소부장 > 에스앤에스텍 서브탭 카드.

입력: manual/asml_litho_units.csv — ASML이 SEC에 내는 분기 실적(6-K) 발표자료의
'Sales in lithography units' 막대(EUV·ArFi·ArF dry·KrF·i-line)를 옮겨 적은 것.
**이 표는 슬라이드 이미지로만 제출돼 자동 추출이 안 된다**(글자로는 전체 대수만 있음). 그래서 분기마다
한 줄씩 수기로 추가한다. 검증 장치 두 가지:
  ① 분기 5개 기술의 합 == 같은 6-K 재무표의 'Sales of lithography systems (in units)'(글자, 자동 대조 가능)
  ② 연간 합 == 연간보고서의 기술별 대수(2013~2022 표) / 'EUV systems recognized'(2023~)
2016년 이전은 연간보고서 값만 있어 연 단위로 둔다. 대수는 '매출 인식' 기준(출하 아님).

    python scripts/aggregate_asml.py
"""
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "manual" / "asml_litho_units.csv"
OUT = ROOT / "data" / "semicon"
SEC_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000937966&type=6-K"
SOURCE = "ASML 분기 실적 6-K 발표자료(SEC) · 연간보고서"
TECH = ["euv", "arfi", "arf_dry", "krf", "i_line"]
LABEL = {"euv": "EUV", "arfi": "ArFi(액침)", "arf_dry": "ArF dry", "krf": "KrF", "i_line": "i-line"}
DUV = ["arfi", "arf_dry", "krf", "i_line"]
QEND = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}

# 같은 6-K 재무표(글자)의 분기별 전체 노광기 대수 — 기술별 합과 대조하는 기준값
TOTAL_TEXT = {
    "2016Q4": 38, "2017Q1": 44, "2017Q2": 42, "2017Q3": 55, "2017Q4": 57, "2018Q1": 49, "2018Q2": 58,
    "2018Q3": 53, "2018Q4": 64, "2019Q1": 48, "2019Q2": 48, "2019Q3": 57, "2019Q4": 76, "2020Q1": 57,
    "2020Q2": 61, "2020Q3": 60, "2020Q4": 80, "2021Q1": 76, "2021Q2": 72, "2021Q3": 79, "2021Q4": 82,
    "2022Q1": 62, "2022Q2": 91, "2022Q3": 86, "2022Q4": 106, "2023Q1": 100, "2023Q2": 113, "2023Q3": 112,
    "2023Q4": 124, "2024Q1": 70, "2024Q2": 100, "2024Q3": 116, "2024Q4": 132, "2025Q1": 77, "2025Q2": 76,
    "2025Q3": 72, "2025Q4": 102, "2026Q1": 79, "2026Q2": 91,
}
# 연간보고서 EUV 대수 — 분기 합 대조용
EUV_ANNUAL = {2017: 11, 2018: 18, 2019: 26, 2020: 31, 2021: 42, 2022: 40, 2023: 53, 2024: 44, 2025: 48}


def num(v):
    return int(v) if str(v).strip() else None


def run():
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    annual = {int(r["period"]): r for r in rows if r["period"].isdigit()}
    quarters = [r for r in rows if "Q" in r["period"]]

    # ── 검증 ──────────────────────────────────────────────────
    bad = []
    for r in quarters:
        s = sum(num(r[t]) for t in TECH)
        if r["period"] in TOTAL_TEXT and s != TOTAL_TEXT[r["period"]]:
            bad.append(f"{r['period']} 합 {s} ≠ 재무표 {TOTAL_TEXT[r['period']]}")
    for y, e in EUV_ANNUAL.items():
        s = sum(num(r["euv"]) for r in quarters if r["period"].startswith(str(y)))
        if s != e:
            bad.append(f"{y} EUV 분기합 {s} ≠ 연간 {e}")
    if bad:
        raise SystemExit("검증 실패:\n  " + "\n  ".join(bad))

    def qdate(p):
        return f"{p[:4]}-{QEND[p[4:]]}"

    # ① 분기 판매 대수
    series = {"EUV": [], "DUV 합계": []}
    for t in DUV:
        series[LABEL[t]] = []
    for r in quarters:
        d = qdate(r["period"])
        series["EUV"].append([d, num(r["euv"])])
        series["DUV 합계"].append([d, sum(num(r[t]) for t in DUV)])
        for t in DUV:
            series[LABEL[t]].append([d, num(r[t])])
    last = quarters[-1]["period"]
    euv_share = num(quarters[-1]["euv"]) / sum(num(quarters[-1][t]) for t in TECH) * 100
    common = {"source": SOURCE, "source_url": SEC_URL, "manual": True,
              "updated": qdate(last), "fetched": dt.date.today().isoformat()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "asml_units_quarterly.json").write_text(json.dumps({
        "id": "asml_units_quarterly", "name": "ASML 노광기 판매 대수 (분기)",
        "unit": "대", "frequency": "quarterly", **common,
        "default_series": ["EUV", "DUV 합계"],
        "description": (
            "ASML이 분기마다 매출로 인식한 노광기 대수를 기술별로 나눈 것. EUV(극자외선)는 최첨단 공정용, "
            "DUV는 ArFi(액침)·ArF dry·KrF·i-line을 합친 것이다. 노광기 한 대가 돌 때마다 포토마스크가 쓰이고 "
            "그 원판이 블랭크마스크라, 판매 대수는 에스앤에스텍 제품 수요의 선행 지표가 된다 — 특히 EUV용 "
            "블랭크마스크는 단가가 높아 EUV 대수가 중요하다. 칩으로 DUV 세부 기술을 켠다."
        ),
        "note": (f"최근 {last} EUV 비중 {euv_share:.0f}%. 대수는 출하가 아니라 매출 인식 기준이라, 고객 현장 검수가 "
                 "늦으면 다음 분기로 넘어간다. 발표자료 이미지에서 옮겨 적은 값이며, 분기마다 기술별 합이 같은 "
                 "보고서 재무표의 전체 대수와 맞는지, 연간 합이 연간보고서와 맞는지로 검증했다(2020년 2분기는 "
                 "슬라이드가 없어 연간 − 나머지 분기로 계산)."),
        "series": series,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # ② 누적 판매 대수 — 연간(2011~2015) + 분기(2016Q4~). 2016Q1~Q3은 연간 − Q4로 한 점에 묶는다.
    q16_4 = next(r for r in quarters if r["period"] == "2016Q4")
    cum_e, cum_d, e_pts, d_pts = 0, 0, [], []
    cum_t = {t: 0 for t in DUV}
    t_pts = {t: [] for t in DUV}  # DUV 기술별 누적(KrF·ArF·ArFi를 따로 보려고)
    for y in sorted(annual):
        a = annual[y]
        e, dsum = num(a["euv"]), (sum(num(a[t]) for t in DUV) if a["arfi"] else None)
        if y == 2016:  # Q1~Q3만 여기서 더하고 Q4는 분기 루프에서
            e -= num(q16_4["euv"])
            dsum -= sum(num(q16_4[t]) for t in DUV)
            date = "2016-09-30"
        else:
            date = f"{y}-12-31"
        cum_e += e
        e_pts.append([date, cum_e])
        if dsum is not None:
            cum_d += dsum
            d_pts.append([date, cum_d])
            for t in DUV:
                v = num(a[t]) - (num(q16_4[t]) if y == 2016 else 0)
                cum_t[t] += v
                t_pts[t].append([date, cum_t[t]])
    for r in quarters:
        cum_e += num(r["euv"])
        cum_d += sum(num(r[t]) for t in DUV)
        e_pts.append([qdate(r["period"]), cum_e])
        d_pts.append([qdate(r["period"]), cum_d])
        for t in DUV:
            cum_t[t] += num(r[t])
            t_pts[t].append([qdate(r["period"]), cum_t[t]])
    # 누적은 EUV(수백 대)와 DUV(수천 대)의 자릿수가 달라 한 차트에 두면 EUV가 바닥에 깔린다 → 두 장으로 나눈다.
    common_cum = {"unit": "대", "frequency": "quarterly", "full_range": True, **common}
    (OUT / "asml_units_cumulative.json").write_text(json.dumps({
        "id": "asml_units_cumulative", "name": "ASML EUV 누적 판매 대수", **common_cum,
        "description": (
            "팔려 나간 EUV 노광기가 쌓인 숫자 — 설치 대수(인스톨드 베이스)의 근사치다. 블랭크마스크는 새로 팔린 "
            "장비뿐 아니라 이미 돌고 있는 장비 전체에서 소모되므로, 분기 판매보다 이 누적이 수요의 바탕에 가깝다. "
            "EUV 블랭크마스크는 단가가 높아 에스앤에스텍에 가장 중요한 선이다. 상업 출하 이전 시제품까지 포함해 "
            "2011년부터 셌다."
        ),
        "note": (f"{last} 기준 누적 {cum_e}대. 2024년부터 High-NA(EXE) 장비가 포함된다. 2016년 이전은 연 단위 점이다."),
        "series": {"EUV 누적(2011~)": e_pts},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "asml_duv_cumulative.json").write_text(json.dumps({
        "id": "asml_duv_cumulative", "name": "ASML DUV 누적 판매 대수 (2013년 이후)", **common_cum,
        "default_series": [f"{LABEL[t]} 누적" for t in DUV],
        "description": (
            "DUV 노광기의 누적 판매를 광원별로 나눴다. ArFi(액침, 193nm)는 EUV 직전 세대 첨단 공정의 주력이고, "
            "ArF dry(193nm)·KrF(248nm)·i-line(365nm)은 파장이 길어 성숙 공정(전력반도체·디스플레이 구동칩·센서·"
            "아날로그)과 첨단 칩의 비핵심 층에 쓰인다. 블랭크마스크도 노광 파장마다 규격이 달라, 어느 광원의 장비가 "
            "늘어나는지가 제품 믹스를 가늠하게 해 준다. 'DUV 합계'는 칩으로 켠다."
        ),
        "note": (f"{last} 기준 2013년 이후분 {cum_d:,}대(" + " · ".join(f"{LABEL[t]} {cum_t[t]:,}" for t in DUV) + "). DUV는 1980년대부터 팔려 실제 설치 대수는 훨씬 많고, "
                 "공개 표가 2013년부터라 그 이후분만 셌다. 오래된 장비의 폐기·이전은 반영하지 않았다."),
        "series": {**{f"{LABEL[t]} 누적": t_pts[t] for t in DUV}, "DUV 합계": d_pts},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ASML: 분기 {len(quarters)}개(~{last}) 검증 통과 · EUV 누적 {cum_e} · DUV 누적(2013~) {cum_d:,}")
    capacity(annual, quarters, common)


def capacity(annual, quarters, common):
    """연간 판매 vs ASML이 밝힌 생산능력. 생산능력은 정기 공시가 아니라 실적 발표·투자자의 날 문장이라
    manual/asml_capacity.csv에 원문 인용과 함께 둔다. 진행 중인 해는 지금까지 분기 × (4/분기수)로 연환산한다."""
    cap = list(csv.DictReader((ROOT / "manual" / "asml_capacity.csv").open(encoding="utf-8")))

    # 연간 실적: 2016년까지는 연간보고서 행, 2017년부터는 분기 합
    yearly = {t: {} for t in TECH}
    for y, a in annual.items():
        for t in TECH:
            if str(a[t]).strip():
                yearly[t][y] = num(a[t])
    by_year = {}
    for r in quarters:
        by_year.setdefault(int(r["period"][:4]), []).append(r)
    run_rate = {}
    for y, rs in by_year.items():
        if y <= 2016:
            continue
        for t in TECH:
            s = sum(num(r[t]) for r in rs)
            if len(rs) == 4:
                yearly[t][y] = s
            else:
                run_rate.setdefault(t, {})[y] = round(s * 4 / len(rs), 1)
    part_year = max(by_year)
    part_q = len(by_year[part_year])

    def pts(d):
        return [[f"{y}-01-01", v] for y, v in sorted(d.items())]

    def capser(tech, kinds):
        return [[f"{r['year']}-01-01", float(r["capacity"])] for r in cap
                if r["tech"] == tech and r["kind"] in kinds]
    duv_year = {y: sum(yearly[t].get(y, 0) for t in DUV) for y in yearly["arfi"]}
    duv_run = {y: sum(run_rate.get(t, {}).get(y, 0) for t in DUV) for y in run_rate.get("arfi", {})}
    common_y = {**common, "unit": "대", "frequency": "yearly", "full_range": True}
    rr_label = f"{part_year} 연환산({part_q}분기×{4 // part_q if 4 % part_q == 0 else round(4 / part_q, 2)})"

    euv_now = run_rate.get("euv", {}).get(part_year)
    cap26 = next((float(r["capacity"]) for r in cap if r["tech"] == "euv" and r["year"] == str(part_year) and r["kind"] == "stated"), None)
    (OUT / "asml_euv_capacity.json").write_text(json.dumps({
        "id": "asml_euv_capacity", "name": "ASML EUV — 연간 판매 vs 생산능력", **common_y,
        "default_series": ["EUV 판매(연간 실적)", rr_label, "생산능력(당해 발표)", "생산능력(중기 목표)", "생산능력(증설 계획)"],
        "series": {
            "EUV 판매(연간 실적)": pts(yearly["euv"]),
            rr_label: pts(run_rate.get("euv", {})),
            "생산능력(당해 발표)": capser("euv", {"stated"}),
            "생산능력(중기 목표)": capser("euv", {"target"}),
            "생산능력(증설 계획)": capser("euv", {"plan"}),
        },
        "description": (
            "ASML이 그해 EUV를 몇 대까지 만들 수 있다고 밝힌 생산능력과 실제 매출 인식 대수를 겹쳤다. 실적이 생산능력에 "
            "바짝 붙으면 공급이 빠듯하다는 뜻이고, 그 뒤엔 증설 발표가 따라온다. 블랭크마스크 수요는 장비가 늘어나는 "
            "속도를 따라가므로, 증설 계획선이 곧 몇 년 뒤 EUV 블랭크마스크 수요의 기울기다."
        ),
        "note": (f"{part_year}년 연환산 {euv_now}대 vs 당해 생산능력 약 {cap26:.0f}대"
                 f"({euv_now / cap26 * 100:.0f}%). 2022년 투자자의 날 목표(2025~26년 90대)는 2026년 실제 발표 65대로 "
                 "낮아졌다. 생산능력은 정기 공시가 아니라 실적 발표·투자자의 날 문장이고 정의도 조금씩 다르다(출하 가능 대수, "
                 "Low-NA만 등). 판매는 매출 인식 기준이라 출하와 시차가 있어 비율은 '가동률'이 아니라 계획 대비 실현 정도의 "
                 "근사치다. 2021년은 '45~50대'의 중간값, 증설 계획은 '+30%'를 곱한 값. 원문은 manual/asml_capacity.csv."),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    imm_now = run_rate.get("arfi", {}).get(part_year)
    (OUT / "asml_duv_capacity.json").write_text(json.dumps({
        "id": "asml_duv_capacity", "name": "ASML DUV — 연간 판매 vs 생산능력", **common_y,
        "default_series": ["ArFi 판매(연간 실적)", f"ArFi {rr_label}", "ArFi 생산능력(발표·계획)"],
        "series": {
            "ArFi 판매(연간 실적)": pts(yearly["arfi"]),
            f"ArFi {rr_label}": pts(run_rate.get("arfi", {})),
            "ArFi 생산능력(발표·계획)": capser("arfi", {"stated", "plan"}),
            "DUV 전체 판매(연간 실적)": pts(duv_year),
            f"DUV 전체 {rr_label}": pts(duv_run),
            "DUV 전체 생산능력(중기 목표)": capser("duv", {"target"}),
        },
        "description": (
            "DUV는 액침(ArFi) 생산능력만 따로 밝힌다. 액침은 EUV 직전 세대 첨단 공정의 주력이라 EUV와 함께 첨단 "
            "블랭크마스크 수요를 이룬다. DUV 전체(ArFi·ArF dry·KrF·i-line)와 2022년 투자자의 날 목표(600대)는 칩으로 켠다."
        ),
        "note": (f"{part_year}년 ArFi 연환산 {imm_now}대 vs 생산능력 약 130대 — EUV와 달리 여유가 있다. "
                 "2027년은 '+30%' 계획을 곱한 값. 판매는 매출 인식 기준, 생산능력은 발표 문장(정기 공시 아님)."),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  생산능력: EUV {part_year} 연환산 {euv_now} / {cap26} · ArFi 연환산 {imm_now}")


if __name__ == "__main__":
    run()

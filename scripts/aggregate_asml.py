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
    for r in quarters:
        cum_e += num(r["euv"])
        cum_d += sum(num(r[t]) for t in DUV)
        e_pts.append([qdate(r["period"]), cum_e])
        d_pts.append([qdate(r["period"]), cum_d])
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
        "description": (
            "ArFi·ArF dry·KrF·i-line을 합친 DUV 노광기의 누적 판매. 성숙 공정(전력반도체·디스플레이 구동칩·센서 등)과 "
            "첨단 공정의 비핵심 층에 쓰이며, 블랭크마스크 물량 측면에서는 EUV보다 훨씬 많은 바탕을 이룬다."
        ),
        "note": (f"{last} 기준 2013년 이후분 {cum_d:,}대. DUV는 1980년대부터 팔려 실제 설치 대수는 훨씬 많고, "
                 "공개 표가 2013년부터라 그 이후분만 셌다. 오래된 장비의 폐기·이전은 반영하지 않았다."),
        "series": {"DUV 누적(2013~)": d_pts},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ASML: 분기 {len(quarters)}개(~{last}) 검증 통과 · EUV 누적 {cum_e} · DUV 누적(2013~) {cum_d:,}")


if __name__ == "__main__":
    run()

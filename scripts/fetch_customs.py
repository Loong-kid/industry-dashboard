# -*- coding: utf-8 -*-
"""관세청 수출입무역통계 → data/semicon/*.json (반도체 소부장 품목).

수집: 공공데이터포털 관세청 품목별 국가별 수출입실적(GW).
키는 env CUSTOMS_API_KEY(로컬)/GitHub Secret(CI). **Decoding 키**를 넣어야 한다
(params= 로 넘기면 requests가 인코딩하므로 Encoding 키를 쓰면 이중 인코딩 → 미등록키 에러).

    CUSTOMS_API_KEY=... python scripts/fetch_customs.py

카드는 전부 **월별 원값**이다(급변 시점 탐지가 목적이라 이동평균을 쓰지 않는다).

API가 주는 측정값은 4개뿐: expDlr/expWgt/impDlr/impWgt (금액 US$, 중량 kg).
**수량(개·㎡)은 제공되지 않아** 단가는 $/kg으로만 계산 가능하다.

API 함정(실측):
  - cntyCd는 명세상 필수지만 생략하면 전 세계 국가별로 한 번에 반환된다(국가 루프 불필요).
  - 조회구간은 1년 이내만 허용(초과 시 resultCode 99) → 연도 단위 루프.
  - 응답 첫 행이 year="총계", hsCd="-" 인 집계 행이라 거르지 않으면 수치가 2배가 된다.
  - year 형식은 "2025.01"(점 구분), 금액은 US$ 1달러 단위, 중량은 kg.
"""
import json
import os
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "semicon"
API_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
API_KEY = os.environ.get("CUSTOMS_API_KEY", "").strip()
SOURCE = "관세청 수출입무역통계 (공공데이터포털)"
SOURCE_URL = "https://www.data.go.kr/data/15100475/openapi.do"

# codes: [(HS 10단위, 시작연도, 종료연도 or None)] — 관세율표 개정으로 번호가 바뀐 품목은
# 구/신 코드를 이어 붙여 연속 시계열을 만든다(정의가 같을 때만).
#
# 실측으로 확인한 코드 이력:
#   - 3701991000 반도체 제조용: 2000년부터 번호 변경 없이 연속. 2022년 개정 영향 없음.
#   - 디스플레이용 블랭크마스크: 2017년 3701309930으로 신설 → 2022년 개정 때 3701304000으로
#     번호만 변경(품목명·정의 동일). 2016년 이전에는 전용 코드가 없어 추적 불가.
#   - 8486902030 정전척: 2022년 신설.
ITEMS = [
    {"key": "blank_semi", "name": "블랭크마스크 (반도체용)", "short": "반도체용",
     "codes": [("3701991000", 2000, None)],
     "note": "HS 3701991000 · 2000년부터 코드 변경 없이 연속"},
    {"key": "blank_disp", "name": "블랭크마스크 (디스플레이용)", "short": "디스플레이용",
     "codes": [("3701309930", 2017, 2021), ("3701304000", 2022, None)],
     "note": "HS 3701309930(2017~2021) → 3701304000(2022~). 2022년 관세율표 개정으로 "
             "번호만 바뀌었고 품목 정의는 동일해 이어 붙였다. 2016년 이전은 전용 코드 없음"},
    {"key": "esc", "name": "정전척 ESC", "short": "정전척(ESC)",
     "codes": [("8486902030", 2022, None)],
     "note": "HS 8486902030 · 2022년 관세율표 개정으로 신설(이전 자료 없음)"},
]

# 시도별 품목별은 **다른 엔드포인트**(sidoitemtrade)이고 제약이 많다. 실측 확인:
#   - `sidoCd` 필수(대구=27). 없으면 resultCode 99 "필수 요청변수 누락"
#   - HS는 **6단위까지만**. 10단위를 넣어도 6단위로 뭉쳐서 반환한다
#   - 기간을 어떻게 주든 priodTitle이 연 단위 → **월별이 필요하면 월 1회씩 호출**
#   - 금액 단위가 **천달러**(nitemtrade는 1달러 단위)
# 에스앤에스텍이 대구 소재 유일 블랭크마스크 제조사라, 대구 6단위 집계가 전국보다
# 훨씬 타이트한 회사 대리지표가 된다.
REGION_URL = "https://apis.data.go.kr/1220000/sidoitemtrade/getSidoitemtradeList"
REGION_START = 2021
REGIONS = [{
    "key": "daegu_blank", "sido": "27", "name": "대구 블랭크마스크",
    "codes": [("370199", "반도체용 계열"), ("370130", "디스플레이용 계열")],
    "note": "HS 6단위 집계(시도별 품목별 API의 최대 깊이). 370199에는 3701991000(반도체용 "
            "블랭크마스크) 외 인쇄제판용 등이, 370130에는 3701304000(디스플레이용) 외 "
            "인쇄제판·PCB용이 섞이지만 대구에서는 비중이 미미하다",
}]

TOP_N = 6        # 국가별 금액 카드에 표시할 상위 국가 수
TOP_N_PRICE = 4     # 국가별 단가 카드에 넣을 최대 국가 수
MIN_WGT_SHARE = 0.03  # 단가 카드 국가 선정: 최근 12개월 중량 비중 하한
MIN_PT_SHARE = 0.01   # 단가 카드 점 선정: 그 달 전체 중량 대비 하한
USD_M = 1_000_000.0


def fetch_year(session, hs, year):
    """(월, 국가, expDlr, expWgt, impDlr, impWgt) 리스트."""
    last_err = None
    for _ in range(5):
        try:
            r = session.get(API_URL, params={
                "serviceKey": API_KEY, "strtYymm": f"{year}01",
                "endYymm": f"{year}12", "hsSgn": hs,
            }, timeout=(5, 60))
            r.raise_for_status()
            root = ET.fromstring(r.text)
            code = root.findtext(".//resultCode")
            if code != "00":
                raise RuntimeError(f"resultCode={code} {root.findtext('.//resultMsg')}")
            rows = []
            for it in root.findall(".//item"):
                if (it.findtext("hsCd") or "") in ("", "-"):
                    continue  # 총계 행
                ym = (it.findtext("year") or "").replace(".", "-")
                if len(ym) != 7:
                    continue
                rows.append((
                    f"{ym}-01", it.findtext("statCdCntnKor1") or "기타",
                    int(it.findtext("expDlr") or 0), int(it.findtext("expWgt") or 0),
                    int(it.findtext("impDlr") or 0), int(it.findtext("impWgt") or 0),
                ))
            return rows
        except Exception as e:  # noqa
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"{hs} {year} 실패: {last_err}")


def collect(session, item):
    """품목 1개의 전 기간 원자료. 코드 체인을 순서대로 이어 붙인다."""
    rows, this_year = [], date.today().year
    for hs, y0, y1 in item["codes"]:
        for y in range(y0, (y1 or this_year) + 1):
            rows.extend(fetch_year(session, hs, y))
            time.sleep(0.15)
    return rows


def fetch_region_month(session, sido, hs, ym):
    """시도×HS6 한 달치 (수출 천$, 수입 천$). 값이 없으면 (0, 0)."""
    last_err = None
    for _ in range(4):
        try:
            r = session.get(REGION_URL, params={
                "serviceKey": API_KEY, "strtYymm": ym, "endYymm": ym,
                "sidoCd": sido, "hsSgn": hs}, timeout=(5, 45))
            r.raise_for_status()
            root = ET.fromstring(r.text)
            if root.findtext(".//resultCode") != "00":
                raise RuntimeError(root.findtext(".//resultMsg"))
            for it in root.findall(".//item"):
                if not it.findtext("hsSgn"):
                    continue  # 총계 행(hsSgn 없음)
                num = lambda t: int((it.findtext(t) or "0").replace(",", "").strip() or 0)
                return num("expUsdAmt"), num("impUsdAmt")
            return 0, 0
        except Exception as e:  # noqa
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"{sido}/{hs}/{ym} 실패: {last_err}")


def collect_region(session, reg):
    """{HS6: {월: [수출 백만$, 수입 백만$]}} — 월 1회씩 호출해 월별로 만든다."""
    this = date.today()
    out = {}
    for hs, _label in reg["codes"]:
        months = {}
        for y in range(REGION_START, this.year + 1):
            for m in range(1, 13):
                if y == this.year and m > this.month:
                    break
                ym = f"{y}{m:02d}"
                e, i = fetch_region_month(session, reg["sido"], hs, ym)
                if e or i:
                    months[f"{y}-{m:02d}-01"] = [e / 1000.0, i / 1000.0]  # 천$ → 백만$
                time.sleep(0.05)
        out[hs] = months
    return out


def doc(ind_id, name, unit, series, default, updated, note=None):
    d = {
        "id": ind_id, "name": name, "unit": unit, "frequency": "monthly",
        "source": SOURCE, "source_url": SOURCE_URL,
        "updated": updated, "fetched": date.today().isoformat(),
        "default_series": default, "series": series,
    }
    if note:
        d["note"] = note
    return d


def write(ind_id, payload):
    (OUT_DIR / f"{ind_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = sum(len(v) for v in payload["series"].values())
    print(f"  {ind_id}: {len(payload['series'])}시리즈 {n:,}점 (~{payload['updated']})")


def by_country(rows, amt_idx, wgt_idx, months, top_n):
    """최근 12개월 금액 기준 상위 국가 목록과 {국가: {월: [금액, 중량]}}."""
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        a = agg[r[1]][r[0]]
        a[0] += r[amt_idx]
        a[1] += r[wgt_idx]
    recent = set(months[-12:])
    scored = [(c, sum(v[0] for m, v in mm.items() if m in recent)) for c, mm in agg.items()]
    top = [c for c, v in sorted(scored, key=lambda kv: -kv[1]) if v > 0][:top_n]
    return top, agg


def run():
    if not API_KEY:
        raise SystemExit("CUSTOMS_API_KEY 미설정: env(로컬) 또는 GitHub Secret(CI)로 주입하세요.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    compare_exp, compare_imp, last_all = {}, {}, ""

    for item in ITEMS:
        rows = collect(session, item)
        if not rows:
            print(f"  {item['key']}: 데이터 없음 — 건너뜀")
            continue

        tot = defaultdict(lambda: [0, 0, 0, 0])  # 월 → [expDlr, expWgt, impDlr, impWgt]
        for m, _c, ed, ew, idl, iw in rows:
            a = tot[m]
            a[0] += ed
            a[1] += ew
            a[2] += idl
            a[3] += iw
        months = sorted(tot)
        last = months[-1]
        last_all = max(last_all, last)
        key, note = item["key"], item["note"]

        # 1) 금액 (백만$)
        write(f"{key}_amount", doc(
            f"{key}_amount", f"{item['name']} 수출입 금액", "백만$", {
                "수출액": [[m, round(tot[m][0] / USD_M, 3)] for m in months],
                "수입액": [[m, round(tot[m][2] / USD_M, 3)] for m in months],
                "무역수지": [[m, round((tot[m][0] - tot[m][2]) / USD_M, 3)] for m in months],
            }, ["수출액", "수입액"], last, note))

        # 2) 중량 (kg)
        write(f"{key}_weight", doc(
            f"{key}_weight", f"{item['name']} 수출입 중량", "kg", {
                "수출중량": [[m, tot[m][1]] for m in months],
                "수입중량": [[m, tot[m][3]] for m in months],
            }, ["수출중량", "수입중량"], last, note))

        # 3) 단가 ($/kg) — 중량 0인 달은 점을 만들지 않는다
        write(f"{key}_price", doc(
            f"{key}_price", f"{item['name']} 단가", "$/kg", {
                "수출단가": [[m, round(tot[m][0] / tot[m][1], 1)] for m in months if tot[m][1]],
                "수입단가": [[m, round(tot[m][2] / tot[m][3], 1)] for m in months if tot[m][3]],
            }, ["수출단가", "수입단가"], last,
            f"{note} · 금액 ÷ 중량. API에 수량이 없어 개당 단가는 산출 불가"))

        # 4~6) 국가별
        for direction, ai, wi in (("수출", 2, 3), ("수입", 4, 5)):
            top, agg = by_country(rows, ai, wi, months, TOP_N)
            if not top:
                continue
            tag = "exp" if direction == "수출" else "imp"
            write(f"{key}_{tag}_country", doc(
                f"{key}_{tag}_country", f"{item['name']} 국가별 {direction}액", "백만$",
                {c: [[m, round(agg[c][m][0] / USD_M, 3)] for m in months if m in agg[c]]
                 for c in top},
                top[:3], last, f"{note} · 최근 12개월 {direction}액 상위 {len(top)}개국"))

            # 단가는 수출 쪽만(제품 믹스 판별 목적).
            # 소량 거래국은 단가가 수천 $/kg까지 튀어 축을 못 쓰게 만든다. 두 겹으로 거른다:
            #   (1) 국가 선정 — 최근 12개월 '중량' 비중이 MIN_WGT_SHARE 미만이면 제외
            #   (2) 점 선정  — 그 달 전체 중량의 MIN_PT_SHARE 미만인 달은 점을 만들지 않음
            if direction != "수출":
                continue
            recent_wgt = sum(tot[m][1] for m in months[-12:]) or 1
            price = {}
            for c in top:
                if len(price) >= TOP_N_PRICE:
                    break
                share = sum(agg[c][m][1] for m in months[-12:] if m in agg[c]) / recent_wgt
                if share < MIN_WGT_SHARE:
                    continue
                pts = [[m, round(agg[c][m][0] / agg[c][m][1], 1)] for m in months
                       if m in agg[c] and agg[c][m][1] >= tot[m][1] * MIN_PT_SHARE > 0]
                if pts:
                    price[c] = pts
            if price:
                write(f"{key}_exp_price", doc(
                    f"{key}_exp_price", f"{item['name']} 국가별 수출단가", "$/kg",
                    price, list(price)[:3], last,
                    f"{note} · 같은 HS코드라도 대상국별 단가 차이가 제품 믹스를 드러낸다. "
                    f"물량이 적어 단가가 튀는 국가·월은 제외(최근 12개월 중량 비중 "
                    f"{MIN_WGT_SHARE:.0%} 이상, 월 중량 비중 {MIN_PT_SHARE:.0%} 이상)"))

        if key.startswith("blank_"):
            compare_exp[item["short"]] = [[m, round(tot[m][0] / USD_M, 3)] for m in months]
            compare_imp[item["short"]] = [[m, round(tot[m][2] / USD_M, 3)] for m in months]

    if compare_exp:
        write("blank_export_compare", doc(
            "blank_export_compare", "블랭크마스크 수출액 (용도별)", "백만$",
            compare_exp, list(compare_exp), last_all,
            "반도체용(HS 3701991000)과 디스플레이용(3701304000)은 크기 기준으로 원래 다른 호에 "
            "속한다. 한 회사가 양쪽을 함께 공급하는 구조라 나란히 본다"))
    if compare_imp:
        write("blank_import_compare", doc(
            "blank_import_compare", "블랭크마스크 수입액 (용도별)", "백만$",
            compare_imp, list(compare_imp), last_all))

    # 시도별(대구) — 회사 대리지표용
    for reg in REGIONS:
        data = collect_region(session, reg)
        months = sorted({m for mm in data.values() for m in mm})
        if not months:
            print(f"  {reg['key']}: 데이터 없음 — 건너뜀")
            continue
        series = {}
        for hs, label in reg["codes"]:
            series[label] = [[m, round(data[hs][m][0], 3)] for m in months if m in data[hs]]
        series["합계"] = [[m, round(sum(data[hs].get(m, [0, 0])[0]
                                      for hs, _ in reg["codes"]), 3)] for m in months]
        write(f"{reg['key']}_export", doc(
            f"{reg['key']}_export", f"{reg['name']} 수출액 (시도별)", "백만$",
            series, ["합계"], months[-1], reg["note"]))


if __name__ == "__main__":
    run()

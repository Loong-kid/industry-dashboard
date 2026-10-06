"""HOYA 시트의 공표 사업부 매출과 제품별 추정을 실제 달력 분기로 변환한다."""
import json
import math
import re
from pathlib import Path

from aggregate_blankmask_ir import period_date

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "manual" / "hoya_sheet_revenue.json"
OUT = ROOT / "data" / "semicon"
SPECS = {
    "hoya_electronics_revenue_estimate": (
        "HOYA · Electronics 매출 · 공표 실적", "Electronics 매출 (공표 실적)",
        "LSI·FPD·HDD를 묶은 전자 제품군 매출입니다. Information Technology 사업부 안에서 블랭크마스크와 관련된 제품 매출의 비중을 확인할 수 있습니다.",
        "HOYA IR의 세부 매출 공표값을 사용자 시트에 정리한 실적입니다. 광학 제품 등을 포함하는 전체 IT 사업부와 범위가 다릅니다. 하위 제품군 LSI·FPD·HDD의 매출은 별도의 추정치입니다.",
    ),
    "hoya_lsi_revenue_estimate": (
        "HOYA · LSI 블랭크마스크 매출 · EUV·DUV 추정", "LSI · EUV·DUV 블랭크마스크 (추정)",
        "반도체용 블랭크마스크 매출 추정입니다. HOYA LSI 제품군은 EUV와 DUV를 함께 포함하며, EUV 단독 매출로 분리된 값은 아닙니다.",
        "공시 성장률과 컨콜에서 언급된 금액을 바탕으로 산출한 사용자 시트 추정입니다. 금액은 명목 엔화 기준이며, 표시 기간의 YoY는 공시된 LSI 명목 성장률과 대조했습니다.",
    ),
    "hoya_fpd_revenue_estimate": (
        "HOYA · FPD 디스플레이 마스크 매출 · 추정", "FPD · 디스플레이 마스크 (추정)",
        "시트의 FPD 디스플레이용 제품 매출 추정입니다. HOYA는 이 제품군을 디스플레이 제조용 포토마스크 사업으로 설명합니다.",
        "공시 성장률과 컨콜 금액을 바탕으로 산출한 사용자 추정입니다. 디스플레이 블랭크마스크만의 매출로 한정된 금액은 아니므로 반도체 LSI와 제품 범위를 구분합니다.",
    ),
    "hoya_hdd_revenue_estimate": (
        "HOYA · HDD 유리기판 매출 · 추정", "HDD 유리기판 (추정)",
        "시트 메모에 따른 하드디스크용 유리기판 매출 추정입니다. Electronics 안에서 LSI·FPD와 함께 구성 비중을 확인하는 참고 지표입니다.",
        "블랭크마스크 매출에 포함하지 않습니다. 사용자 시트의 제품별 추정 금액입니다.",
    ),
}


def build_docs(raw, official=None):
    if raw["unit"] != "million_jpy":
        raise ValueError("Expected million JPY")
    if not raw["source_url"].startswith("https://docs.google.com/spreadsheets/d/"):
        raise ValueError("Missing Sheet provenance")
    quarters = raw["calendar_quarters"]
    dates = [period_date(q) for q in quarters]
    if len(set(dates)) != len(dates) or any(d > raw["checked"] for d in dates):
        raise ValueError("Duplicate or future period")
    if len(quarters) != len(raw["source_headers"]):
        raise ValueError("Missing period mapping")
    for q, header in zip(quarters, raw["source_headers"]):
        match = re.fullmatch(r"(\d{2})\.([1-4])Q", header)
        if not match:
            raise ValueError("Invalid source quarter")
        # シート見出しは実際の暦四半期より一つ先。元の値は変更しない。
        source_index = (2000 + int(match[1])) * 4 + int(match[2]) - 1
        calendar_index = int(q[:4]) * 4 + int(q[-1]) - 1
        if source_index - calendar_index != 1:
            raise ValueError("Source/calendar quarter mismatch")
    anchor = raw["period_mapping"]["anchor"]
    if anchor["calendar_quarter"] != quarters[0] or anchor["sheet_header"] != raw["source_headers"][0]:
        raise ValueError("Incorrect period anchor")
    if abs(anchor["group_revenue_million_jpy"] / 1000 - anchor["official_revenue_billion_jpy"]) > 0.05:
        raise ValueError("Group revenue does not match official quarter anchor")
    metrics = {m["id"]: m for m in raw["metrics"]}
    if set(metrics) != set(SPECS) or len(metrics) != len(raw["metrics"]):
        raise ValueError("Missing or duplicate metric")
    for m in metrics.values():
        expected_status = "actual" if m["id"] == "hoya_electronics_revenue_estimate" else "estimate"
        if m["status"] != expected_status or len(m["values"]) != len(dates):
            raise ValueError("Incorrect status or missing values")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in m["values"]):
            raise ValueError("Invalid revenue value")
    for i in range(len(dates)):
        parts = sum(metrics[id_]["values"][i] for id_ in SPECS if id_ != "hoya_electronics_revenue_estimate")
        if abs(parts - metrics["hoya_electronics_revenue_estimate"]["values"][i]) > 0.2:
            raise ValueError("Electronics does not reconcile with product estimates")
    if official is None:
        official = json.loads((ROOT / "manual/blankmask_japan_ir.json").read_text(encoding="utf8"))
    growth = {r["period"]: r["value"] for r in official["records"] if r["company"] == "HOYA" and r["metric"] == "lsi_yoy"}
    lsi = dict(zip(quarters, metrics["hoya_lsi_revenue_estimate"]["values"]))
    for quarter, value in lsi.items():
        prior = f"{int(quarter[:4])-1}{quarter[4:]}"
        if prior in lsi and quarter in growth:
            if abs((value / lsi[prior] - 1) * 100 - growth[quarter]) > 0.05:
                raise ValueError("LSI estimate YoY differs from official nominal growth")
    docs = {}
    for id_, (name, label, description, note) in SPECS.items():
        metric = metrics[id_]
        points = sorted([[d, round(v / 100, 4)] for d, v in zip(dates, metric["values"])])
        docs[id_] = dict(
            id=id_, name=name, unit="억 엔", frequency="quarterly", manual=True,
            source="사용자 구글 시트 · HOYA", source_url=raw["source_url"],
            updated=points[-1][0], fetched=raw["checked"], span_gaps=False,
            description=description, note=note + " 달력 분기로 통일한 분기별 3개월 금액입니다.",
            series={label: points}, default_series=[label],
            quarter_labels=True, quarterly_revenue_summary=True, revenue_status=metric["status"],
            point_sources={d: {"url": raw["source_url"] + "&range=" + metric["range"], "label": "HOYA 시트 · " + metric["range"]} for d, _ in points},
            methodology_url=raw["estimation_basis"]["scope_url"],
            basis_details=[
                {"label": "자료 성격" if metric["status"] == "actual" else "추정 근거", "value": "HOYA IR에서 공표한 Electronics 세부 매출 실적을 사용자 시트에 정리한 값입니다." if metric["status"] == "actual" else raw["estimation_basis"]["user_explanation"]},
                {"label": "시트 메모", "value": metric.get("sheet_note", "LSI·FPD·HDD 합계")},
                {"label": "분기 정렬", "value": raw["period_mapping"]["note"]},
                {"label": "확보 기간", "value": "2023 Q2~2026 Q1 · 입력된 12개 분기. 이후 빈 셀은 연장 추정하지 않았습니다."},
            ],
        )
    return docs


def run():
    docs = build_docs(json.loads(INPUT.read_text(encoding="utf8")))
    OUT.mkdir(parents=True, exist_ok=True)
    for id_, doc in docs.items():
        (OUT / f"{id_}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"HOYA 시트: {len(docs)}개 카드 · 각 {len(next(iter(docs.values()))['point_sources'])}개 분기")


if __name__ == "__main__":
    run()

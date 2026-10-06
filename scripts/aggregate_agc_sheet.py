"""AGC 구글 시트의 선택된 실적·추정값 스냅샷을 카드로 변환한다."""
import json
import math
import re
from pathlib import Path

from aggregate_blankmask_ir import period_date

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "manual" / "agc_sheet_revenue.json"
OUT = ROOT / "data" / "semicon"
SPECS = {
    "agc_sheet_materials_revenue": (
        "AGC · 전자부재 매출 · 시트 정리값", "전자부재 매출 (공표값 반올림)", "reported_rounded",
        "EUV·DUV 추정의 배경이 되는 Electronic Materials 사업 매출입니다. 사용자 시트에 정리된 공표 실적의 반올림값입니다.",
        "위의 공식 IR 전자부재 매출 카드와 같은 사업부 범위이며, 시트의 반올림으로 값이 조금 다를 수 있습니다. 블랭크마스크 외에 다른 전자 소재를 포함합니다.",
    ),
    "agc_euv_revenue_estimate": (
        "AGC · EUV 블랭크마스크 매출 · 추정", "EUV Mask Blanks (추정)", "estimate",
        "사용자 구글 시트에 입력된 EUV Mask Blanks 분기 매출 추정치입니다. 분기별 추이를 같은 단위로 비교할 수 있습니다.",
        "AGC가 공개한 단독 분기 매출액이 아닌 사용자 추정치입니다. 추정 산식은 해당 셀에서 확인되지 않았습니다. 2024년 4개 분기 추정 합계는 400억 엔으로 기존 공식 연간 공개값과 일치합니다.",
    ),
    "agc_duv_substrate_revenue_estimate": (
        "AGC · DUV 포토마스크 기판 매출 · 추정", "DUV Photomask Substrate (추정)", "estimate",
        "사용자 구글 시트의 DUV Photomask Substrate 분기 매출 추정치입니다. 포토마스크용 기판 매출을 추적합니다.",
        "DUV 완성 블랭크마스크 매출과 제품 범위가 다릅니다. 사용자 추정치이며 추정 산식은 해당 셀에서 확인되지 않았습니다. EUV 완성 블랭크와 단순 합산해 전체 블랭크마스크 시장으로 해석하지 않습니다.",
    ),
}


def build_docs(raw):
    if raw["unit"] != "million_jpy":
        raise ValueError("Expected million JPY in the source snapshot")
    if not raw["source_url"].startswith("https://docs.google.com/spreadsheets/d/"):
        raise ValueError("Missing Google Sheet provenance")
    dates = []
    for label in raw["quarters"]:
        match = re.fullmatch(r"(\d{2})Q([1-4])", label)
        if not match:
            raise ValueError(f"Invalid calendar quarter: {label}")
        dates.append(period_date(f"20{match[1]}Q{match[2]}"))
    if len(set(dates)) != len(dates):
        raise ValueError("Duplicate quarters")
    if any(date > raw["checked"] for date in dates):
        raise ValueError("Source contains a future quarter")
    docs = {}
    for metric in raw["metrics"]:
        id_ = metric["id"]
        if id_ in docs:
            raise ValueError(f"Duplicate metric: {id_}")
        name, label, status, description, note = SPECS[id_]
        if metric["status"] != status:
            raise ValueError(f"Incorrect disclosure status: {id_}")
        values = metric["values"]
        if len(values) != len(dates):
            raise ValueError(f"Missing quarter values: {id_}")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError(f"Non-numeric or negative revenue: {id_}")
        # 百万円 → 億円。シートのラベルを使用し、全社売上の列から推測しない。
        points = sorted([[date, round(value / 100, 4)] for date, value in zip(dates, values)])
        docs[id_] = dict(
            id=id_, name=name, unit="억 엔", frequency="quarterly", manual=True,
            source="사용자 구글 시트 · AGC", source_url=raw["source_url"],
            updated=points[-1][0], fetched=raw["checked"], span_gaps=False,
            description=description,
            note=note + f" 달력 분기 기준의 분기별 3개월 금액입니다. 원본 백만 엔을 100으로 나눠 억 엔으로 표시했습니다. 시트 확인일 {raw['checked']}.",
            series={label: points}, default_series=[label],
            quarter_labels=True, quarterly_revenue_summary=True,
            point_sources={date: {"url": raw["source_url"] + "&range=" + metric["range"], "label": "AGC 시트 · " + metric["range"]} for date, _ in points},
            revenue_status=status,
        )
    if set(docs) != set(SPECS):
        raise ValueError("Missing AGC revenue metric")
    return docs


def run():
    docs = build_docs(json.loads(INPUT.read_text(encoding="utf8")))
    OUT.mkdir(parents=True, exist_ok=True)
    for id_, doc in docs.items():
        (OUT / f"{id_}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"AGC 시트: {len(docs)}개 카드 · 각 {len(next(iter(docs.values()))['point_sources'])}개 분기")


if __name__ == "__main__":
    run()

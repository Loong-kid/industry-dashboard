# -*- coding: utf-8 -*-
"""TI 웹앱의 공개 VLCC 성약 응답을 누적하고 7일 TCE 중앙값을 산출한다.

계약형 공식 API와 다른 공개 웹앱 엔드포인트다. 로그인/유료 Last Done은 사용하지 않는다.
"""
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import DATA_DIR, UA

API_URL = "https://fixturesappfunctionsproduction.azurewebsites.net/api/v1/fixtures"
SOURCE_URL = "https://app.tankersinternational.com/"
CATEGORY_LABELS = {
    "Modern (Scrubber)": "Modern · 스크러버",
    "Modern (VLSFO)": "Modern · VLSFO",
    "+15 Years (Scrubber)": "15년 초과 · 스크러버",
    "+15 Years (VLSFO)": "15년 초과 · VLSFO",
}
ROUTES = ["AG → China", "AG → Korea", "WAF → China", "USG → China", "Brazil → China"]
OVERALL = "전체 VLCC"
NOTE = (
    "무료 공개 자료는 지연될 수 있습니다. TI가 공개한 VLCC 성약 표본이며 전체 시장 평균이나 "
    "TI 풀의 실현 수익이 아닙니다. 발표일 기준으로 집계하고, 이후 상태·TCE 정정 시 과거 집계도 수정합니다."
)


def number(value):
    """0/음수는 실제 TCE일 수 있다. 결측·무한대·반올림된 K/Day 표시는 사용하지 않는다."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def normalize_fixture(row):
    fixture_id = row.get("FixtureId")
    if not re.fullmatch(r"\d+", str(fixture_id)) or not row.get("Id"):
        raise ValueError("TI 성약 ID 누락")
    reported = row.get("ReportedTime") or ""
    try:
        # 영어 월 이름은 CI/로컬 locale에 의존하지 않고 해석한다.
        day, month, year, *_ = reported.split()
        month_number = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split().index(month) + 1
        reported_date = date(int(year), month_number, int(day)).isoformat()
    except (ValueError, TypeError):
        published = row.get("PublicationTimestamp") or ""
        try:
            reported_date = date.fromisoformat(published[:10]).isoformat()
        except ValueError as exc:
            raise ValueError(f"TI 성약 {fixture_id}: 발표일 파싱 실패") from exc
    actual = row.get("ActualValues") or {}
    tce = number(actual.get("ActTcPerDayIncIdle"))
    if tce is None:
        text = row.get("ActualTCEPerDay") or ""
        if re.fullmatch(r"USD\s+-?[\d,]+(?:\.\d+)?", text):
            tce = number(text.removeprefix("USD").strip().replace(",", ""))
    load = row.get("SubLoadArea") or row.get("LoadArea") or "미공개"
    discharge = row.get("SubDischargeArea") or "미공개"
    return {
        "fixture_id": str(fixture_id), "id": str(row["Id"]),
        "reported_date": reported_date, "reported_time": reported,
        "published": row.get("PublicationTimestamp") or "",
        "vessel": row.get("Vessel") or "미공개", "operator": row.get("Operator") or "미공개",
        "charterer": row.get("Charterer") or "미공개", "status": row.get("Status") or "Unknown",
        "category": row.get("VesselCategory") or "Unknown", "vessel_age": number(row.get("VesselAge")),
        "load_area": load, "discharge_area": discharge, "route": f"{load} → {discharge}",
        "tce": tce, "rv_tce": number(actual.get("RvTcPerDayExIdle")),
        "cargo_tonnes": number(actual.get("CargoSize")),
        "source_url": f"{SOURCE_URL}fixtures/{fixture_id}",
    }


def parse_payload(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("Results"), list):
        raise ValueError("TI 공개 응답 형식 변경")
    if payload.get("HasMoreResults") or payload.get("ContinuationToken"):
        raise ValueError("TI 응답이 페이지로 분할됨: 페이지 수집 구현 확인 필요, 기존 데이터 유지")
    rows = payload["Results"]
    if not rows or payload.get("Count", len(rows)) != len(rows):
        raise ValueError("TI 공개 응답이 비어 있거나 건수가 일치하지 않음")
    fixtures = [normalize_fixture(row) for row in rows]
    if len({row["fixture_id"] for row in fixtures}) != len(fixtures):
        raise ValueError("TI 응답에 중복 성약 ID")
    if not any(row["status"] == "Fixed" and row["tce"] is not None for row in fixtures):
        raise ValueError("TI 공개 응답에 유효한 확정 성약 TCE가 없음")
    return fixtures


def merge_fixtures(previous, incoming):
    """현재 응답 밖으로 밀려난 성약은 보존하고, 동일 성약의 상태/결측 정정은 덮어쓴다."""
    merged = {row["fixture_id"]: row for row in previous}
    for row in incoming:
        merged[row["fixture_id"]] = row
    return sorted(merged.values(), key=lambda row: (row["reported_date"], row["reported_time"], row["fixture_id"]), reverse=True)


def aggregate(fixtures):
    """[D-6, D]의 확정 계약을 집계. 자료 시작 6일과 마지막 공개 발표일 이후는 생성하지 않는다."""
    first = min(date.fromisoformat(row["reported_date"]) for row in fixtures)
    last = max(date.fromisoformat(row["reported_date"]) for row in fixtures)
    by_day = defaultdict(list)
    for row in fixtures:
        if row["status"] == "Fixed":
            by_day[row["reported_date"]].append(row)
    categories = {OVERALL: [], **{label: [] for label in CATEGORY_LABELS.values()}}
    routes = {route: [] for route in ROUTES}
    category_counts = {key: [] for key in categories}
    route_counts = {key: [] for key in routes}
    counts = {"확정 성약": [], "TCE 공개 성약": []}
    current = first + timedelta(days=6)
    while current <= last:
        d = current.isoformat()
        window = [row for offset in range(7) for row in by_day[(current - timedelta(days=offset)).isoformat()]]
        valid = [row for row in window if row["tce"] is not None]
        counts["확정 성약"].append([d, len(window)])
        counts["TCE 공개 성약"].append([d, len(valid)])
        for key, points in categories.items():
            values = [row["tce"] for row in valid if key == OVERALL or CATEGORY_LABELS.get(row["category"]) == key]
            points.append([d, round(median(values), 2) if values else None])
            category_counts[key].append([d, len(values)])
        for key, points in routes.items():
            values = [row["tce"] for row in valid if row["route"] == key]
            points.append([d, round(median(values), 2) if values else None])
            route_counts[key].append([d, len(values)])
        current += timedelta(days=1)
    if not categories[OVERALL]:
        raise ValueError("TI 7일 집계에 필요한 발표일 범위가 부족함")
    return categories, routes, counts, category_counts, route_counts


def build_documents(fixtures, fetched, latest_response_date):
    categories, routes, counts, category_counts, route_counts = aggregate(fixtures)
    latest = max(row["reported_date"] for row in fixtures)
    first = min(row["reported_date"] for row in fixtures)
    common = {
        "frequency": "daily", "source": "Tankers International · 공개 VLCC 성약",
        "source_url": SOURCE_URL, "updated": latest, "fetched": fetched,
        "latest_response_date": latest_response_date, "data_stale_days": 10,
        "span_gaps": False, "change_mode": "none", "note": NOTE,
        "license_url": SOURCE_URL + "terms", "license": "TI 이용 조건 · 공식 API 계약은 별도",
        "basis_details": [
            {"label": "TCE 기준", "value": "ActTcPerDayIncIdle: 대기일을 포함한 항차 TCE(USD/day). WS 운임이나 대기일 제외 왕복 TCE와 다릅니다."},
            {"label": "7일 중앙값", "value": "각 발표일 D의 D-6~D에 공개된 Fixed 계약 중 TCE가 있는 성약만 집계. 성약당 동일 가중치이며 계약일·선적일 기준이 아닙니다."},
            {"label": "표본·수정", "value": f"현재 누적 발표일 {first}~{latest}. 조건부(On Subs)·실패(Failed) 제외. 같은 성약의 상태·TCE 수정 시 과거 시계열을 재산출합니다. 첫 6일은 집계하지 않습니다."},
            {"label": "자료 공백", "value": "7일 창에 유효 TCE가 없으면 공백으로 표시합니다. 최신 공개 발표일 이후로 값을 연장하지 않습니다. 선령 분류는 TI 원본 카테고리를 따릅니다."},
        ],
    }
    docs = [
        {**common, "id": "ti_vlcc_tce", "name": "TI VLCC 성약 TCE · 7일 중앙값", "unit": "USD/day",
         "series": categories, "sample_counts": category_counts,
         "default_series": [OVERALL, CATEGORY_LABELS["Modern (Scrubber)"], CATEGORY_LABELS["Modern (VLSFO)"]],
         "description": "확정된 VLCC 성약의 하루 환산 수익을 추적합니다. 전체·선령·스크러버별로 비교하며, 표본 수는 차트에 마우스를 올려 확인할 수 있습니다."},
        {**common, "id": "ti_vlcc_routes", "name": "TI VLCC 주요 항로 TCE · 7일 중앙값", "unit": "USD/day",
         "series": routes, "sample_counts": route_counts, "default_series": ["AG → China", "USG → China", "Brazil → China"],
         "description": "AG=중동 걸프, WAF=서아프리카, USG=미국 걸프. 동일 항로 안에도 선령·선박 사양·항차 조건 차이가 있으며 Baltic TD 항로 평가치와 직접 같지 않습니다."},
        {**common, "id": "ti_vlcc_count", "name": "TI VLCC 공개 성약 건수 · 최근 7일", "unit": "건",
         "series": counts, "default_series": list(counts), "zero_baseline": True,
         "description": "7일 중앙값을 뒷받침하는 표본 규모입니다. 확정 성약 중 TCE가 비공개인 건도 있어 두 건수를 함께 표시합니다. 전체 시장의 계약 건수는 아닙니다."},
        {**common, "id": "ti_vlcc_fixtures", "name": "TI VLCC 성약 내역", "unit": "USD/day", "series": {},
         "fixtures": fixtures, "description": "기본은 확정 계약만 표시합니다. 조건부·실패 계약은 상태 필터로 확인할 수 있습니다. TCE 미공개는 —로 표시하며, 발표 시각은 TI 원문 표기입니다."},
    ]
    return docs


def run():
    response = requests.get(API_URL, headers=UA, timeout=45)
    response.raise_for_status()
    incoming = parse_payload(response.json())
    out = DATA_DIR / "shipping"
    archive_path = out / "ti_vlcc_fixtures.json"
    previous = json.loads(archive_path.read_text(encoding="utf-8")).get("fixtures", []) if archive_path.exists() else []
    fixtures = merge_fixtures(previous, incoming)
    fetched = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9))).date().isoformat()
    docs = build_documents(fixtures, fetched, max(row["reported_date"] for row in incoming))
    # 전체 응답의 검증·집계가 완료된 뒤에만 기록한다.
    out.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        path = out / f"{doc['id']}.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        temp.replace(path)
        print(f"  saved {path.name}")
    print(f"  TI: response {len(incoming)}, archived {len(fixtures)}, latest {docs[0]['updated']}")


if __name__ == "__main__":
    run()

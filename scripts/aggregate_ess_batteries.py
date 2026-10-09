"""Publish reviewed issuer metrics without inventing cell/system splits or dates."""
import copy
import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"cell": "셀 제조", "battery": "배터리 제품 · 셀/모듈 미분리",
          "system": "시스템 · 모듈/컨테이너 조립", "finance": "재무 · 공시 범위 합산"}
STATUSES = {"actual": "공시 실적 / 가동 확인", "design": "프로젝트 설계·계획",
            "target": "향후 목표", "contracted": "공급 계약 / 수주", "framework": "전략적·기본 협약"}
MEASURES = {"capacity", "production", "production_milestone", "sales", "shipments", "contract",
            "project_delivery", "framework", "revenue", "gross_profit", "gross_margin",
            "revenue_mix", "order_intake", "backlog", "revenue_growth"}
FINANCIAL = {"revenue", "gross_profit", "gross_margin", "revenue_mix", "revenue_growth"}


def build(source):
    doc = copy.deepcopy(source)
    reviewed = dt.date.fromisoformat(doc["reviewed"])
    assert doc["manual"] is True
    sources = doc["sources"]
    for ref in sources.values():
        assert ref["url"].startswith("https://") and ref["label"]
        assert dt.date.fromisoformat(ref.get("published") or ref["accessed"]) <= reviewed
    company_ids = [c["id"] for c in doc["companies"]]
    assert len(company_ids) == len(set(company_ids))
    for c in doc["companies"]:
        assert c["sources"] and set(c["sources"]) <= sources.keys()
        assert all(c[k] for k in ("role", "capacity_note", "financial_note", "gaps"))
    ids, cards, excluded = set(), [], []
    for item in doc["metrics"]:
        assert item["id"] not in ids
        ids.add(item["id"])
        assert item["company"] in company_ids
        assert item["stage"] in STAGES and item["status"] in STATUSES
        assert item["measure"] in MEASURES
        assert item["scope"] and item["chemistry"]
        assert (item["stage"] == "finance") == (item["measure"] in FINANCIAL)
        if item["measure"] == "capacity":
            assert item["unit"] == "GWh/년"
            assert item["stage"] in {"cell", "battery", "system"}
        if item["measure"] == "production":
            assert item["stage"] == "cell" and item["unit"] == "백만 셀"
        if item["status"] != "actual":
            assert item["target_period"]
        if item["measure"] in {"contract", "order_intake", "backlog"}:
            assert item["status"] == "contracted"
        if item["measure"] == "framework":
            assert item["status"] == "framework"
        views, view_points = {}, {}
        all_points = []
        for key, raw in item["views"].items():
            assert raw["frequency"] in {"yearly", "semiannual", "irregular"}
            raw_series = raw.get("series", {item["name"].split(" · ", 1)[-1]: raw["points"]})
            series, refs, qualifiers, checked_points = {}, {}, {}, []
            for name, points in raw_series.items():
                dates = [p["date"] for p in points]
                assert dates and dates == sorted(set(dates)), (item["id"], dates)
                for p in points:
                    day = dt.date.fromisoformat(p["date"])
                    assert day <= reviewed
                    assert p["source"] in sources
                    assert day <= dt.date.fromisoformat(sources[p["source"]]["published"])
                    if raw["frequency"] == "yearly": assert p["date"].endswith("-12-31")
                    if raw["frequency"] == "semiannual": assert p["date"].endswith(("-06-30", "-12-31"))
                    assert isinstance(p["value"], (float, int)) and not isinstance(p["value"], bool)
                    assert math.isfinite(p["value"]) and p["value"] > 0
                    assert p.get("qualifier") in {None, "lower_bound"}
                    ref = copy.deepcopy(sources[p["source"]])
                    if p.get("supporting_sources"):
                        assert set(p["supporting_sources"]) <= sources.keys()
                        ref["supporting_sources"] = [copy.deepcopy(sources[key]) for key in [p["source"], *p["supporting_sources"]]]
                    if p.get("pdf_page"):
                        assert isinstance(p["pdf_page"], int) and p["pdf_page"] > 0
                        ref["pdf_page"] = p["pdf_page"]
                    assert p["date"] not in refs or refs[p["date"]] == ref
                    refs[p["date"]] = ref
                    if p.get("qualifier"): qualifiers[p["date"]] = p["qualifier"]
                series[name] = [[p["date"], p["value"]] for p in points]
                all_points.extend(points)
                checked_points.extend(points)
            one_date = len({p[0] for s in series.values() for p in s}) == 1
            views[key] = dict(label=raw["label"], frequency=raw["frequency"], series=series,
                              unit=item["unit"], period_sources=refs, value_qualifiers=qualifiers,
                              year_labels=raw["frequency"] == "yearly",
                              chart_type="bar" if one_date else "line", zero_baseline=True)
            if item["measure"] == "revenue_mix":
                assert all(math.isclose(sum(dict(s).get(day, 0) for s in series.values()), 100, abs_tol=0.01)
                           for day in refs)
                views[key]["default_series"] = list(series)
            view_points[key] = checked_points
        if item.get("calculation"):
            assert item["calculation"] == "revenue_minus_cost"
            values = {p["date"]: p["value"] for p in all_points}
            assert set(values) == {r["date"] for r in item["reconciliation"]}
            for r in item["reconciliation"]:
                assert math.isclose(values[r["date"]], r["revenue"] - r["cost"], abs_tol=0.000001)
        # Validate the archive before excluding one-date views, including those on
        # cards whose other period view already has history.
        for key in list(views):
            if any(len(series) < 2 for series in views[key]["series"].values()):
                excluded.append({"id": item["id"], "name": item["name"], "view": key,
                                 "reason": "fewer_than_two_periods"})
                del views[key]
        if not views:
            continue
        all_points = [p for key in views for p in view_points[key]]
        default = max(views, key=lambda k: max(p[0] for s in views[k]["series"].values() for p in s))
        latest_ref = sources[max(all_points, key=lambda p: (p["date"], sources[p["source"]]["published"]))["source"]]
        details = [{"label": "생산 단계", "value": STAGES[item["stage"]]},
                   {"label": "실적·계획 구분", "value": STATUSES[item["status"]]},
                   {"label": "집계 범위", "value": item["scope"]},
                   {"label": "배터리 화학계열", "value": item["chemistry"]}]
        if item.get("target_period"):
            details.append({"label": "계획·계약 대상 기간", "value": item["target_period"]})
        if item["note"]: details.append({"label": "해석 기준", "value": item["note"]})
        details.append({"label": "자료 검토일", "value": doc["reviewed"]})
        card = {k: item[k] for k in ("id", "company", "stage", "measure", "status", "name", "unit", "scope", "chemistry", "note")}
        card.update(manual=True, company_kpi=True, change_mode="none", span_gaps=False,
                    updated=max(p["date"] for p in all_points), reviewed=doc["reviewed"],
                    source=latest_ref["label"], source_url=latest_ref["url"],
                    series_views=views, default_view=default, basis_details=details,
                    snapshot_history=True, history_note="연간과 상반기는 별도로 비교합니다. 결측 기간은 추정하지 않습니다.")
        cards.append(card)
    doc.pop("metrics")
    for row in doc.get("focus_history", []):
        assert row["company"] in doc["focus_companies"]
        assert row["kind"] in {"revenue", "capacity"}
        assert len(row["periods"]) == 5
        for year, point in row["periods"].items():
            assert year in {"2021", "2022", "2023", "2024", "2025"}
            assert point["source"] in sources and point["label"]
            if "value" in point:
                assert math.isfinite(point["value"]) and point["value"] > 0
                assert point["status"] == "actual"
            else:
                assert point["status"] == "unverified"
    for target in doc.get("focus_targets", []):
        assert target["status"] == "target" and target["source"] in sources
        assert target["company"] in doc["focus_companies"] and target["target_period"]
    doc.update(cards=cards, stages=STAGES, statuses=STATUSES, updated=doc["reviewed"],
               excluded_views=excluded, minimum_history_periods=2)
    return doc


if __name__ == "__main__":
    source = json.loads((ROOT / "manual/ess_batteries.json").read_text(encoding="utf-8"))
    doc = build(source)
    (ROOT / "data/ess/ess_batteries.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(doc['cards'])} ESS battery metrics for {len(doc['companies'])} issuers; reviewed {doc['reviewed']}")

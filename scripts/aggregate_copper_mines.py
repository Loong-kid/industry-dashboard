"""Validate and publish the source-reviewed copper mine register.

No network calls or automatic review-date changes. Missing facts remain null;
annual production is never multiplied by mine age to invent lifetime production.
"""
import copy
import json
import math
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
LB_TO_T = 0.00045359237


def build(source):
    doc = copy.deepcopy(source)
    reviewed = date.fromisoformat(doc["reviewed"])
    assert doc["manual"] is True
    sources = doc["sources"]
    for src in sources.values():
        assert src["url"].startswith("https://")
        assert src["title"]
        assert date.fromisoformat(src["accessed"]) <= reviewed

    def check_refs(refs):
        assert refs and set(refs) <= sources.keys(), refs

    def check_fact(fact):
        if fact is None:
            return
        assert isinstance(fact["value"], (int, float)) and not isinstance(fact["value"], bool)
        assert math.isfinite(fact["value"]) and fact["value"] >= 0
        assert fact["unit"] in {"t Cu", "kt Cu", "Mt Cu", "million lb Cu", "billion lb Cu", "Mt ore", "kt ore"}
        assert fact["basis"] and fact["date"] and fact["locator"]
        assert date.fromisoformat(fact["date"]) <= reviewed
        check_refs(fact["sources"])
        factors = {"t Cu": 1, "kt Cu": 1000, "Mt Cu": 1e6,
                   "million lb Cu": 1e6 * LB_TO_T, "billion lb Cu": 1e9 * LB_TO_T}
        fact["cu_tonnes"] = round(fact["value"] * factors[fact["unit"]], 4) if fact["unit"] in factors else None

    ids = set()
    for row in doc["rows"]:
        assert row["id"] not in ids
        ids.add(row["id"])
        assert row["name"] and row["country"] and row["region"] and row["operator"]
        assert row["status"] in {"operating", "ramp_up", "suspended", "closed", "construction", "development", "unconfirmed"}
        check_refs(row["sources"])
        check_refs(row["ownership_sources"])
        check_refs(row["status_sources"])
        assert date.fromisoformat(row["ownership_date"]) <= reviewed
        assert date.fromisoformat(row["status_date"]) <= reviewed
        assert row.get("ownership_date_kind") in {"reported", "checked"}
        assert row.get("status_date_kind") in {"reported", "checked"}
        assert row["owners"] and row["ownership_basis"]
        known = [o["pct"] for o in row["owners"] if o["pct"] is not None]
        assert all(0 < x <= 100 for x in known)
        assert sum(known) <= 100.05, row["id"]
        if all(o["pct"] is not None for o in row["owners"]):
            assert abs(sum(known) - 100) < 0.05, row["id"]
        years = []
        for fact in row["production"]:
            check_fact(fact)
            assert fact["unit"] not in {"Mt ore", "kt ore"}
            assert isinstance(fact["year"], int) and fact["year"] <= reviewed.year
            assert fact["period"] in {"calendar", "fiscal"}
            years.append(fact["year"])
        assert len(years) == len(set(years)), row["id"]
        row["production"].sort(key=lambda f: f["year"])
        for field in ("reserves", "resources", "ore_mined", "cumulative"):
            check_fact(row.get(field))
        if row.get("ore_mined"):
            assert row["ore_mined"]["unit"] in {"Mt ore", "kt ore"}
        if row.get("cumulative"):
            assert row["cumulative"]["cu_tonnes"] is not None
        if row.get("reserves") or row.get("resources"):
            assert not (row.get("reserves") is row.get("resources"))
        if row.get("reserves"):
            assert row["reserves"]["classification"] in {"P&P", "reported reserve"}
        if row.get("resources"):
            assert "classification" in row["resources"]
        if row.get("start_year") is not None:
            assert 1800 <= row["start_year"] <= reviewed.year
            check_refs(row["history_sources"])
        if row.get("end_year") is not None:
            assert row["start_year"] is None or row["end_year"] >= row["start_year"]
            assert row["end_year"] <= reviewed.year
        row["period_total"] = None
        # Only sum contiguous years with identical physical, fiscal and equity bases.
        facts = row["production"]
        if len(facts) > 1 and years and max(years) - min(years) + 1 == len(years):
            if len({(f["basis"], f["period"]) for f in facts}) == 1:
                row["period_total"] = {
                    "cu_tonnes": round(sum(f["cu_tonnes"] for f in facts), 4),
                    "from_year": min(years), "to_year": max(years),
                    "basis": facts[0]["basis"], "period": facts[0]["period"],
                    "lifetime": row.get("history_complete") is True and row.get("start_year") == min(years),
                    "sources": sorted({s for f in facts for s in f["sources"]}),
                }
        if row.get("history_complete"):
            assert row["period_total"] and row["period_total"]["lifetime"]
    doc["updated"] = doc["reviewed"]
    doc["coverage"] = {
        "mines": len(doc["rows"]), "countries": len({r["country"] for r in doc["rows"]}),
        "with_production": sum(bool(r["production"]) for r in doc["rows"]),
        "with_reserves": sum(r.get("reserves") is not None for r in doc["rows"]),
        "with_resources": sum(r.get("resources") is not None for r in doc["rows"]),
        "with_lifetime": sum(bool(r.get("cumulative") or (r["period_total"] and r["period_total"]["lifetime"])) for r in doc["rows"]),
        "with_complete_ownership": sum(all(o["pct"] is not None for o in r["owners"]) for r in doc["rows"]),
        "with_start_year": sum(r.get("start_year") is not None for r in doc["rows"]),
        "with_ore_mined": sum(r.get("ore_mined") is not None for r in doc["rows"]),
        "complete_global_census": False,
    }
    return doc


def main():
    doc = build(json.loads((ROOT / "manual/copper_mines.json").read_text(encoding="utf-8")))
    out = ROOT / "data/commodities/comm_copper_mines.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc["coverage"], ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Validate and publish manufacturer product specifications; never estimate missing AC ratings."""
import copy
import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(source):
    doc = copy.deepcopy(source)
    dt.date.fromisoformat(doc["reviewed"])
    assert doc["manual"] is True
    for item in doc["sources"].values():
        assert item["url"].startswith("https://")
        assert item["author"] in {"Tesla", "Fluence"}
        assert item["revision"] and item["pages"] > 0
    for product in doc["products"].values():
        assert product["company"] in {"tesla", "fluence"}
        assert product["rating_status"] in {"standard", "design_estimate"}
        assert product["capacity_scope"] in {"battery_unit", "battery_enclosure", "pack_option"}
        assert product["capacity_basis"] and product["architecture"] and product["rte_basis"]
        for ref in product["references"]:
            assert ref["source"] in doc["sources"]
            assert 1 <= ref["page"] <= doc["sources"][ref["source"]]["pages"]
            assert ref["fields"]
    ids = set()
    for row in doc["rows"]:
        assert row["id"] not in ids
        ids.add(row["id"])
        assert row["product"] in doc["products"]
        assert row["duration_basis"] and row["power_basis"] and row["dimensions"] and row["mass_basis"]
        for field in ("energy_kwh", "ac_power_kw", "ac_current_a", "rte_percent"):
            fact = row[field]
            if fact is None:
                continue
            assert fact["qualifier"] in {"exact", "range", "approx", "up_to", "greater_than"}
            lo, hi = fact["min"], fact["max"]
            assert all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in (lo, hi))
            assert lo <= hi
            if fact["qualifier"] != "range":
                assert lo == hi
            if field == "rte_percent":
                assert hi <= 100
        assert row["energy_kwh"] is not None
        assert all(isinstance(h, int) and h > 0 for h in row["duration_hours"])
        # CP-rate and maximum current are not manufacturer-published active power.
        if row["product"] in {"gridstack_pro", "smartstack"}:
            assert row["ac_power_kw"] is None
        if row["product"] == "smartstack":
            assert row["rte_percent"] is None
        if row["id"] == "smartstack_10":
            assert row["duration_hours"] == [4, 6, 8]
    doc["updated"] = doc["reviewed"]
    return doc


if __name__ == "__main__":
    source = json.loads((ROOT / "manual/ess_products.json").read_text(encoding="utf-8"))
    doc = build(source)
    (ROOT / "data/ess/ess_products.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(doc['rows'])} ESS product configurations; reviewed {doc['reviewed']}")

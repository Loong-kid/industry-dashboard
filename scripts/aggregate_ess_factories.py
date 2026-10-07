"""Publish the manually reviewed ESS facility register without refreshing its dates."""
import copy
import datetime as dt
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQFT_TO_M2 = 0.09290304


def build(source):
    doc = copy.deepcopy(source)
    dt.date.fromisoformat(doc["reviewed"])
    assert doc["manual"] is True
    sources = doc["sources"]
    for item in sources.values():
        assert item["url"].startswith("https://")
        assert re.fullmatch(r"\d{4}(-\d{2})?(-\d{2})?", item["published"])
    ids = set()
    for row in doc["rows"]:
        assert row["id"] not in ids
        ids.add(row["id"])
        assert row["company"] in {"tesla", "sungrow", "fluence"}
        assert row["operation"] in {"direct", "contract"}
        assert row["stage"] in {"system", "component"}
        assert row["status"] in {"operating", "planned", "unconfirmed"}
        for field in ("ownership", "status"):
            assert row[field + "_sources"]
            assert set(row[field + "_sources"]) <= sources.keys()
            assert row[field + "_date"] <= doc["reviewed"]
        assert set(row.get("extra_sources", [])) <= sources.keys()
        for field in ("floor_area", "other_area", "installed_capacity", "design_capacity"):
            fact = row[field]
            if fact is None:
                continue
            assert isinstance(fact["value"], (int, float)) and not isinstance(fact["value"], bool)
            assert math.isfinite(fact["value"]) and fact["value"] > 0
            assert fact["date"] <= doc["reviewed"]
            assert fact["basis"] and fact["sources"]
            assert set(fact["sources"]) <= sources.keys()
            if field.endswith("area"):
                assert fact["unit"] in {"m2", "ft2"}
                fact["m2"] = round(fact["value"] * (SQFT_TO_M2 if fact["unit"] == "ft2" else 1), 2)
            else:
                assert fact["qualifier"] in {"exact", "greater_than", "approx", "up_to"}
        # An unconfirmed or future project must not appear to have installed capacity.
        if row["status"] != "operating":
            assert row["installed_capacity"] is None
    doc["updated"] = doc["reviewed"]
    return doc


if __name__ == "__main__":
    source = json.loads((ROOT / "manual/ess_factories.json").read_text(encoding="utf-8"))
    doc = build(source)
    out = ROOT / "data/ess/ess_factories.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(doc['rows'])} reviewed facility/project records; reviewed {doc['reviewed']}")

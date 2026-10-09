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
    cell_register = doc["id"] == "ess_cell_factories"
    companies = {"catl", "lg", "sdi", "sk"} if cell_register else {"tesla", "sungrow", "fluence"}
    for item in sources.values():
        assert item["url"].startswith("https://")
        assert re.fullmatch(r"\d{4}(-\d{2})?(-\d{2})?", item["published"])
        if cell_register:
            assert item["kind"] in {"primary", "analyst", "media"}
    ids = set()
    for row in doc["rows"]:
        assert row["id"] not in ids
        ids.add(row["id"])
        assert row["company"] in companies
        assert row["operation"] in {"direct", "contract"}
        assert row["stage"] in ({"cell"} if cell_register else {"system", "component"})
        if cell_register:
            assert row["chemistry"] in {"lfp", "nca_ncm", "sodium", "mixed"}
        assert row["status"] in {"operating", "planned", "unconfirmed"}
        for field in ("ownership", "status"):
            assert row[field + "_sources"]
            assert set(row[field + "_sources"]) <= sources.keys()
            assert row[field + "_date"] <= doc["reviewed"]
        assert set(row.get("extra_sources", [])) <= sources.keys()
        facts = [(field, row[field]) for field in ("floor_area", "other_area", "installed_capacity", "design_capacity")]
        facts += [("reference_capacity", fact) for fact in row.get("reference_capacities", [])]
        for field, fact in facts:
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
                if cell_register:
                    assert fact["unit"] == "GWh/year"
                    assert fact["scope"] in {"ess", "mixed", "ev", "unsplit"}
                    assert fact["evidence"] in {"primary", "analyst", "media"}
                    if field in {"installed_capacity", "design_capacity"}:
                        assert fact["scope"] == "ess" and fact["evidence"] == "primary"
                    assert all(sources[key]["kind"] == fact["evidence"] for key in fact["sources"])
        # An unconfirmed or future project must not appear to have installed capacity.
        if row["status"] != "operating":
            assert row["installed_capacity"] is None
    for item in doc.get("regional_targets", []):
        assert item["scope"] == "region", "Regional totals must not be assigned to an individual factory"
        assert item["sources"] and set(item["sources"]) <= sources.keys()
        assert item["date"] <= doc["reviewed"]
    for item in doc.get("claim_checks", []):
        assert item["sources"] and set(item["sources"]) <= sources.keys()
    doc["updated"] = doc["reviewed"]
    return doc


if __name__ == "__main__":
    for name in ("ess_factories", "ess_cell_factories"):
        source = json.loads((ROOT / f"manual/{name}.json").read_text(encoding="utf-8"))
        doc = build(source)
        out = ROOT / f"data/ess/{name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Published {name}: {len(doc['rows'])} reviewed facility/project records; reviewed {doc['reviewed']}")

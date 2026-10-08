import copy
import json
import unittest
from pathlib import Path
from aggregate_ess_batteries import build

ROOT = Path(__file__).resolve().parents[1]


class ReviewedBatteryMetricsTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "manual/ess_batteries.json").read_text(encoding="utf-8"))

    def test_scope_and_source_regressions(self):
        doc = build(self.raw)
        self.assertEqual(len(doc["companies"]), 10)
        self.assertEqual(len(doc["cards"]), 30)
        cards = {c["id"].removeprefix("ess_battery_"): c for c in doc["cards"]}
        # These are not interchangeable cell capacity, system capacity or revenue.
        self.assertEqual(cards["hithium_system_capa"]["stage"], "system")
        self.assertEqual(cards["lg_cell_capa"]["status"], "target")
        self.assertEqual(cards["eve_cell_capa"]["status"], "design")
        self.assertEqual(cards["sdi_sales_target"]["measure"], "sales")
        self.assertEqual(cards["cornex_framework"]["status"], "framework")
        self.assertEqual(cards["sk_contract"]["series_views"]["snapshot"]["series"]["NeoVolta LFP 셀 공급 계약"], [["2026-09-24", 9]])
        for key in ("catl_sales", "hithium_battery_sales", "rept_shipments", "cornex_shipments"):
            self.assertEqual(cards[key]["stage"], "battery")
        # 2026H1 13.1% includes EV, so it cannot extend the ESS margin series.
        self.assertNotIn("half", cards["rept_margin"]["series_views"])
        self.assertNotIn("half", cards["rept_gross"]["series_views"])
        self.assertIn("others", cards["calb_revenue"]["scope"])
        self.assertEqual(cards["eve_revenue"]["series_views"]["half"]["period_sources"]["2025-06-30"]["pdf_page"], 20)
        for c in doc["cards"]:
            self.assertTrue(c["basis_details"])
            for v in c["series_views"].values():
                dates = {p[0] for s in v["series"].values() for p in s}
                self.assertEqual(dates, set(v["period_sources"]))
                self.assertTrue(all(p[1] is not None for s in v["series"].values() for p in s))

    def test_rejects_capacity_as_output_or_finance(self):
        item = next(m for m in self.raw["metrics"] if m["measure"] == "capacity")
        item["unit"] = "GWh"
        with self.assertRaises(AssertionError): build(self.raw)

    def test_rejects_unlabeled_target(self):
        item = next(m for m in self.raw["metrics"] if m["status"] == "target")
        item.pop("target_period")
        with self.assertRaises(KeyError): build(self.raw)

    def test_rejects_duplicate_dates_and_missing_values(self):
        for bad in ("duplicate", "missing", "unknown_source", "future"):
            raw = copy.deepcopy(self.raw)
            points = raw["metrics"][0]["views"]["annual"]["points"]
            if bad == "duplicate": points.append(copy.deepcopy(points[-1]))
            if bad == "missing": points[-1]["value"] = None
            if bad == "unknown_source": points[-1]["source"] = "missing"
            if bad == "future": points[-1]["date"] = "2027-12-31"
            with self.subTest(bad=bad), self.assertRaises(AssertionError): build(raw)

    def test_rejects_bad_gross_profit_calculation(self):
        item = next(m for m in self.raw["metrics"] if m.get("calculation"))
        item["reconciliation"][0]["cost"] += 100
        with self.assertRaises(AssertionError): build(self.raw)

    def test_review_date_does_not_follow_ci_run(self):
        self.assertEqual(build(self.raw)["updated"], self.raw["reviewed"])
        published = json.loads((ROOT / "data/ess/ess_batteries.json").read_text(encoding="utf-8"))
        self.assertEqual(published, build(self.raw))


if __name__ == "__main__": unittest.main()

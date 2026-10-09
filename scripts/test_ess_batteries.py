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
        self.assertEqual(len(doc["cards"]), 15)
        cards = {c["id"].removeprefix("ess_battery_"): c for c in doc["cards"]}
        archive = {c["id"].removeprefix("ess_battery_"): c for c in self.raw["metrics"]}
        # These are not interchangeable cell capacity, system capacity or revenue.
        self.assertEqual(archive["hithium_system_capa"]["stage"], "system")
        self.assertEqual(archive["lg_cell_capa"]["status"], "target")
        self.assertEqual(archive["eve_cell_capa"]["status"], "design")
        self.assertEqual(archive["sdi_sales_target"]["measure"], "sales")
        self.assertEqual(archive["cornex_framework"]["status"], "framework")
        self.assertEqual(archive["sk_contract"]["views"]["snapshot"]["points"][0]["value"], 9)
        for key in ("catl_sales", "hithium_battery_sales", "rept_shipments", "cornex_shipments", "eve_shipments"):
            self.assertEqual(archive[key]["stage"], "battery")
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
                self.assertGreaterEqual(len(dates), 2)
                self.assertTrue(all(len(s) >= 2 for s in v["series"].values()))

    def test_history_and_single_period_exclusion(self):
        doc = build(self.raw)
        cards = {c["id"].removeprefix("ess_battery_"): c for c in doc["cards"]}
        def values(key, view): return next(iter(cards[key]["series_views"][view]["series"].values()))
        self.assertEqual(values("catl_sales", "annual"), [["2022-12-31",47],["2023-12-31",69],["2024-12-31",93],["2025-12-31",121]])
        self.assertEqual(values("eve_shipments", "half"), [["2024-06-30",20.95],["2025-06-30",28.71],["2026-06-30",44.46]])
        self.assertEqual(values("rept_shipments", "half"), [["2025-06-30",18.87],["2026-06-30",27.2]])
        for key in ("eve_shipments", "eve_gross", "eve_margin"):
            self.assertNotIn("annual", cards[key]["series_views"])
            self.assertEqual(cards[key]["default_view"], "half")
        self.assertNotIn("hithium_mix", cards)  # Three categories on one date are not history.
        self.assertNotIn("lg_cell_capa", cards)
        self.assertNotIn("sk_contract", cards)
        self.assertEqual(len({x["id"] for x in doc["excluded_views"]} - {c["id"] for c in doc["cards"]}), 18)

    def test_single_period_data_still_validated(self):
        item = next(m for m in self.raw["metrics"] if m["id"] == "ess_battery_sk_contract")
        item["views"]["snapshot"]["points"][0]["source"] = "missing"
        with self.assertRaises(AssertionError): build(self.raw)

    def test_focused_history_preserves_units_and_disclosure_gaps(self):
        doc = build(self.raw)
        cards = {c["id"].removeprefix("ess_battery_"): c for c in doc["cards"]}
        def points(key): return next(iter(cards[key]["series_views"]["annual"]["series"].values()))
        self.assertEqual(points("lg_ess_capa"), [["2024-12-31",12],["2025-12-31",36]])
        self.assertEqual(points("sdi_ess_production"), [["2021-12-31",20.3],["2022-12-31",20.8],["2023-12-31",20.6],["2024-12-31",22.2]])
        self.assertEqual(cards["sdi_ess_production"]["unit"], "백만 셀")
        self.assertEqual(points("catl_revenue")[0], ["2021-12-31",13623.8347])
        self.assertEqual([p[1] for p in points("catl_margin")[:3]], [28.52,17.01,23.79])
        self.assertNotIn("2026-12-31", dict(points("lg_ess_capa")))
        self.assertEqual(doc["focus_companies"], ["catl","lg","sdi","sk"])
        for row in doc["focus_history"]:
            if row["kind"] == "revenue" and row["company"] != "catl":
                self.assertTrue(all("value" not in p for p in row["periods"].values()))
        raw = copy.deepcopy(self.raw)
        next(m for m in raw["metrics"] if m["measure"] == "production")["unit"] = "GWh"
        with self.assertRaises(AssertionError): build(raw)

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

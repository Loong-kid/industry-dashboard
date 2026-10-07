"""Financial period, source reconciliation and product-scope regression checks."""
import copy
import json
import unittest

from fetch_mask_patterning import CACHE, TEKSCEND, TEKSCEND_FINANCIALS, PRODUCTS, build_documents, photronics_quarters


class MaskPatterningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = json.loads(CACHE.read_text(encoding="utf8"))
        cls.tek = json.loads(TEKSCEND.read_text(encoding="utf8"))
        cls.financials = json.loads(TEKSCEND_FINANCIALS.read_text(encoding="utf8"))
        cls.docs = build_documents(cls.cache, cls.tek)

    def test_latest_reported_revenue_and_history(self):
        rows = photronics_quarters(self.cache)
        self.assertGreaterEqual(len(rows), 23)
        self.assertEqual((rows[0]["fiscal_year"], rows[0]["quarter"]), (2021, 1))
        anchor = next(r for r in rows if r["period_end"] == "2026-08-02")
        self.assertEqual(anchor["values"], dict(zip(PRODUCTS, [68506, 86165, 154671, 52311, 9065, 61376])))

    def test_q4_is_annual_minus_nine_months_with_both_sources(self):
        rows = photronics_quarters(self.cache)
        for year in range(2021, 2026):
            annual = next(f for f in self.cache["filings"] if f["fiscal_year"] == year and f["quarter"] == 4)
            q3 = next(f for f in self.cache["filings"] if f["fiscal_year"] == year and f["quarter"] == 3)
            q4 = next(r for r in rows if r["fiscal_year"] == year and r["quarter"] == 4)
            for key in PRODUCTS:
                self.assertEqual(q4["values"][key], annual["table"][key][0] - q3["table"][key][2])
            self.assertEqual(len(q4["sources"]), 2)
            self.assertTrue(q4["derived"])

    def test_fiscal_comparisons_survive_changing_end_dates(self):
        doc = self.docs["photronics_ic_revenue"]
        self.assertEqual(doc["period_labels"]["2026-08-02"], "FY2026 Q3")
        self.assertEqual(doc["comparison_dates"]["2026-08-02"], {
            "year_ago": "2025-08-03", "quarter_ago": "2026-05-03"})
        self.assertNotIn("quarter_labels", doc)
        cache = copy.deepcopy(self.cache)
        cache["filings"] = [f for f in cache["filings"] if not (f["fiscal_year"] == 2026 and f["quarter"] == 2)]
        sparse = build_documents(cache, self.tek)["photronics_ic_revenue"]
        self.assertIsNone(sparse["comparison_dates"]["2026-08-02"]["quarter_ago"])

    def test_preserves_disclosed_category_discrepancy(self):
        doc = self.docs["photronics_ic_revenue"]
        self.assertEqual(doc["reconciliation_differences_thousand_usd"], {"2022": {"ic_high": -389, "ic_main": 390}})
        self.assertTrue(any("0.39" in x["value"] for x in doc["basis_details"]))

    def test_rejects_material_total_mismatch(self):
        cache = copy.deepcopy(self.cache)
        q1 = next(f for f in cache["filings"] if f["fiscal_year"] == 2021 and f["quarter"] == 1)
        q1["table"]["ic_high"][0] += 1000
        q1["table"]["ic_total"][0] += 1000
        with self.assertRaisesRegex(ValueError, "quarter sum differs"):
            build_documents(cache, self.tek)

    def test_tekscend_calendar_mapping_and_product_scope(self):
        node = self.docs["tekscend_node_mix"]
        app = self.docs["tekscend_application_mix"]
        self.assertGreaterEqual(len(node["point_sources"]), 9)
        self.assertGreaterEqual(node["updated"], "2026-06-30")
        self.assertEqual([dict(s)["2026-06-30"] for s in node["series"].values()], [35, 35, 30])
        self.assertEqual([dict(s)["2026-06-30"] for s in app["series"].values()], [89, 11])
        self.assertIn("EUV 단독", node["description"])
        self.assertIn("근사 추정치", node["note"])
        self.assertEqual(node["point_sources"]["2024-06-30"]["pdf_page"], 8)

    def test_rejects_invalid_mix(self):
        tek = copy.deepcopy(self.tek)
        tek["quarters"][-1]["node"] = [35, 35, 35]
        with self.assertRaisesRegex(ValueError, "sum to 100"):
            build_documents(self.cache, tek)

    def test_tekscend_disclosed_financials_and_unit(self):
        revenue = self.docs["tekscend_revenue"]
        profit = self.docs["tekscend_operating_profit"]
        self.assertEqual(dict(revenue["series"]["매출"])["2026-06-30"], 345.18)
        self.assertEqual(dict(profit["series"]["영업이익"])["2026-06-30"], 73.6)
        self.assertEqual(revenue["unit"], "억 엔")
        self.assertEqual(revenue["point_sources"]["2024-06-30"]["pdf_page"], 26)
        self.assertIn("연결 실적", revenue["description"])
        self.assertNotIn("point_annotations", revenue)

    def test_tekscend_approximate_amounts_keep_reported_ratios(self):
        node = self.docs["tekscend_node_mix"]
        app = self.docs["tekscend_application_mix"]
        self.assertEqual(node["default_view"], "amount")
        amount = node["series_views"]["amount"]
        ratio = node["series_views"]["ratio"]
        self.assertEqual([dict(s)["2026-06-30"] for s in amount["series"].values()], [120.81, 120.81, 103.55])
        self.assertEqual([dict(s)["2026-06-30"] for s in app["series_views"]["amount"]["series"].values()], [307.21, 37.97])
        self.assertEqual(ratio["series"], node["series"])
        self.assertEqual(ratio["unit"], "%")
        self.assertFalse(ratio["quarterly_revenue_summary"])
        self.assertIn("공시한", amount["description"])
        self.assertIn("대용", amount["description"])
        self.assertEqual(len(amount["point_sources"]["2026-06-30"]["supporting_sources"]), 2)
        self.assertTrue(amount["point_annotations"])

    def test_tekscend_missing_denominator_and_misaligned_period_rejected(self):
        missing = copy.deepcopy(self.financials)
        missing["quarters"] = missing["quarters"][:-1]
        with self.assertRaisesRegex(ValueError, "Missing same-quarter"):
            build_documents(self.cache, self.tek, missing)
        wrong = copy.deepcopy(self.financials)
        wrong["quarters"][-1]["fiscal_period"] = "FY2026 Q2"
        with self.assertRaisesRegex(ValueError, "fiscal mapping"):
            build_documents(self.cache, self.tek, wrong)
        wrong = copy.deepcopy(self.financials)
        wrong["quarters"][0]["revenue"] += 100
        with self.assertRaisesRegex(ValueError, "quarter sum differs"):
            build_documents(self.cache, self.tek, wrong)


if __name__ == "__main__":
    unittest.main()

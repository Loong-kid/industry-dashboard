import copy
import json
import unittest

from aggregate_hoya_sheet import INPUT, build_docs


class HOYASheetTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(INPUT.read_text(encoding="utf8"))

    def test_calendar_alignment_units_and_product_scope(self):
        docs = build_docs(self.raw)
        expected = {
            "hoya_electronics_revenue_estimate": (449.5, 789.42),
            "hoya_lsi_revenue_estimate": (231.77, 413.581),
            "hoya_fpd_revenue_estimate": (69.85, 68.408),
            "hoya_hdd_revenue_estimate": (147.88, 307.431),
        }
        for id_, (first, last) in expected.items():
            doc = docs[id_]
            points = next(iter(doc["series"].values()))
            self.assertEqual(len(points), 12)
            self.assertEqual(points[0], ["2023-06-30", first])
            self.assertEqual(points[-1], ["2026-03-31", last])
            self.assertEqual(doc["revenue_status"], "estimate")
            self.assertEqual(set(doc["point_sources"]), {d for d, _ in points})
        self.assertIn("EUV와 DUV", docs["hoya_lsi_revenue_estimate"]["description"])
        self.assertIn("포토마스크", docs["hoya_fpd_revenue_estimate"]["description"])

    def test_reject_wrong_calendar_and_missing_values(self):
        for mutate in (
            lambda r: r["calendar_quarters"].__setitem__(0, "2026Q2"),
            lambda r: r["period_mapping"]["anchor"].__setitem__("official_revenue_billion_jpy", 255.7),
            lambda r: r["metrics"][0]["values"].pop(),
            lambda r: r["metrics"][1].__setitem__("status", "actual"),
        ):
            raw = copy.deepcopy(self.raw)
            mutate(raw)
            with self.assertRaises(ValueError):
                build_docs(raw)

    def test_catch_bad_nominal_growth_even_if_parent_sum_matches(self):
        raw = copy.deepcopy(self.raw)
        raw["metrics"][1]["values"][0] += 1000
        raw["metrics"][0]["values"][0] += 1000
        with self.assertRaisesRegex(ValueError, "nominal growth"):
            build_docs(raw)

    def test_reject_subtotal_error_and_approximate_zero(self):
        raw = copy.deepcopy(self.raw)
        raw["metrics"][0]["values"][0] += 1000
        with self.assertRaisesRegex(ValueError, "reconcile"):
            build_docs(raw)
        raw = copy.deepcopy(self.raw)
        raw["metrics"][1]["values"][0] = "~0"
        with self.assertRaises(ValueError):
            build_docs(raw)


if __name__ == "__main__":
    unittest.main()

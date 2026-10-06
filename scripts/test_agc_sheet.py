import copy
import json
import unittest

from aggregate_agc_sheet import INPUT, build_docs


class AGCSheetTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(INPUT.read_text(encoding="utf8"))

    def test_units_periods_and_estimate_scope(self):
        docs = build_docs(self.raw)
        expected = {
            "agc_sheet_materials_revenue": (230, 402, "reported_rounded"),
            "agc_euv_revenue_estimate": (29, 97, "estimate"),
            "agc_duv_substrate_revenue_estimate": (8.5, 12.1, "estimate"),
        }
        for id_, (first, last, status) in expected.items():
            doc = docs[id_]
            points = next(iter(doc["series"].values()))
            self.assertEqual(len(points), 22)
            self.assertEqual(points[0], ["2021-03-31", first])
            self.assertEqual(points[-1], ["2026-06-30", last])
            self.assertEqual(doc["revenue_status"], status)
            self.assertEqual(set(doc["point_sources"]), {p[0] for p in points})
            if status == "estimate":
                self.assertIn("추정", doc["name"])
        euv = next(iter(docs["agc_euv_revenue_estimate"]["series"].values()))
        self.assertEqual(sum(v for date, v in euv if date.startswith("2024")), 400)

    def test_reject_period_errors_and_missing_values(self):
        for mutate in (
            lambda raw: raw["quarters"].__setitem__(0, "27Q1"),
            lambda raw: raw["quarters"].__setitem__(0, raw["quarters"][1]),
            lambda raw: raw["metrics"][0]["values"].pop(),
        ):
            raw = copy.deepcopy(self.raw)
            mutate(raw)
            with self.assertRaises(ValueError):
                build_docs(raw)

    def test_reject_approximate_zero_and_bad_status(self):
        for value in ("~0", None, float("nan"), -1):
            raw = copy.deepcopy(self.raw)
            raw["metrics"][2]["values"][0] = value
            with self.assertRaises(ValueError):
                build_docs(raw)
        raw = copy.deepcopy(self.raw)
        raw["metrics"][1]["status"] = "actual"
        with self.assertRaises(ValueError):
            build_docs(raw)


if __name__ == "__main__":
    unittest.main()

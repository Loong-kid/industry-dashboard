import copy
import json
import unittest

from aggregate_ess_factories import ROOT, build


class FacilityDataTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / "manual/ess_factories.json").read_text(encoding="utf-8"))
        self.doc = build(self.source)
        self.rows = {r["id"]: r for r in self.doc["rows"]}

    def test_capacity_bases_and_missing_values(self):
        shanghai = self.rows["tesla_shanghai"]
        self.assertEqual(shanghai["installed_capacity"]["value"], 20)
        self.assertEqual(shanghai["design_capacity"]["value"], 40)
        self.assertEqual(self.rows["tesla_nevada"]["installed_capacity"]["qualifier"], "greater_than")
        texas = self.rows["tesla_texas"]
        self.assertIsNone(texas["installed_capacity"])
        self.assertEqual(texas["design_capacity"]["value"], 50)
        self.assertIsNone(self.rows["fluence_vietnam"]["installed_capacity"])
        self.assertEqual(self.rows["fluence_vietnam"]["design_capacity"]["value"], 35)
        self.assertTrue(all(r["operation"] == "contract" for r in self.doc["rows"] if r["company"] == "fluence"))

    def test_area_scope_conversion_and_review_date(self):
        lathrop = self.rows["tesla_lathrop"]
        self.assertIsNone(lathrop["floor_area"])
        self.assertEqual(lathrop["other_area"]["m2"], 40927.32)
        self.assertIsNone(self.rows["tesla_nevada"]["floor_area"])
        self.assertIsNone(self.rows["sungrow_hefei_20"]["floor_area"])
        self.assertEqual(self.rows["sungrow_hefei_20"]["other_area"]["m2"], 9402.9)
        self.assertEqual(self.rows["sungrow_hefei_25"]["floor_area"]["m2"], 430000)
        self.assertEqual(self.doc["reviewed"], self.doc["updated"])
        self.assertEqual(self.source, json.loads((ROOT / "manual/ess_factories.json").read_text(encoding="utf-8")))
        self.assertEqual(self.doc, json.loads((ROOT / "data/ess/ess_factories.json").read_text(encoding="utf-8")))

    def test_bad_units_dangling_sources_and_plans_rejected(self):
        for edit in (lambda r: r["other_area"].update(unit="mu"),
                     lambda r: r["installed_capacity"].update(sources=["missing"]),
                     lambda r: r.update(status="planned")):
            invalid = copy.deepcopy(self.source)
            edit(invalid["rows"][0])
            with self.assertRaises(AssertionError):
                build(invalid)


if __name__ == "__main__":
    unittest.main()

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


class CellFacilityDataTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / "manual/ess_cell_factories.json").read_text(encoding="utf-8"))
        self.doc = build(self.source)
        self.rows = {r["id"]: r for r in self.doc["rows"]}

    def test_ess_capacity_does_not_include_mixed_or_analyst_numbers(self):
        self.assertEqual(self.rows["lg_holland"]["installed_capacity"]["value"], 16.5)
        self.assertIsNone(self.rows["sdi_ulsan"]["installed_capacity"])
        self.assertIsNone(self.rows["sdi_kokomo"]["installed_capacity"])
        self.assertIsNone(self.rows["lg_lansing"]["installed_capacity"])
        self.assertEqual(self.rows["catl_jining"]["reference_capacities"][0]["scope"], "mixed")
        self.assertEqual(self.rows["sdi_ulsan"]["reference_capacities"][0]["evidence"], "analyst")
        for field, fact in [("scope", "mixed"), ("evidence", "analyst"), ("unit", "GWh")]:
            invalid = copy.deepcopy(self.source)
            next(r for r in invalid["rows"] if r["id"] == "lg_holland")["installed_capacity"][field] = fact
            with self.assertRaises(AssertionError):
                build(invalid)

    def test_plans_contracts_and_regional_totals_are_separate(self):
        self.assertEqual(self.rows["sk_seosan"]["design_capacity"]["value"], 3)
        self.assertEqual(self.rows["lg_ochang"]["design_capacity"]["value"], 1)
        self.assertIsNone(self.rows["sk_georgia"]["design_capacity"])
        self.assertTrue(all(r["installed_capacity"] is None for r in self.doc["rows"] if r["status"] != "operating"))
        self.assertEqual(len(self.doc["regional_targets"]), 3)
        self.assertTrue(all(r["scope"] == "region" for r in self.doc["regional_targets"]))
        self.assertEqual(len(self.doc["claim_checks"]), 4)
        self.assertEqual(self.rows["catl_fuding"]["chemistry"], "sodium")
        self.assertIsNone(self.rows["catl_fuding"]["installed_capacity"])
        self.assertIsNone(self.rows["catl_jining"]["design_capacity"])

    def test_data_and_catalog_preserve_four_company_focus(self):
        self.assertEqual(len(self.doc["rows"]), 15)
        self.assertEqual({r["company"] for r in self.doc["rows"]}, {"catl", "lg", "sdi", "sk"})
        self.assertEqual(self.doc, json.loads((ROOT / "data/ess/ess_cell_factories.json").read_text(encoding="utf-8")))
        cat = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
        sections = next(i for i in cat["industries"] if i["id"] == "ess")["sections"]
        physical = next(i for i, s in enumerate(sections) if s.get("battery_view") == "physical")
        cells = next(i for i, s in enumerate(sections) if "ess_cell_factories" in s.get("indicators", []))
        financial = next(i for i, s in enumerate(sections) if s.get("companies"))
        self.assertTrue(physical < cells < financial)


if __name__ == "__main__":
    unittest.main()

import copy
import json
import unittest

from aggregate_ess_products import ROOT, build


class ESSProductSpecTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / "manual/ess_products.json").read_text(encoding="utf-8"))
        self.doc = build(self.source)
        self.rows = {r["id"]: r for r in self.doc["rows"]}

    def test_standard_power_is_not_module_maximum_or_apparent_power(self):
        two = self.rows["megapack3_2h"]
        four = self.rows["megapack3_4h"]
        self.assertEqual(two["ac_power_kw"]["min"], 2186)
        self.assertEqual(two["energy_kwh"]["min"], 4372)
        self.assertEqual(four["energy_kwh"]["min"], 4826)
        self.assertEqual(four["rte_percent"]["min"], 92.5)
        self.assertEqual(self.rows["megapack3_8h"]["ac_power_kw"]["min"], 603)
        self.assertEqual(self.doc["products"]["megapack_3"]["capacity_scope"], "battery_unit")

    def test_missing_ratings_are_not_backfilled_or_derived(self):
        for row in self.doc["rows"]:
            if row["product"] != "megapack_3":
                self.assertIsNone(row["ac_power_kw"])
            if row["product"] == "smartstack":
                self.assertIsNone(row["rte_percent"])
        self.assertEqual(self.rows["smartstack_75"]["ac_current_a"]["qualifier"], "up_to")
        self.assertEqual(self.rows["smartstack_10"]["ac_current_a"]["min"], 2508)
        invalid = copy.deepcopy(self.source)
        invalid["rows"][-1]["ac_power_kw"] = {"min": 2997, "max": 2997, "qualifier": "exact"}
        with self.assertRaises(AssertionError):
            build(invalid)

    def test_variant_durations_bounds_and_component_scopes(self):
        self.assertEqual(self.rows["smartstack_10"]["duration_hours"], [4, 6, 8])
        self.assertEqual(self.rows["smartstack_75"]["energy_kwh"]["max"], 7524)
        self.assertEqual(self.rows["smartstack_10"]["energy_kwh"]["qualifier"], "approx")
        self.assertEqual(self.rows["gridstack_5000_3xx"]["energy_kwh"]["min"], 4872)
        self.assertEqual(self.rows["gridstack_5000_5xx"]["duration_hours"], [])
        self.assertEqual(self.rows["gridstack_5000_5xx"]["rte_percent"]["qualifier"], "greater_than")
        self.assertIn("냉각수 제외", self.rows["gridstack_5000_3xx"]["mass_basis"])
        self.assertIn("부품", self.rows["smartstack_10"]["mass_basis"])
        self.assertIn("선택", self.doc["products"]["smartstack"]["warranty"])
        self.assertEqual(self.doc["products"]["gridstack_pro"]["capacity_scope"], "battery_enclosure")

    def test_invalid_evidence_and_values_fail_validation(self):
        mutations = [lambda d: d["rows"][0]["energy_kwh"].update(min=float("nan")),
                     lambda d: d["rows"][0]["rte_percent"].update(min=101, max=101),
                     lambda d: d["products"]["megapack_3"]["references"][0].update(page=4),
                     lambda d: d["rows"][-1].update(duration_hours=[2, 4, 6, 8])]
        for mutation in mutations:
            invalid = copy.deepcopy(self.source)
            mutation(invalid)
            with self.assertRaises(AssertionError):
                build(invalid)

    def test_published_data_and_dashboard_position(self):
        self.assertEqual(self.doc, json.loads((ROOT / "data/ess/ess_products.json").read_text(encoding="utf-8")))
        self.assertEqual(self.doc["reviewed"], self.doc["updated"])
        self.assertEqual(len(self.doc["rows"]), 8)
        cat = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
        sections = next(i for i in cat["industries"] if i["id"] == "ess")["sections"]
        products = next(i for i, s in enumerate(sections) if s.get("table_kind") == "ess_products")
        systems = next(i for i, s in enumerate(sections) if "ess_factories" in s.get("indicators", []))
        cells = next(i for i, s in enumerate(sections) if s.get("battery_view") == "physical")
        self.assertTrue(1 < products < systems < cells)
        self.assertEqual(sections[0]["data_industry"], "power")


if __name__ == "__main__":
    unittest.main()

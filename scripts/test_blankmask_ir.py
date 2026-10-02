import copy
import json
import unittest
from aggregate_blankmask_ir import INPUT, build_docs, period_date, validate


class BlankmaskIRTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(INPUT.read_text(encoding="utf8"))

    def test_calendar_quarters_and_units(self):
        docs=build_docs(self.raw)
        for id_, latest in [("hoya_it_revenue",1010), ("agc_materials_revenue",402.05), ("shinetsu_materials_revenue",2792)]:
            doc=docs[id_]
            pts=next(iter(doc["series"].values()))
            self.assertEqual(len(pts),21)
            self.assertEqual(pts[0][0],"2021-06-30")
            self.assertEqual(pts[-1],["2026-06-30",latest])
            self.assertEqual(set(doc["point_sources"]),{p[0] for p in pts})
            self.assertIn("블랭크마스크 단독",doc["note"])
        growth=docs["hoya_blank_growth"]
        self.assertEqual(growth["series"]["명목 YoY"][-1],["2026-06-30",21])
        self.assertEqual(growth["series"]["환율 제외 YoY (CC)"][-1],["2026-06-30",18])
        self.assertEqual(growth["series"]["명목 YoY"][7],["2025-03-31",39])
        euv=docs["agc_euv_annual_revenue"]
        self.assertEqual(list(euv["series"].values()),[[["2024-12-31",400]]])
        self.assertEqual(euv["frequency"],"yearly")
        self.assertEqual(euv["point_sources"]["2024-12-31"]["pdf_page"],45)
        self.assertEqual(period_date("2026Q1"),"2026-03-31")

    def test_reject_forecasts_and_annual_to_quarter(self):
        raw=copy.deepcopy(self.raw)
        raw["records"][0]["status"]="forecast"
        with self.assertRaises(AssertionError):validate(raw)
        raw=copy.deepcopy(self.raw)
        r=next(r for r in raw["records"] if r["metric"]=="euv_blanks_annual_revenue")
        r["period"]="2024Q4"
        with self.assertRaises(AssertionError):validate(raw)

    def test_reject_missing_provenance_and_double_count(self):
        raw=copy.deepcopy(self.raw)
        raw["records"][0]["pdf_page"]=0
        with self.assertRaises(AssertionError):validate(raw)
        raw=copy.deepcopy(self.raw)
        raw["records"].append(copy.deepcopy(raw["records"][0]))
        with self.assertRaises(ValueError):validate(raw)

    def test_annual_reconciliation_catches_wrong_quarter_amount(self):
        raw=copy.deepcopy(self.raw)
        r=next(r for r in raw["records"] if r["company"]=="AGC" and r["period"]=="2025Q4")
        r["value"]*=2  # A cumulative number cannot pass as a standalone quarter.
        with self.assertRaises(AssertionError):validate(raw)


if __name__=="__main__":unittest.main()

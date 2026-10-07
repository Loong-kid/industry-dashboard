import copy
import json
import unittest
from unittest.mock import patch

import pymupdf
import fetch_mask_equipment as m


class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.cache = json.loads(m.CACHE.read_text(encoding="utf8"))
        self.manual = json.loads(m.MANUAL.read_text(encoding="utf8"))
        self.docs = m.build_documents(self.cache, self.manual)

    def test_reported_amounts_units_and_periods(self):
        self.assertEqual(len(self.docs), 14)
        self.assertGreaterEqual(len(self.cache["jeol"]["quarters"]), 41)
        self.assertGreaterEqual(len(self.cache["mycronic"]), 32)
        self.assertEqual(dict(self.docs["jeol_industrial_sales"]["series"]["매출"])["2026-06-30"], 49.76)
        self.assertEqual(dict(self.docs["jeol_industrial_profit"]["series"]["영업이익"])["2026-06-30"], 2.21)
        self.assertEqual(dict(self.docs["jeol_industrial_backlog"]["series"]["수주잔고"])["2026-03-31"], 484.38)
        self.assertEqual(dict(self.docs["nuflare_sales"]["series"]["매출"])["2026-03-31"], 1380)
        self.assertEqual(m.end_date(2025, 4), "2026-03-31")

    def test_missing_does_not_become_zero(self):
        self.assertIsNone(m.number("-"))
        self.assertIsNone(m.number(None))
        self.assertEqual(m.number("0"), 0)
        sb = self.docs["jeol_sb_units"]
        self.assertEqual(sb["series"]["수주"][0][0], "2019-06-30")
        self.assertEqual(dict(sb["series"]["수주"])["2026-06-30"], 0)
        self.assertEqual(sb["series_views"]["annual"]["series"]["수주"][0], ["2019-03-31", 5])
        self.assertEqual(self.docs["jeol_mb_units"]["series_views"]["annual"]["series"]["수주"][0], ["2013-03-31", 2])

    def test_ttm_is_ratio_of_sums_and_requires_contiguous_quarters(self):
        points = self.docs["mycronic_book_to_bill"]["series"]["TTM 수주/매출"]
        self.assertEqual([v for d, v in points[:3]], [None]*3)
        # Published quarter sales sum to 3,258, versus rounded reported TTM 3,257.
        self.assertAlmostEqual(dict(points)["2026-06-30"], 2606/3258, places=4)
        self.assertEqual(dict(self.docs["mycronic_orders_sales"]["series"]["수주액"])["2026-06-30"], 675)
        gap = copy.deepcopy(self.cache)
        gap["mycronic"] = [r for r in gap["mycronic"] if r["date"] != "2025-12-31"]
        doc = m.build_documents(gap, self.manual)["mycronic_book_to_bill"]
        self.assertIsNone(dict(doc["series"]["TTM 수주/매출"])["2026-06-30"])

    def test_units_are_deliveries_not_qualification_revenue(self):
        units = dict(self.docs["mycronic_systems"]["series"]["분기 납품"])
        self.assertEqual(units["2025-09-30"], 4)
        self.assertEqual(units["2025-12-31"], 5)
        self.assertEqual(units["2026-03-31"], 7)
        self.assertEqual(dict(self.docs["mycronic_systems"]["series"]["기말 수주잔고"])["2026-06-30"], 13)

    def test_pdf_quarter_table_and_layout_failure(self):
        text = "SEK million\nQuarterly data\n" + "\n".join(f"Q{q} {y}" for q, y in [(2,26),(1,26),(4,25),(3,25),(2,25),(1,25),(4,24),(3,24)])
        for label in ("Order intake", "Order Backlog", "Net Sales", "Gross Margin", "Of which EBIT"):
            text += "\n"+label+"\nPattern Generators\n"+"\n".join(str(i) for i in range(1,9))
        with pymupdf.open() as pdf:
            page = pdf.new_page(width=600, height=1600)
            page.insert_text((30,30), text, fontsize=10)
            rows = m.extract_mycronic(pdf.tobytes(), "https://example.com/report.pdf")
            self.assertEqual(rows[0]["date"], "2026-06-30")
            self.assertEqual(rows[-1]["date"], "2024-09-30")
            self.assertEqual(rows[0]["sales"], 1)
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((30,30), "Quarterly data Pattern Generators")
            with self.assertRaisesRegex(ValueError, "unit"):
                m.extract_mycronic(pdf.tobytes(), "https://example.com/bad.pdf")

    def test_workbook_annual_reconciliation_rejects_bad_units(self):
        sheets = {"2-1": {"CL3": "Unit: Millions of yen", "A9": "Industrial Equipment", "C4": "FY2025"},
                  "4-2": {"A1": "Industrial", "CA3": "Unit: Units", "H4": "FY2025"},
                  "12": {"A1": "Orders Received", "C5": "FY2025", "C7": "100", "C23": "200"}}
        for col, period in zip("CDEFJ", ["1Q", "2Q", "3Q", "4Q", "FY"]):
            sheets["2-1"].update({col+"5": period, col+"9": "4" if period == "FY" else "1", col+"10": "0"})
        for col, period in zip("HIJKO", ["1Q", "2Q", "3Q", "4Q", "FY"]):
            sheets["4-2"].update({col+"5": period, col+"6": "4" if period == "FY" else "1", col+"7": "0"})
        with patch.object(m, "read_xlsx", return_value=sheets):
            m.extract_jeol(b"", "source")
            sheets["4-2"]["O6"] = "9"
            with self.assertRaisesRegex(ValueError, "reconciliation"):
                m.extract_jeol(b"", "source")


if __name__ == "__main__":
    unittest.main()

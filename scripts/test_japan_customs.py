"""Guard source units, release boundaries, missing ratios and revisions."""
import csv
import io
import unittest

from fetch_japan_customs import MONTHS, PRODUCTS, build_docs, parse_csv


def fixture(**overrides):
    fields = ["Exp or Imp", "Year", "HS", "Country", "Unit2", "Value-Year", "Quantity2-Year"]
    fields += [f"{field}-{month}" for month in MONTHS for field in ["Value", "Quantity2"]]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for hs in PRODUCTS:
        row = dict.fromkeys(fields, 0)
        row.update({"Exp or Imp": 1, "Year": 2026, "HS": f"'{hs}'", "Country": 103, "Unit2": "SM",
                    "Value-Jan": 2000, "Quantity2-Jan": 4, "Value-Year": 2000, "Quantity2-Year": 4})
        row.update(overrides)
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


class JapanCustomsTests(unittest.TestCase):
    def test_monthly_not_ytd_and_no_unpublished_months(self):
        rows = parse_csv(fixture(), 2026, 1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1:], ["2026-01-01", "103", 2000, 4])

    def test_reject_wrong_units_direction_and_subtotals(self):
        for overrides in [{"Unit2": "KG"}, {"Exp or Imp": 2}, {"Country": 0}, {"Year": 2025}]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                parse_csv(fixture(**overrides), 2026, 1)

    def test_reject_duplicate_rows(self):
        content = fixture().decode("utf-8-sig")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_csv((content + content.splitlines()[1] + "\n").encode(), 2026, 1)

    def test_reject_cumulative_mismatch_and_future_values(self):
        for overrides in [{"Value-Year": 3000}, {"Value-Feb": 1000, "Value-Year": 3000}]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                parse_csv(fixture(**overrides), 2026, 1)

    def test_units_weighted_ratios_country_reconciliation_and_zero_area(self):
        rows = parse_csv(fixture(), 2026, 1)
        rows += [[hs, "2026-01-01", "106", 1000, 0] for hs in PRODUCTS]
        cache = {"years": {"2026": {"records": rows, "release": {"table_url": "https://www.e-stat.go.jp/", "release_date": "2026-02-27"}}}}
        docs = {doc["id"]: doc for doc in build_docs(cache, "2026-03-01")}
        self.assertEqual(docs["jp_blank_amount"]["series"]["세계 수출액"][0][1], 3)
        self.assertEqual(docs["jp_blank_area"]["series"]["세계 수출 면적"][0][1], 4)
        self.assertEqual(docs["jp_blank_price"]["series"]["면적당 수출액"][0][1], 750000)
        self.assertIsNone(docs["jp_blank_country_price"]["series"]["대만"][0][1])
        self.assertEqual(sum(s[0][1] for s in docs["jp_blank_country"]["series"].values()), 3)


if __name__ == "__main__":
    unittest.main()

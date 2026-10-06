import copy
import html
import json
import unittest

from fetch_snstech_production import ARCHIVE, build_documents, parse_report, period_end, quarter_value, selected_reports


class ProductionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Historical source anchors stay stable when future quarters and
        # amendment receipts are appended by CI. Old receipts are retained.
        cls.records = [r for r in json.loads(ARCHIVE.read_text(encoding="utf8"))["records"]
                       if r["receipt"] <= "20260813000645"]
        cls.reports = selected_reports(cls.records)

    def fixture(self, record):
        def table(rows):
            return "<table>" + "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in rows) + "</table>"
        return (f'<p>{html.escape(record["capacity"]["disclosure_text"])}</p><p>생산실적 '
                + ("(단위 : 장)" if record["production"]["unit"] == "장" else "") + "</p>"
                + table(record["production"]["table_rows"]) + "<p>당해 사업년도의 가동률</p>" + table(record["hours"]["table_rows"]))

    def test_units_scope_and_narrative_capacity_parser(self):
        for period in ["2009-03-31", "2011-12-31", "2015-06-30", "2026-06-30"]:
            r = self.reports[period]
            parsed = parse_report(self.fixture(r), {key: r[key] for key in ["receipt", "title", "year", "month"]}, r["viewer_url"])
            for field in ["capacity", "production", "hours", "header_issue"]:
                self.assertEqual(parsed[field], r[field])
        self.assertEqual(self.reports["2009-03-31"]["capacity"]["values"], {"반도체용": 16632, "디스플레이용": 1026})
        self.assertEqual(self.reports["2011-12-31"]["production"]["values"], {"블랭크마스크": [50118523, 38637858, 50564695]})
        self.assertNotIn("Chemical", self.reports["2011-12-31"]["hours"]["values"])

    def test_three_month_flow_and_time_based_rate(self):
        docs = build_documents(self.records, "2026-10-07")
        amount = docs["snstech_production_amount"]["series"]["블랭크마스크 생산실적"]
        self.assertEqual(len(amount), 58)
        self.assertEqual(amount[-2:], [["2026-03-31", 602.31284], ["2026-06-30", 648.41216]])
        self.assertAlmostEqual(sum(v for d, v in amount if d.startswith("2025")), 2348.10219)
        hours = docs["snstech_production_hours"]["series"]
        self.assertEqual(hours["가동가능시간"][-1], ["2026-06-30", 16512])
        self.assertEqual(hours["실제가동시간"][-1], ["2026-06-30", 13851])
        util = docs["snstech_production_utilization"]["series"]
        self.assertEqual(util["분기 가동률(시간 기준)"][-1], ["2026-06-30", 83.88])
        self.assertEqual(util["연초 누적 가동률(시간 기준)"][-1], ["2026-06-30", 83.7])
        self.assertEqual(len(docs["snstech_production_amount"]["point_sources"]["2026-06-30"]["reports"]), 2)

    def test_annual_capacity_is_not_a_quarter_flow(self):
        self.assertEqual(quarter_value(self.reports, "2009-12-31", "capacity")[0], 23526)
        for period in ["2010-03-31", "2010-06-30", "2010-12-31", "2011-09-30", "2026-06-30"]:
            self.assertIsNone(quarter_value(self.reports, period, "capacity")[0])
        docs = build_documents(self.records, "2026-10-07")
        points = docs["snstech_production_capacity"]["series"]["공시된 연간 생산능력"]
        self.assertEqual(len(points), 8)
        self.assertEqual({v for _, v in points}, {94104})
        self.assertEqual(len(docs["snstech_production_pieces"]["series"]["분기 생산능력(장)"]), 4)

    def test_unit_transition_missing_quarter_and_negative_flow(self):
        self.assertIsNone(quarter_value(self.reports, "2011-12-31", "amount")[0])
        self.assertIsNone(quarter_value(self.reports, "2011-12-31", "pieces")[0])
        self.assertIsNone(quarter_value({"2026-06-30": self.reports["2026-06-30"]}, "2026-06-30", "amount")[0])
        reports = copy.deepcopy(self.reports)
        reports["2026-06-30"]["production"]["values"]["블랭크마스크"][0] = 1
        with self.assertRaisesRegex(ValueError, "Negative quarter"):
            quarter_value(reports, "2026-06-30", "amount")

    def test_bad_original_hours_preserved_without_fabricated_quarters(self):
        r = self.reports["2020-03-31"]
        self.assertEqual(r["hours"]["values"]["블랭크마스크"]["available"], 53856)
        self.assertFalse(r["hours"]["valid"])
        for period in ["2020-03-31", "2020-06-30"]:
            self.assertIsNone(quarter_value(self.reports, period, "available")[0])
            self.assertIsNotNone(quarter_value(self.reports, period, "amount")[0])
        self.assertEqual(quarter_value(self.reports, "2020-09-30", "available")[0], 16704)
        parsed = parse_report(self.fixture(r), {key: r[key] for key in ["receipt", "title", "year", "month"]}, r["viewer_url"])
        self.assertFalse(parsed["hours"]["valid"])

    def test_latest_revision_and_annual_comparisons(self):
        r = copy.deepcopy(self.reports["2026-03-31"])
        r["receipt"] = "20260901000001"
        self.assertEqual(selected_reports(self.records + [r])["2026-03-31"]["receipt"], r["receipt"])
        docs = build_documents(self.records, "2026-10-07")
        annual = dict(docs["snstech_production_annual"]["series"]["연간 블랭크마스크 생산실적"])
        self.assertEqual(len(annual), 17)
        self.assertEqual(annual["2009-12-31"], 505.64695)
        self.assertEqual(annual["2011-12-31"], 500.48316)
        self.assertEqual(annual["2021-12-31"], 984.68955)
        self.assertNotIn("2026-12-31", annual)
        self.assertEqual(len(self.reports), 70)
        self.assertEqual(set(self.reports), {period_end(year, month) for year in range(2009, 2027) for month in (3, 6, 9, 12) if (year, month) <= (2026, 6)})

    def test_unknown_unit_and_unexplained_year_mismatch_fail(self):
        r = self.reports["2026-06-30"]
        info = {key: r[key] for key in ["receipt", "title", "year", "month"]}
        with self.assertRaisesRegex(ValueError, "unit"):
            parse_report(self.fixture(r).replace("천원", "kg"), info, r["viewer_url"])
        with self.assertRaisesRegex(ValueError, "year mismatch"):
            parse_report(self.fixture(r).replace("2026년", "2024년"), info, r["viewer_url"])


if __name__ == "__main__":
    unittest.main()

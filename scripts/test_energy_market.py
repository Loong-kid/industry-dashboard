import calendar
import json
import unittest

from fetch_energy_market import (
    BATTERY, METRIC_UNITS, OUT, POWER_TYPES, SCENARIOS, build_atb, eia_series, latest_atb_key, workbook_series,
)


def atb_fixture():
    for tech in (*POWER_TYPES, BATTERY):
        for metric in ("CAPEX", "Fixed O&M", "CF", "LCOE", "Heat Rate"):
            for scenario in SCENARIOS:
                for year in range(2023, 2043):
                    yield {
                        "atb_year": 2025, "technology": tech[0], "techdetail": tech[1], "techdetail2": tech[2],
                        "core_metric_parameter": metric, "core_metric_variable": year, "scenario": scenario,
                        "units": METRIC_UNITS[metric], "value": 0.25 if metric == "CF" else 400.0,
                    }


class TestEnergyMarket(unittest.TestCase):
    def test_latest_atb_revision_sorts_numerically(self):
        contents = "".join(
            f"<Contents><Key>ATB/electricity/parquet/{key}</Key><LastModified>2026-11-13T01:00:00Z</LastModified></Contents>"
            for key in ("2026/", "2025/v2.0.0/ATBe.parquet", "2025/v10.0.0/ATBe.parquet", "2024/v11.0.0/ATBe.parquet")
        )
        edition, key, modified = latest_atb_key(f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{contents}</ListBucketResult>')
        self.assertEqual((edition, key, modified), (2025, "ATB/electricity/parquet/2025/v10.0.0/ATBe.parquet", "2026-11-13"))

    def test_atb_capacity_conversion_and_forecast_boundary(self):
        source = "https://example.org/2025/v2.0.0/ATBe.parquet"
        docs = {doc["id"]: doc for doc in build_atb(atb_fixture(), 2025, source, "2026-11-13", "2026-11-26")}
        costs = docs["atb_ess_4h_capex"]
        self.assertEqual(costs["series"]["중간"][0], ["2023-12-31", 100.0])
        self.assertEqual(costs["forecast_from"], "2024-01-01")
        self.assertEqual(docs["atb_power_capacity_factor"]["series"]["대형 태양광"][0], ["2023-12-31", 25.0])
        self.assertNotIn("H급 가스복합", docs["atb_power_lcoe"]["series"])
        self.assertEqual(list(docs["atb_gas_heat_rate"]["series"]), ["H급 가스복합"])

        rows = list(atb_fixture())
        with self.assertRaisesRegex(ValueError, "Duplicate ATB observation"):
            build_atb(rows + [rows[0]], 2025, source, "2026-11-13", "2026-11-26")
        with self.assertRaisesRegex(ValueError, "Incomplete ATB projection"):
            build_atb(rows[1:], 2025, source, "2026-11-13", "2026-11-26")

    def test_berkeley_year_filter_preserves_missing_values(self):
        rows = [(2022, 35.1), (2023, None), (2024, 37.0), (2025, 48.0)]
        self.assertEqual(workbook_series(rows, 0, {"PPA": 1}, 2024), {"PPA": [["2022-12-31", 35.1], ["2024-12-31", 37.0]]})
        with self.assertRaisesRegex(ValueError, "Duplicate or unordered"):
            workbook_series(rows + [(2024, 38.0)], 0, {"PPA": 1}, 2024)

    def test_eia_month_end_and_annual_totals_are_separate(self):
        header = ("Period", "Residential", "Commercial", "Industrial", "Total")
        annual_rows = [(year, 200, 90, 10, 300) for year in range(2016, 2024)]
        monthly_rows = [(f"Year {year}", None, None, None, None) if month == 0
                        else (("Sept" if month == 9 else calendar.month_name[month]), 200, 90, 11, 301)
                        for year in (2023, 2024) for month in range(13)]
        annual, monthly = eia_series([header, *annual_rows, *monthly_rows])
        self.assertEqual(annual["전체"]["2023-12-31"], 0.3)
        self.assertEqual(monthly["전체"]["2023-12-31"], 0.301)
        self.assertIn("2024-02-29", monthly["전체"])
        self.assertIn("2024-09-30", monthly["전체"])

    def test_public_cards_are_routed_and_have_valid_observations(self):
        catalog = json.loads((OUT.parent / "catalog.json").read_text(encoding="utf-8"))
        routes = {
            (industry["id"], section.get("tab")): set().union(*(s["indicators"] for s in industry["sections"]
                if s.get("data_industry") == OUT.name and s.get("tab") == section.get("tab")))
            for industry in catalog["industries"] for section in industry["sections"] if section.get("data_industry") == OUT.name
        }
        self.assertEqual({route: len(ids) for route, ids in routes.items()}, {("power", None): 5, ("ess", "market"): 2, ("solar", "market"): 5})
        self.assertEqual(set().union(*routes.values()), {file.stem for file in OUT.glob("*.json")})
        for indicator in set().union(*routes.values()):
            with self.subTest(indicator=indicator):
                doc = json.loads((OUT / f"{indicator}.json").read_text(encoding="utf-8"))
                self.assertEqual(doc["id"], indicator)
                self.assertTrue(doc["source_url"].startswith("https://"))
                for view in [doc, *doc.get("series_views", {}).values()]:
                    for series in view["series"].values():
                        dates = [day for day, _ in series]
                        self.assertEqual(dates, sorted(set(dates)))
                        self.assertGreaterEqual(len(dates), 2)
                if indicator.startswith("atb_"):
                    self.assertGreater(doc["forecast_from"], max(points[0][0] for points in doc["series"].values()))


if __name__ == "__main__":
    unittest.main()

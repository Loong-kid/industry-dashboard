import tempfile
import json
import unittest
from pathlib import Path

from fetch_ppi import export, parse_csv, recent_points


class PPIExportTests(unittest.TestCase):
    def test_csv_missing_months_and_finite_values(self):
        points = parse_csv("observation_date,PCU1,PCU2\n2025-01-01,100,.\n2025-02-01,.,200\n2025-03-01,NaN,inf\n", ["PCU1", "PCU2"])
        self.assertEqual(points, {"PCU1": [["2025-01", 100.0]], "PCU2": [["2025-02", 200.0]]})

    def test_reject_upstream_error_page(self):
        with self.assertRaises(ValueError):
            parse_csv("<html>Too many requests</html>", ["PCU1"])
        with self.assertRaises(ValueError):
            parse_csv("DATE,OTHER\n2025-01-01,5\n", ["PCU1"])

    def test_recent_window_by_calendar_not_row_count(self):
        points = [["2020-01", 1], ["2021-12", 2], ["2022-01", 3], ["2026-01", 4]]
        self.assertEqual(recent_points(points, "2026-01"), points[2:])

    def test_export_retains_full_history_and_metadata(self):
        catalog = {"built_at": "2025-01-01", "root_category_id": 1,
                   "categories": [{"id": 2, "parent_id": 1, "name": "Sector"}],
                   "series": [{"id": "PCU1", "category_ids": [2]}, {"id": "PCU2", "category_ids": [2]}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            result = export(catalog, {"PCU1": [["1990-01", 50], ["2026-01", 100]], "PCU2": []}, path)
            self.assertEqual(result["available"], 1)
            self.assertIn("1990-01", (path / "series/PCU1.json").read_text())
            self.assertNotIn("1990-01", (path / "sectors/2.json").read_text())
            nav = json.loads((path / "navigation.json").read_text())
            self.assertEqual(nav["latest_dates"], {"PCU1": "2026-01", "PCU2": None})
            self.assertEqual(nav["updated"], result["updated"])
            original = (path / "catalog.json").read_bytes()
            with self.assertRaises(ValueError):
                export(catalog, {"PCU1": []}, path)
            self.assertEqual(original, (path / "catalog.json").read_bytes())


if __name__ == "__main__":
    unittest.main()

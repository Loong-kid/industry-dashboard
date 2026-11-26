import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_steam_trends as st


class SteamTrendsTests(unittest.TestCase):
    def test_release_formats(self):
        self.assertEqual(st.parse_release("Jun 16, 2025"), "2025-06-16")
        self.assertEqual(st.parse_release("4 Nov, 2026"), "2026-11-04")
        self.assertEqual(st.parse_release("Nov 2026"), "2026-11-01")
        self.assertIsNone(st.parse_release("Coming soon"))
        self.assertIsNone(st.parse_release("Q1 2027"))

    def test_details_price_and_coop(self):
        payload = {"1": {"success": True, "data": {"name": "X", "type": "game", "is_free": False,
                   "price_overview": {"currency": "USD", "initial": 799, "final": 495},
                   "release_date": {"coming_soon": False, "date": "Jun 16, 2025"},
                   "categories": [{"description": "Online Co-op"}], "genres": [{"description": "Indie"}]}}}
        d = st.parse_details(1, payload)
        self.assertEqual(d["price_usd"], 7.99)  # 할인가가 아닌 정가
        self.assertTrue(d["coop"] and d["online_coop"] and d["multi"])
        self.assertEqual(d["release"], "2025-06-16")

    def test_non_usd_price_is_not_converted(self):
        payload = {"1": {"success": True, "data": {"name": "X", "is_free": False,
                   "price_overview": {"currency": "KRW", "initial": 2420000}, "release_date": {"date": "Jun 16, 2025"}}}}
        self.assertIsNone(st.parse_details(1, payload)["price_usd"])
        self.assertIsNone(st.parse_details(2, {"2": {"success": False}}))

    def test_short_ranking_is_rejected(self):
        with self.assertRaises(ValueError):
            st.parse_concurrent({"response": {"last_update": 0, "ranks": [{"appid": 1, "rank": 1}]}})

    def test_lifecycle_ratio_from_release_month(self):
        app = {"release": "2025-06-16", "steamcharts": {"points": [["2025-06", 100.0, 300], ["2025-07", 200.0, 500], ["2025-10", 50.0, 90]]}}
        self.assertEqual(st.lifecycle(app), [[0, "2025-06", 100.0, 300, 50.0], [1, "2025-07", 200.0, 500, 100.0], [4, "2025-10", 50.0, 90, 25.0]])
        self.assertEqual(st.lifecycle({"release": None, "steamcharts": {"points": [["2025-06", 1, 1]]}}), [])

    def test_early_access_launch_uses_first_steamcharts_month(self):
        app = {"release": "2026-07-09", "steamcharts": {"points": [["2024-01", 900.0, 2000], ["2026-07", 300.0, 500]]}}
        self.assertEqual(st.launch_date(app), "2024-01-01")
        self.assertEqual(st.lifecycle(app)[-1][0], 30)
        self.assertEqual(st.age_days(app, "2024-01-31"), 30)
        self.assertEqual(st.launch_date({"release": "2025-06-16", "steamcharts": {"points": [["2025-06", 1, 1]]}}), "2025-06-16")

    def test_daily_upsert_replaces_same_day_and_trims(self):
        rows = st.upsert_daily([["2024-01-01", 1, None, None], ["2026-11-27", 5, None, None]], "2026-11-27", [9, 10, 3])
        self.assertEqual(rows, [["2026-11-27", 9, 10, 3]])

    def test_failed_rankings_keep_previous_file(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "steam_trends.json"
            out.write_text(json.dumps({"date": "2026-11-26"}), encoding="utf-8")
            with patch.object(st, "OUT", out), patch.object(st, "get", side_effect=RuntimeError("blocked")):
                with self.assertRaises(RuntimeError):
                    st.collect("2026-11-27", pause=0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), {"date": "2026-11-26"})


if __name__ == "__main__":
    unittest.main()

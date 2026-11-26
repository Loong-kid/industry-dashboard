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

    def test_topsellers_keep_apps_only(self):
        ranks = [{"appid": i, "rank": i, "last_week_rank": i + 1, "consecutive_weeks": 2, "item": {"item_type": 0}} for i in range(1, 60)]
        ranks.append({"appid": 999, "rank": 60, "item": {"item_type": 1}})  # 묶음 상품 등은 제외
        week, rows = st.parse_topsellers({"response": {"start_date": 1794873600, "ranks": ranks}})
        self.assertEqual(week, "2026-11-17")
        self.assertEqual(len(rows), 59)
        self.assertEqual(rows[0], [1, 1, 2, 2])

    def test_wishlist_reads_appid_from_capsule(self):
        items = [{"name": f"G{i}", "logo": f"https://x/steam/apps/{100 + i}/capsule.jpg"} for i in range(25)]
        self.assertEqual(st.parse_wishlist({"items": items})[:2], [[100, 1], [101, 2]])
        with self.assertRaises(ValueError):
            st.parse_wishlist({"items": items[:3]})

    def test_reviews_and_followers(self):
        payload = {"response": {"store_items": [{"id": 5, "success": 1, "reviews": {"summary_filtered": {"review_count": 1200, "percent_positive": 91}}},
                                                {"id": 6, "success": 2}]}}
        self.assertEqual(st.parse_reviews(payload), {5: [1200, 91]})
        self.assertEqual(st.parse_followers("<memberList><memberCount>340326</memberCount></memberList>"), 340326)

    def test_histogram_weeks_roll_into_calendar_months(self):
        # 2025-02-26, 2025-03-05 (주 단위) → 2월·3월
        payload = {"results": {"rollup_type": "week", "rollups": [
            {"date": 1740528000, "recommendations_up": 90, "recommendations_down": 10},
            {"date": 1741132800, "recommendations_up": 40, "recommendations_down": 10}]}}
        months, rollup = st.parse_histogram(payload)
        self.assertEqual(months, [["2025-02", 100, 90], ["2025-03", 50, 40]])
        self.assertEqual(rollup, "week")

    def test_review_lifecycle_excludes_current_month(self):
        app = {"release": "2025-02-26", "review_months": [["2025-02", 100, 90], ["2025-03", 200, 180], ["2025-05", 50, 40], ["2026-11", 9, 9]]}
        self.assertEqual(st.review_lifecycle(app, "2026-11-27"), [[0, "2025-02", 100, 50.0], [1, "2025-03", 200, 100.0], [3, "2025-05", 50, 25.0]])

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

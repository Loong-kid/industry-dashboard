import unittest

from fetch_games import compact_history, parse_apple, parse_play, parse_steam


class GameParsingTests(unittest.TestCase):
    def test_old_history_keeps_real_monthly_endpoints_and_recent_days(self):
        rows=[{"date":date,"id":"one"} for date in ["2026-01-01","2026-01-29","2026-02-03","2026-10-01","2026-10-02"]]
        actual=compact_history(rows,["id"],"2026-10-24")
        self.assertEqual([r["date"] for r in actual],["2026-01-29","2026-02-03","2026-10-01","2026-10-02"])

    def test_steam_excludes_rolling_window_and_unfinished_month(self):
        html = '''<table class="common-table"><tbody>
        <tr><td>Last 30 Days</td><td>999</td><td>1</td><td>1%</td><td>9999</td></tr>
        <tr><td>October 2026</td><td>800</td><td>1</td><td>1%</td><td>900</td></tr>
        <tr><td>September 2026</td><td>1,234.50</td><td>1</td><td>1%</td><td>2,500</td></tr>
        </tbody></table>'''
        self.assertEqual(parse_steam(html, "2026-10"), [["2026-09",1234.5,2500]])

    def test_download_band_is_lower_bound_without_monthly_inference(self):
        html = '''<script type="application/ld+json">{"@type":"SoftwareApplication","name":"Test","applicationCategory":"GAME_PUZZLE","aggregateRating":{"ratingValue":"4.5","ratingCount":"123"}}</script><div>100M+ Downloads</div>'''
        parsed = parse_play(html, "test.package")
        self.assertEqual(parsed["installs_lower"], 100_000_000)
        self.assertNotIn("monthly_downloads", parsed)
        self.assertNotIn("total_estimate", parsed)
        self.assertEqual(parsed["ratings"],123)

    def test_missing_downloads_stay_missing(self):
        html = '<script type="application/ld+json">{"@type":"SoftwareApplication","name":"Test"}</script>'
        self.assertIsNone(parse_play(html,"test")["installs_lower"])

    def test_changed_source_layout_does_not_produce_empty_success(self):
        with self.assertRaises(ValueError): parse_steam("<html>blocked</html>","2026-10")
        with self.assertRaises(ValueError): parse_play("<html>blocked</html>","test")
        with self.assertRaises(ValueError): parse_apple({"feed":{}})


if __name__ == "__main__": unittest.main()

import csv
from datetime import date, timedelta
import io
import unittest
import zipfile

from fetch_game_fx import build_snapshot, METHOD, parse_rates, period_average


def weekdays(start, end, value):
    begin, finish = date.fromisoformat(start), date.fromisoformat(end)
    return {(begin+timedelta(days=i)).isoformat(): {"JPY": value}
            for i in range((finish-begin).days+1) if (begin+timedelta(days=i)).weekday() < 5}


class GameFxTests(unittest.TestCase):
    def test_cross_rate_orientation_and_nonfinite(self):
        csv_data = "Date,USD,JPY,KRW,CNY,PLN,\n2026-06-30,1.25,187.5,1750,N/A,NaN,\n"
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as z:
            z.writestr("eurofxref-hist.csv", csv_data)
        parsed = parse_rates(raw.getvalue())["2026-06-30"]
        self.assertEqual(parsed["EUR"], .8)
        self.assertEqual(parsed["JPY"], 150)  # JPY per USD, NOT reciprocal
        self.assertEqual(parsed["KRW"], 1400)
        self.assertNotIn("CNY", parsed)
        self.assertNotIn("PLN", parsed)

    def test_exact_fiscal_year_daily_weighting(self):
        first = weekdays("2024-04-01", "2024-12-31", 100)
        second = weekdays("2025-01-01", "2025-03-31", 200)
        rates = first | second | weekdays("2025-04-01", "2025-06-30", 999)
        quote = period_average(rates, "JPY", "2024-04-01", "2025-03-31")
        self.assertEqual(quote["observations"], len(first)+len(second))
        self.assertAlmostEqual(quote["local_per_usd"], (len(first)*100+len(second)*200)/(len(first)+len(second)))
        self.assertNotEqual(quote["local_per_usd"], 125)  # actual business-day weights
        self.assertEqual(quote["first"], "2024-04-01")
        leap = period_average(weekdays("2024-01-01", "2024-03-31", 150), "JPY", "2024-01-01", "2024-03-31")
        self.assertEqual(leap["last"], "2024-03-29")  # no invented weekend observations
        self.assertEqual(leap["observations"], 65)

    def test_truncated_feed_and_internal_holes_are_missing(self):
        rates = weekdays("2026-01-01", "2026-03-31", 150)
        self.assertIsNone(period_average(rates, "JPY", "2026-01-01", "2026-06-30"))
        self.assertIsNone(period_average(rates, "CNY", "2026-01-01", "2026-03-31"))
        for day in list(rates):
            if "2026-02-02" <= day <= "2026-02-10":
                del rates[day]
        self.assertIsNone(period_average(rates, "JPY", "2026-01-01", "2026-03-31"))

    def test_fetch_failure_retains_only_exact_completed_interval(self):
        intervals = [("JPY", "2026-01-01", "2026-03-31")]
        old = build_snapshot({}, intervals, weekdays("2026-01-01", "2026-03-31", 150), "old", "hash")
        failed = build_snapshot(old, intervals+[("JPY", "2026-04-01", "2026-06-30")], None, "new", error="unavailable")
        self.assertEqual(failed["fetched"], "old")
        self.assertEqual(len(failed["periods"]), 1)
        self.assertEqual(failed["periods"]["JPY|2026-01-01|2026-03-31"]["fetched"], "old")
        self.assertEqual(failed["missing"], ["JPY|2026-04-01|2026-06-30"])
        self.assertEqual(failed["method"], METHOD)


if __name__ == "__main__":
    unittest.main()

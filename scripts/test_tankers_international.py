import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fetchers import tankers_international as ti


def raw(identifier=1, day="01 Jul 2026 12:00", status="Fixed", tce=100):
    return {"FixtureId": identifier, "Id": f"guid-{identifier}", "ReportedTime": day,
            "PublicationTimestamp": "2026-07-01T11:00:00", "Status": status,
            "Vessel": "Ship <test>", "VesselCategory": "Modern (Scrubber)",
            "SubLoadArea": "AG", "SubDischargeArea": "China",
            "ActualValues": {"ActTcPerDayIncIdle": tce}, "ActualTCEPerDay": "USD "}


class TankersTests(unittest.TestCase):
    def test_tce_uses_idle_inclusive_numeric_and_never_rounded_card_text(self):
        row = raw(tce=123456.78)
        row.update({"ActTcPerDayIncIdle": "123K/Day", "ActualTCEPerDay": "USD 123,457"})
        row["ActualValues"]["RvTcPerDayExIdle"] = 999999
        self.assertEqual(ti.normalize_fixture(row)["tce"], 123456.78)
        for value in [None, float("nan"), float("inf"), True]:
            row["ActualValues"]["ActTcPerDayIncIdle"] = value
            row["ActualTCEPerDay"] = "USD "
            self.assertIsNone(ti.normalize_fixture(row)["tce"])
        row["ActualTCEPerDay"] = "USD -1,234.50"
        self.assertEqual(ti.normalize_fixture(row)["tce"], -1234.5)
        for value in [0, -100]:
            self.assertEqual(ti.normalize_fixture(raw(tce=value))["tce"], value)

    def test_invalid_empty_or_partial_response_does_not_become_market_data(self):
        payload = {"Results": [raw()], "Count": 1, "HasMoreResults": False}
        self.assertEqual(len(ti.parse_payload(payload)), 1)
        for patch in [{"Results": []}, {"Count": 2}, {"HasMoreResults": True},
                      {"ContinuationToken": "next"}, {"Results": [raw(), raw()], "Count": 2},
                      {"Results": [raw(status="Failed")]}, {"Results": [raw(tce=None)]}]:
            with self.assertRaises(ValueError):
                ti.parse_payload({**payload, **patch})
        for field, value in [("FixtureId", "javascript:bad"), ("ReportedTime", "broken")]:
            row = raw(); row[field] = value
            if field == "ReportedTime":
                row["PublicationTimestamp"] = "broken"
            with self.assertRaises(ValueError):
                ti.normalize_fixture(row)

    def test_archive_preserves_old_fixtures_but_applies_status_and_missing_tce_corrections(self):
        previous = [ti.normalize_fixture(raw(1)), ti.normalize_fixture(raw(2, "08 Jul 2026 12:00", tce=200))]
        revised = ti.normalize_fixture(raw(1, status="Failed", tce=None))
        merged = ti.merge_fixtures(previous, [revised])
        self.assertEqual(len(merged), 2)
        corrected = next(row for row in merged if row["fixture_id"] == "1")
        self.assertEqual(corrected["status"], "Failed")
        self.assertIsNone(corrected["tce"])
        series, _, counts, _, _ = ti.aggregate(merged)
        self.assertIsNone(dict(series[ti.OVERALL])["2026-07-07"])
        self.assertEqual(dict(series[ti.OVERALL])["2026-07-08"], 200)
        self.assertEqual(dict(counts["확정 성약"])["2026-07-07"], 0)

    def test_failed_collection_keeps_previous_archive_and_collection_date(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "shipping" / "ti_vlcc_fixtures.json"
            path.parent.mkdir()
            previous = json.dumps({"fetched": "2026-07-01", "fixtures": [ti.normalize_fixture(raw())]})
            path.write_text(previous, encoding="utf-8")
            response = Mock()
            response.json.return_value = {"Results": [], "Count": 0}
            with patch.object(ti, "DATA_DIR", root), patch.object(ti.requests, "get", return_value=response):
                with self.assertRaises(ValueError):
                    ti.run()
            self.assertEqual(path.read_text(encoding="utf-8"), previous)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_rolling_window_filters_status_missing_tce_and_routes_and_retains_gaps(self):
        rows = [
            raw(1, tce=100), raw(2, "02 Jul 2026 12:00", tce=300),
            raw(3, "03 Jul 2026 12:00", status="Failed", tce=9999),
            raw(4, "04 Jul 2026 12:00", status="On Subs", tce=9999),
            raw(5, "05 Jul 2026 12:00", tce=None),
            raw(6, "16 Jul 2026 12:00", status="On Subs", tce=9999),
        ]
        docs = ti.build_documents([ti.normalize_fixture(row) for row in rows], "2026-07-20", "2026-07-16")
        tce, routes, counts, archive = docs
        self.assertEqual(tce["series"][ti.OVERALL][0], ["2026-07-07", 200])
        self.assertEqual(dict(tce["series"][ti.OVERALL])["2026-07-08"], 300)
        self.assertIsNone(dict(tce["series"][ti.OVERALL])["2026-07-09"])
        self.assertEqual(dict(counts["series"]["확정 성약"])["2026-07-07"], 3)
        self.assertEqual(dict(counts["series"]["TCE 공개 성약"])["2026-07-07"], 2)
        self.assertEqual(dict(tce["sample_counts"][ti.OVERALL])["2026-07-07"], 2)
        self.assertEqual(dict(routes["series"]["AG → China"])["2026-07-07"], 200)
        self.assertIsNone(dict(routes["series"]["USG → China"])["2026-07-07"])
        self.assertFalse(tce["span_gaps"])
        self.assertEqual(tce["series"][ti.OVERALL][-1][0], "2026-07-16")
        self.assertEqual(tce["updated"], "2026-07-16")
        self.assertEqual(tce["fetched"], "2026-07-20")
        self.assertEqual(len(archive["fixtures"]), 6)
        self.assertEqual(archive["series"], {})


if __name__ == "__main__":
    unittest.main()

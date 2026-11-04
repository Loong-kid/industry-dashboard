# -*- coding: utf-8 -*-
"""LNG 탭 이름, 미국 프로젝트·FLNG 원장과 막대 자료, EIA 파싱 회귀 시험."""
import csv
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_lng_capacity as board  # noqa: E402
import fetch_lng_projects as eia  # noqa: E402


class FakeSheet:
    def __init__(self, rows):
        self.rows = rows

    def iter_rows(self, min_row=1, values_only=True):
        return iter(self.rows[min_row - 1:])


def eia_row(name, train, base, peak, status):
    row = [None] * 21
    row[0], row[1], row[3], row[5], row[6], row[7], row[20] = name, train, base, peak, status, 2027, "Op"
    return row


class LngCapacityTest(unittest.TestCase):
    def test_tab_is_named_lng_and_cards_are_wired(self):
        catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
        natgas = next(i for i in catalog["industries"] if i["id"] == "natgas")
        tab = next(t for t in natgas["tabs"] if t["id"] == "overview")
        self.assertEqual(tab["name"], "LNG")
        kinds = {x for s in natgas["sections"] if s.get("table_kind") == "lng_capacity" for x in s["indicators"]}
        self.assertEqual(kinds, {"lng_us_by_company", "flng_by_company"})
        app = (ROOT / "assets/app.js").read_text(encoding="utf-8")
        self.assertIn('section.table_kind === "lng_capacity" ? renderLngCapacity', app)
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("assets/lng-capacity.js", html)
        self.assertIn("assets/lng-capacity.css", html)
        self.assertLess(html.index("assets/lng-capacity.js"), html.index("assets/app.js"))

    def test_ledgers_are_valid_and_unique(self):
        for rows in (board.read_us(), board.read_flng()):
            keys = Counter((r["company"], r["project"]) for r in rows)
            self.assertEqual([k for k, n in keys.items() if n > 1], [])
            for r in rows:
                self.assertIn(r["status"], board.STATUSES)
                self.assertGreater(r["mtpa"], 0)
                self.assertTrue(r["source_url"].startswith("https://"))

    def test_published_docs_match_ledgers(self):
        for cid, rows in (("lng_us_by_company", board.read_us()), ("flng_by_company", board.read_flng())):
            doc = json.loads((ROOT / f"data/natgas/{cid}.json").read_text(encoding="utf-8"))
            self.assertEqual(doc["rows"], rows)
            self.assertEqual(doc["totals"], board.totals(rows))
            self.assertEqual(set(doc["status_labels"]), set(doc["status_order"]))

    def test_recent_decisions_stay_recorded(self):
        us = {r["project"]: r for r in board.read_us()}
        for project in ("Port Arthur 2단계", "CP2 2단계", "Commonwealth LNG", "Rio Grande T5", "Delfin FLNG 1"):
            self.assertEqual(us[project]["status"], "construction", project)
        self.assertEqual(us["Lake Charles LNG"]["status"], "suspended")
        flng = {r["project"]: r for r in board.read_flng()}
        self.assertEqual(flng["Hilli Episeyo"]["status"], "construction")
        self.assertEqual(flng["Nguya FLNG"]["status"], "operating")
        self.assertNotIn("Ichthys FLNG", flng)

    def test_delfin_matches_between_boards(self):
        us = sum(r["mtpa"] for r in board.read_us() if r["company"] == "Delfin Midstream")
        flng = sum(r["mtpa"] for r in board.read_flng() if r["company"] == "Delfin Midstream")
        self.assertEqual(round(us, 3), round(flng, 3))

    def test_eia_keeps_first_row_and_total_capacity(self):
        rows = [["title"], ["head"], ["unit"],
                eia_row("Sabine Pass", "Train 1", 4.5, 5.76, "Commercial operation"),
                eia_row("Port Arthur LNG Phase 1", "Trains 1-2", 12, "13.5^", "Under construction"),
                eia_row("Woodside Louisiana LNG Phase 1", "Trains 1-3", 5.52, 16.56, "Under constructionH")]
        built = {r["project"]: r["mtpa"] for r in eia.parse_built(FakeSheet(rows))}
        self.assertEqual(built["Sabine Pass"], 4.5, "첫 행을 건너뛰면 안 된다")
        self.assertEqual(built["Port Arthur LNG Phase 1"], 12, "피크가 약간 크면 기준 용량을 쓴다")
        self.assertEqual(built["Woodside Louisiana LNG Phase 1"], 16.56, "기준 칸이 트레인당이면 합계를 쓴다")

    def test_flng_fleet_csv_has_source_column(self):
        with (ROOT / "manual/flng_fleet.csv").open(encoding="utf-8", newline="") as f:
            self.assertIn("source_url", csv.DictReader(f).fieldnames)


if __name__ == "__main__":
    unittest.main()

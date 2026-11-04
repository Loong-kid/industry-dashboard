# -*- coding: utf-8 -*-
"""한국·일본 블랭크마스크 분기 비교: 환산, 분기 합계, 점유율, 카드 연결 시험."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import derive_blank_share as share  # noqa: E402


class BlankShareTest(unittest.TestCase):
    def test_monthly_fx_and_share(self):
        korea = {"2026-01": 1.0, "2026-02": 2.0, "2026-03": 3.0}
        japan = {"2026-01": 1000.0, "2026-02": 3000.0, "2026-03": 1000.0}
        fx = {"2026-01": 100.0, "2026-02": 150.0, "2026-03": 100.0}
        row = share.quarter_rows(korea, japan, fx)[0]
        self.assertEqual(row["date"], "2026-03-31")
        self.assertEqual(row["korea"], 6.0)
        self.assertEqual(row["japan"], 40.0, "달마다 그달 환율로 바꾼다")
        self.assertEqual(row["korea_share"], 13.0)
        self.assertEqual(row["japan_share"], 87.0)

    def test_incomplete_quarter_is_dropped(self):
        months = {f"2026-{m:02d}": 1.0 for m in (1, 2, 3, 4, 5)}
        rows = share.quarter_rows(months, months, {k: 100.0 for k in months})
        self.assertEqual([r["date"] for r in rows], ["2026-03-31"])
        no_fx = share.quarter_rows(months, months, {"2026-01": 100.0, "2026-02": 100.0})
        self.assertEqual(no_fx, [], "환율이 빠진 달이 있으면 그 분기를 만들지 않는다")

    def test_monthly_average(self):
        self.assertEqual(share.monthly_average({"2026-09-01": {"JPY": 100.0}, "2026-09-02": {"JPY": 102.0}, "2026-10-01": {"JPY": 90.0}}),
                         {"2026-09": 101.0, "2026-10": 90.0})

    def test_published_docs_are_consistent(self):
        load = lambda name: json.loads((ROOT / f"data/semicon/{name}.json").read_text(encoding="utf-8"))
        amount, percent = load("blank_kr_jp_export"), load("blank_kr_jp_share")
        self.assertEqual(amount["chart_type"], "bar")
        self.assertEqual(percent["bar_value_suffix"], "%")
        korea = dict(map(tuple, amount["series"][share.KOREA]))
        japan = dict(map(tuple, amount["series"][share.JAPAN]))
        for date, value in percent["series"][share.KOREA]:
            self.assertAlmostEqual(value, korea[date] / (korea[date] + japan[date]) * 100, delta=0.06, msg=date)
        for (date, kr), (_, jp) in zip(percent["series"][share.KOREA], percent["series"][share.JAPAN]):
            self.assertAlmostEqual(kr + jp, 100, delta=0.11, msg=date)
        self.assertIn("HS 370199000", percent["note"])
        self.assertIn("세계 시장 점유율이 아니", percent["note"])

    def test_card_is_wired(self):
        catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
        semicon = next(i for i in catalog["industries"] if i["id"] == "semicon")
        section = next(s for s in semicon["sections"] if "blank_kr_jp_share" in (s.get("indicators") or []))
        self.assertEqual(section["tab"], "snstech")
        self.assertEqual(section["indicators"], ["blank_kr_jp_export", "blank_kr_jp_share"])
        app = (ROOT / "assets/app.js").read_text(encoding="utf-8")
        self.assertIn("doc.bar_value_digits", app)
        self.assertIn("doc.bar_value_suffix", app)
        self.assertIn("thin: doc.bar_value_thin", app)
        self.assertIn("scripts/derive_blank_share.py", (ROOT / ".github/workflows/update-data.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""에스앤에스텍 수출 vs 전국 용도별 수출 카드 시험."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aggregate_snstech import export_stack_series  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SEMI = ROOT / "data" / "semicon"


def load(name):
    return json.loads((SEMI / f"{name}.json").read_text(encoding="utf-8"))


class ExportStackSeries(unittest.TestCase):
    def test_keeps_quarters_only_one_side_has(self):
        sns = {"2022-03-31": {"수출": 1.0}, "2022-06-30": {"수출": 2.0}, "2021-12-31": {"매출": 9.0}}
        semi = {"2021-12-31": 5.0, "2022-03-31": 6.0, "2022-09-30": 7.0}
        disp = {"2022-03-31": 8.0, "2022-09-30": 9.0}
        got = export_stack_series(sns, semi, disp)
        # 회사 수출 공시 시작 전 관세청 분기는 빼고, 회사 공시가 아직 없는 최근 분기는 남긴다.
        self.assertEqual(got["에스앤에스텍 수출"], [["2022-03-31", 1.0], ["2022-06-30", 2.0]])
        self.assertEqual(got["전국 반도체용"], [["2022-03-31", 6.0], ["2022-09-30", 7.0]])
        self.assertEqual(got["전국 디스플레이용"], [["2022-03-31", 8.0], ["2022-09-30", 9.0]])


class PublishedCard(unittest.TestCase):
    def test_parts_add_up_to_existing_national_series(self):
        stack = load("snstech_export_stack")["series"]
        total = dict(load("snstech_vs_national")["series"]["전국 블랭크마스크 수출"])
        semi, disp = dict(stack["전국 반도체용"]), dict(stack["전국 디스플레이용"])
        checked = 0
        for quarter, value in total.items():
            self.assertAlmostEqual(semi[quarter] + disp[quarter], value, delta=0.5, msg=quarter)
            checked += 1
        self.assertGreaterEqual(checked, 18)

    def test_company_line_matches_existing_card(self):
        stack = dict(load("snstech_export_stack")["series"]["에스앤에스텍 수출"])
        existing = dict(load("snstech_vs_national")["series"]["에스앤에스텍 수출"])
        for quarter, value in existing.items():
            self.assertEqual(stack[quarter], value, quarter)

    def test_card_is_listed_in_blank_mask_tab(self):
        catalog = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
        semicon = next(i for i in catalog["industries"] if i["id"] == "semicon")
        section = next(s for s in semicon["sections"] if "snstech_export_stack" in s["indicators"])
        self.assertEqual(section["tab"], "snstech")


if __name__ == "__main__":
    unittest.main()

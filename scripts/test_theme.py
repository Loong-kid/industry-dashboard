# -*- coding: utf-8 -*-
"""디자인 테마가 마지막에 덮이도록 불러오는 순서와 기본 규칙을 지키는지 시험한다 (AGENTS.md 디자인 규칙)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-⛿✀-➿]")


class ThemeTest(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_theme_is_last_stylesheet(self):
        sheets = re.findall(r'<link rel="stylesheet" href="([^"]+)"', self.html)
        self.assertEqual(sheets[-1], "assets/theme-mercury.css", "새 CSS는 theme-mercury.css 위에 넣는다")
        self.assertTrue(any("pretendard" in s for s in sheets))

    def test_chart_font_runs_before_app(self):
        self.assertLess(self.html.index("chart.umd.min.js"), self.html.index("assets/theme-mercury.js"))
        self.assertLess(self.html.index("assets/theme-mercury.js"), self.html.index("assets/app.js"))

    def test_page_shell_has_no_emoji(self):
        body = self.html[self.html.index("<body"):]
        self.assertEqual(EMOJI.findall(body), [], "버튼·제목에는 이모지 대신 SVG")

    def test_theme_defines_status_tokens(self):
        css = (ROOT / "assets/theme-mercury.css").read_text(encoding="utf-8")
        for token in ("--ok:", "--err:", "--up:", "--down:", "--accent:", "--pill:"):
            self.assertIn(token, css)


if __name__ == "__main__":
    unittest.main()

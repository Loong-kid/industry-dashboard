"""data/darpa/budget.json 검증 — PDF 없이 결과 파일만 본다(예산서는 scripts/build_darpa_budget.py 로 다시 만든다)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((ROOT / 'data/darpa/budget.json').read_text(encoding='utf-8'))

# 예산서 R-1 총액(PB 요청 연도, 백만 달러). 집계가 원문 총액에서 벗어나면 파싱이 깨진 것이다.
OFFICIAL_REQUEST = {'2016': 2972.7, '2020': 3556.2, '2024': 4388.4, '2027': 5039.4}


class DarpaBudgetTests(unittest.TestCase):
    def test_totals_match_the_books(self):
        for fy, total in OFFICIAL_REQUEST.items():
            with self.subTest(fy=fy):
                self.assertAlmostEqual(DOC['totals']['request'][fy], total, delta=0.5)

    def test_sectors_add_up_to_the_total_every_year(self):
        for basis in ('request', 'actual'):
            for fy, total in DOC['totals'][basis].items():
                with self.subTest(basis=basis, fy=fy):
                    self.assertAlmostEqual(sum(s[basis][fy] for s in DOC['sectors']), total, delta=0.05)

    def test_programs_add_up_to_the_sectors(self):
        for s in DOC['sectors']:
            mine = [p for p in DOC['programs'] if p['sector'] == s['id']]
            for fy, v in s['request'].items():
                with self.subTest(sector=s['id'], fy=fy):
                    self.assertAlmostEqual(sum(p['request'].get(fy, 0) for p in mine), v, delta=0.05)

    def test_every_program_has_a_known_sector_and_valid_years(self):
        sectors = {s['id'] for s in DOC['sectors']}
        years = set(map(int, DOC['years']['request'])) | set(map(int, DOC['years']['actual']))
        for p in DOC['programs']:
            with self.subTest(title=p['title']):
                self.assertIn(p['sector'], sectors)
                self.assertTrue(p['title'])
                self.assertTrue(set(map(int, p['request'])) <= years)
                if p['new_fy'] is not None:
                    self.assertGreaterEqual(p['new_fy'], min(map(int, DOC['years']['request'])))

    def test_known_programs_land_in_the_right_sector(self):
        expect = {'Quantum Benchmarking Initiative (QBI)': 'quantum', 'Tactical Boost Glide': 'aero',
                  'Next Generation Microelectronics Manufacturing (NGMM)': 'micro', 'Pandemic Prevention': 'bio',
                  'Artificial Intelligence Cyber Challenge (AIxCC)': 'ai', 'Otter': 'space'}
        for title, sector in expect.items():
            with self.subTest(title=title):
                hits = [p['sector'] for p in DOC['programs'] if p['title'].startswith(title)]
                self.assertTrue(hits)
                self.assertEqual(hits[0], sector)

    def test_darpa_tab_is_wired(self):
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        self.assertTrue(any(i['id'] == 'darpa' for i in catalog['industries']))
        self.assertIn('import("./darpa.js")', (ROOT / 'assets/app.js').read_text(encoding='utf-8'))
        self.assertIn('assets/darpa.css', (ROOT / 'index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

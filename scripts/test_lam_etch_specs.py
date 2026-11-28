import json
import unittest

from build_lam_etch_specs import GROUPS, OUT, ROOT, build


class LamEtchSpecsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build()
        cls.rows = {r['id']: {k: v['value'] for k, v in r['reviews'].items()} for r in cls.doc['rows']}

    def test_generated_file_matches_builder(self):
        self.assertEqual(self.doc, json.loads(OUT.read_text(encoding='utf-8')))

    def test_every_value_cites_an_official_lam_page(self):
        columns = {c['id'] for c in self.doc['columns']}
        for view in self.doc['views']:
            self.assertTrue(set(view['keys']) <= columns)
        for source in self.doc['sources'].values():
            self.assertRegex(source['url'], r'^https://(www|newsroom)\.lamresearch\.com/')
        for row in self.doc['rows']:
            self.assertIn(row['group'], GROUPS)
            self.assertIsNone(row['sheet_row'])
            for key in ('method', 'apps', 'page'):
                self.assertIn(key, row['reviews'], (row['id'], key))
            for key, review in row['reviews'].items():
                self.assertIn(key, columns)
                self.assertIn(review['source'], self.doc['sources'])
                # Release-only facts must say so; page facts must point at the product page.
                self.assertEqual(review['note'].startswith('Lam 보도자료'), review['source'].startswith('r_'), (row['id'], key))

    def test_launch_dates_are_sortable(self):
        for row_id, row in self.rows.items():
            if 'launched' in row:
                self.assertRegex(row['launched'], r'^\d{4}(-\d{2}-\d{2})?$', row_id)

    def test_key_figures(self):
        self.assertEqual(self.rows['akara']['launched'], '2025-02-19')
        self.assertIn('100배', self.rows['akara']['figures'])
        self.assertIn('10 µm', self.rows['cryo-3']['figures'])
        self.assertIn('2.5배', self.rows['cryo-3']['figures'])
        self.assertIn('50%', self.rows['sense-i']['figures'])
        self.assertEqual(self.rows['vantex']['launched'], '2021-01-27')
        self.assertEqual(len(self.rows), 14)
        self.assertEqual({r['group'] for r in self.doc['rows']}, set(GROUPS))

    def test_lam_rows_live_in_the_cross_maker_etch_table(self):
        # 2026-11-28: the Lam-only card was folded into 전공정 세부 > 식각 (build_process_etch_specs reuses these rows).
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        semicon = next(i for i in catalog['industries'] if i['id'] == 'semicon')
        self.assertFalse([s for s in semicon['sections'] if s['indicators'] == ['lam_etch_specs']])
        process = json.loads((ROOT / 'data/semicon/process_etch_specs.json').read_text(encoding='utf-8'))
        self.assertEqual({r['id'] for r in process['rows'] if r['company'] == 'Lam Research'}, {'lam-' + r['id'] for r in self.doc['rows']})


if __name__ == '__main__':
    unittest.main()

import json
import unittest

from build_amat_dep_specs import GROUPS, OUT, ROOT, SOURCES, build


class AmatDepSpecsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build()
        cls.rows = {r['id']: {k: v['value'] for k, v in r['reviews'].items()} for r in cls.doc['rows']}

    def test_generated_file_matches_builder(self):
        self.assertEqual(self.doc, json.loads(OUT.read_text(encoding='utf-8')))

    def test_every_value_cites_an_applied_press_release(self):
        columns = {c['id'] for c in self.doc['columns']}
        for view in self.doc['views']:
            self.assertTrue(set(view['keys']) <= columns)
        for sid, source in self.doc['sources'].items():
            self.assertTrue(source['title'].startswith('AMAT 보도자료 '), sid)
            self.assertRegex(source['url'], r'^https://(www\.nasdaq\.com/press-release/|finance\.yahoo\.com/news/|www\.theglobeandmail\.com/investing/markets/stocks/AMAT/pressreleases/)')
        for row in self.doc['rows']:
            self.assertIn(row['group'], GROUPS)
            self.assertIsNone(row['sheet_row'])
            for key in ('method', 'launched', 'figures', 'apps', 'tech', 'page'):
                self.assertIn(key, row['reviews'], (row['id'], key))
            for key, review in row['reviews'].items():
                self.assertIn(key, columns)
                self.assertIn(review['source'], self.doc['sources'])
            # The launch date is the date of the release the row cites.
            release = row['reviews']['page']['source']
            self.assertIn(row['reviews']['launched']['value'], SOURCES[release][0], row['id'])

    def test_launch_dates_are_sortable(self):
        for row_id, row in self.rows.items():
            self.assertRegex(row['launched'], r'^\d{4}-\d{2}-\d{2}$', row_id)

    def test_key_figures(self):
        self.assertIn('15%', self.rows['spectral-mo']['figures'])
        self.assertIn('Volta Selective Tungsten', self.rows['spectral-mo']['figures'])
        self.assertIn('50%', self.rows['xtera-epi']['figures'])
        self.assertIn('40%', self.rows['xtera-epi']['figures'])
        self.assertIn('25%', self.rows['volta-ru']['figures'])
        self.assertIn('50%', self.rows['cubs-ims']['figures'])
        self.assertIn('20:1', self.rows['ventura2']['figures'])
        self.assertEqual(self.rows['trillium-ald']['launched'], '2026-04-08')
        self.assertEqual(len(self.rows), 18)
        self.assertEqual({r['group'] for r in self.doc['rows']}, set(GROUPS))

    def test_catalog_places_table_in_deposition_process_tab(self):
        # 2026-11-28: moved from 전공정 (financials) to 전공정 세부 > 증착.
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        semicon = next(i for i in catalog['industries'] if i['id'] == 'semicon')
        section = next(s for s in semicon['sections'] if s['indicators'] == ['amat_dep_specs'])
        self.assertEqual((section['tab'], section['table_kind'], section['type']), ('process_deposition', 'gpu_specs', 'table'))


if __name__ == '__main__':
    unittest.main()

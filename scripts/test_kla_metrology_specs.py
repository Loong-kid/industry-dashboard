import json
import unittest

from build_kla_metrology_specs import GROUPS, OUT, ROOT, build


class KlaMetrologySpecsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build()
        cls.rows = {r['id']: {k: v['value'] for k, v in r['reviews'].items()} for r in cls.doc['rows']}

    def test_generated_file_matches_builder(self):
        self.assertEqual(self.doc, json.loads(OUT.read_text(encoding='utf-8')))

    def test_every_value_cites_an_official_kla_source(self):
        columns = {c['id'] for c in self.doc['columns']}
        for view in self.doc['views']:
            self.assertTrue(set(view['keys']) <= columns)
        for sid, source in self.doc['sources'].items():
            self.assertRegex(source['url'], r'^https://(www|ir)\.kla\.com/', sid)
            if sid.startswith('r'):
                self.assertIn('ir.kla.com/news-events/press-releases/detail/', source['url'])
                self.assertRegex(source['title'], r'보도자료 \d{4}-\d{2}-\d{2}')
            if sid.startswith('b'):
                self.assertTrue(source['url'].endswith('.pdf'))
        for row in self.doc['rows']:
            self.assertIn(row['group'], GROUPS)
            self.assertIsNone(row['sheet_row'])
            for key in ('measures', 'method', 'figures', 'lineup', 'page'):
                self.assertIn(key, row['reviews'], (row['id'], key))
            for key, review in row['reviews'].items():
                self.assertIn(key, columns)
                self.assertIn(review['source'], self.doc['sources'])
                # The note names the kind of source the value was read from.
                if key != 'name':
                    expected = {'p': 'KLA 공식 제품 페이지 기재', 'b': 'KLA 제품 소개서 기재', 'r': 'KLA 보도자료 기재'}[review['source'][0]]
                    self.assertEqual(review['note'], expected, (row['id'], key))

    def test_launch_dates_match_their_release(self):
        for row in self.doc['rows']:
            launched = row['reviews'].get('launched')
            if launched:
                self.assertRegex(launched['value'], r'^\d{4}-\d{2}-\d{2}$', row['id'])
                self.assertIn(launched['value'], self.doc['sources'][launched['source']]['title'], row['id'])

    def test_key_figures(self):
        self.assertIn('1000 µm', self.rows['pwg']['figures'])
        self.assertIn('40 µm', self.rows['pwg']['figures'])
        self.assertIn('100:1', self.rows['axion']['figures'])
        self.assertIn('1 nm', self.rows['atl']['figures'])
        self.assertIn('500 nm', self.rows['microrsp']['figures'])
        self.assertEqual(self.rows['axion']['launched'], '2022-12-06')
        self.assertEqual(len(self.rows), 16)
        self.assertEqual({r['group'] for r in self.doc['rows']}, set(GROUPS))

    def test_catalog_places_table_under_kla_in_inspection_tab(self):
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        semicon = next(i for i in catalog['industries'] if i['id'] == 'semicon')
        section = next(s for s in semicon['sections'] if s['indicators'] == ['kla_metrology_specs'])
        self.assertEqual((section['tab'], section['table_kind'], section['type']), ('equipment_inspection', 'gpu_specs', 'table'))
        titles = [s['title'] for s in semicon['sections'] if s['tab'] == 'equipment_inspection']
        self.assertEqual(titles.index(section['title']), titles.index('KLA · KLAC · 실적') + 1)


if __name__ == '__main__':
    unittest.main()

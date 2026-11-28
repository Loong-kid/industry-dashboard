import json
import unittest

from build_asml_litho_specs import GROUPS, OUT, ROOT, build


class ASMLLithoSpecsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build()

    def test_generated_file_matches_builder(self):
        self.assertEqual(self.doc, json.loads(OUT.read_text(encoding='utf-8')))

    def test_every_value_cites_its_official_asml_page(self):
        columns = {c['id'] for c in self.doc['columns']}
        for view in self.doc['views']:
            self.assertTrue(set(view['keys']) <= columns)
        for row in self.doc['rows']:
            self.assertIn(row['group'], GROUPS)
            self.assertIsNone(row['sheet_row'])
            for key, review in row['reviews'].items():
                self.assertIn(key, columns)
                source = self.doc['sources'][review['source']]
                self.assertTrue(source['url'].startswith('https://www.asml.com/en/products/'))
                self.assertEqual(review['source'], row['id'])
            for key in ('light', 'na', 'resolution', 'throughput', 'page'):
                self.assertIn(key, row['reviews'], (row['id'], key))

    def test_key_figures(self):
        rows = {r['id']: {k: v['value'] for k, v in r['reviews'].items()} for r in self.doc['rows']}
        self.assertEqual((rows['exe-5200b']['na'], rows['exe-5200b']['throughput'], rows['exe-5200b']['dose']), ('0.55', '≥ 175', '50 mJ/cm²'))
        self.assertEqual((rows['nxe-3800e']['resolution'], rows['nxe-3800e']['throughput']), ('13 nm', '≥ 220'))
        self.assertEqual(rows['nxt-2150i']['throughput'], '≥ 310')
        self.assertIn('1.4 nm', rows['nxe-3400c']['overlay'])
        # XT:260's page shows XT:400M's overlay in a related-content card; it must not be copied over.
        self.assertEqual(rows['xt-260']['overlay'], '수치 미기재')
        self.assertEqual(len(rows), 19)
        self.assertEqual(sum(r['group'].startswith('EUV') for r in self.doc['rows']), 5)

    def test_catalog_places_table_in_photo_process_tab(self):
        # 2026-11-28: spec tables moved from 전공정 (financials) to 전공정 세부 > 포토 (technical comparison).
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        semicon = next(i for i in catalog['industries'] if i['id'] == 'semicon')
        section = next(s for s in semicon['sections'] if s['indicators'] == ['asml_litho_specs'])
        self.assertEqual((section['tab'], section['table_kind'], section['type']), ('process_photo', 'gpu_specs', 'table'))
        tab = next(t for t in semicon['tabs'] if t['id'] == 'process_photo')
        self.assertEqual(tab['parent_tab'], 'process_detail')


if __name__ == '__main__':
    unittest.main()

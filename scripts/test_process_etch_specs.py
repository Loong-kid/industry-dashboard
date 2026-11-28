import json
import re
import unittest

import build_lam_etch_specs as lam
from build_process_etch_specs import COMPANIES, GROUPS, OUT, ROOT, build


class ProcessEtchSpecsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build()
        cls.rows = {r['id']: {k: v['value'] for k, v in r['reviews'].items()} for r in cls.doc['rows']}

    def test_generated_file_matches_builder(self):
        self.assertEqual(self.doc, json.loads(OUT.read_text(encoding='utf-8')))

    def test_every_value_cites_a_maker_source(self):
        columns = {c['id'] for c in self.doc['columns']}
        for view in self.doc['views']:
            self.assertTrue(set(view['keys']) <= columns)
        for sid, source in self.doc['sources'].items():
            self.assertTrue(source['url'].startswith('https://'), sid)
            self.assertIn(source['kind'], ('page', 'release', 'history', 'user'))
        for row in self.doc['rows']:
            self.assertIn(row['group'], GROUPS)
            self.assertIn(row['company'], COMPANIES)
            self.assertEqual(row['reviews']['country']['value'], COMPANIES[row['company']])
            for key in ('method', 'status', 'figures', 'adoption', 'apps', 'page'):
                self.assertIn(key, row['reviews'], (row['id'], key))
            for key, review in row['reviews'].items():
                self.assertIn(key, columns)
                self.assertIn(review['source'], self.doc['sources'], (row['id'], key))

    def test_launch_dates_are_sortable(self):
        for row_id, row in self.rows.items():
            if 'launched' in row:
                self.assertRegex(row['launched'], r'^\d{4}(-\d{2}(-\d{2})?)?$', row_id)

    def test_throughput_and_price_only_from_user_sources(self):
        # Makers publish neither; any value must come from a source of kind 'user'.
        for row in self.doc['rows']:
            for key in ('throughput', 'price'):
                if key in row['reviews']:
                    self.assertEqual(self.doc['sources'][row['reviews'][key]['source']]['kind'], 'user', (row['id'], key))

    def test_covers_us_japan_china_korea_and_all_lam_rows(self):
        countries = {COMPANIES[r['company']] for r in self.doc['rows']}
        self.assertEqual(countries, {'미국', '일본', '중국', '한국'})
        self.assertEqual(len([r for r in self.doc['rows'] if r['company'] == 'Lam Research']), len(lam.PRODUCTS))
        self.assertEqual(self.doc['groups'], GROUPS)
        self.assertEqual({r['group'] for r in self.doc['rows']}, set(GROUPS))

    def test_key_facts(self):
        self.assertIn('35~50%', self.rows['amec-adrie']['figures'])
        self.assertEqual(self.rows['amec-adrie']['launched'], '2011-07')
        self.assertIn('33분', self.rows['tel-cryo']['figures'])
        self.assertEqual(self.rows['tel-tactras']['launched'], '2006')
        self.assertIn('1,000', self.rows['amat-selectra']['adoption'])
        self.assertIn('250', self.rows['amat-sym3z']['adoption'])
        self.assertEqual(self.rows['vm-leo-wh']['launched'], '2021-01')
        self.assertIn('200', self.rows['tes-cumax']['figures'])

    def test_catalog_builds_process_detail_tabs(self):
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        semicon = next(i for i in catalog['industries'] if i['id'] == 'semicon')
        tabs = {t['id']: t for t in semicon['tabs']}
        self.assertEqual(tabs['process_detail']['category'], 'equipment')
        self.assertNotIn('parent_tab', tabs['process_detail'])
        children = [t['id'] for t in semicon['tabs'] if t.get('parent_tab') == 'process_detail']
        self.assertEqual(children, ['process_photo', 'process_etch', 'process_deposition'])
        routes = [t.get('route') or t['id'] for t in semicon['tabs'] if t.get('category') == 'equipment']
        self.assertEqual(len(routes), len(set(routes)))
        kinds = {(s['tab'], s['table_kind']) for s in semicon['sections'] if s['indicators'] == ['process_etch_specs']}
        self.assertEqual(kinds, {('process_detail', 'process_matrix'), ('process_etch', 'process_matrix'), ('process_etch', 'gpu_specs')})

    def test_app_renders_child_tabs_and_matrix(self):
        app = (ROOT / 'assets/app.js').read_text(encoding='utf-8')
        self.assertIn('tab.parent_tab === parentTab.id', app)
        self.assertIn('"process_matrix" ? (await import("./process-matrix.js")).renderProcessMatrix', app)
        index = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertLess(index.index('assets/process-matrix.css'), index.index('assets/theme-mercury.css'))
        css = (ROOT / 'assets/process-matrix.css').read_text(encoding='utf-8')
        self.assertFalse(re.search(r'#[0-9a-fA-F]{3,6}\b|font-weight:\s*[6-9]00', css))


if __name__ == '__main__':
    unittest.main()

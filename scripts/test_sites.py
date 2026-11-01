import json
import unittest
from pathlib import Path

import build_sites

ROOT = Path(__file__).resolve().parent.parent


class SitesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build_sites.build()

    def test_every_site_has_a_valid_position_layer_and_status(self):
        layers = {layer['id'] for layer in self.doc['layers']}
        for site in self.doc['sites']:
            with self.subTest(site=site['id']):
                self.assertTrue(-90 <= site['lat'] <= 90 and -180 <= site['lon'] <= 180)
                self.assertIn(site['layer'], layers)
                self.assertIn(site['status'], self.doc['status_labels'])
                self.assertTrue(site['name'])

    def test_ids_are_unique(self):
        ids = [site['id'] for site in self.doc['sites']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_lng_terminals_keep_gem_scale(self):
        counts = self.doc['counts']
        self.assertGreater(counts['lng_export'], 200)
        self.assertGreater(counts['lng_import'], 400)
        self.assertTrue(all(s.get('size') is None or s['size'] > 0 for s in self.doc['sites']))

    def test_coordinate_ledger_is_well_formed(self):
        ledger = json.loads((ROOT / 'manual/site_coords.json').read_text(encoding='utf-8'))
        for sid, geo in ledger['coords'].items():
            with self.subTest(id=sid):
                self.assertTrue(-90 <= geo['lat'] <= 90 and -180 <= geo['lon'] <= 180)
                self.assertIn(geo['accuracy'], build_sites.ACCURACY_KO)
                self.assertTrue(geo['query'])

    def test_missing_coordinates_are_reported_not_guessed(self):
        drawn = {s['id'] for s in self.doc['sites']}
        for row in self.doc['missing_coords']:
            self.assertNotIn(row['id'], drawn)

    def test_user_sites_follow_the_documented_shape(self):
        data = json.loads((ROOT / 'manual/sites.json').read_text(encoding='utf-8'))
        ids = [row['id'] for row in data['sites']]
        self.assertEqual(len(ids), len(set(ids)))
        for row in data['sites']:
            with self.subTest(id=row['id']):
                self.assertRegex(row['id'], r'^[a-z0-9_]+$')
                self.assertTrue(row['name'])
                self.assertTrue(-90 <= float(row['lat']) <= 90 and -180 <= float(row['lon']) <= 180)
                self.assertIn(row.get('category', 'other'), data['categories'])
                self.assertIn(row.get('status', 'operating'), build_sites.STATUS_LABEL)

    def test_globe_tab_is_wired(self):
        catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
        self.assertTrue(any(i['id'] == 'globe' for i in catalog['industries']))
        app = (ROOT / 'assets/app.js').read_text(encoding='utf-8')
        self.assertIn('import("./globe.js")', app)
        self.assertIn('assets/globe.css', (ROOT / 'index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

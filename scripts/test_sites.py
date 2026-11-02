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

    def test_place_labels_are_korean_and_on_the_globe(self):
        places = json.loads((ROOT / 'data/sites/places.json').read_text(encoding='utf-8'))
        self.assertGreater(len(places['countries']), 150)
        self.assertGreater(len(places['cities']), 500)
        self.assertTrue(places['seas'])
        for kind in ('countries', 'cities', 'seas'):
            for row in places[kind]:
                with self.subTest(kind=kind, name=row['n']):
                    self.assertRegex(row['n'], r'[가-힣]')
                    self.assertTrue(-90 <= row['lat'] <= 90 and -180 <= row['lon'] <= 180)
        names = {row['n'] for row in places['countries']}
        self.assertTrue({'한국', '중국', '대만', '북한'} <= names)
        self.assertIn('places.json', (ROOT / 'assets/globe.js').read_text(encoding='utf-8'))

    def test_korean_data_centers_are_on_the_map(self):
        doc = json.loads((ROOT / 'data/sites/sites.json').read_text(encoding='utf-8'))
        confirmed = [s for s in doc['sites'] if s['layer'] == 'dc_kr']
        candidates = [s for s in doc['sites'] if s['layer'] == 'dc_kr_candidate']
        self.assertGreaterEqual(len(confirmed), 100)
        self.assertTrue(candidates)
        for site in confirmed + candidates:
            with self.subTest(site=site['id']):
                self.assertTrue(33 < site['lat'] < 39 and 124 < site['lon'] < 132, '한반도 안')
                self.assertEqual(site['size_unit'], 'MW')
                self.assertIn(site['status'], ('operating', 'construction', 'planned'))
        self.assertTrue(any(s['size'] for s in confirmed), '수전용량이 막대 높이가 된다')
        globe = (ROOT / 'assets/globe.js').read_text(encoding='utf-8')
        self.assertIn('"dc_kr", "user"', globe, '확정 레이어는 기본으로 켠다')
        self.assertNotIn('"dc_kr_candidate", "user"', globe, '후보는 기본으로 끈다')
        self.assertIn('막대 높이', globe)

    def test_dc_status_follows_confirmed_steps_only(self):
        from build_sites import dc_status
        ok = lambda d: {'kind': 'confirmed', 'date': d}
        self.assertEqual(dc_status({'completion': ok('2020-01-01')}, '2026-11-03'), 'operating')
        self.assertEqual(dc_status({'completion': {'kind': 'planned', 'date': '2027-01-01'}, 'start': ok('2025-01-01')}, '2026-11-03'), 'construction')
        self.assertEqual(dc_status({'permit': ok('2026-01-01')}, '2026-11-03'), 'planned')
        self.assertEqual(dc_status({'completion': {'kind': 'uncertain', 'text': '2027.4Q', 'year': 2027}, 'permit': ok('2025-01-01')}, '2026-11-03'), 'planned')

    def test_korea_admin_boundaries(self):
        for name, count in (('korea_sido.json', 17), ('korea_sigungu.json', 250)):
            doc = json.loads((ROOT / 'data/sites' / name).read_text(encoding='utf-8'))
            self.assertEqual(len(doc['labels']), count)
            self.assertEqual(sum(len(o['geometries']) for o in doc['topology']['objects'].values()), count)
            for label in doc['labels']:
                with self.subTest(name=label['n']):
                    self.assertRegex(label['n'], r'[가-힣]')
                    self.assertTrue(33 < label['lat'] < 39 and 124 < label['lon'] < 132)
        sido = json.loads((ROOT / 'data/sites/korea_sido.json').read_text(encoding='utf-8'))['labels']
        self.assertTrue({'강원특별자치도', '전북특별자치도'} <= {row['full'] for row in sido})
        self.assertTrue({'경기', '충북'} <= {row['n'] for row in sido})
        sigungu = {row['n'] for row in json.loads((ROOT / 'data/sites/korea_sigungu.json').read_text(encoding='utf-8'))['labels']}
        self.assertIn('분당구', sigungu)
        self.assertNotIn('성남시분당구', sigungu)


if __name__ == '__main__':
    unittest.main()

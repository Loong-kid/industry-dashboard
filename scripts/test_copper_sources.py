import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_copper_snapshot as snapshot
import fetch_copper_warrants as warrants


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 10, 1)
        self.payload = {'schema_version': 1, 'license': 'CC BY 4.0', 'signals': [
            {'key': 'comex_copper_total', 'unit': 'short tons', 'value': 774208, 'as_of': '2026-09-28'},
            {'key': 'comex_registered_copper', 'unit': 'short tons', 'value': 470317, 'as_of': '2026-09-28'},
            {'key': 'lme_copper', 'unit': 'mt', 'value': 250475, 'as_of': '2026-09-29'}]}

    def test_conversion_and_components(self):
        comex, lme = snapshot.build_documents(self.payload, self.today)
        total = comex['series'][snapshot.TOTAL][0][1]
        registered = comex['series'][snapshot.REGISTERED][0][1]
        eligible = comex['series'][snapshot.ELIGIBLE][0][1]
        self.assertAlmostEqual(total, 774208 * .90718474, places=3)
        self.assertAlmostEqual(total, registered + eligible, delta=.002)
        self.assertEqual(lme['series'][snapshot.LME], [['2026-09-29', 250475]])
        self.assertEqual(len(comex['series'][snapshot.TOTAL]), 1)

    def test_rejects_misaligned_dates_units_values_and_licence(self):
        for index, key, value in [(1, 'as_of', '2026-09-27'), (0, 'unit', 'pounds'),
                                  (0, 'value', float('nan')), (0, 'value', -1),
                                  (1, 'value', 999999), (2, 'as_of', '2026-10-02')]:
            bad = copy.deepcopy(self.payload)
            bad['signals'][index][key] = value
            with self.assertRaises(ValueError):
                snapshot.build_documents(bad, self.today)
        bad = copy.deepcopy(self.payload)
        bad['license'] = 'changed'
        with self.assertRaises(ValueError):
            snapshot.build_documents(bad, self.today)
        bad = copy.deepcopy(self.payload)
        bad['signals'].append(bad['signals'][0])
        with self.assertRaises(ValueError):
            snapshot.build_documents(bad, self.today)

    def test_history_merge_deduplicates_and_rejects_regression(self):
        doc = snapshot.build_documents(self.payload, self.today)[0]
        merged = snapshot.merge_history(copy.deepcopy(doc), copy.deepcopy(doc))
        self.assertEqual(len(merged['series'][snapshot.TOTAL]), 1)
        newer = copy.deepcopy(doc)
        newer['updated'] = '2026-09-29'
        for name, points in newer['series'].items():
            points[0][0] = '2026-09-29'
        merged = snapshot.merge_history(doc, newer)
        self.assertEqual(len(merged['series'][snapshot.TOTAL]), 2)
        with self.assertRaises(ValueError):
            snapshot.merge_history(merged, doc)


class WarrantTests(unittest.TestCase):
    def test_scope_unit_date_and_total(self):
        rows = [['2026-09-30 2026年 第181期'], ['地区', '仓库', '期货', '增减'],
                ['铜', '单位：吨'], ['合计', '999', '1'],
                ['保税商品总计', '0', '0'], ['完税商品总计', '10011', '-721'],
                ['总计', '10011', '-721'], ['铝', '单位：吨'], ['总计', '80000', '200']]
        html = '<table>' + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows) + '</table>'
        self.assertEqual(warrants.parse_report(html, '20260930'), (10011, -721))
        for bad in [html.replace('单位：吨', '单位：千克'), html.replace('2026-09-30', '2026-09-29'),
                    html.replace('10011', 'NaN'), html.replace('期货', '库存')]:
            with self.assertRaises(ValueError):
                warrants.parse_report(bad, '20260930')

    def test_failed_fetch_preserves_existing_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'card.json'
            before = json.dumps({'series': {warrants.NAME: [['2026-09-30', 10011]]}, 'fetched': '2026-09-30'})
            path.write_text(before, encoding='utf-8')
            with patch.object(warrants, 'OUTPUT', path), patch.object(warrants.time, 'sleep'), patch.object(warrants.requests, 'Session') as session:
                session.return_value.get.return_value.status_code = 404
                with self.assertRaises(RuntimeError):
                    warrants.run()
            self.assertEqual(path.read_text(encoding='utf-8'), before)


if __name__ == '__main__':
    unittest.main()

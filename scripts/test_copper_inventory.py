import copy
import unittest
from unittest.mock import patch
import tempfile
import json
from pathlib import Path

import fetch_copper_inventory as copper


class CopperTests(unittest.TestCase):
    def setUp(self):
        self.report = {'report_date': '20250926', 'o_tradingday': '20250926', 'o_cursor': [
            {'VARNAME': '铜$$COPPER', 'WHABBRNAME': '总计$$Total', 'WGHTUNIT': '2',
             'SPOTWGHTS': 98779, 'PRESPOTWGHTS': 105814, 'SPOTCHANGE': -7035,
             'WHSTOCKS': 972043, 'WRTWGHTS': 26557},
            {'VARNAME': '铜$$COPPER', 'WHABBRNAME': '合计$$Subtotal', 'SPOTWGHTS': 63753},
            {'VARNAME': '铜$$COPPER', 'WHABBRNAME': '保税商品总计$$Total (Bonded)', 'SPOTWGHTS': 18}]}

    def test_uses_stock_not_capacity_or_warrants_and_excludes_subtotals(self):
        self.assertEqual(copper.parse_report(self.report, '20250926'), (98779, -7035))

    def test_rejects_wrong_date_unit_missing_and_bad_values(self):
        with self.assertRaises(ValueError):
            copper.parse_report(self.report, '20250925')
        for key, value in [('WGHTUNIT', '1'), ('SPOTWGHTS', -1), ('SPOTWGHTS', float('nan')), ('SPOTCHANGE', 0)]:
            doc = copy.deepcopy(self.report)
            doc['o_cursor'][0][key] = value
            with self.assertRaises(ValueError):
                copper.parse_report(doc, '20250926')
        self.report['o_cursor'] = []
        with self.assertRaises(ValueError):
            copper.parse_report(self.report, '20250926')

    def test_missing_reports_preserve_file_and_fetch_date(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            original = json.dumps({'series': {copper.NAME: [['2025-09-26', 98779]]}, 'fetched': '2025-09-26'})
            path.write_text(original, encoding='utf-8')
            with patch.object(copper, 'OUTPUT', path), patch.object(copper.time, 'sleep'), patch.object(copper.requests, 'Session') as session:
                session.return_value.get.return_value.status_code = 404
                with self.assertRaises(RuntimeError):
                    copper.run()
            self.assertEqual(path.read_text(encoding='utf-8'), original)


if __name__ == '__main__':
    unittest.main()

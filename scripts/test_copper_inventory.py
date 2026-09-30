import copy
import unittest
from unittest.mock import patch
import tempfile
import json
from pathlib import Path

import fetch_copper_inventory as copper


class CopperTests(unittest.TestCase):
    def test_html_copper_scope_headers_and_date(self):
        # Official 2026-09-24 copper total; adjacent metal must not be included.
        rows = [
            ['2026-09-24 2026年 第(37)期,总第1404期'],
            ['地区', '仓库', '上周库存', '本周库存', '库存增减', '可用库容量'],
            ['小计', '期货', '小计', '期货', '小计', '期货', '上周', '本周', '增减'],
            ['铜', '单位：吨'],
            ['完税商品总计', '56055', '26655', '47129', '16620', '-8926', '-10035', '908496', '923376', '14880'],
            ['总计', '56073', '26655', '47147', '16620', '-8926', '-10035', '968496', '983376', '14880'],
            ['铝', '单位：吨'],
            ['总计', '1', '1', '1', '1', '0', '0', '1', '1', '0']]
        html = '<table>' + ''.join('<tr>' + ''.join(f'<td><div>{c}</div></td>' for c in row) + '</tr>' for row in rows) + '</table>'
        self.assertEqual(copper.parse_html_report(html, '20260924'), (47147, -8926))
        for invalid in [html.replace('2026-09-24', '2026-09-23'), html.replace('单位：吨', '单位：千克'), html.replace('本周库存', 'changed'), html.replace('47147', '47148')]:
            with self.assertRaises(ValueError):
                copper.parse_html_report(invalid, '20260924')

    def test_new_html_precedes_json_and_legacy_fallback(self):
        with patch.object(copper, 'parse_html_report', return_value=(1, 0)):
            from unittest.mock import Mock
            session = Mock()
            session.get.return_value.status_code = 200
            self.assertEqual(copper.fetch_report(session, '20260924')[:2], (1, 0))
            self.assertEqual(session.get.call_count, 1)
            session.get.reset_mock()
            session.get.side_effect = [Mock(status_code=404), Mock(status_code=200, json=lambda: self.report)]
            self.assertEqual(copper.fetch_report(session, '20250926')[:2], (98779, -7035))
            self.assertEqual(session.get.call_count, 2)

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

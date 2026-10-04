import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import common
import fetch_all
from fetchers import kcla, stockq


class ShippingTests(unittest.TestCase):
    def test_kcla_dates_and_values_cannot_shift_when_a_cell_is_missing(self):
        html = '<table summary="SCFI"><tr><td rowspan="2">지수</td><td>2026.09.24</td><td>2026.09.30</td></tr><tr><td>3,686.62</td><td>3662.3</td></tr></table>'
        self.assertEqual(kcla.parse_table(html, 'SCFI'), [('2026-09-24', 3686.62), ('2026-09-30', 3662.3)])
        for wrong in [html.replace('<td>3662.3</td>', ''), html.replace('3662.3', '-'), html.replace('2026.09.30', 'unavailable')]:
            with self.assertRaises(ValueError):
                kcla.parse_table(wrong, 'SCFI')

    def test_nlic_fallback_keeps_series_columns_aligned_and_existing_newer_history(self):
        html = '<li class="con_list_2">SCFI</li><li class="con_list_2">CCFI</li><div class="box W_m_1000px">' + ''.join(f'<ul><li>{value}</li></ul>' for value in ['2026-09-24', '2026-09-18', '3686.62', '3750', '1917.68', '1897.15']) + '</div>'
        self.assertEqual(kcla.parse_nlic(html, 'scfi')[0], ('2026-09-24', 3686.62))
        self.assertEqual(kcla.parse_nlic(html, 'ccfi')[0], ('2026-09-24', 1917.68))
        error_response = Mock(); error_response.raise_for_status.side_effect = kcla.requests.HTTPError('404')
        fallback_response = Mock(); fallback_response.content = html
        previous = {'id': 'scfi', 'series': {'SCFI': [['2026-09-30', 3662.3]]}}
        with patch.object(kcla.requests, 'get', side_effect=[error_response, fallback_response]), patch.object(kcla, 'load_indicator', return_value=previous), patch.object(kcla, 'save_indicator') as save:
            kcla.fetch_one('scfi', *kcla.PAGES['scfi'])
        self.assertEqual(previous['series']['SCFI'][-1], ['2026-09-30', 3662.3])
        self.assertEqual(previous['latest_source_date'], '2026-09-24')
        self.assertEqual(previous['source_url'], kcla.NLIC_URL)
        save.assert_called_once_with('shipping', previous, data_date=True)
        with self.assertRaises(ValueError):
            kcla.parse_nlic(html.replace('<ul><li>1897.15</li></ul>', ''), 'ccfi')

    def test_stockq_public_display_values_and_full_dates_bind_correctly(self):
        # Captured from the site's public renderer: header and history values both = 3148.
        header = 'MTQ4MzA3NjQ2MnwzMjh8OC4wfDB8ODUyfDMxNA=='
        history = 'Mzg1MjYxNDk4fDB8MzE0OC58NzQxfDB8NDU4'
        self.assertEqual(float(stockq.render_value(header)), 3148)
        self.assertEqual(float(stockq.render_value(history)), 3148)
        html = f'<div class="stockq-desktop-quote"><div class="stockq-desktop-quote__price"><span data-sq="{header}"></span></div><p class="stockq-desktop-quote__time">local: 10/02</p></div><table class="indexpagetable"><tr><td>2026/10/02</td><td><span data-sq="{history}"></span></td><td>0.25%</td><td>2026/10/01</td><td>3140.00</td><td>-0.2%</td></tr></table>'
        with patch.object(stockq, 'date', wraps=date) as clock:
            clock.today.return_value = date(2026, 10, 4)
            self.assertEqual(stockq.parse_page(html), [('2026-10-01', 3140), ('2026-10-02', 3148)])
            clock.today.return_value = date(2027, 1, 2)
            self.assertEqual(stockq.infer_year(12, 31), 2026)
            self.assertEqual(stockq.infer_year(1, 2), 2027)
        for malformed in ['bad!', 'MTIzfDE=']:
            with self.assertRaises(ValueError):
                stockq.render_value(malformed)
        with self.assertRaises(ValueError):
            stockq.parse_page('<table class="indexpagetable"><tr><td>2026/10/02</td><td>-</td></tr></table>')

    def test_failure_remains_visible_and_does_not_refresh_success_date(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(common, 'DATA_DIR', Path(temp)), patch.object(common, 'ROOT', Path(temp)):
            path = Path(temp) / 'shipping' / 'scfi.json'; path.parent.mkdir()
            doc = {'id': 'scfi', 'updated': '2026-07-10', 'fetched': '2026-07-14', 'series': {'SCFI': [['2026-07-10', 3184.82]]}}
            path.write_text(json.dumps(doc), encoding='utf-8')
            common.record_fetch_failure('shipping', 'scfi', ValueError('broken'))
            failed = common.load_indicator('shipping', 'scfi')
            self.assertEqual(failed['updated'], doc['updated'])
            self.assertEqual(failed['fetched'], doc['fetched'])
            self.assertFalse(failed['collection_status']['ok'])
            failed['series']['SCFI'].append(['2026-09-30', 3662.3])
            common.save_indicator('shipping', failed, data_date=True)
            self.assertEqual(failed['updated'], '2026-09-30')
            self.assertNotIn('collection_status', failed)

    def test_one_index_failure_does_not_skip_other_indices(self):
        bad, good = Mock(side_effect=ValueError('404')), Mock()
        with patch.object(fetch_all, 'JOBS', [('bad CCFI', bad, ['ccfi']), ('good SCFI', good, ['scfi'])]), patch.object(fetch_all, 'record_fetch_failure') as record, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            fetch_all.main()
        good.assert_called_once()
        record.assert_called_once()
        self.assertEqual(record.call_args.args[:2], ('shipping', 'ccfi'))


if __name__ == '__main__':
    unittest.main()

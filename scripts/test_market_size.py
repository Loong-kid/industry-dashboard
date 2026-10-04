import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fetch_market_size as market


SP_HTML = '''<table><tr><td>PERIOD</td><td>MARKET</td></tr>
<tr><td></td><td>VALUE</td></tr>
<tr><td>12 Mo Jun,'25</td><td>$999,999</td></tr>
<tr><td>2024</td><td>$49,805</td></tr>
<tr><td>6/28/2024</td><td>$45,843</td></tr>
<tr><td>6/30/2025 Prelim.</td><td>$52,501</td></tr></table>
<table><tr><td>BUYBACKS</td><td>$ BILLIONS</td></tr><tr><td>2024</td><td>$942</td></tr></table>'''


class MarketSizeTests(unittest.TestCase):
    def test_sp_uses_actual_dates_and_market_value_not_rolling_period_or_buyback(self):
        annual, quarter = market.parse_sp_html(SP_HTML)
        self.assertEqual(annual, {'2024-12-31': 49805})
        self.assertEqual(quarter['2024-06-30']['value'], 45843)
        self.assertEqual(quarter['2024-06-30']['observed'], '2024-06-28')
        self.assertEqual(quarter['2025-06-30']['value'], 52501)
        self.assertTrue(quarter['2025-06-30']['preliminary'])
        self.assertEqual(len(quarter), 2)

    def test_sp_rejects_missing_table_and_unexpected_observation_dates(self):
        with self.assertRaises(ValueError):
            market.parse_sp_html('<table><tr><td>2024</td><td>$49,805</td></tr></table>')
        with self.assertRaises(ValueError):
            market.parse_sp_html(SP_HTML.replace('6/28/2024', '5/28/2024'))

    def test_pdf_excludes_percent_columns_and_chart_years(self):
        lines = ['($B)', 'NYSE', 'Nasdaq', 'Total', '(Y/Y)', 'NYSE', 'Nasdaq', 'Total']
        for year in range(2011, 2026):
            lines += [str(year), '1,000', '2,000.5', '3,000.5', str(year), '10%', '20%', '30%']
        text = '\n'.join(lines + ['Average', '2016', '2017', '2018', '2019'])
        rows = market.parse_pdf_rows(text, 3)
        self.assertEqual(len(rows), 15)
        self.assertEqual(rows[2025]['Nasdaq'], 2000.5)
        with self.assertRaises(ValueError):
            market.parse_pdf_rows(text.replace('3,000.5', '8,000.5', 1), 3)

    def test_world_bank_nulls_units_and_truncation(self):
        rows = [{'indicator': {'id': 'CM.MKT.LCAP.CD'}, 'countryiso3code': country,
                 'date': str(year), 'value': 1e12 if year != 2026 else None}
                for country in ['USA', 'WLD'] for year in range(1975, 2027)]
        values = market.parse_world_bank([{'pages': 1}, rows])
        self.assertEqual(len(values['USA']), 51)
        self.assertEqual(market.annual_points(values['USA'])[-1], ['2025-12-31', 1])
        with self.assertRaises(ValueError):
            market.parse_world_bank([{'pages': 2}, rows])
        with self.assertRaises(ValueError):
            market.parse_world_bank([{'pages': 1}, rows[:4]])

    def test_new_sp_release_revises_history_preserves_older_periods_and_adds_real_q4(self):
        url = 'https://press.spglobal.com/2026-06-01-S-P-500-Buybacks'
        archive = f'<a href="{url}">S&amp;P 500 Q1 Buybacks</a>'.encode()
        html = '''<table><tr><td>PERIOD</td><td>MARKET VALUE</td></tr>
        <tr><td>2023</td><td>$9,000</td></tr><tr><td>2024</td><td>$10,000</td></tr>
        <tr><td>12/31/2025</td><td>$12,000</td></tr><tr><td>3/31/2026</td><td>$14,000</td></tr></table>'''.encode()
        old = {'value': 5000, 'observed': '1999-12-31', 'published': '2000-03-01', 'url': url}
        revised = {'value': 11000, 'observed': '2025-12-31', 'published': '2026-03-01', 'url': url}
        with tempfile.TemporaryDirectory() as tmp, patch.object(market, 'OUT', Path(tmp) / 'out'), \
                patch.object(market, 'CACHE', Path(tmp) / 'cache'), \
                patch.object(market, 'get', side_effect=lambda address: SimpleNamespace(content=archive if address == market.SP_ARCHIVE else html)):
            market.write_json(market.CACHE / 'sp500.json', {'annual': {'1999-12-31': old},
                               'quarterly': {'1999-12-31': old, '2025-12-31': revised}})
            market.collect_sp()
            annual = json.loads((market.OUT / 'market_sp500.json').read_text(encoding='utf-8'))
            quarter = json.loads((market.OUT / 'market_sp500_q.json').read_text(encoding='utf-8'))
            self.assertEqual(annual['series']['시장규모'][0], ['1999-12-31', 5])
            self.assertEqual(annual['series']['시장규모'][-1], ['2025-12-31', 12])
            self.assertEqual(quarter['series']['시장규모'][-1], ['2026-03-31', 14])
            self.assertEqual(quarter['updated'], '2026-03-31')
            self.assertTrue(quarter['quarter_labels'])
            self.assertFalse(quarter['year_labels'])

    def test_failed_world_bank_fetch_preserves_published_data(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(market, 'OUT', Path(tmp)), \
                patch.object(market, 'get', side_effect=RuntimeError('network unavailable')):
            path = Path(tmp) / 'market_equity_us.json'
            path.write_text('existing valid published history', encoding='utf-8')
            with self.assertRaises(RuntimeError):
                market.collect_world_bank()
            self.assertEqual(path.read_text(encoding='utf-8'), 'existing valid published history')

    def test_one_source_failure_does_not_block_independent_sources(self):
        with patch.object(market, 'collect_world_bank', side_effect=RuntimeError('offline')) as wb, \
                patch.object(market, 'collect_sifma') as sifma, patch.object(market, 'collect_sp') as sp:
            wb.__name__ = 'collect_world_bank'
            with self.assertRaises(SystemExit):
                market.run()
            sifma.assert_called_once()
            sp.assert_called_once()


if __name__ == '__main__':
    unittest.main()

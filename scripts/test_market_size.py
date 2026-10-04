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
    def test_additional_world_bank_countries_keep_real_gaps_and_require_coverage(self):
        rows = [{'indicator': {'id': 'CM.MKT.LCAP.CD'}, 'countryiso3code': 'GBR',
                 'date': str(year), 'value': 1e12 if year in [2014, 2021, 2022] else None}
                for year in range(2014, 2026)]
        values = market.parse_world_bank([{'pages': 1}, rows], ['GBR'])
        self.assertEqual(list(values['GBR']), [2014, 2021, 2022])
        self.assertNotIn(2025, values['GBR'])
        with self.assertRaises(ValueError):
            market.parse_world_bank([{'pages': 1}, rows], ['GBR', 'FRA'])

    def test_ecos_market_caps_use_thousand_won_not_index_levels_or_months(self):
        row = {'STAT_CODE': '901Y014', 'ITEM_CODE1': '1040000', 'UNIT_NAME': '천원',
               'TIME': '2025', 'DATA_VALUE': '3477839534743'}
        payload = {'StatisticSearch': {'list_total_count': 1, 'row': [row]}}
        self.assertAlmostEqual(market.parse_ecos_cap(payload, '1040000')['2025'], 3477.839534743)
        for field, wrong in [('UNIT_NAME', '1980.01.04=100'), ('TIME', '202512'), ('ITEM_CODE1', '1070000')]:
            invalid = {'StatisticSearch': {'list_total_count': 1, 'row': [{**row, field: wrong}]}}
            with self.assertRaises(ValueError):
                market.parse_ecos_cap(invalid, '1040000')
        with self.assertRaises(ValueError):
            market.parse_ecos_cap({'StatisticSearch': {'list_total_count': 2, 'row': [row]}}, '1040000')

    def test_ecos_monthly_accepts_valid_months_but_rejects_index_and_invalid_month(self):
        row = {'STAT_CODE': '901Y014', 'ITEM_CODE1': '1040000', 'UNIT_NAME': '천원',
               'TIME': '202608', 'DATA_VALUE': '5620144799211'}
        payload = {'StatisticSearch': {'list_total_count': 1, 'row': [row]}}
        self.assertAlmostEqual(market.parse_ecos_cap(payload, '1040000', 'M')['202608'], 5620.144799211)
        for field, wrong in [('TIME', '202613'), ('TIME', '2026'), ('ITEM_CODE1', '1070000'), ('UNIT_NAME', '포인트')]:
            with self.assertRaises(ValueError):
                market.parse_ecos_cap({'StatisticSearch': {'list_total_count': 1, 'row': [{**row, field: wrong}]}}, '1040000', 'M')

    def test_monthly_latest_regression_keeps_all_three_published_cards(self):
        def response(url):
            parts = url.split('/')
            start, end, item = parts[-3:]
            first = int(start[:4]) * 12 + int(start[4:]) - 1
            final = int(end[:4]) * 12 + int(end[4:]) - 1
            rows = []
            for offset in range(first, final + 1):
                year, month = divmod(offset, 12)
                period = f'{year}{month + 1:02}'
                if period > '202608':
                    continue
                rows.append({'STAT_CODE': '901Y014', 'ITEM_CODE1': item, 'UNIT_NAME': '천원',
                             'TIME': period, 'DATA_VALUE': '1000000000000'})
            if not rows:
                return SimpleNamespace(json=lambda: {'RESULT': {'CODE': 'INFO-200'}})
            return SimpleNamespace(json=lambda: {'StatisticSearch': {'list_total_count': len(rows), 'row': rows}})
        with tempfile.TemporaryDirectory() as tmp, patch.object(market, 'OUT', Path(tmp)), \
                patch.object(market, 'get', side_effect=response), patch.dict(market.os.environ, {'ECOS_API_KEY': 'sample'}):
            for cid in ['market_kospi_m', 'market_kosdaq_m', 'market_equity_kr_krw_m']:
                market.write_json(Path(tmp) / f'{cid}.json', {'updated': '2026-09-30', 'keep': 'existing'})
            with self.assertRaisesRegex(ValueError, 'regressed'):
                market.collect_korea_monthly()
            for path in Path(tmp).glob('*.json'):
                self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['keep'], 'existing')

    def test_esma_requires_two_years_all_27_members_and_consistent_ratios(self):
        countries = 'FR DE NL ES SE IT IE DK BE FI LU PL AT GR PT RO HU CZ HR SI BG CY MT EE LT SK LV'.split()
        def pdf(ratio='3.7037', omit=False):
            with market.fitz.open() as book:
                for year in [2024, 2025]:
                    page = book.new_page()
                    text = f'Table 1 Market capitalisation and market capitalisation ratios of Member States ({year})\nEUR bn\n'
                    text += '\n'.join(f'{country} {1000 + i}.1234 {ratio}' for i, country in enumerate(countries[:-1] if omit else countries))
                    page.insert_text((30,30), text, fontsize=10)
                return book.tobytes()
        values = market.parse_esma_pdf(pdf())
        self.assertEqual(set(values), {'2024', '2025'})
        self.assertEqual(values['2025']['FR'], 1000.1234)
        for invalid in [pdf('9.0'), pdf(omit=True)]:
            with self.assertRaises(ValueError):
                market.parse_esma_pdf(invalid)

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
                patch.object(market, 'collect_sifma') as sifma, patch.object(market, 'collect_sp') as sp, \
                patch.object(market, 'collect_korea_boards') as korea, patch.object(market, 'collect_esma') as esma, \
                patch.object(market, 'collect_korea_monthly') as monthly, patch.object(market, 'collect_wfe_monthly') as wfe:
            wb.__name__ = 'collect_world_bank'
            with self.assertRaises(SystemExit):
                market.run()
            sifma.assert_called_once()
            sp.assert_called_once()
            korea.assert_called_once()
            esma.assert_called_once()
            monthly.assert_called_once()
            wfe.assert_called_once()


if __name__ == '__main__':
    unittest.main()

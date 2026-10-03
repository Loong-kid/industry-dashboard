import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_mineral_prices as prices


def uranium_html(rows):
    return '<table><thead><tr><th></th><th>Uranium Spot Price</th><th>Long-term Uranium Price</th></tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table>'


def swu_html(rows, check=False):
    caption = ('Table 16. Purchases of enrichment services' if check else
               'Table S2. Uranium feed deliveries, enrichment services,')
    caption += ' by owners and operators of U.S. civilian nuclear power reactors'
    headers = (['Country of enrichment service (SWU-origin)', '2024', '2025'] if check else
               ['Average price (US$ per SWU)', 'Year', 'Total purchased enrichment services'])
    return '<table><caption>' + caption + '</caption><thead><tr>' + ''.join(
        f'<th>{cell}</th>' for cell in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table>'


class MineralPriceTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 10, 4)
        self.payload = {
            'dataAvg': {'INFO': {'mnrkndKornNm': '네오디뮴', 'prcCrtr': '99.5%min FOB China',
                                 'weigUnitCd': 'kg', 'prcUnitCdNm': 'USD'},
                        'stdMap': {'CRTRYMD': {'crtrYmd': '20260924', 'cmercPrc': '127.75'}}},
            'data': {'defaultMnrl': [
                {'crtrYmd': '20260924', 'cmercPrc': '127.75', 'lowstPrc': '127.50', 'hghstPrc': '128.00'},
                {'crtrYmd': '20100702', 'cmercPrc': '37.33', 'lowstPrc': '0', 'hghstPrc': '0'}]},
        }

    def test_uranium_month_end_leap_year_sparse_term_and_duplicate(self):
        html = uranium_html([['1988/01/01', '16.40', ''], ['2024/02/29', '95', '75'],
                             ['2026/09/30', '89.63', '96.50'], ['2026/09/30', '89.63', '96.50']])
        parsed = prices.parse_cameco(html, self.today)
        self.assertEqual(parsed[prices.SPOT], [['1988-01-31', 16.4], ['2024-02-29', 95.0], ['2026-09-30', 89.63]])
        self.assertEqual(parsed[prices.TERM][0], ['2024-02-29', 75.0])

    def test_uranium_rejects_conflicting_rows_invalid_prices_future_and_bad_headers(self):
        for rows in [
            [['2026/09/30', '89.63', '96.5'], ['2026/09/30', '90', '96.5']],
            [['2026/09/30', 'NaN', '96.5']], [['2026/09/30', '-1', '96.5']],
            [['2026/10/01', '89.63', '96.5']], [['2026/09/30', '89.63', '']],
        ]:
            with self.assertRaises(ValueError):
                prices.parse_cameco(uranium_html(rows), self.today)
        with self.assertRaises(ValueError):
            prices.parse_cameco(uranium_html([['2026/09/30', '89.63', '96.5']]).replace('Uranium Spot Price', 'Price'), self.today)

    def test_komis_valid_dates_and_unpublished_ranges(self):
        parsed = prices.parse_komis(self.payload, '네오디뮴', self.today)
        self.assertEqual(parsed, [['2010-07-02', 37.33], ['2026-09-24', 127.75]])

    def test_terbium_requires_its_own_purity_in_product_and_price_response(self):
        options = {'data': [{'cdKey': 806, 'cdVal': 'Terbium Oxide', 'spcfct': '99.99'}]}
        prices.validate_komis_product(options, 806, 'Terbium Oxide', '99.99')
        with self.assertRaises(ValueError):
            prices.validate_komis_product(options, 806, 'Terbium Oxide')
        payload = copy.deepcopy(self.payload)
        payload['dataAvg']['INFO'].update(mnrkndKornNm='터븀', prcCrtr='99.99%min FOB China')
        self.assertEqual(len(prices.parse_komis(payload, '터븀', self.today, '99.99')), 2)
        with self.assertRaises(ValueError):
            prices.parse_komis(payload, '터븀', self.today)

    def test_swu_maps_price_header_skips_missing_years_and_checks_independent_table(self):
        parsed = prices.parse_eia_swu(swu_html([
            ['-', '2003', '100000'], ['97.66', '2024', '120000'], ['108.70', '2025', '140000']]), self.today)
        self.assertEqual(parsed, [['2024-12-31', 97.66], ['2025-12-31', 108.7]])
        prices.validate_eia_swu(parsed, swu_html([
            ['Total', '120000', '140000'], ['Average price (US$ per SWU)', '97.66', '108.70']], check=True), self.today)

    def test_swu_rejects_unfinished_duplicate_missing_latest_invalid_price_and_unit(self):
        for rows in [
            [['108.70', '2026', '100']], [['108.70', '2025', '100'], ['108.70', '2025', '100']],
            [['97.66', '2024', '100'], ['-', '2025', '100']], [['NaN', '2025', '100']],
            [['0', '2025', '100']],
        ]:
            with self.assertRaises(ValueError):
                prices.parse_eia_swu(swu_html(rows), self.today)
        with self.assertRaises(ValueError):
            prices.parse_eia_swu(swu_html([['108.70', '2025', '100']]).replace('US$ per SWU', 'US$ per kg'), self.today)

    def test_swu_rejects_mismatched_verification_price_latest_year_or_unit(self):
        points = [['2024-12-31', 97.66], ['2025-12-31', 108.7]]
        valid = swu_html([['Average price (US$ per SWU)', '97.66', '108.70']], check=True)
        for html in [valid.replace('108.70', '109'), valid.replace('2025', '2026'),
                     valid.replace('2025', '2023'), valid.replace('US$ per SWU', 'US$ per kg')]:
            with self.assertRaises(ValueError):
                prices.validate_eia_swu(points, html, self.today)

    def test_komis_rejects_changed_unit_basis_or_product(self):
        for key, value in [('prcUnitCdNm', 'CNY'), ('weigUnitCd', 't'),
                           ('prcCrtr', 'EXW China'), ('mnrkndKornNm', '디스프로슘')]:
            payload = copy.deepcopy(self.payload)
            payload['dataAvg']['INFO'][key] = value
            with self.assertRaises(ValueError):
                prices.parse_komis(payload, '네오디뮴', self.today)
        for name in ['Neodymium Metal', 'Neodymium Oxide']:
            options = {'data': [{'cdKey': 757, 'cdVal': name, 'spcfct': '99'}]}
            with self.assertRaises(ValueError):
                prices.validate_komis_product(options, 757, 'Neodymium Oxide')

    def test_komis_rejects_empty_future_invalid_range_and_latest_mismatch(self):
        for key, value in [('cmercPrc', '0'), ('cmercPrc', 'Infinity'), ('crtrYmd', '20261005'),
                           ('lowstPrc', '130'), ('hghstPrc', 'NaN')]:
            payload = copy.deepcopy(self.payload)
            payload['data']['defaultMnrl'][0][key] = value
            with self.assertRaises(ValueError):
                prices.parse_komis(payload, '네오디뮴', self.today)
        for change in ('empty', 'summary'):
            payload = copy.deepcopy(self.payload)
            if change == 'empty':
                payload['data']['defaultMnrl'] = []
            else:
                payload['dataAvg']['stdMap']['CRTRYMD']['cmercPrc'] = '128'
            with self.assertRaises(ValueError):
                prices.parse_komis(payload, '네오디뮴', self.today)

    def test_merge_preserves_older_history_accepts_revisions_and_rejects_regression(self):
        doc = {'id': 'test', 'unit': '$/kg', 'price_reference': 757, 'series': {'price': [['2025-01-01', 100], ['2026-09-24', 127.75]]}}
        with tempfile.TemporaryDirectory() as directory, patch.object(prices, 'OUT', Path(directory)):
            prices.save_document(copy.deepcopy(doc))
            revised = {**doc, 'series': {'price': [['2026-09-24', 128], ['2026-09-25', 130]]}}
            prices.save_document(revised)
            path = Path(directory) / 'test.json'
            before = path.read_bytes()
            self.assertEqual(json.loads(before)['series']['price'], [['2025-01-01', 100], ['2026-09-24', 128], ['2026-09-25', 130]])
            with self.assertRaises(ValueError):
                prices.save_document(copy.deepcopy(doc))
            self.assertEqual(path.read_bytes(), before)

    def test_failed_source_does_not_stop_other_sources_or_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(prices, 'OUT', Path(directory)):
            path = Path(directory) / 'comm_uranium.json'
            path.write_text('{"fetched":"2026-09-30"}', encoding='utf-8')
            before = path.read_bytes()
            with patch.object(prices, 'fetch_uranium', side_effect=ValueError('bad table')), \
                    patch.object(prices, 'fetch_swu') as swu, \
                    patch('fetch_komis_prices.run') as komis, patch.object(prices.requests, 'Session'):
                with self.assertRaises(RuntimeError):
                    prices.run()
            komis.assert_called_once()
            swu.assert_called_once()
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

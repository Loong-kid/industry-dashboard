import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import fetch_komis_prices as komis


class KomisPriceTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 10, 4)
        self.registry = komis.load_registry()
        self.card = next(card for card in self.registry['cards'] if card['id'] == 'comm_lithium')
        self.payload = {
            'dataAvg': {'INFO': copy.deepcopy(self.card['info']),
                        'stdMap': {'CRTRYMD': {'crtrYmd': '20260924', 'cmercPrc': '19.35'}}},
            'data': {'defaultMnrl': [
                {'crtrYmd': '20260924', 'cmercPrc': '19.35', 'lowstPrc': '19.10', 'hghstPrc': '19.60'},
                {'crtrYmd': '20180108', 'cmercPrc': '10.5', 'lowstPrc': '0', 'hghstPrc': '0'}]},
        }
        self.options = {773: {'product': self.card['product'], 'specification': self.card['specification']}}

    def test_registry_covers_all_minerals_distinct_references_and_empty_options(self):
        cards = self.registry['cards']
        all_options = cards + self.registry['excluded']
        self.assertEqual(len(cards), 79)
        self.assertEqual(len(all_options), 83)
        self.assertEqual(len({(card['group'], card['mineral_code']) for card in all_options}), 49)
        self.assertEqual(len({komis.identity(card) for card in all_options}), len(all_options))
        self.assertEqual(len({card['id'] for card in cards}), len(cards))
        self.assertEqual(len([card for card in cards if card['mineral_code'] == 'MNRL0001']), 3)
        self.assertTrue(all(card['explanation'] and card['methodology_url'].startswith('https://') for card in cards))

    def test_distinct_currencies_units_products_and_attributions_are_pinned(self):
        for key, value in [('prcUnitCdNm', 'CNY'), ('weigUnitCd', 'mt'), ('prcCrtr', '99.5%min EXW China'),
                           ('mnrkndKornNm', '코발트'), ('isISE', 'N')]:
            payload = copy.deepcopy(self.payload)
            payload['dataAvg']['INFO'][key] = value
            with self.assertRaises(ValueError):
                komis.parse_payload(payload, self.card, self.today)
        payload = copy.deepcopy(self.payload)
        payload['dataAvg']['INFO']['prcCrtr'] += '  '
        self.assertEqual(komis.parse_payload(payload, self.card, self.today)[0][-1], ['2026-09-24', 19.35])
        changed = copy.deepcopy(self.options)
        changed[773]['specification'] = '99'
        with self.assertRaises(ValueError):
            komis.validate_option(self.card, changed)

    def test_auxiliary_range_error_does_not_rewrite_reference_price(self):
        self.payload['data']['defaultMnrl'][0]['lowstPrc'] = '20260112'
        points, quality = komis.parse_payload(self.payload, self.card, self.today)
        self.assertEqual(points[-1], ['2026-09-24', 19.35])
        self.assertEqual(quality['range_mismatch_dates'], ['2026-09-24'])
        self.assertTrue(any('2026-09-24' in row['value'] for row in komis.quotation_details(self.card, quality)))

    def test_missing_or_zero_historical_prices_are_omitted_and_recorded(self):
        self.payload['data']['defaultMnrl'][1]['cmercPrc'] = '0'
        points, quality = komis.parse_payload(self.payload, self.card, self.today)
        self.assertEqual(points, [['2026-09-24', 19.35]])
        self.assertEqual(quality['omitted_dates'], ['2018-01-08'])

    def test_future_invalid_latest_and_conflicting_duplicates_fail(self):
        for key, value in [('cmercPrc', '-1'), ('cmercPrc', 'NaN'), ('cmercPrc', '0'),
                           ('cmercPrc', 'Infinity'), ('crtrYmd', '20261005')]:
            payload = copy.deepcopy(self.payload)
            payload['data']['defaultMnrl'][0][key] = value
            with self.assertRaises(ValueError):
                komis.parse_payload(payload, self.card, self.today)
        payload = copy.deepcopy(self.payload)
        payload['data']['defaultMnrl'].append({'crtrYmd': '20260924', 'cmercPrc': '20'})
        with self.assertRaises(ValueError):
            komis.parse_payload(payload, self.card, self.today)

    def test_empty_manual_lithium_can_migrate_but_existing_different_basis_cannot(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(komis.common, 'OUT', Path(directory)):
            path = Path(directory) / 'comm_lithium.json'
            placeholder = {'id': 'comm_lithium', 'unit': '¥/톤', 'manual': True, 'series': {}}
            path.write_text(json.dumps(placeholder), encoding='utf-8')
            response = Mock()
            response.json.return_value = self.payload
            with patch.object(komis.common, 'request', return_value=response) as request:
                komis.fetch_card(Mock(), self.today, self.card, self.options)
            self.assertEqual(request.call_args.kwargs['data']['srchStartDate'], 1987)
            doc = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(doc['unit'], 'USD/kg')
            self.assertNotIn('manual', doc)
            placeholder['series'] = {'旧': [['2025-01-01', 100]]}
            path.write_text(json.dumps(placeholder), encoding='utf-8')
            before = path.read_bytes()
            with patch.object(komis.common, 'request', return_value=response), self.assertRaises(ValueError):
                komis.fetch_card(Mock(), self.today, self.card, self.options)
            self.assertEqual(path.read_bytes(), before)

    def test_failed_metadata_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(komis.common, 'OUT', Path(directory)):
            path = Path(directory) / 'comm_lithium.json'
            path.write_text('{"series":{"price":[["2025-01-01",10]]}}', encoding='utf-8')
            before = path.read_bytes()
            self.payload['dataAvg']['INFO']['prcUnitCdNm'] = 'CNY'
            response = Mock()
            response.json.return_value = self.payload
            with patch.object(komis.common, 'request', return_value=response), self.assertRaises(ValueError):
                komis.fetch_card(Mock(), self.today, self.card, self.options)
            self.assertEqual(path.read_bytes(), before)

    def test_incremental_update_preserves_older_quality_and_history(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(komis.common, 'OUT', Path(directory)):
            path = Path(directory) / 'comm_lithium.json'
            old = {'id': self.card['id'], 'unit': 'USD/kg', 'price_reference': self.card['price_reference'],
                   'series': {'기준가격': [['2020-01-01', 9], ['2026-09-24', 19]]},
                   'data_quality': {'range_mismatch_dates': ['2020-01-01', '2026-09-24'], 'omitted_dates': []}}
            path.write_text(json.dumps(old), encoding='utf-8')
            self.payload['data']['defaultMnrl'] = self.payload['data']['defaultMnrl'][:1]
            response = Mock()
            response.json.return_value = self.payload
            with patch.object(komis.common, 'request', return_value=response) as request:
                komis.fetch_card(Mock(), self.today, self.card, self.options)
            self.assertEqual(request.call_args.kwargs['data']['srchStartDate'], 2025)
            doc = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(doc['series']['기준가격'], [['2020-01-01', 9], ['2026-09-24', 19.35]])
            self.assertEqual(doc['data_quality']['range_mismatch_dates'], ['2020-01-01'])

    def test_one_card_failure_does_not_stop_other_prices_and_inventory_drift_is_detected(self):
        second = copy.deepcopy(self.card)
        second.update(id='second', reference=772)
        registry = {'cards': [self.card, second], 'excluded': []}
        response = Mock()
        response.json.return_value = {'data': [{'cdKey': self.card['mineral_code']}]}
        with patch.object(komis, 'load_registry', return_value=registry), patch.object(komis, 'GROUPS', {'HP002': ()}), \
                patch.object(komis.common, 'request', return_value=response), \
                patch.object(komis, 'options_for', return_value={773: {}, 772: {}, 999: {}}), \
                patch.object(komis, 'fetch_card', side_effect=[ValueError('bad price'), None]) as fetch:
            with self.assertRaises(RuntimeError):
                komis.run(session=Mock(headers={}), today=self.today)
            self.assertEqual(fetch.call_count, 2)


if __name__ == '__main__':
    unittest.main()

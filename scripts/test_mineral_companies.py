import copy
import datetime as dt
import unittest
from unittest.mock import patch

import fetch_mineral_companies as m


class CompanyTests(unittest.TestCase):
    def report(self, quarter=2):
        return {'year': 2026, 'quarter': quarter, 'period': m.quarter_end(2026, quarter), 'url': 'https://issuer.test/result'}

    def test_mp_missing_ndpr_is_not_zero_or_percent(self):
        points = m.parse_mp('REO Production Volume (MTs) 11072 13145 (2073) (16)%\nNdPr Production Volume (MTs) 131 N/A N/A N/A', self.report())
        self.assertEqual([p.get('ndpr') for p in points if 'ndpr' in p], [131, None])
        with self.assertRaises(ValueError):
            m.parse_mp('REO Production Volume (MTs) -1 20', self.report())

    def test_fcx_quarter_not_ytd_and_annual_columns(self):
        points = m.parse_fcx('SUMMARY OPERATING DATA\n2026 millions of recoverable pounds\nProduction 786 963 1448 1831\nGold (', self.report())
        self.assertEqual(points[0]['copper'], 786)
        self.assertEqual(len(points), 2)
        q4 = m.parse_fcx('SUMMARY OPERATING DATA\n2026 millions of recoverable pounds\nProduction 800 900 3400 3600\nGold (', self.report(4))
        self.assertEqual(q4[2]['copper'], 3400)
        self.assertEqual(q4[2]['kind'], 'annual')

    def test_alb_growth_is_not_absolute_volume(self):
        points = m.parse_alb('Q2 sales volume growth of 10%; FY 2026 guidance 235 kt LCE', self.report())
        self.assertIsNone(points[0]['lce_sales'])
        self.assertEqual(m.parse_alb('Q2 2026 sales volumes of 65 kt LCE', self.report())[0]['lce_sales'], 65)

    def test_alcoa_loss_and_reconciliation_signs(self):
        text = ('Segment Information\n1Q26 2Q26 2025\nAluminum production (kmt) 607 636 2319\n'
                'Alumina production (kmt) 2355 2218 9640\nConsolidated loss before income taxes (30) 482 1064\n'
                'Interest expense (30) (36) (158)\nOther (expenses) income, net 10 (200) 1057')
        points = m.parse_aa(text, self.report())
        self.assertEqual([p['profit'] for p in points if 'profit' in p], [-10, 718, 165])
        with self.assertRaises(ValueError):
            m.parse_aa(text.replace('607 636 2319', '607 636'), self.report())

    def test_cameco_cad_thousands_and_ytd(self):
        text = ('Production volume (million lbs) 3.9 4.6 (15)% 10.1 10.6 (5)%\n'
                'Consolidated statements of earnings\nEarnings from operations 84139 165951 247976 351763')
        points = m.parse_ccj(text, self.report())
        self.assertEqual(points[0]['uranium'], 3.9)
        self.assertEqual(points[2]['profit'], 84.139)
        self.assertEqual(len(points), 4)

    def test_sec_identity_currency_and_q4_difference(self):
        row = {'start': '2025-01-01', 'end': '2025-12-31', 'filed': '2026-02-01', 'form': '10-K', 'accn': '0000000001-26-000001', 'val': 100}
        payload = {'cik': 1, 'facts': {'us-gaap': {'OperatingIncomeLoss': {'units': {'USD': [row]}}}}}
        annual = m.sec_rows(payload, 1, 'us-gaap', 'OperatingIncomeLoss', 'USD', '2026-10-05')
        annual[('2025-01-01', '2025-09-30')] = {**next(iter(annual.values())), 'value': 130}
        quarters, years = m.earnings_periods(annual, '2026-10-05')
        self.assertEqual(quarters['2025-12-31']['value'], -30)
        self.assertEqual(years['2025-12-31']['value'], 100)
        with self.assertRaises(ValueError):
            m.sec_rows(payload, 2, 'us-gaap', 'OperatingIncomeLoss', 'USD', '2026-10-05')
        with self.assertRaises(KeyError):
            m.sec_rows(payload, 1, 'us-gaap', 'OperatingIncomeLoss', 'CAD', '2026-10-05')

    def test_history_and_zero_preservation(self):
        old = {'updated': '2026-06-30', 'series': {'x': [['2026-03-31', 0], ['2026-06-30', -1]]}}
        new = copy.deepcopy(old)
        m.preserve_history(old, new)
        new['series']['x'][0][1] = None
        with self.assertRaises(ValueError):
            m.preserve_history(old, new)

    def test_incomplete_exchange_session_and_wrong_symbol(self):
        now = int(dt.datetime(2026, 10, 2, 16, tzinfo=dt.timezone.utc).timestamp())
        timestamps = [now - 86400 * n for n in range(120, -1, -1)]
        payload = {'chart': {'result': [{'meta': {'symbol': 'FCX', 'currency': 'USD', 'instrumentType': 'EQUITY',
                     'currentTradingPeriod': {'regular': {'end': now + 14400}}}, 'timestamp': timestamps,
                     'indicators': {'quote': [{'close': [30] * 121}]}}]}}
        prices = m.price_series(payload, 'FCX', now)
        self.assertEqual(prices[-1][0], '2026-10-01')
        self.assertEqual(len(prices), 120)
        with self.assertRaises(ValueError):
            m.price_series(payload, 'SCCO', now)

    def test_collection_failure_keeps_other_company_cohorts_running(self):
        with patch.object(m, 'stock_doc', side_effect=ValueError('source failed')), patch.object(m, 'earnings_doc', return_value={'id': 'profit'}), patch.object(m, 'publish') as publish, patch.object(m, 'operating_docs') as operations:
            with self.assertRaises(RuntimeError):
                m.collect(only=['fcx', 'scco'])
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(operations.call_count, 2)


if __name__ == '__main__':
    unittest.main()

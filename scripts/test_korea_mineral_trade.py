import datetime as dt
import unittest
from unittest.mock import patch

from fetch_korea_mineral_trade import FIELDS, annual_rows, month_dates, monthly_history, number, ranked_rows, reconcile_months


def country(**changes):
    return {'ntnCd': 'CL', 'ntnKornNm': '칠레', 'incmAmt': 40, 'incmWeig': 2000,
            'expAmt': 0, 'expWeig': 0, 'sumIncmAmt': 100, 'sumIncmWeig': 5000,
            'sumExpAmt': 0, 'sumExpWeig': 0, **changes}


def payload(rows):
    return {'srchDateS': '20260101', 'srchDateE': '20260831', 'list': rows}


class TradeParserTests(unittest.TestCase):
    def test_source_totals_are_not_reconstructed_from_top_countries(self):
        result = ranked_rows(payload([country()]), '20260101', '20260831', 'I')
        self.assertEqual(result['totals']['incmAmt'], 100)
        self.assertEqual(result['countries'][0]['incmAmt'], 40)
        self.assertEqual(result['totals']['incmWeig'], 5000)

    def test_empty_country_response_is_unavailable_not_zero(self):
        result = ranked_rows(payload([]), '20260101', '20260831', 'I')
        self.assertIsNone(result['totals'])

    def test_missing_country_name_retains_the_code_and_its_weight(self):
        result = ranked_rows(payload([country(ntnCd='ZZ', ntnKornNm=None)]), '20260101', '20260831', 'I')
        self.assertEqual(result['countries'][0]['name'], '국가명 미제공(ZZ)')
        self.assertEqual(result['countries'][0]['incmWeig'], 2000)

    def test_wrong_period_duplicate_country_and_inconsistent_totals_fail(self):
        with self.assertRaises(ValueError):
            ranked_rows(payload([country()]), '20250101', '20250831', 'I')
        for rows in ([country(), country()], [country(), country(ntnCd='US', sumIncmAmt=101)],
                     [country(incmAmt=101)], [country(incmWeig=-1)],
                     [country(incmAmt=1), country(ntnCd='US', incmAmt=2)]):
            with self.assertRaises(ValueError):
                ranked_rows(payload(rows), '20260101', '20260831', 'I')

    def test_annual_values_keep_usd_kg_and_real_zero(self):
        row = {'crtrYmd': '2025', 'totalIncmAmt': 1000000, 'totalIncmWeig': 1234,
               'totalExpAmt': 0, 'totalExpWeig': 0}
        result = annual_rows([row], 2014, 2025)
        self.assertEqual(result['2025']['incmWeig'], 1234)
        self.assertEqual(result['2025']['expAmt'], 0)
        with self.assertRaises(ValueError):
            annual_rows([{**row, 'crtrYmd': '2026'}], 2014, 2025)
        with self.assertRaises(ValueError):
            annual_rows([row, row], 2014, 2025)
        with self.assertRaises(ValueError):
            annual_rows([{**row, 'totalExpAmt': None}], 2014, 2025)

    def test_invalid_values_are_rejected(self):
        self.assertEqual(number(0), 0)
        for value in (None, '', True, -1, 'NaN', 'Infinity'):
            with self.assertRaises(ValueError):
                number(value)

    def test_month_periods_cover_first_month_through_cutoff_and_leap_day(self):
        periods = month_dates(2024, dt.date(2024, 2, 29))
        self.assertEqual(periods, [('2024-01-01', '20240101', '20240131'),
                                   ('2024-02-01', '20240201', '20240229')])

    def test_monthly_sums_match_all_four_published_annual_fields(self):
        point = {field: 10 for field in FIELDS}
        monthly = {f'2025-{month:02d}-01': point.copy() for month in range(1, 13)}
        total = {field: 120 for field in FIELDS}
        checks = reconcile_months(monthly, {'2025': total}, {})
        self.assertEqual(checks['2025']['status'], 'matched')
        monthly['2025-02-01']['expWeig'] = 11
        with self.assertRaises(ValueError):
            reconcile_months(monthly, {'2025': total}, {})

    def test_missing_month_stays_unavailable_and_is_not_counted_as_zero(self):
        monthly = {'2025-01-01': {field: 10 for field in FIELDS},
                   **{f'2025-{month:02d}-01': None for month in range(2, 13)}}
        checks = reconcile_months(monthly, {'2025': {field: 20 for field in FIELDS}}, {})
        self.assertEqual(checks['2025'], {'status': 'partial', 'available_months': 1, 'expected_months': 12})
        self.assertIsNone(monthly['2025-02-01'])
        with self.assertRaises(ValueError):
            reconcile_months(monthly, {'2025': {field: 9 for field in FIELDS}}, {})

    def test_monthly_ytd_validation_uses_matching_year_and_months(self):
        point = {field: 10 for field in FIELDS}
        monthly = {f'2026-{month:02d}-01': point for month in range(1, 9)}
        snapshots = {'ytd': {'start': '20260101', 'end': '20260831', 'totals': {field: 80 for field in FIELDS}}}
        self.assertEqual(reconcile_months(monthly, {}, snapshots)['ytd']['available_months'], 8)
        with self.assertRaises(ValueError):
            reconcile_months(monthly, {}, {'ytd': {**snapshots['ytd'], 'totals': {field: 90 for field in FIELDS}}})

    def test_incremental_collection_preserves_old_years_and_applies_recent_revision(self):
        old_point = {field: 10 for field in FIELDS}
        periods = month_dates(2023, dt.date(2025, 2, 28))
        previous = {'monthly': {date: old_point.copy() for date, _, _ in periods},
                    'annual': {year: {field: 120 for field in FIELDS} for year in ('2023', '2024')}}
        def response(worker, url, params):
            totals = country()
            for field in FIELDS:
                totals[field] = 10 if params['srchDateS'] != '20240201' else 11
                totals['sum' + field[0].upper() + field[1:]] = totals[field]
            return {'list': [totals], 'srchDateS': params['srchDateS'], 'srchDateE': params['srchDateE']}
        annual = {'2023': {field: 120 for field in FIELDS}, '2024': {field: 121 for field in FIELDS}}
        with patch('fetch_korea_mineral_trade.post', side_effect=response) as mocked:
            points, checks = monthly_history(None, 'MNRL0008', 2023, dt.date(2025, 2, 28), annual, previous, {})
        self.assertEqual(mocked.call_count, 14)
        self.assertEqual(points['2023-02-01'], old_point)
        self.assertEqual(points['2024-02-01']['incmAmt'], 11)
        self.assertEqual(checks['2024']['status'], 'matched')

    def test_historical_annual_revision_triggers_monthly_recheck(self):
        point = {field: 10 for field in FIELDS}
        previous = {'monthly': {date: point.copy() for date, _, _ in month_dates(2023, dt.date(2025, 1, 31))},
                    'annual': {'2023': {field: 119 for field in FIELDS}}}
        def response(worker, url, params):
            row = country(**{field: 10 for field in FIELDS},
                          **{'sum' + field[0].upper() + field[1:]: 10 for field in FIELDS})
            return {'list': [row], 'srchDateS': params['srchDateS'], 'srchDateE': params['srchDateE']}
        with patch('fetch_korea_mineral_trade.post', side_effect=response) as mocked:
            monthly_history(None, 'MNRL0008', 2023, dt.date(2025, 1, 31),
                            {'2023': {field: 120 for field in FIELDS}}, previous, {})
        self.assertEqual(mocked.call_count, 25)

    def test_disappearing_previously_published_month_fails(self):
        previous = {'monthly': {'2026-01-01': {field: 10 for field in FIELDS}}}
        with patch('fetch_korea_mineral_trade.post', return_value={'list': [], 'srchDateS': '20260101', 'srchDateE': '20260131'}):
            with self.assertRaises(ValueError):
                monthly_history(None, 'MNRL0008', 2026, dt.date(2026, 1, 31), {}, previous, {})


if __name__ == '__main__':
    unittest.main()

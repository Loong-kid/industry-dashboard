import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_ess_companies as m


class ESSTests(unittest.TestCase):
    def row(self, date, value):
        return m.point('cumulative', 'quarter', date, value, {'url': 'https://issuer.test/result'})

    def test_net_deployment_requires_adjacent_quarters_and_allows_retirement(self):
        rows = {date: self.row(date, value) for date, value in
                [('2025-09-30', 10), ('2026-03-31', 15), ('2026-06-30', 14)]}
        net = m.quarterly_difference(rows)
        self.assertEqual(list(net), ['2026-06-30'])
        self.assertEqual(net['2026-06-30']['value'], -1)

    def test_partial_cumulative_never_bridges_missing_quarter(self):
        rows = {date: self.row(date, value) for date, value in
                [('2025-03-31', 2), ('2025-06-30', 3), ('2025-12-31', 4)]}
        with self.assertRaises(ValueError):
            m.cumulative_sum(rows, '2025-03-31')
        self.assertEqual(m.annual_sum(rows), {})
        rows['2025-09-30'] = self.row('2025-09-30', 1)
        self.assertEqual(m.cumulative_sum(rows, '2025-03-31')['2025-12-31']['value'], 10)
        self.assertEqual(m.annual_sum(rows)['2025-12-31']['value'], 10)

    def test_view_inserts_null_instead_of_fabricating_zero(self):
        rows = {date: self.row(date, value) for date, value in [('2025-12-31', 0), ('2026-06-30', 1)]}
        view = m.view(rows, 'test', 'quarterly', fiscal=True)
        self.assertEqual(view['series']['test'], [['2025-12-31', 0], ['2026-03-31', None], ['2026-06-30', 1]])
        self.assertEqual(view['fiscal_year_end_month'], 9)

    def test_financial_deck_waits_for_filed_financial_report(self):
        payload = {'cik': 1318605, 'filings': {'recent': {
            'form': ['8-K', '10-Q', '10-Q'], 'reportDate': ['2026-10-02', '2026-06-30', '2026-09-30'],
            'filingDate': ['2026-10-02', '2026-07-23', '2026-10-22'], 'accessionNumber': ['1', '2', '3']}}}
        existing = {'deck': {'parser': 'tesla', 'period': '2026-06-30'}}
        with patch.object(m, 'korea_today', return_value=dt.date(2026, 10, 7)), patch.object(m, 'download', return_value=json.dumps(payload).encode()) as download:
            reports = m.latest_tesla(existing)
        self.assertEqual(download.call_count, 1)
        self.assertEqual([r['period'] for r in reports], ['2026-06-30'])

    def fluence_html(self, columns, quarter=True):
        labels = ['Total revenue', 'Gross profit', 'Research and development', 'Sales and marketing', 'General and administrative', 'Depreciation and amortization']
        return ('Fluence Energy results in thousands<table><tr><td>' + ('Three Months' if quarter else 'Year ended') + '</td></tr>' +
                ''.join('<tr><td>' + label + '</td>' + ''.join('<td>' + str(value) + '</td>' for value in values) + '</tr>'
                        for label, values in zip(labels, columns)) + '</table>').encode()

    def test_fluence_profit_is_component_subtotal_not_net_income(self):
        html = self.fluence_html([[649848, 600000], [33241, 50000], [23740, 10000], [25300, 10000], [37735, 20000], [3986, 3000]])
        rows = m.parse_fluence(html, {'period': '2026-06-30', 'quarter': 3, 'url': 'https://issuer.test'})
        current = {(r['metric'], r['kind']): r['value'] for r in rows if r['date'] == '2026-06-30'}
        self.assertEqual(current[('revenue', 'quarter')], 649.848)
        self.assertEqual(current[('profit', 'quarter')], -57.52)
        with self.assertRaises(ValueError):
            m.parse_fluence(html.replace(b'in thousands', b''), {'period': '2026-06-30', 'quarter': 3, 'url': 'https://issuer.test'})

    def test_annual_statement_not_misidentified_as_q4(self):
        html = self.fluence_html([[1000000, 900000], [100000, 90000], [1000, 1000], [1000, 1000], [1000, 1000], [1000, 1000]], quarter=False)
        rows = m.parse_fluence(html, {'period': '2025-09-30', 'quarter': 4, 'url': 'https://issuer.test'})
        self.assertEqual({row['kind'] for row in rows}, {'annual'})

    def test_aum_and_revenue_basis_gwh_never_become_deployed(self):
        html = self.fluence_html([[1000, 900], [100, 90], [10, 10], [10, 10], [10, 10], [10, 10]])
        html += b'<table><tr><td>Services and Digital Deployed (GWh) 999 998</td></tr></table>'
        html += b'<table><tr><td>Energy Storage Products and Solutions June 30, 2026 September 30, 2025</td></tr><tr><td>Deployed (GWh)</td><td>19.3</td><td>17.8</td></tr><tr><td>Energy storage solutions GWh (Revenue basis)</td><td>3.1</td><td>7.4</td></tr></table>'
        rows = m.parse_fluence(html, {'period': '2026-06-30', 'quarter': 3, 'url': 'https://issuer.test'})
        self.assertEqual([r['value'] for r in rows if r['metric'] == 'cumulative'], [19.3, 17.8])

    def test_report_correction_precedence(self):
        old, newer = self.row('2025-09-30', 10), self.row('2025-09-30', 11)
        data = m.merge_points({'a': {'period': '2025-09-30', 'points': [old]}, 'b': {'period': '2026-06-30', 'points': [newer]}})
        self.assertEqual(next(iter(data.values()))['value'], 11)

    def test_tesla_energy_rpo_excludes_automotive_credits_and_revenue_table(self):
        text = ('Energy generation and storage sales 2998 2646 Automotive Regulatory Credits '
                'contracts with an original expected length of more than one year was $287 million '
                'EnergyGenerationandStorageSegment Energy Generation and Storage Sales '
                'contracts with an original expected length of more than one year was $10.05 billion '
                'IncomeTaxes')
        with patch.object(m, 'blocks', return_value=[(12, text)]):
            rows = m.parse_tesla(b'', {'parser': 'tesla_rpo', 'period': '2026-06-30', 'url': 'https://issuer.test'})
        self.assertEqual(rows[0]['value'], 10050)

    def test_sungrow_half_revenue_not_quarter_and_not_operating_profit(self):
        with patch.object(m, 'blocks', return_value=[(34, '阳光电源 储能行业 15,455,765,101.22 43.00% 17,802,777,589.48 50.00%')]):
            rows = m.parse_sungrow(b'', {'kind': 'half', 'period': '2026-06-30', 'url': 'https://issuer.test'})
        self.assertEqual({(r['metric'], r['kind']) for r in rows}, {('revenue', 'half')})
        self.assertAlmostEqual(rows[0]['value'], 15455.76510122)

    def test_all_company_validation_precedes_writes(self):
        valid = {'id': 'a', 'series': {'x': [['2026-06-30', 1]]}}
        invalid = {'id': 'b', 'series': {'x': [['2026-06-30', None]]}}
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'OUT', Path(folder)), patch.object(m, 'build_cards', return_value=[valid, invalid]), patch.object(m, 'atomic_json') as write:
            with self.assertRaises(ValueError):
                m.publish('tesla', {})
            write.assert_not_called()

    def test_company_failure_preserves_publication_and_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            registry, cache, out = base / 'registry.json', base / 'cache.json', base / 'out'
            registry.write_text(json.dumps({'reports': [{'company': 'tesla', 'period': '2026-06-30', 'url': 'https://issuer.test', 'parser': 'tesla'}]}))
            cache.write_text('{"companies":{}}')
            out.mkdir()
            marker = out / 'ess_tesla_revenue.json'
            marker.write_text('previous publication')
            with patch.object(m, 'REGISTRY', registry), patch.object(m, 'CACHE', cache), patch.object(m, 'OUT', out), patch.object(m, 'download', return_value=b'invalid'):
                with self.assertRaises(RuntimeError):
                    m.collect(offline=True, only=['tesla'])
            self.assertEqual(marker.read_text(), 'previous publication')
            self.assertEqual(cache.read_text(), '{"companies":{}}')

    def test_checked_in_publication_matches_audited_sources(self):
        def at(metric, date='2026-06-30'):
            doc = json.loads((m.OUT / (metric + '.json')).read_text(encoding='utf-8'))
            return dict(next(iter(doc['series'].values())))[date]
        self.assertEqual(at('ess_tesla_deployment', '2026-09-30'), 13.7)
        self.assertEqual(at('ess_tesla_revenue'), 3139)
        self.assertEqual(at('ess_tesla_rpo'), 10050)
        self.assertEqual(at('ess_fluence_revenue'), 627.3)
        self.assertEqual(at('ess_fluence_profit'), -57.52)
        self.assertEqual(at('ess_fluence_cumulative'), 19.3)
        self.assertEqual(at('ess_fluence_deployment'), .1)
        self.assertEqual(at('ess_fluence_order_intake'), 1441)
        self.assertEqual(at('ess_fluence_pipeline'), 163.7)
        self.assertEqual(at('ess_sungrow_shipments', '2025-12-31'), 43)


if __name__ == '__main__':
    unittest.main()

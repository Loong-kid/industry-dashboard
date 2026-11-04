import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fetch_copper_valuation import ROOT, REGISTRY, OUT, run, copper_fundamentals
from fetch_semicon_valuation import load, analytics

FIX = ROOT / 'scripts/fixtures/copper_valuation'


class CopperValuationTests(unittest.TestCase):
    def test_registered_usd_listings_and_industry_isolation(self):
        specs = load(REGISTRY, [])
        self.assertEqual([(s['id'], s['symbol'], s['currency']) for s in specs],
                         [('scco', 'SCCO', 'USD'), ('fcx', 'FCX', 'USD'), ('ero', 'ERO', 'USD')])
        semi = load(ROOT/'manual/semicon-valuation/companies.json', [])
        self.assertFalse({'scco', 'fcx', 'ero'} & {s['id'] for s in semi})
        index = load(OUT/'copper_valuation_index.json', {})
        self.assertEqual(index['id'], 'copper_valuation_index')
        self.assertEqual(index['auto_collect_time'], '08:20')
        self.assertEqual([c['id'] for c in index['companies']], [s['id'] for s in specs])
        for summary in index['companies']:
            d = load(OUT/(summary['id']+'.json'), {})
            self.assertEqual(d['kind'], 'copper_valuation')
            self.assertEqual(d['currency'], 'USD')
            self.assertGreater(len(d['prices']), 1000)
            self.assertEqual(d['prices'][-1], [summary['price_date'], summary['price']])
            self.assertEqual(len(d['prices']), len(dict(d['prices'])))
            latest, bands = analytics(d['prices'], d['fundamentals'], 'USD', d['fx'])
            self.assertEqual(latest, d['latest']); self.assertEqual(bands, d['bands'])
            self.assertEqual(summary['per'], latest['per']); self.assertEqual(summary['pbr'], latest['pbr'])
            self.assertTrue(d['fundamentals']['eps']); self.assertTrue(d['fundamentals']['bps'])
            self.assertNotIn('반도체·개별 사업부', d['methodology'])
        ero = load(OUT/'ero.json', {})
        self.assertGreaterEqual(ero['prices'][0][0], '2021-06-15')
        self.assertTrue(any(r[1] < 0 for r in ero['fundamentals']['eps']))

    def test_scco_ignores_mixed_basis_trailing_and_sums_four_actual_quarters(self):
        payload = load(FIX/'SCCO_fund.json', {})
        fund = copper_fundamentals(payload, 'SCCO', '2026-11-05', [['2026-11-03', 1.01]])
        eps = {r[0]: r[1] for r in fund['eps']}
        self.assertNotIn('2023-09-30', eps)
        self.assertAlmostEqual(eps['2025-12-31'], 5.030072)
        self.assertAlmostEqual(eps['2026-09-30'], 1.497502+1.858746+1.965333+2.127449)
        self.assertNotAlmostEqual(eps['2026-09-30'], 7.434584)
        self.assertTrue(all('trailingDilutedEPS' not in r[3] for r in fund['eps']))

    def test_missing_or_consensus_quarter_never_becomes_actual_ttm(self):
        payload = load(FIX/'SCCO_fund.json', {})
        for series in payload['timeseries']['result']:
            if series['meta']['type'][0] == 'quarterlyDilutedEPS':
                series['quarterlyDilutedEPS'] = [r for r in series['quarterlyDilutedEPS'] if r['asOfDate'] != '2026-03-31']
        fund = copper_fundamentals(payload, 'SCCO', '2026-11-05')
        self.assertNotIn('2026-09-30', [r[0] for r in fund['eps']])
        with self.assertRaisesRegex(ValueError, 'issuer'):
            copper_fundamentals(payload, 'FCX', '2026-11-05')

    def test_source_failure_keeps_last_success_without_touching_semiconductor_data(self):
        import requests
        original = load(OUT/'ero.json', {})
        semi = ROOT/'data/semicon/valuation/valuation_index.json'
        before = semi.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out/'ero.json').write_text(json.dumps(original), encoding='utf8')
            specs = out/'companies.json'; specs.write_text(json.dumps([load(REGISTRY, [])[-1]]), encoding='utf8')
            with patch('fetch_copper_valuation.OUT', out), patch('fetch_copper_valuation.REGISTRY', specs), \
                 patch('fetch_semicon_valuation.requests.Session') as session:
                session.return_value.get.side_effect = requests.ConnectionError('outage')
                run()
            new = load(out/'ero.json', {})
            self.assertEqual(new['prices'], original['prices'])
            self.assertEqual(new['fundamentals'], original['fundamentals'])
            self.assertFalse(new['ok']); self.assertTrue(new['errors'])
        self.assertEqual(before, semi.read_bytes())

    def test_only_copper_miners_links_all_three_charts(self):
        industry = next(i for i in load(ROOT/'data/catalog.json', {})['industries'] if i['id']=='commodities')
        links = []
        for section in industry['sections']:
            ids = ([section['valuation_company']] if section.get('valuation_company') else [])
            ids += section.get('valuation_companies', [])
            ids += [c['valuation_company'] for c in section.get('companies', []) if c.get('valuation_company')]
            if ids:
                self.assertEqual((section['tab'], section['view']), ('copper', 'miners'))
                links += ids
        self.assertEqual(sorted(links), ['ero','ero','fcx','fcx','scco','scco'])


if __name__ == '__main__':
    unittest.main()

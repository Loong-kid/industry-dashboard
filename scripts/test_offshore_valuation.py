"""Issuer, currency, restructuring boundaries and actual valuation regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fetch_offshore_valuation import REGISTRY, OUT, ROOT, run
from fetch_semicon_valuation import load
from semicon_valuation_sources import analytics, converted, at_or_before


class OffshoreValuationTests(unittest.TestCase):
    def test_all_six_operators_and_no_industry_cross_contamination(self):
        specs = load(REGISTRY, [])
        financials = load(ROOT/'data/offshore/offshore_financials.json', {})
        self.assertEqual([c['id'] for c in specs], [c['id'] for c in financials['companies']])
        self.assertEqual([c['symbol'] for c in specs], ['RIG', 'VAL', 'NE', 'SDRL', 'ODL.OL', 'BORR'])
        index = load(OUT/'offshore_valuation_index.json', {})
        self.assertEqual(index['id'], 'offshore_valuation_index')
        self.assertEqual(index['auto_collect_time'], '08:30')
        self.assertEqual([c['id'] for c in index['companies']], [c['id'] for c in specs])
        semiconductor = load(ROOT/'manual/semicon-valuation/companies.json', [])
        self.assertFalse({c['id'] for c in specs} & {c['id'] for c in semiconductor})

    def test_price_boundaries_and_split_share_identity(self):
        for spec in load(REGISTRY, []):
            doc = load(OUT/(spec['id']+'.json'), {})
            self.assertEqual((doc['symbol'], doc['currency'], doc['kind']), (spec['symbol'], spec['currency'], 'offshore_valuation'))
            self.assertGreater(len(doc['prices']), 1000)
            self.assertGreaterEqual(doc['prices'][0][0], spec.get('price_since', '2014-01-01'))
            self.assertEqual(doc['prices'], sorted(doc['prices']))
            self.assertEqual(len(doc['prices']), len(dict(doc['prices'])))
            self.assertTrue(all(v > 0 for _, v in doc['prices']))
            self.assertTrue(doc['fundamentals']['eps'])
            self.assertTrue(doc['fundamentals']['bps'])
            self.assertTrue(doc['bands']['per'])
            self.assertTrue(doc['bands']['pbr'])
            self.assertNotIn('반도체·개별 사업부', doc['methodology'])
        seadrill = load(OUT/'seadrill.json', {})
        self.assertTrue(all(r[0] >= '2023-01-01' for r in seadrill['fundamentals']['eps']))

    def test_published_bands_reconcile_and_losses_are_not_negative_per(self):
        index = load(OUT/'offshore_valuation_index.json', {})
        for summary in index['companies']:
            doc = load(OUT/(summary['id']+'.json'), {})
            latest, bands = analytics(doc['prices'], doc['fundamentals'], doc['currency'], doc['fx'])
            self.assertEqual(doc['latest'], latest)
            self.assertEqual(doc['bands'], bands)
            self.assertEqual(doc['prices'][-1], [summary['price_date'], summary['price']])
            self.assertEqual(summary['per'], latest['per'])
            self.assertEqual(summary['pbr'], latest['pbr'])
            for key in ('per', 'pbr'):
                self.assertTrue(latest[key] is None or latest[key] > 0)
        doc = load(OUT/'transocean.json', {})
        negative = next(r for r in doc['fundamentals']['eps'] if r[1] < 0)
        price = next(r for r in doc['prices'] if r[0] >= negative[0])
        latest, _ = analytics([price], doc['fundamentals'], doc['currency'], doc['fx'])
        self.assertIsNone(latest['per'])
        self.assertEqual(latest['eps_reason'], '적자·0 이하')

    def test_odfjell_uses_usd_nok_and_missing_fx_is_not_one_to_one(self):
        doc = load(OUT/'odfjell.json', {})
        self.assertEqual(doc['currency'], 'NOK')
        self.assertTrue(doc['fx']['USDNOK'])
        date, price = doc['prices'][-1]
        for field, key in [('eps', 'per'), ('bps', 'pbr')]:
            row = at_or_before(doc['fundamentals'][field], date)
            self.assertEqual(row[2], 'USD')
            rate = at_or_before(doc['fx']['USDNOK'], date, 7)[1]
            self.assertAlmostEqual(converted(row, date, 'NOK', doc['fx']), row[1]*rate)
            self.assertAlmostEqual(doc['latest'][key], price/(row[1]*rate), places=4)
            self.assertIsNone(converted(row, date, 'NOK', {}))

    def test_failure_keeps_last_successful_cohort(self):
        import requests
        original = load(OUT/'seadrill.json', {})
        before = (ROOT/'data/semicon/valuation/valuation_index.json').read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out/'seadrill.json').write_text(json.dumps(original), encoding='utf8')
            registry = out/'companies.json'
            registry.write_text(json.dumps([next(s for s in load(REGISTRY, []) if s['id']=='seadrill')]), encoding='utf8')
            with patch('fetch_offshore_valuation.OUT', out), patch('fetch_offshore_valuation.REGISTRY', registry), patch('fetch_semicon_valuation.requests.Session') as session:
                session.return_value.get.side_effect = requests.ConnectionError('outage')
                run()
            result = load(out/'seadrill.json', {})
            self.assertFalse(result['ok'])
            self.assertTrue(result['errors'])
            self.assertEqual(result['prices'], original['prices'])
            self.assertEqual(result['fundamentals'], original['fundamentals'])
        self.assertEqual(before, (ROOT/'data/semicon/valuation/valuation_index.json').read_bytes())

    def test_view_scoped_sections_and_scheduled_publication(self):
        oil = next(i for i in load(ROOT/'data/catalog.json', {})['industries'] if i['id']=='oil')
        sections = [s for s in oil['sections'] if s.get('type') in ('valuation_summary','valuation_charts')]
        self.assertEqual([s['type'] for s in sections], ['valuation_summary','valuation_charts'])
        for section in sections:
            self.assertEqual((section['tab'], section['view'], section['data_industry']), ('offshore','valuations','offshore/valuation'))
            self.assertEqual(section['valuation_companies'], [s['id'] for s in load(REGISTRY, [])])
        publish = (ROOT/'.github/workflows/publish-data.yml').read_text(encoding='utf8')
        self.assertIn('update-offshore-valuation', publish)
        workflow = (ROOT/'.github/workflows/update-offshore-valuation.yml').read_text(encoding='utf8')
        self.assertIn("cron: '30 23 * * *'", workflow)
        self.assertIn('git add data/offshore/valuation/*.json', workflow)


if __name__ == '__main__':
    unittest.main()

"""Independent financial anchors, frequency boundaries and reconciliation."""
import copy
import json
import unittest
from pathlib import Path

from fetch_mocvd import build
from mocvd_gan import validate_gan

ROOT=Path(__file__).resolve().parents[1]


class GaNTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=json.loads((ROOT/'manual/mocvd_gan_financials.json').read_text(encoding='utf-8'))
        facts=json.loads((ROOT/'data/_mocvd/facts.json').read_text(encoding='utf-8'))
        manual=json.loads((ROOT/'manual/mocvd.json').read_text(encoding='utf-8'))
        cls.docs=build(facts,manual,gan=cls.snapshot)

    def test_powi_original_annual_anchors(self):
        rows=self.snapshot['companies']['powi']
        self.assertEqual(len(rows['quarters']),50)
        first=rows['annuals'][0]
        self.assertEqual((first['year'],first['revenue'],first['profit'],first['capex']),
                         (2014,348.797,55.796,23.071))
        last=rows['quarters'][-1]
        self.assertEqual((last['date'],last['revenue'],last['profit'],last['capex']),
                         ('2026-06-30',118.939,8.9,4.302))

    def test_powi_quarter_conservation_with_disclosed_restatement(self):
        meta=self.snapshot['companies']['powi']
        for annual in meta['annuals']:
            quarters=[r for r in meta['quarters'] if r['year']==annual['year']]
            self.assertEqual(len(quarters),4)
            for metric in ['revenue','profit','capex']:
                difference=annual[metric]-sum(r[metric] for r in quarters)
                # 2017 10-K note 2: 2015 revenue restated on ASU2014-09
                # adoption, 343.989 -> 344.609 million. Do not invent a quarter.
                expected=.620 if annual['year']==2015 and metric=='revenue' else 0
                self.assertAlmostEqual(difference,expected,places=3)
        self.assertIn('0.620',self.docs['mocvd_powi_revenue']['description'])
        self.assertIn('특허소송',self.docs['mocvd_powi_profit']['description'])
        self.assertFalse(self.docs['mocvd_powi_profit'].get('point_annotations'))

    def test_ifx_operating_income_is_not_segment_result_or_ebit(self):
        rows=self.snapshot['companies']['infineon']
        self.assertEqual(len(rows['annuals']),12)
        self.assertEqual((rows['annuals'][0]['revenue'],rows['annuals'][0]['profit']),(4320,525))
        self.assertEqual((rows['annuals'][-1]['revenue'],rows['annuals'][-1]['profit']),(14662,1515))
        self.assertEqual((rows['quarters'][-1]['revenue'],rows['quarters'][-1]['profit']),(4172,594))
        for metric in ['revenue','profit','capex']:
            d=self.docs['mocvd_infineon_'+metric]
            self.assertEqual(d['default_view'],'annual')
            self.assertEqual(d['frequency'],'yearly')
            self.assertEqual(len(next(iter(d['series_views']['quarter']['series'].values()))),2)

    def test_inno_public_history_limits_and_cash_scope(self):
        meta=self.snapshot['companies']['innoscience']
        self.assertEqual(meta['founded'],'2017-07-21')
        self.assertEqual(len(meta['annuals']),5)
        self.assertEqual(len(meta['halfyears']),7)
        first=meta['annuals'][0]
        self.assertEqual((first['year'],first['revenue'],first['profit'],first['capex']),
                         (2021,68.215,-1007.207,1121.280))
        self.assertEqual(meta['halfyears'][-1]['capex'],398.248)
        for metric in ['revenue','profit','capex']:
            doc=self.docs['mocvd_innoscience_'+metric]
            self.assertEqual(set(doc['series_views']),{'half','annual'})
            self.assertEqual(doc['series_views']['half']['frequency'],'semiannual')
            self.assertFalse(doc['series_views']['half']['quarterly_profit_summary'])
            self.assertIn('2021',doc['description'])
        self.assertIn('무형자산',next(iter(self.docs['mocvd_innoscience_capex']['series'])))

    def test_inno_halves_conserve_every_annual_metric(self):
        meta=self.snapshot['companies']['innoscience']
        for annual in meta['annuals'][2:]:
            halves=[r for r in meta['halfyears'] if r['year']==annual['year']]
            self.assertEqual([r['half'] for r in halves],[1,2])
            for metric in ['revenue','profit','capex']:
                self.assertAlmostEqual(sum(r[metric] for r in halves),annual[metric],places=3)
                self.assertEqual(halves[1]['refs'][metric]['calculation'],'FY minus H1')
                self.assertEqual(len(halves[1]['refs'][metric]['supporting_sources']),2)

    def test_original_currency_sources_and_invalid_observations(self):
        for company,unit in [('powi','백만 USD'),('innoscience','백만 CNY'),('infineon','백만 EUR')]:
            self.assertEqual(self.snapshot['companies'][company]['unit'],unit)
            for key in ['annuals','quarters','halfyears']:
                for row in self.snapshot['companies'][company].get(key,[]):
                    for metric,ref in row['refs'].items():
                        self.assertTrue(ref['url'].startswith('https://'))
                        if company=='innoscience':
                            self.assertGreater(ref['pdf_page'],0)
                            self.assertEqual(len(ref['pdf_sha256']),64)
        for value in [float('nan'),-1]:
            invalid=copy.deepcopy(self.snapshot)
            invalid['companies']['innoscience']['annuals'][0]['capex']=value
            with self.assertRaises(ValueError):validate_gan(invalid)


if __name__=='__main__':unittest.main()

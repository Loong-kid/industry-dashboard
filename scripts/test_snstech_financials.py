import copy
import json
import unittest
from aggregate_snstech_financials import INPUT, build


class FinancialHistory(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads(INPUT.read_text(encoding='utf8'))
        self.docs=build(self.raw,[])

    def test_continuing_operations_and_cash_flow_quarters(self):
        rows=self.raw['quarters']
        self.assertEqual((len(rows),rows[0]['date'],rows[-1]['date']),(50,'2014-03-31','2026-06-30'))
        self.assertEqual(rows[0]['revenue'],11363655165)
        self.assertEqual(rows[1]['profit'],1596913340)
        self.assertEqual(sum(r['capex'] for r in rows if r['year']==2014),3124555551)
        self.assertEqual(rows[1]['capex'],1204777103-500086165)
        self.assertEqual(len(rows[1]['sources']['capex']),2)
        doc=self.docs['snstech_operating_profit']
        self.assertEqual(doc['comparison_dates']['2015-03-31']['year_ago'],'2014-03-31')
        self.assertTrue(doc['quarterly_profit_summary'])

    def test_reported_reconciliation_differences_are_explicit(self):
        differences={(c['year'],c['metric']):c['difference'] for c in self.raw['annual_checks'] if c['difference']}
        self.assertEqual(differences,{(2015,'revenue'):95217,(2015,'profit'):-26329076,(2025,'revenue'):-42035269})
        self.assertIn('-26.329076',self.docs['snstech_operating_profit']['note'])
        for check in self.raw['annual_checks']:
            total=sum(r[check['metric']] for r in self.raw['quarters'] if r['year']==check['year'])
            self.assertEqual(total-check['annual'],check['difference'])

    def test_reject_duplicate_future_or_unsourced_facts(self):
        for edit in ['duplicate','future','source']:
            raw=copy.deepcopy(self.raw)
            if edit=='duplicate':raw['quarters'].append(copy.deepcopy(raw['quarters'][0]))
            elif edit=='future':raw['quarters'][0]['date']='2030-03-31'
            else:raw['quarters'][0]['sources']['capex']=[]
            with self.assertRaises(ValueError):build(raw,[])


if __name__=='__main__':unittest.main()

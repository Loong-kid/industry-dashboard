"""Keep CAPEX forecast vintages separate from actuals, capacity and funding."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
import fetch_mocvd_guidance as m

ROOT=Path(__file__).resolve().parents[1]

class GuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=json.loads((ROOT/'manual/mocvd-capex-guidance.json').read_bytes())

    def test_reviewed_history_coverage_and_no_imputed_dollars(self):
        rows=self.seed['rows'];m.validate(rows,self.seed['companies'],'2026-11-18')
        for company in self.seed['companies']:
            periods={(r['reported_fy'],r['reported_quarter']) for r in rows if r['company']==company}
            self.assertEqual(periods,{(y,q) for y in (2025,2026) for q in range(1,5)}|{(2027,1)})
        self.assertTrue(all(r['amount_low'] is None and r['amount_high'] is None for r in rows))

    def test_latest_direction_is_next_quarter_not_budget_revision(self):
        row=next(r for r in self.seed['rows'] if r['id']=='coherent-fy2027-q1')
        self.assertEqual((row['target_start'],row['target_end']),('2026-10-01','2026-12-31'))
        self.assertEqual(row['capex_direction'],'increase_qoq')
        self.assertEqual(m.revision(row,row),'not_comparable')

    def test_order_plan_is_not_cash_and_latest_release_is_not_call(self):
        rows={r['id']:r for r in self.seed['rows']}
        self.assertEqual(rows['lumentum-fy2025-q2']['guidance_kind'],'relative_order')
        self.assertIn('현금',rows['lumentum-fy2025-q2']['summary'])
        self.assertEqual(rows['lumentum-fy2027-q1']['review_status'],'release_only')
        self.assertEqual(rows['lumentum-fy2027-q1']['guidance_kind'],'release_only')

    def budget(self):
        row=copy.deepcopy(self.seed['rows'][0]);row.update(guidance_kind='range',amount_low=100,amount_high=200,
            target_start='2026-07-01',target_end='2027-06-30',basis='전사 현금 CAPEX',review_status='call_reviewed')
        return row

    def test_invalid_forecast_and_unreviewed_amounts_rejected(self):
        valid=self.budget();m.validate([valid],self.seed['companies'],'2026-11-18')
        for change in [dict(amount_low=-1),dict(amount_low=201),dict(amount_high=float('nan')),
                       dict(target_start=None),dict(basis='production capacity'),dict(currency='CNY'),
                       dict(amount_unit='billion'),dict(review_status='pending'),dict(guidance_kind='point'),
                       dict(announced_at='2099-01-01'),dict(quote=' '.join(['word']*21))]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                m.validate([dict(valid,**change)],self.seed['companies'],'2026-11-18')
        with self.assertRaises(ValueError):m.validate([dict(valid,guidance_kind='capacity_only')],self.seed['companies'],'2026-11-18')

    def test_revisions_require_same_target_scope_currency_and_units(self):
        row=self.budget()
        for change,result in [(dict(amount_low=110,amount_high=210),'raised'),
                              (dict(amount_low=90,amount_high=190),'lowered'),
                              (dict(amount_low=90,amount_high=210),'range_changed'),({},'maintained'),
                              (dict(target_end='2027-12-31'),'not_comparable'),
                              (dict(basis='InP 전용 CAPEX'),'not_comparable'),
                              (dict(currency='CNY'),'not_comparable'),
                              (dict(amount_unit='billion'),'not_comparable')]:
            self.assertEqual(m.revision(row,dict(row,**change)),result)

    def test_candidate_excludes_actual_tables_and_revenue_only_guidance(self):
        html='<p>We spent $776 million in capital expenditures.</p><table><tr><td>We expect capital expenditures of $999 million.</td></tr></table><p>We expect revenue growth of $350 million.</p><p>We expect capital expenditures to increase next quarter.</p>'
        self.assertEqual(m.forward_sentences(html),['We expect capital expenditures to increase next quarter.'])

    def test_candidates_always_pending_even_if_numeric_or_funded(self):
        for sentence in ['We expect capital expenditures of $200 million.',
                         'We plan capital expenditures with $2 billion funding.',
                         'We expect a $50 million grant for capital spending.']:
            row=m.pending('coherent',{'filed':'2026-11-04','url':'https://example.com/earnings'},
                          '<h1>First Quarter Fiscal 2027 Results</h1><p>'+sentence+'</p>')
            self.assertEqual(row['guidance_kind'],'pending_review');self.assertIsNone(row['amount_low'])
            self.assertEqual(row['date_basis'],'filed')

    def test_no_capex_release_still_queued_for_call_review(self):
        row=m.pending('lumentum',{'filed':'2027-08-10','url':'https://example.com'},
                      '<h1>Fourth Quarter and Full Fiscal Year 2027 Results</h1><p>Revenue reached $2 billion.</p>')
        self.assertEqual((row['reported_fy'],row['reported_quarter']),(2027,4))
        self.assertEqual(row['review_status'],'pending');self.assertIsNone(row['amount_high'])

    def test_new_release_retains_reviewed_rows_and_filters_future(self):
        releases=[{'filed':'2027-02-03','url':'https://example.com/new'},
                  {'filed':'2028-02-03','url':'https://example.com/future'}]
        class Response:
            text='<h1>Second Quarter Fiscal 2027 Results</h1><p>We expect capital spending to increase.</p>'
        with patch.object(m,'earnings_exhibits',return_value=releases):
            state=m.refresh(self.seed,{},'2027-02-04',get=lambda _:Response())
        self.assertEqual(len(state['rows']),20)
        self.assertTrue(all(s['latest_seen']=='2027-02-03' for s in state['companies_status'].values()))
        self.assertEqual(next(r for r in state['rows'] if r['id']=='coherent-fy2027-q1')['review_status'],'call_reviewed')

    def test_source_failure_preserves_history_last_success_and_pending(self):
        pending=dict(self.seed['rows'][0],id='pending-example',review_status='pending',guidance_kind='pending_review')
        old={'rows':[pending], 'companies_status':{'coherent':{'ok':True,'last_success':'2026-11-17'}}}
        with patch.object(m,'earnings_exhibits',side_effect=requests.HTTPError('403')):
            state=m.refresh(self.seed,old,'2026-11-18')
        self.assertEqual(len(state['rows']),19)
        self.assertFalse(state['companies_status']['coherent']['ok'])
        self.assertEqual(state['companies_status']['coherent']['last_success'],'2026-11-17')

    def test_publication_and_catalog_keep_actuals_and_future_separate(self):
        doc=json.loads(m.OUT.read_bytes());m.validate(doc['rows'],doc['companies'],m.today())
        self.assertNotIn('series',doc)
        c=json.loads((ROOT/'data/catalog.json').read_bytes());industry=next(i for i in c['industries'] if i['id']=='semicon')
        sections=[s for s in industry['sections'] if s.get('tab')=='mocvd']
        self.assertEqual(sections[0]['table_kind'],'mocvd_guidance')
        ids=[i for s in sections for i in s.get('indicators',[])]
        for id in ('mocvd_capex_guidance','mocvd_lumentum_capex','mocvd_coherent_capex','mocvd_aix_backlog'):self.assertIn(id,ids)
        self.assertNotIn('MOCVD · 수요·공급',(ROOT/'assets/app.js').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()

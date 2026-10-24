import unittest

from fetch_game_financials import parse_sec, parse_dart, dart_company


class FinancialRules(unittest.TestCase):
    def fact(self, start, end, value, filed='2026-05-01', **kwargs):
        return dict(start=start,end=end,val=value,accn='0000000001-26-000001',filed=filed,form='10-K',**kwargs)

    def document(self, facts, currency='USD', tag='RevenueFromContractWithCustomerExcludingAssessedTax'):
        return dict(cik=1,facts={'us-gaap':{tag:{'units':{currency:facts}}}})

    def test_march_fiscal_year_and_q4(self):
        # Comparative fy labels cannot anchor a fiscal year; actual dates can.
        facts=[self.fact('2025-04-01','2025-06-30',10e6,fy=2027),
               self.fact('2025-04-01','2025-12-31',45e6),
               self.fact('2025-04-01','2026-03-31',80e6),
               self.fact('2026-04-01','2026-06-30',20e6,filed='2026-08-01')]
        rows=parse_sec(self.document(facts),dict(cik=1,currency='USD',fiscal_start=4),'2026-10-25')
        q4=next(r for r in rows if r['period']=='FY2026 Q4')
        self.assertEqual(q4['revenue'],35)
        self.assertEqual(q4['start'],'2026-01-01')
        self.assertEqual(len(q4['refs']['revenue']['components']),2)
        self.assertEqual(next(r for r in rows if r['date']=='2026-06-30')['period'],'FY2027 Q1')

    def test_never_divide_annual_or_use_future_filing(self):
        facts=[self.fact('2025-01-01','2025-12-31',100e6),self.fact('2025-10-01','2025-12-31',9e6,filed='2027-01-01')]
        rows=parse_sec(self.document(facts),dict(cik=1,currency='USD',fiscal_start=1),'2026-10-25')
        self.assertEqual([r['kind'] for r in rows],['annual'])

    def test_currency_restated_value_and_direct_quarter_preference(self):
        facts=[self.fact('2025-01-01','2025-03-31',10e6),self.fact('2025-01-01','2025-03-31',12e6,filed='2026-06-01'),
               self.fact('2025-01-01','2025-06-30',30e6),self.fact('2025-04-01','2025-06-30',17e6)]
        doc=self.document(facts,'CNY');doc['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']['units']['USD']=[self.fact('2025-01-01','2025-03-31',999e6)]
        rows=parse_sec(doc,dict(cik=1,currency='CNY',fiscal_start=1),'2026-10-25')
        self.assertEqual([r['revenue'] for r in rows],[12,17])

    def test_no_difference_between_incompatible_taxonomies(self):
        doc=self.document([self.fact('2025-01-01','2025-12-31',100e6)])
        doc['facts']['ifrs-full']={'Revenue':{'units':{'USD':[self.fact('2025-01-01','2025-09-30',60e6)]}}}
        rows=parse_sec(doc,dict(cik=1,currency='USD',fiscal_start=1),'2026-10-25')
        self.assertFalse(any(r.get('period')=='FY2025 Q4' for r in rows))

    def test_dart_three_months_distinct_from_cumulative(self):
        def row(tag,amount,cumulative,sj='IS'):
            return dict(sj_div=sj,currency='KRW',account_id=tag,account_nm='',thstrm_amount=amount,thstrm_add_amount=cumulative,rcept_no='20260814000001')
        direct,ytd=parse_dart([row('ifrs-full_Revenue','300,000,000','500,000,000'),row('dart_OperatingIncomeLoss','(20,000,000)','10,000,000'),
                               row('ifrs-full_ProfitLoss','-10,000,000','20,000,000'),row('ifrs-full_Revenue','999,000,000','999,000,000','CF')],2026,2)
        self.assertEqual(direct['revenue'],300)
        self.assertEqual(ytd['revenue'],500)
        self.assertEqual(direct['operating_profit'],-20)
        self.assertEqual(direct['net_income'],-10)
        self.assertEqual(direct['start'],'2026-04-01')

    def test_dart_q4_and_failure_preserves_previous_period(self):
        class Response:
            def raise_for_status(self):
                pass
            def __init__(self, doc):
                self.doc=doc
            def json(self):
                return self.doc
        class Session:
            def get(self, url, params, timeout):
                if params['reprt_code']=='11012':
                    raise TimeoutError('must not expose URL containing key')
                if params['bsns_year']!=2025 or params['reprt_code']=='11013':
                    return Response({'status':'013'})
                annual=params['reprt_code']=='11011'
                return Response({'status':'000','list':[dict(sj_div='IS',currency='KRW',account_id='ifrs-full_Revenue',account_nm='',
                    thstrm_amount='1000000000' if annual else '200000000',thstrm_add_amount='' if annual else '700000000',rcept_no='20260314000001')]})
        prior=[dict(kind='quarter',date='2025-06-30',revenue=123,source='OpenDART')]
        rows,failures=dart_company(Session(),'not-a-real-key','12345678',{},'2026-10-25',prior)
        self.assertEqual(next(r for r in rows if r.get('period')=='FY2025 Q4')['revenue'],300)
        self.assertEqual(next(r for r in rows if r['date']=='2025-06-30')['revenue'],123)
        self.assertTrue(failures)
        self.assertFalse(any('key' in e or 'https://' in e for e in failures))


if __name__=='__main__':
    unittest.main()

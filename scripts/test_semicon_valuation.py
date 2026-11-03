import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fetch_semicon_valuation import ROOT,load,analytics,collect
from semicon_valuation_sources import price_rows,yahoo_fundamentals,naver_fundamentals,at_or_before,positive_ratio

FIX=ROOT/'scripts/fixtures/semicon_valuation'


class ValuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=load(ROOT/'manual/semicon-valuation/companies.json',[])
        cls.reviews=load(ROOT/'manual/semicon-valuation/ttm_split_reviews.json',{})
        cls.index=load(ROOT/'data/semicon/valuation/valuation_index.json',{})

    def test_completed_session_close_not_dividend_adjusted_price(self):
        p=load(FIX/'LRCX_price.json',{});x=p['chart']['result'][0];end=x['meta']['currentTradingPeriod']['regular']['end']
        rows,_,_=price_rows(p,'LRCX','USD','2026-11-02',end+1)
        self.assertEqual(rows[0][1],round(x['indicators']['quote'][0]['close'][0],6))
        self.assertNotEqual(rows[0][1],round(x['indicators']['adjclose'][0]['adjclose'][0],6))
        # A current trading session must not be published as a completed close.
        from zoneinfo import ZoneInfo
        session=dt.datetime.fromtimestamp(end,ZoneInfo(x['meta']['exchangeTimezoneName'])).date().isoformat()
        earlier,_,_=price_rows(p,'LRCX','USD','2026-11-02',end-1)
        self.assertNotIn(session,[r[0] for r in earlier])
        with self.assertRaisesRegex(ValueError,'identity'):price_rows(p,'LRCX','KRW','2026-11-02',end+1)

    def test_reviewed_split_basis_and_annual_eps_are_not_double_adjusted(self):
        for symbol,split,period,expected,year_end,year_eps in [
            ('LRCX',['2024-10-03',10.],'2023-09-30',2.948,'2024-06-30',2.9),
            ('NVDA',['2024-06-10',10.],'2023-10-31',.758,'2024-01-31',1.19),
            ('8035.T',['2026-09-29',5.],'2025-09-30',235.52,'2026-03-31',250.176)]:
            p=load(FIX/(symbol+'_fund.json'),{});f=yahoo_fundamentals(p,symbol,'2026-11-02',[split],self.reviews[symbol]);values={r[0]:r[1] for r in f['eps']}
            self.assertAlmostEqual(values[period],expected);self.assertAlmostEqual(values[year_end],year_eps)
        p=load(FIX/'LRCX_fund.json',{})
        # If the supplier restates TTM too, recognize the annual anchor and do
        # not divide it again on the next daily collection.
        for s in p['timeseries']['result']:
            if s['meta']['type'][0]=='trailingDilutedEPS':
                for r in s['trailingDilutedEPS']:
                    if r['asOfDate']<='2024-06-30':r['reportedValue']['raw']/=10
        f=yahoo_fundamentals(p,'LRCX','2026-11-02',[['2024-10-03',10]],self.reviews['LRCX'])
        self.assertAlmostEqual(next(r[1] for r in f['eps'] if r[0]=='2023-09-30'),2.948)

    def test_unreviewed_pre_split_ttm_is_not_mixed_with_current_price(self):
        f=yahoo_fundamentals(load(FIX/'LRCX_fund.json',{}),'LRCX','2026-11-02',[['2024-10-03',10]])
        self.assertFalse(any(r[0]=='2023-09-30' for r in f['eps']))
        self.assertTrue(any(r[0]=='2023-06-30' for r in f['eps'])) # completed annual still valid

    def test_consensus_excluded_actual_four_quarters_and_reported_korean_bps(self):
        f=naver_fundamentals(load(FIX/'naver_annual.json',{}),load(FIX/'naver_quarter.json',{}),'005930','2026-11-02')
        self.assertNotIn('2026-09-30',[r[0] for r in f['eps']])
        self.assertEqual(next(r[1] for r in f['eps'] if r[0]=='2026-06-30'),1783+2864+6993+10718)
        self.assertEqual(next(r[1] for r in f['bps'] if r[0]=='2026-06-30'),86052.)
        self.assertNotIn('2026-12-31',[r[0] for r in f['eps']])

    def test_fx_nonpositive_denominators_and_stale_fundamentals(self):
        fund=dict(eps=[['2025-12-31',2,'USD','reported']],bps=[['2025-12-31',-5,'USD','reported']])
        latest,bands=analytics([['2026-01-02',70]],fund,'CNY',{'USDCNY':[['2026-01-02',7.]]})
        self.assertEqual(latest['per'],5.);self.assertIsNone(latest['pbr']);self.assertEqual(bands['pbr'],[])
        self.assertIsNone(positive_ratio(1,0));self.assertIsNone(at_or_before(fund['eps'],'2025-01-01'))
        self.assertIsNone(at_or_before(fund['eps'],'2028-01-01'))
        missing,_=analytics([['2026-01-02',70]],fund,'CNY',{})
        self.assertIsNone(missing['per'])

    def test_coverage_and_cached_documents_reconcile_to_summary(self):
        added=load(ROOT/'manual/korea-equipment/companies.json',{})['companies']
        self.assertEqual(len(self.spec),69+len(added));self.assertEqual(len({c['id'] for c in self.spec}),len(self.spec))
        self.assertEqual(len([c for c in self.spec if c['status']=='listed']),65+len(added))
        self.assertEqual(len(self.index['companies']),len(self.spec))
        for s,c in zip(self.spec,self.index['companies']):
            self.assertEqual(s['id'],c['id'])
            if s['status']!='listed':self.assertIsNone(c['price']);continue
            d=load(ROOT/'data/semicon/valuation'/(s['id']+'.json'),{})
            self.assertEqual(d['symbol'],s['symbol']);self.assertEqual(d['currency'],s['currency'])
            self.assertEqual(d['prices'][-1],[c['price_date'],c['price']])
            latest,bands=analytics(d['prices'],d['fundamentals'],d['currency'],d['fx'])
            self.assertEqual(d['latest'],latest);self.assertEqual(d['bands'],bands)
            self.assertEqual(len(d['prices']),len(dict(d['prices'])))
            if s.get('price_since'):self.assertGreaterEqual(d['prices'][0][0],s['price_since'])
            self.assertTrue(all(r[0]<=d['checked'] for r in d['fundamentals']['eps']+d['fundamentals']['bps']))

    def test_all_registered_financial_companies_linked_without_changing_old_indicators(self):
        catalog=load(ROOT/'data/catalog.json',{});s=next(i for i in catalog['industries'] if i['id']=='semicon')
        summaries={sec['tab']:set(sec['valuation_companies']) for sec in s['sections'] if sec.get('type')=='valuation_summary'}
        for c in self.spec:
            for tab in c['tabs']:self.assertIn(c['id'],summaries[tab])
        for tab,ids in summaries.items():
            charts=[sec['valuation_company'] for sec in s['sections'] if sec.get('tab')==tab and sec.get('valuation_company')]
            charts += [key for sec in s['sections'] if sec.get('tab')==tab and sec.get('type')=='valuation_charts' for key in sec['valuation_companies']]
            self.assertEqual(set(charts),ids);self.assertEqual(len(charts),len(set(charts)))

    def test_source_failure_keeps_verified_data_and_marks_retry(self):
        one=self.spec[0];old=load(ROOT/'data/semicon/valuation'/(one['id']+'.json'),{})
        import requests
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/(one['id']+'.json')).write_text(json.dumps(old),encoding='utf8')
            original_load=load
            def loader(path,fallback):return [one] if path.name=='companies.json' else original_load(path,fallback)
            with patch('fetch_semicon_valuation.OUT',out),patch('fetch_semicon_valuation.CACHE',out/'cache'),patch('fetch_semicon_valuation.load',side_effect=loader),patch('fetch_semicon_valuation.requests.Session') as session:
                session.return_value.get.side_effect=requests.ConnectionError('test outage');collect()
            new=load(out/(one['id']+'.json'),{})
            self.assertEqual(new['prices'],old['prices']);self.assertEqual(new['fundamentals'],old['fundamentals']);self.assertFalse(new['ok']);self.assertTrue(new['errors'])


if __name__=='__main__':unittest.main()

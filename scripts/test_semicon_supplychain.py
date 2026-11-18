"""Regression checks for source eligibility, scope and twenty issuer histories."""
import copy
import unittest
from pathlib import Path
from fetch_semicon_supplychain import ROOT, META, STATE, load, normalize, finalize, documents, overview, offline


class SupplychainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta=load(META,{})
        cls.state=load(STATE,{})

    def test_issuers_and_every_financial_document_is_linked(self):
        specs=self.meta['companies'];self.assertEqual(len(specs),28)
        self.assertEqual(len({c['ticker'] for c in specs.values()}),28)
        industry=next(i for i in load(ROOT/'data/catalog.json',{})['industries'] if i['id']=='semicon')
        docs=documents(self.meta,self.state);self.assertEqual(len(docs),84)
        for key,spec in specs.items():
            tabs=spec['tabs']+(['equipment_summary'] if any(t.startswith('equipment_') for t in spec['tabs']) else [])
            for tab in tabs:
                section=next(s for s in industry['sections'] if s.get('tab')==tab and s.get('valuation_company')=='supplychain_'+key)
                self.assertEqual(section['indicators'],[f'company_supplychain_{key}_{m}' for m in ('revenue','profit','capex')])
            for metric in ('revenue','profit','capex'):
                identifier=f'company_supplychain_{key}_{metric}'
                self.assertEqual(docs[identifier],load(ROOT/f'data/semicon/{identifier}.json',{}))

    def test_blog_selection_excludes_already_registered_issuers(self):
        selection=load(ROOT/'manual/semicon-supplychain/blog-20261118.json',{})
        new={c['ticker'] for c in selection['companies'].values()}
        prior={c['ticker'] for c in selection['already_registered']}
        self.assertEqual(len(new),8);self.assertEqual(len(prior),11)
        self.assertFalse(new&prior);self.assertEqual(len(new|prior),19)
        registry=load(ROOT/'manual/semicon-valuation/companies.json',[])
        for ticker in new|prior:self.assertEqual(sum(c.get('naver_code')==ticker for c in registry),1,ticker)
        for key,spec in selection['companies'].items():
            self.assertEqual(self.meta['companies'][key]['ticker'],spec['ticker'])
        self.assertEqual(selection['companies']['isupetasys']['tabs'],['pcb_boards'])
        self.assertEqual(selection['companies']['newpower']['tabs'],['plasma_components'])

    def test_wonik_retained_company_history_has_a_scope_boundary(self):
        doc=documents(self.meta,self.state)['company_supplychain_wonikholdings_revenue']
        annual=doc['series_views']['annual']['comparison_dates']
        for date in ('2015-12-31','2016-12-31','2017-12-31'):
            if date in annual:self.assertIsNone(annual[date]['year_ago'])
        quarter=doc['series_views']['quarter']['comparison_dates']
        if '2016-06-30' in quarter:self.assertIsNone(quarter['2016-06-30']['quarter_ago'])
        self.assertTrue(any('사업범위' in item['label'] for item in doc['basis_details']))

    def test_reviewed_okins_cash_outflow_sign_keeps_original_inputs(self):
        fixture=load(ROOT/'scripts/fixtures/semicon_supplychain/okins_2021_q1.json',{})
        report=normalize(fixture['list'],2021,1,fixture['corp_code'],'CFS',self.meta['companies']['okins'])
        field=report['fields']['capex']
        self.assertAlmostEqual(field['ytd'],1945.258)
        self.assertAlmostEqual(sum(p['value'] for p in field['inputs'])/1e6,field['ytd'])
        original=next(p for p in field['original_signed_inputs'] if p['account_name']=='공구와기구의 취득')
        self.assertEqual(original['value'],-1362504000.)
        self.assertEqual(fixture['source_url'],'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20210517000923')

    def test_history_has_sources_and_no_stub_quarters_or_spac_filings(self):
        for key,spec in self.meta['companies'].items():
            co=self.state['companies'][key];self.assertTrue(co['annual']);self.assertTrue(co['rows'])
            for kind in ('annual','rows'):
                rows=co[kind];dates=[r['date'] for r in rows]
                self.assertEqual(dates,sorted(set(dates)))
                for row in rows:
                    for metric in ('revenue','profit','capex'):
                        if metric not in row:continue
                        ref=row['refs'][metric]
                        self.assertTrue(ref['url'].startswith('https://dart.fss.or.kr/'))
                        self.assertLessEqual(ref['filed'],co['checked'])
                        self.assertEqual(ref['fs_div'],row['fs_div'])
                        for part in ref['components']:
                            self.assertGreaterEqual(part['filed'],spec.get('minimum_source_filed','0000'))
                    if kind=='rows' and spec.get('first_period_start'):
                        self.assertGreaterEqual(f'{row["year"]}-{row["quarter"]*3-2:02d}-01',spec['first_period_start'])
            rebuilt=copy.deepcopy(co);finalize(rebuilt,spec)
            self.assertEqual(rebuilt['rows'],co['rows'])

    def test_reverse_merger_empty_shell_cannot_override_operating_comparative(self):
        for key in ('lake','neosem'):
            spec=self.meta['companies'][key]
            excluded=normalize([],spec['minimum_primary_year']-1,4,'dummy','CFS',spec)
            self.assertEqual(excluded['fields'],{})
            co=copy.deepcopy(self.state['companies'][key])
            co['reports'].insert(0,excluded);finalize(co,spec)
            self.assertEqual(co['rows'],self.state['companies'][key]['rows'])
            early=co['rows'][0]
            self.assertLess(early['year'],spec['minimum_primary_year'])
            self.assertTrue(early['refs']['revenue']['comparative'])

    def test_actual_post_merger_filing_retains_operating_company_comparative(self):
        fixture=load(ROOT/'scripts/fixtures/semicon_supplychain/lake_2020_q1.json',{})
        report=normalize(fixture['list'],2020,1,fixture['corp_code'],'CFS',self.meta['companies']['lake'])
        fields=report['fields']
        self.assertAlmostEqual(fields['revenue']['value'],7906.526157)
        self.assertAlmostEqual(fields['profit']['value'],-61.388537)
        self.assertAlmostEqual(fields['capex']['ytd'],1279.719915)
        prior=next(r for r in report['comparatives'] if r['year']==2019)
        self.assertAlmostEqual(prior['fields']['revenue']['value'],6774.252656)
        self.assertEqual(prior['fields']['revenue']['filed'],'2020-05-15')

    def test_spin_off_first_three_months_in_later_comparative_are_not_discarded(self):
        fixture=load(ROOT/'scripts/fixtures/semicon_supplychain/simmtech_2016_q3.json',{})
        report=normalize(fixture['list'],2016,3,fixture['corp_code'],'CFS',self.meta['companies']['simmtech'])
        fields=next(r for r in report['comparatives'] if r['year']==2015)['fields']
        self.assertEqual(fields['revenue']['start'],'2015-07-01')
        self.assertAlmostEqual(fields['revenue']['value'],187157.273129)
        self.assertAlmostEqual(fields['profit']['value'],7388.494388)
        row=self.state['companies']['simmtech']['rows'][0]
        self.assertEqual(row['date'],'2015-09-30')
        if row['refs']['capex']['filed']=='2016-11-11':self.assertAlmostEqual(row['capex'],12493.599848)

    def test_comparisons_require_matching_basis_and_full_annual_periods(self):
        for identifier,doc in documents(self.meta,self.state).items():
            key=identifier.removeprefix('company_supplychain_').rsplit('_',1)[0]
            spec=self.meta['companies'][key];co=self.state['companies'][key]
            for kind,view in doc['series_views'].items():
                rows={r['date']:r for r in co['annual' if kind=='annual' else 'rows']}
                for date,comparisons in view['comparison_dates'].items():
                    for previous in comparisons.values():
                        if previous:self.assertEqual(rows[date]['fs_div'],rows[previous]['fs_div'])
                    if kind=='annual' and spec.get('first_period_start') and date[:4] in (spec['first_period_start'][:4],str(int(spec['first_period_start'][:4])+1)):
                        self.assertIsNone(comparisons['year_ago'])

    def test_cash_capex_reconciles_only_with_complete_same_scope_quarters(self):
        checked=0
        for co in self.state['companies'].values():
            for annual in co['annual']:
                quarters=[r for r in co['rows'] if r['year']==annual['year']]
                if 'capex' in annual and len(quarters)==4 and all('capex' in r and r['fs_div']==annual['fs_div'] for r in quarters):
                    # Restated annual cash flow can differ from interim filings;
                    # compare only quarters derived from this same annual YTD.
                    q4=quarters[-1]['refs']['capex']
                    if q4['components'][0]['url']!=annual['refs']['capex']['url']:continue
                    if any(r['refs']['capex']['components'][0]['filed']>annual['refs']['capex']['filed'] for r in quarters):continue
                    self.assertAlmostEqual(sum(r['capex'] for r in quarters),annual['capex'],places=4)
                    checked+=1
        self.assertGreater(checked,50)

    def test_failed_source_preserves_last_success(self):
        one='soulbrain';meta=dict(self.meta,companies={one:self.meta['companies'][one]})
        result=offline(meta,self.state,self.state['checked'],{one:{'ok':False}},cache=ROOT/'nonexistent',normalize_report=normalize)
        self.assertFalse(result['companies'][one]['ok'])
        self.assertEqual(result['companies'][one]['rows'],self.state['companies'][one]['rows'])
        self.assertEqual(result['companies'][one]['fetched'],self.state['companies'][one]['fetched'])

    def test_business_snapshot_units_and_scope_are_explicit(self):
        doc=overview(self.meta,self.state)
        for company in doc['companies']:
            mix=company['business_mix'];self.assertIsNotNone(mix,company['id'])
            self.assertTrue(mix['period_label']);self.assertTrue(mix['scope']);self.assertTrue(mix['unit'])
            self.assertTrue(mix['source_url'].startswith('https://dart.fss.or.kr/'))
            self.assertTrue(mix['rows']);self.assertTrue(mix['reviewed'])
            shares=[r['share_pct'] for r in mix['rows'] if r['share_pct'] is not None]
            if len(shares)==len(mix['rows']):self.assertAlmostEqual(sum(shares),100,delta=.3)


if __name__=='__main__':unittest.main()

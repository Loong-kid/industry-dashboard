"""Korean equipment classification, fiscal spin-offs and signed cash sources."""
import copy,datetime as dt,json,math,tempfile,unittest
from pathlib import Path
from fetch_korea_equipment import ROOT,normalize,first_period,build,universe
from fetch_cosmetics import offline
from fetch_rings import validate

def read(path):return json.loads(path.read_text(encoding='utf-8'))


class KoreanEquipment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta=read(ROOT/'manual/korea-equipment/companies.json');cls.state=read(ROOT/'data/semicon/korea_equipment_state.json')

    def test_classification_matches_actual_equipment_not_ticker_name(self):
        expected={'jusung':['equipment_frontend'],'eo':['equipment_frontend','equipment_packaging'],
          'wonikips':['equipment_frontend'],'pskholdings':['equipment_packaging'],'hpsp':['equipment_frontend'],
          'psk':['equipment_frontend'],'eugene':['equipment_frontend'],'tes':['equipment_frontend'],
          'park':['equipment_inspection'],'kohyoung':['equipment_inspection']}
        self.assertEqual({k:v['tabs'] for k,v in self.meta['companies'].items()},expected)
        self.assertEqual(len({v['ticker'] for v in self.meta['companies'].values()}),10)
        self.assertNotEqual(self.meta['companies']['psk']['ticker'],self.meta['companies']['pskholdings']['ticker'])
        doc=universe(self.meta,self.state);self.assertEqual(len(doc['companies']),11)
        self.assertEqual([c['id'] for c in doc['companies'] if c['existing']],['hanmi'])

    def test_market_cap_snapshot_selects_the_ten_large_new_candidates(self):
        snapshot=read(ROOT/'manual/korea-equipment/market-cap-selection.json')
        candidates=sorted([c for c in snapshot['candidates'] if c['ticker']!='042700'],key=lambda c:c['market_cap_krw'],reverse=True)
        expected={c['ticker'] for c in candidates[:10]}
        self.assertEqual({c['ticker'] for c in self.meta['companies'].values()},expected)
        self.assertTrue(all(c['source_url'].startswith('https://finance.naver.com/') for c in candidates))
        self.assertTrue(all(c['traded_at'].startswith('2026-11-03') for c in candidates))

    def test_original_signed_cash_disbursements_are_not_negative_capex(self):
        for year,q,expected in [(2024,4,30999.739416),(2025,1,4048.988677)]:
            f=read(ROOT/f'scripts/fixtures/korea_equipment/jusung-{year}-q{q}.json');raw=copy.deepcopy(f['items']);corp=raw[0]['corp_code']
            report=normalize(raw,year,q,corp,'CFS',self.meta['companies']['jusung']);cash=report['fields']['capex']
            self.assertAlmostEqual(cash['ytd'],expected)
            self.assertAlmostEqual(sum(x['value'] for x in cash['original_signed_inputs'] if x['value'] is not None)/1e6,-expected)
            self.assertAlmostEqual(sum(x['value'] for x in cash['inputs'] if x['value'] is not None)/1e6,expected)
            self.assertEqual(raw,f['items'])
        co=self.state['companies']['jusung'];annual=next(r for r in co['annual'] if r['year']==2024)
        self.assertAlmostEqual(annual['capex'],30999.739416)

    def test_first_three_months_after_split_are_actual_quarters(self):
        for key,year,expected in [('wonikips',2016,4963.131916),('psk',2019,228.532061)]:
            spec=self.meta['companies'][key];fixture=read(ROOT/f'scripts/fixtures/korea_equipment/{key}-{year}-q2.json')
            report=normalize(fixture['items'],year,2,fixture['items'][0]['corp_code'],'CFS',spec)
            self.assertIsNotNone(report['fields']['revenue']['value'])
            co=self.state['companies'][key];row=next(r for r in co['rows'] if r['date']==f'{year}-06-30')
            self.assertAlmostEqual(row['capex'],expected)
            self.assertEqual(row['refs']['capex']['components'][0]['start'],spec['first_period_start'])
            self.assertTrue(all(r['date']>=spec['first_period_start'] for r in co['rows']+co['annual']))
            self.assertFalse(any(r['date']==f'{year}-03-31' for r in co['rows']))

    def test_published_accounts_sources_and_views_reconcile(self):
        self.assertEqual(set(self.state['companies']),set(self.meta['companies']))
        asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
        docs=build(self.meta,self.state);self.assertEqual(len(docs),30)
        for key,co in self.state['companies'].items():
            validate(co,asof)
            self.assertEqual(co['entity']['ticker'],self.meta['companies'][key]['ticker'])
            for metric in ['revenue','profit','capex']:
                doc=docs[f'company_kr_equipment_{key}_{metric}']
                self.assertEqual(doc,read(ROOT/'data/semicon'/(doc['id']+'.json')))
                self.assertEqual(doc['unit'],'KRW 백만');self.assertEqual(set(doc['series_views']),{'quarter','annual'})
                for kind,rows in [('quarter',co['rows']),('annual',co['annual'])]:
                    series=next(iter(doc['series_views'][kind]['series'].values()));values=dict(series)
                    for row in rows:
                        self.assertEqual(values[row['date']],row.get(metric))
                        if metric in row:
                            for ref in row['refs'][metric]['components']:
                                self.assertTrue(ref['url'].startswith('https://dart.fss.or.kr/'))
                                self.assertLessEqual(ref['filed'],asof)
        self.assertNotIn('crtfc_key',json.dumps(self.state))

    def test_failure_preserves_each_company_and_marks_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            failed=offline(self.meta,self.state,self.state['checked'],{k:{'ok':False} for k in self.meta['companies']},cache=Path(temp),normalize_report=normalize)
        for key,co in failed['companies'].items():
            self.assertFalse(co['ok']);self.assertEqual(co['rows'],self.state['companies'][key]['rows'])

    def test_catalog_and_valuation_scope_no_duplicates(self):
        semicon=next(i for i in read(ROOT/'data/catalog.json')['industries'] if i['id']=='semicon')
        registry=read(ROOT/'manual/semicon-valuation/companies.json');registered={c['id']:c for c in registry}
        for key,spec in self.meta['companies'].items():
            identifier='kr_equipment_'+key;expected=['equipment_summary']+spec['tabs']
            self.assertEqual(registered[identifier]['tabs'],expected)
            for tab in expected:
                sections=[s for s in semicon['sections'] if s.get('tab')==tab and s.get('valuation_company')==identifier]
                self.assertEqual(len(sections),1)
                self.assertEqual(sections[0]['indicators'],[f'company_kr_equipment_{key}_{m}' for m in ['revenue','profit','capex']])
        self.assertNotIn('??',json.dumps(semicon,ensure_ascii=False))


if __name__=='__main__':unittest.main()

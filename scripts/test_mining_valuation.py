import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fetch_semicon_valuation import ROOT, load, fx_quote, analytics
from fetch_mining_valuation import OUT, REGISTRY, INDEX, REUSED_IDS, combine_index, run
from semicon_valuation_sources import converted


class MiningValuationTests(unittest.TestCase):
    def test_all_ten_companies_have_prices_and_both_reported_bands(self):
        specs=load(REGISTRY,[])
        ids=[c['id'] for c in load(ROOT/'manual/mining/companies.json',{})['companies']]
        index=load(OUT/INDEX,{})
        self.assertEqual([c['id'] for c in index['companies']],ids)
        self.assertEqual(set(c['id'] for c in specs)|REUSED_IDS,set(ids))
        self.assertEqual(len(specs),8)
        self.assertEqual(index['auto_collect_time'],'08:25')
        for c in index['companies']:
            path=ROOT/'data'/c.get('data_path','commodities/mining-valuation')/(c['id']+'.json')
            d=load(path,{})
            self.assertEqual(c['symbol'],d['symbol']);self.assertEqual(c['currency'],d['currency'])
            self.assertGreater(len(d['prices']),1000)
            self.assertEqual(d['prices'][-1],[c['price_date'],c['price']])
            latest,bands=analytics(d['prices'],d['fundamentals'],d['currency'],d['fx'])
            self.assertEqual(latest,d['latest']);self.assertEqual(bands,d['bands'])
            self.assertTrue(d['fundamentals']['eps']);self.assertTrue(d['fundamentals']['bps'])
            self.assertTrue(bands['per']);self.assertTrue(bands['pbr'])
            self.assertEqual(len(d['prices']),len(dict(d['prices'])))
            for field in ('eps','bps'):
                rows=d['fundamentals'][field]
                self.assertEqual([r[0] for r in rows],sorted(set(r[0] for r in rows)))
                self.assertTrue(all(r[0]<=d['checked'] for r in rows))

    def test_pence_scaling_and_native_reporting_currencies(self):
        self.assertEqual(fx_quote('USD','GBp'),('USDGBP','GBP',100,False))
        self.assertEqual(fx_quote('USD','AUD'),('AUD','AUD',1,False))
        self.assertEqual(fx_quote('GBP','GBp'),('GBPGBP','GBP',100,True))
        self.assertEqual(fx_quote('USD','USD'),('USDUSD','USD',1,True))
        self.assertAlmostEqual(converted(['2026-01-01',2,'USD'],'2026-01-02','GBp',{'USDGBp':[['2026-01-02',75]]}),150)
        for key in ('rio','glen'):
            d=load(OUT/(key+'.json'),{})
            self.assertEqual(d['currency'],'GBp')
            self.assertTrue(all(r[2]=='USD' for r in d['fundamentals']['eps']))
            # USD/GBP times 100, not unscaled GBP or a fictional USDGBp FX ticker.
            self.assertTrue(all(40<r[1]<120 for r in d['fx']['USDGBp']))
            self.assertIsNotNone(d['latest']['per']);self.assertIsNotNone(d['latest']['pbr'])
        self.assertEqual(load(OUT/'bhp.json',{})['symbol'],'BHP.AX')
        self.assertEqual(load(OUT/'barrick.json',{})['symbol'],'ABX.TO')
        self.assertEqual(load(OUT/'zijin.json',{})['fundamentals']['eps'][-1][2],'CNY')

    def test_reused_copper_data_is_not_copied_or_overwritten(self):
        index=load(OUT/INDEX,{})
        reused=[c for c in index['companies'] if c['id'] in REUSED_IDS]
        self.assertEqual(len(reused),2)
        for c in reused:
            self.assertEqual(c['data_path'],'commodities/valuation')
            self.assertFalse((OUT/(c['id']+'.json')).exists())
            original=load(ROOT/'data/commodities/valuation/copper_valuation_index.json',{})
            base=next(row for row in original['companies'] if row['id']==c['id'])
            self.assertEqual({k:v for k,v in c.items() if k!='data_path'},base)

    def test_source_failure_preserves_native_values_fx_and_shared_copper_files(self):
        import requests
        old=load(OUT/'rio.json',{})
        copper=ROOT/'data/commodities/valuation/scco.json';before=copper.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'rio.json').write_text(json.dumps(old),encoding='utf8')
            specs=out/'specs.json';specs.write_text(json.dumps([next(s for s in load(REGISTRY,[]) if s['id']=='rio')]),encoding='utf8')
            def partial(rows):return rows
            with patch('fetch_mining_valuation.OUT',out),patch('fetch_mining_valuation.REGISTRY',specs), \
                 patch('fetch_mining_valuation.combine_index',side_effect=partial), \
                 patch('fetch_semicon_valuation.requests.Session') as session:
                session.return_value.get.side_effect=requests.ConnectionError('test outage')
                run()
            saved=load(out/'rio.json',{})
            for field in ('prices','fundamentals','fx','price_fetched','financial_fetched'):
                self.assertEqual(saved[field],old[field])
            self.assertFalse(saved['ok']);self.assertTrue(saved['errors'])
        self.assertEqual(copper.read_bytes(),before)

    def test_every_mining_financial_section_links_its_valuation_once(self):
        commodity=next(i for i in load(ROOT/'data/catalog.json',{})['industries'] if i['id']=='commodities')
        sections=[s for s in commodity['sections'] if s['tab']=='mining']
        summary=next(s for s in sections if s.get('type')=='valuation_summary')
        linked=[s['valuation_company'] for s in sections if s.get('valuation_company')]
        self.assertEqual(summary['valuation_companies'],linked)
        self.assertEqual(len(linked),10);self.assertEqual(len(set(linked)),10)
        for section in sections:
            if section.get('valuation_company'):
                self.assertEqual(len(section['indicators']),3)
                self.assertEqual(section['anchor'],'mining-'+section['valuation_company'])


if __name__=='__main__':unittest.main()

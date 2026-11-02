import copy
import datetime as dt
from pathlib import Path
import unittest
from unittest.mock import patch

import fetch_cosmetics as cosmetics
import fetch_cosmetics_global as global_cosmetics
from cosmetics_global_sources import loreal_release,shiseido_statement
from ring_financial_sources import accounts

ROOT=Path(__file__).resolve().parents[1]
META=cosmetics.read(ROOT/'manual/cosmetics/companies.json')
STATE=cosmetics.read(ROOT/'data/cosmetics/state.json')
GLOBAL=cosmetics.read(ROOT/'data/cosmetics/global_state.json')
GLOBAL_META=cosmetics.read(ROOT/'manual/cosmetics/global-companies.json')
ASOF=max(dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat(),'2026-11-02')


class CosmeticsFinancials(unittest.TestCase):
    def test_nine_issuers_and_value_chain_scopes(self):
        self.assertEqual(list(META['companies']),['amorepacific','lghnh','apr','clio','vt','cosmax','kolmar_korea','cosmecca','silicon2'])
        self.assertEqual([sum(s['category']==c for s in META['companies'].values()) for c in ['brands','odm','distribution']],[5,3,1])
        self.assertEqual(META['companies']['amorepacific']['ticker'],'090430')
        self.assertEqual(META['companies']['cosmax']['ticker'],'192820')
        self.assertIn('음료',META['companies']['lghnh']['scope'])
        self.assertIn('제약',META['companies']['kolmar_korea']['scope'])
        self.assertIn('디바이스',META['companies']['apr']['scope'])
        for key,co in STATE['companies'].items():
            self.assertEqual(co['entity']['ticker'],META['companies'][key]['ticker'])
            cosmetics.validate(co,ASOF)
            self.assertLessEqual(co['annual'][0]['year'],2021)
            self.assertIn(2025,[r['year'] for r in co['annual']])
            self.assertTrue(all(r['year']<int(ASOF[:4]) for r in co['annual']))

    def test_provisional_income_is_not_capex_and_confirmed_replaces_it(self):
        fixtures=cosmetics.read(ROOT/'manual/cosmetics/preliminary-fixtures.json')
        for key in ['amorepacific','apr']:
            row=fixtures[key]
            self.assertTrue(row['provisional'])
            self.assertNotIn('capex',row)
            confirmed=copy.deepcopy(row);confirmed.pop('provisional')
            self.assertEqual(cosmetics.with_preliminaries([confirmed],[row],[row],ASOF),[])
            future=copy.deepcopy(row)
            for ref in future['refs'].values():ref['filed']='2099-01-01'
            self.assertEqual(cosmetics.with_preliminaries([],[],[future],ASOF),[])
        apr=fixtures['apr']
        self.assertEqual((apr['revenue'],apr['profit']),(773115,160640))
        amore=fixtures['amorepacific']
        self.assertEqual((amore['revenue'],amore['profit']),(1129493,115243))
        from shipbuilding_equipment_sources import provisional
        for key,row in fixtures.items():
            receipt=row['refs']['revenue']['url'].split('rcpNo=')[1]
            parsed=provisional((ROOT/'manual/cosmetics'/(key+'-2026-q3-preliminary.html')).read_bytes(),receipt,'CFS','2026-11-02',required_metrics=('revenue','profit'))
            for metric in ['revenue','profit']:self.assertEqual(parsed[metric],row[metric])

    def test_cumulative_only_is_not_misreported_as_a_quarter(self):
        fixture=cosmetics.read(ROOT/'manual/cosmetics/statement-fixtures.json')
        raw=copy.deepcopy(fixture['cosmax-2026-q2-CFS.json']['list'])
        from ring_financial_sources import choose
        for metric in ['revenue','profit']:
            row=choose(raw,metric)
            row['thstrm_amount']=row['thstrm_add_amount']
            row['frmtrm_q_amount']=row['frmtrm_add_amount']
        report=cosmetics.normalize(raw,2026,2,STATE['companies']['cosmax']['entity']['corp_code'],'CFS',META['companies']['cosmax'])
        for metric in ['revenue','profit']:self.assertIsNone(report['fields'][metric]['value'])
        self.assertFalse(any('revenue' in r for r in accounts([report],ASOF)['rows']))

    def test_official_cosmax_income_and_cash_flow_anchors(self):
        fixture=cosmetics.read(ROOT/'manual/cosmetics/statement-fixtures.json')
        co=STATE['companies']['cosmax']
        report=cosmetics.normalize(fixture['cosmax-2026-q2-CFS.json']['list'],2026,2,co['entity']['corp_code'],'CFS',META['companies']['cosmax'])
        self.assertAlmostEqual(report['fields']['revenue']['value'],794891.203546,places=6)
        self.assertAlmostEqual(report['fields']['revenue']['ytd'],1476914.529128,places=6)
        self.assertAlmostEqual(report['fields']['profit']['value'],73735.296100,places=6)
        self.assertAlmostEqual(report['fields']['capex']['ytd'],122275.383176,places=6)
        row=next(r for r in co['rows'] if r['date']=='2026-06-30')
        self.assertAlmostEqual(row['capex'],38809.999220,places=6)

    def test_docs_catalog_metric_dates_and_source_links(self):
        docs=cosmetics.build(META,STATE)
        self.assertEqual(len(docs),27)
        industry=next(i for i in cosmetics.read(ROOT/'data/catalog.json')['industries'] if i['id']=='cosmetics')
        all_docs=dict(docs,**global_cosmetics.build(GLOBAL_META,GLOBAL))
        for tab,count in [('overview',36),('brands',15),('odm',9),('distribution',3),('global',9)]:
            linked=[id for section in industry['sections'] if section.get('tab')==tab for id in section['indicators']]
            self.assertEqual(len(linked),count)
            self.assertTrue(set(linked)<=all_docs.keys())
        for id,doc in docs.items():
            self.assertEqual(doc,cosmetics.read(ROOT/'data/cosmetics'/(id+'.json')))
            self.assertEqual(doc['unit'],'KRW 백만')
            self.assertFalse(doc['span_gaps'])
            self.assertTrue(doc['series_views']['annual']['annual_axis'])
            self.assertNotEqual(doc['series_views']['quarter']['series'],doc['series_views']['annual']['series'])
            for v in doc['series_views'].values():
                self.assertTrue(v['source_url'].startswith('https://dart.fss.or.kr/'))
                self.assertNotIn('crtfc_key',str(v))
        for key in ['amorepacific','apr']:
            income=docs[f'company_cosmetics_{key}_revenue']
            self.assertGreaterEqual(income['updated'],'2026-09-30')
            for row in STATE['companies'][key].get('provisional_rows',[]):
                self.assertIn('잠정',income['period_labels'][row['date']])
                self.assertNotIn('capex',row)
                self.assertNotIn(row['date'],docs[f'company_cosmetics_{key}_capex']['period_labels'])

    def test_first_cosmax_period_and_failed_refresh_preserves_history(self):
        doc=cosmetics.build(META,STATE)['company_cosmetics_cosmax_revenue']
        self.assertIn('분할 후 기간',doc['series_views']['annual']['period_labels']['2014-12-31'])
        annual=next(r for r in STATE['companies']['cosmax']['annual'] if r['year']==2014)
        self.assertEqual(annual['refs']['revenue']['start'],'2014-03-01')
        with patch.object(cosmetics,'read',return_value={}):
            failed=cosmetics.offline(META,STATE,ASOF,{})
        for key,co in failed['companies'].items():
            self.assertFalse(co['ok'])
            for field in ['rows','annual','fetched']:self.assertEqual(co[field],STATE['companies'][key][field])

    def test_global_actual_profit_periods_currency_and_sources(self):
        docs=global_cosmetics.build(GLOBAL_META,GLOBAL)
        self.assertEqual(len(docs),9)
        for key,c in GLOBAL['companies'].items():global_cosmetics.validate(c,ASOF)
        for id,doc in docs.items():self.assertEqual(doc,cosmetics.read(ROOT/'data/cosmetics'/(id+'.json')))
        self.assertEqual(docs['company_cosmetics_loreal_revenue']['unit'],'EUR 백만')
        self.assertEqual(docs['company_cosmetics_loreal_profit']['default_view'],'half')
        self.assertNotIn('quarter',docs['company_cosmetics_loreal_profit']['series_views'])
        self.assertNotIn('quarter',docs['company_cosmetics_loreal_capex']['series_views'])
        self.assertEqual(docs['company_cosmetics_estee_profit']['period_labels']['2026-06-30'],'FY2026 Q4')
        shiseido=next(r for r in GLOBAL['companies']['shiseido']['records'] if r['kind']=='annual' and r['date']=='2025-12-31')
        self.assertEqual(shiseido['profit'],-28788)
        self.assertNotEqual(shiseido['profit'],44520) # Core adjusted profit is a different measure.
        self.assertIn('reported_annual',docs['company_cosmetics_shiseido_capex']['series_views'])
        self.assertIn('transition',docs['company_cosmetics_shiseido_revenue']['series_views'])
        from cosmetics_global_sources import quarterly_from_ytd
        co=GLOBAL['companies']['shiseido']
        row=next(r for r in quarterly_from_ytd(co['records'],co['versions']) if r['date']=='2025-09-30')
        self.assertEqual(row['profit'],-51434)
        refs=row['refs']['profit']['components']
        self.assertLessEqual(refs[1]['filed'],refs[0]['filed'])
        self.assertEqual(refs[1]['filed'],'2025-08-06')

    def test_global_official_fixtures_and_no_forecast_or_quarterly_allocation(self):
        fixture=cosmetics.read(ROOT/'manual/cosmetics/global-fixtures.json')
        for case in fixture['loreal']:
            rows=loreal_release(case['html'],case['meta'])
            self.assertEqual({r['kind'] for r in rows},set(case['kinds']))
            target=next(r for r in rows if r['kind']==case['target_kind'])
            for metric,value in case['expected'].items():self.assertAlmostEqual(target[metric],value,places=6)
        case=fixture['shiseido'];rows=shiseido_statement(case['text'],case['meta'])
        current=next(r for r in rows if r['date']=='2025-12-31')
        self.assertEqual((current['revenue'],current['profit'],current['capex']),(969992,-28788,25299))
        # An H1 release creates one actual half, never two estimated quarters.
        half=next(r for r in GLOBAL['companies']['loreal']['records'] if r['kind']=='half' and r['date']=='2026-06-30')
        self.assertEqual((half['profit'],half['capex']),(5063,716.1))


if __name__=='__main__':unittest.main()

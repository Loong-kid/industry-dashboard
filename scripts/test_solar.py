import copy
import json
import math
import re
import unittest
from pathlib import Path

from fetch_solar import ROOT,document
from solar_sources import release_rows,merge_rows


class SolarTests(unittest.TestCase):
    def setUp(self):
        self.meta=json.loads((ROOT/'manual/solar/companies.json').read_text(encoding='utf8'))

    def test_original_currency_parent_profit_and_actual_quarters(self):
        # Extracts from the GAAP tables of SEC 6-K earnings exhibits:
        # CSIQ 0001104659-26-101856 ex99-1; JKS 0001104659-26-101093
        # ex99-2; DQ 0001104659-26-099218 ex99-1 (all Q2 2026).
        expected={'csiq':(1207.714,-71.059,-76.859),'jks':(12356.951,-1436.406,-697.253),'dq':(62.657,-98.076,-81.153)}
        for key,anchor in expected.items():
            raw=(ROOT/f'scripts/fixtures/solar/{key}.html').read_bytes()
            rows=release_rows(raw,self.meta[key],'https://www.sec.gov/source','2026-08-27','2026-10-29')
            r=next(r for r in rows if r['kind']=='quarter' and r['date']=='2026-06-30')
            self.assertEqual(tuple(r[k] for k in ('revenue','profit','netincome')),anchor)
            self.assertEqual(r['start'],'2026-04-01');self.assertEqual(r['currency'],self.meta[key]['currency'])
            self.assertEqual(release_rows(raw,self.meta[key],'source','2026-08-27','2026-08-26'),[])

    def test_ambiguous_statement_and_currency_collision_fail_closed(self):
        from bs4 import BeautifulSoup
        raw=(ROOT/'scripts/fixtures/solar/csiq.html').read_bytes()
        soup=BeautifulSoup(raw,'html.parser');row=next(tr for tr in soup.find_all('tr') if tr.get_text(' ',strip=True).startswith('Net revenues'))
        row.insert_after(copy.copy(row))
        self.assertEqual(release_rows(str(soup),self.meta['csiq'],'source','2026-08-27','2026-10-29'),[])
        rows=release_rows(raw,self.meta['csiq'],'source','2026-08-27','2026-10-29')
        wrong=copy.deepcopy(rows[0]);wrong['currency']='CNY'
        with self.assertRaises(ValueError):merge_rows(rows,[wrong])
        jks=(ROOT/'scripts/fixtures/solar/jks.html').read_text(encoding='utf8')
        renamed=re.sub(r'JinkoSolar\s+Holding','Jinko Holdings',jks)
        parsed=release_rows(renamed,self.meta['jks'],'source','2026-08-27','2026-10-29')
        self.assertTrue(any(r['date']=='2026-06-30' and r['kind']=='quarter' for r in parsed))
        subsidiary=re.sub(r'JinkoSolar\s+Holding','Jinko Solar',jks)
        self.assertFalse(release_rows(subsidiary,self.meta['jks'],'source','2026-08-27','2026-10-29'))

    def test_public_history_views_fx_fiscal_change_and_sources(self):
        state=json.loads((ROOT/'data/solar/state.json').read_text(encoding='utf8'))
        fx=json.loads((ROOT/'data/solar/fx.json').read_text(encoding='utf8'))
        for key,meta in self.meta.items():
            cohort=state['companies'][key];rows=cohort['rows']
            self.assertEqual(len(rows),len({(r['kind'],r['date']) for r in rows}))
            self.assertTrue(any(r['kind']=='quarter' for r in rows));self.assertTrue(any(r['kind']=='annual' for r in rows))
            for r in rows:
                self.assertLessEqual(r['date'],cohort['checked'])
                for metric in ('revenue','profit','netincome'):
                    if metric not in r:continue
                    self.assertTrue(math.isfinite(r[metric]));self.assertLessEqual(r['refs'][metric]['filed'],cohort['checked'])
                    self.assertTrue(r['refs'][metric]['url'].startswith('https://www.sec.gov/'))
            for metric in ('revenue','profit','netincome'):
                doc=document(key,metric,meta,cohort,fx)
                actual=json.loads((ROOT/f'data/solar/company_{key}_{metric}.json').read_text(encoding='utf8'))
                self.assertEqual(doc,actual);self.assertIn('annual',doc['series_views']);self.assertFalse(doc['span_gaps'])
                for kind,view in doc['series_views'].items():
                    values=dict(next(iter(view['series'].values())))
                    for r in rows:
                        if r['kind']!=kind or metric not in r:continue
                        expected=r[metric]
                        if r['currency']!='USD':expected/=fx['periods'][f"{r['currency']}|{r['start']}|{r['date']}"]['local_per_usd']
                        self.assertAlmostEqual(values[r['date']],expected)
        sedg=state['companies']['sedg']['rows']
        self.assertTrue(any(r['kind']=='transition' and r['start']=='2016-07-01' and r['date']=='2016-12-31' for r in sedg))
        self.assertFalse(any(r['kind']=='annual' and r['date']=='2016-12-31' for r in sedg))
        nxt=next(r for r in state['companies']['nxt']['rows'] if r['kind']=='quarter' and r['date']=='2026-07-03')
        self.assertEqual(nxt['period'],'FY2027 Q1')
        jks=document('jks','revenue',self.meta['jks'],state['companies']['jks'],fx)
        self.assertEqual(dict(jks['series_views']['quarter_cny']['series']['매출'])['2026-06-30'],12356.951)
        self.assertEqual(jks['series_views']['quarter_cny']['unit'],'백만 CNY')

    def test_catalog_has_24_charts_across_four_value_chain_groups(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        sector=next(i for i in catalog['industries'] if i['id']=='solar')
        self.assertEqual([t['id'] for t in sector['tabs']],['modules','inverters','trackers','materials'])
        ids=[i for s in sector['sections'] for i in s['indicators']]
        self.assertEqual(len(ids),24);self.assertEqual(len(set(ids)),24)
        for identifier in ids:self.assertTrue((ROOT/f'data/solar/{identifier}.json').exists())
        self.assertEqual(len(self.meta),8)

    def test_missing_fx_never_turns_into_zero_or_healthy_usd(self):
        state=json.loads((ROOT/'data/solar/state.json').read_text(encoding='utf8'))
        doc=document('jks','revenue',self.meta['jks'],state['companies']['jks'],{})
        self.assertFalse(doc['collection_status']['ok'])
        self.assertTrue(all(v is None for d,v in doc['series']['매출']))
        self.assertEqual(dict(doc['series_views']['quarter_cny']['series']['매출'])['2026-06-30'],12356.951)


if __name__=='__main__':unittest.main()

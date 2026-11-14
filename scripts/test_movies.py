import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_movies as collect
import movie_financials as financial
from movie_sources import parse_schedule,parse_worldwide,combine,money

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'scripts/fixtures/movies'


class MovieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheduled=parse_schedule((FIX/'schedule-2026.html').read_bytes(),2026)
        cls.world=parse_worldwide((FIX/'world-2026.html').read_bytes(),2026)

    def test_events_merge_by_source_identity_and_keep_full_calendar_title(self):
        doc=combine(2026,self.scheduled,self.world,[],'2026-11-15')
        film=next(f for f in doc['films'] if f['id']=='/movie/Odyssey-The-(2026)')
        self.assertEqual(len(film['events']),4)
        self.assertEqual({e['date'] for e in film['events']},{'2026-07-17','2026-12-11'})
        self.assertTrue(film['imax_confirmed'])
        film=next(f for f in doc['films'] if f['id']=='/movie/Star-Wars-The-Mandalorian-and-Grogu-(2026)')
        self.assertEqual(film['title'],'Star Wars: The Mandalorian and Grogu')
        self.assertEqual(len({f['id'] for f in doc['films']}),len(doc['films']))

    def test_missing_regional_totals_are_not_zero_or_estimated(self):
        film=dict(id='/movie/Example-(2027)',title='Example',url='https://www.the-numbers.com/movie/Example-(2027)',year=2027,events=[],distributors=[])
        doc=combine(2027,[film],[],[],'2026-11-15')
        self.assertNotIn('worldwide_usd',doc['films'][0])
        self.assertIsNone(money(''))
        self.assertEqual(money('$0'),0)
        self.assertEqual(money('$12,345'),12345)
        with self.assertRaises(ValueError):money('USD 20 unknown')
        with self.assertRaises(ValueError):parse_worldwide('<p>access denied</p>',2026)

    def test_official_undated_ir_entry_does_not_invent_january_first(self):
        review=dict(movie_id='imax-ir:2028:test',title='Undated film',years=[2028],kind='official_ir',source_url='https://investors.imax.com/',note='Expected slate',checked='2026-11-15')
        doc=combine(2028,[],[],[review],'2026-11-15')
        film=doc['films'][0]
        self.assertTrue(film['imax_confirmed']);self.assertIsNone(film['events'][0]['date'])
        self.assertFalse(any(k in film for k in ('worldwide_usd','domestic_usd','international_usd')))

    def test_parent_entity_does_not_sum_joint_cinemark_subsidiary(self):
        filing=dict(accessionNumber='0001193125-26-444406',filingDate='2026-11-03',form='10-Q',url='https://www.sec.gov/Archives/edgar/data/1385280/000119312526444406/cnk-20260930.htm')
        facts=financial.cnk_instance((FIX/'cnk-2026-q3.xml').read_bytes(),filing)
        profit=next(f for f in facts if f['metric']=='profit' and f['start']=='2026-07-01')
        self.assertEqual(profit['val'],206600000)
        self.assertNotEqual(profit['val'],207600000)
        self.assertTrue(all('CnkMember' in f['source_tag'] for f in facts))

    def test_fiscal_year_transition_and_week_based_ends(self):
        self.assertEqual(financial.fiscal_period('mcs','2014-08-28'),(2015,1))
        self.assertEqual(financial.fiscal_period('mcs','2015-05-28'),(2015,4))
        self.assertIsNone(financial.fiscal_period('mcs','2015-12-31'))
        self.assertEqual(financial.fiscal_period('ncmi','2026-01-01'),(2025,4))
        self.assertEqual(financial.fiscal_period('ncmi','2026-10-01'),(2026,3))

    def test_cumulative_quarters_do_not_subtract_different_reporting_starts(self):
        def f(start,end,val):return dict(start=start,end=end,val=val,filed='2026-11-03',accn='x',form='10-Q',tag='test',metric='capex')
        revenue=[dict(f('2026-07-01','2026-09-30',100),metric='revenue'),dict(f('2025-01-01','2025-12-31',400),metric='revenue',form='10-K')]
        facts=revenue+[dict(f('2026-07-01','2026-09-30',10),metric='profit'),f('2026-01-01','2026-09-30',90),f('2026-02-01','2026-06-30',60)]
        # A full earlier CAPEX quarter supplies the metric without making the bad Q3 difference valid.
        facts += [f('2025-01-01','2025-03-31',5),dict(f('2025-01-01','2025-03-31',20),metric='revenue')]
        filings=[dict(form='10-Q',reportDate=e,filingDate='2026-11-03') for e in ['2025-03-31','2026-09-30']]+[dict(form='10-K',reportDate='2025-12-31',filingDate='2026-02-01')]
        rows,_=financial.accounts('imax',facts,filings,'2026-11-15')
        self.assertNotIn('capex',rows[-1])

    def test_source_failure_retains_previous_year_data_and_observation_date(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            prior=dict(years=[dict(year=y,file=f'films_{y}.json',films=1,imax=0,fetched='2026-11-01',checked='2026-11-01',ok=True) for y in range(2025,2029)])
            collect.save(out/'release_index.json',prior)
            with patch.object(collect,'OUT',out),patch.object(collect,'today',return_value='2026-11-15'),patch.object(collect,'download',side_effect=RuntimeError('unavailable')):
                doc=collect.collect_films()
            self.assertFalse(doc['collection_status']['ok'])
            self.assertTrue(all(y['fetched']=='2026-11-01' and not y['ok'] for y in doc['years']))

    def test_offline_rebuild_does_not_claim_a_new_source_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            collect.save(out/'release_index.json',dict(years=[dict(year=2026,file='films_2026.json',films=1,imax=0,fetched='2026-11-01',checked='2026-11-10',ok=False)]))
            def cached(url,*args):return (FIX/('schedule-2026.html' if '/release-schedule/' in url else 'world-2026.html')).read_bytes()
            with patch.object(collect,'OUT',out),patch.object(collect,'today',return_value='2026-11-15'),patch.object(collect,'download',side_effect=cached):
                doc=collect.collect_films(offline=True)
            self.assertEqual(doc['fetched'],'2026-11-01')
            self.assertEqual(doc['years'][0]['checked'],'2026-11-10')
            self.assertFalse(doc['collection_status']['ok'])

    def test_published_accounts_and_chart_documents(self):
        state=collect.load(ROOT/'data/movies/financial_state.json',{})
        self.assertEqual(set(state['companies']),set(financial.SPECS))
        for key,company in state['companies'].items():
            rows=company['rows'];self.assertGreaterEqual(len(rows),45)
            self.assertLessEqual(rows[0]['date'],'2014-06-01')
            self.assertEqual(len({(r['year'],r['quarter']) for r in rows}),len(rows))
            self.assertTrue(all(m in rows[-1] for m in financial.TAGS))
            for id,doc in financial.documents(key,company).items():
                self.assertEqual(doc,collect.load(ROOT/'data/movies'/f'{id}.json',{}))
                self.assertFalse(doc['span_gaps'])
                self.assertIn('annual',doc['series_views'])
                for r in rows:
                    for ref in r['refs'].values():
                        self.assertLessEqual(ref['filed'],company['checked'])
                        self.assertTrue(ref['url'].startswith('https://www.sec.gov/'))
        mcs=collect.load(ROOT/'data/movies/company_mcs_revenue.json',{})
        self.assertIsNone(mcs['comparison_dates']['2016-03-31']['year_ago']) if '2016-03-31' in mcs['comparison_dates'] else None

    def test_published_calendars_keep_year_scope_and_unique_ids(self):
        index=collect.load(ROOT/'data/movies/release_index.json',{})
        self.assertTrue({2014,2026,2027,2028}.issubset({r['year'] for r in index['years']}))
        for meta in index['years']:
            doc=collect.load(ROOT/'data/movies'/meta['file'],{})
            self.assertEqual(doc['year'],meta['year']);self.assertEqual(len(doc['films']),meta['films'])
            self.assertEqual(len({f['id'] for f in doc['films']}),len(doc['films']))
            for film in doc['films']:
                for e in film['events']:
                    if e['date']:self.assertEqual(int(e['date'][:4]),doc['year'])
                self.assertEqual(film['imax_confirmed'],bool(film['imax_evidence']))

    def test_catalog_routes_and_narrow_refresh_workflow(self):
        catalog=collect.load(ROOT/'data/catalog.json',{})
        industry=next(i for i in catalog['industries'] if i['id']=='movies')
        self.assertEqual(industry['default_tab'],'slate')
        self.assertEqual({t['id'] for t in industry['tabs']},{'slate','imax','peers'})
        for section in industry['sections']:
            for id in section['indicators']:self.assertTrue((ROOT/'data/movies'/f'{id}.json').exists())
        workflow=(ROOT/'.github/workflows/update-movies.yml').read_text(encoding='utf8')
        self.assertIn('group: ${{ github.workflow }}',workflow);self.assertIn('git add data/movies/',workflow)
        self.assertNotIn('git add -A',workflow)
        self.assertIn('update-movies',(ROOT/'.github/workflows/publish-data.yml').read_text(encoding='utf8'))


if __name__=='__main__':unittest.main()

"""Accounting, disclosure parsing and retention regressions for power peers."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
import fetch_power_semicon as collector
from fetch_cpu_companies import ROOT, load
from power_semicon_sources import numbers, statement_facts

FIX=ROOT/'scripts/fixtures/power_semicon'


class PowerSemiconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=load(ROOT/'data/semicon/power_semicon_state.json',{})
        cls.seed=load(ROOT/'manual/power_semicon_history.json',{})

    def test_original_stm_tables_preserve_gaap_and_gross_cash_capex(self):
        meta=load(FIX/'sources.json',{})['stm_q3_2026']
        facts=statement_facts((FIX/'stm_q3_2026.html').read_bytes(),meta['url'],meta['filed'],meta['accn'])
        quarter={f['metric']:f['val']/1e6 for f in facts if f['start']>'2026-01-01'}
        ytd={f['metric']:f['val']/1e6 for f in facts if f['start']=='2026-01-01'}
        self.assertEqual(quarter,dict(revenue=3757,profit=367)) # adjusted operating income is 429
        self.assertEqual(ytd,dict(revenue=10339,profit=625,capex=1685))
        q3=self.state['companies']['stm']['rows'][-1]
        self.assertEqual(q3['capex'],683) # net CAPEX is 643; cash PP&E is gross
        self.assertEqual(q3['refs']['capex']['calculation'],'same fiscal-year YTD minus prior YTD')

    def test_source_parses_loss_and_excludes_adjusted_percentage_summaries(self):
        meta=load(FIX/'sources.json',{})['stm_q1_2014']
        facts=statement_facts((FIX/'stm_q1_2014.html').read_bytes(),meta['url'],meta['filed'],meta['accn'])
        self.assertEqual({f['metric']:f['val']/1e6 for f in facts},dict(revenue=1825,profit=-4,capex=114))
        self.assertEqual(numbers('$ ( 1,685 )  — -4 −5 0'),[-1685,0,-4,-5,0])

    def test_complete_quarters_annuals_currency_and_source_coverage(self):
        for key,company in collector.COMPANIES.items():
            c=self.state['companies'][key];rows=c['rows']
            self.assertEqual(len({(r['year'],r['quarter']) for r in rows}),len(rows))
            self.assertEqual(rows[0]['year'],2014)
            self.assertGreaterEqual(len(rows),51)
            self.assertTrue(set(range(2014,2026))<={r['year'] for r in c['annual']})
            for row in rows+c['annual']:
                for metric in ('revenue','profit','capex'):
                    self.assertIsInstance(row[metric],(int,float))
                    self.assertTrue(row['refs'][metric]['url'].startswith('https://www.sec.gov/Archives/edgar/'))
                    self.assertTrue(row['refs'][metric]['components'])
                self.assertGreaterEqual(row['capex'],0)
                self.assertLessEqual(row['date'],c['fetched'])
            for metric in ('revenue','profit','capex'):
                doc=load(ROOT/'data/semicon'/f'company_{key}_{metric}.json',{})
                self.assertEqual(doc['unit'],'USD 백만')
                self.assertEqual(doc['frequency'],'quarterly')
                self.assertIn('annual',doc['series_views'])
                self.assertIn('전사',doc['description'])
                self.assertNotIn('CPU',doc['description'])
            self.assertEqual(company['fiscal_start'],1)

    def test_latest_official_disclosures_and_exact_week_based_ends(self):
        expected={
            'nxp':('2026-09-27',3786,1228,51),
            'onsemi':('2026-10-02',1722.3,378.3,27.8),
            'stm':('2026-09-26',3757,367,683),
        }
        for key,values in expected.items():
            # Validate the reviewed point; allow scheduled collection to advance.
            row=next(r for r in self.state['companies'][key]['rows'] if r['date']==values[0])
            self.assertEqual((row['date'],row['revenue'],row['profit'],row['capex']),values)
        nxp=self.state['companies']['nxp']['rows']
        self.assertEqual(next(r for r in nxp if (r['year'],r['quarter'])==(2015,3))['date'],'2015-10-04')
        q4=next(r for r in nxp if (r['year'],r['quarter'])==(2014,4))
        self.assertEqual(q4['capex'],107) # 329 annual minus 51+89+82 quarters
        self.assertEqual(len(q4['refs']['capex']['components']),4)

    def test_new_financial_reports_are_collected_and_ifrs_reports_skipped(self):
        recent=dict(form=['6-K','6-K'],filingDate=['2026-11-04','2026-11-03'],
                    primaryDocument=['stm-6k_q3x2026.htm','stm_sarxmaster.htm'],
                    accessionNumber=['0000932787-26-000094','0000932787-26-000093'])
        calls=[]
        def get(name,url,raw=False):
            calls.append(url)
            return (FIX/'stm_q3_2026.html').read_bytes() if raw else dict(filings=dict(recent=recent))
        extra=collector.refresh_originals(get,dict(checked='2026-11-01',facts=[],sources=[]),'2026-11-18')
        self.assertEqual(len(extra['facts']),5)
        self.assertEqual(len(extra['sources']),1)
        self.assertEqual(extra['checked'],'2026-11-18')
        self.assertEqual(len(calls),2)
        def broken(name,url,raw=False):return b'<html>changed report</html>' if raw else dict(filings=dict(recent=recent))
        with self.assertRaisesRegex(ValueError,'format changed'):
            collector.refresh_originals(broken,dict(checked='2026-11-01'),'2026-11-18')

    def test_source_failure_keeps_successful_values_and_dates(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            (out/'power_semicon_state.json').write_text(json.dumps(self.state),encoding='utf8')
            with patch.object(collector,'OUT',out),patch.object(collector.requests,'Session') as session:
                session.return_value.get.side_effect=requests.ConnectionError('test outage')
                result=collector.collect()
            for key,old in self.state['companies'].items():
                new=result['companies'][key]
                self.assertFalse(new['ok'])
                self.assertEqual(new['rows'],old['rows'])
                self.assertEqual(new['annual'],old['annual'])
                self.assertEqual(new['fetched'],old['fetched'])
                self.assertFalse(load(out/f'company_{key}_revenue.json',{})['collection_status']['ok'])

    def test_manual_originals_have_traceable_source_hashes_and_issuer_guard(self):
        for key,meta in self.seed['companies'].items():
            urls={source['url'] for source in meta['sources']}
            self.assertTrue(all(len(s['sha256'])==64 for s in meta['sources']))
            self.assertTrue(all(f['source_url'] in urls for f in meta['facts']))
        with self.assertRaisesRegex(ValueError,'mismatch'):
            collector.combined_payload(dict(cik=1),[],collector.COMPANIES['nxp'])


if __name__=='__main__':unittest.main()

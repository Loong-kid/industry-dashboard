import json
from pathlib import Path
import unittest

from bs4 import BeautifulSoup
from fetch_midstream import merge_hp,reconcile_quarters,today
from midstream_sources import SPECS,hp_dates,horsepower_tables

ROOT=Path(__file__).resolve().parents[1]

class OperatingDataTests(unittest.TestCase):
    def test_distinct_quarter_and_previous_december_columns(self):
        header='Three Months Ended March 31, 2015 December 31, 2014 March 31, 2014'
        self.assertEqual(hp_dates(header,{}),['2015-03-31','2014-12-31','2014-03-31'])

    def test_mixed_quarter_and_annual_prospectus_columns(self):
        header='Three Months Ended March 31, Year Ended December 31, 2023 2022 2022 2021'
        self.assertEqual(hp_dates(header,{}),['2023-03-31','2022-03-31','2022-12-31','2021-12-31'])

    def test_prefer_total_available_not_fleet(self):
        soup=BeautifulSoup('<table><tr><th>March 31, 2026</th></tr><tr><td>Fleet horsepower</td><td>4,930,737</td></tr><tr><td>Total available horsepower</td><td>5,012,892</td></tr><tr><td>Revenue-generating horsepower</td><td>4,439,968</td></tr><tr><td>Average revenue-generating horsepower</td><td>4,438,366</td></tr></table>','html.parser')
        result=horsepower_tables(soup,'usac',dict(date='2026-03-31',filed='2026-05-07',form='10-Q',url='https://www.sec.gov/example'))
        self.assertEqual(result[0]['available'],5012.892)
        self.assertEqual(result[0]['operating'],4439.968)

    def test_each_hp_metric_keeps_its_own_reference(self):
        ref=dict(url='https://www.sec.gov/annual',filed='2023-03-01')
        rows=merge_hp([], [dict(date='2021-12-31',available=2935.826,operating=2933.203,ref=ref),dict(date='2021-03-31',operating=2815.051,ref=dict(url='https://www.sec.gov/ipo',filed='2023-06-27'))],'2026-10-26')
        self.assertNotIn('available',rows[0])
        self.assertEqual(rows[1]['refs']['available']['url'],ref['url'])

class PublishedHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=json.loads((ROOT/'data/natgas/midstream_state.json').read_text(encoding='utf8'))['companies']

    def test_independent_annual_statement_anchors(self):
        expected={'kmi':(16937,4724,3026),'wmb':(11950,4196,4893),'et':(85536,9027,6303),'epd':(52596,7266,5620),'trgp':(17028.3,3331.2,3333.3),'aroc':(1489.818,543.226,502.465),'kgs':(1308.1,340.01,315.472),'usac':(998.099,306.505,117.277)}
        for key,values in expected.items():
            row=next(r for r in self.state[key]['annual'] if r['year']==2025)
            for metric,value in zip(['revenue','profit','capex'],values):self.assertAlmostEqual(row[metric],value,places=3,msg=f'{key} {metric}')

    def test_2014_and_private_company_coverage(self):
        for key,company in self.state.items():
            self.assertEqual(company['annual'][0]['year'],2021 if key=='kgs' else 2014)
            self.assertEqual(company['rows'][0]['date'],'2021-03-31' if key=='kgs' else '2014-03-31')

    def test_no_incompatible_quarter_sums(self):
        for key,company in self.state.items():
            for annual in company['annual']:
                quarters=[r for r in company['rows'] if r['year']==annual['year']]
                for metric in ['revenue','profit','capex']:
                    if metric in annual and len(quarters)==4 and all(metric in r for r in quarters):
                        self.assertAlmostEqual(sum(r[metric] for r in quarters),annual[metric],delta=max(.005,abs(annual[metric])*.00005),msg=f'{key} {annual["year"]} {metric}')

    def test_monetary_signs_and_citations(self):
        for key,company in self.state.items():
            for row in company['annual']+company['rows']:
                for metric in ['revenue','profit','capex']:
                    if metric not in row:continue
                    if metric!='profit':self.assertGreaterEqual(row[metric],0)
                    self.assertTrue(row['refs'][metric]['url'].startswith('https://www.sec.gov/'))
                    self.assertLessEqual(row['refs'][metric]['filed'],today())

    def test_actual_hp_and_unit_anchors(self):
        expected={'aroc':(4784,4516),'kgs':(4495.394,4413.451),'usac':(5023.815,4455.148)}
        for key,values in expected.items():
            row=next(r for r in self.state[key]['hp'] if r['date']=='2026-06-30')
            self.assertEqual((row['available'],row['operating']),values)
        usac=next(r for r in self.state['usac']['hp'] if r['date']=='2014-03-31')
        self.assertEqual((usac['available'],usac['operating']),(1340.542,1107.218))

    def test_kodiak_no_reverse_engineered_capacity(self):
        row=next(r for r in self.state['kgs']['hp'] if r['date']=='2021-03-31')
        self.assertEqual(row['operating'],2815.051)
        self.assertNotIn('available',row)
        row=next(r for r in self.state['kgs']['hp'] if r['date']=='2023-03-31')
        self.assertEqual((row['available'],row['operating']),(3175.006,3169.301))
        row=next(r for r in self.state['kgs']['hp'] if r['date']=='2024-03-31')
        self.assertEqual((row['available'],row['operating']),(3290.971,3285.592))
        self.assertEqual(row['refs']['available']['pdf_page'],3)

    def test_30_documents_and_route(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        gas=next(i for i in catalog['industries'] if i['id']=='natgas')
        ids=[id for section in gas['sections'] if section['tab']=='midstream' for id in section['indicators']]
        self.assertEqual(len(ids),30)
        self.assertEqual(len(set(ids)),30)
        for id in ids:
            doc=json.loads((ROOT/'data/natgas'/f'{id}.json').read_text(encoding='utf8'))
            self.assertEqual(doc['id'],id)
            self.assertFalse(doc['span_gaps'])
            for series in doc['series'].values():
                for date,value in series:
                    if value is not None:self.assertIn(date,doc['point_sources'])
            if id.startswith('company_'):self.assertIn('annual',doc['series_views'])
            else:self.assertNotIn('series_views',doc)  # stock, never annual sum

if __name__=='__main__':unittest.main()

import json,unittest
from pathlib import Path
from fetch_asml_history import parse_quarter_tables,fiscal_quarter
from fetch_cpu_companies import ROOT,load


class AsmlHistory(unittest.TestCase):
    def test_complete_2014_onward_and_anchors(self):
        state=load(ROOT/'data/semicon/equipment_state.json',{})['companies']['asml']
        rows=state['rows'];by={(r['year'],r['quarter']):r for r in rows}
        self.assertEqual(len(rows),len(by))
        self.assertTrue({(y,q) for y in range(2014,2026) for q in range(1,5)}|{(2026,q) for q in range(1,4)}<=set(by))
        for period,expected in { (2014,1):('2014-03-30',1396.5,265.7,75.5),
            (2018,1):('2018-04-01',2285.,642.2,129.2),
            (2024,4):('2024-12-31',9262.8,3355.4,704.),
            (2025,1):('2025-03-30',7741.5,2737.9,415.),
            (2025,2):('2025-06-29',7691.7,2664.1,414.8),
            (2026,3):('2026-09-27',11662.,5172.8,413.3)}.items():
            row=by[period];self.assertEqual(row['date'],expected[0])
            for metric,value in zip(('revenue','profit','capex'),expected[1:]):self.assertAlmostEqual(row[metric],value)
        for row in rows:
            for metric in ('revenue','profit','capex'):
                self.assertIsNotNone(row[metric]);self.assertTrue(row['refs'][metric]['url'].startswith('https://www.sec.gov/Archives/edgar/data/937966/'))
            self.assertAlmostEqual(row['system']+row['service'],row['revenue'],places=1)
        annual={r['year']:r for r in state['annual']}
        # Latest annuals restate 2016/2017 on ASC606/842; the historical quarter
        # tables retain the then-published basis rather than invent adjustments.
        for year in [2014,2015,*range(2018,2025)]:
            for metric in ('revenue','profit','capex'):
                self.assertLessEqual(abs(sum(by[year,q][metric] for q in range(1,5))-annual[year][metric]),.15)
        for metric in ('revenue','profit','capex'):
            doc=load(ROOT/f'data/semicon/company_asml_{metric}.json',{})
            self.assertEqual(next(iter(doc['series'].values()))[0][0],'2014-03-30')
            self.assertGreaterEqual(len(next(iter(doc['series'].values()))),51)
            self.assertIn('ASC 606',doc['description'])
        mix=load(ROOT/'data/semicon/equipment_asml_revenue_mix.json',{})
        self.assertTrue(all(len(points)>=51 for points in mix['series'].values()))

    def test_quarter_headers_signs_and_no_ytd_substitution(self):
        def table(dates,years,columns):
            return '<table><tr><td>in millions EUR</td>'+''.join('<td>'+d+'</td>' for d in dates)+'</tr><tr><td></td>'+''.join('<td>'+str(y)+'</td>' for y in years)+'</tr>'+''.join('<tr><td>'+label+'</td>'+''.join('<td>'+v+'</td>' for v in vals)+'</tr>' for label,vals in columns.items())+'</table>'
        columns={'Total net sales':['10','20','30','40','50'], 'Income from operations':['1','(2)','3','4','5'],
            'Purchase of property, plant and equipment':['(1',')','(2)', '(3)', '(4)', '(5)']}
        bad=table(['Dec 31,']*4,[2013,2014,2013,2014],{'Total net sales':['999']*4})
        valid=table(['Dec 31,','Mar 30,','Jun 29,','Sep 28,','Dec 31,'],[2013,2014,2014,2014,2014],columns)
        rows=parse_quarter_tables(bad+valid,'https://www.sec.gov/Archives/edgar/data/937966/test','2015-01-21')
        self.assertEqual([r['revenue'] for r in rows],[20,30,40,50])
        self.assertEqual([r['capex'] for r in rows],[2,3,4,5])
        self.assertEqual(rows[0]['profit'],-2)
        self.assertEqual(fiscal_quarter('2016-10-02'),(2016,3))
        self.assertEqual(fiscal_quarter('2018-04-01'),(2018,1))
        with self.assertRaises(ValueError):parse_quarter_tables(bad,'https://example.com','2015-01-21')
        with self.assertRaises(ValueError):parse_quarter_tables(valid.replace('millions EUR','thousands EUR'),'https://example.com','2015-01-21')


if __name__=='__main__':unittest.main()

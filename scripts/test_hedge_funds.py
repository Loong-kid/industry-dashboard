"""Economic semantics and preservation checks, independent of live endpoints."""
import calendar
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from fetch_hedge_funds import (INDEX_NAMES, annual_returns, cumulative_indices,
                               parse_adv, parse_ofr, parse_pivotal, write_cohort)

TODAY = date(2026, 10, 5)


class HedgeFundTest(unittest.TestCase):
    def test_annual_compounds_and_excludes_partial_years(self):
        points = {f"2025-{m:02d}-{calendar.monthrange(2025,m)[1]}": 0 for m in range(1,13)}
        points['2025-01-31'] = .1
        points['2025-02-28'] = -.1
        points['2026-01-31'] = .5
        self.assertEqual(annual_returns(points), [['2025-12-31', -1.0]])

    def test_missing_month_does_not_become_annual_return(self):
        points = {f"2025-{m:02d}-28": .01 for m in range(1,12)}
        self.assertEqual(annual_returns(points), [])

    def test_cumulative_uses_common_period(self):
        series = {'iHFC': {'2024-12-31': 9, '2025-01-31': .1, '2025-02-28': -.1},
                  'iQNT': {'2025-01-31': 0, '2025-02-28': 0}}
        result, start = cumulative_indices(series)
        self.assertEqual(start, '2024-12-31')
        self.assertEqual(result[INDEX_NAMES['iHFC']], [[start,100],['2025-01-31',110],['2025-02-28',99]])
        self.assertEqual(result[INDEX_NAMES['iQNT']][-1][1], 100)

    def pivotal_text(self):
        return 'date,id,mtd\n' + ''.join(f'{y}-{m:02d},{key},0\n' for key in INDEX_NAMES
                for y in range(2015,2025) for m in range(1,13))

    def test_monthly_schema_gap_nonfinite_and_conflicting_duplicate(self):
        text = self.pivotal_text()
        self.assertEqual(len(parse_pivotal(text,TODAY,'2024-12')['iHFC']),120)
        bad = [text.replace('2017-01,iHFC,0\n',''),
               text.replace('2017-01,iHFC,0','2017-01,iHFC,nan'),
               text + '2017-01,iHFC,0.1\n', text + '2027-01,iHFC,0\n',
               text.replace('mtd','ytd',1), text.replace('2017-01,iHFC,0','2017-01,iHFC,-1.01')]
        for payload in bad:
            with self.subTest(payload=payload[-30:]), self.assertRaises(ValueError):
                parse_pivotal(payload,TODAY,'2024-12')

    def ofr(self):
        rows = [[f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]}', 1e9] for y in range(2020,2025) for m in [3,6,9,12]]
        return {'test': {'metadata': {'mnemonic':'test','schedule':{'observation_frequency':'Quarterly'},
                 'unit':{'type':'Value','name':'U.S. dollars','magnitude':0}}, 'timeseries':{'aggregation':rows}}}

    def test_ofr_null_unit_and_quarter_end(self):
        p=self.ofr();p['test']['timeseries']['aggregation'][2][1]=None
        points,_=parse_ofr(p,'test',TODAY)
        self.assertIsNone(points[2][1]);self.assertEqual(points[0][1],1)
        for section in ['unit','date','negative']:
            bad=copy.deepcopy(p)
            if section=='unit':bad['test']['metadata']['unit']['name']='millions'
            elif section=='date':bad['test']['timeseries']['aggregation'][0][0]='2020-03-30'
            else:bad['test']['timeseries']['aggregation'][0][1]=-1
            with self.assertRaises(ValueError):parse_ofr(bad,'test',TODAY)

    def adv(self):
        return '''Primary Business Name: TEST ADVISER
CRD Number: 12345
Other-Than-Annual Amendment - All Sections
8/14/2026 7:45:08 PM
Regulatory Assets Under Management
Discretionary:
(a)
$ 1,200,000
(d)
19
Non-Discretionary:
(b)
$ 300,000
(e)
2
Total:
(c)
$ 1,500,000
(f)
21
'''

    def test_adv_labeled_total_not_account_count_or_filing_year_end(self):
        p=parse_adv(self.adv(),'TEST ADVISER',12345,TODAY)
        self.assertEqual(p['value'],1500000)
        self.assertEqual(p['date'],'2026-08-14')
        self.assertIsNone(p['valuation_date'])
        for txt,name,crd in [(self.adv(),'OTHER',12345),(self.adv(),'TEST ADVISER',99999),
                             (self.adv().replace('1,500,000','1,600,000'),'TEST ADVISER',12345)]:
            with self.assertRaises(ValueError):parse_adv(txt,name,crd,TODAY)

    def test_cohort_preserves_all_files_when_one_history_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            good={'a':{'updated':'2025-12-31','series':{'value':[['2024-12-31',1],['2025-12-31',2]]}},
                  'b':{'updated':'2025-12-31','series':{'value':[['2025-12-31',2]]}}}
            write_cohort(good,out)
            before={p.name:p.read_bytes() for p in out.iterdir()}
            bad=copy.deepcopy(good);bad['a']['series']['value'].pop(0);bad['b']['series']['value'][0][1]=3
            with self.assertRaises(ValueError):write_cohort(bad,out)
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir()})
            corrected=copy.deepcopy(good);corrected['a']['series']['value'][0][1]=3
            write_cohort(corrected,out)
            self.assertEqual(json.loads((out/'a.json').read_text())['series']['value'][0][1],3)


if __name__ == '__main__':
    unittest.main()

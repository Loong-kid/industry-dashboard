import json
from pathlib import Path
import unittest

from company_period_views import add_period_views
from aggregate_semicon_companies import build

ROOT=Path(__file__).resolve().parents[1]


class PeriodViews(unittest.TestCase):
    def test_only_complete_fiscal_year_and_preserve_zero(self):
        dates=['2024-12-28','2025-03-29','2025-06-28','2025-09-27','2025-12-27']
        doc=dict(series={'매출':list(zip(dates,[0,2,3,4,99])),'CAPEX':list(zip(dates,[1,None,3,4,99]))},
                 period_labels={date:f'FY{2025+(i==4)} Q{i%4+1}' for i,date in enumerate(dates)},
                 point_sources={d:dict(url='https://example.com/'+d) for d in dates})
        add_period_views(doc)
        annual=doc['series_views']['annual']
        self.assertEqual(doc['default_view'],'quarter')
        self.assertEqual(annual['series']['매출'],[['2025-09-27',9]])
        self.assertEqual(annual['series']['CAPEX'],[['2025-09-27',None]])
        self.assertEqual(annual['period_labels']['2025-09-27'],'FY2025')
        self.assertEqual(len(annual['point_sources']['2025-09-27']['supporting_sources']),4)
        self.assertFalse(annual['quarter_labels'])

    def test_all_memory_foundry_ssd_cards_and_known_annual_totals(self):
        docs=build(json.loads((ROOT/'manual/semicon_companies.json').read_text(encoding='utf-8')))
        self.assertEqual(len(docs),27)
        for doc in docs.values():self.assertEqual(set(doc['series_views']),{'quarter','annual'})
        def values(key):return {label:{year[:4]:value for year,value in points} for label,points in docs[key]['series_views']['annual']['series'].items()}
        tsmc=values('company_tsmc_revenue')
        self.assertAlmostEqual(next(iter(tsmc.values()))['2024'],2894.30,delta=.003)
        micron=values('company_micron_revenue')
        self.assertAlmostEqual(next(iter(micron.values()))['2024'],25111,delta=2)
        gf=values('company_globalfoundries_revenue')
        self.assertNotIn('2020',next(iter(gf.values())))
        self.assertAlmostEqual(next(iter(gf.values()))['2024'],6750,delta=.01)


if __name__=='__main__':unittest.main()

"""Original subsidiary units, missing-period boundaries and contract evidence."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
import fetch_hybe_labels as hybe
from hybe_label_sources import annual_and_quarters,entity_key,financial_tables,grid,load

DOC=load(hybe.OUT)
FIXTURES=load(hybe.ROOT/'manual/entertainment/hybe-label-fixtures.json')

class HybeLabelsTests(unittest.TestCase):
    def test_actual_original_units_and_prefixed_company_column(self):
        for receipt,expected in [('20240322001002',552335.912),('20260814004127',681973.756)]:
            tables=financial_tables(FIXTURES[receipt]['html']);self.assertEqual(len(tables),2)
            row=next(r for r in tables[0] if entity_key(r['name'])=='빅히트뮤직')
            self.assertAlmostEqual(row['revenue'],expected,places=6)
        current=financial_tables(FIXTURES['20260814004127']['html'])[0]
        america=next(r for r in current if entity_key(r['name'])==entity_key('HYBE America Inc.'))
        self.assertAlmostEqual(america['net_income'],-140273.957,places=6)

    def test_original_current_and_comparative_do_not_become_two_current_periods(self):
        current,prior=financial_tables(FIXTURES['20260814004127']['html'])
        get=lambda rows:next(r['revenue'] for r in rows if '빅히트뮤직' in r['name'])
        self.assertEqual(get(current),681973.756);self.assertEqual(get(prior),189087.198)

    def test_rowspan_preserves_label_group_and_members(self):
        table=BeautifulSoup('<table><tr><th>회사명</th><th>그룹</th><th>아티스트</th></tr><tr><td rowspan="3">레이블A</td><td rowspan="2">그룹1</td><td>멤버1</td></tr><tr><td>멤버2</td></tr><tr><td>그룹2</td><td>멤버3</td></tr></table>','html.parser').table
        self.assertEqual(grid(table)[2],['레이블A','그룹1','멤버2'])
        self.assertEqual(grid(table)[3],['레이블A','그룹2','멤버3'])

    def test_quarter_difference_never_bridges_missing_or_cross_year_period(self):
        def row(year,q,value,**kw):return dict(entity='a',year=year,quarter=q,date=hybe.date_end(year,q),revenue=value,net_income=-value,filed=f'{year+1}-01-01',source_url='https://dart.fss.or.kr/example',**kw)
        views=annual_and_quarters([row(2024,4,99),row(2025,1,10),row(2025,2,30),row(2025,4,80)])
        self.assertEqual([(r['quarter'],r['revenue'],r['net_income']) for r in views['quarter']],[(1,10,-10),(2,20,-20)])
        views=annual_and_quarters([row(2025,1,10),row(2025,2,0)])
        self.assertEqual(len(views['quarter']),1)

    def test_actual_current_period_wins_over_comparative(self):
        row=copy.deepcopy(DOC['observations'][0]);base=dict(row,comparative=False,revenue=10)
        compare=dict(row,comparative=True,revenue=999,filed='2026-01-01')
        views=annual_and_quarters([compare,base]);self.assertEqual(views['cumulative'][0]['revenue'],10)

    def test_published_history_has_no_parent_revenue_before_spin_off(self):
        hybe.validate(DOC)
        big=[r for r in DOC['financial_views']['cumulative'] if r['entity']=='bighit']
        self.assertTrue(all(r['date']>='2021-07-01' for r in big))
        annual=next(r for r in DOC['financial_views']['annual'] if r['entity']=='bighit' and r['year']==2025)
        self.assertAlmostEqual(annual['revenue'],437533.228,places=6)
        self.assertEqual(len([r for r in DOC['financial_views']['cumulative'] if r['date']=='2026-06-30' and r['entity'] in ['bighit','pledis','source','koz','ador','belift']]),6)
        state=load(hybe.ROOT/'data/entertainment/state.json')
        self.assertLessEqual(DOC['updated'],max(r['date'] for r in hybe.filings(state)))

    def test_missing_summary_revenue_is_not_zero_or_allocated_to_group(self):
        labels={l['id'] for l in DOC['labels']};self.assertTrue({'bigmachine','qualitycontrol','sbprojects','jconic'}<=labels)
        rows=[r for r in DOC['financial_views']['cumulative'] if r['entity']=='hybe_umg' and r['date']=='2025-12-31']
        self.assertTrue(rows);self.assertIsNone(rows[0]['revenue'])
        self.assertFalse(any(r['entity']=='bts' for r in DOC['financial_views']['cumulative']))
        for row in DOC['financial_views']['quarter']:
            for metric in ['revenue','net_income']:
                if row[metric] is not None and row['quarter']>1:
                    same=lambda q:next(r for r in DOC['financial_views']['cumulative'] if r['entity']==row['entity'] and r['year']==row['year'] and r['quarter']==q)
                    self.assertAlmostEqual(row[metric],same(row['quarter'])[metric]-same(row['quarter']-1)[metric],places=5)

    def test_contracts_do_not_invent_term_or_use_debut_as_signing_date(self):
        contracts={r['id']:r for r in DOC['contracts']}
        for id in ['bts','txt','seventeen','lesserafim','illit','cortis']:
            self.assertIsNone(contracts[id]['first_signed']);self.assertIsNone(contracts[id]['expires'])
        self.assertEqual(contracts['seventeen']['events'][-1]['date'],'2026-07-13')
        self.assertEqual(contracts['txt']['events'][-1]['date'],'2025-08-22')
        self.assertEqual(contracts['newjeans']['expires'],'2029-07-31');self.assertTrue(contracts['newjeans']['expiry_scope'])
        if DOC['roster']['report_date']=='2026-06-30':
            self.assertEqual(len(contracts['newjeans']['members']),4);self.assertEqual(len(contracts['enhypen']['members']),6)
            self.assertTrue(contracts['evan']['current'])
        self.assertFalse(contracts['fromis9']['current'])
        self.assertEqual(contracts['fromis9']['expires'],'2024-12-31')

    def test_failure_retains_last_success_and_contract_review_date(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'hybe.json';hybe.save(out,DOC)
            with patch.object(hybe,'OUT',out),patch.object(hybe,'collect',side_effect=ValueError('source unavailable')):
                hybe.run()
            kept=load(out);self.assertFalse(kept['ok'])
            for field in ['financial_views','contracts','fetched','contracts_reviewed']:self.assertEqual(kept[field],DOC[field])

    def test_chart_source_is_financial_note_and_workflow_is_isolated(self):
        self.assertNotEqual(DOC['source_url'],DOC['roster']['source_url'])
        for chart in DOC['charts']:
            self.assertTrue(chart['source_url'].startswith('https://dart.fss.or.kr/report/viewer.do?'))
            self.assertEqual(chart['unit'],'억원');self.assertEqual(set(chart['series_views']),{'quarter','annual','cumulative'})
            self.assertEqual(chart['series_views']['cumulative']['change_mode'],'none')
        workflow=(hybe.ROOT/'.github/workflows/update-hybe-labels.yml').read_text(encoding='utf8')
        self.assertIn('git add data/entertainment/hybe_labels.json',workflow)
        self.assertNotIn('DART_API_KEY',workflow)
        self.assertIn('update-entertainment',workflow)
        self.assertNotIn('crtfc_key',str(DOC))

if __name__=='__main__':unittest.main()

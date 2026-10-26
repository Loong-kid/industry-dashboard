"""Financial anchors and regressions for oil accounts and nested drilling."""
import json
import math
from pathlib import Path
import unittest
from oil_sources import financial_soup,html_row,shell_quarter_facts
from fetch_oil import merge_rows

ROOT=Path(__file__).resolve().parents[1]

class OilTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.state=json.loads((ROOT/'data/oil/state.json').read_bytes())

    def test_seven_consolidated_histories_and_actual_years(self):
        self.assertEqual(set(self.state['companies']),{'xom','cvx','shell','bp','tte','cop','equinor'})
        for key,c in self.state['companies'].items():
            self.assertEqual({r['year'] for r in c['annual']},set(range(2014,max(r['year'] for r in c['annual'])+1)))
            self.assertEqual(len(c['rows']),len({r['date'] for r in c['rows']}))
            self.assertGreaterEqual(len(c['rows']),35)
            if key!='shell':
                self.assertEqual(c['rows'][0]['date'],'2014-03-31')
                self.assertGreaterEqual(len(c['rows']),50)
            for r in c['rows']+c['annual']:
                self.assertLessEqual(r['date'],self.state['updated'])
                for metric in ['revenue','profit','capex']:
                    if metric not in r:continue
                    self.assertTrue(math.isfinite(r[metric]))
                    self.assertTrue(r['refs'][metric]['url'].startswith('https://'))
                    self.assertIn('components',r['refs'][metric])
                    if metric!='profit':self.assertGreaterEqual(r[metric],0)

    def test_2025_original_statement_sales_not_total_income(self):
        expected={'xom':323905,'cvx':184432,'shell':266886,'bp':189335,'tte':182344,'cop':58944,'equinor':105828}
        for key,value in expected.items():
            row=next(r for r in self.state['companies'][key]['annual'] if r['year']==2025)
            self.assertAlmostEqual(row['revenue'],value,places=3,msg=key)
        q=next(r for r in self.state['companies']['xom']['rows'] if r['date']=='2026-06-30')
        self.assertEqual(q['revenue'],114529)
        self.assertIn('/2115436/',q['refs']['revenue']['url'])
        shell=next(r for r in self.state['companies']['shell']['annual'] if r['year']==2014)
        self.assertEqual((shell['revenue'],shell['profit'],shell['capex']),(421105,25995,31676))

    def test_cash_capex_is_not_gross_additions_or_company_total_investment(self):
        expected={'xom':28358,'cvx':17347,'shell':18947,'bp':13221,'tte':16953,'cop':12553,'equinor':13994}
        for key,value in expected.items():
            row=next(r for r in self.state['companies'][key]['annual'] if r['year']==2025)
            self.assertAlmostEqual(row['capex'],value,places=3,msg=key)
        old=next(r for r in self.state['companies']['xom']['annual'] if r['year']==2018)
        self.assertEqual(old['capex'],19574) # not gross PP&E additions 20,051

    def test_equinor_pdf_column_alignment_and_usd_transition(self):
        c=self.state['companies']['equinor'];q=next(r for r in c['rows'] if r['date']=='2021-12-31')
        self.assertEqual(q['revenue'],32125)
        self.assertEqual(q['profit'],13578)
        q=next(r for r in c['rows'] if r['date']=='2019-03-31')
        self.assertEqual(q['revenue'],16410)
        self.assertAlmostEqual(c['rows'][0]['revenue'],27875.810,places=3)
        self.assertIn('.xlsx',c['rows'][0]['refs']['revenue']['url'])

    def test_complete_quarters_reconcile_to_published_annual_accounts(self):
        for key,c in self.state['companies'].items():
            for annual in c['annual']:
                quarters=[r for r in c['rows'] if r['year']==annual['year']]
                if len(quarters)!=4:continue
                for metric in ['revenue','profit','capex']:
                    if metric not in annual or any(metric not in r for r in quarters):continue
                    # Four individually rounded million-dollar observations may
                    # differ slightly; mixed scopes/columns must not slip through.
                    self.assertLessEqual(abs(sum(r[metric] for r in quarters)-annual[metric]),4,
                        f"{key} {annual['year']} {metric}: statement vintage or column mismatch")

    def test_positioned_xhtml_uses_row_and_context_not_ambiguous_revenue_tag(self):
        raw=b'''<html><body><xbrli:context id="whole"><xbrli:period><xbrli:startDate>2019-01-01</xbrli:startDate><xbrli:endDate>2019-12-31</xbrli:endDate></xbrli:period></xbrli:context><div id="Page1"><div style="top:10px;left:20px">Sales and other operating revenues</div><div style="top:10px;left:300px"><ix:nonFraction name="us-gaap:Revenues" contextRef="whole" scale="6">32,567</ix:nonFraction></div><div style="top:30px;left:20px">Total revenues and other income</div><div style="top:30px;left:300px"><ix:nonFraction name="us-gaap:Revenues" contextRef="whole" scale="6">36,670</ix:nonFraction></div></div></body></html>'''
        facts,_=html_row(financial_soup(raw),r'^Sales and other operating revenues')
        self.assertEqual([f['val'] for f in facts],[32567000000])

    def test_merge_preserves_history_without_adding_duplicated_periods(self):
        old=[dict(date='2014-03-31',year=2014,quarter=1,revenue=10,refs={'revenue':dict(url='old',filed='2014-05-01')})]
        new=[dict(date='2014-03-31',year=2014,quarter=1,revenue=12,refs={'revenue':dict(url='new',filed='2015-05-01')})]
        self.assertEqual(merge_rows(old,[]),old)
        self.assertEqual(len(merge_rows(old,new)),1)
        self.assertEqual(merge_rows(old,new)[0]['revenue'],12)

    def test_old_shell_percentage_column_is_not_a_financial_period(self):
        content=b'''<table><tr><td>$ million Quarters Q1 2015 Q4 2014 Q1 2014 %</td></tr>
        <tr><td>Revenue</td><td>65,706</td><td>92,374</td><td>109,658</td></tr>
        <tr><td>Interest and other income</td><td>1,735</td><td>974</td><td>351</td></tr>
        <tr><td>Interest expense</td><td>376</td><td>430</td><td>452</td></tr>
        <tr><td>Income before taxation</td><td>5,839</td><td>2,528</td><td>8,545</td><td>-32</td></tr></table>'''
        meta=dict(date='2015-03-31',filed='2015-04-30',accn='original',url='https://www.sec.gov/original')
        facts=shell_quarter_facts(content,meta)
        old={f['metric']:f['val']/1e6 for f in facts if f['end']=='2014-03-31'}
        self.assertEqual(old['revenue'],109658)
        self.assertEqual(old['profit'],8646)

    def test_nested_drilling_keeps_its_original_data_paths(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_bytes());oil=next(i for i in catalog['industries'] if i['id']=='oil')
        self.assertFalse(any(i['id']=='offshore' for i in catalog['industries']))
        self.assertEqual([t['id'] for t in oil['tabs']],['majors','offshore'])
        for section in oil['sections']:
            directory=section.get('data_industry','oil')
            for id in section['indicators']:self.assertTrue((ROOT/'data'/directory/(id+'.json')).exists())
            if section['tab']=='offshore':self.assertEqual(directory,'offshore')

if __name__=='__main__':unittest.main()

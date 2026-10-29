import copy
import datetime as dt
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import fetch_rings as rings
from ring_financial_sources import parse_report,accounts

ROOT=Path(__file__).resolve().parents[1]
META=rings.read(ROOT/'manual/rings/companies.json')
STATE=rings.read(ROOT/'data/semicon/rings_state.json')
ASOF=max(dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat(),'2026-10-29')


class RingFinancials(unittest.TestCase):
    def test_five_issuers_scopes_and_coverage(self):
        self.assertEqual(list(META['companies']),['tck','hana_materials','knj','worldex','cmtx'])
        coverage={'tck':(2014,2015),'hana_materials':(2015,2016),'knj':(2017,2019),'worldex':(2014,2015),'cmtx':(2023,2024)}
        corp={'tck':'00245472','hana_materials':'00660750','knj':'00769158','worldex':'00580065','cmtx':'01529982'}
        for key,co in STATE['companies'].items():
            self.assertEqual(co['entity']['corp_code'],corp[key]);rings.validate(co,ASOF)
            self.assertEqual((co['annual'][0]['year'],co['rows'][0]['year']),coverage[key])
        self.assertTrue(all(r['fs_div']=='OFS' for r in STATE['companies']['tck']['rows']))
        self.assertTrue(all(r['fs_div']=='CFS' for r in STATE['companies']['worldex']['rows']))

    def test_official_annual_and_latest_quarter_anchors(self):
        expected={'tck':(301334.302844,83887.319363,4496.721586),
                  'hana_materials':(273481.969679,50081.056398,20022.518828),
                  'knj':(84444.745007,22242.526961,21809.064422),
                  'worldex':(291764.969976,58544.362713,10752.116177),
                  'cmtx':(160555.762764,51781.944189,16574.169232)}
        for key,values in expected.items():
            row=next(r for r in STATE['companies'][key]['annual'] if r['year']==2025)
            for metric,amount in zip(['revenue','profit','capex'],values):self.assertAlmostEqual(row[metric],amount,places=6)
        row=next(r for r in STATE['companies']['cmtx']['rows'] if r['date']=='2026-06-30')
        self.assertAlmostEqual(row['revenue'],47897.115675,places=6)
        self.assertAlmostEqual(row['capex'],15271.418744,places=6)

    def test_cash_refund_is_subtracted_and_total_not_double_counted(self):
        fixtures=rings.read(ROOT/'manual/rings/statement-fixtures.json')
        reports=[parse_report(fixtures[f'cmtx-2026-q{q}-CFS.json']['list'],2026,q,'01529982','CFS') for q in [1,2]]
        self.assertAlmostEqual(reports[1]['fields']['capex']['ytd'],23519.336492,places=6)
        facility=next(f for f in reports[1]['fields']['capex']['inputs'] if f['account_name']=='시설장치의 취득')
        self.assertEqual(facility['value'],-995580000)
        rows=accounts(reports,ASOF)['rows'];self.assertAlmostEqual(rows[-1]['capex'],15271.418744,places=6)
        raw=copy.deepcopy(fixtures['cmtx-2026-q2-CFS.json']['list'])
        total=dict(raw[0],sj_div='CF',account_id='ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities',account_nm='유형자산의 취득',thstrm_amount='23519336492',frmtrm_q_amount='7050000000')
        raw.append(total)
        self.assertAlmostEqual(parse_report(raw,2026,2,'01529982','CFS')['fields']['capex']['ytd'],23519.336492,places=6)
        self.assertNotEqual(parse_report(raw,2026,2,'01529982','CFS')['fields']['capex']['tag'],'calculated_PPE_cash_components')

    def test_scope_and_vintage_cannot_be_mixed(self):
        fixtures=rings.read(ROOT/'manual/rings/statement-fixtures.json')
        reports=[parse_report(fixtures[f'cmtx-2026-q{q}-CFS.json']['list'],2026,q,'01529982','CFS') for q in [1,2]]
        other=copy.deepcopy(reports);other[0]['fs_div']='OFS'
        for f in other[0]['fields'].values():f['fs_div']='OFS'
        row=next(r for r in accounts(other,ASOF)['rows'] if r['date']=='2026-06-30')
        self.assertNotIn('capex',row)
        with self.assertRaises(ValueError):parse_report(fixtures['cmtx-2026-q2-CFS.json']['list'],2026,2,'wrong','CFS')

    def test_no_fabricated_capex_or_annualized_incomplete_year(self):
        co=STATE['companies']['cmtx']
        self.assertNotIn(2026,[r['year'] for r in co['annual']])
        self.assertFalse(any(r['date']=='2024-03-31' for r in co['rows']))
        doc=rings.build(META,STATE)['company_rings_cmtx_capex']
        self.assertNotIn('2024-03-31',dict(next(iter(doc['series'].values()))))
        self.assertFalse(doc['span_gaps'])

    def test_pre_ipo_half_year_is_not_a_single_quarter(self):
        fixtures=rings.read(ROOT/'manual/rings/statement-fixtures.json')
        parsed=parse_report(fixtures['cmtx-2025-q2-CFS.json']['list'],2025,2,'01529982','CFS')
        self.assertIsNone(parsed['fields']['revenue']['value'])
        self.assertAlmostEqual(parsed['fields']['revenue']['ytd'],77349.935666,places=6)
        row=next(r for r in STATE['companies']['cmtx']['rows'] if r['date']=='2025-06-30')
        self.assertAlmostEqual(row['revenue'],40401.010884,places=6)
        self.assertAlmostEqual(row['profit'],13688.726106,places=6)

    def test_docs_catalog_and_failure_preservation(self):
        docs=rings.build(META,STATE)
        self.assertEqual(len(docs),15)
        catalog=rings.read(ROOT/'data/catalog.json');ind=next(i for i in catalog['industries'] if i['id']=='semicon')
        self.assertEqual(next(t for t in ind['tabs'] if t['id']=='rings')['category'],'components')
        linked=[id for s in ind['sections'] if s.get('tab')=='rings' for id in s['indicators']]
        self.assertEqual(set(linked),set(docs))
        for id,doc in docs.items():
            self.assertEqual(doc,rings.read(ROOT/'data/semicon'/(id+'.json')))
            self.assertEqual(doc['unit'],'KRW 백만');self.assertEqual(doc['default_view'],'quarter')
            self.assertIn('annual',doc['series_views']);self.assertTrue(doc['series_views']['annual']['annual_axis'])
            self.assertNotEqual(doc['series_views']['quarter']['series'],doc['series_views']['annual']['series'])
        with patch.object(rings,'read',side_effect=lambda path,default=None: {}):
            failed=rings.offline(META,STATE,ASOF,{})
        for key,co in failed['companies'].items():
            self.assertFalse(co['ok'])
            for field in ['rows','annual','fetched']:self.assertEqual(co[field],STATE['companies'][key][field])


if __name__=='__main__':unittest.main()

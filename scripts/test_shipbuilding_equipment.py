import unittest
import json
from pathlib import Path

from shipbuilding_equipment_sources import report, accounts, provisional
from fetch_shipbuilding_equipment import document


def item(tag,name,value,ytd=None,fs='CFS',receipt='20260814000001'):
    return dict(corp_code='00000001',fs_div=fs,sj_div='IS',account_id=tag,account_nm=name,thstrm_amount=str(value),
                thstrm_add_amount=str(ytd) if ytd is not None else '',rcept_no=receipt)


class EquipmentTests(unittest.TestCase):
    def items(self,fs='CFS',receipt='20260814000001',annual=False):
        return [item('ifrs-full_Revenue','매출액',100e6,300e6,fs,receipt),
                item('dart_OperatingIncomeLoss','영업이익(손실)',-10e6,-30e6,fs,receipt),
                item('ifrs-full_ProfitLossAttributableToOwnersOfParent','지배주주순이익',99e6,None,fs,receipt),
                item('ifrs-full_ProfitLoss','당기순이익(손실)',-20e6,-60e6,fs,receipt)]

    def test_total_net_income_not_parent_attribution_and_signed_losses(self):
        r=report(self.items(),2026,2,'00000001','CFS')
        self.assertEqual(r['fields']['netincome']['value'],-20)
        row=next(x for x in accounts([r],'2026-10-27') if x['quarter']==2)
        self.assertEqual((row['revenue'],row['profit'],row['netincome']),(100,-10,-20))

    def test_q4_keeps_negative_net_income_and_same_basis_only(self):
        q3=report(self.items(receipt='20251114000001'),2025,3,'00000001','CFS')
        annual=report(self.items(receipt='20260320000001'),2025,4,'00000001','CFS')
        annual['fields']['netincome']['ytd']=-80
        q4=next(r for r in accounts([q3,annual],'2026-10-27') if r['kind']=='quarter' and r['quarter']==4)
        self.assertEqual(q4['netincome'],-20)
        q3['fs_div']='OFS'
        self.assertFalse(any(r['kind']=='quarter' and r['quarter']==4 for r in accounts([q3,annual],'2026-10-27')))

    def test_future_filings_and_missing_prior_ytd_do_not_create_q4(self):
        a=report(self.items(receipt='20270320000001'),2026,4,'00000001','CFS')
        self.assertFalse(accounts([a],'2026-10-27'))
        a=report(self.items(receipt='20260320000001'),2025,4,'00000001','CFS')
        self.assertTrue(all(r['kind']=='annual' for r in accounts([a],'2026-10-27')))

    def test_missing_q1_is_same_statement_h1_minus_actual_q2(self):
        r=report(self.items(),2026,2,'00000001','CFS')
        first=next(row for row in accounts([r],'2026-10-27') if row['quarter']==1)
        self.assertEqual((first['revenue'],first['profit'],first['netincome']),(200,-20,-40))
        self.assertIn('minus Q2',first['refs']['revenue']['calculation'])

    def test_issuer_and_reporting_basis_mismatches_fail(self):
        with self.assertRaises(ValueError):report(self.items(),2026,2,'00000002','CFS')
        with self.assertRaises(ValueError):report(self.items(),2026,2,'00000001','OFS')

    def test_comparative_quarter_uses_quarter_column_not_prior_annual_amount(self):
        items=self.items()
        for i in items:
            i.update(frmtrm_amount='9000000000',frmtrm_q_amount='50000000',frmtrm_add_amount='120000000')
        r=report(items,2026,2,'00000001','CFS')
        previous=r['comparatives'][0]
        self.assertEqual(previous['year'],2025)
        self.assertEqual(previous['fields']['revenue']['value'],50)
        self.assertEqual(previous['fields']['revenue']['ytd'],120)
        self.assertTrue(previous['fields']['revenue']['comparative'])

    def test_provisional_actual_quarter_excludes_ytd_and_parent_net(self):
        raw='''연결재무제표 기준 단위 : 억원<table>
        <tr><td>당기실적</td><td>2026-07-01 ~ 2026-09-30</td></tr>
        <tr><td>매출액</td><td>당해실적</td><td>6,501</td></tr><tr><td>누계실적</td><td>18,051</td></tr>
        <tr><td>영업이익</td><td>당해실적</td><td>957</td></tr>
        <tr><td>지배기업 소유주지분 순이익</td><td>당해실적</td><td>999</td></tr>
        <tr><td>당기순이익</td><td>당해실적</td><td>326</td></tr></table>'''
        r=provisional(raw,'20261026800212','CFS','2026-10-27')
        self.assertEqual((r['revenue'],r['profit'],r['netincome']),(650100,95700,32600))
        self.assertTrue(r['provisional'])
        with self.assertRaises(ValueError):provisional(raw,'20261026800212','OFS','2026-10-27')

    def test_zero_native_amounts_are_preserved_with_basis_and_source(self):
        items=self.items()
        items[-1]['thstrm_amount']='0'
        rows=accounts([report(items,2026,2,'00000001','CFS')],'2026-10-27')
        fx={'periods':{'KRW|2026-04-01|2026-06-30':dict(local_per_usd=1400,observations=62,first='2026-04-01',last='2026-06-30')}}
        m=dict(name='Company',scope='group',comparability_note='',ir_url='https://dart.fss.or.kr')
        d=document('c','netincome',m,dict(rows=rows,status='ok'),fx)
        self.assertEqual(dict(d['series']['순이익'])['2026-06-30'],0)
        self.assertIn('재무제표: 연결',d['point_notes']['2026-06-30'])
        self.assertNotIn('supporting_sources',d['point_sources']['2026-06-30'])

    def test_shipbuilding_market_and_equipment_routes_coexist(self):
        root=Path(__file__).resolve().parents[1]
        catalog=json.loads((root/'data/catalog.json').read_text(encoding='utf8'))
        ship=next(i for i in catalog['industries'] if i['id']=='shipbuilding')
        self.assertEqual([t['id'] for t in ship['tabs']],['market','engines','engine_parts','aftermarket'])
        market=[s for s in ship['sections'] if s['tab']=='market']
        ids=[id for s in market for id in s['indicators']]
        for original in ['clarksons_nb_index','korea_orders','asiasis_orders','korea_revenue_progress']:
            self.assertIn(original,ids)
        financial=[s for s in ship['sections'] if s['tab']!='market']
        self.assertEqual(len(financial),7)
        self.assertEqual(sum(len(s['indicators']) for s in financial),21)


if __name__=='__main__':unittest.main()

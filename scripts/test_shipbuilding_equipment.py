import unittest

from shipbuilding_equipment_sources import report, accounts, provisional


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
        row=accounts([r],'2026-10-27')[0]
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

    def test_issuer_and_reporting_basis_mismatches_fail(self):
        with self.assertRaises(ValueError):report(self.items(),2026,2,'00000002','CFS')
        with self.assertRaises(ValueError):report(self.items(),2026,2,'00000001','OFS')

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


if __name__=='__main__':unittest.main()

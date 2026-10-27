import unittest
from shipbuilding_equipment_sources import report,accounts


class ContainmentTests(unittest.TestCase):
    def test_total_income_and_actual_quarters(self):
        rows=[dict(sj_div='IS',account_id=tag,account_nm=name,thstrm_amount=value,thstrm_add_amount=ytd,rcept_no='20260814000123') for tag,name,value,ytd in [
            ('ifrs-full_Revenue','매출액','200000000','350000000'),
            ('dart_OperatingIncomeLoss','영업이익','-20000000','-30000000'),
            ('ifrs-full_ProfitLoss','당기순이익','-10000000','-25000000'),
            ('ifrs-full_ProfitLossAttributableToOwnersOfParent','지배주주순이익','999000000','999000000')]]
        parsed=accounts([report(rows,2026,2,'01234567','CFS')],'2026-10-27')
        q2=next(r for r in parsed if r['quarter']==2)
        self.assertEqual([q2[m] for m in ['revenue','profit','netincome']],[200,-20,-10])
        self.assertEqual(next(r for r in parsed if r['quarter']==1)['netincome'],-15)


if __name__=='__main__':unittest.main()

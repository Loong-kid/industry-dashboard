import io
import unittest
import openpyxl

from telecom_sources import columns, dart_accounts, dart_report, number, parse_ntt, reporting_period, softbank_link
from fetch_telecom import document, merge_rows


class TelecomTests(unittest.TestCase):
    def test_fiscal_year_and_no_annualization(self):
        self.assertEqual(reporting_period(2027,1,4)['date'],'2026-06-30')
        self.assertEqual(reporting_period(2026,None,4)['start'],'2025-04-01')
        row=reporting_period(2026,1);row.update(revenue=100,profit=-10,capex=20,refs={k:dict(url='https://issuer.test/report') for k in ['revenue','profit','capex']})
        doc=document('sample','capex',dict(name='Sample',currency='USD',scope='whole group',capex_basis='cash PP&E'),dict(rows=[row],status='ok'),{})
        self.assertEqual(doc['series']['CAPEX'],[['2026-03-31',20]])
        self.assertEqual(doc['series_views']['annual']['series'],{})

    def test_dart_direct_income_and_ytd_cashflow(self):
        def item(tag,name,value,div,add=''):
            return dict(account_id=tag,account_nm=name,thstrm_amount=value,thstrm_add_amount=add,sj_div=div,rcept_no='20260814000001',corp_code='correct')
        fields=dart_report([item('ifrs-full_Revenue','매출액','250','IS','450'),item('dart_OperatingIncomeLoss','영업이익','-10','IS','20'),item('ifrs-full_PurchaseOfPropertyPlantAndEquipment','유형자산의 취득','150','CF')],2026,2,'correct')['fields']
        self.assertEqual(fields['revenue']['value'],.00025)
        self.assertEqual(fields['revenue']['ytd'],.00045)
        self.assertEqual(fields['profit']['value'],-.00001)
        self.assertEqual(fields['capex']['ytd'],.00015)
        with self.assertRaises(ValueError):dart_report([item('x','x','1','CF')],2026,2,'other')

    def test_cf_quarter_differences_and_missing_not_zero(self):
        reports=[]
        for q,amount in [(1,10),(2,30),(4,100)]:
            reports.append(dict(year=2025,quarter=q,fields={'capex':dict(value=amount,ytd=amount,filed='2026-03-01',tag='same',url='https://issuer.test')}))
        rows=dart_accounts(reports,'2026-10-26')
        self.assertEqual(next(r for r in rows if r['kind']=='annual')['capex'],100)
        self.assertEqual(next(r for r in rows if r.get('quarter')==2)['capex'],20)
        self.assertFalse(any(r.get('quarter')==4 and 'capex' in r for r in rows))
        self.assertEqual(number('(1,234)'),-1234)

    def test_ntt_excludes_margin_and_forecasts(self):
        w=openpyxl.Workbook();s=w.active;s.title='1 '
        s['I4']='FY2025';s['O4']='FY2026';s['U4']='FY2026'
        for col,text in [('I5','1Q\nApr-Jun'),('J5','2Q'),('K5','3Q'),('L5','4Q'),('M5','Results'),('O5','1Q\nApr-Jun'),('P5','2Q'),('Q5','3Q'),('R5','4Q'),('S5','Results'),('U5','Full Year Forecasts')]:s[col]=text
        s['C7']='営業利益 / Operating profit';s['O7']=400
        s['C11']='EBITDA margin [EBITDA/Operating revenues]';s['O11']=.24
        s['C14']='営業収益 / Operating revenues';s['O14']=3000;s['U14']=15000
        cap=w.create_sheet('3');cap['A1']='Financial Results Summary (Capital Investment)';cap['I4']='FY2025';cap['O4']='FY2026';cap['I5']='1Q';cap['O5']='1Q';cap['C6']='設備投資額 / Capital Investment';cap['O6']=500
        raw=io.BytesIO();w.save(raw)
        rows=parse_ntt(raw.getvalue(),'https://issuer.test/file.xlsx','2026-10-26')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['revenue'],3000000)
        self.assertEqual(rows[0]['capex'],500000)
        self.assertFalse(any(col==21 for col,_,_ in columns(s,5,4)))

    def test_usd_preserves_original_and_partial_updates(self):
        row=reporting_period(2026,1);row.update(revenue=150000,refs={'revenue':dict(url='https://issuer.test')})
        fx={'periods':{'KRW|2026-01-01|2026-03-31':{'local_per_usd':1500,'observations':60,'first':'2026-01-02','last':'2026-03-31'}}}
        meta=dict(name='Korea',currency='KRW',scope='group',capex_basis='cash PP&E')
        doc=document('k','revenue',meta,dict(rows=[row],status='ok'),fx)
        self.assertEqual(doc['series']['매출'][0][1],100)
        self.assertEqual(doc['original_series']['매출'][0][1],150000)
        self.assertIn('KRW',' '.join(doc['point_notes']['2026-03-31']))
        self.assertEqual(document('k','revenue',meta,dict(rows=[row]),{})['series']['매출'][0][1],None)
        newer=dict(reporting_period(2026,1),profit=-5,refs={'profit':dict(url='https://issuer.test/new')})
        updated=merge_rows([row],[newer])[0]
        self.assertEqual(updated['revenue'],150000);self.assertEqual(updated['profit'],-5)


if __name__=='__main__':unittest.main()

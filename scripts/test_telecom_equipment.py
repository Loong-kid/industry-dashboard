import unittest
import pymupdf

from fetch_telecom import document
from fetch_telecom_equipment import ifrs_annual
from telecom_equipment_sources import parse_nokia_pdf, row_values


class EquipmentTests(unittest.TestCase):
    def test_52_week_quarters_do_not_gain_calendar_gaps(self):
        rows=[]
        for q,start,end in [(1,'2025-11-02','2026-01-31'),(2,'2026-02-01','2026-05-02'),(3,'2026-05-03','2026-08-01')]:
            rows.append(dict(kind='quarter',year=2026,quarter=q,start=start,date=end,period=f'FY2026 Q{q}',revenue=100,refs={'revenue':{'url':'https://issuer.test'}}))
        doc=document('ciena','revenue',dict(name='Ciena',currency='USD',fiscal_start=11,scope='group',capex_basis='cash PPE'),dict(rows=rows),{})
        self.assertEqual(doc['series']['매출'],[[r['date'],100] for r in rows])

    def test_ifrs_annual_is_not_replaced_by_partial_year_or_future(self):
        f=lambda start,end,value,filed:dict(start=start,end=end,val=value,filed=filed,accn='0000000000-26-000001',form='20-F')
        payload={'cik':924613,'facts':{'ifrs-full':{'ProfitLossFromOperatingActivities':{'units':{'EUR':[
            f('2025-01-01','2025-12-31',-5000000,'2026-03-01'),
            f('2026-01-01','2026-06-30',2000000,'2026-08-01'),
            f('2025-01-01','2025-12-31',999000000,'2027-03-01')]}}}}}
        rows=ifrs_annual(payload,dict(cik=924613,currency='EUR'),'2026-10-26')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['profit'],-5)

    def test_pdf_note_column_and_parent_column_are_excluded(self):
        doc=pymupdf.open();p=doc.new_page()
        p.insert_text((40,100),'Operating profit');p.insert_text((210,100),'2')
        for x,value in [(260,'(50)'),(330,'147'),(410,'999'),(490,'888')]:p.insert_text((x,100),value)
        self.assertEqual(row_values(p,'Operating profit',2,240),[-50,147])

    def test_nokia_restatement_uses_same_document_for_q1(self):
        doc=pymupdf.open()
        for heading,labels in [('Consolidated income statement (condensed)', [('Net sales',[4815,4443,9248,8743]),('Operating profit',[-50,147,33,151])]),('Consolidated statement of cash flows (condensed)', [('Purchase of property, plant and equipment and intangible assets',[-129,-121,-283,-290])])]:
            p=doc.new_page(width=900,height=600);p.insert_text((35,35),heading);p.insert_text((35,60),'EUR million')
            for x,text in [(500,"Q2'26"),(590,"Q2'25"),(680,"Q1-Q2'26"),(770,"Q1-Q2'25")]:p.insert_text((x,80),text)
            for index,(label,values) in enumerate(labels):
                y=120+index*24
                p.insert_text((35,y),label,fontsize=9)
                for x,value in zip([500,590,680,770],values):p.insert_text((x,y),str(value),fontsize=9)
        rows=parse_nokia_pdf(doc.tobytes(),'https://issuer.test/recast.pdf',2026,2,'2026-10-26')
        q1=next(r for r in rows if r['year']==2026 and r['quarter']==1)
        self.assertEqual((q1['revenue'],q1['profit'],q1['capex']),(4433,83,154))
        q2=next(r for r in rows if r['year']==2026 and r['quarter']==2)
        self.assertEqual(q2['profit'],-50)


if __name__=='__main__':unittest.main()

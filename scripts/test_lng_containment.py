import unittest
import io
import json
from pathlib import Path
import zipfile
from shipbuilding_equipment_sources import report,accounts
from fetch_lng_containment import business_document,ROOT
from lng_containment_sources import reviewed_rows
from build_lng_containment_kpis import korean_business,gtt_business,period_end_quote


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

    def test_gtt_total_operating_profit_and_no_fabricated_quarters(self):
        sources=json.loads((ROOT/'manual/lng-containment/gtt-reviewed.json').read_text(encoding='utf8'))
        rows=reviewed_rows(sources,'2026-10-27')
        annual=next(r for r in rows if r['kind']=='annual' and r['year']==2025)
        self.assertEqual(annual['profit'],472.6)  # includes non-current -48.7; not EBIT 521.3
        self.assertEqual(annual['netincome'],413.6)
        h1=next(r for r in rows if r['kind']=='half' and r['start']=='2026-01-01')
        self.assertEqual((h1['profit'],h1['netincome']),(248.2,210.4))
        self.assertTrue(all('profit' not in r and 'netincome' not in r for r in rows if r['kind']=='quarter'))
        q3=next(r for r in rows if r['kind']=='quarter' and r['date']=='2026-09-30')
        self.assertAlmostEqual(q3['revenue'],182.8)
        self.assertTrue(all(r['date']<='2026-10-27' for r in rows))

    def test_business_xml_never_chooses_attached_audit_report(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('first.xml','<DOCUMENT><DOCUMENT-NAME>연결감사보고서</DOCUMENT-NAME></DOCUMENT>'.encode('utf8'))
            z.writestr('second.xml','<DOCUMENT><DOCUMENT-NAME>사업보고서</DOCUMENT-NAME><P>보냉재</P></DOCUMENT>'.encode('cp949'))
        result=business_document(b.getvalue()).decode('utf8')
        self.assertIn('사업보고서',result)
        self.assertNotIn('연결감사보고서',result)

    def test_domestic_backlog_uses_last_amount_and_explicit_unit(self):
        raw='<p>(단위 : 백만원)</p><table><tr><td>수주총액 기납품액 수주잔고</td></tr><tr><td>초저온보냉재</td><td>2,417,695</td><td>376,610</td><td>2,041,085</td></tr></table>'
        row=korean_business(raw,'dongsung_finetec','2026-06-30','20260814002437')
        self.assertEqual(row['backlog'],2041085)
        self.assertEqual(row['backlog_currency'],'KRW')
        self.assertNotIn('backlog',korean_business(raw.replace('백만원','개'),'dongsung_finetec','2026-06-30','20260814002437'))
        raw=raw.replace('백만원','천USD').replace('초저온보냉재','LNG운반선 화물창판넬').replace('2,041,085','1,161,108')
        self.assertEqual(korean_business(raw,'hankuk_carbon','2026-06-30','20260814000604')['backlog'],1161.108)

    def test_gtt_core_units_include_tanks_and_fuel_is_separate(self):
        text='Orders received: 71 LNG carriers, 2 ethane carriers, 5 onshore storage tanks, 1 FSRU, 1 FLNG; As of September 30, 2026, the order book, excluding LNG as fuel, stood at 299 units, broken down as follows: - 266 LNG carriers; Regarding LNG as fuel, with the delivery of 8 vessels, there were 40 vessels in the order book at September 30, 2026. Press release'
        r=gtt_business(text,dict(year=2026,quarter=3,url='https://www.gtt.fr/report.pdf',filed='2026-10-23'))
        self.assertEqual([r[k] for k in ['core_book','lng_book','fuel_book','core_orders_ytd','lng_orders_ytd']],[299,266,40,80,71])

    def test_stock_fx_uses_latest_published_observation_not_period_average(self):
        rates={'2026-06-25':{'KRW':1390},'2026-06-26':{'KRW':1400},'2026-06-29':{'KRW':1500}}
        q=period_end_quote(rates,'KRW','2026-06-28')
        self.assertEqual((q['observed'],q['local_per_usd']),('2026-06-26',1400))
        self.assertIsNone(period_end_quote(rates,'KRW','2026-07-20'))

    def test_latest_financial_cards_and_kpi_catalog_are_connected(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        gas=next(i for i in catalog['industries'] if i['id']=='natgas')
        sections=[s for s in gas['sections'] if s.get('tab')=='containment']
        self.assertEqual([len(s['indicators']) for s in sections],[5,5,5])
        ids=[id for s in sections for id in s['indicators']]
        self.assertEqual(len(set(ids)),15)
        self.assertTrue(all((ROOT/'data/natgas'/f'{id}.json').exists() for id in ids))
        self.assertEqual(sections[0]['indicators'][-2:],['containment_gtt_backlog','containment_gtt_orders'])
        self.assertEqual(next(t for t in gas['tabs'] if t['id']=='containment')['name'],'보냉재')
        self.assertFalse(any(t['id']=='containment_kpis' for t in gas['tabs']))


if __name__=='__main__':unittest.main()

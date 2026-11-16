"""Financial-definition regressions: maturities, reopening keys, TIPS and nulls."""
import json
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
from us_treasury_sources import (ROOT, merge_auctions, normalize_auction, parse_borrowing,
                                 parse_statement, parse_yields, parse_calendar, number)


class TreasuryTests(unittest.TestCase):
    def raw(self, **kw):
        return dict(cusip='X',security_type='Note',security_term='9-Year 10-Month',original_security_term='10-Year',
                    inflation_index_security='No',floating_rate='No',auction_date='2026-10-07',issue_date='2026-10-15',
                    reopening='Yes',offering_amt='39000000000',high_yield='4.2',bid_to_cover_ratio='2.5',
                    direct_bidder_accepted='20',indirect_bidder_accepted='60',primary_dealer_accepted='20',**kw)

    def test_reopenings_and_allocations(self):
        r=normalize_auction(self.raw());self.assertEqual(r['term'],'10-Year');self.assertTrue(r['reopening'])
        self.assertEqual(r['amount'],39);self.assertEqual(r['indirect'],60)
        # Same CUSIP at two auctions must remain two observations.
        a=self.raw();b=dict(a,auction_date='2026-09-09');self.assertEqual(len(merge_auctions([a,b],[])),2)
        self.assertIsNone(normalize_auction(dict(a,inflation_index_security='Yes')))
        self.assertIsNone(normalize_auction(dict(a,floating_rate='Yes')))
        replacement=normalize_auction(dict(a,security_term='2-Year',original_security_term='7-Year'))
        self.assertEqual(replacement['term'],'2-Year')
        self.assertEqual(replacement['original_term'],'7-Year')
        self.assertTrue(normalize_auction(dict(a,offering_amt='25000000'))['small_value'])

    def test_updated_schema_and_missing_results(self):
        old=self.raw();new=dict(old,inflation_protected='No',comp_auction_close_date=old['auction_date'],
            dir_bid_comp_par_awarded='10',indir_bid_comp_par_awarded='70',prim_deal_comp_par_awarded='20')
        r=merge_auctions([old],[new]);self.assertEqual(len(r),1);self.assertEqual(r[0]['indirect'],70)
        pending=dict(new,high_yield='null',bid_to_cover_ratio='null')
        self.assertEqual(merge_auctions([old],[pending])[0]['bid_to_cover'],2.5)
        self.assertFalse(normalize_auction(pending,True)['completed'])
        self.assertIsNone(normalize_auction(pending,True)['indirect'])
        self.assertIsNone(number('null'));self.assertEqual(number('0'),0)

    def test_borrowing_signs_and_trillion(self):
        html='''<time datetime="2026-11-02"></time><div class="field--name-field-news-body">
        During the October–December 2026 quarter, Treasury expects to borrow $1.250 trillion in privately-held net marketable debt, assuming an end-of-December cash balance of $850 billion.
        During the July–September 2026 quarter, Treasury paid down $25 billion and ended the quarter with a cash balance of $984 billion.
        Additional financing details.</div>'''
        v=parse_borrowing(html,'source');self.assertEqual(v['rows'][0]['borrowing'],1250)
        self.assertEqual(v['rows'][0]['cash'],850);self.assertEqual(v['rows'][1]['borrowing'],-25)
        self.assertEqual(v['rows'][1]['status'],'actual')

    def test_plan_months_and_year_rollover(self):
        html='''<time datetime="2026-11-04"></time><div class="field--name-field-news-body"><table>
        <tr><th></th><th>10-Year</th><th>30-Year</th></tr>
        <tr><td>Oct-26</td><td>39</td><td>22</td></tr>
        <tr><td>Nov-26</td><td>42</td><td>25</td></tr>
        <tr><td>Jan-27</td><td>39</td><td>22</td></tr></table></div>'''
        v=parse_statement(html,'source');self.assertEqual(v['monthly'][0]['status'],'reported_actual')
        self.assertEqual(v['monthly'][2]['status'],'plan');self.assertEqual(v['monthly'][-1]['month'],'2027-01')

    def test_xml_null_and_spread(self):
        xml='''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"><entry><content><m:properties><d:NEW_DATE>2026-11-13T00:00:00</d:NEW_DATE><d:BC_2YEAR>4.2</d:BC_2YEAR><d:BC_10YEAR>4.1</d:BC_10YEAR><d:BC_30YEAR m:null="true"/></m:properties></content></entry></feed>'''
        row=parse_yields(xml)[0];self.assertEqual(row['spread'],-10);self.assertIsNone(row['30'])

    def test_tentative_calendar_excludes_tips_and_holidays(self):
        row='<SecurityTermWeekYear>10-Year</SecurityTermWeekYear><SecurityType>NOTE</SecurityType><TIPS>N</TIPS><FloatingRate>N</FloatingRate><AuctionDate>2027-01-12</AuctionDate><ReOpeningIndicator>Y</ReOpeningIndicator>'
        xml='<AuctionCalendar><AuctionCalendarDate>'+row+'</AuctionCalendarDate><AuctionCalendarDate>'+row.replace('<TIPS>N','<TIPS>Y')+'</AuctionCalendarDate><AuctionCalendarDate><HolidayDate>2027-01-01</HolidayDate></AuctionCalendarDate></AuctionCalendar>'
        rows=parse_calendar(xml);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['date'],'2027-01-12');self.assertTrue(rows[0]['reopening'])

    def test_published_integrity(self):
        folder=ROOT/'data/us-treasury'
        if not (folder/'auctions.json').exists():self.skipTest('First source bootstrap')
        rows=json.loads((folder/'auctions.json').read_text(encoding='utf-8'))['rows']
        self.assertGreater(len(rows),700);self.assertEqual(len(rows),len({(r['date'],r['cusip']) for r in rows}))
        for r in rows:
            if r['completed']:
                self.assertGreater(r['bid_to_cover'],0);self.assertIsNotNone(r['high_yield'])
            if r['direct'] is not None:
                self.assertAlmostEqual(r['direct']+r['indirect']+r['dealer'],100,places=4)
        yields=json.loads((folder/'yields.json').read_text(encoding='utf-8'))['rows']
        self.assertEqual(yields,sorted(yields,key=lambda r:r['date']));self.assertGreater(len(yields),2000)
        self.assertTrue(yields[0]['date'].startswith('2014'))

    def test_refresh_failure_retains_last_success_and_updates_other_sources(self):
        import fetch_us_treasury as collector
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            for name in ['qra','auctions','yields']:
                (out/(name+'.json')).write_text(json.dumps(dict(ok=True,checked='2026-11-13',fetched='2026-11-13',rows=[{'kept':1}])),'utf-8')
            with patch.object(collector,'OUT',out),patch('sys.argv',['fetch_us_treasury.py']),patch.object(collector,'today',return_value='2026-11-16'),patch.object(collector,'collect_qra',side_effect=ValueError('simulated source outage')),patch.object(collector,'collect_auctions',return_value={'rows':[{'new':2}]}),patch.object(collector,'collect_yields',return_value={'rows':[{'new':3}]}):
                with self.assertRaises(SystemExit):collector.main()
            qra=json.loads((out/'qra.json').read_text('utf-8'))
            self.assertFalse(qra['ok']);self.assertEqual(qra['fetched'],'2026-11-13');self.assertEqual(qra['rows'],[{'kept':1}])
            self.assertEqual(json.loads((out/'auctions.json').read_text('utf-8'))['rows'],[{'new':2}])
            state=json.loads((out/'state.json').read_text('utf-8'));self.assertFalse(state['ok']);self.assertTrue(state['sources']['yields']['ok'])


if __name__=='__main__':unittest.main()

import unittest
import copy
import datetime as dt

from fetch_quantum import document
from quantum_sources import period, sec_rows, derive_first_quarters, reviewed_table, holdings
from fetch_quantum_prices import parse


class QuantumTests(unittest.TestCase):
    def test_etf_price_identity_and_unfinished_session(self):
        stamp=lambda day:int(dt.datetime.fromisoformat(day).timestamp())
        raw=dict(chart=dict(result=[dict(meta=dict(symbol='QNTM.L',currency='USD',instrumentType='ETF',exchangeName='LSE',dataGranularity='1d',exchangeTimezoneName='Europe/London',
            currentTradingPeriod={'regular':{'end':stamp('2026-10-28T16:30:00+00:00')}}),
            timestamp=[stamp('2026-10-27T08:00:00+00:00'),stamp('2026-10-28T08:00:00+00:00')],indicators=dict(quote=[dict(close=[30,31])],adjclose=[dict(adjclose=[30,31])]))]))
        rows=parse(raw,'qntm_ucits','2026-10-28',stamp('2026-10-28T12:00:00+00:00'))
        self.assertEqual(rows,[['2026-10-27',30,30]])
        for field,value in [('symbol','QNTM'),('instrumentType','EQUITY'),('currency','GBP'),('exchangeName','NCM'),('dataGranularity','1mo')]:
            wrong=copy.deepcopy(raw);wrong['chart']['result'][0]['meta'][field]=value
            with self.assertRaises(ValueError):parse(wrong,'qntm_ucits','2026-10-28',stamp('2026-10-28T12:00:00+00:00'))

    def fact(self, start, end, value, filed='2026-08-01'):
        return dict(start=start, end=end, val=value, filed=filed, accn='0000000001-26-000001', form='10-Q')

    def test_spac_and_future_filings_are_excluded_and_net_loss_is_group_total(self):
        meta=dict(cik=1, filing_floor='2026-03-01', tags={'revenue':['Revenues'], 'netincome':['ProfitLoss','NetIncomeLoss']})
        f=lambda val,day='2026-08-01':self.fact('2026-04-01','2026-06-30',val,day)
        payload=dict(cik=1, facts={'us-gaap':{
            'Revenues':{'units':{'USD':[f(2e6),f(9e9,'2026-11-01')]}},
            'ProfitLoss':{'units':{'USD':[f(-6e6),f(9e6,'2026-02-01')]}},
            'NetIncomeLoss':{'units':{'USD':[f(-1e6)]}}}})
        rows=sec_rows(payload,meta,'2026-10-26')
        self.assertEqual((rows[0]['revenue'],rows[0]['netincome']),(2,-6))
        with self.assertRaises(ValueError):sec_rows(dict(payload,cik=2),meta,'2026-10-26')

    def test_ytd_subtraction_never_crosses_fiscal_year(self):
        facts=[self.fact('2025-01-01','2025-03-31',5e6),self.fact('2026-01-01','2026-06-30',8e6)]
        rows=sec_rows(dict(cik=1,facts={'us-gaap':{'Revenues':{'units':{'USD':facts}}}}),dict(cik=1,tags={'revenue':['Revenues']}),'2026-10-26')
        self.assertFalse(any(r['kind']=='quarter' and r['date']=='2026-06-30' for r in rows))

    def test_same_statement_h1_minus_q2_replaces_old_unrestated_q1(self):
        rows=[]
        for start,end,value,filed in [('2025-01-01','2025-03-31',8.303,'2026-05-15'),('2025-01-01','2025-06-30',13.472,'2026-08-18'),('2025-04-01','2025-06-30',5.277,'2026-08-18')]:
            r=period(start,end,'USD');r['revenue']=value;r['refs']={'revenue':dict(url='https://www.sec.gov/recast' if filed=='2026-08-18' else 'https://www.sec.gov/old',filed=filed,start=start,end=end)};rows.append(r)
        first=next(r for r in derive_first_quarters(rows) if r['date']=='2025-03-31')
        self.assertAlmostEqual(first['revenue'],8.195)
        self.assertIn('minus Q2',first['refs']['revenue']['calculation'])

    def test_reviewed_table_uses_native_sgd_not_convenience_usd(self):
        source=dict(table=0,filed='2026-04-16',url='https://www.sec.gov/source',guards=['2024','2025','SGD'],
            numeric_columns=3,scale_to_millions=1e-6,labels={'revenue':'Revenue','profit':'Loss from operations'},
            columns=[dict(index=0,start='2024-01-01',end='2024-12-31',currency='SGD'),dict(index=1,start='2025-01-01',end='2025-12-31',currency='SGD')],location='group accounts')
        raw=b'<table><tr><th>2024 SGD 2025 SGD USD</th></tr><tr><td>Revenue</td><td>13</td><td>360,000</td><td>50,000</td><td>38,883</td></tr><tr><td>Loss from operations</td><td>(7,851,403)</td><td>(22,057,337)</td><td>(17,153,229)</td></tr></table>'
        rows=reviewed_table(raw,source,'2026-10-26')
        self.assertAlmostEqual(rows[1]['profit'],-22.057337)
        self.assertAlmostEqual(rows[1]['revenue'],.05)
        with self.assertRaises(ValueError):reviewed_table(raw.replace(b'SGD',b'EUR'),source,'2026-10-26')

    def test_half_only_default_fx_and_visible_empty_quarter(self):
        r=period('2026-01-01','2026-06-30','EUR');r['revenue']=4.872
        r['refs']['revenue']=dict(url='https://www.sec.gov/source',tag='Revenue')
        meta=dict(name='Pasqal',scope='QPU and cryostats',comparability_note='half year only',ir_url='https://www.pasqal.com')
        fx={'periods':{'EUR|2026-01-01|2026-06-30':dict(local_per_usd=.8,observations=125,first='2026-01-02',last='2026-06-30')}}
        doc=document('pasqal','revenue',meta,dict(rows=[r],status='ok'),fx)
        self.assertEqual(doc['default_view'],'half')
        self.assertFalse(doc['series_views']['quarter']['series'])
        self.assertAlmostEqual(doc['series']['매출'][0][1],6.09)
        self.assertIn('4.872000 백만 EUR',doc['point_notes']['2026-06-30'][1])
        self.assertNotIn('supporting_sources',doc['point_sources']['2026-06-30'])

    def test_holdings_do_not_treat_swap_as_ordinary_stock(self):
        rows=[('IONQ','Ionq','1','12.40%'),('CUSIP-TRS-X','Ionq-swap','2','9.10%'),('HQ','Horizon','3','8.76%'),('QNT','Quantinuum','4','4.87%'),('Cash&Other','Cash','5','-25.30%')]
        raw='Data as of 10/26/2026<table>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in (*r,'100'))+'</tr>' for r in rows)+'</table>'
        snapshot=holdings(raw,'2026-10-26')
        self.assertEqual([r['kind'] for r in snapshot['positions']],['equity','derivative','equity','equity','cash'])
        with self.assertRaises(ValueError):holdings(raw,'2026-10-25')

    def test_missing_period_is_a_gap_and_pending_review_is_not_healthy(self):
        rows=[]
        for start,end,value in [('2025-01-01','2025-03-31',-2),('2025-07-01','2025-09-30',-4)]:
            r=period(start,end,'USD');r['profit']=value;r['refs']['profit']=dict(url='https://www.sec.gov/source',tag='OperatingIncomeLoss');rows.append(r)
        meta=dict(name='Company',scope='group',comparability_note='',ir_url='https://www.sec.gov')
        doc=document('c','profit',meta,dict(rows=rows,status='ok',source_errors=['new 6-K requires mapping']),{})
        self.assertEqual(doc['series']['영업이익'],[['2025-03-31',-2],['2025-06-30',None],['2025-09-30',-4]])
        self.assertFalse(doc['span_gaps'])
        self.assertFalse(doc['collection_status']['ok'])
        self.assertIn('new 6-K',doc['basis_details'][-1]['value'])


if __name__=='__main__':unittest.main()

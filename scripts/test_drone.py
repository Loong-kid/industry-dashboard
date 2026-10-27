import copy,datetime as dt,json,unittest
from pathlib import Path
from drone_sources import accounts,prepare,prices,indexed
from fetch_drone import financial_document,ROOT


class DroneTests(unittest.TestCase):
    def fact(self,start,end,value,tag='Revenues',filed='2026-08-10',accn='0000000001-26-000001'):
        return dict(start=start,end=end,val=value,filed=filed,accn=accn,form='10-Q')

    def source(self,items):
        return dict(cik=1,facts={'us-gaap':{k:dict(units={'USD':v}) for k,v in items.items()}})

    def submissions(self,ends):
        return dict(cik='1',filings=dict(recent=dict(accessionNumber=['0000000001-26-000001']*len(ends),reportDate=ends,form=['10-Q']*len(ends))))

    def meta(self,**kw):
        return dict(cik=1,ticker='TEST',minimum_start='2020-01-01',fiscal_start=1,**kw)

    def test_actual_periods_losses_and_missing_ytd_not_divided(self):
        f=self.fact
        p=self.source({'Revenues':[f('2026-01-01','2026-06-30',6e6),f('2026-04-01','2026-06-30',4e6),f('2026-01-01','2026-09-30',9e6,filed='2026-11-10')],
            'OperatingIncomeLoss':[f('2026-04-01','2026-06-30',-3e6)],'NetIncomeLoss':[f('2026-04-01','2026-06-30',-4e6)]})
        rows=accounts(p,self.submissions(['2026-06-30']),self.meta(),'2026-10-27')
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['revenue'],rows[0]['profit'],rows[0]['netincome']),(4,-3,-4))
        self.assertFalse(any(r['date']=='2026-03-31' for r in rows))
        with self.assertRaises(ValueError):accounts(dict(p,cik=2),self.submissions([]),self.meta(),'2026-10-27')

    def test_ytd_difference_requires_same_fiscal_start_and_tag(self):
        f=self.fact
        p=self.source({'Revenues':[f('2026-01-01','2026-03-31',2e6),f('2026-01-01','2026-06-30',6e6)],
            'OperatingIncomeLoss':[f('2026-01-01','2026-03-31',-1e6),f('2026-01-01','2026-06-30',-3e6)],
            'NetIncomeLoss':[f('2026-01-01','2026-03-31',-2e6),f('2026-01-01','2026-06-30',-5e6)]})
        rows=accounts(p,self.submissions(['2026-06-30']),self.meta(),'2026-10-27')
        last=rows[-1];self.assertEqual((last['revenue'],last['profit'],last['netincome']),(4,-2,-3))
        self.assertEqual(len(last['refs']['revenue']['components']),2)
        bad=copy.deepcopy(p);bad['facts']['us-gaap']['Revenues']['units']['USD'][0]['start']='2025-01-01'
        with self.assertRaises(ValueError):
            accounts(bad,self.submissions(['2026-06-30']),self.meta(),'2026-10-27')

    def test_rcat_operating_subtotal_does_not_cross_filings(self):
        f=self.fact;meta=self.meta();meta['ticker']='RCAT'
        p=self.source({'GrossProfit':[f('2020-05-01','2020-07-31',3e6)],'OperatingExpenses':[f('2020-05-01','2020-07-31',5e6)]})
        result=prepare(p,meta)['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD'];self.assertEqual(result[0]['val'],-2e6)
        self.assertNotIn('OperatingIncomeLoss',p['facts']['us-gaap'])
        p['facts']['us-gaap']['OperatingExpenses']['units']['USD'][0]['accn']='another'
        self.assertFalse(prepare(p,meta)['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD'])

    def test_only_completed_daily_matching_symbol_prices(self):
        def stamp(s):return int(dt.datetime.fromisoformat(s).timestamp())
        payload=dict(chart=dict(result=[dict(meta=dict(symbol='DRNZ',currency='USD',dataGranularity='1d',exchangeTimezoneName='America/New_York',currentTradingPeriod={'regular':{'end':stamp('2026-10-27T20:00:00+00:00')}}),
            timestamp=[stamp('2026-10-26T13:30:00+00:00'),stamp('2026-10-27T13:30:00+00:00')],indicators=dict(quote=[dict(close=[20,21])],adjclose=[dict(adjclose=[19.5,21])]))],error=None))
        rows=prices(payload,'DRNZ','2026-10-27',stamp('2026-10-27T15:00:00+00:00'))
        self.assertEqual(rows,[['2026-10-26',20,19.5]])
        with self.assertRaises(ValueError):prices(payload,'JEDI','2026-10-27',0)
        payload['chart']['result'][0]['meta']['dataGranularity']='1mo'
        with self.assertRaises(ValueError):prices(payload,'DRNZ','2026-10-27',0)
        day,series=indexed({'A':[['2025-01-01',10,10],['2025-01-02',20,20]],'B':[['2025-01-02',5,5],['2025-01-03',6,6]]})
        self.assertEqual(day,'2025-01-02');self.assertEqual(series['A'][0][1],100);self.assertEqual(series['B'][0][1],100)

    def test_public_financial_and_price_definitions(self):
        meta=json.loads((ROOT/'manual/drone_universe.json').read_text(encoding='utf-8'))
        state=json.loads((ROOT/'data/drone/state.json').read_text(encoding='utf-8'))
        anchors={'rcat':('2026-06-30',20.189,-38.645),'uavs':('2026-06-30',2.685971,-5.605631),
                 'umac':('2026-06-30',16.722467,-7.834143),'avav':('2026-08-01',480.49,-10.871),'onds':('2026-06-30',83.772,-162.946)}
        for key,(end,revenue,profit) in anchors.items():
            cohort=state['companies'][key];rows=cohort['rows']
            r=next(r for r in rows if r['kind']=='quarter' and r['date']==end)
            self.assertAlmostEqual(r['revenue'],revenue);self.assertAlmostEqual(r['profit'],profit)
            self.assertEqual(len(rows),len({(r['kind'],r['date']) for r in rows}))
            for metric in ('revenue','profit','netincome'):
                doc=financial_document(key,metric,meta['companies'][key],cohort)
                self.assertEqual(doc,json.loads((ROOT/f'data/drone/company_{key}_{metric}.json').read_text(encoding='utf-8')))
                self.assertIn('annual',doc['series_views']);self.assertFalse(doc['span_gaps'])
                self.assertTrue(any(v is not None for d,v in next(iter(doc['series'].values()))))
                for row in rows:
                    if metric in row:self.assertLessEqual(row['refs'][metric]['filed'],cohort['checked'])
        rcat=state['companies']['rcat']['rows']
        self.assertAlmostEqual(next(r for r in rcat if r['kind']=='quarter' and r['date']=='2024-07-31')['revenue'],2.776535)
        self.assertTrue(any(r['kind']=='transition' and r['start']=='2024-05-01' and r['date']=='2024-12-31' for r in rcat))
        self.assertFalse(any(r['kind']=='annual' and r['date']=='2024-12-31' for r in rcat))
        for ticker,data in state['prices'].items():
            rows=data['rows'];self.assertEqual(len(rows),len({r[0] for r in rows}));self.assertTrue(all(d<=data['checked'] for d,c,a in rows))
            self.assertGreaterEqual(len(rows),200)
        self.assertGreaterEqual(state['prices']['UMAC']['rows'][0][0],'2024-02-14')
        self.assertGreaterEqual(state['prices']['DRNZ']['rows'][0][0],'2025-10-29')

    def test_catalog_company_scope_and_all_24_chart_links(self):
        cat=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'));sector=next(i for i in cat['industries'] if i['id']=='drone')
        identifiers=[i for s in sector['sections'] for i in s['indicators']]
        self.assertEqual(len(identifiers),24);self.assertEqual(len(set(identifiers)),24)
        for identifier in identifiers:self.assertTrue((ROOT/f'data/drone/{identifier}.json').exists())
        self.assertEqual([t['id'] for t in sector['tabs']],['overview','prices','platforms','components','expanded'])
        meta=json.loads((ROOT/'manual/drone_universe.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['companies']['avav']['group'],'expanded')
        self.assertEqual(meta['companies']['onds']['group'],'expanded')
        self.assertEqual(meta['companies']['umac']['group'],'components')
        self.assertEqual([e['ticker'] for e in meta['etfs']],['DRNZ','JEDI'])


if __name__=='__main__':unittest.main()

"""Price-only sector momentum: market sessions, no look-ahead filling and baskets."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from fetch_momentum import ROOT, OUT, REGISTRY, fetch_snapshot, naver_price_rows, validate_universe
from momentum_model import WINDOWS, build_market, equal_weight_history, metrics


def calendar(count=300):
    first=dt.date(2024,1,1)
    return [(first+dt.timedelta(days=i)).isoformat() for i in range(count)]


def rows(dates,base=100,step=1):
    return [[date,base+step*i] for i,date in enumerate(dates)]


class MomentumTests(unittest.TestCase):
    def test_registry_is_explicit_and_unleveraged_with_versioned_baskets(self):
        config=json.loads(REGISTRY.read_text(encoding='utf-8'))
        validate_universe(config)
        self.assertEqual([len(m['industries']) for m in config['markets']],[25,24])
        industries=[r for m in config['markets'] for r in m['industries']]
        self.assertEqual(sum(r['kind']=='etf' for r in industries),43)
        self.assertEqual(sum(r['kind']=='basket' for r in industries),6)
        for row in industries:
            if row['kind']=='basket':
                self.assertEqual(row['membership_asof'],'2026-11-26')
                self.assertGreaterEqual(len(row['instruments']),3)
            self.assertTrue(row['scope'])
        duplicate=copy.deepcopy(config)
        duplicate['markets'][0]['industries'].append(duplicate['markets'][0]['industries'][0])
        with self.assertRaises(AssertionError):
            validate_universe(duplicate)

    def test_return_uses_the_exact_market_anchor_not_last_n_available_prices(self):
        dates=calendar()
        prices=rows(dates)
        benchmark=rows(dates,base=100,step=.5)
        values=metrics(dates,prices,benchmark)
        for key,lag in WINDOWS.items():
            self.assertAlmostEqual(values[key],(prices[-1][1]/prices[-1-lag][1]-1)*100,places=6)
        missing=[r for r in prices if r[0]!=dates[-22]]
        self.assertIsNone(metrics(dates,missing,benchmark)['ret_1m'])
        self.assertIsNotNone(metrics(dates,missing,benchmark)['ret_3m'])
        self.assertIsNone(metrics(dates,missing,benchmark)['sma50_gap'])
        no_end=prices[:-1]
        self.assertTrue(all(metrics(dates,no_end,benchmark)[key] is None for key in WINDOWS))

    def test_excess_return_is_percentage_points_and_ma_requires_every_session(self):
        dates=calendar()
        prices=rows(dates)
        benchmark=rows(dates,base=100,step=.5)
        result=metrics(dates,prices,benchmark)
        expected=((prices[-1][1]/prices[-64][1]-1)-(benchmark[-1][1]/benchmark[-64][1]-1))*100
        self.assertAlmostEqual(result['relative_3m'],expected,places=6)
        self.assertAlmostEqual(result['sma200_gap'],(prices[-1][1]/(sum(p[1] for p in prices[-200:])/200)-1)*100,places=6)
        self.assertEqual(result['trend'],'up')
        decreasing=rows(dates,base=500,step=-1)
        self.assertEqual(metrics(dates,decreasing,benchmark)['trend'],'down')
        self.assertEqual(metrics(dates[:50],prices[:50],benchmark[:50])['trend'],'unavailable')

    def test_equal_weight_rebalancing_and_no_silent_member_substitution(self):
        dates=calendar(3)
        a=list(zip(dates,[100,110,99]))
        b=list(zip(dates,[100,100,110]))
        self.assertEqual(equal_weight_history(dates,[a,b]),[[dates[0],100],[dates[1],105],[dates[2],105]])
        gap=[b[0],b[2]]
        self.assertEqual(equal_weight_history(dates,[a,gap]),[[dates[0],100],[dates[2],104.5]])
        ipo=b[1:]
        result=equal_weight_history(dates,[a,ipo])
        self.assertEqual(result[0],[dates[1],100])
        self.assertEqual(len(result),2)
        self.assertEqual(equal_weight_history(dates,[a,[]]),[])

    def test_delayed_member_or_benchmark_failure_is_not_ranked_as_current(self):
        dates=calendar()
        instrument=lambda key:{'symbol':key,'name':key,'source_url':'https://example.com'}
        spec={'id':'us','name':'US','currency':'USD','timezone':'America/New_York','benchmark':instrument('SPY'),
              'industries':[{'id':'basket','name':'basket','kind':'basket','instruments':[instrument('A'),instrument('B')]}]}
        snapshots={symbol:{'prices':rows(dates),'ok':True,'errors':[],'fetched':'2024-10-26'} for symbol in ('SPY','A','B')}
        snapshots['B']['prices']=snapshots['B']['prices'][:-1]
        doc=build_market(spec,snapshots,'2024-10-27T08:40:00+09:00','test')
        self.assertEqual(doc['rows'][0]['status'],'stale')
        self.assertFalse(doc['rows'][0]['eligible'])
        self.assertEqual(doc['rows'][0]['member_coverage'],1)
        self.assertIsNone(doc['rows'][0]['metrics']['ret_3m'])
        snapshots['SPY']['ok']=False
        self.assertEqual(build_market(spec,snapshots,'2024-10-27T08:40:00+09:00','test')['rows'][0]['status'],'benchmark_error')

    def test_korean_chart_uses_close_column_and_conservative_completed_day(self):
        payload={'basic':{'itemCode':'123456','stockExchangeType':{'code':'KS'},'stockName':'sample'},
                 'chart_xml':'<protocol><chartdata symbol="123456" timeframe="day" name="sample"><item data="20261124|999|999|90|100|123"/><item data="20261125|999|999|90|110|456"/></chartdata></protocol>'}
        before=dt.datetime(2026,11,25,8,59,tzinfo=dt.timezone.utc)
        after=dt.datetime(2026,11,25,9,0,tzinfo=dt.timezone.utc)
        self.assertEqual(naver_price_rows(payload,'123456.KS',before,'2019-01-01')[0],[['2026-11-24',100]])
        self.assertEqual(naver_price_rows(payload,'123456.KS',after,'2019-01-01')[0][-1],['2026-11-25',110])
        wrong=copy.deepcopy(payload);wrong['basic']['itemCode']='654321'
        with self.assertRaisesRegex(ValueError,'issuer'):
            naver_price_rows(wrong,'123456.KS',after,'2019-01-01')
        with self.assertRaisesRegex(ValueError,'venue'):
            naver_price_rows(payload,'123456.KQ',after,'2019-01-01')

    def test_us_intraday_candle_is_excluded_and_network_failure_retains_evidence(self):
        def stamp(day,hour):
            return int(dt.datetime(2026,11,day,hour,tzinfo=dt.timezone.utc).timestamp())
        payload={'chart':{'error':None,'result':[{'meta':{'symbol':'SPY','currency':'USD','dataGranularity':'1d','exchangeTimezoneName':'America/New_York','instrumentType':'ETF','exchangeName':'PCX','longName':'SPY','currentTradingPeriod':{'regular':{'end':stamp(25,21)}}},'timestamp':[stamp(24,14),stamp(25,14)],'indicators':{'quote':[{'close':[100,120]}]}}]}}
        instrument={'symbol':'SPY','quote_type':'ETF'}
        market={'id':'us','currency':'USD','timezone':'America/New_York'}
        now=dt.datetime(2026,11,25,17,tzinfo=dt.timezone.utc)
        response=Mock();response.json.return_value=payload
        with tempfile.TemporaryDirectory() as folder,patch('fetch_momentum.CACHE',Path(folder)),patch('fetch_momentum.requests.get',return_value=response):
            result=fetch_snapshot(instrument,market,{},now,'2019-01-01')
        self.assertTrue(result['ok'])
        self.assertEqual(result['prices'],[['2026-11-24',100]])
        old=copy.deepcopy(result)
        offline=fetch_snapshot(instrument,market,old,now+dt.timedelta(hours=12),'2019-01-01',offline=True)
        self.assertEqual(offline['prices'],[['2026-11-24',100]])
        self.assertEqual(offline['fetched'],old['fetched'])
        with patch('fetch_momentum.requests.get',side_effect=requests.ConnectionError('offline')),patch('fetch_momentum.time.sleep'):
            failed=fetch_snapshot(instrument,market,old,now,'2019-01-01')
        self.assertFalse(failed['ok'])
        self.assertEqual(failed['prices'],old['prices'])
        self.assertEqual(failed['fetched'],old['fetched'])

    def test_published_metrics_reconcile_to_raw_prices_and_all_market_calendars(self):
        config=json.loads(REGISTRY.read_text(encoding='utf-8'))
        snapshots=json.loads((OUT/'state.json').read_text(encoding='utf-8'))['snapshots']
        for market in config['markets']:
            doc=json.loads((OUT/('momentum_'+market['id']+'.json')).read_text(encoding='utf-8'))
            rebuilt=build_market(market,snapshots,doc['collected_at'],config['version'])
            self.assertEqual(doc,rebuilt)
            self.assertEqual(len(doc['rows']),len(market['industries']))
            self.assertEqual(doc['updated'],doc['calendar'][-1])
            self.assertEqual(doc['calendar'],sorted(set(doc['calendar'])))
            for row in doc['rows']:
                self.assertEqual(row['history'],sorted(row['history']))
                self.assertTrue(all(d<=doc['updated'] and v>0 for d,v in row['history']))
                self.assertEqual(len(row['history']),len(dict(row['history'])))
                if row['eligible']:
                    self.assertEqual(row['price_date'],doc['updated'])
                    self.assertEqual(row['status'],'ok')
                    self.assertIsNotNone(row['metrics']['ret_3m'])
                for instrument in row['instruments']:
                    expected='naver' if market['id']=='kr' else 'yahoo'
                    self.assertEqual(instrument['provider'],expected)
                    self.assertTrue(instrument['price_source'].startswith('https://'))
        source=(ROOT/'.github/workflows/publish-data.yml').read_text(encoding='utf-8')
        self.assertIn('update-momentum',source)
        self.assertIn('update-momentum',(ROOT/'scripts/actions_digest.py').read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()

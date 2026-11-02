import copy,datetime as dt
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch

import fetch_entertainment as entertainment
import fetch_cosmetics as domestic
from ring_financial_sources import parse_report,accounts,number
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
META=entertainment.read(ROOT/'manual/entertainment/companies.json')
STATE=entertainment.read(ROOT/'data/entertainment/state.json')
ASOF=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()


class EntertainmentFinancials(unittest.TestCase):
    def test_four_issuers_and_confirmed_history(self):
        self.assertEqual(list(META['companies']),['hybe','sm','jyp','yg'])
        tickers=['352820','041510','035900','122870']
        self.assertEqual([s['ticker'] for s in META['companies'].values()],tickers)
        for key,co in STATE['companies'].items():
            entertainment.validate(co,ASOF)
            self.assertEqual(co['entity']['ticker'],META['companies'][key]['ticker'])
            self.assertIn(2025,[r['year'] for r in co['annual']])
            self.assertTrue(all(r['year']<int(ASOF[:4]) for r in co['annual']))
            if key!='hybe':self.assertEqual(co['annual'][0]['year'],2014)

    def test_actual_quarter_income_and_ytd_cash_are_distinct(self):
        fixtures=entertainment.read(ROOT/'manual/entertainment/statement-fixtures.json')
        reports=[]
        for q in [1,2]:
            raw=fixtures[f'jyp-2026-q{q}-CFS.json']
            reports.append(parse_report(raw['list'],2026,q,STATE['companies']['jyp']['entity']['corp_code'],'CFS'))
        rows=accounts(reports,ASOF)['rows'];quarter=next(r for r in rows if r['date']=='2026-06-30')
        self.assertEqual(quarter['revenue'],reports[1]['fields']['revenue']['value'])
        self.assertAlmostEqual(quarter['capex'],reports[1]['fields']['capex']['ytd']-reports[0]['fields']['capex']['ytd'],places=6)
        self.assertEqual(len(quarter['refs']['capex']['components']),2)
        self.assertEqual(len(quarter['refs']['revenue']['components']),1)

    def test_music_rights_and_acquisitions_are_not_ppe_cash_capex(self):
        fixtures=entertainment.read(ROOT/'manual/entertainment/statement-fixtures.json')
        raw=copy.deepcopy(fixtures['jyp-2026-q2-CFS.json']['list'])
        corp=STATE['companies']['jyp']['entity']['corp_code']
        before=parse_report(raw,2026,2,corp,'CFS')['fields']['capex']['ytd']
        original=next(r for r in raw if r.get('sj_div')=='CF')
        for tag,name in [('ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities','무형자산의 취득'),('ifrs-full_PaymentsToAcquireSubsidiariesNetOfCashAcquired','종속기업 취득')]:
            raw.append(dict(original,account_id=tag,account_nm=name,thstrm_amount='900000000000',frmtrm_q_amount='800000000000'))
        self.assertEqual(parse_report(raw,2026,2,corp,'CFS')['fields']['capex']['ytd'],before)
        with self.assertRaises(ValueError):parse_report(raw,2026,2,'wrong-issuer','CFS')

    def test_jyp_original_cash_table_reconciles_separate_cip(self):
        review=entertainment.read(ROOT/'manual/entertainment/cash-review.json')
        for case in review:
            table=BeautifulSoup(case['html'],'html.parser')
            rows=[[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)] for tr in table.select('tr')]
            start=next(i for i,r in enumerate(rows) if r and ''.join(r[0].split())=='투자활동현금흐름')
            stop=next(i for i,r in enumerate(rows) if i>start and r and ''.join(r[0].split())=='재무활동현금흐름')
            # Both purchases are peer rows: the original CFI reconciles only
            # when CIP is counted independently, rather than as a subtotal.
            self.assertEqual(number(rows[start][1]),sum(number(r[1]) or 0 for r in rows[start+1:stop]))
            self.assertEqual(sum('건설중인자산의취득'==''.join(r[0].split()) for r in rows[start+1:stop]),1)
        fixtures=entertainment.read(ROOT/'manual/entertainment/statement-fixtures.json');reports=[]
        for q in [1,2,3,4]:
            reports.append(entertainment.normalize(fixtures[f'jyp-2019-q{q}-CFS.json']['list'],2019,q,STATE['companies']['jyp']['entity']['corp_code'],'CFS',META['companies']['jyp']))
        rows=[r for r in accounts(reports,ASOF)['rows'] if r['year']==2019]
        self.assertEqual(len(rows),4)
        for row,expected in zip(rows,[522.054356,226.738988,555.567421,442.209820]):self.assertAlmostEqual(row['capex'],expected,places=6)
        self.assertAlmostEqual(sum(r['capex'] for r in rows),1746.570585,places=6)

    def test_official_annual_consolidated_anchors(self):
        # SM's official highlights contain both OFS and CFS: use the latter.
        sm=next(r for r in STATE['companies']['sm']['annual'] if r['year']==2025)
        self.assertEqual((round(sm['revenue']/100),round(sm['profit']/100)),(11749,1830))
        yg=next(r for r in STATE['companies']['yg']['annual'] if r['year']==2025)
        self.assertEqual((round(yg['revenue']),round(yg['profit'])),(545404,71342))

    def test_docs_tabs_and_original_sources(self):
        docs=entertainment.build(META,STATE);self.assertEqual(len(docs),12)
        industry=next(i for i in entertainment.read(ROOT/'data/catalog.json')['industries'] if i['id']=='entertainment')
        self.assertEqual(industry['auto_collect_time'],'09:55')
        for tab,count in [('overview',12),('hybe',3),('sm',3),('jyp',3),('yg',3)]:
            linked=[id for s in industry['sections'] if s.get('tab')==tab for id in s['indicators']]
            self.assertEqual(len(linked),count);self.assertTrue(set(linked)<=docs.keys())
        for id,doc in docs.items():
            self.assertEqual(doc,entertainment.read(ROOT/'data/entertainment'/(id+'.json')))
            self.assertEqual(doc['unit'],'KRW 백만');self.assertFalse(doc['span_gaps'])
            self.assertEqual(doc['default_view'],'quarter')
            self.assertNotEqual(doc['series_views']['annual']['series'],doc['series_views']['quarter']['series'])
            self.assertTrue(doc['series_views']['annual']['annual_axis'])
            self.assertTrue(doc['source_url'].startswith('https://dart.fss.or.kr/'))
            self.assertNotIn('crtfc_key',str(doc))
        for key,co in STATE['companies'].items():
            for row in co.get('provisional_rows',[]):
                self.assertNotIn('capex',row)
                self.assertIn('잠정',docs[f'company_entertainment_{key}_revenue']['period_labels'][row['date']])
                self.assertNotIn(row['date'],docs[f'company_entertainment_{key}_capex']['period_labels'])

    def test_failed_source_preserves_history_and_uses_own_cache(self):
        before=copy.deepcopy(STATE)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(entertainment,'CACHE',Path(directory)):
                failed=entertainment.offline(META,STATE,ASOF)
        for key,co in failed['companies'].items():
            self.assertFalse(co['ok'])
            for field in ['rows','annual','fetched']:self.assertEqual(co[field],STATE['companies'][key][field])
        self.assertEqual(STATE,before)
        # Supplying a new sector cache does not mutate the cosmetics default.
        self.assertEqual(domestic.CACHE,ROOT/'.cache/cosmetics')


if __name__=='__main__':unittest.main()

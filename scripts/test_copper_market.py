import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
import derive_copper_market as m
import fetch_copper_tc as tc
import fetch_copper_tc_mysteel as mysteel
import fetch_copper_lme_warrants as lme


def tc_html(value='-231.68', date='Sep 30, 2026'):
    return (f'<div><a href="/Copper/201910240001">{tc.PRODUCT} ($/dmt)</a>'
        f'<div>{value}-{value}</div><div>{value}</div><div>-7.15</div><div>{date}</div></div>')


class CopperMarketTests(unittest.TestCase):
    def setUp(self):
        self.sources = json.loads((m.ROOT/'manual/copper_market_sources.json').read_text(encoding='utf-8'))

    def test_lme_exact_source_tonnage_and_share(self):
        doc = m.lme_document(self.sources)
        self.assertEqual(doc['updated'], '2026-10-02')
        self.assertEqual([points[-1][1] for points in doc['series'].values()], [134650, 114000, 248650])
        share = next(iter(doc['series_views']['share']['series'].values()))[-1][1]
        self.assertAlmostEqual(share, 114000/248650*100, places=4)
        self.assertNotEqual(share, 47.01)
        self.assertEqual(len(next(iter(doc['series'].values()))), 1)
        self.assertNotIn('daily_changes', doc)
        self.assertTrue(doc['manual'])

    def test_bad_lme_records_rejected(self):
        cases = [dict(total=248700), dict(cancelled=-1), dict(reported_cancelled_share=46.5),
            dict(reported_previous_share=101), dict(unit='short tons'), dict(date='2026-10-10')]
        for change in cases:
            source = copy.deepcopy(self.sources)
            source['lme_warrants'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.lme_document(source)
        source = copy.deepcopy(self.sources)
        source['lme_warrants'].append(source['lme_warrants'][0])
        with self.assertRaises(ValueError): m.lme_document(source)

    def test_tc_negative_positive_and_monthly_separation(self):
        row = tc.parse_public_row(tc_html(), '2026-10-09')
        self.assertEqual(row['value'], -231.68)
        self.assertEqual(row['date'], '2026-09-30')
        self.assertEqual(row['unit'], 'USD/dmt')
        self.assertEqual(tc.parse_public_row(tc_html('60'), '2026-10-09')['value'], 60)
        for text in [tc_html().replace('201910240001', '201910240002'),
            tc_html().replace('($/dmt)', '($/mt)'), tc_html()+tc_html(),
            tc_html('NaN'), tc_html('login to view'), tc_html(date='Oct 10, 2026'),
            tc_html().replace('<div>-231.68</div>', '<div>-230</div>')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                tc.parse_public_row(text, '2026-10-09')

    def test_tc_history_dates_and_conflicting_revision(self):
        row = tc.parse_public_row(tc_html(), '2026-10-09')
        doc = tc.merge({}, self.sources['tc_history'], row, '2026-10-09')
        self.assertEqual(len(doc['series'][tc.NAME]), 3)
        self.assertEqual(doc['updated'], '2026-09-30')
        self.assertFalse(any('RC' in key for key in doc['series']))
        self.assertEqual(tc.merge(doc, self.sources['tc_history'], row, '2026-10-09')['series'], doc['series'])
        bad = dict(row, value=-231.5)
        with self.assertRaises(ValueError): tc.merge(doc, [], bad, '2026-10-09')
        with self.assertRaises(ValueError): tc.merge(doc, [], dict(row, date='2026-09-29'), '2026-10-09')

    def test_network_failure_keeps_tc_observation_and_fetch_date(self):
        old = tc.merge({}, [], tc.parse_public_row(tc_html(), '2026-10-08'), '2026-10-08')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/(tc.ID+'.json')
            path.write_text(json.dumps(old), encoding='utf-8')
            with patch.object(tc, 'OUT', Path(folder)), patch.object(m, 'OUT', Path(folder)), \
                 patch.object(tc.requests, 'get', side_effect=requests.HTTPError('403')):
                with self.assertRaises(requests.HTTPError): tc.run('2026-10-09')
            after = json.loads(path.read_text(encoding='utf-8'))
            for field in ['updated', 'fetched', 'series', 'source_records']:
                self.assertEqual(after[field], old[field])
            self.assertFalse(after['collection_status']['ok'])

    def test_premium_pairs_match_provider_date_grade_and_keep_terms(self):
        def doc(contract, rows):
            return dict(unit='USD/톤', fetched='2026-10-09', source_url='https://example.com/',
                source_records=[dict(date=date, grade=grade, provider='Mysteel', contract=contract,
                    midpoint=value, low=value-2, high=value+2, unit='USD/metric tonne',
                    source_url='https://example.com/', delivery_pricing_terms=terms)
                    for date,grade,value,terms in rows])
        warrant = doc('warehouse_warrant', [('2026-09-29','pyrometallurgical',120,'QP09'),
            ('2026-09-30','pyrometallurgical',120,'QP10'), ('2026-09-30','hydrometallurgical',100,'QP10')])
        bill = doc('bill_of_lading', [('2026-09-30','pyrometallurgical',115,'QP11'),
            ('2026-09-30','hydrometallurgical',105,'QP10')])
        result = m.premium_document(warrant, bill)
        self.assertEqual(len(result['source_records']), 2)
        self.assertEqual([p[-1][1] for p in result['series'].values()], [5, -5])
        fire = next(r for r in result['source_records'] if r['grade']=='pyrometallurgical')
        self.assertEqual((fire['warehouse_terms'],fire['bill_of_lading_terms']), ('QP10','QP11'))
        bad = copy.deepcopy(bill)
        bad['source_records'][0]['provider'] = 'SMM'
        with self.assertRaises(ValueError): m.premium_document(warrant, bad)
        bad = copy.deepcopy(bill)
        bad['source_records'].append(bad['source_records'][0])
        with self.assertRaises(ValueError): m.premium_document(warrant, bad)

    def test_published_derived_docs_match_validated_inputs(self):
        def read(name): return json.loads((m.OUT/name).read_text(encoding='utf-8'))
        published = read('comm_copper_lme_warrant_composition.json')
        if published.get('collection_provider') == 'mjfins_archive':
            rebuilt = m.lme_document(dict(reviewed=published['fetched'],lme_warrants=published['source_records']))
            for field in ('series','series_views','updated','history_started'):
                self.assertEqual(published[field],rebuilt[field])
            self.assertGreater(len(published['source_records']),1000)
            self.assertLessEqual(published['history_started'],'2022-01-04')
        else:
            self.assertEqual(published,m.lme_document(self.sources))
        self.assertEqual(read('comm_copper_yangshan_delivery_gap.json'), m.premium_document(
            read('comm_copper_yangshan_warehouse_warrant.json'), read('comm_copper_yangshan_bill_of_lading.json')))

    def test_lme_pdf_dates_columns_and_stock_identity(self):
        text = ('8/10/2026\nLME库存报告\n伦敦铜\n239875\n300\n4950\n235225\n-4650\n129700\n105525\n44.9%\n伦敦锌')
        def parse(value):return lme.parse_text(value,'2026-10-08','2026-10-09',lme.pdf_url('2026-10-08'),'abc')
        row = parse(text)
        self.assertEqual((row['total'],row['live'],row['cancelled']),(235225,129700,105525))
        self.assertTrue(row['flows_valid'])
        self.assertEqual(row['share_precision'],1)
        for bad in [text.replace('8/10/2026','9/10/2026'),text.replace('129700','129725'),
                text.replace('44.9%','40.0%'),text.replace('300\n',''),text.replace('105525','-105525')]:
            with self.subTest(value=bad),self.assertRaises(ValueError):parse(bad)

    def test_lme_bad_flow_does_not_invent_or_discard_valid_stocks(self):
        text = '2022/4/28\nLME库存报告\n伦敦铜\n148500\n2000\n200\n150850\n2350\n102100\n48750\n32.32\n伦敦锌'
        row = lme.parse_text(text,'2022-04-28','2026-10-09',lme.pdf_url('2022-04-28'),'abc')
        self.assertFalse(row['flows_valid'])
        self.assertEqual(row['delivered_in'],2000)  # preserve the incorrect source cell, never repair by inference
        good = dict(row,date='2022-04-29',flows_valid=True)
        doc = m.lme_document(dict(reviewed='2026-10-09',lme_warrants=[row,good]))
        self.assertEqual(len(next(iter(doc['series'].values()))),2)
        self.assertEqual(len(next(iter(doc['series_views']['flows']['series'].values()))),1)

    def test_lme_only_public_archive_links(self):
        html = '<a href="/Uploads/LMEData/LME库存报告_20261008.pdf">PDF</a><a href="/login">login</a>'
        self.assertEqual(lme.public_links(html,'2026-10-09'),{'2026-10-08':lme.pdf_url('2026-10-08')})
        with self.assertRaises(ValueError):lme.public_links('<a href="/login">login</a>','2026-10-09')
        with self.assertRaises(ValueError):lme.public_links(html.replace('20261008','20261010'),'2026-10-09')

    def test_mysteel_chart_identity_dates_negatives_and_missing_values(self):
        def payload(dates=None,values=None,code=None):
            return {'status':'200','response':json.dumps({'xAxis':dates or ['2013-01-11','2026-10-09'],
                'datas':[{'indexCode':code or mysteel.CODE,'yAxis':values or ['75','-237.8']}]})}
        rows = mysteel.parse_chart(payload(),'2026-10-09')
        self.assertEqual([r['value'] for r in rows],[75,-237.8])
        self.assertTrue(all(r['provider']=='Mysteel' and r['unit']=='USD/dmt' for r in rows))
        self.assertEqual(len(mysteel.parse_chart(payload(values=['75',None]),'2026-10-09')),1)
        for bad in [payload(code='ID01154993'),payload(dates=['2013-01-11','2013-01-11']),
                payload(dates=['2026-10-09','2013-01-11']),payload(values=['75','NaN']),
                payload(values=['75']),payload(dates=['2013-01-11','2026-10-10']),{'status':'403'}]:
            with self.subTest(payload=bad),self.assertRaises(ValueError):mysteel.parse_chart(bad,'2026-10-09')

    def test_mysteel_failure_or_revision_preserves_history(self):
        rows = mysteel.parse_chart({'status':'200','response':json.dumps({'xAxis':['2013-01-11'],
            'datas':[{'indexCode':mysteel.CODE,'yAxis':['75']}]})},'2026-10-08')
        old = mysteel.build_document(rows,'2026-10-08')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/(mysteel.ID+'.json')
            path.write_text(json.dumps(old),encoding='utf-8')
            with patch.object(mysteel,'OUT',Path(folder)),patch.object(m,'OUT',Path(folder)),\
                    patch.object(mysteel.requests,'get',side_effect=requests.HTTPError('403')):
                with self.assertRaises(requests.HTTPError):mysteel.run('2026-10-09')
            after = json.loads(path.read_text(encoding='utf-8'))
            for field in ('series','source_records','updated','fetched'):
                self.assertEqual(old[field],after[field])
            self.assertFalse(after['collection_status']['ok'])

    def test_published_mysteel_history_matches_original_records(self):
        doc = json.loads((m.OUT/(mysteel.ID+'.json')).read_text(encoding='utf-8'))
        rebuilt = mysteel.build_document(doc['source_records'],doc['fetched'])
        self.assertEqual(doc['series'],rebuilt['series'])
        self.assertEqual(doc['history_started'],'2013-01-11')
        self.assertGreater(len(doc['source_records']),1600)
        points = dict(next(iter(doc['series'].values())))
        self.assertEqual(points['2024-12-26'],7.75)  # independently published daily article
        self.assertEqual(points['2024-07-24'],9.5)


if __name__ == '__main__':
    unittest.main()

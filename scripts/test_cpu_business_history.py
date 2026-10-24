import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import cpu_business_history as history
import fetch_cpu_companies as cpu

ROOT=Path(__file__).resolve().parents[1]


def instance(contexts,facts=''):
    return ('<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:d="http://xbrl.org/2006/xbrldi" xmlns:t="http://example.com">'
        '<unit id="USD"><measure>iso4217:USD</measure></unit>'+contexts+facts+'</xbrl>').encode()


def context(id,start,end,members=()):
    dimensions=''.join(f'<d:explicitMember dimension="t:Axis{i}">{m}</d:explicitMember>' for i,m in enumerate(members))
    return f'<context id="{id}"><entity><identifier>1973239</identifier><segment>{dimensions}</segment></entity><period><startDate>{start}</startDate><endDate>{end}</endDate></period></context>'


FILING=dict(form='10-Q',reportDate='2014-03-29',filingDate='2014-04-24',accessionNumber='test',url='https://example.com/report')


class BusinessHistory(unittest.TestCase):
    def test_dimension_total_not_double_counted_with_related_party(self):
        xml=instance(context('total','2026-04-01','2026-06-30',['us-gaap:RoyaltyMember'])+
            context('related','2026-04-01','2026-06-30',['us-gaap:RoyaltyMember','us-gaap:RelatedPartyMember']),
            '<t:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="total" unitRef="USD">715000000</t:RevenueFromContractWithCustomerExcludingAssessedTax>'+
            '<t:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="related" unitRef="USD">124000000</t:RevenueFromContractWithCustomerExcludingAssessedTax>')
        fields=history.parse_instance(xml,'arm',FILING)
        self.assertEqual([r['val'] for r in fields['royalty']],[715000000])
        self.assertIsNone(history.field_for('qualcomm','Revenues',['qcom:QtlMember','country:CN']))

    def test_old_apple_sales_table_excludes_unit_sales_and_percentages(self):
        xml=instance(context('q','2013-12-29','2014-03-29')+context('p','2012-12-30','2013-03-30')+
            context('y','2013-09-29','2014-03-29')+context('z','2012-09-30','2013-03-30'))
        html='''<table><tr><td>Three Months Ended Six Months Ended March 29, 2014 March 30, 2013</td></tr>
          <tr><td>Net Sales by Product:</td></tr>
          <tr><td>iPhone (1)(2)</td><td>26,064</td><td>22,955</td><td>14</td><td>%</td><td>58,562</td><td>53,615</td><td>9%</td></tr>
          <tr><td>Mac (1)</td><td>5,519</td><td>5,447</td><td>1%</td><td>11,914</td><td>10,966</td><td>9%</td></tr>
          <tr><td>Other Products (1)(3)</td><td>2,189</td><td>1,689</td><td>30%</td><td>6,540</td><td>4,378</td><td>49%</td></tr>
          <tr><td>Unit Sales by Product:</td></tr><tr><td>iPhone</td><td>43,719</td><td>37,430</td><td>17%</td><td>94,744</td><td>85,219</td><td>11%</td></tr></table>'''
        fields=history.parse_apple_legacy(html,xml,FILING)
        current=[r for r in fields['iphone'] if r['start']=='2013-12-29']
        self.assertEqual(current[0]['val'],26064e6)
        self.assertEqual(fields['other_products'][0]['val'],2189e6)

    def test_complete_published_histories_and_reconciliations(self):
        state=cpu.load(ROOT/'data/semicon/cpu_state.json',{})
        docs=cpu.build_business_history(state['business'],cpu.load(ROOT/'manual/cpu_segments.json',{}))
        arm=docs['company_arm_business'];core={r['date']:r['revenue'] for r in state['companies']['arm']['rows']}
        royalty,license=(dict(arm['series'][n]) for n in ('Royalty · 로열티','License and other · 라이선스·기타'))
        self.assertGreaterEqual(len(royalty),16)
        self.assertTrue(all(royalty[d] is not None and license[d] is not None for d in core))
        for date,total in core.items():self.assertEqual(royalty[date]+license[date],total)
        qtl=docs['company_qualcomm_royalty']
        points=next(iter(qtl['series'].values()))
        self.assertGreaterEqual(len(points),50)
        self.assertTrue(all(v is not None for d,v in points))
        self.assertEqual(dict(points)['2026-06-28'],1278)
        apple=docs['company_apple_business']
        mapping={field:dict(apple['series'][label]) for field,label in cpu.load(ROOT/'manual/cpu_segments.json',{})['companies']['apple']['fields'].items()}
        self.assertEqual(mapping['iphone']['2014-03-29'],26064)
        for field in ('iphone','ipad','mac','services'):
            self.assertGreaterEqual(len(mapping[field]),50)
            self.assertTrue(all(v is not None for v in mapping[field].values()))
        for row in state['companies']['apple']['rows']:
            date=row['date']
            tail=mapping['wearables'][date] if mapping['wearables'].get(date) is not None else mapping['other_products'][date] if mapping['other_products'].get(date) is not None else (mapping['ipod'].get(date) or 0)+(mapping['accessories'].get(date) or 0)
            total=sum(mapping[f][date] for f in ('iphone','ipad','mac','services'))+tail
            self.assertAlmostEqual(total,row['revenue'],delta=.001)
        self.assertTrue(all(set(d['series_views'])=={'quarter','annual'} for d in docs.values()))

    def test_unavailable_index_retains_last_successful_history(self):
        old={'arm':dict(facts={'royalty':[dict(val=10)]},filings=['a'],fetched='2026-10-24',ok=True)}
        with patch.object(history.SecClient,'filings',side_effect=ValueError('unavailable')):
            result=history.collect_business({'arm':cpu.COMPANIES['arm']},copy.deepcopy(old),ROOT/'.cache/cpu/test','2026-10-25')
        self.assertFalse(result['arm']['ok'])
        self.assertEqual(result['arm']['facts'],old['arm']['facts'])
        self.assertEqual(result['arm']['fetched'],'2026-10-24')


if __name__=='__main__':unittest.main()

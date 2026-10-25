import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import requests
import fetch_equipment_companies as equipment
from equipment_global_sources import METADATA,build_global_company,parse_asm,parse_adv_report,difference_cumulative,observation

ROOT=Path(__file__).resolve().parents[1]


class EquipmentCompanies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=equipment.load(ROOT/'data/semicon/equipment_state.json',{})

    def test_history_complete_and_matches_official_anchors(self):
        anchors={'lam':('2026-09-27',8219.418,3283.727,257.697),
            'amat':('2026-07-26',9115,3075,707),'kla':('2026-06-30',3657.556,1553.948,89.288)}
        for key,(end,revenue,profit,capex) in anchors.items():
            cohort=self.state['companies'][key];rows=cohort['rows']
            self.assertGreaterEqual(len(rows),50)
            self.assertTrue(rows[0]['date'].startswith('2014'))
            row=next(r for r in rows if r['date']==end)
            for metric,value in [('revenue',revenue),('profit',profit),('capex',capex)]:
                if row['refs'][metric]['filed']<='2026-10-25':self.assertAlmostEqual(row[metric],value)
            self.assertEqual(len(rows),len({(r['year'],r['quarter']) for r in rows}))
            for row in rows+cohort['annual']:
                for metric in ('revenue','profit','capex'):
                    self.assertIn(metric,row)
                    for ref in row['refs'][metric]['components']:
                        self.assertTrue(ref['url'].startswith('https://www.sec.gov/Archives/edgar/data/'))
                        self.assertLessEqual(ref['filed'],cohort['checked'])

    def test_kla_derivation_requires_same_accession_and_period(self):
        def f(value,accn='same',start='2025-07-01'):
            return dict(start=start,end='2026-06-30',val=value,accn=accn,filed='2026-08-06',form='10-K')
        tags={'RevenueFromContractWithCustomerExcludingAssessedTax':f(13579476000),
              'CostOfRevenue':f(5255060000),'ResearchAndDevelopmentExpense':f(1532118000),
              'SellingGeneralAndAdministrativeExpense':f(1131518000),'AssetImpairmentCharges':f(0),
              'GainsLossesOnExtinguishmentOfDebt':f(-100000000)}
        payload=dict(facts={'us-gaap':{tag:dict(units={'USD':[value]}) for tag,value in tags.items()}})
        result=equipment.prepare_payload('kla',payload)['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD']
        self.assertEqual(result[0]['val'],5660780000)
        self.assertEqual(len(result[0]['inputs']),5)
        self.assertNotIn('OperatingIncomeLoss',payload['facts']['us-gaap'])
        for key,change in [('accn','other'),('start','2025-07-02')]:
            wrong=copy.deepcopy(payload)
            wrong['facts']['us-gaap']['SellingGeneralAndAdministrativeExpense']['units']['USD'][0][key]=change
            self.assertFalse(equipment.prepare_payload('kla',wrong)['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD'])
        reported=copy.deepcopy(payload)
        reported['facts']['us-gaap']['OperatingIncomeLoss']=dict(units={'USD':[f(-100)]})
        self.assertEqual(equipment.prepare_payload('kla',reported)['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD'][0]['val'],-100)
        impaired=copy.deepcopy(payload)
        impaired['facts']['us-gaap']['AssetImpairmentCharges']['units']['USD'][0]['val']=1000000
        impaired['facts']['us-gaap']['GoodwillImpairmentLoss']=dict(units={'USD':[f(999999)]})
        self.assertEqual(equipment.prepare_payload('kla',impaired)['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD'][0]['val'],5659780000)

    def test_actual_kla_derived_inputs_reconcile_and_exclude_nonoperating_items(self):
        cohort=self.state['companies']['kla']
        for row in cohort['rows']+cohort['annual']:
            ref=row['refs']['profit'];calculated=[]
            for component in ref['components']:
                if not component.get('derivation'):break
                values=component['inputs']
                self.assertTrue(values[0]['tag'].endswith(('SalesRevenueNet','Revenues','RevenueFromContractWithCustomerExcludingAssessedTax')))
                self.assertFalse(any('Interest' in v['tag'] or 'Debt' in v['tag'] for v in values))
                calculated.append((values[0]['value']-sum(v['value'] for v in values[1:]))/1e6)
            else:
                if calculated:self.assertAlmostEqual(row['profit'],calculated[0] if len(calculated)==1 else calculated[0]-calculated[1])

    def test_docs_scope_periods_and_catalog(self):
        catalog=equipment.load(ROOT/'data/catalog.json',{})
        industry=next(i for i in catalog['industries'] if i['id']=='semicon')
        self.assertEqual([(c['id'],c['default_tab']) for c in industry['material_categories']],
            [('equipment','equipment_summary'),('components','snstech'),('raw_materials','wafer')])
        linked={id for s in industry['sections'] if s.get('tab')=='equipment_summary' for id in s['indicators']}
        docs={}
        for key,company in equipment.COMPANIES.items():
            docs.update(equipment.build_company(key,self.state['companies'][key],company))
        for key,company in METADATA.items():
            docs.update(build_global_company(key,self.state['companies'][key],company))
        self.assertEqual(set(docs),linked)
        self.assertEqual(len(docs),39)
        for identifier,doc in docs.items():
            self.assertEqual(doc,equipment.load(ROOT/'data/semicon'/(identifier+'.json'),{}))
            self.assertNotIn('CPU',doc['description'])
            self.assertIn('annual',doc['series_views'])
        self.assertIn('무형자산',docs['company_lam_capex']['description'])
        self.assertIn('계산',docs['company_kla_profit']['description'])
        kla=self.state['companies']['kla']['annual'][-1]
        if kla['date']=='2026-06-30' and kla['refs']['profit']['filed']<='2026-10-25':self.assertAlmostEqual(kla['profit'],5660.78)
        for year,value in [(2015,661.34),(2020,1502.201),(2023,3994.696)]:
            row=next(r for r in self.state['companies']['kla']['annual'] if r['year']==year)
            if row['refs']['profit']['filed']<='2026-10-25':self.assertAlmostEqual(row['profit'],value)

    def test_failure_preserves_previous_success_and_flags_it(self):
        with tempfile.TemporaryDirectory() as path:
            out=Path(path);equipment.save(out/'equipment_state.json',self.state)
            with patch.object(equipment,'OUT',out),patch.object(equipment,'CACHE',out/'cache'),patch.object(equipment.time,'sleep'),patch.object(requests.Session,'get',side_effect=requests.RequestException):
                result=equipment.collect()
            for key in equipment.COMPANIES:
                self.assertFalse(result['companies'][key]['ok'])
                self.assertEqual(result['companies'][key]['rows'],self.state['companies'][key]['rows'])
                self.assertFalse(equipment.load(out/f'company_{key}_revenue.json',{})['collection_status']['ok'])

    def test_foreign_units_and_reported_profit_anchors(self):
        anchors={'asml':('2026-09-27',11662,5172.8,413.3),
            'tel':('2026-06-30',732388,211407,None),
            'asm':('2026-06-30',1003.1,322.8,63.1),
            'screen':('2026-06-30',121775,14368,None),
            'disco':('2026-09-30',142750,67606,8959),
            'besi':('2026-09-30',283.4,129.679,2.825),
            'hanmi':('2026-06-30',251163.039356,130346.798331,6476.482846),
            'camtek':('2026-06-30',133.2,27.2,None),
            'advantest':('2026-06-30',367473,189990,9852)}
        for key,(date,revenue,profit,capex) in anchors.items():
            cohort=self.state['companies'][key]
            row=next(r for r in cohort['rows'] if r['date']==date)
            for field,value in [('revenue',revenue),('profit',profit),('capex',capex)]:
                if value is not None:self.assertAlmostEqual(row[field],value)
                else:self.assertNotIn(field,row)
            for period in ('rows','annual'):
                dates=[r['date'] for r in cohort[period]]
                self.assertEqual(dates,sorted(set(dates)))
                self.assertTrue(all(d<=cohort['fetched'] for d in dates))
            docs=build_global_company(key,cohort,METADATA[key])
            self.assertEqual(docs[f'company_{key}_revenue']['unit'],METADATA[key]['currency']+' 백만')
            if key in ('tel','screen','camtek'):
                doc=docs[f'company_{key}_capex']
                self.assertEqual(doc['default_view'],'annual')
                self.assertEqual(set(doc['series_views']),{'annual'})
                self.assertEqual(doc['frequency'],'yearly')
        # The issuer's FY begins, rather than ends, in this named calendar year.
        for key in ('disco','advantest'):
            doc=equipment.load(ROOT/f'data/semicon/company_{key}_revenue.json',{})
            self.assertEqual(doc['period_labels']['2026-06-30'],'FY2026 Q1')

    def test_ir_parsers_distinguish_thousands_ytd_and_adjusted_profit(self):
        text='''Financial highlights
€ million Q3 2022 Q2 2023 Q3 2023
Revenue 609.8 669.1 622.3
Normalized operating result 160.0 180.0 157.0
€ thousand
Operating result 159,943 147,301 450,511 522,193
€ thousand
Capital expenditures of property, plant and equipment (21,399) (58,527) (64,402) (129,100)
'''
        row=parse_asm(text,2023,3,'https://www.asm.com/report')
        self.assertEqual(row['revenue'],622.3)
        self.assertEqual(row['profit'],147.301)
        self.assertEqual(row['capex'],58.527)
        adv='''Net sales 263.8 367.5 39.3%
Net sales 263,776 367,473
Operating income 123,952 189,990
Purchases of property, plant and equipment (5,649) (9,852)
'''
        parsed=parse_adv_report(adv,2026,1,'https://www.advantest.com/report')
        self.assertEqual(parsed['revenue'],367473)
        self.assertEqual(parsed['capex'],9852)
        q3=observation(2025,3,1,dict(revenue=90), 'https://example.com/q3')
        q4=observation(2025,4,1,dict(revenue=120,capex=20),'https://example.com/q4')
        rows,annual=difference_cumulative([q3,q4])
        self.assertEqual(rows[-1]['revenue'],30)
        self.assertNotIn('capex',rows[-1])
        self.assertEqual(annual[-1]['capex'],20)

    def test_fields_operational_metrics_and_no_missing_links(self):
        industry=next(i for i in equipment.load(ROOT/'data/catalog.json',{})['industries'] if i['id']=='semicon')
        tabs={t['id']:t for t in industry['tabs']}
        self.assertEqual(tabs['mocvd']['parent_tab'],'equipment_frontend')
        counts={'equipment_summary':39,'equipment_frontend':21,'equipment_packaging':11,'equipment_inspection':6,'equipment_testing':6}
        for tab,count in counts.items():
            ids=[i for s in industry['sections'] if s.get('tab')==tab for i in s['indicators']]
            self.assertEqual(len(ids),count)
            for identifier in ids:self.assertTrue((ROOT/f'data/semicon/{identifier}.json').exists(),identifier)
        docs=equipment.build_operational(self.state['companies'])
        for identifier,doc in docs.items():self.assertEqual(doc,equipment.load(ROOT/f'data/semicon/{identifier}.json',{}))
        mix=self.state['companies']['asml']['rows']
        for row in mix:self.assertAlmostEqual(row['system']+row['service'],row['revenue'])
        self.assertAlmostEqual(next(r for r in self.state['companies']['besi']['annual'] if r['year']==2025)['capex'],15.795)


if __name__=='__main__':unittest.main()

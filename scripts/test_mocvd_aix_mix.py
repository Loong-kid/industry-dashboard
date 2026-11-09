"""YTD denominators, IR pie identity, rounding gaps and existing sales history."""
import copy,json,unittest
import hashlib,pymupdf
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from aixtron_revenue_mix import extract_mix,revenue_rows,DETAIL,COMBINED
from fetch_mocvd import build,merge,collect,aix_report_links

ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'scripts/fixtures/aixtron_mix'
def read(path):return json.loads(path.read_text(encoding='utf8'))

class SourcePage:
    """Factual text coordinates, legend fills and sampled pixels from the PDF."""
    def __init__(self,source=None):
        self.source=source;self.rect=pymupdf.Rect(0,0,*(source['size'] if source else [960,540]))
    def get_text(self,mode=None,clip=None):
        if not self.source:return ''
        return self.source['words'] if mode=='words' else self.source['rawdict'] if mode=='rawdict' else self.source['center_text'] if clip else self.source['text']
    def search_for(self,text):return [pymupdf.Rect(r) for r in self.source['searches'][text]]
    def get_drawings(self):return [dict(r,rect=pymupdf.Rect(r['rect'])) for r in self.source['drawings']]
    def get_pixmap(self,**kwargs):return SimpleNamespace(pixel=lambda x,y:self.source['sampled_pixels'][f'{x},{y}'])

class SourcePDF:
    def __init__(self,name):
        source=read(FIX/(name+'-page.json'));self.pages=[SourcePage() for _ in range(source['pdf_page']-1)]+[SourcePage(source)]
    def __enter__(self):return self.pages
    def __exit__(self,*args):pass

class OriginalPies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reviewed={r['date']:r for r in read(FIX/'reviewed-shares.json')}

    def test_center_pie_maps_to_legend_colors_and_original_period(self):
        for name,year,q,date in [('2026-q3',2026,3,'2026-09-30'),('2026-q2',2026,2,'2026-06-30'),('2022-q1',2022,1,'2022-03-31')]:
            expected=self.reviewed[date];data=name.encode()
            with patch('aixtron_revenue_mix.pymupdf.open',return_value=SourcePDF(name)):r=extract_mix(data,expected['url'],year,q)
            self.assertEqual(r['shares'],expected['shares']);self.assertEqual(r['sha256'],hashlib.sha256(data).hexdigest())
            self.assertEqual(read(FIX/(name+'-page.json'))['source_sha256'],expected['sha256'])
            self.assertEqual(r['scope'],'year_to_date_equipment_revenue')
        q2=self.reviewed['2026-06-30']
        self.assertEqual([q2['shares'][k]['value'] for k in DETAIL],[54,23,16,6,2])
        # 54/18/28 are REGION values on the Q3 slide; equipment is 75%.
        q3=self.reviewed['2026-09-30'];self.assertEqual(q3['shares']['opto']['value'],61)
        self.assertEqual(q3['shares']['gan']['value'],14)
        self.assertEqual(q3['shares']['sic']['value'],5)
        with patch('aixtron_revenue_mix.pymupdf.open',return_value=SourcePDF('2026-q3')):
            with self.assertRaises(ValueError):extract_mix(b'fixture',q3['url'],2026,2)

    def test_ambiguous_legend_does_not_guess_a_new_percentage_order(self):
        q3=self.reviewed['2026-09-30']
        with patch('aixtron_revenue_mix.pymupdf.open',return_value=SourcePDF('2026-q3')),patch('aixtron_revenue_mix.color_tokens',side_effect=ValueError('ambiguous')):
            with self.assertRaises(ValueError):extract_mix(b'fixture',q3['url'],2026,3)

    def test_new_and_historical_report_names_resolve_the_right_quarters(self):
        html=''.join(f'<a href="/investoren/{path}">{label}</a>' for path,label in [
            ('2026/englisch/q3.pdf','QUARTERLY GROUP STATEMENT Q3/2026'),
            ('2026/englisch/h1.pdf','HALF-YEAR GROUP FINANCIAL REPORT H1/2026'),
            ('2026/englisch/q1.pdf','QUARTERLY GROUP STATEMENT Q1/2026'),
            ('2025/en/q3.pdf','9-MONTHS-REPORT 2025')])
        self.assertEqual([(year,q) for _,year,q in aix_report_links(html)],[(2025,3),(2026,1),(2026,2),(2026,3)])

    def test_source_failure_keeps_previous_successful_mix_and_financials(self):
        facts=read(ROOT/'data/_mocvd/facts.json');previous=copy.deepcopy(facts)
        html='<a href="https://example.com/q2.pdf">H1 2026 RESULTS PRESENTATION</a><a href="https://example.com/q3.pdf">Q3 2026 RESULTS PRESENTATION</a>'
        def get(url):
            if url.endswith('q2.pdf'):raise ValueError('source unavailable')
            if url.endswith('q3.pdf'):return SimpleNamespace(content=b'fixture')
            return SimpleNamespace(text=html)
        with patch('fetch_mocvd.get',side_effect=get),patch('fetch_mocvd.sec_earnings.earnings_exhibits',return_value=[]),patch('aixtron_revenue_mix.pymupdf.open',return_value=SourcePDF('2026-q3')):collect(facts)
        self.assertEqual(facts['aix'],previous['aix'])
        self.assertFalse(facts['aix_mix_status']['ok'])
        rows={r['date']:r for r in facts['aix_revenue_mix']};old={r['date']:r for r in previous['aix_revenue_mix']}
        self.assertEqual(rows['2026-06-30'],old['2026-06-30'])
        self.assertGreaterEqual(len(rows),len(old))

class QuarterlyApplicationSales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts=read(ROOT/'data/_mocvd/facts.json');cls.manual=read(ROOT/'manual/mocvd.json');cls.history=read(ROOT/'manual/mocvd_history.json')
        cls.docs=build(copy.deepcopy(cls.facts),copy.deepcopy(cls.manual))
        cls.aix=merge(merge(cls.history['aix'],cls.facts['aix']),cls.manual['aix_annual'])
        cls.rows=revenue_rows(cls.aix,cls.facts['aix_revenue_mix']);cls.combined=revenue_rows(cls.aix,cls.facts['aix_revenue_mix'],True)

    def test_q3_uses_current_and_prior_ytd_money_not_quarter_times_ytd_share(self):
        row=next(r for r in self.rows if r['date']=='2026-09-30')
        expected={'opto':99.003,'led':20.594,'gan':18.322,'sic':6.195,'other':2.966}
        self.assertEqual(row['values'],expected)
        self.assertEqual(row['equipment'],148.3);self.assertEqual(row['after_sales'],35.3)
        self.assertNotAlmostEqual(row['values']['opto'],148.3*.61)
        self.assertEqual(row['rounding_difference'],1.22)
        self.assertNotEqual(sum(row['values'].values()),row['equipment'])
        self.assertEqual(len(row['supporting_sources']),4)
        for k,value in expected.items():
            self.assertLessEqual(row['bounds'][k]['lower'],value);self.assertGreaterEqual(row['bounds'][k]['upper'],value)
        joined=next(r for r in self.combined if r['date']==row['date'])
        self.assertAlmostEqual(joined['values']['power'],expected['gan']+expected['sic'])
        self.assertIn('(14% + 5%)',joined['calculations']['power'])

    def test_full_year_minus_nine_months_and_no_fabricated_category_split(self):
        row=next(r for r in self.rows if r['date']=='2025-12-31')
        self.assertAlmostEqual(row['values']['led'],444.6*.15-289.8*.14,places=3)
        self.assertEqual(self.rows[0]['date'],'2024-03-31')
        self.assertEqual(self.combined[0]['date'],'2022-03-31')
        for r in self.combined:
            if r['date']<'2024-01-01':self.assertNotIn('gan',r['values']);self.assertNotIn('sic',r['values'])
        records={r['date']:r for r in self.facts['aix_revenue_mix']}
        self.assertIsNone(records['2023-06-30']['shares']['other']['value'])
        for date in ['2023-06-30','2023-09-30','2023-12-31','2022-09-30']:
            r=next(r for r in self.combined if r['date']==date)
            self.assertIsNone(r['values']['other']);self.assertTrue(r['notes'])

    def test_quarter_estimates_reconcile_to_the_same_rounded_annual_basis(self):
        financial={r['date']:r for r in self.aix};mix={r['date']:r for r in self.facts['aix_revenue_mix']}
        for year in [2024,2025]:
            rows=[r for r in self.rows if r['year']==year];self.assertEqual(len(rows),4)
            for key in DETAIL:
                expected=financial[f'{year}-12-31']['equipment_ytd']*mix[f'{year}-12-31']['shares'][key]['value']/100
                self.assertAlmostEqual(sum(r['values'][key] for r in rows),expected,delta=.002)

    def test_published_views_and_disclosed_annual_revenues_are_preserved(self):
        for id in ['mocvd_aix_application_revenue','mocvd_aix_application_share','mocvd_aix_revenue_breakdown','mocvd_aix_revenue']:
            self.assertEqual(self.docs[id],read(ROOT/'data/semicon'/(id+'.json')))
        amounts=self.docs['mocvd_aix_application_revenue'];shares=self.docs['mocvd_aix_application_share']
        self.assertEqual(amounts['chart_type'],'line')
        for view in amounts['series_views'].values():
            self.assertEqual(view.get('chart_type',amounts['chart_type']),'line')
        self.assertNotIn('mocvd_aix_order_mix',self.docs)
        self.assertFalse(amounts['span_gaps']);self.assertEqual(set(amounts['series_views']),{'quarter','combined'})
        self.assertGreaterEqual(len(next(iter(amounts['series_views']['quarter']['series'].values()))),11)
        self.assertEqual(shares['change_mode'],'none');self.assertTrue(shares['cumulative_periods'])
        sales=self.docs['mocvd_aix_revenue']
        self.assertEqual(set(sales['series_views']),{'quarter','annual'})
        yearly=sales['series_views']['annual']['series']
        self.assertEqual(yearly['장비 매출'][0][0],'2014-12-31')
        self.assertEqual(dict(yearly['장비 매출'])['2025-12-31'],444.6)
        self.assertEqual(self.docs['mocvd_aix_applications']['series']['광전자·통신'][-1][1],101.4)
        self.assertNotIn('2025-12-31',self.docs['mocvd_aix_applications']['point_annotations'])
        table=self.docs['mocvd_aix_revenue_breakdown'];row=next(r for r in table['rows'] if r['period']=='2026 Q3')
        self.assertEqual(row['equipment'],'148.3');self.assertEqual(row['after_sales'],'35.3')
        self.assertTrue(row['opto'].startswith('약 '));self.assertEqual(row['basis'],'9M/2026 − H1/2026')

if __name__=='__main__':unittest.main()

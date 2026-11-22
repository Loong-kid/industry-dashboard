"""Report tables, source dates and the bulk/container index separation."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import extract_shinyoung as parser

ROOT = Path(__file__).resolve().parents[1]


class ShinyoungTests(unittest.TestCase):
    def test_printed_dates_and_old_report_typographical_variations(self):
        self.assertEqual(parser.parse_header_dates('3-Jul -26 10-Jul-26'), ['2026-07-03','2026-07-10'])
        self.assertEqual(parser.parse_header_dates('7-Jun--2024 14-Jun-2024'), ['2024-06-07','2024-06-14'])
        self.assertEqual(parser.parse_header_dates('30-Aug-2024 6-S-2024'), ['2024-08-30','2024-09-06'])
        self.assertEqual(parser.parse_header_dates('31-Feb-2026'), [])
        document = Mock()
        document.__enter__ = Mock(return_value=document)
        document.__exit__ = Mock(return_value=False)
        document.__getitem__ = Mock(return_value=Mock(get_text=lambda:'2026. 9. 21 #2-169'))
        with patch.object(parser.fitz, 'open', return_value=document):
            self.assertEqual(parser.report_date(Path('260918 download.pdf')), '2026-09-21')

    def test_source_rows_keep_year_end_columns_and_commentary_out_of_weekly_values(self):
        label, size, values = parser.parse_data_row(['Oil','Tankers','430','538','338','642','707','FIRMER!!','121%','46','125'])
        self.assertEqual(label, 'Oil Tankers')
        self.assertEqual(values[-2:], [642,707])
        self.assertEqual(parser.norm_sh('Panamax D/H 5 Yr 중고'), 'Panamax 5Y')

    def test_image_publication_review_applies_only_to_the_verified_file_bytes(self):
        document = Mock()
        document.__enter__ = Mock(return_value=document)
        document.__exit__ = Mock(return_value=False)
        document.__getitem__ = Mock(return_value=Mock(get_text=lambda:''))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'250902 reviewed.pdf'
            path.write_bytes(b'verified original')
            reviews = {hashlib.sha256(path.read_bytes()).hexdigest(): {'report_date':'2025-09-02'}}
            with patch.object(parser.fitz,'open',return_value=document), patch.object(parser.json,'loads',return_value=reviews):
                self.assertEqual(parser.report_date(path),'2025-09-02')
                path.write_bytes(b'replaced file')
                with self.assertRaises(ValueError):
                    parser.report_date(path)

    def test_index_identity_price_classes_and_report_table_coordinates_contract(self):
        dates = ['2026-11-06','2026-11-13']
        tables = {
            '신조선가 동향(단위': (dates, [('VLCC','320,000',[131.5,131.5]), ('LNG','174,000',[245,245]), ('Index Newbuilding Price',None,[187.20,187.15])]),
            '신조선 발주량(단위': (dates, [('TOTAL CONTRACTING',None,[2973,3098]), ('Oil Tankers',None,[642,707])]),
            '중고선가 동향(단위': (dates, [('Tanker',None,None), ('Panamax D/H 5 Yr 중고',None,[76,76]), ('Tanker Secondhand Index(pt)',None,[315.49,315.49]), ('Bulker',None,None), ('Panamax 5 Yr 중고',None,[42,42]), ('Bulk Secondhand Index(pt)',None,[238.82,238.08]), ('Containership',None,None), ('5 Yr 중고','2,750',[48,48]), ('Container Secondhand Index(pt)',None,[88.02,88.02]), ('Secondhand Price(pt)',None,[232.6,232.3])]),
            '선종별 해상운임 추이(단위': (dates, [('VLCC',None,[508633,293038]), ('Panamax',None,[16799,16952]), ('174k cbm LNG',None,[53750,48500]), ('ClarkSeaIndex',None,[64148,55298])]),
        }
        output = {key: {'id': key, 'series': {}} for _, key in parser.META}
        with patch.object(parser.fitz,'open',return_value=Mock()), patch.object(parser,'extract_table',side_effect=lambda doc, anchor: copy.deepcopy(tables[anchor])):
            self.assertEqual(len(parser.extract_pdf('source.pdf',output)),4)
        indices = output['secondhand_index']['series']
        self.assertEqual(indices['벌커 중고선가지수'][-1], ['2026-11-13',238.08])
        self.assertEqual(indices['컨테이너 중고선가지수'][-1], ['2026-11-13',88.02])
        self.assertEqual(indices['탱커 중고선가지수'][-1], ['2026-11-13',315.49])
        self.assertEqual(indices['중고선가지수(종합)'][-1], ['2026-11-13',232.3])
        prices = output['secondhand_prices']['series']
        self.assertEqual(prices['Panamax(탱커) 5Y'][-1][1],76)
        self.assertEqual(prices['Panamax 5Y'][-1][1],42)
        self.assertNotIn('5Y', prices)
        self.assertEqual(output['newbuild_orders']['series']['합계'][-1][1],3098)
        self.assertEqual(output['gas_earnings']['series']['LNG 174k'][-1][1],48500)

    def test_incomplete_report_never_saves_a_partial_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'261116 source.pdf'
            path.write_bytes(b'not needed by the mocked extractor')
            with patch.object(parser,'load_indicator',side_effect=lambda industry, key: {'id':key,'series':{}}), patch.object(parser,'extract_pdf',return_value=['신조선가','발주량','중고선가']), patch.object(parser,'save_indicator') as save:
                with self.assertRaises(ValueError):
                    parser.run(Path(folder))
                save.assert_not_called()

    def test_report_date_observation_date_and_published_anchors(self):
        expected = {
            ('shipbuilding','clarksons_nb_index','신조선가지수'):187.15,
            ('shipbuilding','newbuild_prices','LNG선(174k)'):245,
            ('shipbuilding','newbuild_orders','합계'):3098,
            ('shipbuilding','secondhand_index','벌커 중고선가지수'):238.08,
            ('shipbuilding','secondhand_index','컨테이너 중고선가지수'):88.02,
            ('shipbuilding','secondhand_index','중고선가지수(종합)'):232.3,
            ('shipbuilding','secondhand_prices','VLCC 5Y'):220,
            ('shipping','tanker_earnings','VLCC'):293038,
            ('shipping','bulker_earnings','케이프사이즈'):33837,
            ('shipping','gas_earnings','LNG 174k'):48500,
            ('shipping','clarksea','ClarkSea Index'):55298,
        }
        for (industry,key,series), value in expected.items():
            doc = json.loads((ROOT/'data'/industry/(key+'.json')).read_text(encoding='utf8'))
            self.assertEqual(dict(doc['series'][series])['2026-11-13'], value)
        for industry, key in parser.META:
            doc = json.loads((ROOT/'data'/industry/(key+'.json')).read_text(encoding='utf8'))
            self.assertEqual(doc['updated'],max(row[0] for ps in doc['series'].values() for row in ps))
            self.assertGreaterEqual(doc['latest_report']['report_date'],'2026-11-16')
            self.assertGreaterEqual(doc['fetched'],doc['updated'])
            for ps in doc['series'].values():
                self.assertEqual(ps, sorted(ps))
                self.assertEqual(len(ps),len(dict(ps)))
        manifest = json.loads((ROOT/'manual/shinyoung/reports.json').read_text(encoding='utf8'))
        self.assertEqual(len({r['file'] for r in manifest['reports']}),len(manifest['reports']))
        self.assertTrue(all(len(r['sha256'])==64 for r in manifest['reports']))
        september = next(r for r in manifest['reports'] if r['file'].startswith('260918'))
        self.assertEqual(september['report_date'],'2026-09-21')


if __name__ == '__main__':
    unittest.main()

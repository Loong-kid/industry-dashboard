"""Run with python -m unittest discover -s scripts -p test_holding_document.py."""
import unittest
from holding_document import parse_holding_document, HoldingParseError, number

LISTING={'rcept_no':'20220103000070','rcept_dt':'20220103','corp_code':'00535676',
         'corp_name':'테크윙','report_nm':'주식등의대량보유상황보고서(약식)','flr_nm':'신영자산운용'}

def document(**overrides):
    # Summary values from the public 2022-01-03 Techwing filing.
    values={'THS_STK_RT':'7.77','THS_STK_CNT':'1,506,368','SUM_TMT_RT':'7.77',
            'SUM_TMT_CNT':'1,506,368','BFR_STK_RT':'6.59','BFR_STK_CNT':'1,277,244',
            'MDF_STK_RT':'1.18','MDF_STK_CNT':'229,124','SUM_CHN_RWN':'1% 이상 변동'}
    values.update(overrides)
    return '<DOCUMENT>'+''.join(f'<TE ACODE="{k}">{v}</TE>' for k,v in values.items())+'</DOCUMENT>'

class HoldingDocumentTests(unittest.TestCase):
    def test_old_cp949_and_utf8_are_equivalent(self):
        text=document()
        a=parse_holding_document(text.encode('cp949'),LISTING)
        b=parse_holding_document(text.encode('utf-8'),LISTING)
        self.assertEqual(a,b)
        self.assertEqual(a['stkrt'],'7.77')
        self.assertEqual(a['stkqy_irds'],'229124')
        self.assertEqual(a['rcept_dt'],'2022-01-03')

    def test_missing_is_not_zero(self):
        self.assertIsNone(number('-'))
        with self.assertRaises(HoldingParseError):
            parse_holding_document(b'<DOCUMENT/>',LISTING)

    def test_zero_exit_is_retained(self):
        text=document(THS_STK_RT='0',SUM_TMT_RT='0',THS_STK_CNT='0',SUM_TMT_CNT='0',
                      MDF_STK_RT='-6.59',MDF_STK_CNT='-1,277,244')
        result=parse_holding_document(text.encode(),LISTING)
        self.assertEqual(result['stkrt'],'0')
        self.assertEqual(result['stkrt_irds'],'-6.59')

    def test_contradictory_summary_is_rejected(self):
        with self.assertRaises(HoldingParseError):
            parse_holding_document(document(SUM_TMT_RT='8.0').encode(),LISTING)

    def test_cover_precision_difference_is_accepted(self):
        result=parse_holding_document(document(SUM_TMT_RT='7.774').encode(),LISTING)
        self.assertEqual(result['stkrt'],'7.77')
        with self.assertRaises(HoldingParseError):
            parse_holding_document(document(SUM_TMT_RT='7.776').encode(),LISTING)

    def test_impossible_ratio_is_rejected(self):
        with self.assertRaises(HoldingParseError):
            parse_holding_document(document(THS_STK_RT='500.59',SUM_TMT_RT='500.59').encode(),LISTING)

    def test_contract_ratio_does_not_replace_holdings(self):
        text=document()+'<TE ACODE="CTR_TMT_RT">90</TE>'
        self.assertEqual(parse_holding_document(text.encode(),LISTING)['stkrt'],'7.77')

    def test_duplicate_conflicting_field_is_rejected(self):
        text=document()+'<TE ACODE="THS_STK_RT">9</TE>'
        with self.assertRaises(HoldingParseError): parse_holding_document(text.encode(),LISTING)

if __name__=='__main__': unittest.main()

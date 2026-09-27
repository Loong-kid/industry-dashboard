"""Parse only identified DART holding-summary fields; never infer missing holdings as zero."""
from decimal import Decimal, InvalidOperation
import html
import re

class HoldingParseError(ValueError):
    pass

def decode_document(raw):
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp949')

def field(text, code):
    pattern = r'<([A-Z][A-Z0-9_-]*)\b[^>]*\b(?:ACODE|AUNIT)=["\']' + re.escape(code) + r'["\'][^>]*>(.*?)</\1\s*>'
    values = {re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value).replace('&cr;', ' '))).strip()
              for _, value in re.findall(pattern, text, flags=re.I | re.S)} - {''}
    if len(values) > 1:
        raise HoldingParseError('ambiguous field: ' + code)
    return next(iter(values), '')

def number(value):
    value = re.sub(r'[\s,%]', '', value).replace('−', '-').replace('△', '-').replace('▲', '-')
    if value in ('', '-', '해당없음'):
        return None
    if value.startswith('(') and value.endswith(')'):
        value = '-' + value[1:-1]
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except InvalidOperation:
        raise HoldingParseError('invalid numeric field')

def parse_holding_document(raw, listing):
    text = decode_document(raw)
    def num(code): return number(field(text, code))
    rt, shares = num('THS_STK_RT'), num('THS_STK_CNT')
    cover_rt, cover_shares = num('SUM_TMT_RT'), num('SUM_TMT_CNT')
    if rt is not None and cover_rt is not None and rt != cover_rt:
        raise HoldingParseError('cover/detail ratio mismatch')
    if shares is not None and cover_shares is not None and shares != cover_shares:
        raise HoldingParseError('cover/detail shares mismatch')
    rt = rt if rt is not None else cover_rt
    shares = shares if shares is not None else cover_shares
    if rt is None or shares is None:
        raise HoldingParseError('missing current holding fields')
    if not 0 <= rt <= 100 or shares < 0 or shares != shares.to_integral_value():
        raise HoldingParseError('holding outside expected range')
    chg, qty_chg = num('MDF_STK_RT'), num('MDF_STK_CNT')
    prev_rt, prev_shares = num('BFR_STK_RT'), num('BFR_STK_CNT')
    if chg is None and prev_rt is not None: chg = rt - prev_rt
    if qty_chg is None and prev_shares is not None: qty_chg = shares - prev_shares
    # Allow only rounding differences; contradictory source values require review.
    if chg is not None and prev_rt is not None and abs(rt - prev_rt - chg) > Decimal('0.02'):
        raise HoldingParseError('ratio change mismatch')
    if qty_chg is not None and prev_shares is not None and shares - prev_shares != qty_chg:
        raise HoldingParseError('share change mismatch')
    date = re.sub(r'\D', '', listing['rcept_dt'])
    fmt = lambda n: '' if n is None else format(n, 'f')
    return {
        'rcept_no': listing['rcept_no'], 'rcept_dt': f'{date[:4]}-{date[4:6]}-{date[6:8]}',
        'corp_code': listing.get('corp_code', ''), 'corp_name': listing['corp_name'],
        'report_tp': '약식' if '약식' in listing['report_nm'] else '일반',
        'repror': listing['flr_nm'], 'stkqy': fmt(shares), 'stkqy_irds': fmt(qty_chg),
        'stkrt': fmt(rt), 'stkrt_irds': fmt(chg), 'report_resn': field(text, 'SUM_CHN_RWN'),
    }

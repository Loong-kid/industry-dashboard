"""Parse future stock gifts from identified DART plan fields, never past transactions."""
import datetime as dt
import hashlib
import re
from decimal import Decimal, InvalidOperation
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
PARSER_VERSION = 2


class GiftPlanParseError(ValueError):
    pass


def compact(value):
    return re.sub(r'\s+', '', value or '')


def text(node):
    return node.get_text(' ', strip=True).replace('&cr;', ' ') if node else ''


def field(node, code):
    matches = node.find_all(attrs={'acode': code}) + node.find_all(attrs={'aunit': code})
    values = {text(n) for n in matches} - {''}
    if len(values) > 1:
        raise GiftPlanParseError('ambiguous field: ' + code)
    return next(iter(values), '')


def number(value, integer=False):
    value = compact(value).replace(',', '').replace('%', '').replace('−', '-').replace('△', '-')
    if value in ('', '-', '해당없음'):
        return None
    if value.startswith('(') and value.endswith(')'):
        value = '-' + value[1:-1]
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise GiftPlanParseError('invalid number') from exc
    if not result.is_finite() or (integer and result != result.to_integral_value()):
        raise GiftPlanParseError('non-finite or fractional share count')
    return int(result) if integer else float(result)


def iso_date(value):
    value = compact(value)
    if value in ('', '-'):
        return None
    match = re.fullmatch(r'(\d{4})[.\-/년]?(\d{2})[.\-/월]?(\d{2})일?\.?', value)
    if not match:
        raise GiftPlanParseError('invalid plan date')
    try:
        return dt.date(*map(int, match.groups())).isoformat()
    except ValueError as exc:
        raise GiftPlanParseError('invalid calendar date') from exc


def stock_security(value):
    value = compact(value)
    return bool(re.fullmatch(r'(?:보통주(?:식)?|우선주(?:식)?|종류주(?:식)?|주권|[0-9가-힣]*우선주(?:식)?)', value))


def counterparty(remark):
    match = re.search(r'(?:수증자|증여자)\s*[:：]\s*(.+)', remark)
    return match.group(1).strip() if match else ''


def parse_plan_document(raw, listing):
    if isinstance(raw, bytes):
        try:
            raw = raw.decode('utf-8')
        except UnicodeDecodeError:
            raw = raw.decode('cp949')
    # DART custom TE/TU are XML but legacy bodies may contain non-XML entities.
    soup = BeautifulSoup(raw, 'html.parser')
    title = compact(listing.get('report_nm', '') or field(soup, 'DOCUMENT-NAME'))
    if '거래계획' not in title or '특정증권' not in title:
        raise GiftPlanParseError('not a securities trading plan')
    reporter = field(soup, 'IFR_NM')
    code = field(soup, 'CRP_CD')
    if listing.get('stock_code') and code and listing['stock_code'] != code:
        raise GiftPlanParseError('issuer code mismatch')
    if not reporter or not code:
        raise GiftPlanParseError('missing issuer/reporter identity')
    total = number(field(soup, 'FLT_SUM'), integer=True)
    before_rate = number(field(soup, 'HLD_CMT_RT'))
    after_rate = number(field(soup, 'OWN_HLD_CMT_RT'))
    for value in (before_rate, after_rate):
        if value is not None and not 0 <= value <= 100:
            raise GiftPlanParseError('ownership ratio outside expected range')
    if total is not None and total <= 0:
        raise GiftPlanParseError('invalid issued shares')
    base = {
        'reporter': reporter, 'position': field(soup, 'STF_PSM'),
        'main_sh': field(soup, 'MAIN_SH'), 'stock_code': code,
        'float_total': total, 'before_rate': before_rate, 'after_rate': after_rate,
        'purpose': field(soup, 'TRAN_PPS'),
    }
    events = []
    empty_gift_rows = 0
    plan_tables = [table for table in soup.find_all('table')
                   if any(table.find(attrs={attr: code}) for attr in ('acode', 'aunit')
                          for code in ('MDF_STR_DT', 'MDF_END_DT'))]
    if not plan_tables:
        raise GiftPlanParseError('future transaction table not found')
    for table in plan_tables:
        start, end = None, None
        for row in table.find_all('tr'):
            row_start, row_end = field(row, 'MDF_STR_DT'), field(row, 'MDF_END_DT')
            # Shared date cells use rowspans. Inherit only inside this future plan table.
            if row_start and row_start != '-':
                start = iso_date(row_start)
            if row_end and row_end != '-':
                end = iso_date(row_end)
            method = field(row, 'MDF_MT')
            if not re.fullmatch(r'(?:증여|수증)(?:\([+\-]\))?',compact(method)):
                continue
            security = field(row, 'STR_KND')
            if not stock_security(security):
                continue  # CB/derivative quantities are not numbers of stock gifts.
            shares = number(field(row, 'STR_STK_CNT'), integer=True)
            if not start or not end or end < start or (dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days > 29:
                raise GiftPlanParseError('missing or invalid future transaction period')
            remark = field(row, 'RMK')
            if shares is None and remark in ('','-') and field(row,'ACI_AMT2') in ('','-') and field(row,'TRAN_AMT') in ('','-'):
                # Some filed forms repeat method/security in an otherwise blank template row.
                # Ignore it only when another substantive gift row exists in the document.
                empty_gift_rows += 1
                continue
            if shares is None or shares == 0:
                raise GiftPlanParseError('missing gift share count')
            direction = '수증(받음)' if '수증' in method else '증여(줌)'
            # This column is a transaction quantity, sometimes unsigned even for 증여(-).
            # The explicit method determines the direction; a negative acquisition conflicts.
            if direction.startswith('수증') and shares < 0:
                raise GiftPlanParseError('gift direction/share sign mismatch')
            events.append(dict(base, direction=direction, gift_shares=abs(shares),
                               gift_rate=round(100*abs(shares)/total,4) if total else None,
                               plan_start=start, plan_end=end, security=security,
                               counterparty=counterparty(remark), remark=remark))
    if empty_gift_rows and not events:
        raise GiftPlanParseError('missing gift share count')
    return {'events': events, 'reporter': reporter, 'purpose': base['purpose'],
            'parser_version': PARSER_VERSION, 'sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest()}


def parse_family(raw, current_no):
    """Authoritative DART body selection connects original/correction/withdrawal receipts."""
    soup = BeautifulSoup(raw, 'html.parser')
    selector = soup.select_one('select#family')
    if selector is None:
        raise GiftPlanParseError('DART report family selector unavailable')
    records = []
    for option in selector.find_all('option'):
        match = re.fullmatch(r'rcpNo=(\d{14})', option.get('value', ''))
        title = compact(option.get('title', '') or text(option))
        if match and '특정증권' in title and '거래계획' in title:
            records.append({'rcept_no': match.group(1), 'report_nm': title,
                            'withdrawn': '철회' in title})
    if current_no not in {r['rcept_no'] for r in records}:
        raise GiftPlanParseError('current receipt absent from DART report family')
    return sorted(records, key=lambda row: row['rcept_no'])

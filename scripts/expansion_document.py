"""Extract investment facts from the current body, never the before/after header."""
import datetime as dt
import hashlib
import re
import warnings
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
PARSER_VERSION = 3
CATEGORIES = {'expansion': '생산 증설', 'new_facility': '신설·신사업', 'review': '확인 필요', 'excluded': '기타 시설투자'}


class InvestmentParseError(ValueError):
    pass


def compact(value):
    return re.sub(r'\s+', '', value or '')


def clean(value):
    return re.sub(r'\s+', ' ', value or '').strip()


def iso_date(value):
    if compact(value) in ('', '-', '미정', '해당없음'):
        return None
    match = re.search(r'(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})', value)
    if not match:
        return None
    try:
        return dt.date(*map(int, match.groups())).isoformat()
    except ValueError:
        return None


def number(value):
    value = compact(value).replace(',', '').replace('%', '').replace('△', '-').replace('−', '-')
    if value in ('', '-', '해당없음'):
        return None
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise InvestmentParseError('ambiguous numeric field')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise InvestmentParseError('invalid numeric field') from None
    if not result.is_finite():
        raise InvestmentParseError('non-finite number')
    return int(result) if result == result.to_integral_value() else float(result)


def classify(investment_type, target, purpose):
    """Only the company's stated investment scope supplies classification evidence."""
    scope = clean(' '.join([investment_type, target, purpose]))
    s = compact(scope)
    nonproduction = re.search(r'사옥|업무시설|임대|부동산|상가|호텔|물류센터|연구소|폐수|환경설비|안전설비', s)
    production = re.search(r'생산능력|생산라인|생산시설|제조시설|제조라인|공장|팹|FAB', s, re.I)
    if nonproduction and not production:
        return 'excluded', '생산시설이 아닌 사업장·물류·지원시설 투자'
    if nonproduction and production:
        return 'review', '생산시설과 비생산시설의 복합 투자'
    capacity = re.search(r'증설|생산능력(?:확대|증대|확충)|생산규모(?:확대|증대)|생산량(?:확대|증대)|캐파(?:확대|증대)|CAPA(?:확대|증대)', s, re.I)
    new = re.search(r'신공장|신규공장|생산(?:시설|설비|라인).{0,8}(?:신설|신축|구축)|(?:공장|팹|FAB|제조시설).{0,8}(?:신설|신축|건설)|신규사업.{0,18}양산', s, re.I)
    mixed = re.search(r'노후(?:생산)?(?:설비|시설)|유지보수|설비교체|시설교체|리모델링', s)
    if re.search(r'(?:증설|생산능력확대).{0,6}(?:아님|아니|없음)', s):
        return 'review', '생산능력 확대 여부를 부정·제한하는 표현 확인 필요'
    if capacity:
        return ('review', '생산능력 확대와 교체·보완 목적이 함께 기재됨') if mixed else ('expansion', capacity.group())
    if new:
        if re.search(r'이전|대체공장', s):
            return 'review', '신공장 이전·대체로 생산능력 증가 여부 확인 필요'
        return ('review', '신설과 교체·보완 목적이 함께 기재됨') if mixed else ('new_facility', new.group())
    if re.search(r'사옥|업무시설|임대|부동산|상가|호텔|물류센터|유지보수|노후|교체|환경설비|안전설비|연구소', s):
        return 'excluded', '생산능력 확대가 명시되지 않은 시설투자'
    return 'review', '투자구분·대상·목적만으로 생산능력 확대를 확정하기 어려움'


def parse_document(raw, listing):
    source_hash = hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode('utf-8')).hexdigest()
    if isinstance(raw, bytes):
        try:
            raw = raw.decode('utf-8')
        except UnicodeDecodeError:
            raw = raw.decode('cp949')
    soup = BeautifulSoup(raw, 'html.parser')
    rows = []
    for tr in soup.find_all('tr'):
        cells = [clean(td.get_text(' ', strip=True)) for td in tr.find_all(['td', 'th', 'tu', 'te'], recursive=False)]
        if cells:
            rows.append(cells)
    starts = [i for i, cells in enumerate(rows) if re.match(r'^1[.]?투자구분', compact(cells[0]))]
    if not starts:
        raise InvestmentParseError('investment body not found')
    # The last complete body follows the amendment table. Its rows contain current facts.
    body = rows[starts[-1]:]
    values = {}
    amount_unit_known = False
    for cells in body:
        for i, cell in enumerate(cells[:-1]):
            label = compact(cell).lstrip('-')
            tail = clean(' '.join(cells[i + 1:]))
            if re.fullmatch(r'1[.]?투자구분', label): values['investment_type'] = tail
            elif label in ('투자대상', '투자대상시설'): values['target'] = tail
            elif re.fullmatch(r'3[.]?투자목적', label): values['purpose'] = tail
            elif '투자금액' in label and len(label) < 30:
                scale = 100000000 if '(억원)' in label else 1000000 if '(백만원)' in label else 1000 if '(천원)' in label else 1 if '(원)' in label else None
                if scale:
                    amount_unit_known = True
                    n = number(cells[i + 1]); values['amount_krw'] = n * scale if n is not None else None
            elif re.fullmatch(r'자기자본\(원\)', label): values['equity_krw'] = number(cells[i + 1])
            elif '자기자본대비' in label and '%' in label: values['equity_ratio'] = number(cells[i + 1])
            elif label in ('시작일', '투자시작일'): values['start_date'] = iso_date(tail)
            elif label in ('종료일', '투자종료일'): values['end_date'] = iso_date(tail)
            elif '이사회결의일' in label or '이사회결정일' in label: values['decision_date'] = iso_date(cells[i + 1])
            elif re.match(r'^\d+[.]?기타투자판단', label): values['notes'] = tail
    if not values.get('investment_type') or not values.get('purpose'):
        raise InvestmentParseError('missing investment type/purpose')
    if values.get('amount_krw') is not None and values['amount_krw'] <= 0:
        raise InvestmentParseError('non-positive investment amount')
    notes = values.get('notes', '')
    subsidiary = re.search(r'자회사인\s+(.+?)\s*(?:의\s*주요경영사항|주요경영사항)', soup.get_text(' ', strip=True))
    values['investor'] = clean(subsidiary[1]) if subsidiary else listing.get('corp_name', '')
    values['is_subsidiary'] = bool(subsidiary)
    category, evidence = classify(values['investment_type'], values.get('target', ''), values['purpose'])
    values.update(category=category, category_label=CATEGORIES[category], classification_evidence=evidence)
    values['location'] = ''
    match = re.search(r'(?:투자소재지|투자지역|투자장소|투자위치)\s*[:：-]\s*(.{1,160}?)(?=\s+(?:\d[.]|[가-하][.]|상기)|$)', notes)
    if match: values['location'] = clean(match[1])
    capacity = re.search(r'(?:생산규모|생산능력|연간생산량|생산량)\s*[:：]?\s*(.{1,220}?)(?=\s+(?:\d[.]|[가-하][.]|예상투자|예상 투자|상기)|$)', notes)
    values['capacity_text'] = clean(capacity[0]) if capacity else ''
    correction_date = None
    correction_reason = ''
    for cells in rows[:starts[-1]]:
        if '정정관련공시서류제출일' in compact(cells[0]) and len(cells) > 1: correction_date = iso_date(cells[-1])
        if '정정사유' in compact(cells[0]) and len(cells) > 1: correction_reason = cells[-1]
    values.update(correction_target_date=correction_date, correction_reason=correction_reason,
                  source_sha256=source_hash, parser_version=PARSER_VERSION)
    # Some withdrawals are filed as ordinary text amendments, with a blank current plan.
    values['investment_withdrawn'] = bool(
        values.get('amount_krw') is None and values.get('purpose') in ('', '-') and
        re.search(r'(?:투자|시설).{0,18}(?:철회|취소)', compact(correction_reason)))
    warnings = []
    if values.get('amount_krw') is None:
        warnings.append('투자금액이 미공시되었거나 철회됨' if amount_unit_known else '투자금액의 원화 단위를 확인하지 못함')
    if not values.get('end_date'): warnings.append('투자 종료 예정일 미확인')
    if values.get('start_date') and values.get('end_date') and values['end_date'] < values['start_date']: warnings.append('투자 시작·종료일 순서 확인 필요')
    a, e, r = values.get('amount_krw'), values.get('equity_krw'), values.get('equity_ratio')
    if a and e and r is not None and abs(a / e * 100 - r) > .2: warnings.append('투자금액·자기자본 대비 비율의 정합성 확인 필요')
    values['warnings'] = warnings
    if values.get('amount_krw') is None:
        values.update(category='review', category_label=CATEGORIES['review'])
    return values


def main_metadata(raw, receipt):
    soup = BeautifulSoup(raw, 'html.parser')
    family = []
    for option in soup.select('select#family option'):
        value = option.get('value', '')
        no = re.search(r'(?:^|[?&])rcpNo=(\d{14})', value)
        label = clean(option.get_text(' ', strip=True))
        if no and '신규시설투자' in compact(label):
            family.append(dict(rcept_no=no[1], report_nm=label, rcept_dt=no[1][:8]))
    if not family:
        raise InvestmentParseError('official receipt lineage not found')
    if receipt not in {f['rcept_no'] for f in family}:
        raise InvestmentParseError('receipt absent from official lineage')
    calls = re.findall(r'viewDoc\(\s*"(\d{14})"\s*,\s*"(\d+)"\s*,\s*"([\d]+)"\s*,\s*"([\d]+)"\s*,\s*"([\d]+)"\s*,\s*"([A-Za-z0-9]+)"', raw)
    viewer = next((c for c in calls if c[0] == receipt), None)
    return family, viewer

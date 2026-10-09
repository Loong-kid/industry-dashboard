"""Source-reviewed LME snapshots and matched Yangshan premium differences.

No inferred cancelled tonnage, interpolated history or mixed-provider pairs.
"""
import datetime as dt
import json
import math
from pathlib import Path

from import_yangshan import validate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/commodities'


def check_number(value, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid number')
    if nonnegative and value < 0:
        raise ValueError('Negative stock')


def check_date(value, reviewed):
    if dt.date.fromisoformat(value).isoformat() != value or value > reviewed:
        raise ValueError('Invalid/future date')


def lme_document(source):
    reviewed = source['reviewed']
    records = sorted(source['lme_warrants'], key=lambda r: r['date'])
    dates = set()
    for row in records:
        check_date(row['date'], reviewed)
        check_date(row['checked'], reviewed)
        if row['date'] in dates or row['unit'] != 'metric tonnes':
            raise ValueError('Duplicate date or wrong stock unit')
        dates.add(row['date'])
        for key in ('total', 'live', 'cancelled'):
            check_number(row[key], True)
        if row['total'] <= 0 or abs(row['live'] + row['cancelled'] - row['total']) > .001:
            raise ValueError('LME components do not reconcile')
        check_number(row['reported_cancelled_share'], True)
        check_number(row['reported_previous_share'], True)
        if abs(100 * row['cancelled'] / row['total'] - row['reported_cancelled_share']) > .011:
            raise ValueError('Reported share does not reconcile')
        if row['reported_previous_share'] > 100 or not row['source_url'].startswith('https://'):
            raise ValueError('Invalid share or source')
    if not records:
        raise ValueError('No reviewed LME snapshots')
    names = {'live': '등록 (Live · 선물 인도 가능)', 'cancelled': '취소 (Cancelled · 인도 대상 제외)', 'total': '총재고 (등록 + 취소)'}
    tonnes = {label: [[r['date'], r[key]] for r in records] for key, label in names.items()}
    share = {'취소 비중': [[r['date'], round(100 * r['cancelled'] / r['total'], 4)] for r in records]}
    latest = records[-1]
    difference = latest['reported_cancelled_share'] - latest['reported_previous_share']
    return dict(
        id='comm_copper_lme_warrant_composition', name='LME 구리 · 등록·취소 워런트 구성',
        unit='톤', frequency='irregular', frequency_label='공개표 검토', manual=True,
        reviewed=reviewed, fetched=reviewed, updated=latest['date'], data_stale_days=14,
        source='CNAL · 有色宝 공개 LME 구성표 (수기 검토)', source_url=latest['source_url'],
        source_original='LME warehouse stocks · CNAL 재공표', source_records=records,
        series=tonnes, default_series=list(tonnes), highlight_gaps=True, change_mode='none',
        series_views={
            'tonnes': dict(label='등록·취소 물량', unit='톤', series=tonnes, default_series=list(tonnes)),
            'share': dict(label='취소 비중', unit='%', series=share, default_series=list(share)),
        }, default_view='tonnes',
        basis_details=[dict(label='공식 취득 경로', value='LME Stock breakdown: 2일 지연 XLS. 총재고·등록·취소·입고·출고를 금속·지역별로 제공하며 계정 로그인이 필요합니다.'),
            dict(label='현재 수록값', value='CNAL의 2026-10-02 구리 행: 총재고 248,650톤 = 등록 134,650톤 + 취소 114,000톤. 취소 비중은 원문 45.85%, 계산 정밀값은 114,000 ÷ 248,650 × 100입니다.'),
            dict(label='범위', value='검토된 한 시점입니다. 표의 원문 전일 비중 47.01%는 그 날짜의 총재고·취소톤 이력으로 역산하지 않습니다. 실제 입출고량은 아직 미확보입니다.')],
        methodology_url='https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/stock-breakdown-report',
        description='등록은 LME 선물 인도에 사용할 수 있는 창고증권 물량, 취소는 창고증권을 취소해 인도 대상에서 빠진 물량입니다. 취소 물량도 실제 출고 전에는 창고에 남고 총재고에 포함됩니다. 등록이 곧 즉시 매수 가능하거나 취소가 곧 소비됐다는 뜻은 아닙니다.',
        note=f"현재 {len(records)}개 공개표만 확인했습니다. 일간 전체 이력·실시간 자료가 아니며 자동 수집되지 않습니다. CNAL 원문 {latest['date']} 취소 비중 {latest['reported_cancelled_share']:.2f}%, 원문 전일 {latest['reported_previous_share']:.2f}% 대비 {difference:+.2f}%p. 첨부 보고서·기존 LME 총재고 카드와 제공처 또는 기준 시점이 달라 수치가 다를 수 있습니다. 총재고 합산에는 기존 총재고만 사용하며 이 카드를 더하지 않습니다."
    )


def premium_document(warrant, bill):
    if warrant['unit'] != 'USD/톤' or bill['unit'] != 'USD/톤':
        raise ValueError('Premium unit mismatch')
    def index(doc, contract):
        result = {}
        for row in doc['source_records']:
            check_date(row['date'], doc['fetched'])
            if row['provider'] != 'Mysteel' or row['contract'] != contract or not validate(row):
                raise ValueError('Wrong provider, contract or invalid premium')
            key = row['date'], row['grade']
            if key in result:
                raise ValueError('Duplicate premium')
            result[key] = row
        return result
    a, b = index(warrant, 'warehouse_warrant'), index(bill, 'bill_of_lading')
    rows = []
    for key in sorted(a.keys() & b.keys()):
        w, bl = a[key], b[key]
        rows.append(dict(date=key[0], grade=key[1], provider='Mysteel',
            value=round(w['midpoint']-bl['midpoint'], 4), unit='USD/metric tonne',
            warehouse_warrant=w['midpoint'], bill_of_lading=bl['midpoint'],
            warehouse_terms=w.get('delivery_pricing_terms'), bill_of_lading_terms=bl.get('delivery_pricing_terms'),
            sources=[w['source_url'], bl['source_url']]))
    if not rows:
        raise ValueError('No same-day, same-grade premium pairs')
    series = {label: [[r['date'], r['value']] for r in rows if r['grade'] == grade]
        for grade, label in {'pyrometallurgical': '화법동 · 보세창고 − B/L', 'hydrometallurgical': '습법동 · 보세창고 − B/L'}.items()}
    return dict(id='comm_copper_yangshan_delivery_gap', name='양산 프리미엄 · 보세창고 − 선하증권 차이',
        unit='USD/톤', frequency='daily', fetched=min(warrant['fetched'], bill['fetched']),
        updated=max(r['date'] for r in rows), data_stale_days=14,
        source='Mysteel 공개표 · 같은 날짜·제조 경로의 중간값 차이 (계산)', source_url=warrant['source_url'],
        series=series, default_series=list(series), reference_value=0, reference_label='차이 0',
        highlight_gaps=True, change_mode='none', source_records=rows,
        description='같은 제공처·날짜·제조 경로에서 보세창고증권 프리미엄 − 선하증권(B/L) 프리미엄을 계산합니다. 양수는 도착한 보세창고 물량이 B/L 거래 물량보다 비싸다는 뜻입니다. 음수도 실제 관측값이면 표시합니다.',
        note='즉시 확보할 수 있는 물량의 상대 가격을 보는 보조 지표입니다. B/L은 해상 운송 중·도착 예정 또는 아직 선하증권으로 거래되는 물량이며, 모든 B/L이 운송 중인 것은 아닙니다. QP(기준가격 산정기간), ETA(도착 예정일), 브랜드·금융·보관·통관 조건이 달라질 수 있어 차이를 순수한 품귀 프리미엄이나 확정 차익으로 해석하지 않습니다. 날짜가 없는 한쪽 값은 이월하지 않으며 SMM 값과 혼합하지 않습니다.')


def save(doc):
    path = OUT / (doc['id'] + '.json')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def main():
    source = json.loads((ROOT / 'manual/copper_market_sources.json').read_text(encoding='utf-8'))
    warrants = json.loads((OUT / 'comm_copper_yangshan_warehouse_warrant.json').read_text(encoding='utf-8'))
    bill = json.loads((OUT / 'comm_copper_yangshan_bill_of_lading.json').read_text(encoding='utf-8'))
    docs = [lme_document(source), premium_document(warrants, bill)]
    for doc in docs:
        save(doc)
        print(doc['id'], doc['updated'], {name:len(rows) for name,rows in doc['series'].items()})


if __name__ == '__main__':
    main()

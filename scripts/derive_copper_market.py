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
        if row.get('reported_previous_share') is not None:
            check_number(row['reported_previous_share'], True)
        tolerance = .5 * 10**(-row.get('share_precision', 2)) + .001
        if abs(100 * row['cancelled'] / row['total'] - row['reported_cancelled_share']) > tolerance:
            raise ValueError('Reported share does not reconcile')
        if row.get('reported_previous_share', 0) > 100 or not row['source_url'].startswith('https://'):
            raise ValueError('Invalid share or source')
    if not records:
        raise ValueError('No reviewed LME snapshots')
    names = {'live': '등록 (Live · 선물 인도 가능)', 'cancelled': '취소 (Cancelled · 인도 대상 제외)', 'total': '총재고 (등록 + 취소)'}
    tonnes = {label: [[r['date'], r[key]] for r in records] for key, label in names.items()}
    share = {'취소 비중': [[r['date'], round(100 * r['cancelled'] / r['total'], 4)] for r in records]}
    latest = records[-1]
    archive = all(r.get('provider', '').startswith('Minmetals') for r in records)
    doc = dict(
        id='comm_copper_lme_warrant_composition', name='LME 구리 · 등록·취소 워런트 구성',
        unit='톤', frequency='daily' if archive else 'irregular', manual=not archive,
        reviewed=reviewed, fetched=reviewed, updated=latest['date'], data_stale_days=14,
        source='Minmetals Financial Services 공개 일별 LME 보고서' if archive else 'CNAL · 有色宝 공개 LME 구성표 (수기 검토)', source_url=latest['source_url'],
        source_original='LME warehouse stocks · Minmetals 재공표' if archive else 'LME warehouse stocks · CNAL 재공표', source_records=records,
        series=tonnes, default_series=list(tonnes), highlight_gaps=True, daily_axis=True, change_mode='none',
        series_views={
            'tonnes': dict(label='등록·취소 물량', unit='톤', series=tonnes, default_series=list(tonnes)),
            'share': dict(label='취소 비중', unit='%', series=share, default_series=list(share)),
        }, default_view='tonnes',
        basis_details=[dict(label='공식 취득 경로', value='LME Stock breakdown: 2일 지연 XLS. 총재고·등록·취소·입고·출고를 금속·지역별로 제공하며 계정 로그인이 필요합니다.'),
            dict(label='현재 수록값', value=f"{latest['date']} 총재고 {latest['total']:,}톤 = 등록 {latest['live']:,}톤 + 취소 {latest['cancelled']:,}톤. 취소 비중은 같은 표의 취소 ÷ 총재고 × 100으로 계산합니다."),
            dict(label='범위', value=f"{records[0]['date']}~{latest['date']} 검증된 {len(records):,}개 기준일. 보고서 기준일을 사용하며 파일 게시일과 구분합니다. 누락 날짜를 생성하거나 전일 값으로 채우지 않습니다.")],
        methodology_url='https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/stock-breakdown-report',
        description='등록은 LME 선물 인도에 사용할 수 있는 창고증권 물량, 취소는 창고증권을 취소해 인도 대상에서 빠진 물량입니다. 취소 물량도 실제 출고 전에는 창고에 남고 총재고에 포함됩니다. 등록이 곧 즉시 매수 가능하거나 취소가 곧 소비됐다는 뜻은 아닙니다.',
        history_started=records[0]['date'], snapshot_history=True,
        table_limit=len(records), table_scroll=True,
        point_sources={r['date']:dict(url=r['source_url'],label='일별 원문 PDF' if archive else '구성표 원문') for r in records},
        history_note=f"{records[0]['date']}~{latest['date']} 원문 검증 {len(records):,}개 기준일. 전체 LME 공식 유료 이력과 동일한 범위는 아닙니다.",
        note=f"{records[0]['date']}~{latest['date']} 공개표 {len(records):,}개 기준일. " + ('공개 일별 보고서를 매일 확인하고 새 관측값을 누적합니다. 초기 스캔 PDF는 OCR 후 총재고=등록+취소를 검증했습니다. 입출고는 전일재고+입고−출고=총재고가 맞는 행만 표시합니다. ' if archive else '검토된 한 시점이며 자동 수집되지 않습니다. ') + '취소 비중은 반올림된 원문 비율을 연결하지 않고 같은 날짜의 원문 물량에서 직접 계산합니다. 빠진 날짜는 보간하지 않으며 7일 초과 공백은 점선입니다. 첨부 보고서·기존 LME 총재고 카드와 제공처 또는 기준 시점이 달라 수치가 다를 수 있습니다. 합산 재고에는 기존 총재고만 사용하며 이 카드를 더하지 않습니다.'
    )
    if not archive:
        doc['frequency_label'] = '공개표 검토'
    if archive:
        flows = {label:[[r['date'],r[key]] for r in records if r.get('flows_valid', True)] for key,label in {'delivered_in':'실제 입고','delivered_out':'실제 출고'}.items()}
        doc['series_views']['flows'] = dict(label='실제 입고·출고',unit='톤/일',series=flows,default_series=list(flows))
        doc['collection_provider'] = 'mjfins_archive'
    return doc


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
    lme_path = OUT / 'comm_copper_lme_warrant_composition.json'
    previous = json.loads(lme_path.read_text(encoding='utf-8')) if lme_path.exists() else {}
    # Automated daily/archive values take precedence over the original one-point seed.
    lme = previous if previous.get('collection_provider') == 'mjfins_archive' else lme_document(source)
    docs = [lme, premium_document(warrants, bill)]
    for doc in docs:
        save(doc)
        print(doc['id'], doc['updated'], {name:len(rows) for name,rows in doc['series'].items()})


if __name__ == '__main__':
    main()

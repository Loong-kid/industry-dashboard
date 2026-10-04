"""Wednesday H.4.1 securities, loans and reserve-account reconciliation.

All inputs are published Wednesday levels in millions of USD. Formula inputs
never use daily DTS/ON RRP or weekly averages. Public FRED graph downloads are
batched below its graph series limit and validated before replacing any card.
"""
import csv
import io
import json
import math
import re
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from fetch_liquidity import get

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'macro'
CACHE = ROOT / 'data' / '_liquidity' / 'fed_h41.json'
URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv'
H41 = 'https://www.federalreserve.gov/releases/h41/current/'
TABLE = 'https://fred.stlouisfed.org/release/tables?eid=1193943&rid=20'
BTFP = 'H41RESPPALDKNWW'
IDS = ['WSHOSHO', 'WSHOTSL', 'WSHOFADSL', 'WSHOMCB', 'WLCFLL',
       'WLCFLPCL', 'WLCFLSCL', 'WLCFLSECL', 'H41RESPPALDJNWW', BTFP,
       'WLCFOCEL', 'WRBWFRBL', 'WDTGAL', 'WLRRAL', 'WLRRAFOIAL',
       'WLRRAOL', 'WTFSRFL', 'WTFORBAFL', 'WCICL']
CORE = ['WSHOSHO', 'WLCFLL', 'WRBWFRBL', 'WDTGAL', 'WLRRAL',
        'WTFSRFL', 'WTFORBAFL', 'WCICL']


def parse_download(content, expected, today):
    # Different FRED frequency codes may yield a zip despite all titles being
    # Wednesday Level. In particular BTFP is classified as ending Wednesday.
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        if 'README.txt' not in names or sum(i.file_size for i in archive.infolist()) > 10_000_000:
            raise ValueError('Unexpected FRED package')
        readme = archive.read('README.txt').decode('utf-8-sig')
        blocks = re.split(r'^([A-Z0-9]+)\s{2,}', readme, flags=re.M)
        metadata = dict(zip(blocks[1::2], blocks[2::2]))
        for sid in expected:
            text = ' '.join(re.sub(r'Data Updated:[^\n]*', '', metadata.get(sid, '')).split())
            if 'Millions of U.S. Dollars' not in text or 'Wednesday Level' not in text:
                raise ValueError(f'{sid}: unit or Wednesday-level metadata missing')
        data = {sid: {} for sid in expected}
        found = set()
        for name in names:
            if not name.endswith('.csv'):
                continue
            reader = csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'), newline=''))
            fields = reader.fieldnames or []
            if not fields or fields[0] != 'observation_date':
                raise ValueError('Unexpected FRED columns')
            if len(set(fields)) != len(fields) or found.intersection(fields[1:]) or set(fields[1:]) - set(expected):
                raise ValueError('Duplicate or unexpected FRED series')
            found.update(fields[1:])
            for row in reader:
                day = row['observation_date']
                observed = date.fromisoformat(day)
                if observed > today or observed.weekday() != 2:
                    raise ValueError('Future or non-Wednesday observation')
                for sid in fields[1:]:
                    raw = (row.get(sid) or '').strip()
                    if raw in ('', '.'):
                        continue
                    value = float(raw)
                    if not math.isfinite(value) or value < 0:
                        raise ValueError('Invalid published balance')
                    if day in data[sid] and data[sid][day] != value:
                        raise ValueError('Conflicting date values')
                    data[sid][day] = value
        if found != set(expected) or any(not points for points in data.values()):
            raise ValueError('Incomplete FRED package')
    return data


def fetch_all(session, today):
    data = {}
    # FRED silently truncates overly large graph requests. At most ten series
    # per request, with discontinued BTFP included to obtain metadata-rich zip.
    for group in [IDS[:10], IDS[10:] + [BTFP]]:
        response = get(session, URL, {'id': ','.join(group), 'cosd': '2002-12-18', 'coed': today.isoformat()})
        batch = parse_download(response.content, group, today)
        for sid, points in batch.items():
            if sid in data and data[sid] != points:
                raise ValueError('FRED vintages changed during download')
            data[sid] = points
    return data


def derive(data):
    if len({max(data[sid]) for sid in CORE}) != 1:
        raise ValueError('Core inputs have different latest Wednesdays')
    days = sorted(set.intersection(*(set(data[sid]) for sid in CORE)))
    calculated = {name: {} for name in ['simple', 'reconstructed', 'other_supply', 'other_drain', 'gap']}
    for day in days:
        s, loan, actual, tga, rrp, supply, drain, currency = [data[sid][day] for sid in CORE]
        simple = s + loan - tga - rrp
        other_supply = supply - s - loan
        other_drain = drain - tga - rrp - currency
        reconstructed = simple + other_supply - currency - other_drain
        # Independent totals reconcile; actual reserves are never an input to
        # the estimate or to either omitted-factor correction.
        if abs(reconstructed - actual) > 5:
            raise ValueError(f'H.4.1 identity differs by more than USD 5 million on {day}')
        values = [simple, reconstructed, other_supply, other_drain, simple - actual]
        for key, value in zip(calculated, values):
            calculated[key][day] = value
    return days, calculated


def billions(points):
    return [[day, round(value / 1000, 3)] for day, value in sorted(points.items())]


def card(cid, name, series, defaults, today, description, note, details, inputs):
    histories = {label: billions(points) for label, points in series.items()}
    return dict(id=cid, name=name, unit='십억 달러', frequency='weekly',
                series=histories, default_series=defaults,
                updated=max(points[-1][0] for points in histories.values()), fetched=today.isoformat(),
                compact_ticks=True, span_gaps=False, table_limit=10000, data_stale_days=15,
                source='연준 H.4.1 · FRED', source_url=TABLE, methodology_url=H41,
                description=description, note=note,
                basis_details=[{'label': '관측 / 단위', 'value': '주간 평균이 아닌 수요일 잔고입니다. 원단위 백만 달러를 1,000으로 나눠 십억 달러로 표시합니다. 같은 날짜에 실제 공표된 값만 계산하고 일간 자료를 섞거나 빈 값을 보간하지 않습니다.'},
                               *details, {'label': '원시 시리즈', 'value': ', '.join(inputs)}],
                source_series={sid: 'https://fred.stlouisfed.org/series/' + sid for sid in inputs})


def build_docs(data, today):
    days, calc = derive(data)
    if len(days) < 500:
        raise ValueError('Insufficient common weekly history')
    for day in days:
        if all(day in data[s] for s in ['WSHOTSL', 'WSHOFADSL', 'WSHOMCB']):
            total = sum(data[s][day] for s in ['WSHOTSL', 'WSHOFADSL', 'WSHOMCB'])
            if abs(total - data['WSHOSHO'][day]) > 5:
                raise ValueError('Domestic securities components do not reconcile')
    common = lambda sid: {d: data[sid][d] for d in days}
    actual, reconstructed, simple = '공식 지급준비금', '회계 재구성', '단순식 추정'
    docs = [card('fed_reserves_estimate', '지급준비금 / 추정과 실제',
                 {actual: common('WRBWFRBL'), reconstructed: calc['reconstructed'], simple: calc['simple']},
                 [actual, reconstructed, simple], today,
                 '단순식 = 국내 보유증권 + 연준 전체 대출 − 전체 역레포 − TGA. 회계 재구성은 여기에 빠진 공급·흡수 요인을 보정한 값입니다. 공식 지급준비금과 비교할 수 있습니다.',
                 '단순식에는 현금통화와 기타 자산·부채가 빠져 있어 실제 지준과 차이가 납니다. 점선은 계산값이며 미래 전망이 아닙니다. 지급준비금은 은행이 연준에 보유한 잔고로 시중 통화량 전체와 다릅니다.',
                 [{'label': '보정식', 'value': '단순식 + 기타 공급요인 − 유통 현금통화 − 기타 흡수요인. 기타 공급 = 총 공급 − 보유증권 − 대출. 기타 흡수 = 지준 외 총 흡수 − 전체 역레포 − TGA − 현금통화.'},
                  {'label': '독립 검증', 'value': '회계 재구성 = H.4.1 총 지준 공급요인 − 지준 외 총 흡수요인. 계산에 공식 지준을 넣지 않고 별도 공표된 지준과 검증합니다. 같은 주의 회계 항등식 재구성이며 선행 예측모형은 아닙니다.'},
                  {'label': '최신 비교', 'value': f'{days[-1]} 단순식 {calc["simple"][days[-1]]/1000:,.3f}, 공식 지준 {data["WRBWFRBL"][days[-1]]/1000:,.3f}, 차이 {calc["gap"][days[-1]]/1000:,.3f} 십억 달러.'}], CORE),
            card('fed_reserves_adjustments', '지준 계산의 보정 항목',
                 {'유통 현금통화(차감)': common('WCICL'), '기타 공급요인(가산)': calc['other_supply'], '기타 흡수요인(차감)': calc['other_drain']},
                 ['유통 현금통화(차감)', '기타 공급요인(가산)', '기타 흡수요인(차감)'], today,
                 '단순식과 실제 지준이 다른 이유를 보여줍니다. 현금통화를 차감하고, 기타 공급요인은 더하고, 기타 흡수요인은 뺍니다.',
                 '기타 요인은 순액이므로 음수도 가능합니다. 실측 지준에서 역산한 오차 보정이 아닙니다.',
                 [{'label': '포함 항목', 'value': '기타 공급에는 증권 미상각 프리미엄·할인, Repo, 유동성 스왑, 기타 자산 등이 포함됩니다. 기타 흡수에는 지준·TGA 이외 예금, 기타 부채·자본, 재무부 현금보유 등이 포함됩니다.'}], CORE),
            card('fed_soma', 'SOMA 국내 보유증권 / H.4.1',
                 {'국내 보유증권 합계': data['WSHOSHO'], '미 국채': data['WSHOTSL'], '기관채': data['WSHOFADSL'], '기관 MBS': data['WSHOMCB']},
                 ['국내 보유증권 합계', '미 국채', '기관 MBS'], today,
                 'SOMA 국내 증권 포트폴리오를 연준 H.4.1의 직접 보유증권 기준으로 봅니다. 미 국채, 연방 기관채, 기관 MBS로 구성됩니다.',
                 '해외통화 자산을 포함한 SOMA 전체 자산이나 연준 총자산과 구분됩니다. 계산은 H.4.1의 동일한 잔고 기준을 사용합니다.',
                 [{'label': '평가 기준', 'value': '국채·기관채는 액면 기준(국채 TIPS 물가보상 포함), MBS는 잔존 원금 기준입니다. 미상각 프리미엄·할인은 보유증권 합계와 별도이므로 회계 재구성의 기타 공급요인에 들어갑니다.'}], IDS[:4])]
    discount_days = sorted(set.intersection(*(set(data[s]) for s in IDS[5:8])))
    discount = {d: sum(data[s][d] for s in IDS[5:8]) for d in discount_days}
    docs.append(card('fed_facilities', '연준 유동성 지원 창구 / 대출 잔액',
                     {'연준 전체 대출': data['WLCFLL'], '재할인창구 합계': discount,
                      'Primary credit': data['WLCFLPCL'], 'Secondary credit': data['WLCFLSCL'], 'Seasonal credit': data['WLCFLSECL'],
                      'PPPLF': data['H41RESPPALDJNWW'], 'BTFP(종료)': data[BTFP], '기타 신용공여': data['WLCFOCEL']},
                     ['연준 전체 대출', '재할인창구 합계', 'PPPLF', 'BTFP(종료)'], today,
                     '한도나 신규 대출액이 아닌 창구별 대출 잔액입니다. 재할인창구 합계는 Primary·Secondary·Seasonal credit의 합계입니다.',
                     '전체 대출에는 세부 창구가 이미 포함되어 있으므로 지준 계산에 다시 더하지 않습니다. BTFP 종료 이후의 미공표 기간은 0으로 연장하지 않습니다.',
                     [{'label': 'BTFP 마지막 공표', 'value': f'{max(data[BTFP])}, {data[BTFP][max(data[BTFP])]/1000:,.3f} 십억 달러. 이후는 시계열 종료로 표시됩니다.'},
                      {'label': '범위', 'value': '전체 대출(WLCFLL)을 지준 식에 한 번만 사용합니다. Repo·스왑·특수목적기구의 순자산 등은 이 대출 합계와 다른 항목이며 기타 공급요인에서 보정합니다.'}], IDS[4:11]))
    docs.append(card('fed_reserves', '은행의 실제 지급준비금', {'공식 지급준비금': data['WRBWFRBL']}, ['공식 지급준비금'], today,
                     '예금취급기관이 연준에 보유한 reserve balances의 실제 공표 잔고입니다.',
                     '법정 지급준비율이나 은행 보유 현금까지 포함한 모든 준비자산, M2 통화량과 구분됩니다. 주간 평균 WRESBAL이 아니라 수요일 잔고 WRBWFRBL입니다.', [], ['WRBWFRBL']))
    docs.append(card('fed_tga_rrp', '지준 계산용 TGA / 전체 역레포',
                     {'TGA(수요일)': data['WDTGAL'], '전체 역레포': data['WLRRAL'], '국내 등 역레포(Others)': data['WLRRAOL'], '외국 공적기관 역레포': data['WLRRAFOIAL']},
                     ['TGA(수요일)', '전체 역레포', '국내 등 역레포(Others)'], today,
                     '대차대조표 계산에 사용하는 동일 수요일의 TGA와 전체 역레포 잔고입니다. 전체 역레포에는 외국 공적기관·국제기구 계정도 포함됩니다.',
                     '아래의 일간 TGA 마감 잔고·ON RRP 거래액과 빈도 및 범위가 다릅니다. ON RRP만 차감하면 다른 역레포 부채가 빠집니다.', [], ['WDTGAL', 'WLRRAL', 'WLRRAOL', 'WLRRAFOIAL']))
    docs[0]['series_dashes'] = {reconstructed: [6, 4], simple: [2, 3]}
    return docs


def publish(data, docs, today):
    # Validate the complete cohort before any write. No backwards latest date,
    # deleted history, or loss of discontinued facility history is accepted.
    files = {OUT / (doc['id'] + '.json'): doc for doc in docs}
    files[CACHE] = dict(updated=max(data['WRBWFRBL']), fetched=today.isoformat(), unit='million USD',
                        source_url=TABLE, series={sid: sorted(points.items()) for sid, points in data.items()})
    for path, doc in files.items():
        if path.exists():
            old = json.loads(path.read_text(encoding='utf-8'))
            if doc['updated'] < old['updated']:
                raise ValueError('Latest date regressed')
            for label, points in old['series'].items():
                if not {p[0] for p in points} <= {p[0] for p in doc['series'].get(label, [])}:
                    raise ValueError('Published history regressed')
    for path, doc in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.json.tmp')
        temp.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        temp.replace(path)


def run():
    today = datetime.now(timezone(timedelta(hours=9))).date()
    try:
        with requests.Session() as session:
            data = fetch_all(session, today)
        docs = build_docs(data, today)
        publish(data, docs, today)
        for doc in docs:
            print(f'{doc["id"]}: {len(doc["series"])} series; latest {doc["updated"]}')
        return 0
    except Exception as error:
        print(f'ERROR Fed H.4.1 collection; preserving published cards: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(run())

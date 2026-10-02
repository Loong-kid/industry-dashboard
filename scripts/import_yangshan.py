"""Publish validated, already-collected Yangshan data; no network or scheduler."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'data/commodities'
GRADES = {'pyrometallurgical': '화법동', 'hydrometallurgical': '습법동'}
CONTRACTS = {'warehouse_warrant': '창고증권', 'bill_of_lading': '선하증권'}
PROCESS_EXPLANATION = ('화법동은 고온 제련 후 전해정련으로 정제한 구리, 습법동은 광석에서 구리를 용액으로 녹여 추출한 뒤 전기로 회수한 구리(SX-EW)입니다. '
    '둘 다 고순도 전기동으로 생산될 수 있으므로 습법동을 저순도 구리로 보면 안 됩니다. 이 그래프는 제조 경로별 시장 구분이며, 두 선의 프리미엄 차이를 순도 차이로 해석하지 않습니다.')


def validate(row):
    dt.date.fromisoformat(row['date'])
    if row['unit'] != 'USD/metric tonne':
        raise ValueError('Unexpected unit')
    lo, hi, mid = (row[k] for k in ('low', 'high', 'midpoint'))
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (lo, hi, mid)):
        raise ValueError('Invalid premium')
    return lo <= mid <= hi and abs((lo + hi) / 2 - mid) < .001


def run(folder):
    records = []
    for path in sorted((folder / 'observations').glob('*.json')):
        records.extend(json.loads(path.read_text(encoding='utf-8'))['rows'])
    records.extend(json.loads((folder / 'previously_retrieved_tables.json').read_text(encoding='utf-8'))['observations'])
    unique = {}
    for row in records:
        key = (row['date'], row['contract'], row['grade'])
        if key in unique and any(unique[key][k] != row[k] for k in ('low', 'high', 'midpoint')):
            raise ValueError(f'Conflicting source records: {key}')
        unique[key] = row
    accepted, flagged = [], []
    for key in sorted(unique):
        row = unique[key]
        (accepted if validate(row) else flagged).append(row)
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    docs = []
    for contract, title in CONTRACTS.items():
        rows = [r for r in accepted if r['contract'] == contract]
        series = {name: [[r['date'], r['midpoint']] for r in rows if r['grade'] == grade] for grade, name in GRADES.items()}
        if not all(series.values()):
            raise ValueError('Missing Mysteel series')
        dates = sorted({r['date'] for r in rows})
        gaps = []
        for name, points in series.items():
            for (a, _), (b, _) in zip(points, points[1:]):
                if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days > 7:
                    gaps.append({'series': name, 'from': a, 'to': b})
        docs.append(dict(id=f'comm_copper_yangshan_{contract}', name=f'양산 프리미엄 · {title} (Mysteel)',
            unit='USD/톤', frequency='daily', fetched=today, updated=dates[-1], data_stale_days=14,
            source='Mysteel 공개 일일 가격표', source_url='https://list1.mysteel.com/article/p-2409----0201---------1.html',
            series=series, default_series=list(series), highlight_gaps=True, gaps=gaps,
            snapshot_history=True, history_note=f'{dates[0]}부터 확인된 Mysteel 과거 관측값을 포함합니다.',
            source_records=rows, excluded_observations=len([r for r in flagged if r['contract']==contract]),
            description=f'상하이 양산 구리 {title} 프리미엄의 공시 중간값입니다. ' + PROCESS_EXPLANATION,
            note=f'{dates[0]}~{dates[-1]} 공개 관측값. 누락 구간도 선으로 연결하지만 값을 보간·생성하지 않습니다. 7일 초과 관측 간격은 점선으로 표시하며 휴일도 포함될 수 있습니다. 원문 가격 범위와 중간값이 불일치한 자료는 제외했습니다. ETA·QP 조건은 원문에 따라 바뀝니다. 일회 수집 자료이며 자동 갱신은 아직 설정하지 않았습니다.'))
    smm = json.loads((folder / 'smm_yangshan_snapshot.json').read_text(encoding='utf-8'))
    series = {CONTRACTS[r['contract']]: [[r['date'], r['midpoint']]] for r in smm['observations'] if validate(r)}
    if len(series) != 2:
        raise ValueError('Incomplete SMM snapshot')
    docs.append(dict(id='comm_copper_yangshan_smm', name='양산 프리미엄 · SMM 최신값 누적', unit='USD/톤',
        frequency='daily', fetched=smm['retrieved_at'], updated=max(r['date'] for r in smm['observations']),
        data_stale_days=14, source='SMM 공개 가격 목록', source_url='https://www.smm.com.cn/price',
        series=series, default_series=list(series), source_records=smm['observations'],
        snapshot_history=True, history_note='수집 시작 전 SMM 과거 이력은 확보하지 못했습니다.',
        description='SMM 창고증권·선하증권 평균값을 수집한 날짜부터 누적합니다. 과거 이력은 미확보이며, Mysteel 과거 그래프와는 별도 자료입니다.',
        note='현재 확보한 기준일 1개의 참고값입니다. 과거 이력과 자동 갱신은 아직 연결하지 않았습니다.'))
    for doc in docs:
        path = OUT / (doc['id'] + '.json')
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(doc['id'], {name: len(rows) for name, rows in doc['series'].items()})
    summary = dict(dates=len({r['date'] for r in unique.values()}), collected=len(unique), accepted=len(accepted), excluded=len(flagged))
    (folder / 'deployment_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_folder', type=Path)
    run(parser.parse_args().input_folder)

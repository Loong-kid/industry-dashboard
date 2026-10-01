"""Weekly SHFE-anchored exchange inventory sum, with bounded backward matching."""
import datetime as dt
import json
import math
from bisect import bisect_right

from fetch_copper_snapshot import OUT, TOTAL, LME

NAME = '3대 거래소 구리 합산 재고'
MAX_LAG_DAYS = 4


def validated(doc, name):
    if doc['unit'] != '톤':
        raise ValueError('All inputs must be metric tonnes')
    rows = doc['series'][name]
    dates = []
    for date, value in rows:
        if dt.date.fromisoformat(date).isoformat() != date:
            raise ValueError('Invalid date')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid inventory')
        dates.append(date)
    if not dates or dates != sorted(set(dates)):
        raise ValueError('Empty/unsorted/duplicate inventory dates')
    return rows, dates


def build(shfe, comex, lme):
    sh, _ = validated(shfe, 'SHFE 구리 주간 재고')
    co, co_dates = validated(comex, TOTAL)
    lm, lm_dates = validated(lme, LME)
    series = {NAME: [], 'SHFE': [], 'COMEX': [], 'LME': []}
    source_dates = {}
    skipped = []
    for date, sh_value in sh:
        anchor = dt.date.fromisoformat(date)
        matches = []
        for rows, dates in ((co, co_dates), (lm, lm_dates)):
            index = bisect_right(dates, date) - 1
            if index < 0 or (anchor - dt.date.fromisoformat(dates[index])).days > MAX_LAG_DAYS:
                break
            matches.append(rows[index])
        if len(matches) != 2:
            skipped.append(date)
            continue
        (co_date, co_value), (lm_date, lm_value) = matches
        for name, value in zip(series, (round(sh_value + co_value + lm_value, 3), sh_value, co_value, lm_value)):
            series[name].append([date, value])
        source_dates[date] = {'SHFE': date, 'COMEX': co_date, 'LME': lm_date}
    if not series[NAME]:
        raise ValueError('No sufficiently aligned observations')
    latest = series[NAME][-1][0]
    stamps = source_dates[latest]
    return dict(id='comm_copper_total_inventory', name=NAME, unit='톤', frequency='weekly',
                updated=latest, fetched=min(d['fetched'] for d in (shfe, comex, lme)), data_stale_days=14,
                source='SHFE · COMEX · LME 재고 합산', series=series, default_series=[NAME],
                source_dates=source_dates, omitted_anchor_dates=skipped,
                description='SHFE 주간 총재고 + COMEX 총재고(등록·적격) + LME 보고 재고. 글로벌 거래소 재고 동향을 보는 지표입니다.',
                note='글로벌 전체 재고가 아닙니다. 비거래소·생산자·소비자·운송 중 재고 등을 포괄하지 않으며, 별도 LME off-warrant 재고도 미포함입니다. SHFE 창고증권은 총재고에 포함되므로 중복 합산하지 않습니다. '
                     'SHFE 보고일을 기준으로 각 거래소의 당일 또는 직전 4일 이내 자료를 사용합니다. 미래 자료는 사용하지 않고, 자료가 오래되거나 없으면 그 주는 제외합니다. '
                     f"최신 구성 기준일: SHFE {stamps['SHFE']} / COMEX {stamps['COMEX']} / LME {stamps['LME']}.")


def run():
    docs = [json.loads((OUT / f'comm_copper_{exchange}_inventory.json').read_text(encoding='utf-8'))
            for exchange in ('shfe', 'comex', 'lme')]
    doc = build(*docs)
    path = OUT / (doc['id'] + '.json')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)
    print(f"{doc['id']}: {len(doc['series'][NAME])} observations, latest {doc['updated']}")


if __name__ == '__main__':
    run()

"""Free daily NYSE SCCO / FCX / ERO prices and reported PER/PBR bands."""
import argparse
import calendar

from fetch_semicon_valuation import ROOT, collect
from semicon_valuation_sources import finite, yahoo_fundamentals

REGISTRY = ROOT / 'manual/copper-valuation/companies.json'
OUT = ROOT / 'data/commodities/valuation'
CACHE = ROOT / '.cache/copper-valuation'
METHODOLOGY = (
    'NYSE 보통주·USD 기준. 분할 반영 종가이며 배당 재투자는 미반영합니다. '
    'PER=종가/실적 TTM 희석 EPS, PBR=종가/보통주 귀속 자본 기준 기말 BPS입니다. '
    'EPS·BPS가 0 이하이면 N/M이며 적자 구간의 PER 밴드는 끊습니다. '
    'SCCO는 주식배당으로 과거 TTM 제공값의 주식수가 서로 달라, 해당 TTM을 제외하고 '
    '공급자가 같은 현재 주식수 기준으로 재작성한 완결 연간 EPS 또는 실제 연속 4분기 희석 EPS 합계만 사용합니다. '
    'SCCO의 초기 이력은 연말 EPS만 확보되어 다음 실적까지 유지됩니다. '
    '2022년 이후 양의 유효 배수 중앙값의 0.5·0.75·1·1.25·1.5배를 참고 주가선으로 표시합니다. '
    '실적 이력은 원자료 확보 기간부터이며 전망치나 누락 분기 추정치는 사용하지 않습니다. '
    '재작성된 결산기간 기준으로 공시일 당시의 투자 가능 정보를 재현하는 백테스트가 아닙니다. '
    'ERO는 NYSE 거래 개시일인 2021-06-15부터 표시합니다.'
)


def copper_fundamentals(payload, symbol, asof, splits=(), review=None):
    fund = yahoo_fundamentals(payload, symbol, asof, splits, review)
    if symbol != 'SCCO':
        return fund
    # SCCO pays frequent stock dividends. Supplier trailing EPS has mixed
    # historical share bases (e.g. FY2025 trailing != adjusted annual EPS).
    # Never exempt all pre-split TTM values from the shared safety check.
    eps = {r[0]: r for r in fund['eps'] if r[3].startswith('annualDilutedEPS')}
    quarters = {}
    for series in payload['timeseries'].get('result') or []:
        if series['meta']['type'][0] != 'quarterlyDilutedEPS':
            continue
        for row in series.get('quarterlyDilutedEPS', []):
            date = row['asOfDate']; value = row.get('reportedValue', {}).get('raw')
            if (row.get('periodType') == '3M' and '2022-01-01' <= date <= asof
                    and finite(value) and row.get('currencyCode') == 'USD'):
                quarters[date] = float(value)
    for date in sorted(quarters):
        year, month = int(date[:4]), int(date[5:7])
        periods = []
        for lag in range(4):
            index = year * 12 + month - 1 - lag * 3
            y, m = index // 12, index % 12 + 1
            periods.append(f'{y}-{m:02d}-{calendar.monthrange(y, m)[1]}')
        if all(d in quarters for d in periods) and date not in eps:
            eps[date] = [date, round(sum(quarters[d] for d in periods), 6), 'USD',
                         '동일 주식배당 조정 기준 실제 최근 4개 분기 희석 EPS 합계']
    fund['eps'] = [r for _, r in sorted(eps.items())]
    fund['eps_basis'] = '실적 희석 EPS · 완결 연간 또는 같은 주식수 기준 실제 4분기 합계'
    return fund


def run(offline=False):
    return collect(offline, registry_path=REGISTRY, out=OUT, cache=CACHE,
                   fundamentals_parser=copper_fundamentals, kind='copper_valuation',
                   methodology=METHODOLOGY, collect_time='08:20', index_id='copper_valuation_index',
                   index_filename='copper_valuation_index.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    run(parser.parse_args().offline)

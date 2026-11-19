"""Daily offshore operator closes and reported PER/PBR reference price bands."""
import argparse

from fetch_semicon_valuation import ROOT, collect

REGISTRY = ROOT / 'manual/offshore-valuation/companies.json'
OUT = ROOT / 'data/offshore/valuation'
CACHE = ROOT / '.cache/offshore-valuation'
METHODOLOGY = (
    '상장 보통주 전사 연결 기준. 분할 반영 종가이며 배당 재투자는 미반영합니다. '
    'PER=종가/실적 TTM 희석 EPS(완결 연간 포함), PBR=종가/보통주 귀속 자본 기준 기말 BPS입니다. '
    'Odfjell Drilling의 NOK 주가는 USD 공시 EPS·BPS를 같은 거래일 USD/NOK로 변환해 비교합니다. '
    'EPS·BPS가 0 이하이거나 실적이 없으면 N/M이며 해당 밴드는 끊습니다. '
    '2022년 이후 양의 유효 PER/PBR 중앙값의 0.5·0.75·1·1.25·1.5배를 참고 주가선으로 표시합니다. '
    '주가와 실적 이력의 확보 기간은 다릅니다. 구주와 구조조정 이후 신주의 가격을 이어 붙이지 않습니다. '
    '손상차손·자산 매각·구조조정·세금 등 일회성 손익도 포함한 보고 실적이며 조정 EPS나 전망치가 아닙니다. '
    '재작성된 결산기간 기준 참고치이며 공시일 당시의 투자 가능 정보를 재현하는 백테스트가 아닙니다.'
)


def run(offline=False):
    return collect(offline, registry_path=REGISTRY, out=OUT, cache=CACHE,
                   kind='offshore_valuation', methodology=METHODOLOGY,
                   collect_time='08:30', index_id='offshore_valuation_index',
                   index_filename='offshore_valuation_index.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    run(parser.parse_args().offline)

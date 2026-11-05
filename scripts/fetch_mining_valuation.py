"""Free prices and reported PER/PBR for the existing ten mining companies."""
import argparse

from fetch_semicon_valuation import ROOT, collect, load, save

REGISTRY=ROOT/'manual/mining-valuation/companies.json'
OUT=ROOT/'data/commodities/mining-valuation'
CACHE=ROOT/'.cache/mining-valuation'
INDEX='mining_valuation_index.json'
REUSED_PATH='commodities/valuation'
REUSED_IDS={'scco','fcx'}
METHODOLOGY=(
    '보통주 기준 분할 반영 종가(배당 재투자 미반영). 주가는 표시 거래 통화 그대로이며 '
    'PER=종가/실적 TTM 희석 EPS, PBR=종가/기말 보통주 귀속 BPS입니다. '
    '원공시 EPS/BPS의 통화를 보존하고 각 거래일의 환율로 주가 통화에 맞춥니다. '
    'GBp는 펜스로 100 GBp=1 GBP이며 USD/GBP 환율에 100을 곱합니다. '
    '음수 EPS·0 이하 EPS/순자산은 N/M이며 적자 PER 밴드는 끊습니다. '
    '자동 밴드는 2022년 이후 양의 유효 배수 중앙값의 0.5·0.75·1·1.25·1.5배입니다. '
    '실적은 확보된 보고 TTM·완결 연간만 사용하며 누락 분기나 전망을 추정하지 않습니다. '
    '주가와 밴드의 확보 기간은 다릅니다. 재작성된 결산기간 기준이며 공시일 당시의 투자 정보를 재현하는 백테스트가 아닙니다. '
    '환율은 직전 7일, EPS/BPS는 460일까지 유지하고 이후 만료합니다. '
    '회사 전사 기준으로 구리·금 등 개별 광물 사업부만의 배수가 아닙니다.'
)


def combine_index(summaries):
    """SCCO/FCX reuse the copper files; never give them two competing writers."""
    document=load(OUT/INDEX,{})
    by_id={row['id']:row for row in summaries}
    copper=load(ROOT/'data/commodities/valuation/copper_valuation_index.json',{})
    for row in copper.get('companies',[]):
        if row['id'] in REUSED_IDS:
            by_id[row['id']]=dict(row,data_path=REUSED_PATH)
    order=[c['id'] for c in load(ROOT/'manual/mining/companies.json',{})['companies']]
    missing=set(order)-set(by_id)
    if missing:raise ValueError('Missing mining valuation companies: '+','.join(sorted(missing)))
    rows=[by_id[key] for key in order]
    document.update(id='mining_valuation_index',companies=rows,
        updated=max((row.get('price_date') or '' for row in rows),default=''),
        fetched=min((row[field] for row in rows for field in ('price_fetched','financial_fetched') if row.get(field)),default=''),
        auto_collect_time='08:25')
    save(OUT/INDEX,document)
    return rows


def run(offline=False):
    summaries=collect(offline,registry_path=REGISTRY,out=OUT,cache=CACHE,
        kind='mining_valuation',methodology=METHODOLOGY,collect_time='08:25',
        index_id='mining_valuation_index',index_filename=INDEX)
    return combine_index(summaries)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    run(parser.parse_args().offline)

"""Build an IMAX scenario worksheet from reviewed SEC facts and collected film IDs.

Dollar values here are USD millions. Reviewed reporting bases retain their own
source dates; refreshing a slate never claims a fresh review of contract terms.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def validate(review):
    a = review['annual_2025']
    assert abs(a['dmr'] + a['other_content'] - a['content_revenue']) < 1e-6
    assert abs(sum(a[k] for k in ('rentals', 'system_sales', 'maintenance', 'finance')) - a['technology_revenue']) < 1e-6
    assert abs(a['content_revenue'] + a['technology_revenue'] + a['other'] - a['revenue']) < 1e-6
    assert abs(sum(a[k] for k in ('content_gross', 'technology_gross', 'other_gross')) - a['gross']) < 1e-6
    assert abs(sum(a[k] for k in ('sga', 'rd', 'intangibles_amortization', 'credit_loss', 'goodwill_impairment', 'restructuring')) - (a['gross'] - a['profit'])) < 1e-6
    assert review['odyssey']['imax_gbo'] < review['q3_2026']['gbo']
    assert review['odyssey']['movie_revenue_disclosed'] is False


def build(root=ROOT):
    review = load(root / 'manual/movies/imax-model.json')
    validate(review)
    index = load(root / 'data/movies/release_index.json')
    annual, ytd = review['annual_2025'], review['ytd_2025']
    quarter = {k: round(annual[k] - ytd[k], 6) for k in ytd}
    rates = dict(dmr_pct=annual['dmr']/annual['gbo']*100,
                 jrsa_share_pct=annual['jrsa_gbo']/annual['gbo']*100,
                 jrsa_rate_pct=annual['rentals']/annual['jrsa_gbo']*100)
    periods = {}
    for entry in index['years']:
        year = entry['year']
        if year < 2026:
            continue
        slate = load(root / 'data/movies' / entry['file'])
        basis = quarter if year == 2026 else annual
        params = dict(rates, other_content=basis['other_content'], system_sales=basis['system_sales'],
                      maintenance=basis['maintenance'], finance=basis['finance'], other=basis['other'],
                      content_margin_pct=basis['content_gross']/basis['content_revenue']*100,
                      technology_margin_pct=basis['technology_gross']/basis['technology_revenue']*100,
                      other_margin_pct=basis['other_gross']/basis['other']*100,
                      opex=round(basis['gross']-basis['profit'], 6),
                      residual=round(quarter['gbo']-112, 6) if year == 2026 else round(annual['gbo']-sum(f['gbo'] for f in review['imax_references'][:5]), 6),
                      multiple=15, debt=review['balance_2026_09_30']['debt_carrying'],
                      cash=review['balance_2026_09_30']['cash'], shares=review['balance_2026_09_30']['shares'],
                      nci=None, price=None, odyssey_extra_cost=0)
        case = review['q3_2026']
        params.update(odyssey_dmr_pct=case['dmr']/case['gbo']*100,
                      odyssey_jrsa_share_pct=case['jrsa_gbo']/case['gbo']*100,
                      odyssey_jrsa_rate_pct=case['rentals']/case['jrsa_gbo']*100,
                      odyssey_content_margin_pct=case['content_gross']/case['content_revenue']*100,
                      odyssey_technology_margin_pct=case['technology_gross']/case['technology_revenue']*100)
        films = []
        for f in slate['films']:
            if not f['imax_confirmed']:
                continue
            # The reviewed November IR refers to China in the 2027 slate;
            # its 2026 North American general release is not an IMAX date.
            if f['id'] == '/movie/Avengers-Doomsday-(2026)':
                continue
            dates = sorted(e['date'] for e in f['events'] if e.get('date'))
            # Q4 starts after the fixed YTD reporting cutoff. A later re-release
            # of an earlier movie belongs in residual/carryover, not a new life.
            if year == 2026 and dates and dates[0] < '2026-10-01':
                continue
            comparable = None
            if f['id'] in review['comparables']:
                cy, cid = review['comparables'][f['id']]
                comp = next((r for r in load(root / f'data/movies/films_{cy}.json')['films'] if r['id'] == cid), None)
                if comp and comp.get('worldwide_usd') is not None:
                    comparable = dict(title=comp['title'], worldwide=comp['worldwide_usd']/1e6,
                                      url=comp.get('box_office_url') or comp['url'], checked=comp.get('box_office_checked'),
                                      scope='작품 누적 세계 흥행 · 당해 연도 IMAX 흥행과 다름')
            # Explicit, editable teaching assumptions; neither consensus nor IR.
            recognition = 35 if dates and dates[0][5:7] == '12' else 80 if dates and dates[0][5:7] == '11' else 100
            films.append(dict(id=f['id'], title=f['title'], date=dates[0] if dates else None, url=f['url'],
                              evidence=f['imax_evidence'], comparable=comparable,
                              defaults=dict(include=bool(comparable), worldwide=round(comparable['worldwide'], 1) if comparable else None,
                                            imax_pct=10, in_year_pct=recognition, direct_imax=None)))
        if year == 2027:
            films.append(dict(id='regional:2027:doomsday-china', title='Avengers: Doomsday · 중국 상영',
                date=None, url='https://www.the-numbers.com/movie/Avengers-Doomsday-(2026)',
                evidence=[dict(note='2026 Q3 IR의 2027 중국 상영 계획', source_url=review['sources']['q3']['url'])],
                regional_only=True, comparable=None,
                defaults=dict(include=False, worldwide=None, imax_pct=None, in_year_pct=100, direct_imax=None)))
        periods[str(year)] = dict(year=year, cutoff='2026-09-30' if year == 2026 else None,
            slate_fetched=slate['fetched'], slate_ok=entry.get('ok', True),
            actual=copy.deepcopy(review['ytd_2026']) if year == 2026 else dict(gbo=0, revenue=0, gross=0, profit=0),
            params=params, films=films)
    return dict(id='imax_model', name='IMAX 흥행·실적·가치 추정', schema_version=1,
                fetched=index['fetched'], updated=index['updated'], reviewed=review['reviewed'],
                default_year=2026, periods=periods, facts=review,
                description='공시 실적과 사용자 시나리오를 분리한 IMAX 추정 모델. 금액 단위 USD 백만.')


if __name__ == '__main__':
    doc = build()
    target = ROOT / 'data/movies/imax_model.json'
    target.write_text(json.dumps(doc, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print('IMAX scenario worksheet:', ', '.join(f'{y}: {len(p["films"])} films' for y, p in doc['periods'].items()))

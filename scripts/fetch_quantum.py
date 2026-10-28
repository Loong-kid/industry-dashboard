"""Free quantum-company financials and dated ETF holdings; no paid APIs."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fetch_cpu_companies import save
from fetch_game_fx import SOURCE, parse_rates, build_snapshot
from quantum_sources import METRICS, sec_rows, reviewed_table, merge_rows, derive_first_quarters, holdings, period
from fetch_quantum_prices import collect as collect_prices

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/quantum'
CACHE = ROOT / '.cache/quantum'
MANUAL = ROOT / 'manual/quantum'


def load(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback


def fetch(session, url, offline=False):
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:18] + '.bin')
    if offline:
        return path.read_bytes()
    response = session.get(url, timeout=50)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return response.content


def money(value, row, fx):
    currency = row['currency']
    lines = [f"{row['period']} · {row['start']} ~ {row['date']}", f'원자료: {value:,.6f} 백만 {currency}']
    if currency == 'USD':
        return value, lines + ['회사 USD 공시 그대로 · 환산 없음']
    quote = fx.get('periods', {}).get(f"{currency}|{row['start']}|{row['date']}")
    if not quote:
        return None, lines + ['해당 보고기간 평균환율 미확보 · USD 값 미표시']
    lines += [f"기간 평균: 1 USD = {quote['local_per_usd']:,.6f} {currency}",
              f"ECB 일별 {quote['observations']}개 관측 평균 · 원자료 ÷ 평균환율",
              f"환율 관측: {quote['first']} ~ {quote['last']}"]
    return value / quote['local_per_usd'], lines


def document(key, metric, meta, cohort, fx):
    label = METRICS[metric]
    views = {}
    for kind, view_label, frequency in [('quarter', '분기', 'quarterly'), ('half', '반기', 'semiannual'), ('annual', '연간', 'yearly')]:
        rows = [r for r in cohort.get('rows', []) if r['kind'] == kind]
        # A half-year-only issuer still exposes a clearly empty quarter view.
        if kind == 'half' and not rows:
            continue
        actual = {r['date']: r for r in rows}
        axis = set(actual)
        if rows:
            for year in range(rows[0]['year'], rows[-1]['year'] + 1):
                months = (3, 6, 9, 12) if kind == 'quarter' else (6, 12) if kind == 'half' else (12,)
                for month in months:
                    end = f'{year}-{month:02d}-{30 if month in (6, 9) else 31}'
                    if rows[0]['date'] < end < rows[-1]['date']:
                        axis.add(end)
        native, points, notes, refs = [], [], {}, {}
        for date in sorted(axis):
            row = actual.get(date, {})
            value = row.get(metric)
            native.append([date, value])
            usd, memo = money(value, row, fx) if value is not None else (None, [])
            points.append([date, usd])
            if value is not None:
                ref = row['refs'][metric]
                calculation = ref.get('calculation', '')
                calculation = '같은 공시의 반기 누적 − 2분기' if 'minus Q2' in calculation else '동일 회계연도 누적 − 직전 누적' if 'minus' in calculation else '공시된 실제 기간 실적'
                notes[date] = memo + [calculation]
                components = ref.get('components', [])
                refs[date] = dict(url=ref['url'], label=row['period'] + ' · ' + ref.get('location', 'SEC 연결 실적'),
                    **(dict(supporting_sources=[dict(url=c['url'], label=c['start'] + ' ~ ' + c['end']) for c in components], source_separator=' − ') if components else {}))
        last = next((r for r in reversed(rows) if r.get(metric) is not None), None)
        currencies = {r['currency'] for r in rows}
        lookup = {(r['year'], r.get('quarter')): r['date'] for r in rows}
        views[kind] = dict(label=view_label, frequency=frequency, frequency_label=view_label + (' 단독' if kind == 'quarter' else ' · 실제 공시 기간'),
            quarter_labels=kind == 'quarter', year_labels=kind == 'annual', annual_axis=kind == 'annual',
            series={label: points} if last else {}, original_series={label: native},
            original_currency=next(iter(currencies)) if len(currencies) == 1 else '원통화', original_unit='millions',
            point_notes=notes, point_sources=refs, period_labels={r['date']: r['period'] for r in rows},
            updated=last['date'] if last else '', source_url=last['refs'][metric]['url'] if last else meta['ir_url'],
            quarterly_revenue_summary=kind == 'quarter' and metric == 'revenue',
            quarterly_profit_summary=kind == 'quarter' and metric != 'revenue', change_mode='none',
            comparison_dates={r['date']: dict(year_ago=lookup.get((r['year'] - 1, r['quarter'])),
                quarter_ago=lookup.get((r['year'] - (r['quarter'] == 1), r['quarter'] - 1 or 4))) for r in rows} if kind == 'quarter' else {},
            empty_message=f"{meta['name']} {view_label} {label} 원자료 미확보. 실제 확보한 반기·연간 공시는 해당 버튼에서 확인할 수 있습니다.")
    default = next((k for k in ('quarter', 'half', 'annual') if k in views and views[k]['series']), 'quarter')
    coverage = [r['date'] for r in cohort.get('rows', []) if r.get(metric) is not None]
    errors = cohort.get('source_errors', [])
    ok = cohort.get('status') == 'ok' and not errors
    basis = [dict(label='사업·매출 범위', value=meta['scope']), dict(label='비교 가능성', value=meta['comparability_note']),
             dict(label='손익 기준', value='공시된 영업손익과 연결 전체 당기순손익입니다. 비지배지분을 포함하며, 조정 EBITDA·조정 순익·지배주주 귀속 순익과 구분합니다. 주식보상·파생상품 평가·상장 관련 일회성 비용이 손익에 반영될 수 있습니다.'),
             dict(label='환산·기간', value='USD 공시는 그대로, EUR·SGD 원자료는 실제 분기·반기·연간 보고기간의 ECB 일별 평균환율로 USD 환산합니다. 원통화 금액·환율·기간은 금액과 표·차트의 메모에 보존합니다. 연간을 4등분하거나 반기를 2등분하지 않습니다.'),
             dict(label='확보 범위', value=(' ~ '.join((min(coverage), max(coverage))) if coverage else '미확보') + ' · 공시 확인 ' + cohort.get('checked', '미확보'))]
    if errors:
        basis.append(dict(label='조회·검토 상태', value=' / '.join(errors)))
    return dict(id=f'company_{key}_{metric}', name=meta['name'] + ' · ' + label, unit='백만 USD', company_kpi=True,
        span_gaps=False, zero_baseline=True, fetched=cohort.get('fetched'), source='SEC·공식 연결 공시',
        description=meta['scope'], basis_details=basis,
        collection_status=dict(ok=ok, checked=cohort.get('checked', ''), message='공개 원문 조회 완료' if ok else '최신 조회·공시 검토 필요 · 기존 성공 자료 유지'),
        default_view=default, series_views=views, **{k: v for k, v in views[default].items() if k != 'label'})


def check_new_reports(session, meta, sources, asof, offline):
    """Surface new unreviewed foreign financial statements, not funding notices.

    6-Ks are often untagged. Never mark them automatically parsed merely because
    a submissions list was reachable. New table mappings require review.
    """
    latest = max(s['filed'] for s in sources)
    recent = json.loads(fetch(session, f'https://data.sec.gov/submissions/CIK{meta["cik"]:010d}.json', offline))['filings']['recent']
    warnings = []
    for i, form in enumerate(recent['form']):
        date = recent['filingDate'][i]
        if form not in ('6-K', '20-F', '20-F/A') or not latest < date <= asof:
            continue
        acc = recent['accessionNumber'][i].replace('-', '')
        base = f'https://www.sec.gov/Archives/edgar/data/{meta["cik"]}/{acc}/'
        url = base + recent['primaryDocument'][i]
        raw = fetch(session, url, offline)
        soup = BeautifulSoup(raw, 'html.parser')
        candidates = [urljoin(url, a['href']) for a in soup.select('a[href]') if ('99' in a['href'] and a['href'].endswith(('.htm', '.html')))]
        texts = [soup.get_text(' ', strip=True).lower()]
        for link in list(dict.fromkeys(candidates))[:3]:
            texts.append(BeautifulSoup(fetch(session, link, offline), 'html.parser').get_text(' ', strip=True).lower())
        if any(('consolidated statements' in t or 'consolidated statement' in t) and
               ('revenue' in t and ('operating loss' in t or 'loss from operations' in t)) for t in texts):
            warnings.append('새 재무 공시 수치 확인 필요: ' + date + ' · ' + url)
    return warnings


def collect(offline=False, asof=None):
    asof = asof or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta = load(MANUAL / 'companies.json', {})
    sources = load(MANUAL / 'sources.json', [])
    state = load(OUT / 'state.json', dict(companies={}))
    session = requests.Session()
    session.headers['User-Agent'] = 'industry-dashboard personal research wkorotk@gmail.com'
    for key, spec in meta.items():
        prior = state['companies'].get(key, {})
        rows, errors = [], []
        own_sources = [s for s in sources if s['company'] == key]
        if spec.get('auto_sec'):
            try:
                payload = json.loads(fetch(session, f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json', offline))
                rows = sec_rows(payload, spec, asof)
                if not rows:
                    raise ValueError('empty operating history')
            except (requests.RequestException, ValueError, KeyError, OSError) as e:
                errors.append('SEC 연결 실적 조회 미완료 (' + type(e).__name__ + ')')
        for source in own_sources:
            try:
                rows = merge_rows(rows, reviewed_table(fetch(session, source['url'], offline), source, asof))
            except (requests.RequestException, ValueError, KeyError, OSError, IndexError) as e:
                errors.append(source['filed'] + ' 공시 표 조회·수치 확인 필요 (' + type(e).__name__ + ')')
        if not spec.get('auto_sec'):
            try:
                errors += check_new_reports(session, spec, own_sources, asof, offline)
            except (requests.RequestException, ValueError, KeyError, OSError) as e:
                errors.append('신규 6-K·20-F 확인 미완료 (' + type(e).__name__ + ')')
        # Successful current facts replace their own history; old values do not
        # override restated figures. On partial failure retain reviewed old rows.
        fresh = derive_first_quarters(merge_rows(prior.get('rows', []) if errors else [], rows))
        state['companies'][key] = dict(rows=fresh, checked=prior.get('checked', asof) if offline else asof,
            fetched=prior.get('fetched') if offline else asof if rows else prior.get('fetched'),
            status='ok' if rows and not errors else 'partial' if fresh else 'unavailable', source_errors=errors)
        print(key, len(fresh), 'periods', '; '.join(errors), flush=True)
        time.sleep(.15)
    intervals = sorted({(r['currency'], r['start'], r['date']) for c in state['companies'].values() for r in c['rows'] if r['currency'] != 'USD'})
    raw = None; rates = None; error = None
    try:
        raw = fetch(session, SOURCE, offline); rates = parse_rates(raw)
    except (requests.RequestException, ValueError, KeyError, OSError):
        error = 'ECB unavailable; exact completed intervals retained'
    fx = build_snapshot(load(OUT / 'fx.json', {}), intervals, rates, asof, hashlib.sha256(raw).hexdigest() if raw else None, error)
    if not offline:
        state['updated'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT / 'state.json', state); save(OUT / 'fx.json', fx)
    for key, spec in meta.items():
        for metric in METRICS:
            save(OUT / f'company_{key}_{metric}.json', document(key, metric, spec, state['companies'][key], fx))
    universe = load(OUT / 'universe.json', {})
    etfs = load(MANUAL / 'etfs.json', [])
    for etf in etfs:
        if not etf.get('holdings_url'):
            continue
        try:
            old = next((e for e in universe.get('etfs', []) if e['id'] == etf['id']), {})
            etf.update(holdings(fetch(session, etf['holdings_url'], offline), asof), checked=old.get('checked', asof) if offline else asof, status='ok')
        except (requests.RequestException, ValueError, KeyError, OSError) as e:
            old = next((e for e in universe.get('etfs', []) if e['id'] == etf['id']), {})
            etf.update({k: old[k] for k in ('positions', 'asof') if k in old}, checked=asof, status='조회 미완료 · 이전 보유 내역 유지 (' + type(e).__name__ + ')')
    companies = []
    for key, spec in meta.items():
        c = state['companies'][key]
        companies.append(dict(id=key, **{k: spec[k] for k in ('name', 'ticker', 'technology', 'group', 'scope', 'ir_url')},
            financial_end=max((r['date'] for r in c['rows']), default=''), status=c['status'], source_errors=c['source_errors'],
            periods={kind: len([r for r in c['rows'] if r['kind'] == kind]) for kind in ('quarter', 'half', 'annual')}))
    save(OUT / 'universe.json', dict(name='양자컴퓨터 ETF·추적 대상', updated=asof,
        fetched=universe.get('fetched') if offline else asof, etfs=etfs, companies=companies))
    print('Published', len(meta) * len(METRICS), 'quantum cards;', len(fx['missing']), 'missing FX intervals', flush=True)
    collect_prices(offline, asof)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--asof', help='YYYY-MM-DD; reject later financial disclosures')
    args = parser.parse_args()
    collect(args.offline, args.asof)

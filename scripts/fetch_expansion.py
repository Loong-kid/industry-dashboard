"""Collect KOSPI/KOSDAQ facility-investment filings and official amendment lineage."""
import argparse
import datetime as dt
import io
import json
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from expansion_document import InvestmentParseError, PARSER_VERSION, compact, main_metadata, parse_document

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'data/expansion/source_state.json'
CACHE = ROOT / '.cache/expansion'
LIST_FIELDS = ['rcept_no', 'rcept_dt', 'corp_name', 'corp_code', 'stock_code', 'corp_cls', 'report_nm', 'rm']


def today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    temp.replace(path)


def load_state():
    return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'reports': {}}


def request(session, url, **params):
    # Do not log request exception messages: their URLs may contain the API key.
    for attempt in range(4):
        try:
            response = session.get(url, params=params, timeout=35)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 3: raise RuntimeError('DART transport failed') from None
            time.sleep(2 ** attempt)


def chunks(begin, end):
    b, e = dt.datetime.strptime(begin, '%Y%m%d').date(), dt.datetime.strptime(end, '%Y%m%d').date()
    if b > e: raise ValueError('start is after end')
    while b <= e:
        stop = min(b + dt.timedelta(days=30), e)
        yield b.strftime('%Y%m%d'), stop.strftime('%Y%m%d')
        b = stop + dt.timedelta(days=1)


def scan_reports(api_key, begin, end):
    def scan(market, b, e):
        result = []
        with requests.Session() as session:
            page = 1
            while True:
                data = request(session, 'https://opendart.fss.or.kr/api/list.json', crtfc_key=api_key,
                               bgn_de=b, end_de=e, pblntf_ty='I', pblntf_detail_ty='I001', corp_cls=market,
                               last_reprt_at='N', page_count=100, page_no=page).json()
                if data.get('status') == '013': break
                if data.get('status') != '000': raise RuntimeError('DART list status ' + str(data.get('status')))
                for row in data.get('list', []):
                    if '신규시설투자' in compact(row.get('report_nm', '')):
                        result.append({k: (row.get(k) or '').strip() for k in LIST_FIELDS})
                if page >= int(data.get('total_page', 1)): break
                page += 1
                time.sleep(.08)
        return result
    found = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(scan, cls, b, e) for cls in ['Y', 'K'] for b, e in chunks(begin, end)]
        for future in as_completed(futures):
            for row in future.result(): found[row['rcept_no']] = row
    return sorted(found.values(), key=lambda r: r['rcept_no'])


def fetch_report(listing, api_key='', cached=None):
    no = listing['rcept_no']
    if not re.fullmatch(r'\d{14}', no): raise ValueError('invalid receipt')
    with requests.Session() as session:
        session.headers['User-Agent'] = 'Mozilla/5.0'
        main = request(session, 'https://dart.fss.or.kr/dsaf001/main.do', rcpNo=no)
        main.encoding = 'utf-8'
        family, viewer = main_metadata(main.text, no)
        record = dict(listing=listing, family=family, family_status='verified', checked=today().isoformat(), status='ok')
        # The immutable body can be reused; the public main page always refreshes lineage.
        if cached and cached.get('status') == 'ok' and cached.get('parsed', {}).get('parser_version') == PARSER_VERSION:
            record.update(parsed=cached['parsed'], withdrawn=cached.get('withdrawn', False))
            return record
        own = next(f for f in family if f['rcept_no'] == no)
        withdrawn = '철회' in listing.get('report_nm', '') or '철회' in own['report_nm']
        if withdrawn:
            record.update(parsed={}, withdrawn=True)
            return record
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / (no + '.html')
        raw = path.read_bytes() if path.exists() else None
        provider = 'DART public viewer'
        if raw is None and viewer:
            keys = ['rcpNo', 'dcmNo', 'eleId', 'offset', 'length', 'dtd']
            response = request(session, 'https://dart.fss.or.kr/report/viewer.do', **dict(zip(keys, viewer)))
            raw = response.content
        if raw is None and api_key:
            response = request(session, 'https://opendart.fss.or.kr/api/document.xml', crtfc_key=api_key, rcept_no=no)
            if zipfile.is_zipfile(io.BytesIO(response.content)):
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    names = [n for n in archive.namelist() if n.lower().endswith(('.xml', '.html'))]
                    if len(names) == 1: raw = archive.read(names[0]); provider = 'OpenDART original'
        if raw is None: raise InvestmentParseError('original body unavailable')
        try:
            parsed = parse_document(raw, listing)
        except InvestmentParseError:
            review = CACHE / 'review'; review.mkdir(parents=True, exist_ok=True)
            (review / (no + '.html')).write_bytes(raw)
            raise
        if not path.exists(): path.write_bytes(raw)
        record.update(parsed=parsed, withdrawn=parsed.get('investment_withdrawn', False), source_provider=provider)
        return record


def run(api_key='', begin=None, end=None, seed_only=False, refresh=False, pending_only=False):
    state = load_state()
    end = end or today().strftime('%Y%m%d')
    if begin is None:
        checkpoint = state.get('scanned_through')
        begin = ((dt.datetime.strptime(checkpoint, '%Y%m%d').date() - dt.timedelta(days=7)) if checkpoint else today() - dt.timedelta(days=365)).strftime('%Y%m%d')
    # Validate date arguments before any request (including manual workflow inputs).
    list(chunks(begin, end))
    if pending_only:
        listings = []
    elif seed_only:
        listings = json.loads((ROOT / 'manual/expansion_seeds.json').read_text(encoding='utf-8'))
    else:
        if not api_key: raise RuntimeError('DART_API_KEY is required for the market-wide listing')
        listings = scan_reports(api_key, begin, end)
        state['scanned_from'] = min(begin, state.get('scanned_from', begin))
        state['scanned_through'] = max(end, state.get('scanned_through', end))
    records = state['reports']
    for listing in listings:
        entry = records.setdefault(listing['rcept_no'], {'status': 'pending'})
        entry.setdefault('listing', {}).update(listing)
    # Save the pending queue before requests so a bounded workflow can resume it.
    state['fetched'] = today().isoformat()
    if not pending_only:
        state['initial_collection'] = 'reviewed_seed' if seed_only and not state.get('scanned_through') else 'market_wide'
    write(STATE, state)
    todo = {r['listing']['rcept_no']: r['listing'] for r in records.values()
            if r.get('status') != 'ok' or (not r.get('withdrawn') and r.get('parsed', {}).get('parser_version') != PARSER_VERSION) or refresh}
    todo.update({r['rcept_no']: r for r in listings if '정정' in r.get('report_nm', '') or '철회' in r.get('report_nm', '')})
    seen = set()
    print(f'Listed {len(listings)} facility filings; checking {len(todo)} originals', flush=True)
    while todo:
        batch = {no: row for no, row in todo.items() if no not in seen}
        if not batch: break
        todo = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(fetch_report, row, api_key, None if refresh else records.get(no)): row for no, row in batch.items()}
            for future in as_completed(futures):
                listing = futures[future]; no = listing['rcept_no']; seen.add(no)
                try:
                    result = future.result(); records[no] = result
                    # Bring in originals/amendments outside the scan window using official receipt links.
                    for relative in result['family']:
                        rn = relative['rcept_no']
                        if rn not in records:
                            sibling = dict(listing, **relative, rm='')
                            records[rn] = {'listing': sibling, 'status': 'pending'}
                            todo[rn] = sibling
                except Exception as exc:
                    previous = records[no]
                    previous.update(status='error', error_type=type(exc).__name__, checked=today().isoformat())
                    if isinstance(exc, InvestmentParseError): previous['parse_error'] = str(exc)
                    print(f'Receipt {no}: {type(exc).__name__}; retained for review/retry', flush=True)
                if len(seen) % 25 == 0:
                    write(STATE, state)
                    print(f'Checked {len(seen)} receipts', flush=True)
        write(STATE, state)
    state['fetched'] = today().isoformat()
    if not pending_only:
        state['initial_collection'] = 'reviewed_seed' if seed_only and not state.get('scanned_through') else 'market_wide'
    write(STATE, state)
    errors = sum(r.get('status') != 'ok' for r in records.values())
    print(f'Saved {len(records)} receipts; {errors} pending/error', flush=True)
    return errors


def reparse_cache():
    state = load_state()
    for no, record in state['reports'].items():
        path = CACHE / (no + '.html')
        if not path.exists() or record.get('withdrawn'): continue
        try:
            record['parsed'] = parse_document(path.read_bytes(), record['listing'])
            record['withdrawn'] = record['parsed'].get('investment_withdrawn', False)
            record['status'] = 'ok'
            record.pop('parse_error', None); record.pop('error_type', None)
        except InvestmentParseError as exc:
            record.update(status='error', parse_error=str(exc), error_type=type(exc).__name__)
    write(STATE, state)
    return sum(r.get('status') != 'ok' for r in state['reports'].values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='begin')
    parser.add_argument('--to', dest='end')
    parser.add_argument('--seed-only', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--reparse-cache', action='store_true', help='Reparse cached original bodies without network requests')
    parser.add_argument('--pending-only', action='store_true', help='Retry saved original receipts without querying the market listing')
    args = parser.parse_args()
    raise SystemExit(bool(reparse_cache() if args.reparse_cache else run(os.environ.get('DART_API_KEY', ''), args.begin, args.end, args.seed_only, args.refresh, args.pending_only)))

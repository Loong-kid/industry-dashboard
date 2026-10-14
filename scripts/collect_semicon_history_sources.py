"""Download public regulator facts for a reviewed semiconductor history backfill.

This only collects source facts. It does not publish or estimate missing quarters.
DART_API_KEY stays in the environment and is never written to the archive/log.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import time
import requests
import os

SEC_COMPANIES = {'micron': 723125, 'globalfoundries': 1709048, 'photronics': 810136}

def collect(out, asof):
    out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'IndustryDashboard public financial research; https://github.com/Loong-kid/industry-dashboard'
    status = {}
    for company, cik in SEC_COMPANIES.items():
        url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010}.json'
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
            value = r.json()
            if int(value.get('cik', -1)) != cik or not value.get('facts'):
                raise ValueError('Unexpected regulator response')
            (out / (company + '-sec.json')).write_text(json.dumps(value), encoding='utf-8')
            status[company] = {'ok': True, 'url': url, 'entity': value.get('entityName')}
        except Exception as e:
            status[company] = {'ok': False, 'error_type': type(e).__name__, 'http_status': getattr(getattr(e, 'response', None), 'status_code', None)}
        time.sleep(.3)
    key = os.environ.get('DART_API_KEY')
    reports = []
    if key:
        for year in range(2015, int(asof[:4]) + 1):
            for code, month in [('11013', 3), ('11012', 6), ('11014', 9), ('11011', 12)]:
                # Skip reporting periods not yet ended; unpublished periods return 013.
                if f'{year}-{month:02}-01' > asof:
                    continue
                try:
                    r = session.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json', params={'crtfc_key': key, 'corp_code': '00411048', 'bsns_year': year, 'reprt_code': code, 'fs_div': 'CFS'}, timeout=35)
                    r.raise_for_status(); value = r.json()
                    if value.get('status') == '013':
                        r = session.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json', params={'crtfc_key': key, 'corp_code': '00411048', 'bsns_year': year, 'reprt_code': code, 'fs_div': 'OFS'}, timeout=35)
                        r.raise_for_status(); value = r.json()
                    reports.append({'year': year, 'month': month, 'status': value.get('status'), 'rows': value.get('list', [])})
                except Exception as e:
                    reports.append({'year': year, 'month': month, 'error_type': type(e).__name__})
                time.sleep(.2)
        (out / 'snstech-dart.json').write_text(json.dumps({'checked': asof, 'corp_code': '00411048', 'reports': reports}, ensure_ascii=False), encoding='utf-8')
    status['snstech'] = {'key_configured': bool(key), 'reports': sum(bool(r.get('rows')) for r in reports)}
    (out / 'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    print(json.dumps(status, ensure_ascii=True))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='tmp/semicon-regulator-sources')
    parser.add_argument('--as-of', required=True, type=lambda value: dt.date.fromisoformat(value).isoformat())
    args = parser.parse_args()
    collect(Path(args.output), args.as_of)

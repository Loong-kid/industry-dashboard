"""HD Hyundai Heavy Industries Engine & Machinery segment, from official IR."""
import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlencode
from zipfile import BadZipFile

from bs4 import BeautifulSoup
import pymupdf
import requests

from fetch_game_fx import SOURCE, build_snapshot, parse_rates
from fetch_quantum import document as financial_document
from fetch_shipbuilding_equipment import load
from fetch_cpu_companies import save
from shipbuilding_equipment_sources import end

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/shipbuilding'
MANUAL = ROOT / 'manual/shipbuilding-equipment/hhi-engine.json'
STATE = OUT / 'hhi_engine_state.json'
ORIGIN = 'https://hd-hhi.com'
IR = ORIGIN + '/kr/investors/ir-data/earnings-release'
METRICS = ('revenue', 'profit')
TITLE = re.compile(r'(20\d{2})\s*년\s*([1-4])\s*분기\s*연결\s*실적발표')
DOWNLOAD = re.compile(r"front_file_download\('([^']+)',\s*'([^']+)',\s*'([^']+)'\)")
ENGINE = re.compile(r'^\s*엔\s*진\s*기\s*계\s*')
META = {
    'name': 'HD현대중공업 엔진기계',
    'scope': 'HD현대중공업 연결 기준 엔진기계 부문 실적. 선박용 엔진, 디젤 발전설비, 펌프·유체기계 등을 포함합니다.',
    'comparability_note': '회사 IR의 사업부문별 연결기준 실적표를 일관되게 사용합니다. DART 영업부문 주석의 조정 전 부문 매출과 기준이 다를 수 있습니다.',
    'ir_url': IR,
}


def archive(html):
    result = {}
    for entry in BeautifulSoup(html, 'html.parser').select('.card'):
        title = entry.select_one('.card-subject')
        download = entry.select_one('a.download-button[onclick]')
        if not title or not download:
            continue
        period = TITLE.search(title.get_text(' ', strip=True))
        args = DOWNLOAD.fullmatch(download['onclick'])
        if period and args and args[1] == 'irDataEarningsRelease' and args[2].lower().endswith('.pdf'):
            key = (int(period[1]), int(period[2]))
            result[key] = ORIGIN+'/common/fileDownload?'+urlencode(dict(zip(('folderName','fileName','originalFileName'),args.groups())))
    if not result:
        raise ValueError('Official earnings archive contains no recognized quarterly links')
    return result


def segment_row(text, quarter, pdf_header=''):
    headers = text+'\n'+pdf_header
    compact = re.sub(r'\s+','',headers)
    if '사업부문별' not in compact or '억원' not in compact or compact.count('영업이익') < 3:
        raise ValueError('Expected a segment earnings table in KRW 100m')
    rows = [ENGINE.sub('', line, count=1) for line in text.splitlines() if ENGINE.match(line)]
    if len(rows) != 1:
        raise ValueError('Expected exactly one engine segment row')
    tokens = rows[0].replace('|', ' ').replace('%','').replace(']',' ').split()
    if len(tokens) != (15 if quarter == 4 else 9):
        raise ValueError('Unexpected earnings table columns')
    pairs = []
    for i in range(0, len(tokens), 3):
        revenue, profit = (int(v.replace(',','')) for v in tokens[i:i+2])
        margin = tokens[i+2]
        # OCR occasionally drops the single decimal point in a margin (e.g. 248).
        if re.fullmatch(r'-?\d+', margin):
            margin = int(margin)/10
        if revenue <= 0 or abs(float(margin)-profit/revenue*100) > .12:
            raise ValueError('Engine segment margin does not reconcile')
        pairs.append((revenue, profit))
    return pairs


def parse_release(raw, year, quarter, url, known, tesseract):
    with pymupdf.open(stream=raw, filetype='pdf') as pdf:
        if len(pdf) < 5:
            raise ValueError('Segment earnings page missing')
        page = pdf[4]
        text = page.get_text(sort=True)
        try:
            pairs = segment_row(text, quarter)
        except ValueError:
            if not tesseract:
                raise
            scan = page.get_pixmap(matrix=pymupdf.Matrix(3,3), alpha=False).tobytes('png')
            result = subprocess.run([tesseract, 'stdin', 'stdout', '-l', 'kor+eng', '--psm', '6'],
                                    input=scan, capture_output=True, timeout=45, check=True)
            pairs = segment_row(result.stdout.decode('utf-8'), quarter, text)
    source = url+'#page=5'
    previous = (year-(quarter==1),quarter-1 or 4)
    if previous not in known or (year-1,quarter) not in known:
        raise ValueError('Comparative quarters are missing from reviewed history')
    if pairs[:2] != [tuple(known[year-1,quarter][:2]),tuple(known[previous][:2])]:
        raise ValueError('IR comparative figures changed, review before publication')
    if quarter == 4:
        quarters = [known[year,q][:2] for q in range(1,4)] + [pairs[2]]
        if any(abs(total-sum(row[i] for row in quarters)) > 3 for i,total in enumerate(pairs[4])):
            raise ValueError('Annual engine results differ from the sum of quarters')
        return {(year,4):[*pairs[2],source],(year,0):[*pairs[4],source]}
    return {(year,quarter):[*pairs[2],source]}


def period_rows(records):
    rows = []
    bounds = [('01-01','12-31'),('01-01','03-31'),('04-01','06-30'),('07-01','09-30'),('10-01','12-31')]
    for (year,q),(revenue,profit,url) in sorted(records.items()):
        start,end = (f'{year}-{part}' for part in bounds[q])
        refs = {m:dict(url=url,location='회사 IR · 엔진기계') for m in METRICS}
        rows.append(dict(year=year,quarter=q,kind='quarter' if q else 'annual',period=f'{year} Q{q}' if q else str(year),
                         start=start,date=end,currency='KRW',revenue=revenue*100,profit=profit*100,refs=refs))
    return sorted(rows,key=lambda row:(row['date'],row['kind']))


def docs(rows, state, fx):
    cohort = dict(rows=rows,fetched=state['fetched'],checked=state['checked'],
                  status='partial' if state['errors'] else 'ok',source_errors=state['errors'])
    for metric in METRICS:
        doc = financial_document('hhi_engine_segment',metric,META,cohort,fx)
        doc['source'] = 'HD현대중공업 공식 IR'
        for entry in doc['basis_details']:
            if entry['label']=='손익 기준':
                entry['value']='IR 실적발표의 엔진기계 부문 매출과 영업이익입니다. 2025년 12월 HD현대미포 합병 이후 IR의 공시 기준을 따릅니다.'
            if entry['label']=='환산·기간':
                entry['value']='분기와 연간은 각각 IR에 발표된 단독 실적입니다. 해당 기간 ECB 일별 원/USD 평균으로 환산하고 원화 금액은 메모에 표시합니다.'
        for view in doc['series_views'].values():
            for points in view['original_series'].values():
                for date,value in points:
                    if value is not None:
                        view['point_notes'][date].insert(1,f'IR 원화: {value/100:,.0f}억 원')
        yield doc


def collect(offline=False, tesseract=None):
    today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    reviewed = load(MANUAL,{})
    old = load(STATE,{})
    manual = {(r['year'],r['quarter']):[r['revenue'],r['profit'],r['url']] for r in reviewed['rows']}
    auto = {(r['year'],r['quarter']):r['values'] for r in old.get('automatic',[])}
    known = {**auto,**manual}
    fetched = old.get('fetched',reviewed['reviewed'])
    errors = list(old.get('errors',[]))
    if not offline:
        errors = []
        try:
            with requests.Session() as session:
                response = session.get(IR,timeout=20)
                response.raise_for_status()
                for (year,q),url in sorted(archive(response.content).items()):
                    if (year,q) in known or end(year,q)>today:
                        continue
                    try:
                        response = session.get(url,timeout=25)
                        response.raise_for_status()
                        added = parse_release(response.content,year,q,url,known,tesseract)
                        auto.update(added)
                        known.update(added)
                    except (requests.RequestException,ValueError,OSError,RuntimeError,subprocess.SubprocessError) as exc:
                        errors.append(f'{year} Q{q} 엔진기계 IR 확인 필요 ({type(exc).__name__})')
                if not errors:
                    fetched=today
        except (requests.RequestException,ValueError) as exc:
            errors.append(f'IR 목록 확인 필요 ({type(exc).__name__})')
    rows = period_rows(known)
    shared = load(OUT/'equipment_fx.json',{}).get('periods',{})
    own_fx = old.get('fx',{})
    missing = [('KRW',r['start'],r['date']) for r in rows if f"KRW|{r['start']}|{r['date']}" not in shared]
    if missing and not offline:
        try:
            response = requests.get(SOURCE,timeout=30)
            response.raise_for_status()
            own_fx = build_snapshot(dict(periods=own_fx),missing,parse_rates(response.content),today,
                                    hashlib.sha256(response.content).hexdigest())['periods']
        except (requests.RequestException,ValueError,BadZipFile):
            errors.append('ECB 기간 평균환율 확인 필요')
    fx = dict(periods={**own_fx,**shared})
    if any('|'.join(interval) not in fx['periods'] for interval in missing):
        errors.append('일부 실적 기간의 USD 환산 대기')
    state = dict(checked=old.get('checked',reviewed['reviewed']) if offline else today,fetched=fetched,errors=errors,fx=own_fx,
                 automatic=[dict(year=y,quarter=q,values=v) for (y,q),v in sorted(auto.items())])
    for doc in docs(rows,state,fx):
        save(OUT/(doc['id']+'.json'),doc)
    save(STATE,state)
    print(f'HD Hyundai Heavy Industries engine segment: {len(rows)} published periods, {len(errors)} review items.')


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--offline',action='store_true')
    cli.add_argument('--tesseract',default=shutil.which('tesseract'))
    args = cli.parse_args()
    collect(args.offline,args.tesseract)

"""Read public Minmetals daily LME PDFs; no authenticated LME endpoints.

Normal runs follow the public archive's linked recent PDFs. Backfill checks the
archive's dated filenames, caching originals outside the published data folder.
Scanned PDFs require optional OCR only for the one-time historical import.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import pymupdf
import requests
from bs4 import BeautifulSoup

from derive_copper_market import OUT, check_date, lme_document, save

PAGE = 'https://www.mjfins.com/Service/LMEData/'
BASE = 'https://www.mjfins.com/Uploads/LMEData/LME库存报告_'
ID = 'comm_copper_lme_warrant_composition'


def pdf_url(date):
    return BASE + date.replace('-', '') + '.pdf'


def parse_text(text, date, today, url, digest, extraction='pdf_text'):
    """Reject mismatched dates, shifted columns, bad balances and OCR errors."""
    check_date(date, today)
    stamps = re.findall(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)', text)
    iso_stamps = re.findall(r'(?<!\d)(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)', text)
    dates = {f'{int(y):04}-{int(m):02}-{int(d):02}' for d, m, y in stamps}
    dates.update(f'{int(y):04}-{int(m):02}-{int(d):02}' for y, m, d in iso_stamps)
    if date not in dates or 'LME' not in text.upper():
        raise ValueError('PDF observation date/title mismatch')
    match = re.search(r'伦敦铜\s*(.*?)\s*伦敦锌', text, re.S)
    if not match:
        raise ValueError('Copper row missing or wrong metal order')
    cells = re.findall(r'-?\d+(?:\.\d+)?%?', match[1].replace(',', '').replace('−', '-'))
    if len(cells) != 8:
        raise ValueError(f'Wrong copper column count: {cells}')
    previous, delivered_in, delivered_out, total, change, live, cancelled = map(int, cells[:7])
    share = float(cells[7].rstrip('%'))
    precision = len(cells[7].rstrip('%').partition('.')[2])
    if (min(previous, delivered_in, delivered_out, total, live, cancelled) < 0
            or total <= 0 or total != live + cancelled
            or any(v % 25 for v in (previous, delivered_in, delivered_out, total, live, cancelled))
            or abs(share - cancelled / total * 100) > .5 * 10**(-precision) + .001):
        raise ValueError('Copper quantities/share do not reconcile')
    flows_valid = previous + delivered_in - delivered_out == total
    return dict(date=date, total=total, live=live, cancelled=cancelled,
        previous_total=previous, delivered_in=delivered_in, delivered_out=delivered_out,
        flows_valid=flows_valid, reported_change_consistent=change == total - previous,
        reported_change=change, reported_cancelled_share=share, share_precision=precision,
        unit='metric tonnes', provider='Minmetals Financial Services · LME republication',
        source_url=url, checked=today, sha256=digest, extraction=extraction,
        locator='LME库存报告 · PDF 기준일 · 伦敦铜 행 (등록·취소·입출고 원문)')


def scanned_copper_cells(img, ocr):
    """Read actual bordered cells so printed zeroes cannot vanish in detection."""
    import cv2
    import numpy as np
    binary = cv2.threshold(cv2.cvtColor(img,cv2.COLOR_RGB2GRAY),120,255,cv2.THRESH_BINARY_INV)[1]
    horizontal = cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((1,80),np.uint8))
    vertical = cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((40,1),np.uint8))
    def centers(mask):
        ids = np.flatnonzero(mask)
        groups = np.split(ids,np.flatnonzero(np.diff(ids)>max(6,round(img.shape[1]/200)))+1)
        return [int(np.mean(group)) for group in groups if len(group)]
    ys = centers(np.count_nonzero(horizontal,axis=1)>img.shape[1]*.5)
    xs = centers(np.count_nonzero(vertical,axis=0)>img.shape[0]*.08)
    if len(xs)!=10 or len(ys)!=8:
        raise ValueError('Scanned PDF grid changed; review required')
    margin = max(4,round(img.shape[1]/400))
    rois = [img[ys[1]+margin:ys[2]-margin,xs[i]+margin:xs[i+1]-margin].copy() for i in range(9)]
    cells = [r[0].strip().replace('−','-').replace(',','') for r in ocr.text_recognizer(rois)[0]]
    if cells[0]!='伦敦铜' or not all(re.fullmatch(r'-?\d+(?:\.\d+)?%?',c) for c in cells[1:]):
        raise ValueError(f'Scanned copper row/cell identity changed: {cells}')
    return cells


def read_pdf(content, date, today, url, ocr=None):
    if not content.startswith(b'%PDF'):
        raise ValueError('Not a public PDF')
    doc = pymupdf.open(stream=content, filetype='pdf')
    text = '\n'.join(page.get_text(sort=False) for page in doc)
    method = 'pdf_text'
    if '伦敦铜' not in text:
        if ocr is None:
            raise ValueError('Scanned historical PDF requires reviewed OCR import')
        import numpy as np
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        result, _ = ocr(img)
        if not result:
            raise ValueError('No OCR text')
        header = '\n'.join(r[1] for r in result if 'LME' in r[1].upper() or re.fullmatch(r'\d{1,4}[/-]\d{1,2}[/-]\d{1,4}',r[1]))
        cells = scanned_copper_cells(img,ocr)
        text = header + '\n' + '\n'.join(cells) + '\n伦敦锌'
        method = 'grid_ocr_dual_resolution_with_balance_validation'
    row = parse_text(text, date, today, url, hashlib.sha256(content).hexdigest(), method)
    if method.startswith('grid_ocr'):
        # Require a second render to independently reproduce every numeric cell.
        pix2 = doc[0].get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
        cells2 = scanned_copper_cells(np.frombuffer(pix2.samples,dtype=np.uint8).reshape(pix2.height,pix2.width,pix2.n),ocr)
        verified = parse_text(header+'\n'+'\n'.join(cells2)+'\n伦敦锌',date,today,url,row['sha256'],method)
        for key in ('total','live','cancelled','previous_total','delivered_in','delivered_out','reported_change','reported_cancelled_share'):
            if row[key] != verified[key]:
                raise ValueError('Scanned PDF OCR resolutions disagree; review required')
    return row


def public_links(text, today):
    found = {}
    for a in BeautifulSoup(text, 'html.parser').find_all('a', href=True):
        url = urljoin(PAGE, a['href'])
        stamp = re.fullmatch(re.escape(BASE) + r'(\d{4})(\d{2})(\d{2})\.pdf', url)
        if stamp:
            date = '-'.join(stamp.groups())
            check_date(date, today)
            found[date] = url
    if not found:
        raise ValueError('No publicly linked inventory PDFs')
    return found


def get_pdf(date, cache=None):
    url = pdf_url(date)
    path = cache / (date+'.pdf') if cache else None
    if path and path.exists():
        return date, url, path.read_bytes(), None
    try:
        response = requests.get(url, timeout=(8, 20))
        if response.status_code == 404:
            return date, url, None, 'missing_public_pdf'
        response.raise_for_status()
        if not response.content.startswith((b'%PDF', b'\x89PNG\r\n\x1a\n')):
            raise ValueError('Unrecognized public report format')
        if path:
            path.write_bytes(response.content)
        time.sleep(.12)
        return date, url, response.content, None
    except Exception as exc:
        return date, url, None, type(exc).__name__


def run(start=None, end=None, cache=None, use_ocr=False):
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    path = OUT / (ID+'.json')
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    records = {r['date']:r for r in old.get('source_records', []) if r.get('provider', '').startswith('Minmetals')}
    if start:
        first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end or today)
        check_date(last.isoformat(), today)
        dates = [(first+dt.timedelta(days=n)).isoformat() for n in range((last-first).days+1)
            if (first+dt.timedelta(days=n)).weekday() < 5]
    else:
        response = requests.get(PAGE, timeout=(8, 20))
        response.raise_for_status()
        response.encoding = 'utf-8'
        dates = sorted(public_links(response.text, today))
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    ocr = None
    if use_ocr:
        # Limit ONNX's thread pools during the one-time scanned-PDF import.
        import onnxruntime as ort
        original_options = ort.SessionOptions
        def bounded_options():
            options = original_options()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            return options
        ort.SessionOptions = bounded_options
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        ort.SessionOptions = original_options
    errors, absent, success = [], [], 0
    # Three modest parallel public-file downloads; extraction remains sequential.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for date, url, content, error in pool.map(lambda d:get_pdf(d, cache), dates):
            if error:
                (absent if error == 'missing_public_pdf' else errors).append(dict(date=date, reason=error))
                continue
            try:
                previous = records.get(date)
                if previous and previous.get('sha256') == hashlib.sha256(content).hexdigest():
                    success += 1
                    continue
                row = read_pdf(content, date, today, url, ocr)
                previous = records.get(date)
                if previous and any(previous[k] != row[k] for k in ('total','live','cancelled','delivered_in','delivered_out')):
                    raise ValueError('Source revision requires review')
                records[date] = previous or row
                success += 1
            except Exception as exc:
                errors.append(dict(date=date, reason=str(exc)))
            if (success+len(errors)+len(absent)) % 100 == 0:
                print('LME progress',success,'accepted',len(errors),'flagged',len(absent),'absent',flush=True)
    if not records:
        raise ValueError('No validated daily LME observations')
    # A failed partial refresh cannot erase previously stored observations.
    if not start and not success:
        raise ValueError('Daily archive refresh failed; existing history preserved')
    doc = lme_document(dict(reviewed=today, lme_warrants=list(records.values())))
    doc['collection_status'] = dict(checked=today, ok=success>0,
        message=f'공개 일별 PDF 확인: {success}개 검증, {len(errors)}개 확인 실패 · 기존 이력 보존')
    if start:
        prior = old.get('archive_audit',{})
        first = min(start,prior.get('start',start))
        last = max(end or today,prior.get('end',end or today))
        attempted = set(dates)
        missing = (set(prior.get('unavailable_dates',[]))-attempted) | {r['date'] for r in absent}
        flagged = [r for r in prior.get('flagged',[]) if r['date'] not in attempted] + errors
        flagged = [r for r in flagged if r['date'] not in records]
        days = (dt.date.fromisoformat(last)-dt.date.fromisoformat(first)).days+1
        weekdays = sum((dt.date.fromisoformat(first)+dt.timedelta(days=n)).weekday()<5 for n in range(days))
        doc['archive_audit'] = dict(start=first,end=last,requested_weekdays=weekdays,
            accepted=len(records),unavailable_dates=sorted(missing),flagged=sorted(flagged,key=lambda r:r['date']))
    elif old.get('archive_audit'):
        doc['archive_audit'] = old['archive_audit']
    save(doc)
    if cache:
        (cache/'audit.json').write_text(json.dumps(dict(accepted=len(records),flagged=errors,absent=absent),ensure_ascii=False,indent=2),encoding='utf-8')
    print(ID,min(records),max(records),len(records),'observations;',len(errors),'flagged;',len(absent),'absent')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--ocr',action='store_true')
    args = parser.parse_args()
    run(args.start,args.end,args.cache,args.ocr)

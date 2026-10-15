"""Validate translation integrity and the photomask reader in headless Chrome.

Run against a local static server or pass --url for the deployed site.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def plain_markdown(text):
    text = re.sub(r'^#{1,6} ', '', text, flags=re.M)
    text = re.sub(r'^[-*] |^> ?', '', text, flags=re.M)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^\s)]+\)', r'\1', text)
    return re.sub(r'\s+', '', text)


def verify(base):
    index = json.loads((ROOT / 'data/semicon/photomask_ir_library.json').read_text(encoding='utf-8'))
    catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
    photomask = next(i for i in catalog['industries'] if i['id'] == 'semicon')
    indicator_charts = sum(len(s['indicators']) for s in photomask['sections']
                           if s.get('tab') == 'snstech' and s.get('type') != 'table')
    assert len(index['documents']) == len({d['id'] for d in index['documents']}) == 82
    files = {}
    for row in index['documents']:
        raw = (ROOT / row['translation']['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['translation']['sha256']
        files[row['id']] = raw.decode('utf-8-sig')
    for company in index['companies']:
        rows = [d for d in index['documents'] if d['company'] == company['id']]
        assert len({d['period_end'] for d in rows}) == 22
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        for width in [1440, 390]:
            page = browser.new_page(viewport={'width': width, 'height': 1000}, color_scheme='dark' if width == 390 else 'light')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base + '#/semicon/snstech/ir')
            page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
            assert page.locator('.pm-periods button').count() == 22
            assert page.locator('.photomask-library input').count() == 0
            assert not page.locator('#range-picker').is_visible()
            assert page.evaluate('state.charts.length') == 0
            for company_num, company in enumerate(index['companies']):
                page.locator('.pm-companies button').nth(company_num).click()
                rows = [d for d in index['documents'] if d['company'] == company['id']]
                ends = sorted({d['period_end'] for d in rows}, reverse=True)
                for period_num, end in enumerate(ends):
                    # Check every supplied text on desktop; oldest/latest on mobile.
                    if width == 390 and period_num not in [0, len(ends) - 1]:
                        continue
                    page.locator('.pm-periods button').nth(period_num).click()
                    for row in [d for d in rows if d['period_end'] == end]:
                        page.locator('.pm-source-picker select').select_option(row['id'])
                        page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
                        actual = page.locator('.pm-translation-body').text_content()
                        actual = re.sub(r'\s+', '', actual).removeprefix('번역파일안내')
                        assert actual == plain_markdown(files[row['id']]), row['id']
                        assert page.locator('.pm-translation-download').get_attribute('href') == row['translation']['path']
                        assert page.locator('.pm-original-link').get_attribute('href') == row['url']
                        assert row['translation']['scope'] in page.locator('.pm-translation-state').inner_text()
                        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                page.evaluate('renderIndustry()')
                page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
                assert '2021' in page.locator('.pm-reader-heading').inner_text()
            page.locator('.pm-companies button').first.click()
            page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
            page.locator('.pm-inline-toggle').click()
            assert page.locator('.pm-pdf-area iframe').get_attribute('src').startswith('https://www.hoya.com/')
            page.locator('.pm-inline-toggle').click()
            assert not page.locator('.pm-pdf-area').is_visible()
            # Unsafe Markdown HTML/links stay inert.
            safe = page.evaluate('''() => {
                const rendered = renderPhotomaskMarkdown('<img src=x onerror=alert(1)>\\n\\n[x](javascript:alert)\\n\\n**Q:** test', null);
                return rendered.querySelectorAll('img,script,a').length === 0 && rendered.textContent.includes('<img');
            }''')
            assert safe
            if base.startswith('http://127'):
                output = ROOT / 'tmp/photomask-ir-20261012'
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / f'translation-{width}.png'), full_page=True)
            page.locator('.photomask-views a').first.click()
            page.wait_for_function('state.charts.length > 0 && !document.querySelector(".page-loading")', timeout=60000)
            assert page.locator('canvas').count() == indicator_charts
            assert page.locator('#range-picker').is_visible()
            assert not errors, errors
            print(json.dumps({'width': width, 'documents': 82, 'indicator_charts': indicator_charts, 'errors': errors}), flush=True)
            page.close()
        # Hold an earlier request, select a different company, then release it.
        page = browser.new_page()
        page.goto(base + '#/semicon/snstech/ir')
        page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
        pending = []
        def hold_first(route):
            if not pending:
                pending.append(route)
            else:
                route.continue_()
        page.route(re.compile(r'/photomask-ir-ko/.*\.md'), hold_first)
        page.evaluate('renderIndustry()')
        page.wait_for_selector('.pm-translation-body[aria-busy="true"]')
        page.locator('.pm-companies button').nth(1).click()
        page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
        selected = page.locator('.pm-translation-body').text_content()
        with page.expect_response(lambda response: response.url == pending[0].request.url):
            pending[0].continue_()
        assert page.locator('.pm-translation-body').text_content() == selected
        assert 'AGC' in page.locator('.pm-reader-heading').inner_text()
        page.close()
        # Retry a temporary failed translation without changing the document.
        page = browser.new_page()
        page.goto(base + '#/semicon/snstech/ir')
        page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
        failures = []
        def fail_first(route):
            if not failures:
                failures.append(route.request.url)
                route.fulfill(status=503, body='Unavailable')
            else:
                route.continue_()
        page.route(re.compile(r'/photomask-ir-ko/.*\.md'), fail_first)
        page.evaluate('renderIndustry()')
        page.wait_for_selector('.pm-translation-body button')
        page.locator('.pm-translation-body button').click()
        page.wait_for_selector('.pm-translation-body[aria-busy="false"] .pm-page-heading')
        assert page.locator('.pm-translation-body button').count() == 0
        page.close()
        print('PASS: delayed selection, retry and unchanged translation content', flush=True)
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8787/')
    verify(parser.parse_args().url)

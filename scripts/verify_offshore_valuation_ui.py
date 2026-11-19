"""Exercise all operator bands, zoom/range controls and legacy drilling routes."""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def verify(base):
    out = ROOT/'tmp/drilling-bands/ui'
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        for width in (1440, 390):
            for theme in ('light', 'dark'):
                page = browser.new_page(viewport={'width': width, 'height': 1000}, color_scheme=theme)
                errors = []
                requests = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('request', lambda r: requests.append(r.url))
                page.goto(base+'#/oil/offshore/valuations', wait_until='networkidle')
                if page.locator('#site-gate').count():
                    page.evaluate("() => {if(window.SITE_GATE)localStorage.setItem('site_gate_pass',window.SITE_GATE.hash)}")
                    page.reload(wait_until='networkidle')
                page.wait_for_function('typeof state!=="undefined" && state.oilOffshoreView==="valuations" && !document.querySelector(".page-loading")')
                expect(page.locator('.sv-summary tbody tr')).to_have_count(6)
                expect(page.locator('.sv-company')).to_have_count(6)
                expect(page.locator('.sv-card')).to_have_count(18)
                assert page.locator('#refresh-label').inner_text() == '시추 주가·밴드 갱신'
                assert page.evaluate('currentTarget().workflow') == 'update-offshore-valuation.yml'
                assert page.locator('#range-picker').is_visible()
                assert not page.locator('#content .is-error').count()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path=str(out/f'summary-{width}-{theme}.png'))
                search = page.get_by_label('주가·밸류에이션 기업 검색', exact=True)
                search.fill('ODL.OL')
                expect(page.locator('.sv-summary tbody tr')).to_have_count(1)
                assert page.locator('.sv-summary tbody tr td').nth(2).inner_text() == 'NOK'
                search.fill('')
                for company in ('transocean','valaris','noble','seadrill','odfjell','borr'):
                    root = page.locator('#sv-'+company)
                    root.scroll_into_view_if_needed()
                    expect(root.locator('canvas')).to_have_count(3, timeout=30000)
                    assert '불러오지 못했습니다' not in root.inner_text()
                    for metric in ('per', 'pbr'):
                        card = root.locator('[data-sv-metric="'+metric+'"]')
                        opener = card.locator('.sv-enlarge')
                        expect(opener).to_be_enabled()
                        opener.click()
                        dialog = page.get_by_role('dialog')
                        expect(dialog).to_be_visible()
                        expect(dialog.locator('canvas')).to_have_count(1)
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                        dialog.get_by_role('button', name='1년', exact=True).click()
                        assert dialog.locator('.sv-zoom-status').inner_text()
                        dialog.get_by_role('button', name='전체', exact=True).click()
                        if company == 'transocean' and metric == 'per':
                            page.screenshot(path=str(out/f'per-zoom-{width}-{theme}.png'))
                        page.get_by_role('button', name='확대 창 닫기', exact=True).click()
                        expect(dialog).to_have_count(0)
                assert any('/data/offshore/valuation/odfjell.json' in u for u in requests)
                assert not any('/data/semicon/valuation/' in u for u in requests)
                page.locator('#range-picker [data-range="1y"]').click()
                page.wait_for_function('state.range==="1y" && !document.querySelector(".page-loading")')
                expect(page.locator('.sv-card')).to_have_count(18)
                page.goto(base+'#/offshore/valuations', wait_until='networkidle')
                page.wait_for_function('state.oilOffshoreView==="valuations" && !document.querySelector(".page-loading")')
                assert page.url.endswith('#/oil/offshore/valuations')
                page.goto(base+'#/oil/offshore/financials', wait_until='networkidle')
                page.wait_for_function('state.oilOffshoreView==="financials" && !document.querySelector(".page-loading")')
                assert not page.locator('.sv-company').count()
                assert page.locator('.of-financial-charts canvas').count() == 9
                assert page.evaluate('Object.keys(Chart.instances).length') == 9
                assert not errors, errors
                page.close()
                print('PASS', width, theme, 'six operators, both bands, FX currency, zoom, range, lazy loading and legacy routes', flush=True)
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8811/')
    verify(parser.parse_args().url)

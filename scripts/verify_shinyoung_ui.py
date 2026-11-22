"""Verify weekly source dates, corrected indices and shipbuilding/shipping cards."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
INDICATORS = {
    'shipbuilding':['clarksons_nb_index','newbuild_prices','newbuild_orders','secondhand_index','secondhand_prices'],
    'shipping':['tanker_earnings','bulker_earnings','gas_earnings','clarksea'],
}


def verify(base):
    out = ROOT/'tmp/shipbuilding-reports/ui'
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        for width in (1440,390):
            for theme in ('light','dark'):
                page = browser.new_page(viewport={'width':width,'height':1000},color_scheme=theme)
                errors = []
                page.on('pageerror',lambda e:errors.append(str(e)))
                for industry, keys in INDICATORS.items():
                    page.goto(base+'#/'+industry,wait_until='networkidle')
                    if page.locator('#site-gate').count():
                        page.evaluate("() => {if(window.SITE_GATE)localStorage.setItem('site_gate_pass',window.SITE_GATE.hash)}")
                        page.reload(wait_until='networkidle')
                    page.wait_for_function('(industry)=>typeof state!=="undefined" && state.industry?.id===industry && !document.querySelector(".page-loading")',arg=industry)
                    for key in keys:
                        doc = json.loads((ROOT/'data'/industry/(key+'.json')).read_text(encoding='utf-8'))
                        card = page.locator('#content .card').filter(has=page.get_by_text(doc['name'],exact=True))
                        expect(card).to_have_count(1)
                        expect(card.locator('canvas')).to_have_count(1)
                        assert '2026-11-13' in card.locator('.card-stat').inner_text()
                        assert '2026-11-16' in card.inner_text()
                        assert not card.locator('.stale-badge').count()
                        assert card.locator('canvas').evaluate('(canvas)=>Chart.getChart(canvas).data.labels.at(-1)') == '2026-11-13'
                        if key == 'secondhand_index':
                            values = card.locator('canvas').evaluate('(canvas)=>Object.fromEntries(Chart.getChart(canvas).data.datasets.map(s=>[s.label,s.data.at(-1)]))')
                            assert values['벌커 중고선가지수'] == 238.08
                            assert values['컨테이너 중고선가지수'] == 88.02
                            card.scroll_into_view_if_needed()
                            card.screenshot(path=str(out/f'indices-{width}-{theme}.png'))
                        card.get_by_role('button',name='표 보기',exact=True).click()
                        assert '2026-11-13' in card.locator('.data-table').inner_text()
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                        card.get_by_role('button',name='표 닫기',exact=True).click()
                    page.evaluate('scrollTo(0,0)')
                    page.screenshot(path=str(out/f'{industry}-{width}-{theme}.png'))
                    page.locator('#range-picker [data-range="1y"]').click()
                    page.wait_for_function('state.range==="1y" && !document.querySelector(".page-loading")')
                    for key in keys:
                        assert page.evaluate('(key)=>state.docs.get(key).updated',key) == '2026-11-13'
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                    page.locator('#range-picker [data-range="all"]').click()
                    page.wait_for_function('state.range==="all" && !document.querySelector(".page-loading")')
                assert not errors, errors
                page.close()
                print('PASS',width,theme,'nine weekly cards, observation dates, bulk/container separation, tables and ranges',flush=True)
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8814/')
    verify(parser.parse_args().url)

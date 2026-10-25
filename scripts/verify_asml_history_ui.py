"""Verify ASML's full quarterly history on frontend and summary screens."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,390):
            page=browser.new_page(viewport={'width':width,'height':1000})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'#/semicon/materials/equipment/frontend',wait_until='domcontentloaded')
            def settled(tab,count):
                page.wait_for_function('(v)=>typeof state!=="undefined" && state.subtab===v[0] && state.charts.length===v[1] && !document.querySelector(".page-loading")',arg=[tab,count])
                assert not page.locator('#content .is-error').count()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            def data():
                return page.evaluate('state.charts.filter(c=>["ASML · 매출","ASML · 영업이익","ASML · CAPEX"].includes(c.canvas.closest(".card").querySelector(".card-name").textContent)).map(c=>({name:c.canvas.closest(".card").querySelector(".card-name").textContent,labels:c.data.labels,values:c.data.datasets[0].data}))')
            def quarters():
                charts=data();assert len(charts)==3
                for chart in charts:
                    assert chart['labels'][0]=='2014-03-30'
                    assert chart['labels'][-1]=='2026-09-27'
                    assert len(chart['values'])==51 and all(v is not None for v in chart['values'])
                assert [chart['values'][0] for chart in charts]==[1396.5,265.7,75.5]
            settled('equipment_frontend',21);quarters()
            for name in ['ASML · 매출','ASML · 영업이익','ASML · CAPEX']:
                card=page.locator('.card.ir-chart').filter(has=page.get_by_text(name,exact=True))
                card.get_by_role('button',name='연간',exact=True).click()
            for chart in data():
                assert len(chart['values'])==12
                assert chart['labels'][0]=='2014-12-31'
            for name in ['ASML · 매출','ASML · 영업이익','ASML · CAPEX']:
                page.locator('.card.ir-chart').filter(has=page.get_by_text(name,exact=True)).get_by_role('button',name='분기',exact=True).click()
            quarters()
            page.get_by_text('ASML · 실적',exact=True).scroll_into_view_if_needed()
            folder=ROOT/'tmp/asml-20261026';folder.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(folder/f'frontend-{width}.png'))
            page.locator('.semicon-material-tabs').get_by_role('link',name='전체 요약',exact=True).click()
            settled('equipment_summary',39);quarters()
            assert not errors,errors
            print('ASML verified',width,'51 complete quarters, annual switch, frontend and summary',flush=True)
            page.close()
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

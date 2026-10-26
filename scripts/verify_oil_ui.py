"""Desktop/mobile routes, source links, period controls and old drilling links."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def verify(base):
    output=ROOT/'tmp/oil-20261026';output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in [1440,390]:
            page=browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width==390 else 'light');errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def wait(tab,view=None):
                page.wait_for_function('([tab,view])=>typeof state!=="undefined" && state.industry.id==="oil" && state.subtab===tab && (!view||state.oilOffshoreView===view) && !document.querySelector(".page-loading")',arg=[tab,view])
                assert page.locator('#content .is-error').count()==0
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.goto(base+'#/oil');wait('majors')
            page.wait_for_function('state.charts.length===21')
            assert page.locator('#nav [aria-current="page"]').inner_text()=='원유'
            assert page.locator('#nav a[data-id="offshore"]').count()==0
            assert page.locator('#refresh-label').inner_text()=='원유 실적 확인'
            assert page.evaluate('Object.keys(Chart.instances).length')==21
            financial=page.locator('#content .card.ir-chart')
            assert financial.count()==21
            for i in range(21):financial.nth(i).get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.labels.length===12 && c.data.datasets.some(d=>d.data.every(v=>v!==null)))')
            first=financial.first;first.get_by_role('button',name='표 보기',exact=True).click()
            assert '2014' in first.locator('tbody').inner_text()
            assert first.locator('tbody a[href^="https://"]').count()>=12
            page.evaluate('scrollTo(0,0)');page.screenshot(path=str(output/f'oil-{width}.png'))
            for i in range(21):financial.nth(i).get_by_role('button',name='분기',exact=True).click()
            page.evaluate('scrollTo(0,1400)');before=page.evaluate('scrollY')
            box=page.locator('#range-picker [data-range="1y"]').bounding_box();page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
            page.wait_for_function('state.range==="1y" && state.charts.length===21 && !document.querySelector(".page-loading")')
            assert abs(page.evaluate('scrollY')-before)<40
            for view in ['market','fleet','contracts','financials']:
                page.goto(base+'#/oil/offshore/'+view);wait('offshore',view)
                assert page.get_by_role('navigation',name='해양 시추 분류').locator('[aria-current="page"]').count()==1
                assert page.locator('#refresh-label').inner_text()=='시추 지표 갱신'
                if view in ['fleet','contracts']:assert not page.locator('#range-picker').is_visible()
                page.goto(base+'#/offshore/'+view);wait('offshore',view)
                assert page.url.endswith('#/oil/offshore/'+view)
            page.goto(base+'#/offshore');wait('offshore','market')
            page.goto(base+'#/oil/offshore/invalid');wait('offshore','market')
            page.goto(base+'#/oil');wait('majors')
            page.wait_for_function('state.charts.length===21');page.reload();wait('majors')
            assert not errors,errors
            print(width,'oil cards, annuals, sources, sticky range, nested drilling and legacy links passed')
            page.close()
        browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8768/');verify(parser.parse_args().url)

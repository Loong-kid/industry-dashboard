"""Exercise the deployed/local refinery tab at desktop and mobile widths."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    output=ROOT/'tmp/refining-20261027';output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,390):
            page=browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width==390 else 'light')
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def wait(tab,count):
                page.wait_for_function('([tab,count])=>typeof state!=="undefined" && state.industry?.id==="oil" && state.subtab===tab && state.charts.length===count && !document.querySelector(".page-loading")',arg=[tab,count])
                assert page.locator('#content .is-error').count()==0
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.goto(base+'#/oil/refining');wait('refining',12)
            assert page.locator('#nav [aria-current="page"]').inner_text()=='원유'
            assert page.locator('#refresh-label').inner_text()=='정유 실적 확인'
            assert page.evaluate('Object.keys(Chart.instances).length')==12
            cards=page.locator('#content .card.ir-chart');assert cards.count()==12
            assert 'S-Oil' in page.locator('#content').inner_text()
            assert 'KRW 백만' in page.locator('#content').inner_text()
            assert 'USD 백만' in page.locator('#content').inner_text()
            assert '영업손익 (계산)' in page.locator('#content').inner_text()
            assert 'CAPEX·투자 (회사 기준)' in page.locator('#content').inner_text()
            for i in range(12):cards.nth(i).get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.labels.length===12 && c.data.datasets.some(d=>d.data.every(v=>v!==null)))')
            first=cards.first;first.get_by_role('button',name='표 보기',exact=True).click()
            assert '2014' in first.locator('tbody').inner_text()
            assert first.locator('tbody a[href^="https://"]').count()>=12
            page.evaluate('scrollTo(0,0)');page.screenshot(path=str(output/f'refining-{width}.png'))
            for i in range(12):cards.nth(i).get_by_role('button',name='분기',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.labels.length>=50 && c.data.datasets.some(d=>d.data.every(v=>v!==null)))')
            page.evaluate('scrollTo(0,1400)');before=page.evaluate('scrollY')
            box=page.locator('#range-picker [data-range="1y"]').bounding_box()
            page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
            page.wait_for_function('state.range==="1y" && state.charts.length===12 && !document.querySelector(".page-loading")')
            assert abs(page.evaluate('scrollY')-before)<40
            page.goto(base+'#/oil');wait('majors',21)
            assert page.locator('#refresh-label').inner_text()=='원유 실적 확인'
            page.goto(base+'#/oil/offshore/market')
            page.wait_for_function('state.subtab==="offshore" && !document.querySelector(".page-loading")')
            assert page.locator('#refresh-label').inner_text()=='시추 지표 갱신'
            page.goto(base+'#/oil/refining');wait('refining',12)
            page.reload();wait('refining',12)
            assert not errors,errors
            print(width,'12 refinery charts, annuals, source tables, sticky range and oil/offshore routing passed')
            page.close()
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8768/')
    verify(parser.parse_args().url)

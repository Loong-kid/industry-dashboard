"""Exercise gas tabs, all financial views, operating tables and sticky controls."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def verify(base):
    output=ROOT/'tmp/natgas';output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in [1440,390]:
            page=browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width==390 else 'light')
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base+'#/natgas/midstream')
            page.wait_for_function('typeof state!=="undefined" && state.subtab==="midstream" && state.charts.length===30 && !document.querySelector(".page-loading")')
            assert '미드스트림' in page.locator('#page-title').inner_text()
            assert page.locator('#content .is-error').count()==0
            assert page.locator('#refresh-btn').is_visible()
            assert page.locator('#refresh-label').inner_text()=='미드스트림 실적 확인'
            page.screenshot(path=str(output/f'midstream-top-{width}.png'))
            financial=page.locator('#content .card.ir-chart').filter(has=page.get_by_role('button',name='연간',exact=True))
            assert financial.count()==24
            for i in range(financial.count()):
                financial.nth(i).get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(chart=>chart.data.datasets.some(dataset=>dataset.data.some(value=>value!==null)))')
            first=financial.first
            first.get_by_role('button',name='표 보기',exact=True).click()
            assert '2014' in first.locator('tbody').inner_text()
            assert first.locator('tbody a[href^="https://www.sec.gov/"]').count()>0
            for i in range(financial.count()):
                financial.nth(i).get_by_role('button',name='분기',exact=True).click()
            ar=page.locator('.card').filter(has=page.locator('.card-name',has_text='Archrock · AROC · 압축기 가용·가동 마력')).first
            ar.scroll_into_view_if_needed();page.screenshot(path=str(output/f'compression-{width}.png'))
            for company in ['Archrock · AROC','Kodiak Gas Services · KGS','USA Compression · USAC']:
                card=page.locator('.card').filter(has=page.locator('.card-name',has_text=company+' · 압축기 가용·가동 마력')).first
                assert card.get_by_role('button',name='연간',exact=True).count()==0
                card.get_by_role('button',name='표 보기',exact=True).click()
                assert card.locator('tbody a[href^="https://www.sec.gov/"]').count()>0
            assert page.evaluate('state.charts.length')==30
            assert page.evaluate('Object.keys(Chart.instances).length')==30
            page.evaluate('scrollTo(0,1500)');before=page.evaluate('scrollY')
            box=page.locator('#range-picker [data-range="1y"]').bounding_box()
            page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
            page.wait_for_function('state.range==="1y" && state.charts.length===30 && !document.querySelector(".page-loading")')
            assert abs(page.evaluate('scrollY')-before)<30
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.goto(base+'#/natgas')
            page.wait_for_function('state.subtab==="overview" && !document.querySelector(".page-loading")')
            assert page.locator('#page-tabs a.active').inner_text()=='가격·LNG'
            assert page.locator('#refresh-label').inner_text()=='천연가스 갱신'
            assert page.locator('#content .is-error').count()==0
            assert page.evaluate('state.charts.length')>5
            page.screenshot(path=str(output/f'gas-prices-{width}.png'))
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not errors,errors
            print(width,'30 charts, 24 annual/quarter views, HP sources, sticky range and legacy gas route passed')
            page.close()
        browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8767/')
    verify(parser.parse_args().url)

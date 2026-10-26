"""Check nested midstream views, financial controls and sticky ranges in Chrome."""
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
            def wait(view):
                page.wait_for_function('(view)=>typeof state!=="undefined" && state.subtab==="midstream" && state.natgasView===view && state.charts.length===15 && !document.querySelector(".page-loading")',arg=view)
                assert page.locator('#content .is-error').count()==0
                assert page.evaluate('Object.keys(Chart.instances).length')==15
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.goto(base+'#/natgas/midstream');wait('summary')
            for view,label,financial_count in [('summary','전체 요약',15),('compression','압축기',9)]:
                if view=='compression':
                    page.get_by_role('navigation',name='미드스트림 분류').get_by_role('link',name=label,exact=True).click()
                    wait(view)
                assert page.get_by_role('navigation',name='미드스트림 분류').locator('[aria-current="page"]').inner_text()==label
                assert page.locator('#page-title').inner_text()=='천연가스 · 미드스트림 · '+label
                assert page.locator('#refresh-label').inner_text()==('압축기 실적 확인' if view=='compression' else '미드스트림 실적 확인')
                assert page.locator('#refresh-btn').is_visible()
                names=page.locator('.card-name').all_text_contents()
                if view=='summary':
                    assert any('KMI' in name for name in names)
                    assert not any('AROC' in name or 'KGS' in name or 'USAC' in name for name in names)
                else:
                    assert not any('KMI' in name or 'WMB' in name for name in names)
                    assert '2023년 6월 상장' in page.locator('.tab-description').inner_text()
                financial=page.locator('#content .card.ir-chart').filter(has=page.get_by_role('button',name='연간',exact=True))
                assert financial.count()==financial_count
                for i in range(financial.count()):financial.nth(i).get_by_role('button',name='연간',exact=True).click()
                assert page.evaluate('state.charts.every(chart=>chart.data.datasets.some(dataset=>dataset.data.some(value=>value!==null)))')
                first=financial.first;first.get_by_role('button',name='표 보기',exact=True).click()
                assert '2014' in first.locator('tbody').inner_text()
                assert first.locator('tbody a[href^="https://www.sec.gov/"]').count()>0
                for i in range(financial.count()):financial.nth(i).get_by_role('button',name='분기',exact=True).click()
                page.evaluate('scrollTo(0,0)');page.screenshot(path=str(output/f'{view}-{width}.png'))
            for company in ['Archrock · AROC','Kodiak Gas Services · KGS','USA Compression · USAC']:
                card=page.locator('.card').filter(has=page.locator('.card-name',has_text=company+' · 압축기 가용·가동 마력')).first
                assert card.get_by_role('button',name='연간',exact=True).count()==0
                card.get_by_role('button',name='표 보기',exact=True).click()
                assert card.locator('tbody a[href^="https://www.sec.gov/"]').count()>0
            page.evaluate('scrollTo(0,1500)');before=page.evaluate('scrollY')
            box=page.locator('#range-picker [data-range="1y"]').bounding_box()
            page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
            page.wait_for_function('state.range==="1y" && state.charts.length===15 && !document.querySelector(".page-loading")')
            assert abs(page.evaluate('scrollY')-before)<30
            page.reload();wait('compression')
            page.get_by_role('navigation',name='미드스트림 분류').get_by_role('link',name='전체 요약',exact=True).click();wait('summary')
            page.go_back();wait('compression')
            page.goto(base+'#/natgas/midstream/invalid');wait('summary')
            page.goto(base+'#/natgas')
            page.wait_for_function('state.subtab==="overview" && !document.querySelector(".page-loading")')
            assert page.locator('#page-tabs a.active').inner_text()=='가격·LNG'
            assert page.get_by_role('navigation',name='미드스트림 분류').count()==0
            assert page.locator('#refresh-label').inner_text()=='천연가스 갱신'
            assert page.locator('#content .is-error').count()==0
            assert not errors,errors
            print(width,'summary/compression split, 24 financial views, HP sources, direct routes, history and sticky range passed')
            page.close()
        browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8767/')
    verify(parser.parse_args().url)

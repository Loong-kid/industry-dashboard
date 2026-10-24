"""Check nested semiconductor navigation and sticky range controls in Chrome."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def verify(base):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome',headless=True)
        for width in [1440,390]:
            page = browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width==390 else 'light')
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            def open_route(route,count):
                page.goto(base+route)
                parts=route.split('/')
                expected=parts[3] if len(parts)>3 and parts[2]=='materials' else parts[2] if len(parts)>2 else 'memory'
                page.wait_for_function('(tab)=>typeof state!=="undefined" && state.catalog && state.subtab===tab && !document.querySelector(".page-loading")',arg=expected)
                page.wait_for_function('(n)=>state.charts.length===n',arg=count)
                assert page.locator('#content .is-error').count()==0,route
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),route
            for route,count,title in [('#/semicon',9,'메모리'),('#/semicon/foundry',12,'파운드리'),('#/semicon/cpu',21,'CPU'),('#/semicon/ssd',6,'SSD')]:
                open_route(route,count)
                assert title in page.locator('#page-title').inner_text()
                assert page.locator('.semicon-groups a').all_text_contents()==['메모리','파운드리','CPU','SSD','소부장']
                assert page.locator('#page-tabs .commodity-tabs').count()==1
                assert '반도체 소부장' not in page.locator('#nav').inner_text()
                cards=page.locator('#content .card.ir-chart')
                for i in range(count):
                    cards.nth(i).get_by_role('button',name='연간',exact=True).click()
                assert page.evaluate('state.charts.every(chart=>chart.data.datasets.some((dataset,i)=>chart.isDatasetVisible(i) && dataset.data.some(value=>value!==null)))'),route
                assert page.evaluate('Object.keys(Chart.instances).length')==count
                if title=='CPU':
                    apple=page.evaluate('state.charts.find(chart=>chart.canvas.closest(".card").querySelector(".card-name").textContent==="Apple · 매출").data')
                    annual_values=dict(zip(apple['labels'],apple['datasets'][0]['data']))
                    assert annual_values['2025-09-27']==416161
                for i in range(count):
                    cards.nth(i).get_by_role('button',name='분기',exact=True).click()
            open_route('#/semicon/memory',9)
            assert page.locator('.section-title').all_text_contents()==['삼성전자 · 실적','SK하이닉스 · 실적','Micron · 실적']
            # Three-column financial groups are shorter on wide screens.
            # Exercise the sticky header away from the document's bottom clamp.
            page.evaluate('window.scrollTo(0,Math.min(800,(document.documentElement.scrollHeight-innerHeight)/2))')
            page.wait_for_function('scrollY>100')
            before=page.evaluate('scrollY')
            # Click the pinned control as a user would. Locator.click's automatic
            # scrollIntoView can scroll a sticky header to its normal-flow position.
            box=page.locator('#range-picker button[data-range="1y"]').bounding_box()
            page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
            page.wait_for_function('state.range==="1y" && state.charts.length===9 && !document.querySelector(".page-loading") && document.querySelector("#content").style.minHeight===""')
            page.wait_for_function('(y)=>Math.abs(scrollY-y)<25',arg=before)
            assert abs(page.locator('.dashboard-header').bounding_box()['y'])<1
            assert page.locator('#range-picker').is_visible()
            box=page.locator('#range-picker button[data-range="all"]').bounding_box()
            page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
            page.wait_for_function('state.range==="all" && state.charts.length===9 && !document.querySelector(".page-loading")')
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(ROOT/f'tmp/semicon-20261014/memory-{width}.png'))
            for route,count,leaf in [('#/semicon/materials/snstech',73,'포토마스크'),('#/semicon/snstech',73,'포토마스크'),
                                     ('#/semicon/materials/esc',6,'정전척'),('#/semicon/esc',6,'정전척'),
                                     ('#/semicon/materials/mocvd',23,'MOCVD'),('#/semicon/mocvd',23,'MOCVD'),
                                     ('#/semicon/materials/wafer',16,'실리콘 웨이퍼'),('#/semicon/wafer',16,'실리콘 웨이퍼')]:
                open_route(route,count)
                assert '소부장' in page.locator('#page-title').inner_text()
                assert leaf in page.locator('#page-title').inner_text()
                assert page.locator('.semicon-groups .active').inner_text()=='소부장'
                assert page.locator('#page-tabs .commodity-tabs').count()==2
            for route in ['#/semicon/materials/snstech/ir','#/semicon/snstech/ir']:
                page.goto(base+route)
                page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
                assert page.locator('.pm-periods button').count()==22
                assert not page.locator('#range-picker').is_visible()
                assert page.locator('.photomask-views [aria-current="page"]').get_attribute('href')=='#/semicon/materials/snstech/ir'
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                assert page.locator('.dashboard-header').bounding_box()['height']<300
            assert not errors,errors
            page.close()
        browser.close()
    print('Nested routes, 27 financial charts, legacy materials, IR reader, mobile and sticky range controls verified')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8765/')
    verify(parser.parse_args().url)

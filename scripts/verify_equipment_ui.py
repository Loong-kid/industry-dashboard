"""Exercise category navigation, legacy links and all equipment financial charts."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,768,390,320):
            page=browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width in (768,390) else 'light')
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def settled(tab,count):
                page.wait_for_function('(args)=>typeof state!=="undefined" && state.subtab===args[0] && state.charts.length===args[1] && !document.querySelector(".page-loading")',arg=[tab,count])
                assert not page.locator('#content .is-error').count()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.goto(base+'#/semicon/materials',wait_until='networkidle')
            settled('equipment_summary',9)
            assert page.locator('.semicon-categories a').all_text_contents()==['장비','부품','소재']
            assert page.locator('.semicon-categories .active').inner_text()=='장비'
            assert page.locator('.semicon-material-tabs a').all_text_contents()==['요약','MOCVD']
            assert page.locator('.section-title').all_text_contents()==['Lam Research · LRCX · 실적','Applied Materials · AMAT · 실적','KLA · KLAC · 실적']
            assert page.locator('#page-title').inner_text()=='반도체 · 소부장 · 장비 · 요약'
            assert page.locator('.refresh-wrap').is_visible()
            assert page.evaluate('currentTarget().workflow')=='update-equipment.yml'
            assert page.evaluate('Object.keys(Chart.instances).length')==9
            cards=page.locator('#content .card.ir-chart')
            assert cards.count()==9
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some(d=>d.data.filter(v=>v!==null).length>=50))')
            if width==1440:
                boxes=[cards.nth(i).bounding_box() for i in range(3)]
                assert max(box['y'] for box in boxes)-min(box['y'] for box in boxes)<1
            for i in range(9):cards.nth(i).get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some(d=>d.data.filter(v=>v!==null).length>=12))')
            values=page.evaluate('state.charts.map(c=>({name:c.canvas.closest(".card").querySelector(".card-name").textContent,labels:c.data.labels,values:c.data.datasets[0].data}))')
            kla=next(v for v in values if v['name']=='KLA · KLAC · 영업이익')
            assert abs(dict(zip(kla['labels'],kla['values']))['2026-06-30']-5660.78)<.001
            for i in range(9):cards.nth(i).get_by_role('button',name='분기',exact=True).click()
            page.evaluate('window.scrollTo(0,0)')
            out=ROOT/'tmp/equipment-20261025';out.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(out/f'summary-{width}.png'))
            page.locator('.semicon-material-tabs').get_by_role('link',name='MOCVD',exact=True).click()
            settled('mocvd',23)
            assert page.locator('.semicon-categories .active').inner_text()=='장비'
            page.locator('.semicon-categories').get_by_role('link',name='부품',exact=True).click()
            settled('snstech',73)
            assert page.locator('.semicon-material-tabs a').all_text_contents()==['블랭크마스크','정전척 ESC']
            page.locator('.semicon-material-tabs').get_by_role('link',name='정전척 ESC',exact=True).click()
            settled('esc',6)
            page.locator('.semicon-categories').get_by_role('link',name='소재',exact=True).click()
            settled('wafer',16)
            assert page.locator('.semicon-material-tabs a').all_text_contents()==['실리콘 웨이퍼']
            page.locator('.semicon-categories').get_by_role('link',name='장비',exact=True).click()
            settled('equipment_summary',9)
            page.go_back();settled('wafer',16)
            page.go_forward();settled('equipment_summary',9)
            page.goto(base+'#/semicon/materials/components/snstech/ir',wait_until='networkidle')
            page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
            assert page.locator('.semicon-categories .active').inner_text()=='부품'
            assert not page.locator('#range-picker').is_visible()
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert page.locator('.dashboard-header').bounding_box()['height']<330
            assert not errors,errors
            page.close()
        browser.close()
    print('Equipment: 4 viewports, 3 categories, 9 quarterly/annual charts, fields, history and IR navigation verified')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

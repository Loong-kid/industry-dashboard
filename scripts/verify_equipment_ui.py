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
            page.goto(base+'#/semicon/materials',wait_until='domcontentloaded')
            settled('equipment_summary',39)
            assert page.locator('.semicon-categories a').all_text_contents()==['장비','부품','소재']
            assert page.locator('.semicon-categories .active').inner_text()=='장비'
            assert page.locator('.semicon-material-tabs a').all_text_contents()==['전체 요약','전공정','패키징·후공정','검사·계측','테스트']
            assert page.locator('.section-title').count()==13
            assert page.locator('#page-title').inner_text()=='반도체 · 소부장 · 장비 · 전체 요약'
            assert page.locator('.refresh-wrap').is_visible()
            assert page.evaluate('currentTarget().workflow')=='update-equipment.yml'
            assert page.evaluate('Object.keys(Chart.instances).length')==39
            cards=page.locator('#content .card.ir-chart')
            assert cards.count()==39
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some(d=>d.data.filter(v=>v!==null).length>=2))')
            if width==1440:
                boxes=[cards.nth(i).bounding_box() for i in range(3)]
                assert max(box['y'] for box in boxes)-min(box['y'] for box in boxes)<1
            for i in range(39):cards.nth(i).get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some(d=>d.data.filter(v=>v!==null).length>=2))')
            values=page.evaluate('state.charts.map(c=>({name:c.canvas.closest(".card").querySelector(".card-name").textContent,labels:c.data.labels,values:c.data.datasets[0].data}))')
            kla=next(v for v in values if v['name']=='KLA · KLAC · 영업이익')
            assert abs(dict(zip(kla['labels'],kla['values']))['2026-06-30']-5660.78)<.001
            for i in range(39):
                button=cards.nth(i).get_by_role('button',name='분기',exact=True)
                if button.count():button.click()
            page.evaluate('window.scrollTo(0,0)')
            out=ROOT/'tmp/equipment-20261025';out.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(out/f'summary-{width}.png'))
            for label,tab,count in [('전공정','equipment_frontend',21),('패키징·후공정','equipment_packaging',11),('검사·계측','equipment_inspection',6),('테스트','equipment_testing',6)]:
                page.locator('.semicon-material-tabs').get_by_role('link',name=label,exact=True).click()
                settled(tab,count)
                assert page.evaluate('Object.keys(Chart.instances).length')==count
                assert page.evaluate('currentTarget().workflow')=='update-equipment.yml'
            page.locator('.semicon-material-tabs').get_by_role('link',name='전공정',exact=True).click()
            settled('equipment_frontend',21)
            page.locator('.semicon-equipment-views').get_by_role('link',name='MOCVD · 수요·공급',exact=True).click()
            settled('mocvd',23)
            assert page.locator('.semicon-material-tabs .active').inner_text()=='전공정'
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
            settled('equipment_summary',39)
            page.go_back();settled('wafer',16)
            page.go_forward();settled('equipment_summary',39)
            page.goto(base+'#/semicon/materials/components/snstech/ir',wait_until='networkidle')
            page.wait_for_selector('.pm-translation-body[aria-busy="false"]')
            assert page.locator('.semicon-categories .active').inner_text()=='부품'
            assert not page.locator('#range-picker').is_visible()
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert page.locator('.dashboard-header').bounding_box()['height']<330
            assert not errors,errors
            page.close()
        browser.close()
    print('Equipment: 4 viewports, 13 companies / 39 quarterly-annual charts, 4 fields, MOCVD, legacy and IR navigation verified')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

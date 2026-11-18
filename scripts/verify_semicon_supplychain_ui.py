"""Real-browser verification of supplier routes, tables and financial views."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
ROUTES=[('process_chemicals','raw_materials/chemicals',4),('specialty_gases','raw_materials/gases',2),
 ('test_components','components/test-components',3),('package_substrates','components/package-substrates',2),
 ('equipment_infrastructure','equipment/infrastructure',2),('equipment_frontend','equipment/frontend',2),
 ('equipment_testing','equipment/testing',3),('equipment_inspection','equipment/inspection',2)]


def verify(base):
    out=ROOT/'tmp/supplychain/ui';out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,390):
            for theme in ('light','dark'):
                page=browser.new_page(viewport={'width':width,'height':1000},color_scheme=theme)
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                for tab,route,count in ROUTES:
                    page.goto(base+'#/semicon/materials/'+route,wait_until='networkidle')
                    if page.locator('#site-gate').count():
                        page.evaluate("() => {if(window.SITE_GATE)localStorage.setItem('site_gate_pass',window.SITE_GATE.hash)}")
                        page.reload(wait_until='networkidle')
                    page.wait_for_function('(tab)=>state.subtab===tab && !document.querySelector(".page-loading")',arg=tab)
                    table=page.locator('.supplychain-overview')
                    expect(table).to_be_visible()
                    assert table.locator('tbody tr').count()==count,(tab,table.locator('tbody tr').count())
                    assert not page.locator('#content .is-error').count(),tab
                    rows=table.locator('tbody tr')
                    for i in range(count):
                        row=rows.nth(i)
                        assert row.locator('td').nth(2).inner_text().strip()!='—'
                        row.locator('summary').click()
                        assert row.locator('details a').count()>=2
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),(width,tab)
                    if tab in ('process_chemicals','specialty_gases','test_components','package_substrates','equipment_infrastructure'):
                        assert page.evaluate('currentTarget().workflow')=='update-semicon-supplychain.yml'
                    cards=page.locator('#content .card.ir-chart')
                    assert cards.count()>=3*count,(tab,cards.count())
                    if width==1440 and theme=='light':
                        for i in range(cards.count()):
                            annual=cards.nth(i).get_by_role('button',name='연간',exact=True)
                            if annual.count():annual.click()
                        assert page.evaluate('state.charts.filter(c=>c.canvas.closest(".ir-chart")).every(c=>c.data.datasets.some(d=>d.data.filter(v=>v!==null).length>=2))')
                    page.evaluate('scrollTo(0,0)')
                    if tab in ('process_chemicals','test_components','equipment_infrastructure'):
                        page.screenshot(path=str(out/f'{tab}-{width}-{theme}.png'))
                assert not errors,errors
                page.close()
                print('PASS',width,theme,'eight routes, business snapshots, quarterly/annual cards and refresh workflows',flush=True)
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8804/')
    verify(parser.parse_args().url)

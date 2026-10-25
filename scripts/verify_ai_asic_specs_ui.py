"""Exercise real table state, original readback, mobile geometry and route controls."""
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
            page.goto(base+'#/semicon/ai_asic',wait_until='networkidle')
            card=page.locator('[data-asic-specs="ai_asic_specs"]')
            card.locator('tbody tr').first.wait_for()
            assert page.locator('#page-title').inner_text()=='반도체 · AI ASIC'
            assert not page.locator('#range-picker').is_visible()
            assert not page.locator('.refresh-wrap').is_visible()
            assert page.evaluate('state.charts.length')==0
            assert card.locator('tbody tr').count()==33
            assert card.locator('tbody tr').first.get_attribute('data-row-id')=='asic-sheet-37'
            assert card.locator('thead th').nth(1).get_attribute('data-column')=='date'
            assert card.locator('thead th').last.inner_text()=='상세'
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            heights=card.locator('tbody tr').evaluate_all('rows=>rows.map(r=>r.getBoundingClientRect().height)')
            assert all(abs(v-40)<.1 for v in heights),heights
            for company,count in [('Google',9),('AWS',8),('Meta',2),('Microsoft',4),('Huawei',5),('Intel',2),('Baidu',3)]:
                card.get_by_label('AI ASIC 기업',exact=True).select_option(company)
                assert card.locator('tbody tr').count()==count,(company,count)
            card.get_by_role('button',name='초기화',exact=True).click()
            assert card.locator('[data-row-id="asic-sheet-56"] [data-column="company"]').count()==0
            card.get_by_label('AI ASIC 검색',exact=True).fill('Trainium 3')
            assert card.locator('tbody tr').count()==1
            assert card.locator('[data-column="date"] .cpu-specs-value').inner_text()=='2025-12-02'
            assert card.locator('[data-column="capacity"] .cpu-specs-value').inner_text()=='144 GB'
            assert card.locator('[data-column="foundry"] .cpu-specs-value').inner_text()=='—'
            card.get_by_label('AI ASIC 열 보기',exact=True).select_option('performance')
            assert card.locator('[data-column="bandwidth"] .cpu-specs-value').inner_text()=='4.9 TB/s'
            card.get_by_role('button',name='Trainium 3 상세 사양',exact=True).click()
            assert card.locator('dialog').is_visible()
            assert '시트 원본: 216' in card.locator('dialog').inner_text()
            card.locator('.specs-raw-row summary').click()
            raw=card.locator('.specs-raw-row dl').evaluate('el=>Object.fromEntries([...el.children].map(d=>[d.querySelector("dt").textContent,d.querySelector("dd").textContent]))')
            assert raw['H49']=='216' and raw['E49']=='2026'
            assert card.locator('dialog a[href^="https://aws.amazon.com/"]').count()>0
            card.get_by_role('button',name='AI ASIC 상세 닫기',exact=True).click()
            card.get_by_label('AI ASIC 값 표시',exact=True).select_option('original')
            assert card.locator('[data-column="capacity"] .cpu-specs-value').inner_text()=='216'
            assert card.locator('[data-column="date"] .cpu-specs-value').inner_text()=='2026'
            card.get_by_role('button',name='초기화',exact=True).click()
            card.get_by_label('AI ASIC 열 보기',exact=True).select_option('all')
            assert card.locator('[data-row-id="asic-sheet-56"] [data-column="company"] .cpu-specs-value').inner_text()=='Microsoft'
            region=card.locator('.cpu-specs-scroll')
            left=card.locator('tbody th').first.bounding_box()['x']
            region.evaluate('el=>el.scrollLeft=600')
            assert abs(card.locator('tbody th').first.bounding_box()['x']-left)<1
            card.get_by_role('button',name='초기화',exact=True).click()
            cell=card.locator('[data-row-id="asic-sheet-41"] [data-column="name"] [data-field]').first
            cell.hover()
            assert card.locator('[role="tooltip"]').is_visible()
            assert 'TPU7x' in card.locator('[role="tooltip"]').inner_text()
            page.keyboard.press('Escape')
            page.mouse.move(0,0)
            page.evaluate('window.scrollTo(0,0)')
            out=ROOT/'tmp/ai-asic-20261025';out.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(out/f'asic-{width}.png'),full_page=True)
            assert not errors,errors
            assert not page.locator('.is-error').count()
            page.close()
        browser.close()
    print('AI ASIC: 4 viewports, source readback, filters, units, sticky names and detail verified')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

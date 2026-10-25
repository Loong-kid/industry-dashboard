"""Verify DDR/HBM source readback, units, filters, fixed rows and memory financials."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    docs={key:json.loads((ROOT/'data/semicon'/f'{key}_specs.json').read_text(encoding='utf8')) for key in ('ddr','hbm')}
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,768,390,320):
            page=browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width in (768,390) else 'light')
            errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
            page.goto(base+'#/semicon/memory',wait_until='networkidle')
            page.wait_for_function('typeof state!=="undefined" && state.charts.length===9 && !document.querySelector(".page-loading")')
            ddr=page.locator('[data-memory-specs="ddr_specs"]');hbm=page.locator('[data-memory-specs="hbm_specs"]')
            assert ddr.locator('tbody tr').count()==6
            assert hbm.locator('tbody tr').count()==15
            assert not hbm.locator('[data-row-id="hbm-sheet-29"]').count()
            assert hbm.locator('[data-row-id="hbm-sheet-39"]').count()==1
            assert ddr.locator('[data-row-id="ddr-sheet-16"] [data-column="bandwidth"] .cpu-specs-value').inner_text()=='25.6~51.2'
            def fixed(card):
                heights=card.locator('tbody tr').evaluate_all('rows=>rows.map(row=>row.getBoundingClientRect().height)')
                assert all(abs(v-40)<.1 for v in heights),heights
                assert card.locator('thead th').last.inner_text()=='상세'
            fixed(ddr);fixed(hbm)
            out=ROOT/'tmp/memory-specs-20261025';out.mkdir(parents=True,exist_ok=True)
            ddr.screenshot(path=str(out/f'ddr-{width}.png'));hbm.screenshot(path=str(out/f'hbm-{width}.png'))
            ddr.get_by_label('DDR 제품 단위',exact=True).select_option('공정 메모')
            ddr.get_by_label('DDR 열 보기',exact=True).select_option('process')
            assert ddr.locator('tbody tr').count()==12
            assert ddr.locator('[data-row-id="ddr-sheet-9"] [data-column="process_nm"] .cpu-specs-value').inner_text()=='26nm'
            fixed(ddr)
            ddr.get_by_role('button',name='초기화',exact=True).click()
            hbm.get_by_label('HBM 기업',exact=True).select_option('SK하이닉스')
            hbm.get_by_label('HBM 검색',exact=True).fill('HBM4')
            assert hbm.locator('tbody tr').count()==1
            assert hbm.locator('[data-column="bandwidth"] .cpu-specs-value').inner_text()=='>2000'
            hbm.get_by_role('button',name='HBM4 상세 사양',exact=True).click()
            expect(hbm.get_by_role('dialog')).to_be_visible()
            assert '시트 원본: 165' in hbm.locator('dialog').inner_text()
            assert '개발·양산 준비' in hbm.locator('dialog').inner_text()
            hbm.locator('.specs-raw-row summary').click()
            raw=hbm.locator('.specs-raw-row dl').evaluate('el=>Object.fromEntries([...el.children].map(div=>[div.querySelector("dt").textContent,div.querySelector("dd").textContent]))')
            assert raw['F27']=='165' and raw['K27']=='2048'
            hbm.get_by_role('button',name='HBM 상세 닫기',exact=True).click()
            hbm.get_by_role('button',name='초기화',exact=True).click()
            hbm.get_by_label('HBM 기업',exact=True).select_option('삼성전자')
            assert hbm.locator('tbody tr').count()==9
            hbm.get_by_label('HBM 검색',exact=True).fill('HBM3E_12H')
            assert hbm.locator('tbody tr').count()==1
            assert hbm.locator('[data-column="capacity"] .cpu-specs-value').inner_text()=='36 · 12H'
            hbm.get_by_role('button',name='초기화',exact=True).click()
            # Both sort directions leave unknown bandwidths last, including bounds/derived labels.
            for direction in range(2):
                hbm.locator('thead [data-sort="bandwidth"]').click()
                order=hbm.locator('tbody tr').evaluate_all('rows=>rows.map(row=>row.dataset.rowId)')
                assert order.index('hbm-sheet-22')<order.index('hbm-sheet-38') if direction==0 else order.index('hbm-sheet-22')>order.index('hbm-sheet-38')
                assert set(order[-1:])=={'hbm-sheet-31'}
            for key,card in [('ddr',ddr),('hbm',hbm)]:
                card.get_by_role('button',name='초기화',exact=True).click()
                card.get_by_label(f'{key.upper()} 제품 단위',exact=True).select_option('all')
                card.get_by_label(f'{key.upper()} 열 보기',exact=True).select_option('all')
                card.get_by_label(f'{key.upper()} 값 표시',exact=True).select_option('original')
                assert card.locator('tbody tr').count()==len(docs[key]['rows'])
                assert card.locator('.cpu-specs-added').count()==0
                actual=card.locator('tbody tr').evaluate_all('rows=>rows.map(row=>Object.fromEntries([...row.cells].filter(c=>c.dataset.column&&c.dataset.column!=="detail").map(c=>[c.dataset.column,c.dataset.column==="name"?c.querySelector("b").textContent:c.querySelector(".cpu-specs-value").textContent])))')
                expected=[{c['id']:r['original'].get(c['id']) or '—' for c in docs[key]['columns']} for r in docs[key]['rows']]
                assert actual==expected
                region=card.locator('.cpu-specs-scroll');region.evaluate('el=>{el.scrollLeft=900;el.scrollTop=80}')
                box=region.bounding_box();sticky=card.locator('thead .cpu-specs-name').bounding_box()
                assert abs(sticky['x']-box['x']-1)<2
                fixed(card)
                card.get_by_role('button',name='초기화',exact=True).click()
            hbm.get_by_label('HBM 검색',exact=True).fill('not-a-memory-xxxx')
            assert '조건에 맞는 제품이 없습니다' in hbm.locator('tbody').inner_text()
            hbm.get_by_role('button',name='초기화',exact=True).click()
            charts=page.locator('#content .card.ir-chart')
            assert charts.count()==9
            for i in range(9):charts.nth(i).get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some((d,i)=>c.isDatasetVisible(i)&&d.data.some(v=>v!==null)))')
            assert not page.locator('.is-error').count()
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not errors,errors
            print(f'PASS {width}px: DDR/HBM source readback, product/process filters, units/scope, fixed rows, sticky names, nine annual financial charts',flush=True)
            page.close()
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

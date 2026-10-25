"""Exercise the CPU worksheet table and retain the financial charts below it."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    doc=json.loads((ROOT/'data/semicon/cpu_specs.json').read_text(encoding='utf8'))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,768,390,320):
            page=browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width in (768,390) else 'light')
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base+'#/semicon/cpu',wait_until='networkidle')
            try:
                page.wait_for_function('typeof state!=="undefined" && state.charts.length===21 && !document.querySelector(".page-loading")')
            except Exception:
                print('CPU boot diagnostics:',page.evaluate('({title:document.title,route:location.hash,charts:typeof state!=="undefined"?state.charts.length:null,subtab:typeof state!=="undefined"?state.subtab:null,loading:document.querySelector(".page-loading")?.textContent,errors:[...document.querySelectorAll(".is-error")].map(el=>el.textContent)})'),errors,flush=True)
                raise
            table=page.locator('.cpu-specs')
            expect(table).to_be_visible()
            assert table.locator('tbody tr').count()==292
            assert table.locator('thead th').count()==14
            assert table.locator('thead th').last.get_attribute('data-column')=='detail'
            assert table.get_by_label('CPU 사양 열 보기',exact=True).input_value()=='overview'
            assert table.locator('.cpu-specs-scroll').evaluate('el=>el.scrollWidth>el.clientWidth')
            def fixed_rows():
                heights=table.locator('tbody tr').evaluate_all('rows=>rows.map(row=>row.getBoundingClientRect().height)')
                assert max(heights)-min(heights)<.1,heights[:10]
                assert all(abs(h-40)<.1 for h in heights),heights[:10]
            fixed_rows()
            m6=table.locator('tr[data-sheet-row="3"]')
            assert m6.locator('[data-column="process"] .cpu-specs-value').inner_text().startswith('TSMC N2')
            if width==1440:
                m6.locator('[data-column="process"] .cpu-specs-cell').hover()
                expect(table.locator('[role="tooltip"]')).to_be_visible()
                assert 'TSMC N2' in table.locator('[role="tooltip"]').inner_text()
                assert table.locator('[role="tooltip"] a[href="https://www.high-yield.net/m-series"]').count()==1
                page.keyboard.press('Escape')
            m6.get_by_role('button',name='M6 상세 사양',exact=True).click()
            expect(table.get_by_role('dialog')).to_be_visible()
            assert table.locator('dialog dt').count()==30
            assert not any(f'Geekbench {version}' in label for label in table.locator('dialog dt').all_text_contents() for version in (2,3,4,5))
            assert 'TSMC N2' in table.locator('dialog').inner_text()
            table.get_by_role('button',name='CPU 상세 닫기',exact=True).click()
            # Composition and all three caches are readable by scrolling the default view.
            sample=next(row for row in doc['rows'] if all(row['values'][i] for i in (8,18,19,20)))
            table.get_by_label('CPU 사양 검색',exact=True).fill(sample['values'][2])
            sample_row=table.locator(f'tr[data-sheet-row="{sample["sheet_row"]}"]')
            region=table.locator('.cpu-specs-scroll')
            region.focus()
            for key,index in (('composition',8),('architecture',12),('l1',18),('l2',19),('l3',20)):
                target=sample_row.locator(f'[data-column="{key}"] .cpu-specs-value')
                target.scroll_into_view_if_needed()
                expect(target).to_be_visible()
                assert target.inner_text()==(sample['values'][index] or '—')
                sticky=table.locator('thead [data-column="chip"]').bounding_box()
                assert abs(sticky['x']-region.bounding_box()['x']-1)<2
            if width>=768:
                page.mouse.move(0,0)
                memo_cell=sample_row.locator('[data-column="l3"] .cpu-specs-cell')
                memo_cell.scroll_into_view_if_needed()
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                memo_cell.hover(position=dict(x=12,y=18))
                expect(table.locator('[role="tooltip"]')).to_be_visible()
                assert sample['values'][20] in table.locator('[role="tooltip"]').inner_text()
                page.keyboard.press('Escape')
            fixed_rows()
            page.mouse.move(0,0)
            out=ROOT/'tmp/cpu-cache-20261025'
            out.mkdir(parents=True,exist_ok=True)
            table.screenshot(path=str(out/f'cpu-cache-scroll-{width}.png'))
            table.get_by_role('button',name='초기화',exact=True).click()
            assert table.locator('tbody tr').first.get_attribute('data-sheet-row')=='2'
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            # All displayed source values remain exact; historical GB2–5 stay in JSON.
            table.get_by_label('CPU 사양 값 표시',exact=True).select_option('original')
            table.get_by_label('CPU 사양 열 보기',exact=True).select_option('all')
            fixed_rows()
            assert table.locator('.cpu-specs-added').count()==0
            actual=table.locator('tbody tr').evaluate_all('rows=>rows.map(row=>[...row.cells].filter(cell=>cell.dataset.column!=="detail").map(cell=>cell.dataset.column==="AK"?(cell.querySelector("a")?.getAttribute("href")||""):cell.querySelector(".cpu-specs-value").textContent))')
            expected=[[(r['values'][i] or '—') if i!=36 else r['values'][i] for i in doc['display_indices']] for r in doc['rows']]
            assert actual==expected
            assert table.locator('thead th').last.get_attribute('data-column')=='detail'
            assert not any(f'Geekbench {version}' in label for label in table.locator('thead th').all_text_contents() for version in (2,3,4,5))
            table.get_by_label('CPU 사양 값 표시',exact=True).select_option('enriched')
            assert table.locator('.cpu-specs-added').count()==226
            table.get_by_label('CPU 사양 기업',exact=True).select_option('AMD')
            assert table.locator('tbody tr').count()==sum(r['values'][0]=='AMD' for r in doc['rows'])
            table.get_by_label('CPU 사양 검색',exact=True).fill('Ryzen 9 9950X')
            assert table.locator('tbody tr').count()==1
            table.get_by_label('CPU 사양 열 보기',exact=True).select_option('gb7')
            assert table.locator('thead th').count()==9
            assert table.locator('tbody [data-column="AH"] .cpu-specs-value').inner_text()=='3067'
            assert table.locator('tbody [data-column="AH"] a').get_attribute('href')=='https://browser.geekbench.com/processor-benchmarks'
            table.get_by_label('CPU 사양 값 표시',exact=True).select_option('original')
            assert table.locator('tbody [data-column="AH"] .cpu-specs-value').inner_text()=='—'
            table.get_by_role('button',name='초기화',exact=True).click()
            table.get_by_label('보완한 CPU만',exact=True).check()
            assert table.locator('tbody tr').count()==81
            table.get_by_label('CPU 사양 열 보기',exact=True).select_option('gb7')
            fixed_rows()
            # Numeric sorting keeps unknown scores at the end in both directions.
            table.get_by_role('button',name='Geekbench 7 Multi-Core').click()
            values=table.locator('tbody [data-column="AI"] .cpu-specs-value').all_text_contents()
            scores=[int(v.split()[0]) for v in values if v!='—']
            assert scores==sorted(scores,reverse=True)
            first_blank=next((i for i,v in enumerate(values) if v=='—'),len(values))
            assert all(v=='—' for v in values[first_blank:])
            table.get_by_role('button',name='Geekbench 7 Multi-Core').click()
            values=table.locator('tbody [data-column="AI"] .cpu-specs-value').all_text_contents()
            scores=[int(v.split()[0]) for v in values if v!='—']
            assert scores==sorted(scores)
            table.get_by_role('button',name='초기화',exact=True).click()
            table.get_by_label('CPU 사양 검색',exact=True).fill('not-a-cpu-xxxxxxxx')
            assert '조건에 맞는 CPU가 없습니다' in table.locator('tbody').inner_text()
            table.get_by_role('button',name='초기화',exact=True).click()
            table.get_by_label('CPU 사양 열 보기',exact=True).select_option('all')
            region=table.locator('.cpu-specs-scroll')
            region.evaluate('element=>{element.scrollLeft=800;element.scrollTop=900}')
            header=table.locator('thead [data-column="C"]').bounding_box()
            region_box=region.bounding_box()
            assert abs(header['y']-region_box['y']-1)<2
            assert abs(header['x']-region_box['x']-1)<2
            table.get_by_role('button',name='초기화',exact=True).click()
            region.evaluate('element=>{element.scrollLeft=0;element.scrollTop=0}')
            table.scroll_into_view_if_needed()
            out=ROOT/'tmp/cpu-cache-20261025'
            out.mkdir(parents=True,exist_ok=True)
            table.screenshot(path=str(out/f'cpu-specs-{width}.png'))
            financials=page.locator('#content .card.ir-chart')
            assert financials.count()==21
            financials.first.get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some((d,i)=>c.isDatasetVisible(i)&&d.data.some(v=>v!==null)))')
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not errors,errors
            print(f'PASS {width}px: horizontal CPU/cache comparisons, fixed 40px rows, tooltip/detail, TSMC, GB6/7 only, 30 source columns, financial charts')
            page.close()
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

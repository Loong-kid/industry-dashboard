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
            page.wait_for_function('typeof state!=="undefined" && state.charts.length===21 && !document.querySelector(".page-loading")')
            table=page.locator('.cpu-specs')
            expect(table).to_be_visible()
            assert table.locator('tbody tr').count()==292
            assert table.locator('thead th').count()==37
            assert table.locator('tbody tr').first.get_attribute('data-sheet-row')=='2'
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            # The source view retains all 292 rows and original cells exactly.
            table.get_by_label('CPU 사양 값 표시',exact=True).select_option('original')
            assert table.locator('.cpu-specs-added').count()==0
            actual=table.locator('tbody tr').evaluate_all('rows=>rows.map(row=>[...row.cells].map(cell=>cell.dataset.column==="AK"?(cell.querySelector("a")?.getAttribute("href")||""):cell.textContent))')
            expected=[[v if v else '—' for v in r['values'][:36]]+[r['values'][36]] for r in doc['rows']]
            assert actual==expected
            table.get_by_label('CPU 사양 값 표시',exact=True).select_option('enriched')
            assert table.locator('.cpu-specs-added').count()==226
            table.get_by_label('CPU 사양 기업',exact=True).select_option('AMD')
            assert table.locator('tbody tr').count()==sum(r['values'][0]=='AMD' for r in doc['rows'])
            table.get_by_label('CPU 사양 검색',exact=True).fill('Ryzen 9 9950X')
            assert table.locator('tbody tr').count()==1
            table.get_by_label('CPU 사양 열 보기',exact=True).select_option('gb7')
            assert table.locator('thead th').count()==8
            assert table.locator('tbody [data-column="AH"]').inner_text().startswith('3067')
            assert table.locator('tbody [data-column="AH"] a').get_attribute('href')=='https://browser.geekbench.com/processor-benchmarks'
            table.get_by_label('CPU 사양 값 표시',exact=True).select_option('original')
            assert table.locator('tbody [data-column="AH"]').inner_text()=='—'
            table.get_by_role('button',name='초기화',exact=True).click()
            table.get_by_label('보완한 CPU만',exact=True).check()
            assert table.locator('tbody tr').count()==81
            table.get_by_label('CPU 사양 열 보기',exact=True).select_option('gb7')
            # Numeric sorting keeps unknown scores at the end in both directions.
            table.get_by_role('button',name='Geekbench 7 Multi-Core').click()
            values=table.locator('tbody [data-column="AI"]').all_text_contents()
            scores=[int(v.split()[0]) for v in values if v!='—']
            assert scores==sorted(scores,reverse=True)
            first_blank=next((i for i,v in enumerate(values) if v=='—'),len(values))
            assert all(v=='—' for v in values[first_blank:])
            table.get_by_role('button',name='Geekbench 7 Multi-Core').click()
            values=table.locator('tbody [data-column="AI"]').all_text_contents()
            scores=[int(v.split()[0]) for v in values if v!='—']
            assert scores==sorted(scores)
            table.get_by_role('button',name='초기화',exact=True).click()
            table.get_by_label('CPU 사양 검색',exact=True).fill('not-a-cpu-xxxxxxxx')
            assert '조건에 맞는 CPU가 없습니다' in table.locator('tbody').inner_text()
            table.get_by_role('button',name='초기화',exact=True).click()
            region=table.locator('.cpu-specs-scroll')
            region.evaluate('element=>{element.scrollLeft=800;element.scrollTop=900}')
            header=table.locator('thead [data-column="C"]').bounding_box()
            region_box=region.bounding_box()
            assert abs(header['y']-region_box['y']-1)<2
            assert abs(header['x']-region_box['x']-(241 if width>=1024 else 1))<2
            region.evaluate('(element,width)=>{element.scrollLeft=width<=600?240:0;element.scrollTop=0}',width)
            table.scroll_into_view_if_needed()
            out=ROOT/'tmp/cpu-specs-20261025'
            out.mkdir(parents=True,exist_ok=True)
            table.screenshot(path=str(out/f'cpu-specs-{width}.png'))
            financials=page.locator('#content .card.ir-chart')
            assert financials.count()==21
            financials.first.get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some((d,i)=>c.isDatasetVisible(i)&&d.data.some(v=>v!==null)))')
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not errors,errors
            print(f'PASS {width}px: 292 source rows, 37 columns, 226 sourced fills, filters, numeric sort, sticky headers, financial charts')
            page.close()
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

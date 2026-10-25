"""Check actual GPU filters, source readback, precision context and fixed rows."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    doc=json.loads((ROOT/'data/semicon/gpu_specs.json').read_text(encoding='utf8'))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,768,390,320):
            page=browser.new_page(viewport=dict(width=width,height=1000),color_scheme='dark' if width in (768,390) else 'light')
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base+'#/semicon/gpu',wait_until='networkidle')
            page.wait_for_selector('.gpu-specs[data-gpu-specs="nvidia_ai_specs"] tbody tr')
            assert not page.locator('.is-error').count()
            assert page.locator('#page-title').inner_text()=='반도체 · GPU'
            assert not page.locator('#range-picker').is_visible()
            assert not page.locator('.refresh-wrap').is_visible()
            general=page.locator('[data-gpu-specs="gpu_specs"]');ai=page.locator('[data-gpu-specs="nvidia_ai_specs"]')
            assert general.locator('tbody tr').count()==40
            assert ai.get_by_label('AI 가속기 제품 단위',exact=True).input_value()=='GPU 모듈'
            def fixed_rows(card):
                heights=card.locator('tbody tr').evaluate_all('rows=>rows.map(row=>row.getBoundingClientRect().height)')
                assert all(abs(h-40)<.1 for h in heights),heights
                assert card.locator('thead th').last.inner_text()=='상세'
            fixed_rows(general);fixed_rows(ai)
            # FLOPS sorting converts PFLOPS/TFLOPS and ignores unverified D/S data.
            ai.get_by_role('button',name='FP16/BF16 · Dense / Sparse').click()
            ai.get_by_role('button',name='FP16/BF16 · Dense / Sparse').click()
            assert ai.locator('tbody tr').first.locator('[data-column="fp16"] .cpu-specs-value').inner_text()=='4 PFLOPS · Dense'
            ordered=ai.locator('tbody tr').evaluate_all('rows=>rows.map(row=>row.dataset.rowId)')
            assert ordered.index('ai-sheet-13')<ordered.index('ai-sheet-10')
            ai.get_by_role('button',name='초기화',exact=True).click()
            general.get_by_label('GPU 열 보기',exact=True).select_option('benchmarks')
            general.get_by_label('GPU 기업',exact=True).select_option('NVIDIA')
            general.get_by_label('GPU 검색',exact=True).fill('GeForce RTX 5090')
            assert general.locator('tbody tr').count()==2
            assert general.locator('[data-row-id="gpu-sheet-24"] [data-column="gb7_opencl"] .cpu-specs-value').inner_text()=='369,574'
            general.get_by_role('button',name='GB7 · OpenCL').click()
            assert general.locator('tbody tr').first.get_attribute('data-row-id')=='gpu-sheet-24'
            general.get_by_role('button',name='GB7 · OpenCL').click()
            assert general.locator('tbody tr').first.get_attribute('data-row-id')=='gpu-sheet-29'
            general.get_by_role('button',name='GeForce RTX 5090 상세 사양',exact=True).click()
            expect(general.get_by_role('dialog')).to_be_visible()
            assert '장치명' in general.locator('dialog').inner_text()
            assert general.locator('dialog a[href="https://browser.geekbench.com/opencl-benchmarks"]').count()==1
            general.get_by_role('button',name='GPU 상세 닫기',exact=True).click()
            general.get_by_role('button',name='초기화',exact=True).click()
            general.get_by_label('GPU 값 표시',exact=True).select_option('original')
            general.get_by_label('GPU 열 보기',exact=True).select_option('all')
            actual=general.locator('tbody tr').evaluate_all('rows=>rows.map(row=>[...row.cells].slice(0,26).map(cell=>cell.dataset.column==="C"?cell.querySelector("b").textContent:["Y","Z"].includes(cell.dataset.column)?(cell.querySelector("a")?.getAttribute("href")||""):cell.querySelector(".cpu-specs-value").textContent))')
            expected=[[(v or '—') if i<24 else v for i,v in enumerate(row['source_values'])] for row in doc['rows']]
            assert actual==expected
            assert general.locator('.cpu-specs-added').count()==0
            general.get_by_role('button',name='초기화',exact=True).click()
            general.get_by_label('GPU 검색',exact=True).fill('not-a-gpu-xxxxxxxx')
            assert '조건에 맞는 제품이 없습니다' in general.locator('tbody').inner_text()
            general.get_by_role('button',name='초기화',exact=True).click()
            ai.get_by_label('AI 가속기 검색',exact=True).fill('H200')
            assert ai.locator('tbody tr').count()==1
            assert ai.locator('tbody [data-column="bandwidth"] .cpu-specs-value').inner_text()=='4.8 TB/s'
            ai.get_by_role('button',name='H200 SXM 상세 사양',exact=True).click()
            text=ai.locator('dialog').inner_text()
            assert '4.8 TB/s' in text and '시트 원본: 4.8GB/s' in text
            assert '989.5 / 1979 TFLOPS' in text
            ai.get_by_role('button',name='AI 가속기 상세 닫기',exact=True).click()
            ai.get_by_label('AI 가속기 값 표시',exact=True).select_option('original')
            assert ai.locator('tbody [data-column="bandwidth"] .cpu-specs-value').inner_text()=='4.8GB/s'
            ai.get_by_role('button',name='초기화',exact=True).click()
            ai.get_by_label('AI 가속기 제품 단위',exact=True).select_option('랙')
            assert ai.locator('tbody tr').count()==5
            assert 'DGX GB200' in ai.locator('tbody').inner_text()
            fixed_rows(ai)
            ai.get_by_label('AI 가속기 제품 단위',exact=True).select_option('네트워크')
            assert ai.locator('tbody tr').count()==5
            assert ai.locator('thead [data-column="network"]').count()==1
            assert ai.locator('thead [data-column="fp4"]').count()==0
            ai.get_by_label('AI 가속기 제품 단위',exact=True).select_option('all')
            assert ai.locator('tbody tr').count()==34
            ai.get_by_label('AI 가속기 값 표시',exact=True).select_option('original')
            assert ai.locator('tbody tr').count()==30
            ai.get_by_role('button',name='초기화',exact=True).click()
            for card in (general,ai):
                region=card.locator('.cpu-specs-scroll')
                region.evaluate('el=>{el.scrollLeft=900;el.scrollTop=120}')
                sticky=card.locator('thead .cpu-specs-name').bounding_box();bounds=region.bounding_box()
                assert abs(sticky['x']-bounds['x']-1)<2
                fixed_rows(card)
            page.mouse.move(0,0)
            out=ROOT/'tmp/gpu-specs-20261025';out.mkdir(parents=True,exist_ok=True)
            general.screenshot(path=str(out/f'gpu-{width}.png'))
            ai.screenshot(path=str(out/f'ai-{width}.png'))
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert page.evaluate('state.charts.length')==0
            assert not errors,errors
            print(f'PASS {width}px: GPU scores/source cells, AI product units/Dense-Sparse, fixed rows, sticky name, details',flush=True)
            page.close()
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8792/')
    verify(parser.parse_args().url)

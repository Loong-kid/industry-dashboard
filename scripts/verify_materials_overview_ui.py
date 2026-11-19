"""Exercise the materials directory, its filters and existing company routes."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    industry=next(i for i in json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))['industries'] if i['id']=='semicon')
    tabs={t['id']:t for t in industry['tabs'] if t['category']!='overview'}
    registered=json.loads((ROOT/'manual/semicon-valuation/companies.json').read_text(encoding='utf-8'))
    companies=[c for c in registered if set(c['tabs'])&set(tabs)]
    expected=len(companies)
    out=ROOT/'tmp/materials-overview/ui';out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,390):
            for theme in ('light','dark'):
                page=browser.new_page(viewport={'width':width,'height':1000},color_scheme=theme)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'#/semicon/materials',wait_until='networkidle')
                if page.locator('#site-gate').count():
                    page.evaluate("() => {if(window.SITE_GATE)localStorage.setItem('site_gate_pass',window.SITE_GATE.hash)}")
                    page.reload(wait_until='networkidle')
                directory=page.get_by_role('region',name='소부장 전체 요약과 등재 기업',exact=True)
                expect(directory).to_be_visible(timeout=30000)
                rows=directory.locator('tbody tr[data-company-id]')
                expect(rows).to_have_count(expected)
                assert page.evaluate('state.subtab')=='materials_overview'
                assert page.evaluate('state.materialCategory')=='overview'
                assert page.evaluate('state.charts.length')==0
                assert page.evaluate('currentTarget().workflow')=='update-semicon-valuation.yml'
                assert not page.locator('#range-picker').is_visible()
                assert not page.locator('#content .is-error').count()
                assert directory.locator('tr[data-company-id="shinetsu"]').count()==1
                assert directory.locator('tr[data-company-id="nuflare"]').count()==1
                assert directory.locator('tr[data-company-id="lumentum"] .mo-badge').inner_text()=='수요처·참고'
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path=str(out/f'overview-{width}-{theme}.png'))
                search=page.get_by_label('소부장 기업 검색',exact=True)
                search.fill('098120');expect(rows).to_have_count(1)
                assert rows.first.get_attribute('data-company-id')=='supplychain_microcont'
                search.fill('')
                directory.locator('[data-category="raw_materials"]').click()
                assert rows.count()==sum(any(tabs[t]['category']=='raw_materials' for t in c['tabs'] if t in tabs) for c in companies)
                page.get_by_label('소부장 세부 분야',exact=True).select_option('wafer')
                assert {r.get_attribute('data-company-id') for r in rows.all()}=={c['id'] for c in companies if 'wafer' in c['tabs']}
                directory.get_by_role('button',name='필터 초기화',exact=True).click()
                page.get_by_label('소부장 상장 시장',exact=True).select_option('domestic')
                domestic=sum(c['status']=='listed' and (bool(c.get('naver_code')) or c.get('symbol','').endswith(('.KS','.KQ'))) for c in companies)
                assert rows.count()==domestic
                page.get_by_label('소부장 등재 상태',exact=True).select_option('review')
                expect(rows).to_have_count(0)
                directory.get_by_role('button',name='필터 초기화',exact=True).click()
                page.get_by_label('소부장 등재 상태',exact=True).select_option('review')
                assert {r.get_attribute('data-company-id') for r in rows.all()}=={c['id'] for c in companies if c['status']=='review'}
                directory.get_by_role('button',name='필터 초기화',exact=True).click()
                page.get_by_label('소부장 세부 분야',exact=True).select_option('esc')
                expect(rows).to_have_count(0)
                assert directory.get_by_role('link',name='정전척 ESC 자료 보기').get_attribute('href')=='#/semicon/materials/components/esc'
                directory.get_by_role('button',name='필터 초기화',exact=True).click()
                for ascending in (True,False):
                    directory.get_by_role('button',name='PER(TTM)',exact=True).click()
                    values=rows.evaluate_all('(rows)=>rows.map(r=>{const t=r.cells[4].textContent;return t.endsWith("배")?Number(t.replaceAll(",","").replace("배","")):null})')
                    numeric=[v for v in values if v is not None]
                    assert numeric==sorted(numeric,reverse=not ascending)
                    assert all(v is None for v in values[len(numeric):])
                directory.get_by_role('button',name='필터 초기화',exact=True).click()
                search.fill('095340');expect(rows).to_have_count(1)
                rows.first.locator('.mo-company a').click()
                target=next(s for s in industry['sections'] if s.get('tab')=='test_components' and s.get('valuation_company')=='supplychain_isc')
                identifier=target.get('anchor') or 'financial-supplychain_isc'
                page.wait_for_function('(id)=>{const e=document.getElementById(id),h=document.querySelector(".dashboard-header");if(!e||document.querySelector(".page-loading"))return false;const y=e.getBoundingClientRect().top,b=h.getBoundingClientRect().bottom;return y>=b-2&&y<b+80}',arg=identifier,timeout=30000)
                assert page.evaluate('state.subtab')=='test_components'
                page.go_back(wait_until='networkidle')
                expect(page.locator('.materials-overview tbody tr[data-company-id]')).to_have_count(expected)
                assert page.evaluate('state.charts.length')==0
                assert page.evaluate('Object.keys(Chart.instances).length')==0
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                assert not errors,errors
                page.close()
                print('PASS',width,theme,'default summary, deduplication, filters, missing companies, sorting, focused navigation and history',flush=True)
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8807/')
    verify(parser.parse_args().url)

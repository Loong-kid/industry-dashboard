"""Exercise real film calendars and all five issuer financial cards."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp/movies'


def verify(base):
    OUT.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width,height in [(1440,1000),(768,1000),(390,844),(320,844)]:
            page=browser.new_page(viewport=dict(width=width,height=height),color_scheme='dark' if width==390 else 'light')
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'#/movies/slate',wait_until='networkidle')
            if page.locator('#site-gate').count():
                page.evaluate("() => {if(window.SITE_GATE) localStorage.setItem('site_gate_pass',window.SITE_GATE.hash)}")
                page.reload(wait_until='networkidle')
            root=page.locator('.movies-root');expect(root).to_be_visible(timeout=30000)
            expect(root.locator('.movie-count')).to_contain_text('2026년',timeout=30000)
            assert not page.locator('#range-picker').is_visible()
            assert page.get_by_role('button',name='영화 데이터 갱신',exact=False).count()==1
            root.screenshot(path=str(OUT/f'slate-{width}.png'))
            year=root.get_by_label('개봉 연도',exact=True);search=root.get_by_role('searchbox',name='작품·배급사 검색')
            year.select_option('2027');expect(root.locator('.movie-count')).to_contain_text('2027년')
            root.get_by_role('checkbox',name='IMAX 공개 라인업만',exact=True).check()
            search.fill('Starfighter');expect(root.locator('tbody tr[data-movie-id]')).to_have_count(1)
            assert '2027-05-28' in root.locator('tbody').inner_text()
            assert root.locator('tbody .movie-number').all_text_contents()==['—','—','—']
            search.fill('Narnia');expect(root.locator('tbody tr[data-movie-id]')).to_have_count(1)
            assert '2027-02-10' in root.locator('tbody').inner_text()
            search.fill('The Prestige');expect(root.locator('tbody tr[data-movie-id]')).to_have_count(1)
            assert '일자 미정' in root.locator('tbody').inner_text()
            assert '2027-01-01' not in root.locator('tbody').inner_text()
            search.fill('');year.select_option('2026');expect(root.locator('.movie-count')).to_contain_text('2026년')
            root.get_by_role('button',name='흥행 성적',exact=True).click()
            search.fill('The Odyssey');expect(root.locator('tbody tr[data-movie-id]')).to_have_count(1)
            assert '2026-07-17' in root.locator('tbody').inner_text()
            assert '550.0' in root.locator('.movie-performance').inner_text()
            root.get_by_role('button',name='상세',exact=True).click()
            assert '2026-12-11' in root.locator('.movie-expanded').inner_text()
            assert root.locator('.movie-expanded a').count()>=4
            root.get_by_role('button',name='전체화면',exact=True).click()
            full=root.get_by_role('dialog',name='영화 개봉·흥행 전체화면',exact=True);expect(full).to_be_visible()
            box=full.bounding_box();assert abs(box['width']-width)<2 and abs(box['height']-height)<2
            assert root.locator('.movie-table-wrap').bounding_box()['height']>100
            full.screenshot(path=str(OUT/f'fullscreen-{width}.png'))
            page.keyboard.press('Escape');expect(full).not_to_be_visible()
            assert search.input_value()=='The Odyssey'
            search.fill('Godzilla Minus Zero');expect(root.locator('tbody tr[data-movie-id]')).to_have_count(1)
            assert '오프닝' in root.locator('.movie-performance').inner_text()
            with page.expect_download() as download_info:root.get_by_role('button',name='조회 결과 CSV',exact=True).click()
            download_info.value.save_as(OUT/f'movies-{width}.csv')
            assert '21300000' in (OUT/f'movies-{width}.csv').read_text(encoding='utf-8-sig')
            search.fill('');root.get_by_role('checkbox',name='IMAX 공개 라인업만',exact=True).uncheck()
            root.get_by_role('checkbox',name='주요 개봉작만',exact=True).uncheck()
            year.select_option('2014');expect(root.locator('.movie-count')).to_contain_text('2014년')
            root.get_by_role('button',name='전체',exact=True).click()
            expect(root.locator('tbody tr[data-movie-id]')).to_have_count(40)
            root.get_by_role('button',name='다음',exact=True).click()
            assert '2 /' in root.locator('.movie-pager').inner_text()
            search.fill('not-a-movie-xxxxxxxx');assert '조건에 맞는 작품이 없습니다' in root.locator('tbody').inner_text()
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.goto(base+'#/movies/imax',wait_until='networkidle')
            page.wait_for_function('state.charts.length===3 && !document.querySelector(".page-loading")')
            assert page.locator('#range-picker').is_visible()
            assert page.locator('#content .ir-chart').count()==3
            first=page.locator('#content .ir-chart').first
            first.get_by_role('button',name='연간',exact=True).click()
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some(d=>d.data.some(v=>v!==null)))')
            page.screenshot(path=str(OUT/f'imax-{width}.png'))
            page.goto(base+'#/movies/peers',wait_until='networkidle')
            page.wait_for_function('state.charts.length===12 && !document.querySelector(".page-loading")')
            assert page.locator('.movie-company-overview tbody tr').count()==5
            assert page.evaluate('state.charts.every(c=>c.data.datasets.some(d=>d.data.some(v=>v!==null)))')
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not errors,errors
            print(f'PASS {width}px: film years, IMAX/date scope, box office, CSV, fullscreen, 15 issuer charts',flush=True)
            page.close()
        browser.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8802/')
    verify(p.parse_args().url)

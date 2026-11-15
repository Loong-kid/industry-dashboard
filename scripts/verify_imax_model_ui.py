"""Real browser regression for the editable IMAX model and existing charts."""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tmp/imax-model'


def verify(base):
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        for width in (1440, 768, 390, 320):
            page = browser.new_page(viewport=dict(width=width, height=1000), color_scheme='dark' if width == 390 else 'light')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base + '#/movies/imax', wait_until='networkidle')
            if page.locator('#site-gate').count():
                page.evaluate("() => {if(window.SITE_GATE) localStorage.setItem('site_gate_pass',window.SITE_GATE.hash)}")
                page.reload(wait_until='networkidle')
            model = page.get_by_role('region', name='IMAX 흥행·실적 추정 모델', exact=True)
            expect(model).to_be_visible(timeout=30000)
            page.wait_for_function('state.charts.length===3 && !document.querySelector(".page-loading")')
            assert not model.locator('.imax-issues').is_visible()
            assert '확정 1~3분기' in model.locator('.imax-results').inner_text()
            assert model.locator('tbody tr[data-film-id]').count() >= 10
            assert '가정상 주당가치' in model.locator('.imax-value-result').inner_text()
            assert model.locator('.imax-value-result tbody tr').nth(5).locator('td').last.inner_text() == '—'
            model.get_by_role('button', name='비지배지분 장부가로 예시 계산', exact=True).click()
            assert model.locator('.imax-value-result tbody tr').nth(5).locator('td').last.inner_text() != '—'
            model.get_by_label('비교 주가 (USD·선택)', exact=True).fill('25')
            assert '%' in model.locator('.imax-value-result tbody tr').last.inner_text()
            model.screenshot(path=str(OUT / f'model-{width}.png'))
            years = model.get_by_label('IMAX 추정 연도', exact=True)
            years.select_option('2027')
            assert '연간 전체를 추정' in model.locator('.imax-period-note').inner_text()
            row = model.locator('tr[data-film-id="/movie/Star-Wars-Starfighter-(2027)"]')
            direct = row.get_by_label('Star Wars: Starfighter IMAX 흥행 직접 입력', exact=True)
            direct.fill('200')
            assert row.get_by_label('Star Wars: Starfighter 세계 흥행 가정', exact=True).is_disabled()
            assert row.locator('td').nth(7).inner_text() == '200.0'
            assert not model.locator('.imax-issues').is_visible()
            direct.fill('')
            world = row.get_by_label('Star Wars: Starfighter 세계 흥행 가정', exact=True)
            assert world.is_enabled()
            world.fill('')
            expect(model.locator('.imax-issues')).to_be_visible()
            assert model.locator('.imax-value-result').inner_text() == ''
            world.fill('1000')
            assert row.locator('td').nth(7).inner_text() == '100.0'
            assert not model.locator('.imax-issues').is_visible()
            page.reload(wait_until='networkidle')
            years = model.get_by_label('IMAX 추정 연도', exact=True)
            years.select_option('2027')
            row = model.locator('tr[data-film-id="/movie/Star-Wars-Starfighter-(2027)"]')
            expect(row.get_by_label('Star Wars: Starfighter 세계 흥행 가정', exact=True)).to_have_value('1000')
            china = model.locator('tr[data-film-id="regional:2027:doomsday-china"]')
            china.get_by_role('checkbox').check()
            assert china.get_by_label('Avengers: Doomsday · 중국 상영 세계 흥행 가정', exact=True).is_disabled()
            expect(model.locator('.imax-issues')).to_be_visible()
            china.get_by_label('Avengers: Doomsday · 중국 상영 IMAX 흥행 직접 입력', exact=True).fill('50')
            assert china.locator('td').nth(7).inner_text() == '50.0'
            model.get_by_role('button', name='작품·이월 흥행 직접 추가', exact=True).click()
            custom = model.locator('tr[data-film-id^="custom:"]').last
            custom.get_by_label('추가 작품명', exact=True).fill('테스트 이월')
            custom.locator('[data-field=direct_imax]').fill('25')
            assert not model.locator('.imax-issues').is_visible()
            with page.expect_download() as info:
                model.get_by_role('button', name='가정·결과 CSV', exact=True).click()
            info.value.save_as(OUT / f'scenario-{width}.csv')
            text = (OUT / f'scenario-{width}.csv').read_text(encoding='utf-8-sig')
            assert '테스트 이월' in text and '2027' in text and '538' not in text
            # Negative/overflow inputs never render partial totals as final values.
            assumptions = model.locator('.imax-assumptions')
            assumptions.locator('summary').click()
            rate = model.get_by_label('DMR 실효 요율 %', exact=True)
            rate.fill('101')
            expect(model.locator('.imax-issues')).to_be_visible()
            assert model.locator('.imax-value-result').inner_text() == ''
            rate.fill('12')
            assert not model.locator('.imax-issues').is_visible()
            model.get_by_role('button', name='이 연도 가정 초기화', exact=True).click()
            assert model.locator('tr[data-film-id^="custom:"]').count() == 0
            assert model.locator('.imax-value-result tbody tr').nth(5).locator('td').last.inner_text() == '—'
            case_cost = model.get_by_label('오디세이 추가 영업비용 가정', exact=True)
            case_cost.fill('')
            assert '확인하세요' in model.locator('.imax-case-results').inner_text()
            assert not model.locator('.imax-results > .imax-issues').is_visible()
            case_cost.fill('10')
            assert '10.0 가정' in model.locator('.imax-case-results').inner_text()
            assert not model.locator('.imax-case-results .imax-issues').count()
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'), width
            assert not errors, errors
            print(f'PASS {width}px: model/year selection, editable forecasts, saved state, missing inputs, China scope, NCI, CSV, charts', flush=True)
            page.close()
        browser.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:8803/')
    verify(p.parse_args().url)

"""Exercise the real momentum monitor across markets, themes and screen sizes."""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def verify(base):
    out=ROOT/'tmp/market-momentum/ui'
    out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        for width in (1440,390):
            for theme in ('light','dark'):
                page=browser.new_page(viewport={'width':width,'height':1050},color_scheme=theme)
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                for market,name in [('us','미국'),('kr','한국')]:
                    page.goto(base+'#/momentum/'+market,wait_until='networkidle')
                    if page.locator('#site-gate').count():
                        page.evaluate("() => {if(window.SITE_GATE)localStorage.setItem('site_gate_pass',window.SITE_GATE.hash)}")
                        page.reload(wait_until='networkidle')
                    page.wait_for_function('(market)=>typeof state!=="undefined" && state.industry?.id==="momentum" && state.subtab===market && !document.querySelector(".page-loading")',arg=market)
                    root=page.get_by_role('region',name=name+' 산업 가격 모멘텀',exact=True)
                    expect(root).to_be_visible()
                    doc=page.evaluate('(market)=>state.docs.get("momentum_"+market)',market)
                    total=len(doc['rows'])
                    rows=root.locator('tbody tr[data-industry-id]')
                    expect(rows).to_have_count(total)
                    assert doc['updated'] in root.locator('.mm-asof').inner_text()
                    assert page.locator('#refresh-label').inner_text()=='모멘텀 갱신'
                    assert page.evaluate('currentTarget().workflow')=='update-momentum.yml'
                    assert page.locator('#range-picker').is_visible()
                    assert not page.locator('#content .is-error').count()
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                    assert page.evaluate('Object.keys(Chart.instances).length')==2
                    palette=page.evaluate('Object.values(Chart.instances).find(c=>c.config.type==="line").data.datasets.map(d=>d.borderColor)')
                    assert all(isinstance(color,str) and color for color in palette)
                    assert len(set(palette))==len(palette)
                    page.screenshot(path=str(out/f'{market}-{width}-{theme}.png'))
                    search=root.get_by_label('산업·ETF·구성 종목 검색',exact=True)
                    search.fill('반도체')
                    expected=sum('반도체' in (r['name']+' '+r['scope']+' '+' '.join(i['name']+' '+i['symbol'] for i in r['instruments'])) for r in doc['rows'])
                    expect(rows).to_have_count(expected)
                    search.fill('no-such-industry')
                    expect(rows).to_have_count(0)
                    assert '조건에 맞는 산업이 없습니다' in root.inner_text()
                    root.get_by_role('button',name='필터 초기화',exact=True).click()
                    root.get_by_label('분류',exact=True).select_option('sector')
                    root.get_by_label('구성 방식',exact=True).select_option('basket')
                    expect(rows).to_have_count(0)
                    root.get_by_role('button',name='필터 초기화',exact=True).click()
                    root.get_by_label('구성 방식',exact=True).select_option('basket')
                    expect(rows).to_have_count(sum(r['kind']=='basket' for r in doc['rows']))
                    target=next(r for r in doc['rows'] if r['id']==market+'_power_equipment')
                    row=rows.filter(has=page.get_by_role('button',name=target['name'],exact=True))
                    row.get_by_role('button',name=target['name'],exact=True).click()
                    detail=root.locator('[data-detail-for="'+target['id']+'"]')
                    expect(detail).to_be_visible()
                    assert '생존편향' in detail.inner_text()
                    assert detail.locator('li').count()==3
                    assert detail.locator('a[href^="https://"]').count()==6
                    row.get_by_role('button',name=target['name'],exact=True).click()
                    root.get_by_role('button',name='필터 초기화',exact=True).click()
                    root.get_by_label('정렬 기준',exact=True).select_option('ret_1m')
                    fresh=[r for r in doc['rows'] if r['status']=='ok' and r['metrics']['ret_1m'] is not None]
                    expected=sorted([r['metrics']['ret_1m'] for r in fresh],reverse=True)
                    actual=rows.evaluate_all('(rows)=>rows.map(r=>r.dataset.industryId)')
                    lookup={r['id']:r for r in doc['rows']}
                    assert [lookup[id]['metrics']['ret_1m'] for id in actual[:len(fresh)]]==expected
                    root.get_by_role('button',name='1개월 기준 정렬',exact=True).click()
                    actual=rows.evaluate_all('(rows)=>rows.map(r=>r.dataset.industryId)')
                    assert [lookup[id]['metrics']['ret_1m'] for id in actual[:len(fresh)]]==list(reversed(expected))
                    root.get_by_role('button',name='필터 초기화',exact=True).click()
                    while rows.locator('input:checked').count():
                        rows.locator('input:checked').first.uncheck()
                    for check in rows.locator('input[type="checkbox"]').all()[:7]:
                        check.click()
                    expect(rows.locator('input:checked')).to_have_count(5)
                    assert '최대 5개 산업' in root.locator('[role="status"]').inner_text()
                    assert '비교 5/5' in root.locator('.mm-resultbar').inner_text()
                    assert page.evaluate('Object.keys(Chart.instances).length')==2
                    main=root.locator('.mm-chart').first
                    expect(main.locator('canvas')).to_have_count(1)
                    values=main.locator('canvas').evaluate('(canvas)=>Chart.getChart(canvas).data.datasets.map(s=>s.data[0])')
                    assert all(v==100 for v in values)
                    root.get_by_role('button',name='시장 대비',exact=True).click()
                    assert main.locator('canvas').evaluate('(canvas)=>Chart.getChart(canvas).data.datasets.at(-1).data.every(v=>v===100)')
                    page.locator('#range-picker [data-range="3y"]').click()
                    page.wait_for_function('state.range==="3y" && !document.querySelector(".page-loading")')
                    expect(rows.locator('input:checked')).to_have_count(5)
                    assert root.get_by_role('button',name='시장 대비',exact=True).get_attribute('aria-pressed')=='true'
                    for quad in root.locator('.mm-quadrants button').all():
                        if int(quad.inner_text().split()[-1])>0:
                            quad.click()
                            assert 0<rows.count()<=total
                            quad.click()
                            expect(rows).to_have_count(total)
                            break
                    root.locator('.mm-chart-grid').scroll_into_view_if_needed()
                    page.screenshot(path=str(out/f'{market}-charts-{width}-{theme}.png'))
                    root.get_by_role('button',name='3개월 상위 3개',exact=True).click()
                    expect(rows.locator('input:checked')).to_have_count(min(3,sum(r['eligible'] for r in doc['rows'])))
                    root.get_by_role('button',name='가격 지수',exact=True).click()
                    root.get_by_text('계산 기준·구성 범위·출처',exact=True).click()
                    assert '252거래일' in root.locator('.mm-methodology').inner_text()
                    assert '생존편향' in root.locator('.mm-methodology').inner_text()
                    page.locator('#range-picker [data-range="1y"]').click()
                    page.wait_for_function('state.range==="1y" && !document.querySelector(".page-loading")')
                    page.reload(wait_until='networkidle')
                    page.wait_for_function('!document.querySelector(".page-loading") && document.querySelector(".momentum")')
                    expect(page.locator('.momentum tbody input:checked')).to_have_count(min(3,sum(r['eligible'] for r in doc['rows'])))
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.goto(base+'#/semicon/materials',wait_until='networkidle')
                page.wait_for_function('!document.querySelector(".page-loading") && document.querySelector(".materials-overview")')
                assert page.evaluate('Object.keys(Chart.instances).length')==0
                assert not errors,errors
                page.close()
                print('PASS',width,theme,'US/Korea rankings, search, filters, 5-way charts, relative mode, sources, ranges, persistence and cleanup',flush=True)
        browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8817/')
    verify(parser.parse_args().url)

import argparse,json,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'tmp/mask-history-20261015'
O.mkdir(parents=True,exist_ok=True)

def verify(base):
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True)
  for width,mode in [(1440,'light'),(390,'dark'),(1024,'dark')]:
   page=b.new_page(viewport=dict(width=width,height=1000),color_scheme=mode);errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(base+'#/semicon/materials/snstech')
   page.wait_for_function('typeof state!=="undefined" && state.charts.length===73 && !document.querySelector(".page-loading")')
   links=page.locator('#nav a');names=links.all_text_contents()
   assert len(names)==len(set(names))==len(json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))['industries'])
   assert page.locator('#nav .nav-group').count()==3
   assert not re.search(r'[\U0001f300-\U0001faff]',page.locator('.sidebar').inner_text())
   assert page.locator('#nav [aria-current="page"]').inner_text()=='반도체'
   assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
   page.locator('#nav a').first.focus()
   assert page.locator('#nav a').first.evaluate('(a)=>getComputedStyle(a).outlineStyle')=='solid'
   page.locator('#page-title').click()
   page.screenshot(path=str(O/f'sidebar-{width}-{mode}.png'))
   page.locator('#range-picker [data-range="all"]').click()
   page.wait_for_function('state.range==="all" && state.charts.length===73 && !document.querySelector(".page-loading")')
   result=page.evaluate('''()=>state.charts.filter(c=>/JEOL.*산업기기|NuFlare/.test(c.canvas.closest('.card').querySelector('.card-name').textContent)).map(c=>({name:c.canvas.closest('.card').querySelector('.card-name').textContent,first:c.data.labels[0],count:c.data.labels.length}))''')
   assert len(result)==6,result
   assert all(c['first']=='2014-03-31' for c in result),result
   assert sorted(c['count'] for c in result)==[13,13,13,13,50,50],result
   card=page.locator('.card').filter(has=page.get_by_text('JEOL · 산업기기 매출 · 분기',exact=True))
   card.scroll_into_view_if_needed();page.screenshot(path=str(O/f'jeol-{width}.png'))
   if width==390:
    page.evaluate('location.hash="#/shipbuilding"')
    page.wait_for_function('state.industry.id==="shipbuilding"')
    bounds=page.locator('#nav [aria-current="page"]').bounding_box();nav=page.locator('#nav').bounding_box()
    assert bounds['x']>=nav['x']-1 and bounds['x']+bounds['width']<=nav['x']+nav['width']+1
   assert not errors,errors
   print(json.dumps(dict(width=width,theme=mode,charts=result,errors=errors),ensure_ascii=False))
   page.close()
  b.close()

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--url',default='http://127.0.0.1:8765/');verify(ap.parse_args().url)

"""Public North American release events and factual lifetime box office totals."""
import datetime as dt
import re
from urllib.parse import urlsplit, unquote

from bs4 import BeautifulSoup

BASE='https://www.the-numbers.com'


def money(value):
    text=value.strip().replace(',','')
    if text in ('','-','—','N/A'):return None
    if not re.fullmatch(r'\$\d+(?:\.\d+)?',text):raise ValueError('Unrecognized box office amount')
    return int(float(text[1:]))


def movie_key(url):
    path=urlsplit(url).path
    if not re.fullmatch(r'/movie/[^/]+',path):raise ValueError('Unexpected movie identity')
    return unquote(path)


def parse_schedule(raw,year):
    soup=BeautifulSoup(raw,'html.parser')
    table=next((t for t in soup.select('table') if 'Release Date' in t.get_text(' ',strip=True)[:150] and 'Distributor' in t.get_text(' ',strip=True)[:150]),None)
    if table is None:raise ValueError('Release calendar table unavailable')
    date=None;date_text='';month=None;result={}
    for tr in table.select('tr'):
        cells=tr.find_all(['td','th'],recursive=False)
        if not cells:continue
        if len(cells)==1:
            label=cells[0].get_text(' ',strip=True)
            if re.fullmatch(r'[A-Za-z]+ '+str(year),label):
                try:month=dt.datetime.strptime(label,'%B %Y').month
                except ValueError:month=None
                date=None;date_text=label
            continue
        if len(cells)!=4 or not cells[1].select_one('a[href^="/movie/"]'):continue
        label=cells[0].get_text(' ',strip=True)
        if label:
            date_text=label;date=None
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}',tr.get('id','')):
                date=dt.date.fromisoformat(tr['id']).isoformat()
            else:
                try:date=dt.datetime.strptime(label+' '+str(year),'%B %d %Y').date().isoformat()
                except ValueError:pass
        if date and int(date[:4])!=year:raise ValueError('Calendar year mismatch')
        anchor=cells[1].select_one('a[href^="/movie/"]');key=movie_key(anchor['href']);title=anchor.get_text(' ',strip=True)
        kind=cells[1].get_text(' ',strip=True)[len(title):].strip().strip('()')
        item=result.setdefault(key,dict(id=key,title=title,url=BASE+anchor['href'],year=year,events=[],distributors=[]))
        distributor=cells[2].get_text(' ',strip=True)
        event=dict(date=date,date_text=date_text,release_type=kind,distributor=distributor,
            source_url=f'{BASE}/movies/release-schedule/{year}')
        if event not in item['events']:item['events'].append(event)
        if distributor and distributor not in item['distributors']:item['distributors'].append(distributor)
        amount=money(cells[3].get_text(' ',strip=True))
        if amount is not None:item['schedule_domestic_usd']=max(item.get('schedule_domestic_usd',0),amount)
    if not result:raise ValueError('Release calendar unexpectedly empty')
    return list(result.values())


def parse_worldwide(raw,year):
    soup=BeautifulSoup(raw,'html.parser')
    table=next((t for t in soup.select('table') if 'Worldwide' in t.get_text(' ',strip=True)[:160] and 'Domestic' in t.get_text(' ',strip=True)[:160]),None)
    if table is None:raise ValueError('Worldwide box office table unavailable')
    rows=[]
    for tr in table.select('tr'):
        cells=tr.find_all(['td','th'],recursive=False)
        if len(cells)<5 or not cells[0].get_text(strip=True).isdigit():continue
        a=cells[1].select_one('a[href^="/movie/"]')
        if a is None:continue
        ww,domestic,international=[money(c.get_text(' ',strip=True)) for c in cells[2:5]]
        if ww is not None and domestic is not None and international is not None and abs(ww-domestic-international)>1:
            raise ValueError('Box office regional totals do not reconcile')
        rows.append(dict(id=movie_key(a['href']),title=a.get_text(' ',strip=True),url=BASE+a['href'],
            worldwide_usd=ww,domestic_usd=domestic,international_usd=international,worldwide_rank=int(cells[0].get_text(strip=True)),
            box_office_year=year,box_office_url=f'{BASE}/box-office-records/worldwide/all-movies/cumulative/released-in-{year}'))
    if not rows:raise ValueError('Worldwide chart unexpectedly empty')
    return rows


def combine(year,scheduled,worldwide,reviewed,checked):
    films={r['id']:dict(r) for r in scheduled}
    for r in worldwide:
        item=films.setdefault(r['id'],dict(id=r['id'],title=r['title'],url=r['url'],year=year,events=[],distributors=[]))
        title=item['title'];item.update(r);item['title']=title
    for record in reviewed:
        if year in record['years'] and record['movie_id'] not in films and record.get('title'):
            films[record['movie_id']]=dict(id=record['movie_id'],title=record['title'],url=record['source_url'],year=year,
                distributors=[],events=[dict(date=None,date_text=f'{year} (일자 미정)',release_type='IMAX IR 예정'+(' · re-release' if record.get('rerelease') else ''),distributor='',source_url=record['source_url'])])
    for item in films.values():
        if 'domestic_usd' not in item and 'schedule_domestic_usd' in item:
            item['domestic_usd']=item['schedule_domestic_usd'];item['box_office_url']=f'{BASE}/movies/release-schedule/{year}'
        item['imax_evidence']=[]
        for event in item['events']:
            if 'IMAX' in event['release_type'].upper():
                item['imax_evidence'].append(dict(source_url=event['source_url'],checked=checked,
                    note='북미 개봉 일정에 IMAX 상영으로 별도 기재',kind='schedule'))
        for record in reviewed:
            if record['movie_id']==item['id'] and year in record['years']:
                item['imax_evidence'].append({k:v for k,v in record.items() if k not in ('movie_id','years')})
        item['imax_confirmed']=bool(item['imax_evidence'])
        item['major_release']=item['imax_confirmed'] or item.get('worldwide_rank') is not None or any('wide' in e['release_type'].lower() for e in item['events'])
        item['rerelease']=any('re-release' in e['release_type'].lower() for e in item['events'])
        item['box_office_checked']=checked if item.get('domestic_usd') is not None or item.get('worldwide_usd') is not None else None
        item['events'].sort(key=lambda e:(e['date'] is None,e['date'] or '',e['release_type']))
    return dict(id=f'films_{year}',name=f'{year}년 영화 개봉·흥행',year=year,fetched=checked,
        release_market='북미(미국·캐나다)',currency='USD',worldwide_limit=100,
        scope='북미 개봉 일정과 The Numbers의 해당 연도 개봉작 분류에 따른 세계 누적 흥행 상위 100편을 영화 원문 ID로 연결합니다. 일부 해외 작품은 북미 개봉일 미확인입니다. 금액은 작품의 누적 티켓 매출이며 재개봉 이전 매출을 포함할 수 있습니다.',
        sources=[f'{BASE}/movies/release-schedule/{year}']+([f'{BASE}/box-office-records/worldwide/all-movies/cumulative/released-in-{year}'] if worldwide else []),
        films=sorted(films.values(),key=lambda r:(r['title'].casefold(),r['id'])))

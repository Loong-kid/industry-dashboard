"""Source-linked stocks / YTD / product KPIs: never mix their definitions."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from pypdf import PdfReader

from fetch_cpu_companies import save
from fetch_game_fx import SOURCE, parse_rates
from fetch_lng_containment import ROOT,OUT,MANUAL,CACHE,load
from shipbuilding_equipment_sources import end,number

warnings.filterwarnings('ignore',category=XMLParsedAsHTMLWarning)


def cells(table):
    return [[re.sub(r'\s+','',c.get_text(' ',strip=True)) for c in tr.find_all(['td','th','te'],recursive=False)] for tr in table.find_all('tr')]


def korean_business(raw,company,date,receipt):
    soup=BeautifulSoup(raw,'html.parser');result=dict(date=date,ref=dict(url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+receipt,label='DART 사업의 내용',filed=f'{receipt[:4]}-{receipt[4:6]}-{receipt[6:8]}'))
    for table in soup.find_all('table'):
        text=re.sub(r'\s+','',table.get_text(' ',strip=True));rows=cells(table)
        if all(k in text for k in ['수주총액','기납품액','수주잔고']):
            unit=table.find_previous(['p','table'])
            unit=re.sub(r'\s+','',unit.get_text()) if unit else ''
            for row in rows:
                expected='초저온보냉재' if company=='dongsung_finetec' else 'LNG운반선화물창판넬'
                if not row or row[0]!=expected:continue
                value=number(row[-1])
                if value is None:continue
                # Enforce the actual column and unit. Unknown units are gaps.
                if company=='dongsung_finetec' and '백만원' in unit:
                    result.update(backlog=value,backlog_currency='KRW',backlog_unit='백만 KRW',backlog_scope='초저온보냉재')
                elif company=='hankuk_carbon' and re.search(r'천(?:USD|US\$|달러)',unit,re.I):
                    result.update(backlog=value/1000,backlog_currency='USD',backlog_unit='백만 USD',backlog_scope='LNG운반선 화물창판넬')
        if company=='dongsung_finetec' and '평균가동률' in text and '실제가동시간' in text:
            for row in rows:
                if row and 'PU단열재' in row[0] and len(row)>=4:
                    value=number(row[-1].replace('%',''))
                    if value is not None and 0<=value<=100:result['utilization']=value
        if company=='hankuk_carbon' and '매출액(비율)' in text:
            for row in rows:
                if row and row[0]=='산업재' and any('LNG' in c for c in row):
                    value=number(row[-1].replace('%',''))
                    if value is not None and 0<=value<=100:result['industrial_share']=value
    return result


def gtt_business(text,source):
    text=re.sub(r'\s+',' ',text)
    result=dict(date=end(source['year'],source['quarter']),ref=dict(url=source['url'],label='GTT 사업활동·수주 공시',filed=source['filed']))
    found=re.search(r'order book,? excluding LNG as fuel,? stood at (\d+) units,? (?:breaking|broken) down as follows:\s*[-–•]?\s*(\d+) LNG carriers',text,re.I)
    if found:result.update(core_book=int(found[1]),lng_book=int(found[2]))
    for fuel in re.finditer(r'Regarding LNG as fuel,(.{0,550})',text,re.I):
        m=re.search(r'(?:there were (\d+) vessels|(?:order book|vessels on order) stood at (\d+) (?:vessels|units))',fuel[1],re.I)
        if m:result['fuel_book']=int(m[1] or m[2])
    special=re.search(r'LNG as fuel order book stands a\s*t (\d+) units',text,re.I)
    if special:result['fuel_book']=int(special[1])
    found=re.search(r'Orders received:\s*(.{1,350}?)(?:As of |At (?:March|June|September|December)|- Orders withdrawn|\d+ See page)',text,re.I)
    if found:
        entries=re.findall(r'(\d+)\s+(LNG carriers?|ethane carriers?|FSRUs?|FLNGs?|onshore storage tanks?)',found[1],re.I)
        if entries:
            result['core_orders_ytd']=sum(int(v) for v,_ in entries)
            result['lng_orders_ytd']=sum(int(v) for v,k in entries if k.lower().startswith('lng carrier'))
    # The reviewed Q1 2022 bridge predates the labelled "Orders received" row.
    if source['year']==2022 and source['quarter']==1:
        legacy=re.search(r'- (\d+) LNG carrier orders\s+At March 31, 2022',text)
        if legacy:result.update(core_orders_ytd=int(legacy[1]),lng_orders_ytd=int(legacy[1]))
    return result


def period_end_quote(rates,currency,date):
    available=sorted(d for d,r in rates.items() if d<=date and currency in r)
    if not available:return None
    day=available[-1]
    if (dt.date.fromisoformat(date)-dt.date.fromisoformat(day)).days>7:return None
    return dict(currency=currency,date=date,observed=day,local_per_usd=rates[day][currency],source=SOURCE)


def card(key,name,unit,rows,fields,note,fx=None,native_currency=None):
    series={label:[[r['date'],r.get(field)] for r in rows] for field,label in fields.items()}
    notes={};refs={};native={label:[] for label in fields.values()}
    for row in rows:
        date=row['date'];refs[date]=row['ref'];notes[date]=[note]
        if native_currency:
            value=row.get('backlog');quote=(fx or {}).get(native_currency+'|'+date)
            usd=value if native_currency=='USD' else value/quote['local_per_usd'] if quote and value is not None else None
            label=next(iter(fields.values()));series[label]=[[d,usd if d==date else v] for d,v in series[label]]
            native[label].append([date,value])
            notes[date]+=[f'원자료: {value:,.3f} 백만 {native_currency}' if value is not None else '원자료 미확보']
            if native_currency=='USD':notes[date].append('공시된 USD 잔고 그대로 · 환산 없음')
            elif quote:notes[date].append(f"기말 ECB 환율: 1 USD = {quote['local_per_usd']:,.6f} {native_currency} · 관측 {quote['observed']}. 잔고는 시점 지표이므로 기간 평균환율을 쓰지 않습니다.")
            else:notes[date].append('기말 환율 미확보 · USD 값 미표시')
    doc=dict(id=key,name=name,unit=unit,series=series,point_notes=notes,point_sources=refs,
        updated=rows[-1]['date'] if rows else '',fetched=max((r.get('checked',r['ref']['filed']) for r in rows),default=''),
        source='GTT 공식 IR·DART 원문',source_url=rows[-1]['ref']['url'] if rows else '',company_kpi=True,
        frequency='quarterly',frequency_label='보고기간 말 · 공시 시점',quarter_labels=True,zero_baseline=True,span_gaps=False,
        description=note,basis_details=[dict(label='정의·해석',value=note),dict(label='원문·시점',value='수치는 해당 보고기간 말 또는 공시된 실제 기간 기준입니다. 빈 기간을 0이나 추정치로 채우지 않습니다. 표의 출처를 눌러 원문을 확인할 수 있습니다.')])
    if native_currency:doc.update(original_series=native,original_currency=native_currency,original_unit='millions')
    if key=='containment_gtt_orders':doc.update(change_mode='none',frequency_label='연초 이후 누적 · YTD')
    elif unit=='%':doc.update(change_mode='none',frequency_label='보고기간 누적 · 공시 기준')
    else:doc['frequency_label']='보고기간 말 잔량'
    return doc


def build(offline=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    state=load(OUT/'containment_state.json',{});business=load(OUT/'containment_business.json',dict(companies={},spot_fx={}))
    for company in ['dongsung_finetec','hankuk_carbon']:
        prior={r['date']:r for r in business['companies'].get(company,[])}
        reports=state['companies'].get(company,{}).get('reports',[])
        for report in reports:
            receipt=next(iter(report['fields'].values()))['url'].split('rcpNo=')[-1]
            path=CACHE/f'{company}-{receipt}.xml';date=end(report['year'],report['quarter'])
            if not path.exists() or date>asof or receipt[:8]>asof.replace('-',''):continue
            row=korean_business(path.read_bytes(),company,date,receipt)
            if 'backlog' not in row:continue
            row['checked']=asof;prior[date]=row
        business['companies'][company]=list(sorted(prior.values(),key=lambda r:r['date']))
    prior={r['date']:r for r in business['companies'].get('gtt',[])}
    sources=load(MANUAL/'gtt-reviewed.json',[])
    for source in sources:
        path=CACHE/source['file']
        if source['year']<2022 or source['filed']>asof or not path.exists():continue
        row=gtt_business(' '.join(p.extract_text() or '' for p in PdfReader(path).pages),source)
        if 'core_book' not in row:continue
        row['checked']=asof;prior[row['date']]=row
    business['companies']['gtt']=list(sorted(prior.values(),key=lambda r:r['date']))
    rates=None;quotes=business.get('spot_fx',{})
    if not offline:
        import requests
        try:
            r=requests.get(SOURCE,timeout=40);r.raise_for_status();rates=parse_rates(r.content)
        except (requests.RequestException,ValueError):pass
    if rates:
        for row in business['companies']['dongsung_finetec']:
            quote=period_end_quote(rates,'KRW',row['date'])
            if quote:quotes['KRW|'+row['date']]=quote
    business.update(spot_fx=quotes,updated=asof);save(OUT/'containment_business.json',business)
    companies=business['companies'];gtt=companies['gtt']
    cards=[card('containment_gtt_backlog','GTT · 화물창 수주잔고','기',gtt,
        {'core_book':'핵심사업 전체','lng_book':'그중 LNG 운반선','fuel_book':'LNG 연료용 · 별도'},
        '보고기간 말 잔량입니다. 핵심사업에는 LNG·에탄 운반선, FSRU·FLNG·육상 탱크 등이 포함됩니다. LNG 운반선은 핵심사업의 부분집합이며 LNG 연료용은 별도 범위입니다. 세 시리즈를 더하지 않습니다. 러시아 프로젝트의 수주 제외 등 범위 변경에 유의하세요.'),
        card('containment_gtt_orders','GTT · 신규 수주 · 연초 이후 누적','기 · YTD',gtt,
        {'core_orders_ytd':'핵심사업 신규 수주 · YTD','lng_orders_ytd':'그중 LNG 운반선 · YTD'},
        '1월부터 해당 보고기간 말까지 신규 수주 누적입니다. 분기 단독 수주가 아니며 매년 1분기에 초기화됩니다. 시리즈를 더하거나 각 분기의 YTD 값을 합산하지 않습니다. 운반선뿐 아니라 육상 탱크 등이 포함되므로 단위는 기입니다.'),
        card('containment_dongsung_backlog','동성화인텍 · 초저온보냉재 수주잔고','백만 USD',companies['dongsung_finetec'],{'backlog':'수주잔고'},
        'DART 사업의 내용에 공시한 초저온보냉재 기말 수주잔고입니다. 계약금액 공시 합계가 아니며 신규 수주·납품·변경계약에 따라 변합니다.',quotes,'KRW'),
        card('containment_dongsung_utilization','동성화인텍 · PU단열재 가동률','%',companies['dongsung_finetec'],{'utilization':'PU단열재 가동률'},
        '공시된 PU단열재 사업부문 실제 가동시간 ÷ 가동가능시간입니다. 분기 말까지의 보고기간 누적 가동률이며 분기 단독 가동률로 차감하지 않습니다. 다른 품목의 생산능력을 합산하지 않습니다.'),
        card('containment_hankuk_backlog','한국카본 · LNG 화물창 판넬 수주잔고','백만 USD',companies['hankuk_carbon'],{'backlog':'수주잔고'},
        'DART 사업의 내용에서 공시한 LNG운반선 화물창 판넬 기말 수주잔고입니다. 원문 단위 천 USD를 백만 USD로 바꿨으며 환율 환산은 하지 않습니다.',quotes,'USD'),
        card('containment_hankuk_mix','한국카본 · 산업재 매출 비중 · LNG 포함','%',companies['hankuk_carbon'],{'industrial_share':'산업재 비중 · LNG 포함'},
        '공시된 연결 매출 중 산업재 비중입니다. LNG 보냉재 외 절연적층물·GPD/F 등이 함께 들어 있으므로 LNG 보냉재만의 매출 비중으로 해석하지 않습니다. 보고기간 누적 비중이며 기간별 비중을 합산하지 않습니다.')]
    for doc in cards:save(OUT/(doc['id']+'.json'),doc)
    print('LNG containment KPIs:',{c:len(rows) for c,rows in companies.items()},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');build(p.parse_args().offline)

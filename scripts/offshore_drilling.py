"""Offshore evidence model. A rig, its manager, and its contracts are separate.

Dates retain source precision; undisclosed rates never become zero or TCV/day.
All derived availability/coverage is a dated public-contract snapshot.
"""
import calendar
import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

from common import collection_date

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/offshore'
CACHE = ROOT / '.cache/offshore'
MANUAL = ROOT / 'manual/offshore'
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
TYPES = {'drillship': '드릴십', 'semi': '반잠수식', 'jackup': '잭업'}
COMPANIES = {
 'transocean': {'name': 'Transocean', 'ticker': 'RIG', 'cik': 1451505,
   'index': 'https://deepwater.com/investors/fleet-status-report', 'focus': '초심해·가혹환경 부유식'},
 'valaris': {'name': 'Valaris', 'ticker': 'VAL', 'cik': 314808,
   'index': 'https://www.valaris.com/investors/financials/fleet-status-reports/default.aspx', 'focus': '드릴십·잭업·ARO JV'},
 'noble': {'name': 'Noble', 'ticker': 'NE', 'cik': 1895262,
   'index': 'https://noblecorp.com/our-investors/reports-filings/fleet-status-report/', 'focus': '초심해·고사양 잭업'},
 'seadrill': {'name': 'Seadrill', 'ticker': 'SDRL', 'cik': 1737706,
   'index': 'https://www.seadrill.com/fleet/', 'focus': '부유식·Sonadrill 관리 선대'},
 'odfjell': {'name': 'Odfjell Drilling', 'ticker': 'ODL · Oslo',
   'index': 'https://www.odfjelldrilling.com/our-fleet/our-fleet2/', 'focus': '가혹환경 반잠수식·타사 관리'},
 'borr': {'name': 'Borr Drilling', 'ticker': 'BORR', 'cik': 1715497,
   'index': 'https://www.borrdrilling.com/fleet-status-report', 'focus': '고사양 잭업'},
}


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def ident(company, name):
    return company + '-' + re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def qend(year, q):
    m = q * 3
    return dt.date(year, m, calendar.monthrange(year, m)[1]).isoformat()


def date_range(raw):
    """Bounds are for timeline rendering, NOT invented exact dates."""
    text = clean(raw).replace('–', '-').replace('—', '-')
    if not text or text == '-' or text.lower() in ('available', 'undisclosed', 'not disclosed'):
        return {'text': text, 'precision': 'unknown', 'min': None, 'max': None}
    q = re.fullmatch(r'(?:Q([1-4])[- ]?(\d{2,4})|(\d{4})[- ]?Q([1-4]))', text, re.I)
    if q:
        year = int(q[2] or q[3]); year += 2000 if year < 100 else 0
        quarter = int(q[1] or q[4]); m = quarter * 3 - 2
        return {'text': text, 'precision': 'quarter', 'min': f'{year}-{m:02d}-01', 'max': qend(year, quarter)}
    half=re.fullmatch(r'([12])H[- ]?(\d{2,4})',text,re.I)
    if half:
        year=int(half[2]);year+=2000 if year<100 else 0
        return {'text':text,'precision':'half_year','min':f'{year}-'+('01-01' if half[1]=='1' else '07-01'),'max':f'{year}-'+('06-30' if half[1]=='1' else '12-31')}
    m = re.fullmatch(r'([A-Za-z]+)\s*[- ]\s*(\d{2,4})', text)
    if m and m[1].lower() in MONTHS:
        year, month = int(m[2]), MONTHS[m[1].lower()]; year += 2000 if year < 100 else 0
        return {'text': text, 'precision': 'month', 'min': f'{year}-{month:02d}-01',
                'max': dt.date(year, month, calendar.monthrange(year, month)[1]).isoformat()}
    if re.fullmatch(r'20\d{2}', text):
        return {'text': text, 'precision': 'year', 'min': text + '-01-01', 'max': text + '-12-31'}
    if re.fullmatch(r'20\d{2}-\d{2}-\d{2}', text):
        dt.date.fromisoformat(text)
        return {'text': text, 'precision': 'day', 'min': text, 'max': text}
    return {'text': text, 'precision': 'unknown', 'min': None, 'max': None}


def contract(rig, customer='', location='', start='', end='', rate=None, kind='firm', note='', source=None):
    s, e = date_range(start), date_range(end)
    if s['min'] and e['max'] and s['min'] > e['max']:
        raise ValueError(f'Reversed contract dates: {rig} {start} {end}')
    if rate is not None and (isinstance(rate, bool) or not 10000 <= rate <= 1000000):
        raise ValueError('Invalid USD/day rate')
    key = '|'.join([rig, customer, location, start, end, kind])
    return {'id': hashlib.sha256(key.encode()).hexdigest()[:16], 'rig_id': rig,
            'customer': clean(customer), 'location': clean(location), 'start': s, 'end': e,
            'dayrate_usd': rate, 'kind': kind, 'note': clean(note), 'source': source}


def rig(company, name, rig_type, source, **kwargs):
    return {'id': ident(company, name), 'name': name, 'company': company, 'type': rig_type,
            'owner_group': COMPANIES[company]['name'], 'ownership_basis': '공시상 소유 그룹 · 개별 등기 법인 별도',
            'manager': COMPANIES[company]['name'], 'ownership_pct': None, 'ownership_kind': 'owned_group',
            'location': '', 'status_reported': '', 'built': None, 'design': '', 'water_depth_ft': None,
            'sources': [source], 'contracts': [], 'notes': '', **kwargs}


def words(page, x0, x1, y0, y1):
    return [w for w in page.get_text('words') if x0 <= (w[0]+w[2])/2 < x1 and y0 <= (w[1]+w[3])/2 < y1]


def word_lines(ws):
    lines = []
    for w in sorted(ws, key=lambda w: ((w[1]+w[3])/2, w[0])):
        y = (w[1]+w[3])/2
        target = next((line for line in reversed(lines[-3:]) if abs(line[0]-y) < 2.4), None)
        if target is None:
            lines.append([y, [w]])
        else:
            target[1].append(w)
    return [(y, ' '.join(w[4] for w in sorted(items, key=lambda w: w[0]))) for y, items in lines]


def cell(page, x0, x1, y0, y1):
    return '\n'.join(text for _, text in word_lines(words(page, x0, x1, y0, y1)))


def rectangles(page, x0, x1, minimum=6):
    spans = set()
    for drawing in page.get_drawings():
        r = drawing['rect']
        if drawing.get('fill') is not None and abs(r.x0-x0) < 1 and abs(r.x1-x1) < 1 and r.height >= minimum:
            spans.add((round(r.y0, 1), round(r.y1, 1)))
    return sorted(spans)


def parse_transocean(content, source):
    result = {}; current = None
    with pymupdf.open(stream=content, filetype='pdf') as pdf:
        for page in pdf:
            text = page.get_text()
            if 'Estimated Average Contract Dayrates' not in text or 'Rig Type/Name' not in text and 'Harsh Environment Semisubmersibles' not in text:
                continue
            typ = 'semi' if 'Harsh Environment Semisubmersibles' in text else 'drillship'
            # Report columns are detected from the colored header cells.
            headers = sorted({(round(d['rect'].x0,1),round(d['rect'].x1,1)) for d in page.get_drawings()
                              if d.get('fill') and d['rect'].y0 < 150 and d['rect'].height > 6 and d['rect'].x0 >= 35})
            # Explicit current layout; fail closed if the publisher changes its page size.
            if abs(page.rect.width - 1224) > 2:
                raise ValueError('Transocean page layout changed')
            cuts = [36,232.8,296.5,442.8,500.5,576.2,683.8,764.3,827.7,891.2,1008,1224]
            header_end = 165 if typ == 'drillship' else 72
            if typ == 'semi':
                candidates=[w[3] for w in page.get_text('words') if w[4]=='(7)']
                if candidates: header_end=max(candidates)+1
            for y, _ in word_lines(words(page,36,1200,header_end,600)):
                cells=[clean(cell(page,a,b,y-3.8,y+3.8)) for a,b in zip(cuts,cuts[1:])]
                name=cells[0]
                if name.startswith(('Deepwater ','Dhirubhai ','Petrobras ','Ocean Rig ','Transocean ')):
                    current=result.setdefault(name,rig('transocean',name,typ,source))
                elif name: continue
                if current is None: continue
                if re.fullmatch(r'20\d{2}', cells[3]):current['built']=int(cells[3])
                location,customer,status,start,end,rate,note=cells[4:]
                if not status:continue
                if status not in ('Firm','Contingent','Priced Option','Priced Options','Idle','Stacked','Out of Service'):
                    continue
                if not current['location'] and location not in ('-',''):current['location']=location
                if not current['status_reported']:current['status_reported']=status
                if status in ('Idle','Stacked','Out of Service'):
                    current['notes']=clean(current['notes']+' '+note)
                kind='firm' if status=='Firm' else 'option' if status.startswith('Priced') else 'contingent' if status=='Contingent' else 'maintenance'
                value=int(rate.replace(',','')) if re.fullmatch(r'[\d,]+',rate) else None
                if start and end and end!='-':
                    current['contracts'].append(contract(current['id'],customer,location,start,end,value,kind,note,source))
    if not 20 <= len(result) <= 40: raise ValueError(f'Transocean rig count {len(result)}')
    return list(result.values())


def parse_seadrill(content, source):
    result=[]; category=''; cuts=[30,130,183.6,256.2,326.5,412,466.4,517.5,930]
    with pymupdf.open(stream=content,filetype='pdf') as pdf:
        for page in pdf:
            if 'Fleet Contract Status' not in page.get_text():continue
            if abs(page.rect.width-960)>2:raise ValueError('Seadrill layout changed')
            lines=sorted({round(d['rect'].y0,1) for d in page.get_drawings() if d['rect'].width>890 and d['rect'].height<1})
            for y0,y1 in zip(lines,lines[1:]):
                cells=[cell(page,a,b,y0+.2,y1-.2) for a,b in zip(cuts,cuts[1:])]
                name=clean(cells[0]); whole=clean(' '.join(cells))
                if name.startswith(('Drillships','Harsh Environment','Sonadrill','Stacked Rigs')):
                    category=name;continue
                if not name.startswith(('West ','Sevan ','Sonangol ')):continue
                name=re.sub(r'(?<=Libongos)1$|(?<=Quenguela)1$', '',name)
                typ='jackup' if 'CJ 70' in cells[2] else 'semi' if 'Semi' in cells[2] else 'drillship'
                item=rig('seadrill',name,typ,source,built=int(cells[1]) if cells[1].isdigit() else None,
                         location=clean(cells[3]),status_reported='Stacked' if category.startswith('Stacked') else 'Available' if 'Available' in cells[4] else 'Contracted',notes=clean(cells[7]))
                if category.startswith('Sonadrill'):
                    item['ownership_kind']='managed_jv';item['manager']='Seadrill / Sonadrill'
                    item['owner_group']='Sonangol' if name.startswith('Sonangol ') else 'Seadrill'
                    item['ownership_basis']='보고서 소유·관리 주석';item['notes']+=' · 일당 매출 대신 관리 수수료를 수취하는 관리 계약'
                starts=cells[5].splitlines();ends=cells[6].splitlines();customers=cells[4].splitlines()
                if len(starts)==len(ends) and starts and starts[0]!='-':
                    for n,(s,e) in enumerate(zip(starts,ends)):
                        if not date_range(s)['min'] or not date_range(e)['max']:continue
                        item['contracts'].append(contract(item['id'],customers[min(n,len(customers)-1)] if customers else '',item['location'],s,e,None,'firm',item['notes'],source))
                result.append(item)
    if not 13<=len(result)<=23:raise ValueError(f'Seadrill rig count {len(result)}')
    return result


def parse_borr(content,source):
    result=[]; cuts=[27,119.7,221.3,269,312,401.2,490.6,584,692,804]
    with pymupdf.open(stream=content,filetype='pdf') as pdf:
        for page in pdf:
            if not all(s in page.get_text() for s in ('Rig Name','Year Built','Contract Start','Contract End')):continue
            if abs(page.rect.width-841.92)>2:raise ValueError('Borr layout changed')
            colored=rectangles(page,27.4,118.8,10)
            anchors=[(w[1]+w[3])/2 for w in words(page,269,312,90,550) if re.fullmatch(r'20\d{2}',w[4])]
            bounds=[]
            for y in anchors:
                containing=next(((a,b) for a,b in colored if a<y<b),None)
                before=[b for a,b in colored if b<y];after=[a for a,b in colored if a>y]
                bounds.append(containing or (max(before) if before else y-8,min(after) if after else y+8))
            for y0,y1 in bounds:
                cells=[cell(page,a,b,y0+.1,y1-.1) for a,b in zip(cuts,cuts[1:])]
                name=clean(cells[0]);year=clean(cells[3])
                if not re.fullmatch(r'20\d{2}',year) or not name:continue
                if not name.startswith('Prospector '):name=re.sub(r' [1-4]$', '',name)
                # Prospector 1/5 have their own trailing superscript note.
                name=re.sub(r'^(Prospector [15]) [1-4]$',r'\1',name)
                item=rig('borr',name,'jackup',source,built=int(year),design=clean(cells[1]),location=clean(cells[7].splitlines()[0] if cells[7] else ''),notes=clean(cells[8]))
                depth=re.search(r'\d+',cells[2]);item['water_depth_ft']=int(depth[0]) if depth else None
                starts=cells[5].splitlines();ends=cells[6].splitlines();customers=cells[4].splitlines();locations=cells[7].splitlines();notes=cells[8].splitlines()
                item['status_reported']='Contracted' if starts and date_range(starts[0])['min'] else clean(cells[4]) or 'Available'
                for n,(s,e) in enumerate(zip(starts,ends)):
                    if not date_range(s)['min'] or not date_range(e)['max']:continue
                    note=notes[min(n,len(notes)-1)] if notes else ''
                    kind='loa' if 'LOA' in note else 'firm'
                    item['contracts'].append(contract(item['id'],re.sub(r' [2-4]$','',customers[min(n,len(customers)-1)]) if customers else '',locations[min(n,len(locations)-1)] if locations else '',s,e,None,kind,note,source))
                result.append(item)
    if not 24<=len(result)<=40:raise ValueError(f'Borr rig count {len(result)}')
    return result


def parse_valaris(content,source):
    result=[]
    with pymupdf.open(stream=content,filetype='pdf') as pdf:
        for page in pdf:
            text=page.get_text()
            if 'VALARIS' not in text or 'Delivered' not in text or 'Asset Category' not in text:continue
            if abs(page.rect.width-1008)>2:raise ValueError('Valaris layout changed')
            first_x=min(d['rect'].x1 for d in page.get_drawings() if d.get('fill') is not None and abs(d['rect'].x0-49.5)<.2 and d['rect'].width>70 and d['rect'].height>7)
            if abs(first_x-135.8)<1:cuts=[49.5,138.8,222,270,335.2,403.5,456.8,510,560.2,958.5]
            elif abs(first_x-134.2)<1:cuts=[49.5,137.2,220.5,278.2,353.2,420,477.8,535.5,590.2,958.5]
            elif abs(first_x-152.2)<1:cuts=[49.5,155.2,256.5,314.2,387,459.8,517.5,575.2,958.5]
            elif abs(first_x-159.8)<1:cuts=[49.5,162.8,265.5,323.2,396,468.8,526.5,584.2,639,958.5]
            else:raise ValueError('Valaris column layout changed')
            colored=rectangles(page,49.5,first_x,7)
            anchors=[(w[1]+w[3])/2 for w in page.get_text('words') if w[4]=='VALARIS' and w[0]<60]
            bounds=[]
            for y in anchors:
                containing=next(((a,b) for a,b in colored if a<y<b),None)
                before=[b for a,b in colored if b<y];after=[a for a,b in colored if a>y]
                bounds.append(containing or (max(before) if before else y-6,min(after) if after else y+20))
            for y0,y1 in bounds:
                cells=[cell(page,a,b,y0+.2,y1-.2) for a,b in zip(cuts,cuts[1:])]
                if len(cells)==8:cells.insert(7,'')
                name=clean(cells[0])
                if not re.fullmatch(r'VALARIS [A-Za-z0-9-]+',name):continue
                typ='drillship' if ' DS-' in name else 'semi' if ' MS-' in name else 'jackup'
                item=rig('valaris',name,typ,source,built=int(cells[2]) if cells[2].isdigit() else None,design=clean(cells[1]),
                         location=clean(cells[4].splitlines()[0] if cells[4] else ''),notes=clean(cells[8]))
                item['status_reported']='Stacked' if 'stacked' in cells[8].lower() or not cells[3] and not cells[5] else 'Contracted'
                starts=cells[5].splitlines();ends=cells[6].splitlines();customers=cells[3].splitlines();locations=cells[4].splitlines();rates=cells[7].splitlines()
                # A blank status line can precede a future contract (e.g. DS-15).
                for n,(s,e) in enumerate(zip(starts,ends)):
                    if not date_range(s)['min'] or not date_range(e)['max']:continue
                    note=item['notes'];kind='loa' if n==0 and note.startswith('LOA') else 'firm'
                    raw_rate=rates[min(n,len(rates)-1)] if rates else ''
                    value=int(re.sub(r'[$,]','',raw_rate)) if re.fullmatch(r'\$[\d,]+',raw_rate) else None
                    item['contracts'].append(contract(item['id'],customers[min(n,len(customers)-1)] if customers else '',locations[-len(starts)+n] if len(locations)>len(starts) else locations[min(n,len(locations)-1)] if locations else '',s,e,value,kind,note,source))
                result.append(item)
    if not 35<=len(result)<=55:raise ValueError(f'Valaris rig count {len(result)}')
    return result


def parse_odfjell_fleet(content,source):
    soup=BeautifulSoup(content,'html.parser');result=[]
    for a in soup.select('a.fleet-rig'):
        name=clean(a.select_one('.fleet-rig__title').get_text())
        values=[clean(x.get_text()) for x in a.select('.fleet-rig__spec-value')]
        if len(values)!=3:raise ValueError('Odfjell fleet columns changed')
        item=rig('odfjell',name,'semi',source,built=int(values[0]),location=values[2],status_reported='회사 선대 페이지',detail_url=a['href'])
        item['customer_reported']=values[1]
        if name in ('Deepsea Yantai','Deepsea Mira','Hercules'):
            item['ownership_kind']='managed';item['owner_group']={'Deepsea Yantai':'CIMC', 'Deepsea Mira':'Northern Ocean','Hercules':'SFL'}[name]
            item['ownership_basis']='별도 소유·관리 공시 대조';item['notes']='타사 소유 · Odfjell 관리'
        result.append(item)
    if not 5<=len(result)<=12:raise ValueError(f'Odfjell fleet count {len(result)}')
    return result


def parse_market(content,year=None):
    """Parse published activity-month paragraphs, not the page's publication month."""
    soup=BeautifulSoup(content,'html.parser');text=soup.get_text(' ',strip=True)
    if year is None:
        meta=soup.select_one('meta[property="article:published_time"]')
        if not meta or not re.match(r'20\d{2}-',meta.get('content','')):raise ValueError('Market publication year missing')
        year=int(meta['content'][:4])
    small={'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9','ten':'10','eleven':'11','twelve':'12','thirteen':'13','fourteen':'14','fifteen':'15'}
    text=re.sub(r'\b('+ '|'.join(small)+r')\b',lambda m:small[m[0].lower()],text,flags=re.I)
    rows={}
    names={'jackup':'jackup','semisubmersible':'semi','drillship':'drillship'}
    pattern=r'The global committed (jackup|semisubmersible|drillship)(?: fleet| count)? (?:increased|decreased|remained).*?to (\d+) (?:units )?in ([A-Z][a-z]+)\.?(.+?)(?=The global committed|Finally,|Offshore Field|$)'
    # The publisher alternates "at" and "to" for unchanged counts.
    pattern=pattern.replace('to (\\d+)', '(?:to|at) (\\d+)')
    for m in re.finditer(pattern,text):
        typ,committed,month,tail=m.groups();month_num=MONTHS.get(month.lower())
        if month_num is None:continue
        av=re.search(r'(?:stand at|leaving|with)\s+(\d+)\s+(?:marketed (?:rigs )?available|marketed rigs available|marketed available|available)',tail)
        if not av:av=re.search(r'with\s+(\d+)\s+(?:marketed )?available',tail)
        cold=re.search(r'(?:and|plus)\s+(\d+)\s+cold[- ]stacked',tail)
        pair=re.search(r'stand at\s+(\d+)\s+and\s+(\d+)',tail)
        if pair:a,s=int(pair[1]),int(pair[2])
        elif av and cold:a,s=int(av[1]),int(cold[1])
        else:continue
        date=dt.date(year,month_num,calendar.monthrange(year,month_num)[1]).isoformat()
        if date>=collection_date():continue
        c=int(committed);k=(date,names[typ])
        rows[k]={'date':date,'type':names[typ],'committed':c,'available':a,'cold_stacked':s,
                 'marketed':c+a,'total':c+a+s,'committed_utilization':round(100*c/(c+a),1)}
    if len(rows)<3 or len({r['type'] for r in rows.values()})!=3:raise ValueError('Insufficient Westwood activity observations')
    return sorted(rows.values(),key=lambda r:(r['date'],r['type']))


def sec_quarters(facts,namespace,tag,unit='USD',since='2023-01-01'):
    data=facts.get('facts',{}).get(namespace,{}).get(tag,{}).get('units',{}).get(unit,[])
    direct={};cumulative={}
    for x in sorted(data,key=lambda r:(r.get('filed',''),r.get('accn',''))):
        if x.get('form') not in ('10-Q','10-K','20-F','40-F','6-K') or not x.get('start'):continue
        start,end=x['start'],x['end']
        if end<since or end>collection_date() or x.get('filed','')>collection_date():continue
        y=int(end[:4]);mo=int(end[5:7])
        if mo not in (3,6,9,12) or end!=qend(y,mo//3):continue
        days=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days
        val=x.get('val')
        if not isinstance(val,(float,int)) or isinstance(val,bool):continue
        obs={'value':val/1e6,'accn':x.get('accn'),'filed':x.get('filed'),'tag':tag,'namespace':namespace,'unit':'USD million','start':start}
        if 75<=days<=105 and start==f'{y}-{mo-2:02d}-01':direct[end]=obs
        if start==f'{y}-01-01' and 75<=days<=370:cumulative[end]=obs
    result=dict(direct)
    for end,x in cumulative.items():
        q=int(end[5:7])//3
        if end in result:continue
        if q==1:result[end]=x
        else:
            prior=qend(int(end[:4]),q-1);base=cumulative.get(prior)
            if base and base['start']==x['start']:
                result[end]={**x,'value':round(x['value']-base['value'],6),'derived':'同一年度累計差分','prior_accn':base['accn']}
    return result


FIN_TAGS={
 'revenue':[('us-gaap','Revenues'),('us-gaap','RevenueFromContractWithCustomerExcludingAssessedTax'),('ifrs-full','Revenue')],
 'operating_profit':[('us-gaap','OperatingIncomeLoss'),('ifrs-full','ProfitLossFromOperatingActivities')],
 'net_income':[('us-gaap','NetIncomeLoss'),('us-gaap','ProfitLoss'),('ifrs-full','ProfitLoss')],
 'operating_cash':[('us-gaap','NetCashProvidedByUsedInOperatingActivities'),('ifrs-full','CashFlowsFromUsedInOperatingActivities')],
 'capex':[('us-gaap','PaymentsToAcquirePropertyPlantAndEquipment'),('ifrs-full','PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities')],
}


def parse_sec_financials(payload):
    metrics={}
    for key,tags in FIN_TAGS.items():
        merged={}
        for namespace,tag in reversed(tags):merged.update(sec_quarters(payload,namespace,tag))
        metrics[key]=merged
    if not metrics['revenue']:raise ValueError('Missing USD quarterly revenue')
    dates=sorted({d for metric in metrics.values() for d in metric})
    rows=[]
    for date in dates:
        row={'date':date,'metric_sources':{}}
        for key,data in metrics.items():
            if date in data:row[key]=data[date]['value'];row['metric_sources'][key]=data[date]
        if row.get('operating_cash') is not None and row.get('capex') is not None:
            row['fcf']=round(row['operating_cash']-row['capex'],6)
        rows.append(row)
    return rows


def parse_odfjell_financials(content,year,quarter,source):
    income=cash=''
    with pymupdf.open(stream=content,filetype='pdf') as pdf:
        for page in pdf:
            left=page.get_text(clip=pymupdf.Rect(0,0,page.rect.width/2,page.rect.height),sort=True)
            flat=clean(left)
            if 'Condensed Consolidated Income Statement' in flat and 'OPERATING PROFIT' in flat:income=left
            if 'Condensed Consolidated Statement of Cash Flows' in flat and 'NET CASH FLOW FROM OPERATING' in flat:cash=left
    if not income or not re.search(rf'Q{quarter}\s+{year%100}',income):raise ValueError('Odfjell quarter layout/year changed')
    def values(text,label):
        m=re.search(label+r'([^\n]*(?:\n[^\n]+)?)',text,re.I)
        if not m:raise ValueError('Odfjell financial row missing: '+label)
        tokens=re.findall(r'\(?-?\d[\d,]*\.\d+\)?',m[1])
        if len(tokens) not in (4,5):raise ValueError('Odfjell financial columns changed: '+label)
        return [float(x.replace(',','').replace('(','-').replace(')','')) for x in tokens]
    metrics={}
    for key,label in [('revenue','OPERATING REVENUE'),('operating_profit',r'OPERATING PROFIT \(EBIT\)'),('net_income','NET PROFIT'),('ebitda',r'\bEBITDA')]:
        metrics[key]=values(income,label)
    if cash:
        metrics['operating_cash']=values(cash,r'NET CASH FLOW FROM OPERATING\s+ACTIVITIES')
        metrics['capex']=[-v for v in values(cash,r'Purchase of property, plant and\s+equipment')]
    rows={qend(year,quarter):{'date':qend(year,quarter),'source':source,'ebitda_label':'공시 EBITDA'},qend(year-1,quarter):{'date':qend(year-1,quarter),'source':source,'ebitda_label':'공시 EBITDA'}}
    for key,vs in metrics.items():
        rows[qend(year,quarter)][key]=vs[0];rows[qend(year-1,quarter)][key]=vs[1]
        if quarter==2 and len(vs)==5:
            for y,at in ((year,0),(year-1,1)):
                r=rows.setdefault(qend(y,1),{'date':qend(y,1),'source':source,'ebitda_label':'공시 EBITDA','derivation':'동일 보고서 상반기 누적−2분기'})
                r[key]=round(vs[at+2]-vs[at],6)
    for row in rows.values():
        if row.get('operating_cash') is not None and row.get('capex') is not None:row['fcf']=round(row['operating_cash']-row['capex'],6)
    return list(rows.values())


def coverage(item,as_of,months):
    """Conservative lower bound. Month/quarter boundaries are not exact dates."""
    if not any(c['kind']=='firm' and c['start']['max'] and c['end']['min'] for c in item['contracts']) and item['status_reported'] not in ('Available','Idle','Stacked'):
        return None
    start=dt.date.fromisoformat(as_of);m=start.month-1+months
    end=dt.date(start.year+m//12,m%12+1,min(start.day,calendar.monthrange(start.year+m//12,m%12+1)[1]))
    intervals=[]
    for c in item['contracts']:
        if c['kind']!='firm' or not c['start']['max'] or not c['end']['min']:continue
        a=max(start,dt.date.fromisoformat(c['start']['max']));b=min(end,dt.date.fromisoformat(c['end']['min']))
        if b>a:intervals.append((a,b))
    merged=[]
    for a,b in sorted(intervals):
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    return round(100*sum((b-a).days for a,b in merged)/(end-start).days,1)


def snapshot(item,today):
    item=copy.deepcopy(item);asof=max((s.get('as_of','') for s in item['sources']),default='') or today
    item['as_of']=asof
    item['contracts']=list({c['id']:c for c in item['contracts']}.values())
    live=[c for c in item['contracts'] if c['kind']=='firm' and c['start']['min'] and c['end']['max'] and c['start']['min']<=asof<=c['end']['max']]
    future=sorted([c for c in item['contracts'] if c['kind']=='firm' and c['start']['min'] and (c['start']['min']>asof or not c['end']['max'] and c['start']['max']>=asof)],key=lambda c:c['start']['min'])
    current=live[0] if live else None
    item['current_contract']=current
    item['next_contract']=future[0] if future else None
    if item.get('retired') or 'sold' in item['status_reported'].lower():item['status']='매각·퇴역'
    elif item['status_reported']=='Held for sale':item['status']='매각 대기'
    elif current:
        item['location']=current['location'] or item['location']
        item['status']='계약 중'
    elif 'stack' in item['status_reported'].lower():item['status']='계선'
    elif future:item['status']='후속 계약 확보'
    elif item['status_reported']=='Out of Service':item['status']='정비·준비'
    elif item['status_reported'] in ('Available','Idle'):item['status']='대기'
    elif any(c['kind']=='firm' for c in item['contracts']):item['status']='계약 기간 일부 미확인'
    elif item.get('customer_reported'):item['status']='고객 확인 · 기간 미확인'
    else:item['status']='일정 미확인'
    item['coverage_12m']=coverage(item,asof,12)
    item['coverage_24m']=coverage(item,asof,24)
    item['coverage_basis']='설비 공시 기준일 · 공개된 확정 계약 · 불확실한 월/분기 경계를 제외한 보수적 하한'
    return item


def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=1),encoding='utf8');temporary.replace(path)


def build_documents(state):
    today=collection_date();fleets=state.get('fleets',{});rows=[]
    for company,data in fleets.items():
        for item in data.get('rows',[]):rows.append(snapshot(item,today))
    ids=[r['id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate rig identities')
    common={'source':'기업 공식 선대·실적 공시 / SEC / Westwood','fetched':state.get('checked'),
            'collection_status':state.get('collection_status',{}),'source_url':'https://deepwater.com/investors/fleet-status-report','stale_days':7}
    fleet={**common,'id':'offshore_fleet','name':'글로벌 해양 시추 리그','updated':max((r['as_of'] for r in rows),default=''),
           'rows':rows,'company_status':{k:{x:v for x,v in data.items() if x!='rows'} for k,data in fleets.items()},
           'companies':COMPANIES,'events':state.get('events',[]),
           'scope':'주요 6개 운영사의 공개 선대. 타사 관리·JV 포함, 매각·퇴역 별도. 전국·전세계 전체 선대 통계와 구분.',
           'coverage_note':'계약 커버리지는 각 설비의 공시 기준일에서 계산한 공개 확정 계약의 보수적 하한입니다. 미공개 계약과 옵션을 포함하지 않습니다.'}
    market={**common,'id':'offshore_market','name':'글로벌 해양 시추 수급','updated':max((r['date'] for r in state.get('market',[])),default=''),
            'rows':state.get('market',[]),'market_source':state.get('market_source'), 'fixtures':state.get('fixtures',[]),
            'market_status':state.get('market_status'), 'backlog_rows':state.get('market_backlog',[])}
    companies=[]
    supplements=state.get('financial_supplements',{})
    for key,company in COMPANIES.items():
        data=state.get('financials',{}).get(key,{})
        quarters={r['date']:copy.deepcopy(r) for r in data.get('rows',[])}
        for supplemental in supplements.get(key,[]):
            target=quarters.setdefault(supplemental['date'],{'date':supplemental['date']})
            for field,value in supplemental.items():
                if field not in target:target[field]=copy.deepcopy(value)
        companies.append({'id':key,**company,'quarters':sorted(quarters.values(),key=lambda r:r['date']),
                          'status':{k:v for k,v in data.items() if k!='rows'}})
    financial={**common,'id':'offshore_financials','name':'해양 시추 운영사 실적','updated':max((r['date'] for c in companies for r in c['quarters']),default=''),
               'companies':companies,'note':'USD 백만, 분기 실적. 회사 공시 EBITDA·조정 EBITDA를 구분합니다. FCF는 영업현금흐름−유형자산 현금취득액이며 인수·자산매각은 제외합니다.'}
    docs={'offshore_fleet':fleet,'offshore_market':market,'offshore_financials':financial}
    docs['offshore_backlog']={**common,'id':'offshore_backlog','name':'글로벌 확정 계약 잔여 기간','unit':'rig-years','frequency':'monthly',
      'source':'Westwood RigLogix 공개 월간 자료','source_url':state.get('market_source',{}).get('url',''),
      'updated':max((r['date'] for r in state.get('market_backlog',[])),default=''),
      'series':{label:[[r['date'],r[typ]] for r in state.get('market_backlog',[])] for typ,label in TYPES.items()},
      'default_series':list(TYPES.values()),'month_labels':True,'monthly_axis':True,'span_gaps':False,'change_mode':'none',
      'description':'공개 월간판의 잔여 계약일수 환산(리그·년). 달러 매출 잔고와 구분합니다. 관측된 두 시점만 표시합니다.'}
    for key,field,title,unit in [('utilization','committed_utilization','영업 대상 선대 계약 확보율','%'),('supply','marketed','영업 대상 리그 수','기')]:
        dates=sorted({r['date'] for r in market['rows']})
        series={label:[[date,next((r[field] for r in market['rows'] if r['type']==typ and r['date']==date),None)] for date in dates] for typ,label in TYPES.items()}
        docs['offshore_'+key]={**common,'id':'offshore_'+key,'name':title,'unit':unit,'frequency':'monthly',
          'source':'Westwood RigLogix 공개 월간 자료','source_url':state.get('market_source',{}).get('url',''),
          'updated':market['updated'],'series':series,'default_series':list(TYPES.values()),'span_gaps':False,
          'month_labels':True,'monthly_axis':True,'change_mode':'none',
          'description':'활동 기준월. 영업 대상은 계약 확보+영업 중 대기 리그이며 장기 계선은 제외합니다. 계약 확보에는 미래 계약이 포함돼 실제 작업 가동률과 다릅니다.'}
    return docs

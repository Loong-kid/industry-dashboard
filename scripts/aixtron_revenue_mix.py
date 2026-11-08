"""AIXTRON IR application shares are YTD equipment shares, never quarter shares."""
import copy,datetime as dt,hashlib,itertools,re
from collections import Counter
from urllib.parse import urljoin
import pymupdf
from bs4 import BeautifulSoup

LABELS={'opto':'광전자·통신','led':'LED·Micro LED','gan':'GaN 전력','sic':'SiC 전력','power':'전력전자 합산','other':'기타·R&D'}
DETAIL=['opto','led','gan','sic','other'];COMBINED=['opto','led','power','other']

def today():return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
def end_date(year,q):
    import calendar
    return f'{year}-{q*3:02d}-{calendar.monthrange(year,q*3)[1]}'
def period(year,q):return f'{["Q1","H1","9M","FY"][q-1]}/{year}'

def color_tokens(page):
    """Pair percentage labels with the legend colors, not PDF text order.

    Raw characters separate touching labels such as 6%2%. A one-to-one color
    assignment handles very narrow wedges whose text overlaps the next wedge.
    Ambiguous images fail closed instead of silently swapping GaN and SiC.
    """
    w,h=page.rect.width,page.rect.height;legend={};drawings=page.get_drawings()
    for key,text in [('opto','Optoelectronics'),('led','LED incl.'),('gan','GaN-Power'),('sic','SiC-Power'),('other','Other incl.')]:
        labels=[r for r in page.search_for(text) if w/3<r.x0<w*2/3 and r.y0>h*.68]
        paths=[p for p in drawings if p.get('fill') and 5<=p['rect'].width<=18 and 5<=p['rect'].height<=18 and any(abs((p['rect'].y0+p['rect'].y1-r.y0-r.y1)/2)<8 and 0<r.x0-p['rect'].x0<30 for r in labels)]
        if len(paths)!=1:raise ValueError('Application legend color not unique')
        legend[key]=tuple(round(c*255) for c in paths[0]['fill'])
    scale=1.5;pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False);parts=[]
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines',[]):
            chars=[c for span in line['spans'] for c in span['chars']];text=''.join(c['c'] for c in chars)
            for match in re.finditer(r'(\d+(?:\.\d+)?)%',text):
                rect=pymupdf.Rect(chars[match.start()]['bbox'])
                for char in chars[match.start()+1:match.end()]:rect|=pymupdf.Rect(char['bbox'])
                if not (w/3<rect.x0<w*2/3 and h*.2<rect.y0<h*.7):continue
                votes=Counter()
                for x in range(9):
                    for y in range(7):
                        rgb=pix.pixel(int((rect.x0+rect.width*(x+.5)/9)*scale),int((rect.y0+rect.height*(y+.5)/7)*scale))[:3]
                        for key,color in legend.items():
                            if max(abs(a-b) for a,b in zip(rgb,color))<=12:votes[key]+=1
                parts.append((match[1],votes))
    if len(parts)!=5:raise ValueError('Detailed application wedge labels changed')
    scores=sorted((sum(votes.get(key,0) for (_,votes),key in zip(parts,order)),order) for order in itertools.permutations(DETAIL))
    score,order=scores[-1]
    if score<75 or score-scores[-2][0]<12 or any(votes.get(key,0)<3 for (_,votes),key in zip(parts,order)):raise ValueError('Application wedge color ambiguous')
    return {key:(False,value) for (value,_),key in zip(parts,order)}

def extract_mix(data,url,year,q):
    """Use the CENTER pie only; left equipment and right regional pies differ."""
    with pymupdf.open(stream=data,filetype='pdf') as pdf:
        pages=[(i,p) for i,p in enumerate(pdf) if 'Revenue Analysis' in p.get_text()]
        if len(pages)!=1:raise ValueError('AIXTRON revenue analysis page not unique')
        index,page=pages[0];full=page.get_text();flat=re.sub(r'\s+',' ',full)
        token={1:'Q1',2:'H1',3:'9M',4:'FY'}[q]
        if not re.search(fr'{token}\s*/\s*(?:{year}|{str(year)[2:]})(?!\d)',flat):raise ValueError('AIXTRON mix period mismatch')
        if not re.search(r'end application\s*\(equipment only\)',flat,re.I):raise ValueError('Equipment-only mix denominator unconfirmed')
        if 'Rounded figures' not in full:raise ValueError('Mix rounding precision needs review')
        w,h=page.rect.width,page.rect.height
        words=[word for word in page.get_text('words') if w/3<word[0]<w*2/3 and 80<word[1]<h-40]
        center=page.get_text(clip=pymupdf.Rect(w/3,80,w*2/3,h-40))
        tokens=[(bool(m[1]),m[2]) for word in words for m in re.finditer(r'(<\s*)?(\d+(?:\.\d+)?)%',word[4])]
        if year>=2024:
            required=['Optoelectronics','LED','GaN-Power','SiC-Power','Other incl']
            if any(s not in center for s in required):raise ValueError('AIXTRON application legend changed')
            order=DETAIL;classification='gan_sic_separate'
            by_color=color_tokens(page);tokens=[by_color[k] for k in order]
        elif year in [2022,2023]:
            if not all(s in center for s in ['Power','Optoelectronics','LED','Other incl']):raise ValueError('Historical application legend changed')
            order=['power','opto','led','other'] if (year,q)==(2023,4) else ['led','power','opto','other']
            classification='power_combined'
        else:raise ValueError('Unreviewed application classification')
        if len(tokens)!=len(order):raise ValueError('Application percentage count changed')
        shares={}
        for key,(censored,value_text) in zip(order,tokens):
            v=float(value_text);precision=.5 if '.' not in value_text else .5*10**(-len(value_text.split('.')[1]))
            if not 0<=v<=100 or censored and v<=0:raise ValueError('Invalid application share')
            shares[key]=dict(value=None if censored else v,lower=0 if censored else max(0,v-precision),upper=v if censored else min(100,v+precision),display=('<' if censored else '')+value_text+'%',qualifier='less_than' if censored else 'rounded',rounding_pp=precision)
        lo=sum(s['lower'] for s in shares.values());hi=sum(s['upper'] for s in shares.values())
        if not lo<=100<=hi:raise ValueError('Application shares inconsistent with rounding')
        return dict(date=end_date(year,q),year=year,quarter=q,scope='year_to_date_equipment_revenue',classification=classification,shares=shares,url=url,pdf_page=index+1,printed_slide=index,fetched=today(),sha256=hashlib.sha256(data).hexdigest(),extraction='legend_color_geometry' if year>=2024 else 'visually_reviewed_historical_text_order',precision_note='Printed rounded percentages; do not normalize their sum to 100%')

def collect_mix(publications_html,get,backfill=False):
    links=[]
    for a in BeautifulSoup(publications_html,'html.parser').select('a[href]'):
        match=re.fullmatch(r'(Q1|H1|Q3|FY) (20\d{2}) RESULTS PRESENTATION',a.get_text(' ',strip=True))
        if not match:continue
        year=int(match[2]);q={'Q1':1,'H1':2,'Q3':3,'FY':4}[match[1]]
        links.append((year,q,urljoin('https://www.aixtron.com/',a['href'])))
    if not links:raise ValueError('No AIXTRON results presentations discovered')
    newest=max(y for y,_,_ in links);rows=[];errors=[]
    for year,q,url in sorted(set(links)):
        if year<2022 or not backfill and year<newest:continue
        try:rows.append(extract_mix(get(url).content,url,year,q))
        except Exception as error:errors.append(f'{year}Q{q}: {type(error).__name__}: {error}')
    return rows,errors

def combined_shares(record):
    shares=copy.deepcopy(record['shares'])
    if 'power' not in shares and all(k in shares for k in ['gan','sic']):
        a,b=shares['gan'],shares['sic']
        shares['power']=dict(value=None if a['value'] is None or b['value'] is None else a['value']+b['value'],lower=a['lower']+b['lower'],upper=a['upper']+b['upper'],display=a['display']+' + '+b['display'],qualifier='sum_of_disclosed_shares')
    return shares

def revenue_rows(aix,mix,combined=False):
    financial={r['date']:r for r in aix};records={r['date']:r for r in mix};rows=[]
    keys=COMBINED if combined else DETAIL
    for date,record in sorted(records.items()):
        current=financial.get(date,{})
        if 'equipment_ytd' not in current:continue
        if not combined and record['classification']!='gan_sic_separate':continue
        year,q=record['year'],record['quarter'];previous_date=end_date(year,q-1) if q>1 else None
        previous=financial.get(previous_date,{}) if previous_date else None
        previous_mix=records.get(previous_date) if previous_date else None
        if q>1 and (not previous_mix or 'equipment_ytd' not in previous):continue
        shares=combined_shares(record) if combined else record['shares']
        prior_shares=(combined_shares(previous_mix) if combined else previous_mix['shares']) if previous_mix else {}
        sources=[dict(url=record['url'],pdf_page=record['pdf_page'],label=period(year,q)+' IR 비중'),dict(url=current['url'],pdf_page=current.get('refs',{}).get('equipment_ytd'),label=period(year,q)+' 누적 장비매출')]
        if previous_mix:sources += [dict(url=previous_mix['url'],pdf_page=previous_mix['pdf_page'],label=period(year,q-1)+' IR 비중'),dict(url=previous['url'],pdf_page=previous.get('refs',{}).get('equipment_ytd'),label=period(year,q-1)+' 누적 장비매출')]
        row=dict(date=date,year=year,quarter=q,url=record['url'],pdf_page=record['pdf_page'],fetched=record['fetched'],supporting_sources=sources,values={},bounds={},calculations={},notes=[])
        for key in keys:
            if key not in shares or q>1 and key not in prior_shares:continue
            s=shares[key];p=prior_shares.get(key);e=current['equipment_ytd'];ep=previous['equipment_ytd'] if previous else 0
            low=max(0,e-.05)*s['lower']/100-(ep+.05)*p['upper']/100 if p else max(0,e-.05)*s['lower']/100
            high=(e+.05)*s['upper']/100-max(0,ep-.05)*p['lower']/100 if p else (e+.05)*s['upper']/100
            value=e*s['value']/100-(ep*p['value']/100 if p else 0) if s['value'] is not None and (not p or p['value'] is not None) else None
            show=lambda share:'('+share['display']+')' if '+' in share['display'] else share['display']
            formula=f'{e:g} × {show(s)}'+(f' − {ep:g} × {show(p)}' if p else '')
            note='비중 < 값 공시 · 금액 범위만 확인' if value is None else ''
            if value is not None and value<0:
                note='반올림 누적 차분이 음수 · 분기 매출 미확정';value=None
            row['values'][key]=round(value,3) if value is not None else None
            row['bounds'][key]=dict(lower=round(max(0,low),3) if high>=0 else None,upper=round(high,3) if high>=0 else None,basis='share rounding and equipment ±0.05m; conditional range, not confidence interval')
            row['calculations'][key]=formula
            if note:row['notes'].append(LABELS[key]+': '+note)
        row['equipment']=round(current['equipment_ytd']-(previous['equipment_ytd'] if previous else 0),3)
        row['after_sales']=round(current['revenue_ytd']-current['equipment_ytd']-((previous['revenue_ytd']-previous['equipment_ytd']) if previous else 0),3)
        known=[row['values'].get(k) for k in keys]
        row['rounding_difference']=round(row['equipment']-sum(known),3) if all(v is not None for v in known) else None
        rows.append(row)
    return rows

def view(rows,keys,label,unit='백만 EUR',shares=False):
    series={LABELS[k]:[[r['date'],r.get('values',{}).get(k)] for r in rows] for k in keys}
    labels={r['date']:f"{r['year']} Q{r['quarter']}" for r in rows}
    notes={r['date']:['IR 반올림 비중 환산 추정 · 장비매출만 분모로 사용']+[LABELS[k]+': '+r['calculations'].get(k,'미공시') for k in keys]+r['notes']+([f"공시 장비 분기매출과 합계 차이 {r['rounding_difference']:g}백만 EUR · 비중 반올림을 보정하지 않음"] if r.get('rounding_difference') else []) for r in rows}
    refs={r['date']:dict(url=r['url'],pdf_page=r['pdf_page'],label=labels[r['date']],supporting_sources=r['supporting_sources'],source_separator=' / ') for r in rows}
    details={r['date']:{k:r[k] for k in ['equipment','after_sales','values','bounds','calculations','rounding_difference','notes'] if k in r} for r in rows if 'bounds' in r}
    return dict(label=label,frequency='quarterly',frequency_label='분기 · IR 비중 환산 추정',quarter_labels=True,series=series,default_series=list(series),updated=rows[-1]['date'],source_url=rows[-1]['url'],period_labels=labels,point_sources=refs,point_notes=notes,calculation_details=details,comparison_dates={r['date']:dict(year_ago=next((x['date'] for x in rows if x['year']==r['year']-1 and x['quarter']==r['quarter']),None),quarter_ago=next((x['date'] for x in rows if x['year']==r['year']-(r['quarter']==1) and x['quarter']==(r['quarter']-2)%4+1),None)) for r in rows})

def extend(docs,aix,records,status=None):
    if not records:return
    detailed=revenue_rows(aix,records);combined=revenue_rows(aix,records,True)
    if not detailed or not combined:raise ValueError('No compatible AIXTRON equipment/mix periods')
    latest=detailed[-1];fetched=latest['fetched']
    sales=docs['mocvd_aix_revenue'];quarter_view=copy.deepcopy(sales)
    quarter_view.update(label='분기',quarterly_revenue_summary=True)
    annual=[r for r in aix if r['quarter']==4 and 'equipment_ytd' in r and 'revenue_ytd' in r]
    annual_refs={r['date']:dict(url=r['url'],pdf_page=r.get('refs',{}).get('equipment_ytd'),label=f"FY{r['year']}") for r in annual}
    annual_view=dict(label='연간',frequency='yearly',frequency_label='연간 · 정기보고서',quarter_labels=False,year_labels=True,annual_axis=True,quarterly_revenue_summary=False,quarterly_profit_summary=False,
        series={'장비 매출':[[r['date'],r['equipment_ytd']] for r in annual],'서비스·부품 등':[[r['date'],round(r['revenue_ytd']-r['equipment_ytd'],3)] for r in annual]},default_series=['장비 매출','서비스·부품 등'],point_sources=annual_refs,period_labels={r['date']:f"FY{r['year']}" for r in annual},updated=annual[-1]['date'],source_url=annual[-1]['url'])
    sales.update(series_views=dict(quarter=quarter_view,annual=annual_view),default_view='quarter',basis_details=[dict(label='공시 매출 구분',value='장비 매출은 공식 보고서 금액, 부품·서비스 등 After Sales는 연결 매출−장비 매출입니다. 분기는 동일 회계연도 누적 차분, 연간은 정기보고서 연간 값입니다. IR 도넛의 반올림된 75%·25%를 곱해 장비·서비스 금액을 추정하지 않습니다.')])
    note='용도별 금액은 공시 장비매출 × IR의 반올림된 누적 비중으로 계산한 추정치입니다. Q2·Q3·Q4는 당기 누적 추정−직전 누적 추정입니다. 전체 매출에 비중을 곱하거나 분기 장비매출에 누적 비중을 곱하지 않습니다. 반올림 때문에 용도별 합계가 장비매출과 다를 수 있으며 100%로 재배분하지 않습니다. 광전자·통신은 InP 단독 매출이 아닙니다.'
    basis=[dict(label='금액과 출처',value=note),dict(label='공시 분류',value='2024년부터 GaN·SiC 개별 비중을 사용합니다. 2022~2023년 전력전자 합산은 상세 분할을 추정하지 않습니다. 2023년 <1% 공시와 음수가 나오는 반올림 차분은 금액을 확정하지 않고 공백으로 둡니다.'),dict(label='계산 확인',value='각 포인트의 출처에서 당기·직전 IR와 장비매출 공시를 확인할 수 있습니다. 원자료 상태에 인쇄된 비중·계산식·반올림 조건부 범위를 보존했습니다. 기존 연간 용도 매출 공시 카드는 그대로 유지합니다.')]
    identifier='mocvd_aix_application_revenue'
    vv={'quarter':view(detailed,DETAIL,'분기 · GaN·SiC 상세'),'combined':view(combined,COMBINED,'분기 · 전력 합산')}
    docs[identifier]=dict(id=identifier,name='AIXTRON · 장비 용도별 분기 매출 (비중 환산 추정)',unit='백만 EUR',fetched=fetched,source='AIXTRON 공식 IR·정기보고서',description=note,basis_details=basis,span_gaps=False,compact_tooltip=True,table_limit=200,chart_type='bar',change_mode='none',series_views=vv,default_view='quarter',**{k:v for k,v in vv['quarter'].items() if k!='label'})
    share_views={}
    for detailed_only,label,key in [(True,'누적 · GaN·SiC 상세','detail'),(False,'누적 · 전력 합산','combined')]:
        keys=DETAIL if detailed_only else COMBINED;rows=[]
        for r in sorted(records,key=lambda r:r['date']):
            if detailed_only and r['classification']!='gan_sic_separate':continue
            ss=r['shares'] if detailed_only else combined_shares(r)
            rows.append(dict(r,values={k:ss[k]['value'] for k in keys},calculations={k:ss[k]['display'] for k in keys},notes=['연초부터 해당 공시일까지의 누적 비중 · 분기 단독 비중 아님'],supporting_sources=[dict(url=r['url'],pdf_page=r['pdf_page'],label=period(r['year'],r['quarter']))]))
        v=view(rows,keys,label);v.update(frequency_label='공시 시점 · 연중 누적 비중',period_labels={r['date']:period(r['year'],r['quarter']) for r in rows})
        v['point_notes']={r['date']:r['notes']+[LABELS[k]+': '+r['calculations'][k] for k in keys] for r in rows}
        share_views[key]=v
    identifier='mocvd_aix_application_share'
    docs[identifier]=dict(id=identifier,name='AIXTRON · 장비 용도별 누적 비중 (IR 원문)',unit='%',cumulative_periods=True,fetched=fetched,source='AIXTRON 공식 IR Presentation',description='공시된 연중 누적 장비매출 비중입니다. 분기 단독 비중·총매출 비중·장비 수주 비중과 구분합니다. 반올림으로 합계가 99~101% 등일 수 있으며 <1%는 0이나 1로 확정하지 않습니다.',basis_details=basis,span_gaps=False,compact_tooltip=True,table_limit=200,change_mode='none',series_views=share_views,default_view='detail',**{k:v for k,v in share_views['detail'].items() if k!='label'})
    table_rows=[]
    details={r['date']:r for r in detailed}
    for r in reversed(combined):
        d=details.get(r['date']);row=dict(company='AIXTRON',period=f"{r['year']} Q{r['quarter']}",equipment=f"{r['equipment']:,.1f}",after_sales=f"{r['after_sales']:,.1f}",basis=period(r['year'],r['quarter'])+((' − '+period(r['year'],r['quarter']-1)) if r['quarter']>1 else ''),url=r['url'],supporting_url=r['supporting_sources'][2]['url'] if r['quarter']>1 else '')
        for k in ['opto','led','gan','sic','power','other']:
            source=d if k in ['gan','sic'] else r
            value=source['values'].get(k) if source else None
            row[k]=f'약 {value:,.1f}' if value is not None else '미분리' if k in ['gan','sic'] and not d else '범위만 확인'
        if d:row['power']='— (GaN·SiC 분리)'
        table_rows.append(row)
    identifier='mocvd_aix_revenue_breakdown'
    docs[identifier]=dict(id=identifier,name='AIXTRON · 분기별 세부 매출표',description='단위: 백만 EUR. 장비·부품/서비스는 공시 금액의 누적 차분이며, 용도별 약 표시는 IR 반올림 비중 환산 추정입니다. 부품/서비스는 총매출−장비매출로 계산합니다.',columns=[['period','분기'],['equipment','장비'],['after_sales','부품·서비스'],['opto','광전자·통신 (추정)'],['led','LED·Micro LED (추정)'],['gan','GaN 전력 (추정)'],['sic','SiC 전력 (추정)'],['power','전력 합산 (구분류)'],['other','기타·R&D (추정)'],['basis','누적 차분 기준']],rows=table_rows,hide_company_filter=True,search_placeholder='2026 Q3, 2025…',note=note+' 표의 전력 합산은 개별 비중이 미공시된 과거 기간만 표시합니다. 확인되지 않은 금액을 0으로 채우지 않습니다.',fetched=fetched,updated=latest['date'])
    if status and not status.get('ok',True):
        for key in ['mocvd_aix_application_revenue','mocvd_aix_application_share','mocvd_aix_revenue_breakdown']:docs[key]['collection_status']=dict(ok=False,checked=status['checked'],message='일부 IR 확인 실패 · 기존 성공 이력 유지')

"""Build display tables from the two explicitly imported Google Sheets tabs."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'manual/ai-overview/sheet-snapshot.json'
PUBLIC=ROOT/'manual/ai-overview/public-models.json'
OUT=ROOT/'data/datacenter'


def letter(index):
    result=''
    while index:
        index,rem=divmod(index-1,26);result=chr(65+rem)+result
    return result


def display(cell):
    if 'formattedValue' in cell:return cell['formattedValue']
    value=cell.get('effectiveValue',{})
    return str(value.get('numberValue',value.get('stringValue','')))


def cell_data(cell):
    value=dict(text=display(cell))
    number=cell.get('effectiveValue',{}).get('numberValue')
    if number is not None:value['number']=number
    if cell.get('note'):value['note']=cell['note']
    links=[cell['hyperlink']] if cell.get('hyperlink') else []
    links.extend(run['format']['link']['uri'] for run in cell.get('textFormatRuns',[]) if run.get('format',{}).get('link',{}).get('uri'))
    if links:value['links']=list(dict.fromkeys(links))
    return value


def grid(sheet):
    rows={}
    for block in sheet.get('data',[]):
        for i,row in enumerate(block.get('rowData',[]),block.get('startRow',0)+1):
            target=rows.setdefault(i,{})
            for j,cell in enumerate(row.get('values',[]),block.get('startColumn',0)+1):target[j]=cell
    return rows


def table(sheet,key,title,start,end,views=None):
    source=grid(sheet);header=source[1]
    active=[i for i in range(start,end+1) if display(header.get(i,{})) or any(display(r.get(i,{})) for n,r in source.items() if n>1)]
    columns=[]
    for i in active:
        raw=display(header.get(i,{}));label=' '.join(raw.split()) or letter(i)
        if i==start:label='기업'
        if key=='video' and i==13:label='가격 · 원문 단위'
        width=104 if i==start else 210 if i==start+1 else 112 if i==start+2 else 84
        if key=='llm' and i in [6,7,8]:width=100
        if key=='llm' and i==9:width=210
        if key=='llm' and i>=10:width=100
        if key=='image' and i in [4,5]:width=310
        if key=='video' and i==13:width=290
        columns.append(dict(key=letter(i),index=i,label=label,source_label=raw,note=header.get(i,{}).get('note',''),width=width))
    rows=[];block=[];group=''
    def flush():
        if not block:return
        known=list(dict.fromkeys(r['raw_provider'] for r in block if r['raw_provider']))
        last=known[0] if known else ''
        for row in block:
            if row['raw_provider']:last=row['raw_provider']
            row['provider']=row['raw_provider'] or (known[0] if len(known)==1 else last)
            row['provider_derived']=not bool(row['raw_provider']) and bool(row['provider'])
            rows.append(row)
        block.clear()
    for n,raw in sorted(source.items()):
        if n==1:continue
        model=display(raw.get(start+1,{}))
        populated=any(display(raw.get(i,{})) for i in active)
        if not populated:flush();continue
        if not model:
            flush()
            if display(raw.get(start,{})):group=display(raw[start])
            continue
        cells={letter(i):cell_data(raw.get(i,{})) for i in active if display(raw.get(i,{})) or raw.get(i,{}).get('note') or raw.get(i,{}).get('hyperlink') or raw.get(i,{}).get('textFormatRuns')}
        block.append(dict(id=f'{key}-r{n}',source_row=n,raw_provider=display(raw.get(start,{})),model=model,group=group,cells=cells))
    flush()
    available={c['key'] for c in columns}
    views=views or [('all','전체 열',[c['key'] for c in columns])]
    unit_note={'llm':'입력·출력 가격은 1M token 기준입니다. 점수와 평가 조건은 시트 기재값입니다.',
      'image':'가격은 구독·토큰·크레딧 등 원문 단위입니다. 모델별 상세에서 가격 조건을 확인하세요.',
      'video':'가격은 초·클립·크레딧 등 원문 단위입니다. 서로 다른 과금 기준을 환산하지 않았습니다.'}[key]
    return dict(id=key,title=title,unit_note=unit_note,provider_key=letter(start),model_key=letter(start+1),date_key=letter(start+2),columns=columns,
        views=[dict(id=id,label=label,keys=[k for k in keys if k in available]) for id,label,keys in views],rows=rows)


def model_key(name):
    return re.sub(r'[^a-z0-9]', '', name.casefold())


def merge_public_models(table, public):
    """Add public releases to the existing provider blocks and spreadsheet columns."""
    rows=table['rows']
    version=public['index_version']
    reviewed=public['imported']
    aliases={'SpaceXAI':'xAI / SpaceXAI','Moonshot AI':'Moonshot'}
    for model in sorted(public['models'],key=lambda item:item['release']):
        provider=aliases.get(model['provider'],model['provider'])
        matches=[row for row in rows if row['provider']==provider and model_key(row['model'])==model_key(model['name'])]
        if len(matches)>1:
            raise ValueError(f"Ambiguous AI Overview row for {model['name']}")
        if matches:
            row=matches[0]
        else:
            group_name='중국' if provider in ('DeepSeek','Moonshot') else ''
            row=dict(id='llm-public-'+model['id'],raw_provider=provider,provider=provider,provider_derived=False,
                     model=model['name'],group=group_name,cells={})
            end_of_group=next((i for i,r in enumerate(rows) if r['group']=='중국'),len(rows)) if not group_name else len(rows)
            index=next((i for i,r in enumerate(rows) if r['provider']==provider and r['group']==group_name),end_of_group)
            rows.insert(index,row)

        cells=row['cells']

        def set_cell(key,text,url,note='',number=None):
            original=cells.get(key)
            cell=dict(text=text,public=True,note=' · '.join(filter(None,[f'공개 자료 확인 {reviewed}',note])),links=[url])
            if number is not None:
                cell['number']=number
            if original:
                cell['original']=original
            cells[key]=cell

        if not row.get('source_row'):
            set_cell('B',model['name'],model['release_url'],model['api_id'])
            set_cell('C',model['release'],model['release_url'],model.get('release_note',''))
        price=model['price']
        for key,field in [('D','input'),('E','output')]:
            value=price.get(field)
            if value is not None:
                money=f'${value:,.2f}' if round(value,2)==value else f'${value:,}'
                set_cell(key,money,price['url'],
                         ' · '.join(filter(None,[price['basis'],price.get('note')])),value)

        bench=model.get('benchmark')
        memo=[]
        if price.get('cache') is not None:
            memo.append(f"캐시 읽기 ${price['cache']:g}/100만")
        if bench:
            memo.append(f"AA 과제당 ${bench['cost']:g} ({bench['effort']})")
            values=[bench,*bench.get('other_efforts',[])]
            effort_note=' / '.join(f"{value['effort']} {value['score']}점 · ${value['cost']:g}" for value in values)
            best=max(values,key=lambda value:value['score'])
            by_effort={value['effort']:value for value in values}
            for key,value in [('J',best),('K',by_effort.get('medium')),('L',by_effort.get('high'))]:
                if value:
                    note=f"AA {version} · {value['effort']} · 과제당 ${value['cost']:g}"
                    if key=='J':
                        note+=' · 확인한 설정 중 최고 점수'
                        if len(values)>1:
                            note+='\n설정별 점수·과제당 비용 '+effort_note
                    if bench.get('note'):
                        note+=' · '+bench['note']
                    set_cell(key,f"{value['score']} · {version.split('.')[0]}",bench['url'],note,value['score'])
        else:
            memo.append('AA 지수 미확인')
        set_cell('I',' · '.join(memo),price['url'],' · '.join(filter(None,[price['basis'],price.get('note')])))
        if bench and bench['url']!=price['url']:
            cells['I']['links'].append(bench['url'])

    table['unit_note'] = f'입력·출력은 USD/100만 토큰 기준입니다. v5 표시는 AA {version} 점수입니다. 시트의 v4.3.x 점수와 평가 구성이 다릅니다.'


AA_SOURCE=ROOT/'manual/ai-overview/aa-leaderboard.json'
# Sheet columns that already hold Artificial Analysis runs; blanks are filled from the snapshot.
AA_FILL={'M':'humanitys-last-exam','N':'terminalbench-4-0','O':'scicode','P':'automationbench-aa'}
# Current AA evaluations (Intelligence Index v5.0.1 components + GDPval-AA) the sheet has no column for.
AA_COLUMNS=[
    ('aa_gdpval','GDPval-AA (Elo)','gdpval-aa-normalized','elo',
     'GDPval-AA v2.1. OpenAI GDPval 데이터(미국 GDP 주요 산업 44개 직업의 실제 업무)를 Artificial Analysis가 평가해 Elo로 비교. DeepSeek V4.1 Flash (max)를 1600으로 고정. 높을수록 좋음. v5.0부터 Intelligence Index에서 빠진 단독 평가.'),
    ('aa_briefcase','AA-Briefcase (Elo)','aa-briefcase','elo',
     'AA-Briefcase v1.1. 업계 전문가가 만든 여러 주짜리 지식노동 프로젝트(연결된 과제 다수, 원자료 수천 개)를 수행하는 평가. Elo, 높을수록 좋음. AA Intelligence Index v5 비중 15%.'),
    ('aa_frontiercode','FrontierCode-AA 2.0','frontiercode-2-0','pct',
     'FrontierCode-AA 2.0. Cognition이 오픈소스 관리자들과 만든 코딩 평가. 실제 저장소 변경이 관리자가 병합할 수준인지 테스트와 채점 기준으로 판정(132과제). AA Intelligence Index v5 비중 15%.'),
    ('aa_gdppdf','GDP.pdf','gdp-pdf','pct',
     'GDP.pdf (Surge AI). 10개 전문 분야의 실제 PDF 문서(4,592쪽)를 읽고 과제별 기준을 충족하는지 보는 평가(100과제·기준 1,275개). AA Intelligence Index v5 비중 5%.'),
    ('aa_hle_diamond','HLE-Diamond','hle-diamond','pct',
     "HLE-Diamond. Humanity's Last Exam을 정제한 1,000문항판(추론 500·지식 500), 도구 없이 평가. 기존 HLE 열과 문항이 다름. AA Intelligence Index v5 비중 10%."),
    ('aa_critpt','CritPt v2 Hard','critpt-v2-hard','pct',
     'CritPt v2 Hard Subset. 연구 수준 물리 문제 70개 중 출시 당시 최상위 모델들이 모두 푼 30개를 뺀 40문항의 정답률. AA Intelligence Index v5 비중 10%.'),
    ('aa_tbsci','Terminal-Bench Science (AA)','terminal-bench-science','pct',
     'Terminal-Bench-Science 0.1. 스탠퍼드·Terminal-Bench 팀이 만든 과학 연구 터미널 작업(생명·물리·수학·공학·지구과학)을 Artificial Analysis가 직접 돌린 값. 제공사 발표값 열(Terminal-Bench Science 0.1)과 구분. AA Intelligence Index v5 비중 15%.'),
    ('aa_omniscience','AA-Omniscience 지수','omniscience-index','index',
     'AA-Omniscience v1.1. 지식·환각 평가(3,000문항). 정확한 지식은 가점, 틀린 추측은 감점하는 지수로 높을수록 좋음. AA Intelligence Index v5 비중 15%.'),
]


def model_aliases(name):
    keys={model_key(name)}
    keys.add(model_key(re.sub(r'\s*\((?:reasoning|preview)\)$','',name,flags=re.I)))
    keys.add(model_key(re.sub(r'\s+preview$','',name,flags=re.I)))
    return keys


def merge_aa_leaderboard(table,aa):
    """Fill blank AA benchmark cells and add current AA evaluations from one leaderboard snapshot."""
    when=aa['retrieved'];url=aa['source']
    index={}
    for release in aa['releases']:
        for key in model_aliases(release['name'])|{model_key(release['slug'])}:
            index.setdefault(key,release)
    def best(release,metric):
        found=[(v['scores'][metric],v['name']) for v in release['variants'] if metric in v['scores']]
        return max(found) if found else (None,None)
    def cell(value,kind,variant,count,metric_note=''):
        if kind=='pct':text,number=f'{value*100:.1f}%',round(value,4)
        elif kind=='sheet_pct':text,number=f'{value*100:.0f}%',round(value,4)
        elif kind=='elo':text,number=f'{value:,.0f}',round(value,2)
        elif kind=='index':text,number=f'{value:.1f}',round(value,2)
        else:text,number=f'{value:.0f} · v5',round(value)
        note=f'Artificial Analysis 리더보드 {when} 확인 · {variant}'
        if count>1:note+=f' · 설정 {count}개 중 최고값'
        if metric_note:note+=' · '+metric_note
        return dict(text=text,number=number,public=True,note=note,links=[url])
    existing={c['key'] for c in table['columns']}
    for key,label,_,kind,note in AA_COLUMNS:
        if key not in existing:
            table['columns'].append(dict(key=key,label=label,source_label=label,note=note+f' 출처: Artificial Analysis ({url}), {when} 확인.',
                                         width=108,added=True))
    for row in table['rows']:
        release=next((index[k] for k in model_aliases(row['model']) if k in index),None)
        if not release:continue
        cells=row['cells']
        count=lambda metric:sum(1 for v in release['variants'] if metric in v['scores'])
        for key,metric in AA_FILL.items():
            value,variant=best(release,metric)
            if value is not None and not cells.get(key,{}).get('text'):
                cells[key]=cell(value,'sheet_pct',variant,count(metric),'시트 빈칸을 AA 값으로 채움')
        v5_note=f"AA {aa['index_version']} 점수. 시트의 v4.3.x 점수와 평가 구성이 다름"
        value,variant=best(release,'intelligence-index')
        current=cells.get('J',{})
        if value is not None and (not current.get('text') or (current.get('public') and current['text'].endswith('v5') and round(value)>current.get('number',0))):
            cells['J']=cell(value,'v5',variant,count('intelligence-index'),v5_note)
            if current.get('text'):
                cells['J']['note']+=f" · 이전 공개 자료 값 {current['text']}(확인한 설정 중 최고였음)"
                if current.get('original'):cells['J']['original']=current['original']
        for key,effort in [('K','medium'),('L','high')]:
            found=[(v['scores']['intelligence-index'],v['name']) for v in release['variants']
                   if 'intelligence-index' in v['scores'] and v['effort'].split(',')[0].strip().lower()==effort]
            if found and not cells.get(key,{}).get('text'):
                value,variant=max(found)
                cells[key]=cell(value,'v5',variant,1,v5_note)
        for key,_,metric,kind,_ in AA_COLUMNS:
            value,variant=best(release,metric)
            if value is not None:cells[key]=cell(value,kind,variant,count(metric))
    keys=[c[0] for c in AA_COLUMNS]
    views={v['id']:v for v in table['views']}
    views['summary']['keys']=list('ABCDE')+['J','M','N','P','aa_gdpval','AA','AO']
    views['core']['keys']=[k for k in views['core']['keys']]+keys
    views['all']['keys']=[k for k in views['all']['keys']]+keys
    table['views'].insert(next(i for i,v in enumerate(table['views']) if v['id']=='extended'),
        dict(id='aa_v5',label='AA v5 평가 항목',keys=list('ABC')+['J','aa_briefcase','P','aa_gdppdf','aa_frontiercode','N','aa_omniscience','aa_hle_diamond','aa_critpt','aa_tbsci','aa_gdpval']))
    table['unit_note']+=f' AA 표시 열은 Artificial Analysis 리더보드({when} 확인)의 설정별 최고값입니다. 단종 모델은 리더보드에 없어 빈칸입니다.'


VALS_SOURCE=ROOT/'manual/ai-overview/vals-index.json'


def merge_vals_index(table,vals):
    """Fill blank Vals Index cells (sheet column AA) from one Vals leaderboard snapshot; never overwrite sheet values."""
    index={}
    for item in vals['items']:
        index.setdefault(model_key(item['model']),item)
    for row in table['rows']:
        item=next((index[k] for k in model_aliases(row['model']) if k in index),None)
        if not item or row['cells'].get('AA',{}).get('text'):continue
        row['cells']['AA']=dict(text=f"{item['score']:.1f}%",number=round(item['score']/100,4),public=True,
            note=f"Vals Index {vals['version']} 순위표 ({vals['updated']} 기준, {vals['retrieved']} 확인) · {item['model']}. 시트 빈칸을 채운 값으로, 다른 셀과 버전이 다를 수 있음",
            links=[vals['source']])


EPOCH_SOURCE=ROOT/'manual/ai-overview/epoch-benchmarks.json'
# 2025-era comparison benchmarks from Epoch AI (own runs or collected official leaderboards).
EPOCH_COLUMNS=[
    ('e_gpqa','Epoch GPQA Diamond','gpqa','pct',
     'GPQA Diamond. 대학원 수준 생물·물리·화학 4지선다 198문항(찍으면 25%). 2024~2025 추론 모델 비교의 대표 지표였고 2026년 들어 90%대로 포화. Epoch AI가 같은 조건으로 직접 돌린 값.'),
    ('e_aime','Epoch AIME형 (OTIS)','aime','pct',
     'OTIS 모의 AIME 2024·2025 문제로 본 경시수학 점수. 2025년 모델 발표마다 나오던 AIME 2025 점수의 대용으로 Epoch AI가 직접 돌린 값. 공식 AIME 2025 점수와 문항이 다름.'),
    ('e_frontiermath','Epoch FrontierMath T1-3','frontiermath','pct',
     'FrontierMath Tier 1-3 (2025-02-28 비공개 문제판). 수학자들이 만든 연구 수준 수학 문제. 2025년 상위 모델 비교에 자주 쓰였고 2026-06에 새 문제판(v2)으로 바뀌어 이후 모델은 이 열에 없음. Epoch AI 직접 실행.'),
    ('e_swe','Epoch SWE-bench Verified','swe','pct',
     'SWE-bench Verified. 실제 GitHub 이슈 500개를 고쳐 테스트를 통과하는 비율. 2025년 코딩 성능의 대표 지표. Epoch AI가 같은 도구 환경으로 직접 돌린 값이라 제공사 발표값(SWE-bench Verified (Reported Best) 열)보다 보통 낮음.'),
    ('e_hle','HLE 외부 공개값','hle','pct',
     "Humanity's Last Exam. 2025년 1월 공개된 전문가 수준 고난도 문제 모음으로 2025년 최상위 모델 비교의 대표 지표. Epoch AI가 모은 외부 공개 결과로, Artificial Analysis 값(HLE (Best) 열)과 측정 주체가 다름."),
    ('e_arc1','ARC-AGI-1','arc1','pct',
     'ARC-AGI-1. 처음 보는 격자 퍼즐의 규칙을 몇 개 예시로 알아내는 일반화 평가. ARC Prize 순위표 값(Epoch AI 수집), 설정별 최고값.'),
    ('e_arc2','ARC-AGI-2','arc2','pct',
     'ARC-AGI-2. 2025년 3월 공개된 ARC-AGI 후속판으로 사람은 쉽게 풀지만 모델은 어려운 퍼즐. ARC Prize 순위표 값(Epoch AI 수집), 설정별 최고값.'),
    ('e_aider','Aider Polyglot','aider','pct',
     'Aider Polyglot. C++·Go·Java·JS·Python·Rust의 어려운 Exercism 문제 225개를 코드 편집으로 푸는 비율. 2025년 코딩 모델 비교에 자주 인용. Aider 순위표 값(Epoch AI 수집).'),
    ('e_metr','METR 작업 시간 (50%)','metr','minutes',
     'METR Time Horizon. 사람 전문가가 걸리는 시간으로 잰 소프트웨어 과제 중 모델이 50% 확률로 해내는 과제 길이. 2025년 "AI가 얼마나 긴 일을 하나"의 대표 지표. 셀마다 METR 버전이 다를 수 있음(Epoch AI 수집).'),
    ('e_simpleqa','Epoch SimpleQA','simpleqa','pct',
     'SimpleQA Verified. 짧은 사실 질문의 정확도로 환각을 보는 평가(2025-09 공개판). Epoch AI 직접 실행.'),
]


def epoch_base(version):
    """'claude-sonnet-4-5-20250929_32K' -> 'claudesonnet45'; 'gemini-2.5-flash-preview-05-20' -> 'gemini25flashpreview'."""
    name=version.split('_')[0]
    name=re.sub(r'-(20\d{2}-?\d{2}-?\d{2}|\d{4}|\d{2}-\d{2}|00\d)$','',name)
    return model_key(name)


def merge_epoch(table,epoch):
    """Add 2025-era benchmark columns from the Epoch AI snapshot; release dates guard same-name generations."""
    from datetime import date as _date
    def days(a,b):
        try:return abs((_date.fromisoformat(a)-_date.fromisoformat(b)).days)
        except ValueError:return 0
    existing={c['key'] for c in table['columns']}
    when=epoch['retrieved']
    for key,label,_,_,note in EPOCH_COLUMNS:
        if key not in existing:
            table['columns'].append(dict(key=key,label=label,source_label=label,width=108,added=True,
                note=note+f" 출처: Epoch AI 'Capabilities & benchmarking' (https://epoch.ai/benchmarks), CC BY 4.0, {when} 내려받음."))
    sheet_keys={model_key(r['model']) for r in table['rows']}
    indexes={}
    for bench,rows in epoch['benchmarks'].items():
        index={}
        for item in rows:
            exact=model_key(item['version'].split('_')[0])
            # A suffix that is part of a listed model name (e.g. 'DeepSeek V4.1 Flash 1017') is not a date stamp.
            base=exact if exact in sheet_keys else epoch_base(item['version'])
            index.setdefault(base,[]).append(item)
            if base.endswith('preview'):index.setdefault(base[:-7],[]).append(item)
        indexes[bench]=index
    for row in table['rows']:
        released=row['cells'].get('C',{}).get('text','')[:10]
        names={model_key(row['model'])}
        if row['model'].endswith(' v2'):names={model_key(row['model'][:-3])}
        for key,_,bench,kind,_ in EPOCH_COLUMNS:
            found=[i for n in names for i in indexes[bench].get(n,[]) if not i['release'] or len(released)<10 or days(i['release'],released)<=60]
            if not found:continue
            item=max(found,key=lambda i:i['score'])
            value=item['score']
            if kind=='minutes':
                text=f'{value:.0f}분' if value<60 else f'{value/60:.1f}시간'
                number=round(value,1)
            else:
                text,number=f'{value*100:.1f}%',round(value,4)
            label=item.get('name') or item['version']
            note=f"Epoch AI {when} 내려받음 · {label}"
            if len(found)>1:note+=f' · 설정 {len(found)}개 중 최고값'
            if item.get('metr_version'):note+=f" · {item['metr_version']}"
            row['cells'][key]=dict(text=text,number=number,public=True,note=note,links=['https://epoch.ai/benchmarks'])
    keys=[c[0] for c in EPOCH_COLUMNS]
    views={v['id']:v for v in table['views']}
    views['all']['keys']=views['all']['keys']+keys
    position=next(i for i,v in enumerate(table['views']) if v['id']=='legacy')
    table['views'].insert(position,dict(id='y2025',label='2025년 기준 벤치마크',
        keys=list('ABC')+['e_gpqa','T','e_aime','U','e_frontiermath','e_swe','S','e_hle','M','e_arc1','e_arc2','e_aider','e_metr','e_simpleqa']))


def build(snapshot,public=None,aa=None,vals=None,epoch=None):
    sheets={s['properties']['title']:s for s in snapshot['sheets']}
    llm=sheets['AI Overview'];media=sheets['AI Overview2']
    views=[('summary','요약',list('ABCDE')+['J','M','N']),('specs','가격·사양',list('ABCDEFGHI')),
      ('core','주요 벤치마크',list('ABC')+[letter(i) for i in range(10,19)]),
      ('extended','확장 벤치마크',list('ABC')+[letter(i) for i in range(27,46)]),
      ('legacy','기존 벤치마크',list('ABC')+[letter(i) for i in range(19,26)]),
      ('all','전체 열',[letter(i) for i in range(1,64)])]
    result={}
    for key,sheet,tables,title in [('dc_ai_overview',llm,[table(llm,'llm','언어모델 · 가격·사양·벤치마크',1,63,views)],'AI Overview'),
      ('dc_ai_overview2',media,[table(media,'image','이미지 AI',1,5),table(media,'video','영상 AI',10,17)],'AI Overview 2')]:
        source=dict(snapshot['spreadsheet'],sheet=sheet['properties']['title'],sheet_id=sheet['properties']['sheetId'])
        source['tab_url']=source['url']+'#gid='+str(source['sheet_id'])
        result[key]=dict(id=key,name=title,manual=True,updated=snapshot['imported'],fetched=snapshot['imported'],imported=snapshot['imported'],source=source,tables=tables,
          note='시트에 저장된 값·메모를 가져온 자료입니다. 빈칸은 미기재이며 0으로 채우지 않습니다. 시트 변경은 다음 재가져오기에 반영됩니다. 가격·벤치마크의 기준일·단위·평가 조건은 원문 메모를 확인해 주세요.')
    if public:
        doc=result['dc_ai_overview']
        merge_public_models(doc['tables'][0],public)
        doc['public_reviewed']=public['imported']
        doc['updated']=doc['fetched']=max(doc['imported'],doc['public_reviewed'])
        doc['note']='시트 자료와 공개 자료를 한 표에 표시합니다. 가격 조건·평가 설정·원본 시트 값은 셀을 눌러 확인할 수 있습니다.'
    if aa:
        doc=result['dc_ai_overview']
        merge_aa_leaderboard(doc['tables'][0],aa)
        doc['aa_reviewed']=aa['retrieved']
        doc['updated']=doc['fetched']=max(doc['updated'],aa['retrieved'])
    if vals:
        merge_vals_index(result['dc_ai_overview']['tables'][0],vals)
    if epoch:
        merge_epoch(result['dc_ai_overview']['tables'][0],epoch)
        result['dc_ai_overview']['epoch_reviewed']=epoch['retrieved']
    return result


if __name__=='__main__':
    snapshot=json.loads(SOURCE.read_text(encoding='utf-8'))
    public=json.loads(PUBLIC.read_text(encoding='utf-8'))
    aa=json.loads(AA_SOURCE.read_text(encoding='utf-8'))
    vals=json.loads(VALS_SOURCE.read_text(encoding='utf-8'))
    epoch=json.loads(EPOCH_SOURCE.read_text(encoding='utf-8'))
    for key,doc in build(snapshot,public,aa,vals,epoch).items():
        (OUT/(key+'.json')).write_text(json.dumps(doc,ensure_ascii=False,indent=1,allow_nan=False)+'\n',encoding='utf-8')
        print(key,[(t['id'],len(t['rows']),len(t['columns'])) for t in doc['tables']])

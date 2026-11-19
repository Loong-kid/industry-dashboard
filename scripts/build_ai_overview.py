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


def build(snapshot,public=None):
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
    return result


if __name__=='__main__':
    snapshot=json.loads(SOURCE.read_text(encoding='utf-8'))
    public=json.loads(PUBLIC.read_text(encoding='utf-8'))
    for key,doc in build(snapshot,public).items():
        (OUT/(key+'.json')).write_text(json.dumps(doc,ensure_ascii=False,indent=1,allow_nan=False)+'\n',encoding='utf-8')
        print(key,[(t['id'],len(t['rows']),len(t['columns'])) for t in doc['tables']])

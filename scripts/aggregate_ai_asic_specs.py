"""Import the ASIC block of Chip without inferring foundries from design partners."""
import json
from pathlib import Path
from aggregate_gpu_specs import base, column, validate_sources

ROOT=Path(__file__).resolve().parents[1]
COMPANIES=['Google','AWS','Meta','Microsoft','Baidu','Huawei','Intel']
COLUMNS=[column('name','칩 / 제품',190),column('date','출시·발표 / 시트 시점',150),column('date_basis','날짜 기준',155),
    column('company','공급사 / 빅테크',125),column('partner','설계 협력사 · 시트',175),column('foundry','제조 파운드리',120),
    column('node','공정',95),column('memory','메모리 종류',150),column('capacity','메모리 용량',130),
    column('bandwidth','메모리 대역폭',140),column('compute','연산 · 정밀도·조건별',270),column('scope','사양 단위',135),
    column('usage','주 용도',160),column('power','전력',100),column('clock','클럭',100),column('status','확인 범위',200)]


def build(raw,extra):
    if len(raw['values'])!=67 or raw['values'][33][1]!='ASICs' or raw['values'][0][1:4]!=['Chip supplier','Chip name','Design partner']:
        raise ValueError('Chip ASIC source layout changed')
    validate_sources(extra['sources'],extra['reviewed'])
    rows=[];company=''
    for number in range(35,68):
        v=[str(c or '') for c in raw['values'][number-1]]
        if len(v)>27 or len(v)<8 or not v[2]:raise ValueError('Invalid ASIC source row')
        v+=['']*(27-len(v))
        if v[1]:company=v[1]
        if not company:raise ValueError('Missing ASIC supplier context')
        original=dict(name=v[2],date=v[4],company=v[1],partner=v[3],node=v[5],memory=v[6],capacity=v[7])
        rows.append(dict(id=f'asic-sheet-{number}',sheet_row=number,source_values=v,name=v[2],company=company,
            group='빅테크 자체 칩' if company in ('Google','AWS','Meta','Microsoft','Baidu') else '기타 AI ASIC',original=original,reviews={},
            review_note='Chip 탭 ASICs 구간 원본입니다. NA·TBC·F와 범위값은 그대로 보존합니다. 헤더가 Capacity (GB)이더라도 칩·보드·시스템 범위가 확인되지 않은 원본은 단위를 확정하지 않습니다. 설계 협력사는 제조 파운드리를 뜻하지 않습니다.'))
    byrow={r['sheet_row']:r for r in rows};keys={c['id'] for c in COLUMNS}
    for cell in extra['cells']:
        row=byrow[cell['row']];key=cell['column']
        if row['name']!=cell['product'] or key not in keys or key in row['reviews']:raise ValueError('Moved or duplicate ASIC supplement')
        if cell['source'] not in extra['sources'] or not cell['note'] or not cell['value']:raise ValueError('Missing ASIC evidence')
        row['reviews'][key]={k:cell[k] for k in ('value','source','note')}
    # Company labels inherited from merged/blank cells are filter context, not original cell values.
    for row in rows:
        if 'company' in row['reviews']:
            row['company']=row['reviews']['company']['value']
            row['group']='빅테크 자체 칩'
        row['display_original']=dict(company=row['company'],date_basis='시트 전망 · 미검증' if row['original']['date'].endswith('F') else '시트 기재 시점 · 미검증',
            status='일부 셀 공식 확인 · 나머지 원본 미검증' if row['reviews'] else '시트 원본 · 개별 검증 전')
        if row['sheet_row']==39:
            row['review_note']+=' TPU v5는 v5e/v5p가 합쳐진 원본 행입니다. 16/96 값을 한 칩의 용량 범위로 비교하지 않습니다.'
        if row['sheet_row']==56:
            row['review_note']+=' B56은 공란이지만 제품명과 Microsoft 공식 발표로 소속을 교정했습니다.'
    rows.sort(key=lambda row:(COMPANIES.index(row['company']),row['sheet_row']))
    doc=base(raw,'ai_asic_specs','AI ASIC · 빅테크 자체 칩과 설계 협력사',
        'Chip 탭의 ASICs 33개 행을 옮겼습니다. NVIDIA·AMD 등 GPU 구간은 GPU 탭에서 봅니다. 설계 협력사와 제조 파운드리는 별도이며 미확인 파운드리는 비워 둡니다. 출시·발표 열은 날짜 기준과 함께 읽습니다. F는 시트의 과거 전망으로, 일정이 지나도 실제 출시로 간주하지 않습니다. 출처가 없는 공정·협력사·메모리 사양은 원본 기재값입니다. 연산 성능은 정밀도·희소성·칩/시스템 단위가 달라 단일 순위로 비교하지 않습니다. 원본 용량은 H열 헤더 기준 GB이며 칩 단위는 미검증입니다. 보완값의 GB·GiB·대역폭 단위를 그대로 유지합니다.')
    doc.update(table_family='asic',short_name='AI ASIC',updated=extra['reviewed'],columns=COLUMNS,rows=rows,name_key='name',
        default_group='all',default_view='overview',company_order=COMPANIES,
        views=[dict(id='overview',label='한눈에 보기',keys=['name','date','date_basis','partner','foundry','node','memory','capacity','status']),
            dict(id='performance',label='메모리·연산 사양',keys=['name','date','memory','capacity','bandwidth','compute','scope','usage','power','clock']),
            dict(id='all',label='전체 사양',keys=[c['id'] for c in COLUMNS])],sources=extra['sources'],group_label='기업 구분',item_label='프로파일',
        caption='칩·시스템 단위와 정밀도 확인 · 설계 협력사 ≠ 제조 파운드리',search_placeholder='TPU·Trainium·Maia·협력사 검색',
        evidence_summary=f"Chip 탭 ASICs 33개 행 · {len(extra['cells'])}개 값 공식 자료 확인 · 미확인·전망치는 원본 표시",
        scroll_hint='제품명 고정 · 행 높이 40px · 긴 값은 마우스 메모 · 상세는 맨 오른쪽')
    return doc


if __name__=='__main__':
    read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
    doc=build(read('ai_asic_chip_sheet.json'),read('ai_asic_supplements.json'))
    (ROOT/'data/semicon/ai_asic_specs.json').write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
    print(doc['id'],len(doc['rows']),'profiles')

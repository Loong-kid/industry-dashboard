"""Publish GPU comparisons without modifying the user's source-sheet values."""
import json
import re
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def column(key,label,width=110,**kwargs):
    return dict(id=key,label=label,width=width,**kwargs)


def base(raw,identifier,name,note):
    return dict(id=identifier,name=name,manual=True,frequency='irregular',updated=raw['imported'],fetched=raw['imported'],
        source='사용자 Google Sheets · '+raw['sheet_name'],source_url=raw['source_url'],source_range=raw['range'],note=note,
        update_note='원본 시트와 공개 자료를 검토해 갱신하는 스냅샷입니다. 표에 표시된 확인일 기준이며 자동 실시간 수집은 아닙니다.')


def validate_sources(sources,reviewed):
    for source in sources.values():
        if not source['url'].startswith('https://') or source['checked']>reviewed or not source['note']:
            raise ValueError('Invalid GPU evidence')


def validate_date(cell):
    value=cell['value']
    precision=cell.get('precision')
    patterns={'year':r'\d{4}','quarter':r'\d{4}-Q[1-4]','month':r'\d{4}-(?:0[1-9]|1[0-2])','day':r'\d{4}-\d{2}-\d{2}'}
    if precision not in patterns or not re.fullmatch(patterns[precision],value):raise ValueError('Invalid GPU date precision')
    if precision=='day':date.fromisoformat(value)
    if not cell.get('basis') or cell.get('status') not in ('announcement','availability','vendor_launch','scheduled','year_only'):raise ValueError('Missing GPU date basis')


def build_gpu(raw,extra,dates):
    headers=raw['values'][0]
    if len(headers)!=26 or headers[2]!='GPU 이름' or not headers[22].startswith('3DMark Time Spy'):
        raise ValueError('GPU source layout changed')
    keys=[chr(65+i) for i in range(26)]
    columns=[column(key,label,190 if i==2 else 170 if i in (7,8,23) else 110,numeric=i==22,url=i in (24,25)) for i,(key,label) in enumerate(zip(keys,headers))]
    columns[14].update(label='AI TOPS · 원본 정밀도 미검증',source_label=headers[14])
    columns[4].update(label='발표/출시일 · 시트 원본',source_label=headers[4])
    columns += [column('gb7_opencl','GB7 · OpenCL',110,numeric=True),column('gb7_vulkan','GB7 · Vulkan',110,numeric=True)]
    columns += [column('announced','발표일',110,date=True),column('released','출시일',124,date=True)]
    rows=[]
    for number,values in enumerate(raw['values'][1:],2):
        if not any(values):continue
        if len(values)>26 or len(values)<3 or not values[2]:raise ValueError('Invalid GPU row')
        values=[v or '' for v in values]+['']*(26-len(values))
        rows.append(dict(id=f'gpu-sheet-{number}',sheet_row=number,source_values=values,company=values[0],group=values[1],name=values[2],original=dict(zip(keys,values)),reviews={}))
    byrow={row['sheet_row']:row for row in rows}
    validate_sources(extra['sources'],extra['reviewed'])
    for cell in extra['cells']:
        row=byrow[cell['row']];key=cell['column']
        if row['name']!=cell['product'] or row['company']!=cell['company']:raise ValueError('GPU source row moved')
        if key not in {c['id'] for c in columns} or row['original'].get(key) or key in row['reviews']:raise ValueError('GPU supplement overwrites source')
        if cell['source'] not in extra['sources'] or not cell['note']:raise ValueError('Missing GPU evidence')
        if key.startswith('gb7_') and not re.fullmatch(r'\d+',cell['value']):raise ValueError('Invalid GPU score')
        row['reviews'][key]={k:cell[k] for k in ('value','source','note')}
    validate_sources(dates['sources'],dates['reviewed'])
    if set(dates['sources'])&set(extra['sources']):raise ValueError('Duplicate GPU source identifier')
    seen=set()
    for product in dates['products']:
        row=byrow[product['row']]
        if row['name']!=product['product'] or row['company']!=product['company'] or product['row'] in seen:raise ValueError('GPU date source row moved or duplicated')
        seen.add(product['row'])
        row['date_note']=product['unverified_announcement']
        for key,cell in product['fields'].items():
            if key not in ('announced','released') or cell['source'] not in dates['sources'] or not cell['note']:raise ValueError('Missing GPU date evidence')
            validate_date(cell)
            if (key=='announced')!=(cell['status']=='announcement'):raise ValueError('GPU date event mismatch')
            row['reviews'][key]=cell
    if seen!=set(byrow):raise ValueError('GPU date coverage changed')
    doc=base(raw,'gpu_specs','일반 GPU · 사양과 벤치마크',
        'Geekbench 7은 OpenCL·Vulkan을 각각 비교합니다. API·버전·드라이버가 다른 점수를 합치지 않습니다. Time Spy는 원본 시트의 대표·중앙값이며 재측정한 값이 아닙니다. 노트북 TGP·공유 메모리와 장치명별 집계 범위는 각 점수의 메모에서 확인하세요. 명확한 대응이 없는 점수는 빈칸입니다.')
    doc.update(columns=columns,rows=rows,name_key='C',default_group='all',default_view='overview',sources={**extra['sources'],**dates['sources']},updated=max(extra['reviewed'],dates['reviewed']),
        views=[dict(id='overview',label='한눈에 보기',keys=['C','released','F','P','S','T','W','gb7_opencl','gb7_vulkan','I','J','K','L','M','N','G']),
               dict(id='all',label='전체 사양',keys=keys[:3]+['announced','released']+keys[3:]+['gb7_opencl','gb7_vulkan']),
               dict(id='dates',label='발표·출시일',keys=['C','announced','released','H','E']),
               dict(id='benchmarks',label='벤치마크',keys=['C','B','W','gb7_opencl','gb7_vulkan','X']),
               dict(id='memory',label='메모리·전력',keys=['C','P','Q','R','S','T','H'])],
        date_definition=dates['definition'],
        evidence_summary=f"원본 {len(rows)}개 GPU · 발표일 {sum('announced' in r['reviews'] for r in rows)}개 · 출시 시기 {sum('released' in r['reviews'] for r in rows)}개 · Geekbench {sum(c['column'].startswith('gb7_') for c in extra['cells'])}개 점수",
        scroll_hint='오른쪽으로 코어 구성·RT·AI 코어·클럭·공정 확인',original_columns=columns[:26])
    return doc


AI_COLUMNS=[column('name','제품 / 프로파일',210),column('architecture','아키텍처',115),column('configuration','GPU·CPU 구성',165),
    column('memory','GPU 메모리',145),column('bandwidth','HBM 대역폭',125),column('power','전력 · 단위 확인',145),column('nvlink','NVLink 대역폭',140),
    column('fp4','FP4 · Dense / Sparse',180),column('fp8','FP8 · Dense / Sparse',180),column('fp16','FP16/BF16 · Dense / Sparse',180),column('fp32','FP32',110),
    column('process','제조 공정',115),column('sm','SM 수',75),column('cores','CUDA 코어',100),column('cache','L2 캐시',100),column('transistors','트랜지스터',130),
    column('die_size','GPU Die 면적',110),column('interface','메모리 인터페이스',120),column('cpu','CPU·시스템 메모리',240),column('c2c','NVLink-C2C',130),
    column('network','네트워크 대역폭',140),column('released','시트 발표/출시일',110),column('scope_note','비교 기준·확인 사항',280)]


def ai_original(values,number):
    mapping=dict(name=1,architecture=0,released=2,configuration=3,power=4,nvlink=5,sm=6,fp4=7,fp8=8,fp16=9,fp32=10,cores=11,transistors=12,process=13,memory=14,bandwidth=15,interface=16,die_size=17,cache=19)
    if 27<=number<=30:
        mapping.pop('interface');mapping.pop('die_size');mapping.pop('cache')
        mapping.update(cpu=16,c2c=19)
    if 37<=number<=40:
        mapping=dict(name=1,configuration=3,power=4,nvlink=10,fp4=15,fp8=16,fp16=17,fp32=18,memory=20,bandwidth=21)
    if number>=43:mapping=dict(name=1,network=4)
    return {key:str(values[i] or '') for key,i in mapping.items()}


def build_ai(raw,reviews):
    if raw['values'][3][0]!='단일 칩(추산)' or raw['values'][3][1]!='Architecture':raise ValueError('AI source layout changed')
    validate_sources(reviews['sources'],reviews['reviewed'])
    rows=[]
    selected=list(range(5,17))+list(range(19,24))+list(range(27,31))+list(range(37,41))+[43,44,45,47,48]
    for number in selected:
        values=[str(v or '') for v in raw['values'][number-1]]
        values+=['']*(31-len(values))
        if not values[1]:raise ValueError('AI source row moved')
        level='GPU 모듈' if number<=16 else 'DGX 서버' if number<=23 else '슈퍼칩' if number<=30 else '랙' if number<=40 else '네트워크'
        original=ai_original(values,number)
        if number<=16 and original.get('configuration'):
            original['configuration']='시트 Die 표기: '+original['configuration']
        if 27<=number<=30:original['cpu']=' · '.join(v for v in values[16:19] if v)
        if 37<=number<=40 and values[19]:original['memory']+=' '+values[19]
        original['scope_note']='시트 기재값 · 공식 SKU·측정 조건 미검증'
        if number in (5,6):original['scope_note']='시트의 칩명 · 보드 SKU 미확인. 제품별 실측·메모리 구성으로 일반화하지 않음.'
        if number==19:original['scope_note']='DGX-1은 P100/V100 모델이 있어 원본만으로 변형을 특정하지 않음.'
        if number==38:original['scope_note']='사용자 구성: NVL36 2랙 묶음. 표준 NVL72 단일 랙과 전력·대역폭을 합산 비교하지 않음.'
        rows.append(dict(id=f'ai-sheet-{number}',sheet_row=number,source_values=values,name=values[1],company='NVIDIA',group=level,original=original,reviews={}))
    byrow={r['sheet_row']:r for r in rows};validkeys={c['id'] for c in AI_COLUMNS}
    for product in reviews['products']:
        if product['row'] is not None:
            row=byrow[product['row']]
            if row['name']!=product['product'] or row['reviews']:raise ValueError('AI review source row mismatch')
        else:
            row=dict(id='ai-extra-'+re.sub(r'[^a-z0-9]+','-',product['product'].lower()).strip('-'),sheet_row=None,source_values=[],name=product['label'],company='NVIDIA',original={},reviews={})
            rows.append(row)
        row['group']=product['level']
        for key,cell in product['fields'].items():
            if key not in validkeys or cell['source'] not in reviews['sources'] or not cell['note'] or not cell['value']:raise ValueError('Invalid AI review evidence')
            row['reviews'][key]=cell
        row['review_note']=product['note']
    doc=base(raw,'nvidia_ai_specs','NVIDIA AI 가속기 · GPU와 시스템 사양',
        '기본은 GPU 모듈 비교입니다. 슈퍼칩·DGX 서버·랙·아키텍처 최대·네트워크는 제품 단위 필터로 나눕니다. FP4·FP8·FP16의 두 수치는 Dense / Sparse 순서이며 실측 벤치마크가 아닌 제조사 이론 성능입니다. Rubin 학습과 추론은 조건이 다릅니다. HBM·NVLink·전력은 선택한 프로파일과 제품 단위 기준이며 미확인 원본 값에는 검증 출처 표시가 없습니다.')
    doc.update(columns=AI_COLUMNS,rows=rows,name_key='name',default_group='GPU 모듈',default_view='overview',sources=reviews['sources'],updated=reviews['reviewed'],
        views=[dict(id='overview',label='한눈에 보기',keys=['name','memory','bandwidth','power','nvlink','fp4','fp8','fp16','fp32','configuration','architecture','process','sm','cores','cache','cpu']),
               dict(id='all',label='전체 사양',keys=[c['id'] for c in AI_COLUMNS]),
               dict(id='memory',label='메모리·연결·전력',keys=['name','configuration','memory','bandwidth','nvlink','c2c','power','cpu','network']),
               dict(id='compute',label='연산 성능',keys=['name','configuration','fp4','fp8','fp16','fp32','architecture','sm','cores'])],
        original_columns=AI_COLUMNS,evidence_summary=f"원본 {len(selected)}개 항목 · {len(reviews['products'])}개 프로파일 검토·추가",
        scroll_hint='단일 GPU와 서버·랙 총합 구분 · 오른쪽으로 구성·캐시·CPU 확인')
    return doc


def main():
    read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
    for doc in [build_gpu(read('gpu_specs_sheet.json'),read('gpu_specs_supplements.json'),read('gpu_release_dates.json')),
                build_ai(read('nvidia_ai_sheet.json'),read('nvidia_ai_reviews.json'))]:
        (ROOT/'data/semicon'/f"{doc['id']}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
        print(doc['id'],len(doc['rows']),'products/profiles')


if __name__=='__main__':main()

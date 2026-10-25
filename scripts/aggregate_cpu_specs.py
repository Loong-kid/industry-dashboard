"""Publish the bounded CPU Sheet snapshot with independently sourced blank fills."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def column_name(index):
    result=''
    while index:
        index,remainder=divmod(index-1,26)
        result=chr(65+remainder)+result
    return result


def build(raw,supplements,foundries):
    headers=raw['values'][0]
    if len(headers)!=37 or headers[2]!='CPU/SoC 이름' or not headers[33].startswith('Geekbench 7 Single'):
        raise ValueError('Unexpected CPU Sheet column layout')
    rows=[]
    for number,values in enumerate(raw['values'][1:],2):
        if not any(values):continue
        if len(values)>len(headers) or len(values)<3 or not values[2]:raise ValueError('Invalid product row')
        rows.append(dict(id=f'cpu-sheet-{number}',sheet_row=number,values=values+['']*(len(headers)-len(values)),supplements={}))
    byrow={r['sheet_row']:r for r in rows}
    for cell in supplements['cells']:
        row=byrow[cell['row']];index=cell['column']-1
        if row['values'][0]!=cell['company'] or row['values'][2]!=cell['product']:
            raise ValueError('Sheet row moved to another CPU; review supplement coordinates')
        if not 0<=index<len(headers) or index<3:raise ValueError('Invalid supplemental column')
        if row['values'][index]!='' or str(index) in row['supplements']:raise ValueError('Supplement overwrites existing cell')
        if cell['source'] not in supplements['sources'] or not str(cell['value']).strip():raise ValueError('Missing evidence')
        if 24<=index<=34 and not re.fullmatch(r'\d+',str(cell['value'])):raise ValueError('Invalid benchmark score')
        row['supplements'][str(index)]={k:cell[k] for k in ('value','source','note')}
    for source in supplements['sources'].values():
        if not source['url'].startswith('https://') or source['checked']>supplements['reviewed']:raise ValueError('Invalid source')
    byproduct={(row['values'][0],row['values'][2]):row for row in rows}
    for product in foundries['products']:
        row=byproduct[(product['company'],product['product'])]
        if 'foundry' in row or product['source'] not in foundries['sources']:raise ValueError('Invalid foundry evidence')
        row['foundry']={key:product[key] for key in ('foundry','node','process_nm','source','note')}
    return dict(id='cpu_specs',name='CPU·SoC 사양과 Geekbench',manual=True,frequency='irregular',updated=max(supplements['reviewed'],foundries['reviewed']),fetched=raw['imported'],
        source='사용자 Google Sheets · CPU',source_url=raw['source_url'],source_range=raw['range'],
        description='핵심 사양과 Geekbench 6·7을 먼저 보고, 오른쪽으로 넘기면 CPU 구성·아키텍처·L1·L2·L3 캐시를 비교할 수 있습니다. 긴 값은 마우스 메모와 상세에서 확인하세요.',
        note='Geekbench 버전 간 점수는 직접 비교하지 않습니다. 평균과 개별 실측, 대표 SKU·기기의 조건을 함께 확인하세요. 시트 기재 점수의 실측 링크는 원본에 포함되지 않았으며 공식 출처 열은 제품 사양의 출처입니다.',
        update_note='시트 원본과 보완값은 원문 검토 후 갱신하는 스냅샷입니다. CPU 실적 갱신 버튼은 기업 재무 공시를 갱신합니다.',
        columns=[dict(id=column_name(i+1),label=label,numeric=24<=i<=34) for i,label in enumerate(headers)],rows=rows,
        default_view='overview',display_indices=list(range(24))+list(range(31,37)),
        column_views=[dict(id='overview',label='한눈에 보기 · 구성·캐시',indices=[2,6,7,23,10,16,15,31,32,33,34,8,12,18,19,20]),
            dict(id='all',label='전체 사양 · Geekbench 6·7',indices=list(range(24))+list(range(31,37))),
            dict(id='specs',label='CPU 사양',indices=list(range(24))+[36]),
            dict(id='memory',label='메모리·캐시',indices=[0,1,2]+list(range(13,22))+[36]),
            dict(id='benchmarks',label='Geekbench 6·7',indices=[0,1,2,23]+list(range(31,37))),
            dict(id='gb6',label='Geekbench 6',indices=[0,1,2,23,31,32,36]),
            dict(id='gb7',label='Geekbench 7',indices=[0,1,2,23,33,34,35,36])],
        sources={**supplements['sources'],**foundries['sources']},foundry_review_count=len(foundries['products']),supplement_count=len(supplements['cells']),
        supplemented_products=sum(bool(r['supplements']) for r in rows))


def main():
    read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
    doc=build(read('cpu_specs_sheet.json'),read('cpu_specs_supplements.json'),read('cpu_foundries.json'))
    (ROOT/'data/semicon/cpu_specs.json').write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
    print(f"Published {len(doc['rows'])} CPU products, {len(doc['columns'])} columns, {doc['supplement_count']} sourced fills")


if __name__=='__main__':main()

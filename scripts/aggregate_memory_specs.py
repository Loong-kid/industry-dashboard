"""Publish separate DDR generation/process and HBM product tables from DRAM!A1:T39."""
import json
import re
from pathlib import Path

from aggregate_gpu_specs import column, validate_sources

ROOT=Path(__file__).resolve().parents[1]
DDR_COLUMNS=[column('name','제품 / 세대 / 공정',190),column('sheet_year','시트 출시연도',100),column('data_rate','데이터 속도 · MT/s',120,measure=True),
    column('bandwidth','64-bit 환산 · GB/s',125,measure=True),column('voltage','전압 · V',90),column('capacity','용량 · 시트 기준',140),
    column('prefetch','Prefetch',85),column('bus','비교 데이터 폭',120),column('die_density','Die 용량 · Gb',130),column('process','공정 코드',95),column('process_nm','공정 치수',100),
    column('company','회사',105),column('net_die','Net die · 원본',110),column('mesh1','Mesh 1 · 원본',110),column('mesh2','Mesh 2 · 원본',110),
    column('cell_height','Cell 높이 · 원본',120),column('dielectrics','High-k 재료 · 원본',220),column('extra','시트 추가 메모',150),
    column('generation','DDR 규격',85),column('io_width','칩 I/O 폭',110),column('chip_bandwidth','칩 대역폭 · GB/s',130,measure=True),
    column('part_number','부품 번호 / 제품군',210),column('profile_kind','자료 범위',150),column('milestone_date','출시·발표일',115,date=True),column('milestone','발표·양산 구분',170)]
HBM_COLUMNS=[column('name','제품 / 적층',170),column('company','회사',110),column('capacity','스택 용량 · GB',150),column('layers','DRAM 적층',95),
    column('data_rate','핀 속도 · Gb/s',120,measure=True),column('bandwidth','스택 대역폭 · GB/s',140,measure=True),column('io','I/O · bit',90,measure=True),column('voltage','전압 · V',85),
    column('die_density','Die 용량 · Gb',145),column('codename','코드명',110),column('dram_process','DRAM 공정',115),column('base_die','Base die',140),
    column('gap_fill','적층·Gap fill',160),column('milestone_date','출시·발표일',115,date=True),column('milestone','발표·양산 구분',150),column('sheet_year','시트 출시연도',100),
    column('bump','Bump CD · 원본',110),column('tsv_diameter','TSV 직경 · 원본',110),column('tsv_depth','TSV 깊이 · 원본',110),column('chip_thickness','칩 두께 · 원본',115),
    column('package_thickness','패키지 두께 · 원본',130),column('package_size','패키지 치수 · 대상 미확인',160),column('die_raw','DRAM 용량 · 시트 J열',145),column('example','적용 예 · 시트 기준',180)]


for _columns in (DDR_COLUMNS,HBM_COLUMNS):
    _date=next(c for c in _columns if c['id']=='milestone_date')
    _kind=next(c for c in _columns if c['id']=='milestone')
    _columns.remove(_date);_columns.remove(_kind)
    _columns[1:1]=[_date,_kind]


def cell_values(raw,number):
    values=raw['values'][number-1]
    if len(values)>20:raise ValueError('DRAM source width changed')
    return [str(v) for v in values]+['']*(20-len(values))


def add_ddr_products(ddr,products):
    validate_sources(products['sources'],products['reviewed'])
    identifiers=set();keys={c['id'] for c in DDR_COLUMNS}
    for product in products['products']:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',product['id']) or product['id'] in identifiers:raise ValueError('Duplicate or invalid DDR product')
        identifiers.add(product['id'])
        if product['company'] not in ('삼성전자','SK하이닉스','CXMT','Micron') or not product['note']:raise ValueError('Invalid DDR manufacturer')
        row=dict(id='ddr-product-'+product['id'],sheet_row=None,source_values=[],name=product['name'],company=product['company'],group='회사별 제품',original={},reviews={},review_note=product['note'])
        for key,cell in product['fields'].items():
            if key not in keys or key in ('bandwidth','chip_bandwidth') or cell['source'] not in products['sources'] or not cell['value'] or not cell['note']:raise ValueError('Missing DDR product evidence')
            if key=='milestone_date':
                from datetime import date
                if date.fromisoformat(cell['value']).isoformat()>products['reviewed']:raise ValueError('Future DDR milestone')
            row['reviews'][key]=cell.copy()
        if any(row['reviews'].get(k,{}).get('value')!=v for k,v in [('name',product['name']),('company',product['company'])]):raise ValueError('DDR product identity mismatch')
        if row['reviews'].get('generation',{}).get('value') not in ('DDR','DDR2','DDR3','DDR3L','DDR4','DDR5'):raise ValueError('Invalid DDR generation')
        speed=row['reviews'].get('data_rate')
        if speed:
            match=re.fullmatch(r'(최대)?(\d+)(?:~(\d+))?',speed['value'])
            if not match:raise ValueError('DDR data rate must be in MT/s')
            numbers=[int(v) for v in match.groups()[1:] if v]
            if any(v<=0 for v in numbers) or numbers!=sorted(numbers):raise ValueError('Invalid DDR speed range')
            prefix='최대' if match[1] else ''
            row['reviews']['bandwidth']=dict(value=prefix+'~'.join(f'{v*.008:g}' for v in numbers)+' · 환산',source=speed['source'],
                note=f"계산: 공개 속도 {speed['value']} MT/s × 가정한 64-bit 데이터 폭 ÷ 8 ÷ 1000. DDR5는 32-bit 서브채널 2개 합계 기준입니다. 실제 칩 I/O·모듈 구성 또는 실측 대역폭을 확인한 값이 아닙니다.")
            width=row['reviews'].get('io_width',{}).get('value','')
            if re.fullmatch(r'x(?:4|8|16)',width) and len(numbers)==1:
                row['reviews']['chip_bandwidth']=dict(value=prefix+f'{numbers[0]*int(width[1:])/8000:g}'+' · 계산',source=speed['source'],note=f"계산: {speed['value']} MT/s × 칩 {width} I/O ÷ 8 ÷ 1000. 64-bit 환산 대역폭과 구분한 칩 이론값입니다.")
        ddr.append(row)


def build(raw,extra,products):
    if len(raw['values'])!=39 or raw['values'][0][:4]!=['Generation','공정','출시일','회사'] or raw['values'][20][4]!='Data Rate BW(Gb/s)':
        raise ValueError('DRAM source layout changed')
    validate_sources(extra['sources'],extra['reviewed'])
    ddr=[];generation=''
    for number in range(2,20):
        v=cell_values(raw,number)
        if v[0]:generation=v[0]
        original=dict(name=v[0] or v[1],process=v[1],sheet_year=v[2],company=v[3],extra=v[4],data_rate=v[5],bandwidth=v[6],voltage=v[7],capacity=v[8],
            net_die=v[9],mesh1=v[10],mesh2=v[11],cell_height=v[12],dielectrics=v[13])
        note='세대 비교의 용량은 시트의 모듈 범위이며 Die 용량과 다릅니다.' if v[0] else '시트에 적힌 공정 메모입니다. 인접 세대명은 행 배치 문맥이며 해당 DDR 규격 전용 공정임을 검증한 것은 아닙니다.'
        if number in (9,10):
            if v[3]!='Hynix' or not re.fullmatch(r'\d+nm',v[4]) or v[5]:raise ValueError('DRAM process row changed')
            original.update(process_nm=v[4],extra='')
            note+=' 원본 E열의 nm 값을 공정 치수로 표시했습니다. 데이터 전송 속도가 아닙니다.'
        ddr.append(dict(id=f'ddr-sheet-{number}',sheet_row=number,source_values=v,name=original['name'],company={'Hynix':'SK하이닉스'}.get(original['company'],original['company']) or '공통 / 미기재',
            group='세대 비교' if v[0] else '공정 메모',context=generation,original=original,reviews={},review_note=note))
    hbm=[];company=''
    for number in list(range(22,28))+list(range(29,37))+[38,39]:
        v=cell_values(raw,number)
        if v[3]:company={'Hynix':'SK하이닉스','Samsung':'삼성전자'}.get(v[3],v[3])
        if not v[0] or not company:raise ValueError('HBM product context missing')
        original=dict(name=v[0],company=v[3],codename=v[1],sheet_year=v[2],data_rate=v[4],bandwidth=v[5],voltage=v[6],capacity=v[7],dram_process=v[8],die_density=v[9] if 'Gb' in v[9] else '',die_raw=v[9],
            io=v[10],bump=v[11],base_die=v[12],tsv_diameter=v[13],tsv_depth=v[14],chip_thickness=v[15],package_thickness=v[16],package_size=v[17],gap_fill=v[18],example=v[19])
        note='대역폭·용량은 HBM 스택 1개 기준입니다. 회사 공란은 앞선 회사 구간을 필터·행 이름의 문맥으로 사용합니다. J열의 단위 없는 숫자는 Die Gb로 간주하지 않고 ‘DRAM 용량 · 시트 J열’에 보존했습니다. 단위 없는 치수와 적용 GPU 예시는 원본 메모이며 개별 검증하지 않았습니다.'
        if number==29:note+=' 이 행은 삼성 HBM 원본 자리표시이며 HBM1 상용 제품의 존재·사양을 확정하지 않습니다.'
        if number==39:note+=' 공식 HBM4E 제품군의 공개 최대 사양을 보완했습니다. 원본 코드명 flamebolt·개별 SKU·고객 출하 여부는 미확인입니다. 공개 최대값과 양산 제품을 구분합니다.'
        hbm.append(dict(id=f'hbm-sheet-{number}',sheet_row=number,source_values=v,name=v[0],company=company,group='시트 메모' if number==29 else '제품 비교',original=original,reviews={},review_note=note))
    for rows,columns,kind in [(ddr,DDR_COLUMNS,'ddr'),(hbm,HBM_COLUMNS,'hbm')]:
        byrow={r['sheet_row']:r for r in rows};keys={c['id'] for c in columns}
        for cell in [c for c in extra['cells'] if c['table']==kind]:
            row=byrow[cell['row']];key=cell['column']
            if row['name']!=cell['product'] or key not in keys or key in row['reviews']:raise ValueError('Memory supplement source row moved or duplicated')
            if cell['source'] not in extra['sources'] or not cell['note'] or not cell['value']:raise ValueError('Missing memory evidence')
            if key=='milestone_date':
                from datetime import date
                date.fromisoformat(cell['value'])
            row['reviews'][key]={k:cell[k] for k in ('value','source','note')}
    if any(c['table'] not in ('ddr','hbm') for c in extra['cells']):raise ValueError('Unknown memory table')
    if set(products['sources'])&set(extra['sources']):raise ValueError('Duplicate memory evidence identifier')
    add_ddr_products(ddr,products)
    docs=[]
    for identifier,label,rows,columns,group,note,views,caption in [
        ('ddr_specs','DDR · 회사별 제품과 공정 사양',ddr,DDR_COLUMNS,'회사별 제품',
         '기본은 삼성전자·SK하이닉스·CXMT·Micron의 DDR 제품·제품군 비교입니다. 각 행은 근거 자료에 나온 시점의 프로파일이며 전 제품 목록·현재 양산 목록이 아닙니다. 제품군의 최대 속도가 모든 용량·SKU에서 동시에 보장되는 것은 아닙니다. Die 용량(Gb), 패키지·모듈 용량(GB), 칩 I/O 폭을 구분합니다. 64-bit 환산은 비교를 위한 가정값이며 칩 자체 대역폭이 아닙니다. 공정 명칭은 회사별 표기이고 같은 1a·1b·1c를 동일한 nm로 취급하지 않습니다. CXMT DDR4의 22nm는 독립 실물 분석값입니다. 공식 이정표는 개발·샘플·양산·인증 당시 공지를 구분하며 최신 공급 상태나 판매일이 아닙니다. 기존 시트는 세대 비교·공정 메모에서 확인합니다.',
         [dict(id='overview',label='회사별 제품 비교',keys=['name','milestone_date','milestone','company','generation','process','die_density','data_rate','voltage','bandwidth','io_width','chip_bandwidth','profile_kind']),
          dict(id='reference',label='세대 비교 · 시트',keys=['name','sheet_year','data_rate','bandwidth','voltage','prefetch','capacity','die_density','bus']),
          dict(id='process',label='공정·셀 구조',keys=['name','process','process_nm','sheet_year','company','net_die','mesh1','mesh2','cell_height','dielectrics','extra']),
          dict(id='dates',label='제품 발표·양산',keys=['name','milestone_date','milestone','company','generation','part_number','profile_kind']),
          dict(id='all',label='전체 사양',keys=[c['id'] for c in DDR_COLUMNS])],
         'DDR 대역폭: 64-bit 데이터 폭 기준 · 공정 메모는 표준 세대 사양과 구분'),
        ('hbm_specs','HBM · 회사별 스택 사양',hbm,HBM_COLUMNS,'제품 비교',
         '대역폭·용량은 스택 1개 기준입니다. DDR 모듈이나 GPU 전체 HBM 합계와 직접 비교하지 않습니다. 핀 속도(Gb/s), 대역폭(GB/s), Die 용량(Gb), 스택 용량(GB)을 구분합니다. 각 셀은 출처에 표시된 발표 시점의 제품·개발 프로파일이며 서로 다른 시점의 최대값을 한 제품의 동시 보장 사양으로 간주하지 않습니다. 공식 이정표일은 개발·샘플·양산 공지를 구분하며 실제 판매일이 아닙니다. 미검증 패키지 치수·코드명은 원본 메모로 남깁니다. 범위·초과·최대값의 수치 정렬은 표기된 첫 숫자 기준입니다.',
         [dict(id='overview',label='한눈에 보기',keys=['name','milestone_date','milestone','capacity','layers','data_rate','bandwidth','io','die_density','dram_process','base_die','gap_fill']),
          dict(id='packaging',label='적층·패키징',keys=['name','company','codename','layers','capacity','dram_process','base_die','gap_fill','bump','tsv_diameter','tsv_depth','chip_thickness','package_thickness','package_size']),
          dict(id='dates',label='발표·양산',keys=['name','milestone_date','milestone','company','sheet_year','example']),
          dict(id='all',label='전체 사양',keys=[c['id'] for c in HBM_COLUMNS])],
         'HBM 스택 1개 기준 · Gb와 GB 구분 · 개발·샘플·양산 구분')]:
        used={cell['source'] for row in rows for cell in row['reviews'].values()}
        sources={**extra['sources'],**(products['sources'] if identifier=='ddr_specs' else {})}
        docs.append(dict(id=identifier,name=label,table_family='memory',short_name='DDR' if identifier=='ddr_specs' else 'HBM',manual=True,frequency='irregular',
            source='사용자 Google Sheets · DRAM',source_url=raw['source_url'],source_range=raw['range'],updated=max(extra['reviewed'],products['reviewed']) if identifier=='ddr_specs' else extra['reviewed'],fetched=raw['imported'],
            update_note='시트 원본과 공식 자료의 확인일 기준 스냅샷입니다. 시트 수정·새 제품 발표 후 검토하여 갱신하며 자동 실시간 수집은 아닙니다.',
            columns=columns,rows=rows,name_key='name',default_group=group,default_view='overview',views=views,sources={k:v for k,v in sources.items() if k in used},
            note=note,caption=caption,search_placeholder='세대·공정·제품·회사 검색',group_label='행 구분',item_label='항목',
            evidence_summary=f"원본 {len(rows)}개 행 · {sum(len(r['reviews']) for r in rows)}개 값 보완·검토",scroll_hint='행 높이 40px · 긴 값은 마우스 메모 · 상세는 맨 오른쪽',
            original_columns=columns,raw_headers=raw['values'][0 if identifier=='ddr_specs' else 20]))
        if identifier=='ddr_specs':
            docs[-1].update(original_group='all',original_view='reference',company_order=['삼성전자','SK하이닉스','CXMT','Micron','공통 / 미기재'],view_groups=dict(overview='회사별 제품',reference='세대 비교',process='공정 메모',dates='회사별 제품'),
                evidence_summary=f"회사별 {len(products['products'])}개 제품·프로파일 · 시트 원본 18개 행 · 개별 셀 출처 확인")
    return docs


def main():
    read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
    for doc in build(read('dram_specs_sheet.json'),read('memory_specs_supplements.json'),read('ddr_products.json')):
        (ROOT/'data/semicon'/f"{doc['id']}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
        print(doc['id'],len(doc['rows']),'rows / profiles')


if __name__=='__main__':main()

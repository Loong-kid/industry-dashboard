"""Publish separate DDR generation/process and HBM product tables from DRAM!A1:T39."""
import json
import re
from pathlib import Path

from aggregate_gpu_specs import column, validate_sources

ROOT=Path(__file__).resolve().parents[1]
DDR_COLUMNS=[column('name','세대 / 공정',170),column('sheet_year','시트 출시연도',100),column('data_rate','데이터 속도 · MT/s',120,measure=True),
    column('bandwidth','64-bit 환산 · GB/s',125,measure=True),column('voltage','전압 · V',90),column('capacity','용량 · 시트 기준',140),
    column('prefetch','Prefetch',85),column('bus','비교 데이터 폭',120),column('die_density','Die 용량 · Gb',130),column('process','공정 코드',95),column('process_nm','공정 치수',100),
    column('company','회사 · 시트 기준',120),column('net_die','Net die · 원본',110),column('mesh1','Mesh 1 · 원본',110),column('mesh2','Mesh 2 · 원본',110),
    column('cell_height','Cell 높이 · 원본',120),column('dielectrics','High-k 재료 · 원본',220),column('extra','시트 추가 메모',150)]
HBM_COLUMNS=[column('name','제품 / 적층',170),column('company','회사',110),column('capacity','스택 용량 · GB',150),column('layers','DRAM 적층',95),
    column('data_rate','핀 속도 · Gb/s',120,measure=True),column('bandwidth','스택 대역폭 · GB/s',140,measure=True),column('io','I/O · bit',90,measure=True),column('voltage','전압 · V',85),
    column('die_density','Die 용량 · Gb',145),column('codename','코드명',110),column('dram_process','DRAM 공정',115),column('base_die','Base die',140),
    column('gap_fill','적층·Gap fill',160),column('milestone_date','공식 이정표일',110,date=True),column('milestone','발표·양산 구분',150),column('sheet_year','시트 출시연도',100),
    column('bump','Bump CD · 원본',110),column('tsv_diameter','TSV 직경 · 원본',110),column('tsv_depth','TSV 깊이 · 원본',110),column('chip_thickness','칩 두께 · 원본',115),
    column('package_thickness','패키지 두께 · 원본',130),column('package_size','패키지 치수 · 대상 미확인',160),column('die_raw','DRAM 용량 · 시트 J열',145),column('example','적용 예 · 시트 기준',180)]


def cell_values(raw,number):
    values=raw['values'][number-1]
    if len(values)>20:raise ValueError('DRAM source width changed')
    return [str(v) for v in values]+['']*(20-len(values))


def build(raw,extra):
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
        ddr.append(dict(id=f'ddr-sheet-{number}',sheet_row=number,source_values=v,name=original['name'],company=original['company'] or '공통 / 미기재',
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
    docs=[]
    for identifier,label,rows,columns,group,note,views,caption in [
        ('ddr_specs','DDR · 세대별 사양과 공정 메모',ddr,DDR_COLUMNS,'세대 비교',
         '기본은 SDRAM·DDR~DDR5 세대 비교입니다. 64-bit 데이터 폭의 이론 대역폭이며 DDR5는 32-bit 서브채널 2개 합계로 환산합니다. Die 용량(Gb)과 모듈 용량(GB)은 다른 단위입니다. DDR4·DDR5 보완 속도는 Micron 백서의 대표 기준이며 전체 최신 제품의 최대 속도는 아닙니다. 출시연도와 공정 구조·재료는 시트 기재 메모로, 표준 제정일·양산일 또는 검증된 제조사 공정으로 해석하지 않습니다.',
         [dict(id='overview',label='한눈에 보기',keys=['name','sheet_year','data_rate','bandwidth','voltage','prefetch','capacity','die_density','bus']),
          dict(id='process',label='공정·셀 구조',keys=['name','process','process_nm','sheet_year','company','net_die','mesh1','mesh2','cell_height','dielectrics','extra']),
          dict(id='all',label='전체 사양',keys=[c['id'] for c in DDR_COLUMNS])],
         'DDR 대역폭: 64-bit 데이터 폭 기준 · 공정 메모는 표준 세대 사양과 구분'),
        ('hbm_specs','HBM · 회사별 스택 사양',hbm,HBM_COLUMNS,'제품 비교',
         '대역폭·용량은 스택 1개 기준입니다. DDR 모듈이나 GPU 전체 HBM 합계와 직접 비교하지 않습니다. 핀 속도(Gb/s), 대역폭(GB/s), Die 용량(Gb), 스택 용량(GB)을 구분합니다. 각 셀은 출처에 표시된 발표 시점의 제품·개발 프로파일이며 서로 다른 시점의 최대값을 한 제품의 동시 보장 사양으로 간주하지 않습니다. 공식 이정표일은 개발·샘플·양산 공지를 구분하며 실제 판매일이 아닙니다. 미검증 패키지 치수·코드명은 원본 메모로 남깁니다. 범위·초과·최대값의 수치 정렬은 표기된 첫 숫자 기준입니다.',
         [dict(id='overview',label='한눈에 보기',keys=['name','capacity','layers','data_rate','bandwidth','io','die_density','dram_process','base_die','gap_fill','milestone_date','milestone']),
          dict(id='packaging',label='적층·패키징',keys=['name','company','codename','layers','capacity','dram_process','base_die','gap_fill','bump','tsv_diameter','tsv_depth','chip_thickness','package_thickness','package_size']),
          dict(id='dates',label='발표·양산',keys=['name','company','milestone_date','milestone','sheet_year','example']),
          dict(id='all',label='전체 사양',keys=[c['id'] for c in HBM_COLUMNS])],
         'HBM 스택 1개 기준 · Gb와 GB 구분 · 개발·샘플·양산 구분')]:
        used={cell['source'] for row in rows for cell in row['reviews'].values()}
        docs.append(dict(id=identifier,name=label,table_family='memory',short_name='DDR' if identifier=='ddr_specs' else 'HBM',manual=True,frequency='irregular',
            source='사용자 Google Sheets · DRAM',source_url=raw['source_url'],source_range=raw['range'],updated=extra['reviewed'],fetched=raw['imported'],
            update_note='시트 원본과 공식 자료의 확인일 기준 스냅샷입니다. 시트 수정·새 제품 발표 후 검토하여 갱신하며 자동 실시간 수집은 아닙니다.',
            columns=columns,rows=rows,name_key='name',default_group=group,default_view='overview',views=views,sources={k:v for k,v in extra['sources'].items() if k in used},
            note=note,caption=caption,search_placeholder='세대·공정·제품·회사 검색',group_label='행 구분',item_label='항목',
            evidence_summary=f"원본 {len(rows)}개 행 · {sum(len(r['reviews']) for r in rows)}개 값 보완·검토",scroll_hint='행 높이 40px · 긴 값은 마우스 메모 · 상세는 맨 오른쪽',
            original_columns=columns,raw_headers=raw['values'][0 if identifier=='ddr_specs' else 20]))
    return docs


def main():
    read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
    for doc in build(read('dram_specs_sheet.json'),read('memory_specs_supplements.json')):
        (ROOT/'data/semicon'/f"{doc['id']}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
        print(doc['id'],len(doc['rows']),'source rows')


if __name__=='__main__':main()

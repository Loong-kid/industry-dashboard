"""Read-only Google Sheets snapshot -> XR reference tables and dated user notes."""
import argparse,copy,datetime as dt,re
from pathlib import Path
from urllib.parse import quote
from fetch_cpu_companies import load,save

ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'manual/vrar/reference-sheet.json';OUT=ROOT/'data/vrar'


def column(n):
    text=''
    while n:n,d=divmod(n-1,26);text=chr(65+d)+text
    return text


def cell_url(raw,tab,start,finish):
    return raw['spreadsheet_url']+'#gid='+str(tab['sheet_id'])+'&range='+quote(start+':'+finish,safe=':')


def values(row,size=35):return [str(v) if v is not None else '' for v in row]+['']*max(0,size-len(row))


def specs(row,headers,start=3):
    result=[]
    for i,value in enumerate(row):
        if i<start or not value:continue
        label=headers.get(i,'추가 기재')
        # Some original panel rows place resolution one column to the right.
        # Preserve the cell location without presenting it as luminance.
        if label=='밝기' and re.search(r'\d\s*[x×]\s*\d',value):label='해상도 기재'
        result.append(dict(label=label,column=column(i+1),value=value))
    return result


VR={3:'가격',4:'출시일 기재',5:'무게',6:'칩',7:'공정',8:'CPU',9:'아키텍처',10:'GPU',11:'NPU',12:'메모리',13:'메모리 대역폭',14:'메모리 용량',15:'픽셀',16:'픽셀 수',17:'디스플레이',18:'픽셀 피치',19:'PPI',20:'지원 재생률',21:'FPS',23:'통신'}
GLASSES={3:'출시일 기재',4:'가격',5:'무게',6:'칩',7:'메모리',8:'저장공간',9:'도수 범위',10:'디스플레이 방식',11:'디스플레이 기재',12:'해상도',13:'밝기',14:'FOV',15:'광학계',16:'카메라',17:'카메라 시야각',19:'배터리',20:'통신',21:'추가 통신'}
ENGINE={3:'출시일 기재',4:'가격',5:'무게',6:'부피(open)',7:'부피(real)',8:'픽셀 피치',9:'PPD',10:'소비전력',11:'추가 전력 기재',12:'해상도',13:'패널 공급사 기재',14:'광속·밝기 기재',15:'FOV'}
PANEL={3:'출시일 기재',4:'인터페이스·추가 기재',5:'무게',6:'유효 면적',7:'크기',8:'모듈 크기',9:'픽셀 피치',10:'소비전력',11:'해상도',12:'밝기',13:'데이터 전송률',14:'재생률',15:'컬러 비트'}
BACKPLANE={3:'색상',4:'인터페이스',5:'해상도',6:'픽셀 피치',7:'공정 등 기재'}


def build(raw):
    groups={k:dict(id=k,title=title,rows=[],notes=[]) for k,title in [('vr','VR / MR 기기'),('ar','AR / 스마트 글래스'),('engine','라이트엔진'),('panel','디스플레이 패널'),('backplane','CMOS 백플레인')]}
    for tab_key in ['vr','ar']:
        tab=raw['tabs'][tab_key];rows=tab['values'];category=tab_key;maker='';variant='';previous=None
        links={}
        for block in tab.get('cell_data',[]):
            for ri,line in enumerate(block.get('rowData',[])):
                for ci,cell in enumerate(line.get('values',[])):
                    urls=[cell.get('hyperlink')]+[x.get('format',{}).get('link',{}).get('uri') for x in cell.get('textFormatRuns',[])]
                    links[block.get('startRow',0)+ri+1,block.get('startColumn',0)+ci+1]=[u for u in urls if u and u.startswith(('https://','http://'))]
        if tab_key=='vr':maker=next((values(r)[1] for r in rows[3:] if values(r)[1] and not values(r)[1].startswith('http')),'')
        for index,original in enumerate(rows,1):
            row=values(original)
            if index<4 or not any(row):continue
            if tab_key=='ar' and row[0]:
                title=row[0]
                if title=='AR Glasses':category='ar'
                elif title.startswith('Light Engine'):category='engine'
                elif title=='Display Panel':category='panel'
                elif title=='CMOS Backplane':category='backplane'
                elif title=='Lens':category='lens'
                maker='';variant='';previous=None;continue
            if row[1] and not row[1].startswith('http'):
                maker=row[1];variant=''
            if category=='engine' and row[3]=='출시일':variant=row[2];continue
            if category=='engine' and row[2]=='Monochrome':variant=row[2];previous=None;continue
            if category=='lens':continue # No lens product is named in this snapshot.
            if row[2] and ('반드시' in row[2] or '개발중' in row[2]):
                groups[category]['notes'].append(dict(text=row[2],source_url=cell_url(raw,tab,'B'+str(index),'AF'+str(index))));continue
            header=VR if category=='vr' else GLASSES if category=='ar' else ENGINE if category=='engine' else PANEL if category=='panel' else BACKPLANE
            fields=specs(row,header)
            if not row[2]:
                if previous and category=='vr' and row[6]:
                    previous['components'].append(dict(chip=row[6],specs=fields,source_row=index));previous['source_end_row']=index
                    previous['source_url']=cell_url(raw,tab,'B'+str(previous['source_row']),'AI'+str(index))
                continue
            source_links=list(dict.fromkeys([u for (r,c),urls in links.items() if r==index for u in urls]+([row[1]] if row[1].startswith('http') else [])))
            record=dict(id=category+'-'+str(index),maker=maker or '미기재',model=row[2],variant=variant,specs=fields,components=[],source_row=index,source_end_row=index,source_sheet=tab['title'],source_url=cell_url(raw,tab,'B'+str(index),('AI' if category=='vr' else 'AF')+str(index)),links=source_links)
            record['release']=row[4] if category=='vr' else row[3] if category in ['ar','engine','panel'] else ''
            record['price']=row[3] if category=='vr' else row[4] if category=='ar' else ''
            record['weight']=row[5] if category in ['vr','ar','engine','panel'] else ''
            record['chip']=row[6] if category in ['vr','ar'] else ''
            record['display']=row[17] if category=='vr' else ' / '.join(v for v in row[10:13] if v) if category=='ar' else ' / '.join(f['value'] for f in fields if f['label'] in ['해상도','해상도 기재','픽셀 피치','소비전력'])
            groups[category]['rows'].append(record);previous=record
    tab=raw['tabs']['contracts'];block=tab['cell_data'];contracts=[]
    for offset,row in enumerate(block['rowData'][1:],1):
        cells=row.get('values',[])
        if not any(c.get('formattedValue') for c in cells):continue
        vals=[c.get('formattedValue','') for c in cells];vals+=['']*max(0,9-len(vals));position=block['startRow']+offset+1
        contracts.append(dict(source_row=position,source_url=cell_url(raw,tab,'AC'+str(position),'BE'+str(position)),start=vals[0],sheet_date=vals[1],end=vals[2],description=vals[3],counterparty=vals[4],usd_display=vals[5],krw_million_display=vals[6],same_type=vals[7],memo=' / '.join(v for v in vals[8:] if v),raw_values=vals))
    return dict(id='reference_tables',fetched=raw['fetched'],source_url=raw['spreadsheet_url'],source='사용자 구글 시트 · 산업(VR)_밸류에이션',
        description='시트에 기재한 가격·일정·사양과 예상·물음표 표현을 보존했습니다. 공란은 미기재이며 출시·탑재가 확인됐다는 뜻은 아닙니다. 가격은 시트의 통화·용량 표기를 따릅니다.',categories=list(groups.values()),contract_notes=contracts)


if __name__=='__main__':
    doc=build(load(SOURCE,{}));save(OUT/'reference_tables.json',doc)
    print('XR sheet tables:',{c['id']:len(c['rows']) for c in doc['categories']},len(doc['contract_notes']),'contract notes')

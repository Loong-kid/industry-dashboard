"""Preserve the full public Mysteel concentrate TC chart, index ID01154994.

This is the publicly served chart used on the publisher's concentrate homepage,
not an authenticated Steelunion history API. Do not combine it with the SMM index.
"""
import datetime as dt
import hashlib
import json
import re

import requests

from derive_copper_market import OUT, check_date, check_number, save

PAGE = 'https://tongjingkuang.mysteel.com/'
API = 'https://api.mysteel.com/publishd/index/chart/zhanTingData'
CODE = 'ID01154994'
ID = 'comm_copper_concentrate_tc_mysteel'
NAME = '정광 TC · Mysteel 중국 수입 현물'
SOURCE_URL = API + '?indexCodes=' + CODE + '&startTime=2000-01-01'


def parse_chart(payload, today):
    if payload.get('status') != '200':
        raise ValueError('Public TC chart unavailable')
    body = json.loads(payload['response'])
    if set(body) != {'xAxis', 'datas'} or len(body['datas']) != 1:
        raise ValueError('TC chart schema changed')
    data = body['datas'][0]
    if data.get('indexCode') != CODE or len(data['yAxis']) != len(body['xAxis']):
        raise ValueError('Wrong TC index or unequal date/value lengths')
    rows, seen = [], set()
    for date, value in zip(body['xAxis'], data['yAxis']):
        check_date(date, today)
        if date in seen or (rows and date <= rows[-1]['date']):
            raise ValueError('Duplicate or unordered TC dates')
        seen.add(date)
        if value is None or value in ('', '--', '-'):
            continue
        if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
            raise ValueError('Invalid public TC value')
        number = float(value)
        check_number(number)
        rows.append(dict(date=date,value=number,reported_value=value,unit='USD/dmt',
            provider='Mysteel',index_code=CODE,source_url=SOURCE_URL,checked=today))
    if not rows:
        raise ValueError('No public TC observations')
    return rows


def build_document(records, today):
    first, last = records[0]['date'], records[-1]['date']
    return dict(id=ID,name=NAME,unit='USD/건조정광톤',frequency='irregular',
        frequency_label='현물 · 원문 발표일',updated=last,fetched=today,data_stale_days=21,
        source='Mysteel 공식 공개 구리 정광 차트 · ID01154994',source_url=PAGE,
        source_records=records,series={NAME:[[r['date'],r['value']] for r in records]},
        reference_value=0,reference_label='TC 0',highlight_gaps=True,daily_axis=True,change_mode='none',
        table_limit=len(records),table_scroll=True,
        history_started=first,snapshot_history=True,
        history_note=f'{first}~{last} 원문 {len(records):,}개 관측값. 주간·일간 발표일을 그대로 보존합니다.',
        description='중국 제련소가 수입 현물 정광을 구매할 때의 TC(제련수수료)입니다. 단위는 구리 금속톤이 아닌 건조 정광톤(USD/dmt)입니다. Mysteel 정광 홈페이지의 동일 지표 코드 ID01154994 공개 이력을 사용합니다. SMM 주간 지수·SHMET 견적·연간 장기계약 TC와는 별도 시리즈입니다.',
        note='2000년부터 조회해 공개 응답의 가장 오래된 2013-01-11부터 수록했습니다. 초기에는 주로 주간, 2021~2025년에는 일간 관측값이 많으며 최근은 주간 중심입니다. 주간·일간을 임의 환산하거나 빈 날짜를 생성하지 않습니다. 같은 지표 코드라도 장기 비교에서는 조사 표본·방법론 변화에 유의하세요. 음수 TC를 그대로 보존하며 TC에서 RC를 자동 계산하지 않습니다. 7일 초과 공백은 점선입니다. 매일 공개 차트를 확인하고 기존 이력을 보존합니다.',
        basis_details=[dict(label='지표 식별',value='Mysteel 정광 홈페이지 · TC/현물가격(美元价格) 차트 · TC=ID01154994. 현물가격 ID01154993·국산광 위안화 가격과 구분합니다.'),
            dict(label='단위·거래 기준',value='USD/건조정광톤. Mysteel 공개 주·일 보고서에서 표준 청정 정광 수입 현물 TC와 대조했습니다. 최근 가격표의 CIF 중국·QP M+3·선적 1~3개월 조건을 모든 과거 시점에 동일하게 적용한다고 가정하지 않습니다.'),
            dict(label='확보 범위',value=f'{first}~{last}, {len(records):,}개 원문 발표일. 원문 차트의 날짜와 값을 일대일 대응하며 평균·보간·전일 값 이월을 하지 않습니다.')])


def run(today=None):
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    path = OUT / (ID+'.json')
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    try:
        response = requests.get(API,params={'indexCodes':CODE,'startTime':'2000-01-01'},timeout=(8,25))
        response.raise_for_status()
        rows = parse_chart(response.json(),today)
        previous = {r['date']:r for r in old.get('source_records',[])}
        if old and rows[-1]['date'] < old['updated']:
            raise ValueError('TC latest observation regressed')
        for row in rows:
            if row['date'] in previous and previous[row['date']]['value'] != row['value']:
                raise ValueError('TC source revision requires review')
            previous.setdefault(row['date'],row)
        records = [previous[k] for k in sorted(previous)]
        doc = build_document(records,today)
        doc['source_response_sha256'] = hashlib.sha256(response.content).hexdigest()
        doc['collection_status'] = dict(checked=today,ok=True,message='Mysteel 공식 공개 TC 차트 확인 · 전체 공개 이력 보존')
        save(doc)
        print(ID,records[0]['date'],records[-1]['date'],len(records),'observations')
    except Exception:
        if old:
            old['collection_status'] = dict(checked=today,ok=False,message='공개 TC 확인 실패 · 기존 관측값 보존')
            save(old)
        raise


if __name__ == '__main__':
    run()

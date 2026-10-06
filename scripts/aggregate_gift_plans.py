"""Publish a distinct stock-gift plan table; elapsed plans never imply execution."""
import json
from collections import Counter
from fetch_gift_plans import DB_PATH, ROOT, load_db
from aggregate_gifts import clean_name, iso_date

OUT=ROOT/'data/gifts/gift_plans.json'
STATUSES=['계획 공시','거래기간 중','기간 경과 / 이행 미확인','철회','정정 전','최신 보고서 확인 필요']


def build_orders(db):
    records=db.get('reports',{})
    parent={}
    def find(no):
        parent.setdefault(no,no)
        if parent[no]!=no: parent[no]=find(parent[no])
        return parent[no]
    def union(left,right):
        left,right=find(left),find(right)
        parent[max(left,right)]=min(left,right)
    for no,record in records.items():
        find(no)
        for member in record.get('family',[]): union(no,member['rcept_no'])
    groups={}
    for no in parent: groups.setdefault(find(no),[]).append(no)
    orders=[]
    for no,record in records.items():
        if record.get('status')!='ok': continue
        listing=record['listing']
        latest=max(groups[find(no)])
        final=records.get(latest,{})
        if record.get('withdrawn') or '철' in listing.get('rm',''): status='withdrawn'
        elif '정' in listing.get('rm',''): status='superseded'
        elif final.get('status')!='ok': status='latest_unverified'
        elif final.get('withdrawn'): status='withdrawn'
        elif no!=latest: status='superseded'
        elif record.get('family_status')=='error': status='latest_unverified'
        else: status='active'
        for index,event in enumerate(record.get('events',[])):
            item=dict(event,rcept_no=no,rcept_dt=iso_date(listing['rcept_dt']),
                      corp_name=listing['corp_name'],market={'Y':'코스피','K':'코스닥'}.get(listing.get('corp_cls'),''),
                      report_nm=listing['report_nm'],event_id=f'{no}:{index}',
                      original_rcept_no=find(no),latest_rcept_no=latest,record_status=status,
                      holder_type='소액임원' if event.get('main_sh') in ('','-',None) else '대주주',
                      reporter=clean_name(event['reporter']),counterparty=clean_name(event.get('counterparty','')))
            orders.append(item)
    return sorted(orders,key=lambda row:(row['rcept_dt'],row['rcept_no'],row['event_id']),reverse=True)


def build_document(db):
    orders=build_orders(db)
    errors=sum(r.get('status')!='ok' for r in db.get('reports',{}).values())
    link_errors=sum(r.get('family_status')=='error' for r in db.get('reports',{}).values())
    scanned=db.get('scanned_through','')
    return {
        'id':'gift_plans','name':'주식 증여 / 수증 계획','is_plan':True,
        'unit':'건','frequency':'수시(사전 공시)',
        'source':'DART 임원·주요주주 특정증권등 거래계획보고서',
        'source_url':'https://dart.fss.or.kr',
        'note':'앞으로 할 거래의 방법이 증여/수증인 주식만 표시합니다. 과거 6개월 거래는 제외합니다. '
               '거래기간 종료는 이행 완료를 뜻하지 않습니다. 지분율의 후 값은 보고서 전체 거래계획의 예상치이며, '
               '동일 거래의 증여자·수증자가 각각 보고할 수 있으므로 행 수는 거래 건수와 다르며, 수량을 단순 합산하지 않습니다. '
               '계획과 실제 내역도 합산하지 않습니다. 정정·철회는 OpenDART 공식 상태 기준입니다. '
               '기본: 소액임원·정정 전·철회·최신 보고서 미확인 숨김.',
        'legal_summary':'2024년 7월 24일 시행된 상장회사 임원·주요주주의 내부자거래 사전공시 제도입니다. '
                        '일반적인 증여도 요건에 따라 대상이 되지만, 모든 주주·모든 증여의 의무 공시는 아닙니다.',
        'legal_checked':'2026-10-06',
        'legal_sections':[
            {'title':'누가 보고하나?',
             'text':'해당 상장회사의 임원(이사·감사 및 사실상 임원) 또는 주요주주가 보고합니다. '
                    '주요주주는 의결권 있는 주식 10% 이상을 자기 계산으로 소유하거나 주요 경영사항에 사실상 영향력을 행사하는 자입니다. '
                    '연기금·집합투자기구 등 법정 제외 대상은 면제됩니다. 증여자와 수증자의 보고의무는 각자의 지위에 따라 별도로 판단합니다.',
             'source_ids':['trade_plan','fsc']},
            {'title':'얼마나 · 언제 보고하나?',
             'text':'거래계획과 거래개시일 기준 과거 6개월 거래를 합산해 거래수량이 특정증권등 총수량의 1% 이상 '
                    '또는 거래금액이 50억원 이상이면 원칙적으로 보고 대상입니다. 두 기준 모두 미만이면 규모에 따른 면제입니다. '
                    '거래개시일 30일 전까지 증권선물위원회와 한국거래소에 각각 보고하며, 거래기간은 30일 이내입니다. '
                    '상속·주식배당 등 법정 제외 거래가 있고, 주식 외 증권의 수량은 별도 산정 규정을 적용합니다.',
             'source_ids':['trade_plan','regulation']},
            {'title':'미이행하면 제재가 있나?',
             'text':'보고자는 거래계획에 따라 거래해야 합니다. 정당한 철회 없이 계획을 실행하지 않으면 과징금 대상이 될 수 있습니다. '
                    '법정 상한은 해당 상장회사 시가총액의 0.02%(1만분의 2), 최대 20억원이며, 실제 부과액은 위반 내용 등에 따라 달라집니다. '
                    '허용되는 거래금액 30% 범위의 조정은 계획 전체를 임의로 취소할 수 있다는 뜻이 아닙니다.',
             'source_ids':['trade_plan','penalty']},
            {'title':'철회할 수 있는 경우는?',
             'text':'사망, 회생·파산절차 개시, 법령에서 정한 수준의 가격 변동 등 부득이한 사유가 있어야 합니다. '
                    '철회 사유에 맞는 법정 절차에 따라 철회하며, 단순한 변심만으로 자유롭게 취소할 수 있는 제도는 아닙니다. '
                    '철회보고 대상 사유는 정해진 기한 내 증권선물위원회와 한국거래소에 보고해야 합니다.',
             'source_ids':['trade_plan','regulation','fsc']},
        ],
        'legal_note':'이 설명은 사전 거래계획 보고 기준입니다. 실제 증여에 따른 소유상황보고·5% 대량보유보고는 별도 제도입니다. '
                     '대시보드의 ‘기간 경과 / 이행 미확인’은 위반 확정을 뜻하지 않으며, 후속 공시·정정·철회 여부를 확인해야 합니다.',
        'legal_sources':[
            {'id':'trade_plan','label':'자본시장법 제173조의3','url':'https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1032437031'},
            {'id':'regulation','label':'시행령 제200조의3','url':'https://law.go.kr/lsLinkCommonInfo.do?lspttninfSeq=189255'},
            {'id':'penalty','label':'자본시장법 제429조 제5항','url':'https://law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1028103467'},
            {'id':'fsc','label':'금융위원회 시행 안내(2024.7.9.)','url':'https://www.fsc.go.kr/po010101/82635'},
        ],
        'updated':orders[0]['rcept_dt'] if orders else None,
        'fetched':db.get('fetched'), 'scanned_from':iso_date(db.get('scanned_from','')),
        'scanned_through':iso_date(scanned),'parse_errors':errors,'link_errors':link_errors,
        'coverage_note':f"코스피·코스닥 거래계획 공시 확인: {iso_date(db.get('scanned_from',''))} ~ {iso_date(scanned)}. "
                        + (f'원문 확인 실패 {errors}건은 다음 수집에서 재시도합니다.' if errors else '확보한 거래계획 원문을 모두 확인했습니다.')
                        + (f' 정정·철회 연결 확인 대기 {link_errors}건은 API 상태 기준으로 보수적으로 표시합니다.' if link_errors else ''),
        'markets':['코스피','코스닥'],'holder_types':['대주주','소액임원'],
        'directions':['증여(줌)','수증(받음)'],'plan_statuses':STATUSES,'orders':orders,
    }


def run():
    if not DB_PATH.exists(): raise SystemExit('Run fetch_gift_plans.py first')
    db=load_db()
    doc=build_document(db)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    tmp.replace(OUT)
    print('Gift plan rows:',len(doc['orders']),Counter(r['record_status'] for r in doc['orders']))


if __name__=='__main__': run()

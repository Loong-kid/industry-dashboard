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
        'legal_summary':'2024년 7월 24일 시행된 내부자거래 사전공시 제도입니다. 상장회사 임원·주요주주의 거래계획과 '
                        '거래 개시일 기준 과거 6개월 거래를 합산하여 특정증권등 총수량의 1% 이상 또는 50억 원 이상이면 '
                        '원칙적으로 개시일 30일 전까지 보고합니다. 거래기간은 30일 이내이며, 제외되는 보고자·거래가 있습니다. '
                        '일반적인 증여도 적용될 수 있지만 모든 증여가 의무 보고되는 것은 아닙니다. '
                        '대시보드는 보고된 계획을 감지하며, 보고 의무나 위법 여부를 자동 판정하지 않습니다.',
        'legal_sources':[
            {'label':'자본시장법 제173조의3','url':'https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1032437031'},
            {'label':'시행령 제200조의3','url':'https://law.go.kr/lsLinkCommonInfo.do?lspttninfSeq=189255'},
            {'label':'금융감독원 기업공시 길라잡이','url':'https://dart.fss.or.kr/info/main.do?menu=340'},
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

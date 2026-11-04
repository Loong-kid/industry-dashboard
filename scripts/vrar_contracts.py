"""Explicit related-filing chains, not mutable contract dates, identify a deal."""
import copy,datetime as dt,re
from collections import defaultdict
from bs4 import BeautifulSoup
from dart_extractor import parse_supply_contract,parse_all_fields


def date(value):
    found=re.search(r'(20\d{2})\D+(\d{1,2})\D+(\d{1,2})',value or '')
    if not found:return None
    try:return dt.date(*map(int,found.groups())).isoformat()
    except ValueError:return None


def parse(raw,entry):
    receipt=entry['rcept_no'];filed=f'{receipt[:4]}-{receipt[4:6]}-{receipt[6:8]}'
    if entry.get('corp_code')!='01676642' or entry.get('stock_code')!='452430':raise ValueError('Contract issuer mismatch')
    soup=BeautifulSoup(raw,'html.parser')
    # The existing extractor expects TD. OpenDART exchange XML can use TU/TE.
    for cell in soup.find_all(['tu','te']):cell.name='td'
    normalized=str(soup);core=parse_supply_contract(normalized);fields=parse_all_fields(normalized)
    if not core.get('contract_name') or not core.get('contract_party'):raise ValueError('Contract body fields unavailable')
    notes=' '.join(v for k,v in fields.items() if '기타투자판단' in k)
    usd=re.search(r'\bUSD\s+([\d,]+(?:\.\d+)?)',notes)
    related=set(re.findall(r'(?i)(?:rcpNo|acptNo|rcept_no|acfno)[\s\"\']*[=:][\s\"\']*(20\d{12})',raw))-{receipt}
    for a in soup.select('a[href]'):
        related.update(re.findall(r'20\d{12}',a['href']))
    rows=[]
    for tr in soup.select('tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.find_all(['td','th'],recursive=False)]
        if cells:rows.append(cells)
    # Preserve the original correction table for before/after review.
    correction_rows=[]
    for r in rows:
        if r and re.match(r'^1\.',r[0].replace(' ','')) and '판매' in r[0] and '공급계약' in r[0]:break
        if len(r)>=3:correction_rows.append(r)
    amount=core.get('contract_amount','')
    return dict(receipt=receipt,filed=filed,title=entry['report_nm'],url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+receipt,
      description=core['contract_name'],counterparty=core['contract_party'],amount_krw=int(amount) if amount.isdigit() else None,amount_usd=float(usd[1].replace(',','')) if usd else None,
      start=date(core.get('contract_start')),end=date(core.get('contract_end')),deal_date=date(core.get('deal_date')),
      correction_reason=core.get('correction_reason',''),is_correction='정정' in entry['report_nm'],cancelled='해지' in entry['report_nm'],
      related_receipts=sorted(related),correction_rows=correction_rows,fields=fields,other_notes=notes,raw_html=raw)


def build(disclosures,sheet,asof,checked,errors=()):
    rows={r['receipt']:r for r in disclosures if r['filed']<=asof};parent={k:k for k in rows}
    def root(k):
        while parent[k]!=k:parent[k]=parent[parent[k]];k=parent[k]
        return k
    for k,row in rows.items():
        for previous in row['related_receipts']:
            # KIND links use the exchange receipt (00xxxx); DART's copy of
            # the same exchange filing uses 90xxxx. Resolve only an existing
            # receipt with the identical date and sequence, never by deal date.
            if previous not in rows and previous[8:10]=='00':
                alias=previous[:8]+'90'+previous[10:]
                if alias in rows:previous=alias
            if previous in rows:
                a,b=root(k),root(previous)
                if a!=b:parent[max(a,b)]=min(a,b)
    groups=defaultdict(list)
    for k,row in rows.items():groups[root(k)].append(row)
    note_groups=defaultdict(list)
    for note in sheet['contract_notes']:
        value=note['usd_display'].replace(',','')
        amounts=[g for g,h in groups.items() if value.replace('.','',1).isdigit() and any(r.get('amount_usd')==float(value) for r in h)]
        dates=[g for g,h in groups.items() if date(note['sheet_date']) in {d for r in h for d in [r['filed'],r.get('deal_date')] if d}]
        candidates=amounts if amounts else dates
        if len(candidates)==1:note_groups[candidates[0]].append(note)
    contracts=[];matched=set();today=dt.date.fromisoformat(asof)
    for identity,history in groups.items():
        history=sorted(history,key=lambda r:(r['filed'],r['receipt']));first=history[0];latest=history[-1];memos=[]
        memos=note_groups[identity]
        matched.update(n['source_row'] for n in memos)
        remaining=(dt.date.fromisoformat(latest['end'])-today).days if latest.get('end') else None
        status='해지 공시' if latest['cancelled'] else '종료일 미기재' if remaining is None else '종료일 경과 · 후속 확인' if remaining<0 else '30일 내 종료 예정' if remaining<=30 else '기간 내'
        changes=[]
        if len(history)>1:
            old=history[-2]
            for key,label in [('amount_krw','원화 금액'),('amount_usd','USD 금액'),('start','시작일'),('end','종료일'),('counterparty','공식 상대방')]:
                if old.get(key)!=latest.get(key):changes.append(label)
        clean=lambda r:{k:v for k,v in r.items() if k!='raw_html'}
        contracts.append(dict(id=identity,latest=clean(latest),original=clean(first),history=[clean(r) for r in history],revision_count=sum(r['is_correction'] for r in history),sheet_notes=memos,
          status=status,status_code='cancelled' if latest['cancelled'] else 'unknown' if remaining is None else 'elapsed' if remaining<0 else 'due' if remaining<=30 else 'active',days_to_end=remaining,changed_fields=changes))
    contracts.sort(key=lambda c:(c['latest']['filed'],c['latest']['receipt']),reverse=True)
    unmatched=[n for n in sheet['contract_notes'] if n['source_row'] not in matched]
    return dict(id='contract_watch',asof=asof,checked=checked,source='DART 단일판매·공급계약 원문',source_url='https://dart.fss.or.kr/dsab002/main.do?autoSearch=true&textCrpNm=452430',
       contracts=contracts,unmatched_sheet_notes=unmatched,collection_status=dict(ok=not errors,checked=checked,errors=list(errors)),
       description='원문 관련공시 링크로 같은 계약의 정정 이력을 연결합니다. 계약금액은 최신 공시 총액이며 매출·수주잔고·미수금 잔액이 아닙니다. 종료일 경과만으로 납품·대금수령 완료를 판단하지 않습니다. 고객사 실명 추정은 시트 메모로 구분합니다.')

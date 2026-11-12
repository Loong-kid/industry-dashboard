"""One current snapshot per officially linked project, with amendment differences."""
import json
from pathlib import Path

from fetch_expansion import ROOT, STATE, today, write
from expansion_document import CATEGORIES

OUT = ROOT / 'data/expansion/investments.json'
CHANGE_FIELDS = {'amount_krw': '투자금액', 'end_date': '완료 예정일', 'start_date': '시작일', 'purpose': '투자목적', 'target': '투자대상', 'investment_type': '투자구분'}


def build(state):
    reports = state.get('reports', {})
    parents = {no: no for no in reports}
    def find(no):
        while parents[no] != no:
            parents[no] = parents[parents[no]]; no = parents[no]
        return no
    def union(a, b):
        a, b = find(a), find(b)
        if a != b: parents[max(a, b)] = min(a, b)
    for no, report in reports.items():
        for rel in report.get('family', []):
            other = rel['rcept_no']
            if other not in reports: continue
            # Receipt lineage must not merge different listed issuers.
            a, b = report['listing'], reports[other]['listing']
            issuer = a.get('stock_code') or a.get('corp_code')
            if issuer and issuer == (b.get('stock_code') or b.get('corp_code')):
                union(no, other)
    groups = {}
    for no, report in reports.items(): groups.setdefault(find(no), []).append(report)
    projects, changes = [], []
    for root, group in groups.items():
        group.sort(key=lambda r: r['listing']['rcept_no'])
        latest = group[-1]; listing = latest['listing']
        good = [r for r in group if r.get('parsed')]
        current = latest.get('parsed') or (good[-1]['parsed'] if good else {})
        history = []
        previous = None
        for record in group:
            row = record['listing']; parsed = record.get('parsed', {})
            diffs = []
            if previous and parsed:
                diffs = [dict(field=key, label=label, before=previous.get(key), after=parsed.get(key))
                         for key, label in CHANGE_FIELDS.items() if previous.get(key) != parsed.get(key)]
            h = dict(rcept_no=row['rcept_no'], date=format_date(row['rcept_dt']), title=row['report_nm'],
                     amount_krw=parsed.get('amount_krw'), end_date=parsed.get('end_date'),
                     reason=parsed.get('correction_reason', ''), changes=diffs,
                     status=record.get('status'), withdrawn=record.get('withdrawn', False),
                     url='https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + row['rcept_no'])
            history.append(h)
            if parsed: previous = parsed
        withdrawn = latest.get('withdrawn') or '철' in listing.get('rm', '')
        status = 'withdrawn' if withdrawn else 'review' if latest.get('status') != 'ok' or not latest.get('parsed') else 'superseded' if '정' in listing.get('rm', '') else 'announced'
        category = current.get('category', 'review') if status not in ('review', 'superseded') else 'review'
        project = dict(id=root, corp_name=listing.get('corp_name', ''), stock_code=listing.get('stock_code', ''),
                       market={'Y': '코스피', 'K': '코스닥'}.get(listing.get('corp_cls'), ''),
                       first_disclosed=history[0]['date'], last_disclosed=history[-1]['date'],
                       **{k: v for k, v in current.items() if k not in ('category', 'category_label')},
                       category=category, category_label=CATEGORIES[category], record_status=status,
                       status_label={'withdrawn': '철회', 'review': '원문 확인 필요', 'superseded': '후속 정정 확인 필요', 'announced': '공시 계획'}[status],
                       history=history, latest_url=history[-1]['url'], source_rcept_no=listing['rcept_no'],
                       facts_rcept_no=good[-1]['listing']['rcept_no'] if good else None)
        projects.append(project)
        for item in history[1:]:
            changes.append(dict(project_id=root, corp_name=project['corp_name'], stock_code=project['stock_code'],
                                category=category, market=project['market'], investor=project.get('investor'), **item))
    projects.sort(key=lambda p: (p['last_disclosed'], p['id']), reverse=True)
    changes.sort(key=lambda p: (p['date'], p['rcept_no']), reverse=True)
    return dict(id='investments', name='증설 투자', fetched=state.get('fetched'), updated=max((p['last_disclosed'] for p in projects), default=None),
                coverage=dict(from_date=format_date(state.get('scanned_from')), through_date=format_date(state.get('scanned_through')),
                              mode=state.get('initial_collection', 'not_collected'), listed_receipts=len(reports),
                              pending=sum(r.get('status') != 'ok' for r in reports.values())),
                categories=CATEGORIES, projects=projects, changes=changes)


def format_date(value):
    return value[:4] + '-' + value[4:6] + '-' + value[6:8] if value and len(value) == 8 else value


if __name__ == '__main__':
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    doc = build(state); write(OUT, doc)
    print(f"{len(doc['projects'])} projects, {len(doc['changes'])} amendments")

"""Daily digest of GitHub Actions results: one status issue instead of one email per failed run.

The issue body is rewritten every run with a table of every workflow grouped by area
(last run, last success). A comment that mentions the owner is added only when something failed in
the last 24 hours, so the owner gets at most one email a day.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY. `--dry-run` prints the body and comment instead of writing.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISSUE_TITLE = '수집 상태 (자동 요약)'
ISSUE_LABEL = 'collect-status'
OWNER_MENTION = '@Loong-kid'
KST = timezone(timedelta(hours=9))

# Area for every scheduled collector (workflow `name:`). New collectors fall into '기타' until listed.
AREAS = {
    '반도체': ['update-cleanroom', 'update-cpu', 'update-equipment', 'update-expansion', 'update-mocvd-guidance',
               'update-power-semicon', 'update-rings', 'update-semicon-cleaning', 'update-semicon-osat',
               'update-semicon-supplychain', 'update-semicon-valuation'],
    '에너지·원자재': ['update-copper-valuation', 'update-mining', 'update-mining-valuation', 'update-specialty-minerals',
                 'update-natgas', 'update-lng-containment', 'update-oil', 'update-refining', 'update-solar',
                 'update-offshore', 'update-offshore-valuation'],
    '데이터센터·IT': ['update-data', 'update-neocloud', 'update-us-datacenter', 'update-telecom', 'update-quantum'],
    '소비·콘텐츠': ['update-cosmetics', 'update-entertainment', 'update-hybe-labels', 'update-games', 'update-movies',
               'update-vrar'],
    '산업재': ['update-shipbuilding-equipment', 'update-drone'],
    '거시': ['update-ppi', 'update-us-treasury', 'update-national-budget'],
    '배포·시험': ['publish-updated-data', 'pages-build-deployment', 'ci-tests', 'actions-digest'],
}
AREA_ORDER = list(AREAS) + ['수동 점검·보충', '기타']


def area_of(name):
    for area, names in AREAS.items():
        if name in names:
            return area
    if name.startswith(('review-', 'backfill-', 'collect-')):
        return '수동 점검·보충'
    return '기타'


def kst(iso):
    return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(KST).strftime('%m-%d %H:%M') if iso else '—'


MARK = {'success': '정상', 'failure': '실패', 'cancelled': '취소', 'skipped': '건너뜀', 'timed_out': '시간 초과',
        'startup_failure': '시작 실패', None: '실행 중'}


def summarize(workflows, runs_by_workflow, failures, now):
    """Return (issue body, comment or None). Pure function so it can be tested without the API."""
    rows = {}
    for wf in workflows:
        runs = runs_by_workflow.get(wf['id'], [])
        last = runs[0] if runs else None
        ok = next((r for r in runs if r['conclusion'] == 'success'), None)
        rows.setdefault(area_of(wf['name']), []).append(dict(
            name=wf['name'], url=wf.get('html_url', ''), last=last, ok=ok,
            state=MARK.get(last['conclusion'], last['conclusion']) if last else '기록 없음'))
    since = now - timedelta(hours=24)
    recent = [r for r in failures if datetime.fromisoformat(r['created_at'].replace('Z', '+00:00')) >= since]
    broken = sorted({r['name'] for area in rows.values() for r in area if r['state'] in ('실패', '시간 초과', '시작 실패')})
    total = sum(len(v) for v in rows.values())
    lines = [f'마지막 갱신: {now.astimezone(KST):%Y-%m-%d %H:%M} KST · 워크플로 {total}개 · '
             f'지금 실패 상태 {len(broken)}개 · 최근 24시간 실패 실행 {len(recent)}건', '',
             '이 이슈 본문은 매일 자동으로 다시 쓰입니다. 실패가 있던 날에만 댓글(메일 1통)이 달립니다.', '']
    for area in AREA_ORDER:
        if area not in rows:
            continue
        items = sorted(rows[area], key=lambda r: r['name'])
        bad = sum(1 for r in items if r['state'] != '정상')
        lines += [f'### {area} ({len(items)}개{f", 확인 필요 {bad}" if bad else ""})', '',
                  '| 워크플로 | 상태 | 마지막 실행 (KST) | 마지막 성공 (KST) |', '|---|---|---|---|']
        for r in items:
            name = f"[{r['name']}]({r['url']})" if r['url'] else r['name']
            lines.append(f"| {name} | {r['state']} | {kst(r['last'] and r['last']['created_at'])} | "
                         f"{kst(r['ok'] and r['ok']['created_at'])} |")
        lines.append('')
    comment = None
    if recent:
        by_name = {}
        for r in recent:
            by_name.setdefault(r['name'], []).append(r)
        parts = [f'{OWNER_MENTION} 최근 24시간 실패 실행 {len(recent)}건 ({len(by_name)}개 워크플로)', '']
        for name, items in sorted(by_name.items(), key=lambda kv: -len(kv[1])):
            still = '지금도 실패 상태' if name in broken else '이후 성공해서 복구됨'
            parts.append(f"- **{name}** {len(items)}건 · {still} · 최근 [{kst(items[0]['created_at'])}]({items[0]['html_url']})")
        comment = '\n'.join(parts)
    return '\n'.join(lines).rstrip() + '\n', comment


class GitHub:
    def __init__(self, repo, token):
        self.base, self.token = f'https://api.github.com/repos/{repo}', token

    def call(self, path, method='GET', body=None, params=None):
        url = (path if path.startswith('http') else self.base + path) + ('?' + urllib.parse.urlencode(params) if params else '')
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json',
                                              'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'industry-dashboard-digest'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp) if resp.status != 204 else None


def collect(gh, now):
    workflows = [w for w in gh.call('/actions/workflows', params={'per_page': 100})['workflows'] if w['state'] == 'active']
    runs = {w['id']: gh.call(f"/actions/workflows/{w['id']}/runs", params={'per_page': 20, 'branch': 'main'})['workflow_runs']
            for w in workflows}
    since = (now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
    failures = gh.call('/actions/runs', params={'status': 'failure', 'created': f'>={since}', 'per_page': 100})['workflow_runs']
    return workflows, runs, failures


def publish(gh, body, comment):
    found = gh.call('/issues', params={'labels': ISSUE_LABEL, 'state': 'all', 'per_page': 5})
    issue = next((i for i in found if i['title'] == ISSUE_TITLE), None)
    if issue is None:
        issue = gh.call('/issues', 'POST', {'title': ISSUE_TITLE, 'body': body, 'labels': [ISSUE_LABEL]})
    else:
        gh.call(f"/issues/{issue['number']}", 'PATCH', {'body': body, 'state': 'open'})
    if comment:
        gh.call(f"/issues/{issue['number']}/comments", 'POST', {'body': comment})
    print('issue', issue['html_url'], 'comment' if comment else 'no failures, no comment')


if __name__ == '__main__':
    now = datetime.now(timezone.utc)
    gh = GitHub(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN'])
    body, comment = summarize(*collect(gh, now), now)
    if '--dry-run' in sys.argv:
        print(body)
        print('---- comment ----')
        print(comment)
    else:
        publish(gh, body, comment)

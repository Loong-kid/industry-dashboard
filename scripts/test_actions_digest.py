import re
import unittest
from datetime import datetime, timezone

from actions_digest import AREAS, ROOT, area_of, summarize


def workflow_names():
    names = {}
    for path in sorted((ROOT / '.github/workflows').glob('*.yml')):
        match = re.search(r'^name:\s*(.+)$', path.read_text(encoding='utf-8'), re.M)
        names[match.group(1).strip()] = path.name
    return names


class ActionsDigestTests(unittest.TestCase):
    def test_areas_name_real_workflows(self):
        names = workflow_names()
        listed = [n for group in AREAS.values() for n in group]
        self.assertEqual(len(listed), len(set(listed)))
        # pages-build-deployment is run by GitHub Pages itself and has no file in .github/workflows.
        self.assertEqual(sorted(set(listed) - set(names) - {'pages-build-deployment'}), [], 'AREAS lists a workflow that no longer exists')
        unlisted = sorted(n for n in names if area_of(n) == '기타')
        if unlisted:  # a new collector only shows under '기타' until someone files it; not a failure
            print('digest: workflows without an area:', unlisted)

    def test_summary_groups_and_comments_only_on_recent_failures(self):
        now = datetime(2026, 11, 25, 13, 0, tzinfo=timezone.utc)
        wfs = [dict(id=1, name='update-cosmetics', html_url='https://x/1'), dict(id=2, name='publish-updated-data'),
               dict(id=3, name='review-oil-sources')]
        run = lambda c, t, url='https://run': dict(conclusion=c, created_at=t, html_url=url, name='')
        runs = {1: [run('failure', '2026-11-25T01:00:00Z'), run('success', '2026-11-09T01:00:00Z')],
                2: [run('success', '2026-11-25T10:00:00Z'), run('failure', '2026-11-25T09:00:00Z')], 3: []}
        failures = [dict(name='update-cosmetics', created_at='2026-11-25T01:00:00Z', html_url='https://f1'),
                    dict(name='publish-updated-data', created_at='2026-11-25T09:00:00Z', html_url='https://f2'),
                    dict(name='publish-updated-data', created_at='2026-11-23T09:00:00Z', html_url='https://old')]
        body, comment = summarize(wfs, runs, failures, now)
        self.assertIn('### 소비·콘텐츠 (1개, 확인 필요 1)', body)
        self.assertIn('| [update-cosmetics](https://x/1) | 실패 | 11-25 10:00 | 11-09 10:00 |', body)
        self.assertIn('### 수동 점검·보충', body)
        self.assertIn('최근 24시간 실패 실행 2건', body)
        self.assertIn('@Loong-kid', comment)
        self.assertIn('update-cosmetics** 1건 · 지금도 실패 상태', comment)
        self.assertIn('publish-updated-data** 1건 · 이후 성공해서 복구됨', comment)
        self.assertNotIn('https://old', comment)
        _, quiet = summarize(wfs, {1: [run('success', '2026-11-25T01:00:00Z')]}, [], now)
        self.assertIsNone(quiet)


if __name__ == '__main__':
    unittest.main()

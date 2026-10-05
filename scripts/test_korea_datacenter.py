import copy
import unittest

from korea_datacenter import address_key, annual_series, date_info, merge_observations, parse_public_rows, reconcile, enrich_records
from fetch_korea_datacenter import declared_period, listing

SOURCE = {'id': '1893', 'title': '공식 허가', 'published': '2026-09-17', 'url': 'https://blcm.go.kr', 'kind': 'permits'}


def observation():
    return {'id': 'observation-1', 'name': '센터', 'location': '경기도 안성시 양성면 추곡리 179-0',
        'address_key': address_key('경기도 안성시 양성면 추곡리 179-0'), 'type': '신축', 'permit_ids': ['new-pk'],
        'dates': {'permit': date_info('20250718'), 'start': date_info('20260612'), 'completion': date_info(None)},
        'classification': 'confirmed', 'classification_reason': '기타용도', 'area': 100, 'area_variants': [100],
        'sources': [SOURCE], 'building_ids': [], 'building_names': []}


def facility():
    row = observation()
    row.update(id='manual-1', origin='baseline', capacity=60, notes='수기 메모', area=90, sources=[])
    row['dates']['start'] = date_info(None)
    row['dates']['alteration'] = date_info(None)
    return row


class DatacenterTests(unittest.TestCase):
    def test_research_preserves_manual_facts_and_uses_explicit_provenance(self):
        row = facility()
        row['owner'] = ''
        row['sources'] = [{**SOURCE, 'id': 'baseline-starts'}, SOURCE]
        original = copy.deepcopy(row)
        entry = {'checked': '2026-10-05', 'stakeholders': [{'role': 'operator', 'name': '운영법인'}],
                 'update': {'stage': '운영', 'as_of': '2026-06-16', 'text': '개장 발표'}, 'sources': [SOURCE]}
        summary = enrich_records([row], {'checked': '2026-10-05', 'records': {row['id']: entry}})
        self.assertEqual(row['dates'], original['dates'])
        self.assertEqual(row['owner'], '')
        self.assertEqual(row['capacity'], original['capacity'])
        self.assertEqual(summary['unresolved_owner'], 1)
        self.assertEqual([s['provenance'] for s in row['sources']], ['user_raw', 'public_download'])
        row['research']['stakeholders'][0]['name'] = '수정'
        self.assertEqual(entry['stakeholders'][0]['name'], '운영법인')

    def test_uncertain_and_invalid_dates_never_become_actual(self):
        for value in ['2022?', '2027.4Q', '2026-06-31(목표)', '2026-04-31(예정)', 2024]:
            self.assertNotEqual(date_info(value)['kind'], 'confirmed')
        self.assertIsNone(date_info('2026-04-31(예정)')['date'])
        self.assertEqual(date_info('20260116')['date'], '2026-01-16')
        self.assertEqual(date_info('2029-01-01', '2026-10-05')['kind'], 'planned')

    def test_aggregate_dongs_not_repeated_total_area(self):
        header = ['건축물명칭', '기타용도','건축인허가번호','허가일','연면적(㎡)','동별_개요_PK','동명칭']
        rows = [['센터','데이터센터','pk','20260616',100,'dong1','A'], ['센터','데이터센터','pk','20260616',100,'dong2','B']]
        obs, stats = parse_public_rows(header, rows, SOURCE)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]['area'], 100)
        self.assertEqual(len(obs[0]['building_ids']), 2)
        rows[1][4] = 110
        obs, _ = parse_public_rows(header, rows, SOURCE)
        self.assertIsNone(obs[0]['area'])

    def test_shifted_user_raw_lots_and_missing_type(self):
        headers = ['업무구분','시도','시군구','법정동','번','지','허가구분','건축구분','허가번호','건축인허가번호','건축물명칭','주용도','기타용도','대지면적(㎡)','건축면적(㎡)','건폐율(%)','연면적(㎡)','용적률산전용면적(㎡)','용적률(%)','허가일']
        row = [None,'경기도','안성시','양성면 추곡리','대지',179,0,'신축허가',None,None,'센터','방송통신시설','데이터센터',200,50,25,100,100,50,20250718]
        obs, _ = parse_public_rows(headers, [row], SOURCE, curated=True)
        self.assertEqual(obs[0]['address_key'], observation()['address_key'])
        self.assertEqual(obs[0]['type'], '신축')

    def test_pk_transition_and_snapshot_repetition(self):
        old, new = observation(), observation()
        old['permit_ids'] = ['47190-1000798042']
        new['permit_ids'] = ['47190-1000000000000000798042']
        old['sources'] = [{**SOURCE, 'id': 'older', 'published': '2026-08-04'}]
        new['dates']['start'] = date_info('20260827')
        merged = merge_observations([old], [new, new])
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0]['permit_ids']), {'47190-1000798042','47190-1000000000000000798042'})
        self.assertEqual(len(merged[0]['sources']), 2)
        self.assertEqual(merged[0]['dates']['start']['date'], '2026-08-27')

    def test_distinct_current_permits_at_same_site_remain_separate(self):
        a, b = observation(), observation()
        a['permit_ids'] = ['47190-1000000000000000798042']
        b['permit_ids'] = ['47190-1000000000000000798043']
        b['id'] = 'observation-2'
        self.assertEqual(len(merge_observations([a], [b])), 2)

    def test_preserve_manual_capacity_notes_area_and_original_dates(self):
        row = facility()
        row['dates']['start'] = date_info('2026-04-31(예정)')
        baseline = {'facilities': [row]}
        records, changes = reconcile(baseline, [observation()])
        self.assertEqual(records[0]['capacity'], 60)
        self.assertEqual(records[0]['notes'], '수기 메모')
        self.assertEqual(records[0]['area'], 90)
        self.assertEqual(records[0]['dates']['start']['date'], '2026-06-12')
        self.assertEqual(records[0]['original_dates']['start']['text'], '2026-04-31(예정)')
        self.assertTrue(any(c['field'] == 'area' and not c['applied'] for c in changes))
        self.assertEqual(baseline['facilities'][0]['dates']['start']['kind'], 'planned')

    def test_conflicting_confirmed_date_not_overwritten(self):
        row = facility(); row['dates']['start'] = date_info('20260101')
        records, changes = reconcile({'facilities': [row]}, [observation()])
        self.assertEqual(records[0]['dates']['start']['date'], '2026-01-01')
        self.assertTrue(any(c['field'] == 'start' and not c['applied'] for c in changes))

    def test_same_name_date_different_known_address_cannot_match(self):
        row = facility(); row['address_key'] = address_key('경기도 안성시 양성면 추곡리 180-0')
        records, changes = reconcile({'facilities': [row]}, [observation()])
        self.assertEqual(records[0]['dates']['start']['kind'], 'missing')
        self.assertEqual(len(records), 2)

    def test_ambiguous_match_does_not_update_multiple_rows(self):
        a, b = facility(), facility(); b['id'] = 'manual-2'
        records, changes = reconcile({'facilities': [a,b]}, [observation()])
        self.assertTrue(all(r['dates']['start']['kind'] == 'missing' for r in records))
        self.assertTrue(any(c['field'] == 'match' for c in changes))

    def test_unlinked_raw_and_name_candidates_excluded_from_counts(self):
        obs = observation(); obs['sources'] = [{**SOURCE, 'id': 'baseline-starts'}]
        records, _ = reconcile({'facilities': []}, [obs])
        self.assertEqual(records[0]['classification'], 'candidate')
        self.assertEqual(annual_series(records, 'start'), {})
        obs['sources'] = [SOURCE]
        obs['dates']['start'] = date_info('2027-01-01', '2026-10-05')
        records, _ = reconcile({'facilities': []}, [obs])
        self.assertEqual(annual_series(records, 'start'), {})

    def test_public_listing_uses_observed_download_link_and_family(self):
        html = "<table><tbody><tr><td>1893</td><td><a href=\"javascript:fn_view('pk')\">전국 건축물 허가 현황(2026년 6월~2026년 8월)</a></td><td>2026-09-17</td><td><a href=\"javascript:fn_egov_downFile('filetoken', '0')\"></a></td></tr></tbody></table>"
        sources = listing(html)
        self.assertEqual(sources[0]['file_id'], 'filetoken')
        self.assertEqual(declared_period(sources[0]['title']), ('2026-06-01','2026-08-31'))


if __name__ == '__main__':
    unittest.main()

"""Build reviewed AI-company disclosures without inferring missing power or ARR."""
import copy
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'manual/ai-companies/reviewed.json'
OUTPUT = ROOT / 'data/datacenter/dc_ai_companies.json'


def validate(doc):
    reviewed = date.fromisoformat(doc['reviewed'])
    sources = {s['id']: s for s in doc['sources']}
    companies = {c['id'] for c in doc['companies']}
    projects = {p['id'] for p in doc['projects']}
    assert len(sources) == len(doc['sources'])
    for source in sources.values():
        host = urlparse(source['url']).hostname
        assert host and any(host == domain or host.endswith('.' + domain) for domain in
                            ['openai.com', 'anthropic.com', 'oracle.com', 'crusoe.ai', 'aboutamazon.com', 'sec.gov'])
        assert source['checked'] <= doc['reviewed']
        if source['published']: assert date.fromisoformat(source['published']) <= reviewed
    for section in ['companies', 'arr', 'compute_history', 'projects', 'events']:
        rows = doc[section]
        assert len({r['id'] for r in rows}) == len(rows)
        for row in rows:
            assert row['source_ids'] and set(row['source_ids']) <= sources.keys()
            if section != 'companies': assert row['company'] in companies
    for row in doc['arr']:
        assert row['usd_bn'] > 0 and row['scope'] == 'company'
        assert row['basis'] in ['reported', 'monthly_annualized']
        assert row['qualifier'] in ['eq', 'gt', 'ge', 'le', 'approx']
        assert date.fromisoformat(row['plot_date']) <= reviewed
        assert date.fromisoformat(row['announced_on']) <= reviewed
    for row in doc['projects']:
        for key in ['known_mw', 'planned_mw', 'grid_mw']:
            assert row[key] is None or row[key] >= 0
        assert row['known_mw'] is None or (row['known_basis'] and row['known_as_of'])
    for row in doc['events']:
        assert row['additive'] is False, 'Overlapping contracts must not be summed'
        assert not row['project_id'] or row['project_id'] in projects
        assert row['date'] <= doc['reviewed']
    return doc


def build(doc):
    return validate(copy.deepcopy(doc))


if __name__ == '__main__':
    doc = build(json.loads(SOURCE.read_text(encoding='utf-8')))
    OUTPUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False) + '\n', encoding='utf-8')
    print('AI companies:', len(doc['arr']), 'ARR points,', len(doc['projects']), 'projects,', len(doc['events']), 'events')

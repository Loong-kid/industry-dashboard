"""Build semiconductor company charts from reviewed quarterly IR facts.

This is an offline builder, not a live collection job. Review new reports,
append quarter facts to manual/semicon_companies.json, then run this file.
"""
import datetime as dt
import json
import math
from pathlib import Path
from company_period_views import add_period_views

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / 'manual/semicon_companies.json'


def validate(snapshot):
    reviewed = dt.date.fromisoformat(snapshot['reviewed'])
    for company, meta in snapshot['companies'].items():
        seen_dates, seen_periods = set(), set()
        for row in meta['quarters']:
            date = dt.date.fromisoformat(row['date'])
            period = (row['year'], row['quarter'])
            if row.get('period_basis') != 'quarter' or not 1 <= row['quarter'] <= 4:
                raise ValueError(f'{company}: must be an actual quarterly period')
            if date > reviewed or row['date'] in seen_dates or period in seen_periods:
                raise ValueError(f'{company}: duplicate or future period {period}')
            seen_dates.add(row['date']); seen_periods.add(period)
            for metric in ['revenue', 'profit', 'capex']:
                value = row[metric]
                if value is None and metric == 'capex' and company == 'sandisk':
                    continue
                if value is None and metric == 'capex' and company == 'micron' and isinstance(row.get('capex_gross'), (int, float)):
                    continue
                if value is None and metric == 'capex' and company == 'kioxia' and row.get('missing_reasons', {}).get(metric):
                    continue
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f'{company}: invalid {metric}')
                if metric != 'profit' and value < 0:
                    raise ValueError(f'{company}: negative {metric}')
            if not row['source_url'].startswith('https://'):
                raise ValueError(f'{company}: official source missing')
        for group in meta.get('history_groups', []):
            if group['unit'] != meta['unit']:
                raise ValueError(f'{company}: historical unit differs')
            dates, periods = set(), set()
            for row in group['quarters']:
                date = dt.date.fromisoformat(row['date'])
                period = (row['year'], row['quarter'])
                if row.get('period_basis') != 'quarter' or not 1 <= row['quarter'] <= 4:
                    raise ValueError(f'{company}: historical fact is not a quarter')
                if date > reviewed or row['date'] in dates or period in periods:
                    raise ValueError(f'{company}: duplicate/future historical quarter')
                dates.add(row['date']); periods.add(period)
                if not row['source_url'].startswith('https://'):
                    raise ValueError(f'{company}: historical source missing')
                facts = [row.get(field) for fields in group['fields'].values() for field in fields]
                if not any(value is not None for value in facts):
                    raise ValueError(f'{company}: empty historical quarter')
                if any(value is not None and (not isinstance(value, (int,float)) or not math.isfinite(value)) for value in facts):
                    raise ValueError(f'{company}: invalid historical fact')


def build(snapshot):
    validate(snapshot)
    docs = {}
    for company, meta in snapshot['companies'].items():
        rows = sorted(meta['quarters'], key=lambda row: row['date'])
        fiscal = company in ['micron', 'sandisk', 'kioxia']
        lookup = {(row['year'], row['quarter']): row['date'] for row in rows}
        labels = {row['date']: f"{'FY' if fiscal else ''}{row['year']} Q{row['quarter']}" for row in rows}
        comparisons = {
            row['date']: dict(
                year_ago=lookup.get((row['year']-1, row['quarter'])),
                quarter_ago=lookup.get((row['year']-(row['quarter']==1), (row['quarter']-2)%4+1))
            ) for row in rows
        }
        for metric, korean in [('revenue','매출'), ('profit','영업이익'), ('capex','CAPEX')]:
            fields = meta.get(metric+'_fields', {metric: '연결 '+korean if metric != 'capex' else ('순 CAPEX' if company == 'micron' else 'CAPEX')})
            series = {label: [[row['date'], row.get(field)] for row in rows] for field,label in fields.items()}
            refs = {}
            for row in rows:
                capex_deck = metric == 'capex' and row.get('capex_source_url')
                ref = dict(url=row['capex_source_url'] if capex_deck else row['source_url'],
                           label=labels[row['date']],
                           pdf_page=row.get('capex_source_page') if capex_deck else row.get('source_pages',{}).get(metric))
                pages = sorted({row.get('source_pages',{}).get(field) for field in fields} - {None})
                if company == 'samsung' and len(pages) > 1:
                    ref['supporting_sources'] = [dict(url=row['source_url'],label=labels[row['date']],pdf_page=page) for page in pages]
                    ref['source_separator'] = ' / '
                if capex_deck:
                    ref['supporting_sources'] = [dict(ref), dict(url=row['source_url'],label='자체 유형자산 · 실적 발표')]
                    ref['source_separator'] = ' / '
                refs[row['date']] = ref
            note = meta.get(metric+'_note', '회사 전체 연결 분기 매출입니다.' if metric=='revenue' else '회사 전체 연결 영업이익입니다.')
            id = 'company_'+company+'_'+metric
            docs[id] = dict(
                id=id, name=meta['name']+' · '+korean, unit=meta['unit'], frequency='quarterly',
                frequency_label='분기 · 공식 IR 확인', quarter_labels=True,
                period_labels=labels, comparison_dates=comparisons,
                updated=rows[-1]['date'], fetched=snapshot['reviewed'], manual=True,
                source='기업 공식 IR·공시', source_url=refs[rows[-1]['date']]['url'],
                description=meta['fiscal']+'. '+note, span_gaps=False,
                series=series, default_series=list(meta.get(metric+'_default',fields.values())),
                point_sources=refs, table_limit=100, company_kpi=True,
                quarterly_revenue_summary=metric!='profit', quarterly_profit_summary=metric=='profit'
            )
            doc = docs[id]
            for group in meta.get('history_groups', []):
                historical = sorted(group['quarters'], key=lambda r:r['date'])
                fields = group['fields'].get(metric, {})
                if not fields:
                    continue
                lookup = {(r['year'],r['quarter']):r['date'] for r in historical}
                for field,label in fields.items():
                    if label in doc['series']:
                        raise ValueError(f'Duplicate historical series {label}')
                    doc['series'][label] = [[r['date'],r.get(field)] for r in historical]
                    doc['default_series'].append(label)
                for row in historical:
                    date = row['date']
                    label = f"{group['name']} FY{row['year']} Q{row['quarter']}"
                    if date in doc['point_sources']:
                        raise ValueError(f'Historical/current periods overlap: {date}')
                    doc['period_labels'][date] = f"FY{row['year']} Q{row['quarter']}"
                    doc['comparison_dates'][date] = dict(
                        year_ago=lookup.get((row['year']-1,row['quarter'])),
                        quarter_ago=lookup.get((row['year']-(row['quarter']==1),(row['quarter']-2)%4+1)))
                    ref = dict(url=row['source_url'],label=label,pdf_page=row.get('source_pages',{}).get(metric))
                    if row.get('supporting_sources'):
                        ref.update(supporting_sources=row['supporting_sources'],source_separator=' / ')
                    doc['point_sources'][date] = ref
                doc.setdefault('basis_details',[]).append(dict(label=group['name'],value=group['description']))
            if meta.get('history_notes',{}).get(metric):
                doc['description'] += ' '+meta['history_notes'][metric]
    return {id:add_period_views(doc) for id,doc in docs.items()}


def main():
    snapshot = json.loads(MANUAL.read_text(encoding='utf-8'))
    docs = build(snapshot)
    for id, doc in docs.items():
        (ROOT/'data/semicon'/f'{id}.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(docs)} semiconductor company charts built')


if __name__ == '__main__':
    main()

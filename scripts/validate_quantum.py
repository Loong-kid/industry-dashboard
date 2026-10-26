"""Publication gate for quantum business history, currencies and provenance."""
import json
import math
from pathlib import Path

from quantum_sources import METRICS

ROOT=Path(__file__).resolve().parents[1]


def validate():
    read=lambda f:json.loads((ROOT/f).read_text(encoding='utf-8'))
    meta=read('manual/quantum/companies.json');state=read('data/quantum/state.json')['companies']
    assert len(meta)==10
    assert not {'IBM','GOOG','GOOGL','MSFT','AMZN'} & {m['ticker'] for m in meta.values()}
    for key,m in meta.items():
        company=state[key];rows=company['rows']
        assert rows and any(r['kind']=='annual' for r in rows),key
        assert len({(r['kind'],r['date']) for r in rows})==len(rows),key
        for r in rows:
            assert r['start']<=r['date']<=company['checked']
            for metric in METRICS:
                if r.get(metric) is None:continue
                assert math.isfinite(r[metric]) and (metric!='revenue' or r[metric]>=0),(key,r)
                ref=r['refs'][metric]
                assert ref['url'].startswith('https://www.sec.gov/') and ref['filed']<=company['checked']
        for metric in METRICS:
            d=read(f'data/quantum/company_{key}_{metric}.json')
            assert d['unit']=='백만 USD' and d['span_gaps'] is False
            assert any(r.get(metric) is not None for r in rows),(key,metric)
            for v in d['series_views'].values():
                native=next(iter(v['original_series'].values()))
                dollars=dict(next(iter(v['series'].values()))) if v['series'] else {}
                for day,value in native:
                    if value is None:continue
                    assert dollars.get(day) is not None and math.isfinite(dollars[day]),(key,metric,day,'FX')
                    assert v['point_notes'][day] and v['point_sources'][day]['url']
                    row=next(r for r in rows if r['kind']==('half' if v['frequency']=='semiannual' else 'annual' if v['frequency']=='yearly' else 'quarter') and r['date']==day)
                    if row['currency']=='USD':assert math.isclose(value,dollars[day],abs_tol=1e-9)
    pasqal=read('data/quantum/company_pasqal_revenue.json')
    assert pasqal['default_view']=='half' and not pasqal['series_views']['quarter']['series']
    infq=next(r for r in state['infleqtion']['rows'] if r['kind']=='quarter' and r['date']=='2025-03-31')
    assert math.isclose(infq['revenue'],8.195,abs_tol=1e-9),'Infleqtion restatement not propagated'
    hq=next(r for r in state['horizon']['rows'] if r['kind']=='annual' and r['year']==2025)
    assert hq['currency']=='SGD' and math.isclose(hq['profit'],-22.057337,abs_tol=1e-9),'holding-company/convenience translation selected'
    qnt=next(r for r in state['quantinuum']['rows'] if r['kind']=='quarter' and r['date']=='2026-06-30')
    assert math.isclose(qnt['netincome'],-596.52,abs_tol=1e-9),'parent attribution substituted for consolidated loss'
    universe=read('data/quantum/universe.json')
    assert len(universe['etfs'])==4 and len(universe['companies'])==10
    for etf in universe['etfs']:
        if etf.get('holdings_url'):
            assert etf.get('positions') and etf['asof']<=universe['updated']
            assert any(p['kind']=='equity' for p in etf['positions'])
    print('PASS: 10 companies, 30 USD cards, actual quarter/half/annual periods, native currencies, restatements, consolidated net losses and dated ETF positions')


if __name__=='__main__':validate()

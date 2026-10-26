"""Publication gate: real equipment financial history, USD and provenance."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def validate():
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    metadata=read('manual/telecom/equipment.json');state=read('data/telecom/equipment_state.json')['companies']
    assert len(metadata)==10
    for key,m in metadata.items():
        rows=state[key].get('rows',[])
        assert rows,f'{key}: no public accounts'
        assert len({(r['kind'],r['date']) for r in rows})==len(rows),key
        assert len({(r['kind'],r['year'],r.get('quarter')) for r in rows})==len(rows),f'{key}: duplicate fiscal period'
        for metric in ['revenue','profit','capex']:
            assert any(r.get(metric) is not None for r in rows),f'{key}: {metric} unavailable'
            d=read(f'data/telecom/company_{key}_{metric}.json')
            assert d['original_currency']==m['currency'] and d['unit']=='백만 USD'
            for view in d['series_views'].values():
                native=next(iter(view['original_series'].values()))
                usd=dict(next(iter(view['series'].values()))) if view['series'] else {}
                for day,value in native:
                    if value is None:continue
                    assert math.isfinite(value) and (metric=='profit' or value>=0)
                    assert math.isfinite(usd[day]),f'{key}: {day} FX unavailable'
                    assert view['point_sources'][day]['url'].startswith('https://')
        assert any(r['kind']=='quarter' and r.get('revenue') is not None for r in rows),key
        assert any(r['kind']=='annual' and r.get('revenue') is not None for r in rows),key
    assert next(r for r in state['ericsson']['rows'] if r['kind']=='quarter' and r['date']=='2026-09-30')['profit']==8864
    nokia=next(r for r in state['nokia']['rows'] if r['kind']=='quarter' and r['date']=='2026-06-30')
    assert nokia['profit']==-50 and nokia['revenue']==4815  # reported, not comparable 434
    print('PASS: 10 equipment issuers, 30 metric cards, fiscal dates, reported losses, original currencies, exact USD intervals and primary provenance')


if __name__=='__main__':validate()

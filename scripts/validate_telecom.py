"""Gate publication on all nine carriers having real revenue, profit and CAPEX."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def validate():
    read=lambda path:json.loads((ROOT/path).read_text(encoding='utf-8'))
    state=read('data/telecom/state.json')['companies']
    metadata=read('manual/telecom/companies.json')
    assert len(metadata)==9
    for key,meta in metadata.items():
        rows=state[key].get('rows',[])
        assert rows,f'{key}: no public company history'
        assert len({(r['kind'],r['date']) for r in rows})==len(rows),key
        for metric in ['revenue','profit','capex']:
            assert any(r.get(metric) is not None for r in rows),f'{key}: {metric} unavailable'
            doc=read(f'data/telecom/company_{key}_{metric}.json')
            assert doc['original_currency']==meta['currency']
            assert doc['unit']=='백만 USD'
            for kind,view in doc['series_views'].items():
                native=next(iter(view['original_series'].values()))
                for date,value in native:
                    if value is None:continue
                    assert math.isfinite(value)
                    if metric!='profit':assert value>=0
                    points=next(iter(view['series'].values()))
                    usd=dict(points)[date]
                    assert usd is not None,f'{key}: {kind} {date} FX unavailable'
                    assert math.isfinite(usd)
                    assert date in view['point_sources'],f'{key}: missing provenance'
    print('PASS: nine telecom carriers, 27 metric cards, fiscal dates, original currencies, USD coverage and provenance')


if __name__=='__main__':validate()

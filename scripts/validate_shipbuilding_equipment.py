"""Publication gate: actual issuer accounts, periods, currencies and source links."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
METRICS=('revenue','profit','netincome')


def validate():
    read=lambda path:json.loads((ROOT/path).read_text(encoding='utf8'))
    meta=read('manual/shipbuilding-equipment/companies.json');state=read('data/shipbuilding/equipment_state.json')['companies']
    assert len(meta)==7
    for key,m in meta.items():
        company=state[key];rows=company.get('rows',[])
        assert rows and any(r['kind']=='annual' for r in rows) and any(r['kind']=='quarter' for r in rows),key
        assert company['entity']['stock_code']==m['ticker']
        assert len({(r['kind'],r['date']) for r in rows})==len(rows)
        for r in rows:
            assert r['currency']=='KRW' and r['date']<=company['checked']
            assert r['fs_div'] in ('CFS','OFS')
            for metric in METRICS:
                if r.get(metric) is None:continue
                assert math.isfinite(r[metric]) and (metric!='revenue' or r[metric]>=0)
                f=r['refs'][metric];assert f['url'].startswith('https://dart.fss.or.kr/') and f['filed']<=company['checked']
                assert f['fs_div']==r['fs_div']
                if 'minus' in f['calculation']:
                    assert len({c['fs_div'] for c in f['components']})==1
        for metric in METRICS:
            d=read(f'data/shipbuilding/company_{key}_{metric}.json')
            assert d['unit']=='백만 USD' and d['original_currency']=='KRW'
            assert any(r.get(metric) is not None for r in rows)
            for v in d['series_views'].values():
                native=dict(next(iter(v['original_series'].values())));dollars=dict(next(iter(v['series'].values()))) if v['series'] else {}
                for day,value in native.items():
                    if value is None:continue
                    assert dollars.get(day) is not None and math.isfinite(dollars[day]),(key,metric,day,'missing FX')
                    assert v['point_sources'][day]['url'] and v['point_notes'][day]
    print('PASS: 7 marine-equipment issuers, 21 cards, actual reporting periods, signed earnings, CFS/OFS provenance and exact-period USD conversion')


if __name__=='__main__':validate()

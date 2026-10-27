"""Validate real published sources, original currency and exact-period USD."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/natgas'


def validate():
    state=json.loads((OUT/'containment_state.json').read_text(encoding='utf8'))
    business=json.loads((OUT/'containment_business.json').read_text(encoding='utf8'))
    fx=json.loads((OUT/'containment_fx.json').read_text(encoding='utf8'))
    assert set(state['companies'])=={'gtt','dongsung_finetec','hankuk_carbon'}
    assert not fx['missing'],fx['missing']
    for company,cohort in state['companies'].items():
        rows=cohort['rows'];assert rows
        assert len({(r['kind'],r['date']) for r in rows})==len(rows)
        assert min(r['year'] for r in rows if r['kind']=='annual')==2014
        for r in rows:
            assert r['start']<=r['date']<=cohort['checked']
            for metric,ref in r['refs'].items():
                assert ref['filed']<=cohort['checked']
                assert ref['url'].startswith(('https://dart.fss.or.kr/','https://www.gtt.fr/'))
                assert isinstance(r[metric],(float,int)) and math.isfinite(r[metric])
        for metric in ['revenue','profit','netincome']:
            doc=json.loads((OUT/f'containment_{company}_{metric}.json').read_text(encoding='utf8'))
            assert doc['id']==f'containment_{company}_{metric}'
            assert doc['unit']=='백만 USD'
            for kind,view in doc['series_views'].items():
                for label,points in view['series'].items():
                    native=dict(view['original_series'][label])
                    for date,usd in points:
                        if usd is None:continue
                        r=next(r for r in rows if r['kind']==kind and r['date']==date)
                        quote=fx['periods'][f"{r['currency']}|{r['start']}|{date}"]
                        assert math.isclose(usd,native[date]/quote['local_per_usd'],rel_tol=1e-10,abs_tol=1e-10)
                        assert view['point_sources'][date]['url']
                        assert any('원자료' in text for text in view['point_notes'][date])
        b=business['companies'][company];assert len(b)>=12
        assert b[-1]['date']==max(r['date'] for r in rows)
    for p in OUT.glob('containment_*.json'):
        doc=json.loads(p.read_text(encoding='utf8'))
        if 'series' not in doc:continue
        assert doc['series']
        for points in doc['series'].values():
            assert len({date for date,_ in points})==len(points)
            for date,value in points:
                assert value is None or (math.isfinite(value) and date in doc['point_sources'])
    gtt=state['companies']['gtt']['rows']
    assert all('profit' not in r and 'netincome' not in r for r in gtt if r['kind']=='quarter')
    assert next(r for r in gtt if r['kind']=='annual' and r['year']==2025)['profit']==472.6
    print('LNG containment: 3 issuer histories, 9 financial charts and 6 source-linked business KPIs passed')


if __name__=='__main__':validate()

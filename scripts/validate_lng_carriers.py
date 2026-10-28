import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/natgas'


def validate():
    state=json.loads((OUT/'lng_carriers_state.json').read_text(encoding='utf8'))
    assert set(state['companies'])=={'flng','glng'}
    for company,cohort in state['companies'].items():
        rows=cohort['rows'];assert len(rows)>=62
        assert len({(r['kind'],r['date']) for r in rows})==len(rows)
        for kind,count in [('quarter',50),('annual',12)]:
            own=[r for r in rows if r['kind']==kind]
            assert len(own)>=count and min(r['year'] for r in own)==2014
        for row in rows:
            assert row['currency']=='USD' and row['start']<=row['date']<=cohort['checked']
            for metric in ['revenue','profit','netincome']:
                assert isinstance(row[metric],(float,int)) and math.isfinite(row[metric])
                assert row['refs'][metric]['filed']<=cohort['checked']
                assert row['refs'][metric]['url'].startswith('https://')
        for metric in ['revenue','profit','netincome']:
            id=f'carrier_{company}_{metric}';doc=json.loads((OUT/(id+'.json')).read_text(encoding='utf8'))
            assert doc['id']==id and doc['unit']=='백만 USD' and set(doc['series_views'])=={'quarter','annual'}
            for kind,view in doc['series_views'].items():
                for label,points in view['series'].items():
                    assert points==view['original_series'][label]
                    assert len({d for d,_ in points})==len(points)
                    for date,value in points:
                        if value is not None:assert date in view['point_sources'] and view['point_notes'][date]
    print('FLNG / GLNG: 6 USD charts, 2014–latest quarter/annual histories, signed total income and source notes passed')


if __name__=='__main__':validate()

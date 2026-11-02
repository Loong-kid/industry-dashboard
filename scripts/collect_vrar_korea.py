"""Original DART accounts for the two Korean XR display semiconductor issuers."""
import argparse,datetime as dt
from pathlib import Path
from collect_ring_sources import collect
from fetch_cosmetics import offline
from fetch_cpu_companies import load,save

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/vrar/korea'


def refresh(full=False):
    meta=load(ROOT/'manual/vrar/companies.json',{})
    meta=dict(meta,companies={k:v for k,v in meta['companies'].items() if v['source_type']=='dart'})
    metadata=CACHE/'companies.json';save(metadata,meta)
    status=collect(full,cache=CACHE,metadata=metadata)
    path=ROOT/'data/vrar/korea_state.json'
    prior=load(path,dict(companies={}))
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    state=offline(meta,prior,asof,status,cache=CACHE)
    for key,co in state['companies'].items():
        floor=meta['companies'][key]['minimum_start']
        for kind in ['rows','annual']:
            co[kind]=[r for r in co[kind] if r['refs']['revenue']['components'][0]['start']>=floor]
        if not co['rows'] or not co['annual']:raise ValueError(key+' has no operating history after SPAC exclusion')
    save(path,state)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full-history',action='store_true');a=p.parse_args()
    refresh(a.full_history)

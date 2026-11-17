"""Original DART financial history for the four selected cleanroom peers."""
import argparse
from pathlib import Path
from collect_ring_sources import collect as originals
from fetch_cosmetics import offline
from fetch_korea_equipment import normalize
from fetch_cpu_companies import load, save, today

ROOT=Path(__file__).resolve().parents[1]
META=ROOT/'manual/cleanroom/companies.json'
CACHE=ROOT/'.cache/cleanroom'
STATE=ROOT/'data/semicon/cleanroom_domestic_state.json'

def collect(refresh=False,full=False):
    meta=load(META,{});old=load(STATE,dict(companies={}))
    status=originals(full,cache=CACHE,metadata=META) if refresh else None
    state=offline(meta,old,today(),status,cache=CACHE,normalize_report=normalize)
    save(STATE,state)
    return state

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--full-history',action='store_true');a=p.parse_args()
    collect(a.refresh,a.full_history)

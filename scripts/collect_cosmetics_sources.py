"""Original OpenDART disclosures for the cosmetics value chain."""
import argparse
import json
from pathlib import Path
from collect_ring_sources import collect as collect_dart

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/cosmetics'
META=ROOT/'manual/cosmetics/companies.json'


def collect(full=False):
    status=collect_dart(full,cache=CACHE,metadata=META)
    from cosmetics_preliminaries import collect as collect_preliminaries
    collect_preliminaries(CACHE,json.loads(META.read_bytes()))
    return status


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full-history',action='store_true');args=p.parse_args()
    collect(args.full_history)

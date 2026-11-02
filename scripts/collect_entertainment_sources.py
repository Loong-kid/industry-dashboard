"""Credential-free original disclosures for the four Korean music agencies."""
import argparse,json
from pathlib import Path
from collect_ring_sources import collect as collect_dart
from cosmetics_preliminaries import collect as collect_preliminaries

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/entertainment'
META=ROOT/'manual/entertainment/companies.json'


def collect(full=False,preliminaries_only=False):
    status=collect_dart(full,cache=CACHE,metadata=META,entities_only=preliminaries_only)
    collect_preliminaries(CACHE,json.loads(META.read_bytes()))
    return status


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full-history',action='store_true');p.add_argument('--preliminaries-only',action='store_true');a=p.parse_args()
    collect(a.full_history,a.preliminaries_only)

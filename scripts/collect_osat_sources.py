"""Archive official packaging/test service issuer accounts, with no credentials saved."""
import argparse
from pathlib import Path
import requests
from collect_ring_sources import collect as collect_dart
from fetch_cpu_companies import load,save

ROOT=Path(__file__).resolve().parents[1]
META=ROOT/'manual/semicon-osat/companies.json'
CACHE=ROOT/'.cache/osat'

def collect(full=False,skip_korea=False):
    status=collect_dart(full,cache=CACHE,metadata=META) if not skip_korea else None
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    for key,spec in load(META,{})['global_companies'].items():
        try:
            r=session.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',timeout=60)
            r.raise_for_status();payload=r.json()
            if int(payload['cik'])!=spec['cik']:raise ValueError('SEC issuer mismatch')
            save(CACHE/(key+'_facts.json'),payload)
            print(key,'SEC original facts archived',flush=True)
        except (requests.RequestException,KeyError,ValueError):
            raise ValueError(key+': original SEC facts unavailable') from None
    return status

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full-history',action='store_true');parser.add_argument('--skip-korea',action='store_true');a=parser.parse_args()
    collect(a.full_history,a.skip_korea)

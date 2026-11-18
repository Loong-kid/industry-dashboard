"""Resume a large first-time DART archive without re-fetching completed issuers."""
import argparse
from pathlib import Path
from collect_ring_sources import collect as collect_dart
from fetch_cpu_companies import load,save

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/semicon-supplychain'
META=ROOT/'manual/semicon-supplychain/companies.json'


def collect(full=False,resume=False):
    if not resume:return collect_dart(full,cache=CACHE,metadata=META)
    meta=load(META,{});prior_entities=load(CACHE/'entities.json',{});completed={}
    for key in meta['companies']:
        status=load(CACHE/(key+'-status.json'),{})
        if status.get('ok') and status.get('reports') and all((CACHE/r['path']).exists() for r in status['reports']):completed[key]=status
    pending={k:v for k,v in meta['companies'].items() if k not in completed}
    print('Resume completed',len(completed),'pending',len(pending),flush=True)
    if pending:
        temporary=CACHE/'pending-metadata.json';save(temporary,dict(meta,companies=pending))
        status=collect_dart(full,cache=CACHE,metadata=temporary)
        entities=dict(prior_entities,**load(CACHE/'entities.json',{}))
    else:status={};entities=prior_entities
    save(CACHE/'entities.json',{k:entities[k] for k in meta['companies']})
    result=dict(completed,**status);save(CACHE/'status.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--full-history',action='store_true');p.add_argument('--resume',action='store_true');a=p.parse_args();collect(a.full_history,a.resume)

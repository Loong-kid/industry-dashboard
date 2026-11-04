"""Build a daily contract follow-up table while preserving verified originals."""
import argparse,datetime as dt
from pathlib import Path
from collect_vrar_contract_sources import CACHE,STATE,collect
from fetch_cpu_companies import load,save
from vrar_contracts import parse,build

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/vrar/contract_watch.json'


def refresh(asof,from_state=False):
    prior=load(STATE,dict(disclosures=[]));records={r['receipt']:r for r in prior['disclosures']};errors=[]
    if not from_state:
        status=load(CACHE/'status.json',{})
        for item in status.get('reports',[]):
            try:
                row=parse((CACHE/item['path']).read_text(encoding='utf8'),item['entry'])
                if row['filed']<=asof:records[row['receipt']]=row
            except Exception as error:errors.append(dict(receipt=item['receipt'],error=type(error).__name__))
        errors+=status.get('errors',[])
        checked=status.get('checked',prior.get('checked',asof))
    else:checked=prior.get('checked',asof);errors=prior.get('errors',[])
    if not records:raise ValueError('No verified Sapien contract originals')
    state=dict(checked=checked,disclosures=sorted(records.values(),key=lambda r:r['receipt']),errors=errors)
    sheet=load(ROOT/'data/vrar/reference_tables.json',{})
    doc=build(state['disclosures'],sheet,asof,checked,errors)
    save(STATE,state);save(OUT,doc)
    print('Sapien contracts:',len(doc['contracts']),'contracts,',len(state['disclosures']),'filings,',len(errors),'review items,',len(doc['unmatched_sheet_notes']),'unmatched sheet notes',flush=True)
    return doc


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--from-state',action='store_true');a=p.parse_args()
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    if a.refresh:
        try:collect()
        except Exception:
            if not STATE.exists():raise
            status=load(CACHE/'status.json',{});status['errors']=[dict(error='Original contract list unavailable')];status['checked']=asof;status['reports']=[];save(CACHE/'status.json',status)
    refresh(asof,a.from_state)

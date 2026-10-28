"""Archive public issuer PDFs from the reviewed IR source registry."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/mining'


def collect():
    registry=json.loads((ROOT/'manual/mining/source_files.json').read_bytes());CACHE.mkdir(parents=True,exist_ok=True)
    def get(item):
        name,meta=item
        try:
            path=CACHE/name
            if not path.exists():
                r=requests.get(meta['url'],timeout=60);r.raise_for_status()
                if not r.content.startswith(b'%PDF'):raise ValueError('Original PDF unavailable')
                path.write_bytes(r.content)
            return name,dict(ok=True)
        except Exception as error:
            print(name,'IR source unavailable:',type(error).__name__,flush=True)
            return name,dict(ok=False)
    with ThreadPoolExecutor(max_workers=4) as pool:status=dict(pool.map(get,registry.items()))
    (CACHE/'ir-status.json').write_text(json.dumps(status),encoding='utf8')
    print(sum(r['ok'] for r in status.values()),'of',len(status),'issuer originals',flush=True)
    return status


if __name__=='__main__':collect()

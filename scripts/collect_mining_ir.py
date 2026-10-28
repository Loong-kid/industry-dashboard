"""Archive public issuer PDFs from the reviewed IR source registry."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import requests
import time

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/mining'


def collect():
    registry=json.loads((ROOT/'manual/mining/source_files.json').read_bytes());CACHE.mkdir(parents=True,exist_ok=True)
    def get(item):
        name,meta=item
        try:
            path=CACHE/name
            if not path.exists():
                started=time.monotonic();chunks=[];size=0
                with requests.get(meta['url'],timeout=(15,30),stream=True) as r:
                    r.raise_for_status()
                    for chunk in r.iter_content(65536):
                        size+=len(chunk)
                        if time.monotonic()-started>180 or size>80_000_000:raise ValueError('PDF download limit')
                        chunks.append(chunk)
                content=b''.join(chunks)
                if not content.startswith(b'%PDF'):raise ValueError('Original PDF unavailable')
                path.write_bytes(content)
            return name,dict(ok=True)
        except Exception as error:
            print(name,'IR source unavailable:',type(error).__name__,flush=True)
            return name,dict(ok=False)
    with ThreadPoolExecutor(max_workers=4) as pool:status=dict(pool.map(get,registry.items()))
    (CACHE/'ir-status.json').write_text(json.dumps(status),encoding='utf8')
    print(sum(r['ok'] for r in status.values()),'of',len(status),'issuer originals',flush=True)
    return status


if __name__=='__main__':collect()

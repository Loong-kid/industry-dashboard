"""Download public DART business tables for reviewed supplier-mix snapshots.

Raw tables are review inputs only; this does not guess sales units or segments.
No DART credential is required or saved by this script.
"""
import concurrent.futures
import json
import re
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from fetch_cpu_companies import load,save

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/semicon-supplychain/business'


def targets(raw,receipt):
    result=[]
    for block in re.split(r'var node\d+\s*=\s*\{\};',raw.decode('utf-8')):
        f=dict(re.findall(r'''node\d+\['(\w+)'\]\s*=\s*"([^"]*)"''',block))
        text=re.sub(r'\s+','',f.get('text',''))
        if not any(t in text for t in ('주요제품및서비스','매출및수주상황')):continue
        if f.get('rcpNo')!=receipt or not all(f.get(k) for k in ('dcmNo','eleId','offset','length','dtd')):continue
        query={k:f[k] for k in ('rcpNo','dcmNo','eleId','offset','length','dtd')}
        result.append(dict(title=f['text'],url='https://dart.fss.or.kr/report/viewer.do?'+urlencode(query),ele=f['eleId']))
    if not result:raise ValueError('Business table viewer mapping unavailable')
    return result


def collect():
    state=load(ROOT/'data/semicon/supplychain_state.json',{})
    CACHE.mkdir(parents=True,exist_ok=True)
    def one(item):
        key,co=item;latest=next(r for r in reversed(co['rows']) if 'revenue' in r)
        url=latest['refs']['revenue']['url'];receipt=re.search(r'rcpNo=(\d+)',url).group(1)
        main=CACHE/f'{key}-{receipt}-main.html'
        session=requests.Session();session.headers['User-Agent']='Mozilla/5.0'
        if not main.exists():r=session.get(url,timeout=30);r.raise_for_status();main.write_bytes(r.content)
        sections=[]
        for target in targets(main.read_bytes(),receipt):
            path=CACHE/f'{key}-{receipt}-{target["ele"]}.html'
            if not path.exists():r=session.get(target['url'],timeout=30);r.raise_for_status();path.write_bytes(r.content)
            soup=BeautifulSoup(path.read_bytes(),'html.parser')
            tables=[]
            for table in soup.select('table'):
                text=table.get_text(' ',strip=True)
                if any(word in text for word in ('매출','제품','사업부문','품목')):
                    rows=[[c.get_text(' ',strip=True) for c in row.find_all(['td','th'],recursive=False)] for row in table.select('tr')]
                    if rows:tables.append(rows)
            sections.append(dict(title=target['title'],url=target['url'],tables=tables,text=soup.get_text(' ',strip=True)))
        value=dict(company=key,receipt=receipt,period=latest['date'],source_url=url,sections=sections)
        save(CACHE/f'{key}-review.json',value);print(key,len(sections),'business sections',sum(len(s['tables']) for s in sections),'review tables',flush=True)
        return key,value
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:return dict(pool.map(one,state['companies'].items()))


if __name__=='__main__':collect()

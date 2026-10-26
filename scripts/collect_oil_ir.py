"""Public issuer IR originals, independently checked per company."""
import datetime as dt
import json
from pathlib import Path
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from collect_oil_sources import CACHE

ROOT=Path(__file__).resolve().parents[1];MANIFEST=ROOT/'manual/oil/source_files.json'

def collect():
    asof=dt.datetime.now(dt.timezone.utc).date().isoformat()
    files=json.loads(MANIFEST.read_bytes());status={k:dict(ok=True,checked=asof) for k in ['tte','equinor','shell']}
    session=requests.Session();session.headers['User-Agent']='industry-dashboard personal research wkorotk@gmail.com'
    for key,url in [('tte','https://totalenergies.com/investors/results'),('equinor','https://www.equinor.com/investors/quarterly-results')]:
        try:
            r=session.get(url,timeout=45);r.raise_for_status()
            if key=='tte':
                for a in BeautifulSoup(r.content,'lxml').select('a[href]'):
                    if a.get_text(strip=True)!='Accounts':continue
                    cells=a.find_parent('tr').find_all(['th','td']);m=re.fullmatch(r'([1-4])Q(\d{2})',cells[0].get_text(strip=True))
                    if not m or int(m[2])<14:continue
                    date=None
                    for fmt in ['%d-%B-%y','%d-%b-%y','%d-%b-%Y','%d-%B-%Y']:
                        try:date=dt.datetime.strptime(cells[1].get_text(strip=True),fmt).date().isoformat();break
                        except ValueError:pass
                    if not date or date>asof:continue
                    files[f'tte-{2000+int(m[2])}-q{m[1]}.pdf']=dict(url=urljoin(url,a['href']),filed=date,date_basis='issuer release date')
            else:
                text=r.text.replace('\\"','"')
                for m in re.finditer(r'"url":"(https:[^"]+\.pdf)"\},"id":"[^"]+","label":"([^"]+)"',text):
                    target,label=m.groups();period=re.search(r'Q([1-4])\s+(20\d{2})',label)
                    if not period or int(period[2])<2014 or not ('report' in label.lower() or 'financial statements and review' in label.lower()):continue
                    name=f'equinor-{period[2]}-q{period[1]}.pdf'
                    files.setdefault(name,dict(url=target,filed=asof,date_basis='verified available on collection date'))
        except Exception as error:status[key]=dict(ok=False,checked=asof,error=type(error).__name__)
    for name,meta in files.items():
        key=name.split('-')[0]
        if meta['filed']>asof:continue
        path=CACHE/name
        if path.exists():continue
        try:
            r=session.get(meta['url'],timeout=90);r.raise_for_status()
            if not (r.content.startswith(b'%PDF') if name.endswith('.pdf') else r.content.startswith(b'PK')):raise ValueError('Source file type mismatch')
            path.write_bytes(r.content)
        except Exception as error:
            if key in status:status[key]=dict(ok=False,checked=asof,error=type(error).__name__)
    MANIFEST.write_text(json.dumps(files,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
    return status

if __name__=='__main__':print(collect())

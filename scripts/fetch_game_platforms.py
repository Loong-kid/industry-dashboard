"""Public platform profiles and observed Steam-wide concurrent online users."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import requests

ROOT=Path(__file__).resolve().parents[1]


def parse_steam_online(html):
    text=BeautifulSoup(html,'html.parser').get_text(' ',strip=True)
    match=re.search(r'PLAYERS ONLINE\s+([\d,]+)\s+PEAK ONLINE\s+([\d,]+)\s+ONLINE NOW',text,re.I)
    if not match:
        raise ValueError('Steam online counters unavailable')
    peak,current=(int(v.replace(',','')) for v in match.groups())
    if not 1e6<=current<=peak<=1e8:
        raise ValueError('Steam online counter bounds/order changed')
    return dict(online_now=current,peak_displayed=peak)


def collect():
    manual=json.loads((ROOT/'manual/games/platforms.json').read_text(encoding='utf-8'))
    path=ROOT/'data/games/platforms.json'
    prior=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    steam=prior.get('steam',{'observations':[]})
    try:
        response=requests.get('https://store.steampowered.com/stats/?l=english',timeout=30)
        response.raise_for_status()
        observation=dict(date=now[:10],observed_at=now,url='https://store.steampowered.com/stats/?l=english',**parse_steam_online(response.text))
        observations={r['date']:r for r in steam['observations']}
        observations[observation['date']]=observation
        # Preserve daily observations for 35 days, then last actual observation
        # of each calendar month. Never sum current concurrent user snapshots.
        from fetch_games import compact_history
        steam=dict(checked=now,status='ok',fetched=now,observations=compact_history(list(observations.values()),[],now[:10]))
    except Exception as exc:
        steam=dict(steam,checked=now,status=type(exc).__name__+' · previous observations retained')
    doc=dict(manual,steam=steam)
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print(f'platforms: {len(manual["profiles"])} profiles; Steam {steam["status"]}',flush=True)
    return doc


if __name__=='__main__':
    collect()

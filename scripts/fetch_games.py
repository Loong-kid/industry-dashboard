"""Key-free game market observations. Never infer downloads from install bands.

SteamCharts: completed calendar months only. Apple: official games chart RSS.
Google Play: public listing metadata and cumulative install lower bounds.
AppBrain estimates are independently dated, manually verified public observations;
they are NOT refreshed by updating a Google Play listing.
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/games"
MANUAL = ROOT / "manual/games"

# A fixed, explicit panel includes long-lived games, recent games and small genres.
# Do not silently change the denominator by replacing it with today's top games.
STEAM = [
 (730,"Counter-Strike 2","슈팅"),(570,"Dota 2","MOBA"),(578080,"PUBG: BATTLEGROUNDS","슈팅"),
 (1172470,"Apex Legends","슈팅"),(440,"Team Fortress 2","슈팅"),(359550,"Rainbow Six Siege","슈팅"),
 (1938090,"Call of Duty","슈팅"),(2767030,"Marvel Rivals","슈팅"),
 (252490,"Rust","생존·제작"),(892970,"Valheim","생존·제작"),(1623730,"Palworld","생존·제작"),
 (108600,"Project Zomboid","생존·제작"),(346110,"ARK: Survival Evolved","생존·제작"),(105600,"Terraria","생존·제작"),
 (1245620,"ELDEN RING","RPG"),(1086940,"Baldur's Gate 3","RPG"),(1091500,"Cyberpunk 2077","RPG"),
 (292030,"The Witcher 3","RPG"),(230410,"Warframe","RPG"),(238960,"Path of Exile","RPG"),
 (413150,"Stardew Valley","시뮬레이션"),(294100,"RimWorld","시뮬레이션"),(427520,"Factorio","시뮬레이션"),
 (255710,"Cities: Skylines","시뮬레이션"),(227300,"Euro Truck Simulator 2","시뮬레이션"),(1222670,"The Sims 4","시뮬레이션"),
 (289070,"Civilization VI","전략"),(8930,"Civilization V","전략"),(281990,"Stellaris","전략"),
 (394360,"Hearts of Iron IV","전략"),(1142710,"Total War: WARHAMMER III","전략"),(813780,"Age of Empires II: DE","전략"),
 (646570,"Slay the Spire","카드·보드"),(2379780,"Balatro","카드·보드"),(286160,"Tabletop Simulator","카드·보드"),
 (1203220,"NARAKA: BLADEPOINT","액션·격투"),(814380,"Sekiro","액션·격투"),(367520,"Hollow Knight","액션·격투"),
 (1145360,"Hades","액션·격투"),(1794680,"Vampire Survivors","액션·격투"),(389730,"TEKKEN 7","액션·격투"),
 (620,"Portal 2","퍼즐"),(400,"Portal","퍼즐"),(210970,"The Witness","퍼즐"),
 (375820,"Human Resource Machine","퍼즐"),(250900,"The Binding of Isaac: Rebirth","액션·격투"),
 (431960,"Wallpaper Engine","제외"),
 (284160,"BeamNG.drive","스포츠·레이싱"),(1551360,"Forza Horizon 5","스포츠·레이싱"),
 (244210,"Assetto Corsa","스포츠·레이싱"),(386360,"SMITE","MOBA"),
 (322330,"Don't Starve Together","생존·제작"),(381210,"Dead by Daylight","호러"),
 (739630,"Phasmophobia","호러"),(1966720,"Lethal Company","호러"),
 (945360,"Among Us","파티·캐주얼"),(1097150,"Fall Guys","파티·캐주얼"),(218620,"PAYDAY 2","슈팅"),
]
STEAM = [g for g in STEAM if g[2] != "제외"]
MOBILE = [
 "com.king.candycrushsaga","com.dreamgames.royalmatch","com.roblox.client","com.kiloo.subwaysurf",
 "com.dts.freefireth","com.block.juggle","com.scopely.monopolygo","com.supercell.clashofclans",
 "com.supercell.clashroyale","com.supercell.brawlstars","com.moonactive.coinmaster","com.playrix.township",
 "com.miHoYo.GenshinImpact","com.miniclip.eightballpool","com.gameloft.android.ANMP.GloftA9HM",
 "com.ea.gp.fifamobile","com.mojang.minecraftpe","com.innersloth.spacemafia","com.nianticlabs.pokemongo",
 "com.YoStarEN.Arknights","com.HoYoverse.hkrpgoversea","com.nexon.bluearchive","com.nexon.maplem.global",
 "com.igg.android.lordsmobile","com.lilithgame.roc.gp","com.fct.global","com.habby.archero",
 "com.zeptolab.ctr.ads","com.ustwo.monumentvalley","com.and.games505.TerrariaPaid",
 "com.balatro.android","com.noodlecake.altosadventure","com.nekki.shadowfight3","com.ea.game.simcitymobile_row",
 "com.rovio.baba","com.outfit7.mytalkingtom2","com.easybrain.sudoku.android","com.dreamgames.royalkingdom",
]

def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)

def get(url):
    r = requests.get(url, timeout=35, headers={"User-Agent":"IndustryDashboard/1.0 (public game statistics)"})
    r.raise_for_status()
    return r

def compact_history(rows, keys, today):
    """Keep the last 35 days and the actual final observation of each month.

    The dashboard needs monthly/yearly comparisons. Preserve those endpoints
    without making every first page load download years of daily charts.
    """
    cutoff = (datetime.strptime(today,"%Y-%m-%d")-timedelta(days=35)).strftime("%Y-%m-%d")
    monthly = {}
    ordered = sorted(rows,key=lambda p:p["date"])
    for row in ordered:
        monthly[(row["date"][:7], *(row[k] for k in keys))] = row
    selected = {(r["date"],*(r[k] for k in keys)):r for r in monthly.values()}
    for row in ordered:
        if row["date"] >= cutoff: selected[(row["date"],*(row[k] for k in keys))] = row
    return sorted(selected.values(),key=lambda r:(r["date"],*(r[k] for k in keys)))

def parse_steam(html, cutoff):
    soup = BeautifulSoup(html, "html.parser")
    points = {}
    for row in soup.select("table.common-table tbody tr"):
        cols = [c.get_text(" ", strip=True) for c in row.select("td")]
        if len(cols) < 5:
            continue
        try:
            date = datetime.strptime(cols[0], "%B %Y").strftime("%Y-%m")
            avg = float(cols[1].replace(",", ""))
            peak = int(cols[4].replace(",", ""))
        except ValueError:
            continue  # Last 30 Days is a rolling window, not the current calendar month.
        if date < cutoff and avg >= 0 and peak >= 0:
            points[date] = [date, avg, peak]
    if not points:
        raise ValueError("No completed Steam calendar months")
    return [points[k] for k in sorted(points)]

def parse_play(html, package):
    soup = BeautifulSoup(html, "html.parser")
    app = None
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            obj = json.loads(tag.string or tag.get_text())
            if obj.get("@type") == "SoftwareApplication":
                app = obj
                break
        except (ValueError, AttributeError):
            continue
    if not app or not app.get("name"):
        raise ValueError("Google Play listing metadata missing")
    text = soup.get_text(" ", strip=True)
    installs = re.search(r"([\d,.]+)\s*([KMB]?)\+\s+Downloads\b", text)
    lower = int(float(installs[1].replace(",", "")) * {"":1,"K":1e3,"M":1e6,"B":1e9}[installs[2]]) if installs else None
    offers = app.get("offers") or [{}]
    if isinstance(offers, dict): offers = [offers]
    rating = app.get("aggregateRating") or {}
    genre = app.get("applicationCategory", "UNKNOWN")
    return {"id":package,"name":app["name"],"genre":genre,"developer":app.get("author",{}).get("name", ""),
            "installs_lower":lower,"rating":float(rating["ratingValue"]) if rating.get("ratingValue") else None,
            "ratings":int(rating["ratingCount"]) if rating.get("ratingCount") else None,
            "price":float(offers[0].get("price",0)),"url":f"https://play.google.com/store/apps/details?id={package}"}

def parse_apple(data):
    entries = data.get("feed", {}).get("entry", [])
    if not entries: raise ValueError("Empty Apple games chart")
    out = []
    for rank, row in enumerate(entries, 1):
        category = row.get("category",{}).get("attributes",{})
        out.append({"id":row["id"]["attributes"]["im:id"],"name":row["im:name"]["label"],"rank":rank,
                    "genre":category.get("label","Games"),"genre_id":category.get("im:id"),
                    "developer":row.get("im:artist",{}).get("label", ""),"url":row["id"]["label"]})
    return out

def collect_steam(today):
    old = load(OUT/"steam.json", {"games":[]})
    prior = {str(g["id"]):g for g in old["games"]}
    errors = []
    def fetch_game(spec):
        appid, name, genre = spec
        try:
            points = parse_steam(get(f"https://steamcharts.com/app/{appid}").text, today[:7])
            return {"id":str(appid),"name":name,"genre":genre,"points":points,"fetched":today,
                    "url":f"https://steamcharts.com/app/{appid}"}
        except Exception as exc:
            errors.append({"id":str(appid),"reason":str(exc)[:100]})
            return prior.get(str(appid))
    with ThreadPoolExecutor(max_workers=3) as pool:
        games = [g for g in pool.map(fetch_game, STEAM) if g]
    if len(games) < len(STEAM)*0.8 or len(errors) > len(STEAM)*0.2:
        raise RuntimeError("Steam successful fetch coverage below 80%; published snapshot preserved")
    save(OUT/"steam.json", {"source":"SteamCharts","fetched":today,"panel_size":len(STEAM),"errors":errors,"games":games})
    return len(games)

def collect_mobile(today, discover):
    old = load(OUT/"mobile.json", {"games":[],"observations":[]})
    prior = {g["id"]:g for g in old["games"]}
    packages = set(MOBILE) | set(prior)
    errors = []
    if discover:
        # Public category discovery, NOT a ranked chart or a complete market census.
        for category in ["PUZZLE","STRATEGY","ROLE_PLAYING","SIMULATION","SPORTS","RACING","CARD","ARCADE","ACTION","ADVENTURE","BOARD","CASUAL"]:
            try:
                soup = BeautifulSoup(get(f"https://play.google.com/store/apps/category/GAME_{category}?hl=en&gl=US").text,"html.parser")
                ids = []
                for link in soup.select('a[href*="/store/apps/details?id="]'):
                    package = parse_qs(urlparse(link["href"]).query).get("id", [None])[0]
                    if package and package not in ids: ids.append(package)
                packages.update(ids[:8])
            except Exception as exc: errors.append({"id":category,"reason":str(exc)[:100]})
    def fetch_game(package):
        try:
            game = parse_play(get(f"https://play.google.com/store/apps/details?id={package}&hl=en&gl=US").text, package)
            game["fetched"] = today
            return game if game["genre"].startswith("GAME_") else None
        except Exception as exc:
            errors.append({"id":package,"reason":str(exc)[:100]})
            return prior.get(package)
    with ThreadPoolExecutor(max_workers=3) as pool:
        games = [g for g in pool.map(fetch_game, sorted(packages)) if g]
    request_errors = sum(e["id"] in packages for e in errors)
    if len(games) < 15 or request_errors > len(packages)*0.2:
        raise RuntimeError("Google Play successful fetch coverage too low; published snapshot preserved")
    observations = { (p["date"],p["id"]):p for p in old.get("observations",[])}
    for game in games:
        if game["fetched"] == today:
            observations[today, game["id"]] = {"date":today,"id":game["id"],"installs_lower":game["installs_lower"],"ratings":game["ratings"]}
    save(OUT/"mobile.json", {"source":"Google Play public listings","fetched":today,"errors":errors,"games":games,
                             "observations":compact_history(list(observations.values()), ["id"], today)})
    return len(games)

def collect_apple(today):
    old = load(OUT/"apple.json", {"charts":[],"history":[]})
    charts, errors = [], []
    previous = {(c["country"],c["kind"]):c for c in old["charts"]}
    def one(spec):
        country, kind = spec
        url = f"https://itunes.apple.com/{country}/rss/{kind}/limit=100/genre=6014/json"
        try:
            r = get(url)
            parsed = parse_apple(r.json())
            # The RSS category is usually only 'Games'; resolve Apple's real
            # game subgenre, without classifying titles by keyword guesses.
            ids = [g["id"] for g in parsed]
            lookup = {}
            for start in range(0,len(ids),100):
                details = get(f"https://itunes.apple.com/lookup?id={','.join(ids[start:start+100])}&country={country}&entity=software").json()
                for app in details.get("results",[]):
                    labels = app.get("genres",[])
                    genre_ids = app.get("genreIds",[])
                    genre_names = {"7001":"Action","7002":"Adventure","7003":"Arcade","7004":"Board","7005":"Card","7006":"Casino","7007":"Dice","7008":"Educational","7009":"Family","7011":"Music","7012":"Puzzle","7013":"Racing","7014":"Role Playing","7015":"Simulation","7016":"Sports","7017":"Strategy","7018":"Trivia","7019":"Word"}
                    specific = [genre_names.get(str(gid),label) for label,gid in zip(labels,genre_ids) if str(gid).startswith("70")]
                    lookup[str(app.get("trackId"))] = specific[0] if specific else "미분류"
            for game in parsed:
                game["genre"] = lookup.get(game["id"],"미분류")
            return {"country":country,"kind":kind,"fetched":today,"source_updated":r.json()["feed"]["updated"]["label"],
                    "url":url,"games":parsed}
        except Exception as exc:
            errors.append({"id":f"{country}/{kind}","reason":str(exc)[:100]})
            return previous.get((country,kind))
    specs = [(c,k) for c in ["kr","us","jp","cn"] for k in ["topfreeapplications","toppaidapplications"]]
    with ThreadPoolExecutor(max_workers=3) as pool: charts = [c for c in pool.map(one,specs) if c]
    if len(charts) < 4 or len(errors) > 4:
        raise RuntimeError("Apple successful fetch coverage too low; published snapshot preserved")
    history = {(h["date"],h["country"],h["kind"]):h for h in old.get("history",[])}
    for c in charts:
        if c["fetched"] == today:
            history[today,c["country"],c["kind"]] = {"date":today,"country":c["country"],"kind":c["kind"],
                "games":[{k:g[k] for k in ["id","name","rank","genre"]} for g in c["games"]]}
    save(OUT/"apple.json", {"source":"Apple games RSS","fetched":today,"errors":errors,"charts":charts,
                            "history":compact_history(list(history.values()),["country","kind"],today)})
    return len(charts)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["all","steam","mobile","apple"],default="all")
    parser.add_argument("--discover",action="store_true")
    args = parser.parse_args()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for name, fn in [("steam",lambda:collect_steam(today)),("mobile",lambda:collect_mobile(today,args.discover)),("apple",lambda:collect_apple(today))]:
        if args.source in ("all",name): print(f"{name}: {fn()} records",flush=True)
    # Public observations keep their original dates; rebuilding never relabels them as fresh.
    for name in ["market","download-estimates"]:
        save(OUT/f"{name}.json",load(MANUAL/f"{name}.json"))

if __name__ == "__main__": main()

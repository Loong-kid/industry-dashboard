"""Steam 신작 흥행 관측: 공식 순위에서 새로 뜬 게임을 찾아 출시 후 흐름을 쌓는다.

무료·무인증 자료만 쓴다.
- Steam 공식 동시접속 상위 100 (ISteamChartsService/GetGamesByConcurrentPlayers): 조회 시점 동접 + Steam이 표시한 오늘 최고값
- Steam 공식 주간 최다 플레이 상위 100 (ISteamChartsService/GetMostPlayedGames): 주간 순위·지난주 순위·주간 최고 동접
- Steam 게임별 현재 접속자 (ISteamUserStats/GetNumberOfCurrentPlayers): 상위 100에서 빠진 뒤에도 같은 시각에 계속 관측
- Steam 상점 상세 (store appdetails, cc=us): 출시일·정가(USD)·무료 여부·장르·협동/멀티 분류
- SteamCharts 월별 기록: 출시 이후 완료된 달의 평균·최고 동접 (수록되지 않은 최신작은 미확보로 둔다)

동시접속자는 판매량·매출·고유 이용자 수가 아니다. 상위 100 밖으로 나간 날을 0으로 채우지 않는다.
SteamSpy는 2025년 이후 출시작의 보유자 수·태그가 비어 있어(예: PEAK 0..20,000) 쓰지 않는다.

사용: python scripts/fetch_steam_trends.py
"""
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_games import get, load, parse_steam, save  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "games" / "steam_trends.json"
API = "https://api.steampowered.com"
CONCURRENT_URL = f"{API}/ISteamChartsService/GetGamesByConcurrentPlayers/v1/"
WEEKLY_URL = f"{API}/ISteamChartsService/GetMostPlayedGames/v1/"
PLAYERS_URL = f"{API}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={{}}"
DETAILS_URL = "https://store.steampowered.com/api/appdetails?appids={}&cc=us&l=english"
STEAMCHARTS_URL = "https://steamcharts.com/app/{}"

NEW_DAYS = 730          # 출시 후 이 기간 안의 게임만 '신작'으로 추적한다
LIFECYCLE_FROM = "2023-01-01"
DAILY_KEEP_DAYS = 400
DETAILS_REFRESH_DAYS = 30
UNTRACKED_RETRY_DAYS = 7

# 2023년 이후 크게 터졌던 저가·협동·단순 루프 게임. 지금 상위 100 밖이어도 출시 후 흐름을 비교하려고 넣는다.
SEED = [
    (3241660, "R.E.P.O."), (3527290, "PEAK"), (3164500, "Schedule I"), (3405340, "Megabonk"),
    (1966720, "Lethal Company"), (2881650, "Content Warning"), (2835570, "Buckshot Roulette"),
    (3097560, "Liar's Bar"), (2567870, "Chained Together"), (4001890, "How to Fish"),
    (4704690, "MECCHA CHAMELEON"), (2670630, "Supermarket Simulator"), (1623730, "Palworld"),
    (3419430, "Bongo Cat"), (3716600, "Mage Arena"), (3949040, "RV There Yet?"), (2062430, "BALL x PIT"),
    (1943950, "Escape the Backrooms"), (2592160, "Dispatch"), (4262460, "ROB RUN"),
]
COOP = {"Online Co-op", "Co-op", "LAN Co-op", "Shared/Split Screen Co-op"}
MULTI = {"Multi-player", "Online PvP", "PvP", "MMO", "Cross-Platform Multiplayer", "LAN PvP", "Shared/Split Screen PvP"} | COOP


def parse_release(text):
    """Steam 표기 출시일을 ISO 날짜로. 월만 있으면 그 달 1일, 분기·미정은 None."""
    text = (text or "").strip()
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y", "%b %Y", "%B %Y", "%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_details(appid, payload):
    entry = payload.get(str(appid)) or {}
    if not entry.get("success"):
        return None
    d = entry.get("data") or {}
    cats = {c.get("description") for c in d.get("categories") or []}
    price = d.get("price_overview") or {}
    if d.get("is_free"):
        price_usd = 0.0
    elif price.get("currency") == "USD" and price.get("initial") is not None:
        price_usd = round(price["initial"] / 100, 2)
    else:
        price_usd = None  # 미국 상점 가격을 확인하지 못함 — 다른 통화로 채우지 않는다
    release = d.get("release_date") or {}
    return {
        "name": d.get("name") or str(appid),
        "type": d.get("type") or "game",
        "release": None if release.get("coming_soon") else parse_release(release.get("date")),
        "free": bool(d.get("is_free")),
        "price_usd": price_usd,
        "genres": [g.get("description") for g in d.get("genres") or [] if g.get("description")],
        "developers": d.get("developers") or [],
        "coop": bool(cats & COOP),
        "online_coop": "Online Co-op" in cats,
        "multi": bool(cats & MULTI),
        "early_access": any(g.get("description") == "Early Access" for g in d.get("genres") or []),
    }


def parse_concurrent(payload):
    r = payload["response"]
    ranks = [[x["appid"], x["rank"], x.get("concurrent_in_game"), x.get("peak_in_game")] for x in r["ranks"]]
    if len(ranks) < 50:
        raise ValueError(f"concurrent ranking too short: {len(ranks)}")
    return datetime.fromtimestamp(r["last_update"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), ranks


def parse_weekly(payload):
    r = payload["response"]
    ranks = [[x["appid"], x["rank"], x.get("last_week_rank"), x.get("peak_in_game")] for x in r["ranks"]]
    if len(ranks) < 50:
        raise ValueError(f"weekly ranking too short: {len(ranks)}")
    return datetime.fromtimestamp(r["rollup_date"], timezone.utc).strftime("%Y-%m-%d"), ranks


def launch_date(app):
    """실제 출시일 추정. 앞서 해보기 후 정식 출시하면 Steam 표기 출시일이 1.0 날짜로 바뀌므로
    SteamCharts 첫 기록 달이 더 이르면 그 달 1일을 쓴다."""
    release = app.get("release")
    points = (app.get("steamcharts") or {}).get("points") or []
    first = points[0][0] if points else None
    if first and (not release or first < release[:7]):
        return f"{first}-01"  # 출시 달보다 이른 기록이 있을 때만 (같은 달이면 Steam 표기 날짜 유지)
    return release


def age_days(app, on):
    start = launch_date(app)
    if not start:
        return None
    return (date.fromisoformat(on) - date.fromisoformat(start)).days


def months_between(start, month):
    return (int(month[:4]) - int(start[:4])) * 12 + int(month[5:7]) - int(start[5:7])


def lifecycle(app):
    """SteamCharts 완료 월을 출시 월 기준 경과 개월로 정렬하고 최고 월평균 대비 비율을 붙인다."""
    points = (app.get("steamcharts") or {}).get("points") or []
    release = launch_date(app) if app.get("release") else None
    if not points or not release:
        return []
    best = max(p[1] for p in points) or None
    rows = []
    for month, avg, peak in points:
        k = months_between(release, month)
        if k < 0:
            continue
        rows.append([k, month, avg, peak, round(avg / best * 100, 1) if best else None])
    return rows


def upsert_daily(rows, day, value):
    rows = [r for r in rows if r[0] != day]
    rows.append([day, *value])
    rows.sort(key=lambda r: r[0])
    cutoff = (date.fromisoformat(day) - timedelta(days=DAILY_KEEP_DAYS)).isoformat()
    return [r for r in rows if r[0] >= cutoff]


def collect(today=None, pause=1.2):
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    old = load(OUT, {}) or {}
    apps = {int(k): v for k, v in (old.get("apps") or {}).items()}
    weekly = old.get("weekly") or []
    errors = []

    # 1) 공식 순위 두 개 — 둘 다 실패하면 기존 파일을 그대로 둔다.
    concurrent = weekly_now = None
    try:
        observed_at, ranks = parse_concurrent(get(CONCURRENT_URL).json())
        concurrent = {"observed_at": observed_at, "ranks": ranks}
    except Exception as e:  # noqa: BLE001
        errors.append(f"concurrent: {type(e).__name__}")
    try:
        week, ranks = parse_weekly(get(WEEKLY_URL).json())
        weekly_now = {"week": week, "ranks": ranks}
        weekly = [w for w in weekly if w["week"] != week] + [weekly_now]
        weekly.sort(key=lambda w: w["week"])
    except Exception as e:  # noqa: BLE001
        errors.append(f"weekly: {type(e).__name__}")
    if concurrent is None and weekly_now is None:
        raise RuntimeError("Steam 공식 순위 두 개 모두 실패 — 기존 자료 유지")
    concurrent = concurrent or old.get("concurrent")

    # 2) 상세 정보 — 처음 본 게임·시드·오래된 상세만 조회
    ranked_ids = {r[0] for r in (concurrent or {}).get("ranks", [])} | {r[0] for r in (weekly_now or {}).get("ranks", [])}
    for appid, name in SEED:
        apps.setdefault(appid, {"name": name})
        apps[appid]["seed"] = True
    for appid in ranked_ids:
        apps.setdefault(appid, {})
        apps[appid].setdefault("first_seen", today)
    for appid in sorted(set(apps)):
        app = apps[appid]
        checked = app.get("details_checked")
        stale = not checked or (date.fromisoformat(today) - date.fromisoformat(checked)).days >= DETAILS_REFRESH_DAYS
        if not stale or (appid not in ranked_ids and not app.get("seed") and checked):
            continue
        try:
            parsed = parse_details(appid, get(DETAILS_URL.format(appid)).json())
            if parsed:
                app.update(parsed)
                app["details_checked"] = today
            else:
                errors.append(f"details {appid}: unavailable")
        except Exception as e:  # noqa: BLE001
            errors.append(f"details {appid}: {type(e).__name__}")
        time.sleep(pause)

    # 3) SteamCharts 월별 기록 — 2023년 이후 출시작 중 시드이거나 상위 100에 든 게임. 달이 바뀔 때만 다시 받는다.
    this_month = today[:7]
    for appid, app in apps.items():
        if app.get("type", "game") != "game" or not app.get("release") or app["release"] < LIFECYCLE_FROM:
            continue
        sc = app.get("steamcharts") or {}
        if sc.get("status") == "ok" and sc.get("checked", "")[:7] == this_month:
            continue
        if sc.get("status") == "untracked" and (date.fromisoformat(today) - date.fromisoformat(sc["checked"])).days < UNTRACKED_RETRY_DAYS:
            continue
        try:
            resp = get_steamcharts(appid)
            if resp is None:
                app["steamcharts"] = {**sc, "status": "untracked", "checked": today}
            else:
                app["steamcharts"] = {"status": "ok", "checked": today, "points": parse_steam(resp, this_month)}
        except ValueError:  # 아직 완료된 달이 없음
            app["steamcharts"] = {**sc, "status": "no_complete_month", "checked": today}
        except Exception as e:  # noqa: BLE001
            errors.append(f"steamcharts {appid}: {type(e).__name__}")
        time.sleep(pause)
    # 4) 추적 대상 = 출시 2년 이내 게임(시드 포함). 상위 100 밖이어도 현재 접속자를 같은 시각에 조회한다.
    in_top = {r[0]: r for r in (concurrent or {}).get("ranks", [])}
    tracked = [a for a, app in apps.items() if app.get("type", "game") == "game"
               and age_days(app, today) is not None and 0 <= age_days(app, today) <= NEW_DAYS]
    for appid in tracked:
        app = apps[appid]
        rank = in_top.get(appid)
        if rank:
            ccu, peak, position = rank[2], rank[3], rank[1]
        else:
            try:
                resp = get(PLAYERS_URL.format(appid)).json()["response"]
                if resp.get("result") != 1:
                    raise ValueError("no count")
                ccu, peak, position = resp.get("player_count"), None, None
            except Exception as e:  # noqa: BLE001
                errors.append(f"players {appid}: {type(e).__name__}")
                continue
            time.sleep(0.3)
        app["daily"] = upsert_daily(app.get("daily") or [], today, [ccu, peak, position])

    for app in apps.values():
        app["lifecycle"] = lifecycle(app)
        app["launch"] = launch_date(app)

    result = {
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": today,
        "concurrent": concurrent,
        "weekly": weekly,
        "apps": {str(k): apps[k] for k in sorted(apps)},
        "errors": errors,
        "rules": {"new_days": NEW_DAYS, "lifecycle_from": LIFECYCLE_FROM, "seed": [a for a, _ in SEED]},
    }
    validate(result)
    save(OUT, result)
    return result


def get_steamcharts(appid):
    import requests
    r = requests.get(STEAMCHARTS_URL.format(appid), timeout=35,
                     headers={"User-Agent": "IndustryDashboard/1.0 (public game statistics)"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text


def validate(result):
    ranks = (result.get("concurrent") or {}).get("ranks") or []
    assert len(ranks) >= 50, "concurrent ranking missing"
    assert len({r[0] for r in ranks}) == len(ranks), "duplicate appid in concurrent ranking"
    for app in result["apps"].values():
        for row in app.get("daily") or []:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[0])
            assert row[1] is None or row[1] >= 0
        for row in app.get("lifecycle") or []:
            assert row[0] >= 0 and row[2] >= 0


if __name__ == "__main__":
    out = collect()
    named = sum(1 for a in out["apps"].values() if a.get("release"))
    print(f"apps {len(out['apps'])} (with release {named}), weekly {len(out['weekly'])}, errors {len(out['errors'])}")
    for e in out["errors"][:20]:
        print("  ", e)

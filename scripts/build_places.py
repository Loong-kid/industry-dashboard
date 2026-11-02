"""🌐 지구본 지명 라벨: Natural Earth(퍼블릭 도메인) 국가·도시 한국어 이름 → data/sites/places.json.

한 번 만들어 두는 정적 데이터라 매일 수집에는 넣지 않는다. 다시 만들 때:
    python scripts/build_places.py
바다·대양 이름과 라벨 위치는 아래 SEAS에 직접 적었다(동해·황해 표기 포함).
"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sites" / "places.json"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"

# NE 한국어 이름 중 정식 국호·옛 표기를 흔히 쓰는 이름으로 바꾼다. None 이면 라벨을 뺀다.
COUNTRY_NAME = {
    "China": "중국", "Taiwan": "대만", "North Korea": "북한", "South Korea": "한국", "Turkey": "튀르키예",
    "Australia": "호주", "South Africa": "남아공", "Dem. Rep. Congo": "민주콩고", "Congo": "콩고",
    "Central African Rep.": "중앙아프리카", "Dominican Rep.": "도미니카공화국", "Eq. Guinea": "적도기니",
    "New Caledonia": "뉴칼레도니아", "Bosnia and Herz.": "보스니아", "Trinidad and Tobago": "트리니다드토바고",
    "Fr. S. Antarctic Lands": None, "N. Cyprus": None, "Somaliland": None,
}
# 110m 국경에 없는 작은 나라 중 사이트가 많은 곳.
EXTRA_COUNTRIES = [
    {"n": "싱가포르", "lat": 1.35, "lon": 103.82, "r": 4},
    {"n": "바레인", "lat": 26.03, "lon": 50.55, "r": 6},
    {"n": "몰타", "lat": 35.9, "lon": 14.45, "r": 6},
]
COUNTRY_RANK = {"Qatar": 4, "United Arab Emirates": 3, "Oman": 3}  # LNG 비중이 커서 조금 일찍 보이게

# 도시 이름: NE 이름에서 행정 접미사를 떼고, 틀린 것만 바로잡는다.
CITY_NAME = {
    "Tokyo": "도쿄", "Hami": "하미", "Kuwait City": "쿠웨이트시티", "Brussels": "브뤼셀", "Zanzibar": "잔지바르",
    "Pyongyang": "평양", "Seoul": "서울", "Ho Chi Minh City": "호찌민", "Kiev": "키이우", "Kyiv": "키이우",
}
EAST_ASIA = {"KR", "KP", "JP", "CN", "TW", "VN"}
# 1:50m 에 없는 국내 산업도시. 국내 도시는 모두 한 단계 일찍(t=1) 보이게 한다.
# 인구(만 명 단위 근사)는 같은 단계 안에서 겹칠 때 큰 도시를 남기는 데만 쓴다.
EXTRA_CITIES = [
    ("대구", 35.871, 128.601, 2_370_000), ("울산", 35.539, 129.311, 1_100_000), ("창원", 35.228, 128.681, 1_000_000),
    ("평택", 36.992, 127.113, 590_000), ("포항", 36.019, 129.343, 500_000), ("여수", 34.760, 127.662, 270_000),
    ("거제", 34.880, 128.621, 230_000),
]
SUFFIX = re.compile(r"(특별자치시|특별시|광역시|직할시|시)$")

# 대양 t=0(항상), 바다 t=1. 라벨은 바다 한가운데에 오도록 손으로 찍은 좌표.
SEAS = [
    ("태평양", 28, -160, 0), ("태평양", -25, -128, 0), ("대서양", 32, -42, 0), ("대서양", -25, -16, 0),
    ("인도양", -22, 80, 0), ("북극해", 84, 20, 0), ("남극해", -62, 30, 0),
    ("동해", 40, 135, 1), ("황해", 35.5, 123.6, 1), ("동중국해", 29, 126, 1), ("남중국해", 14, 114, 1),
    ("필리핀해", 20, 132, 1), ("오호츠크해", 55, 148, 1), ("베링해", 58, -178, 1), ("산호해", -16, 155, 1),
    ("태즈먼해", -40, 160, 1), ("벵골만", 15, 88, 1), ("아라비아해", 15, 64, 1), ("페르시아만", 27, 51.5, 1),
    ("홍해", 20, 38.6, 1), ("지중해", 34.5, 18, 1), ("흑해", 43.2, 34.5, 1), ("카스피해", 42, 51, 1),
    ("북해", 56, 3, 1), ("바렌츠해", 73, 40, 1), ("멕시코만", 25, -90, 1), ("카리브해", 15, -75, 1),
    ("알래스카만", 57, -145, 1), ("허드슨만", 60, -86, 1), ("래브라도해", 58, -54, 1), ("배핀만", 73, -66, 1),
    ("보퍼트해", 73, -142, 1), ("기니만", 2, 3, 1), ("웨들해", -72, -45, 1), ("로스해", -75, -175, 1),
]


def fetch(name):
    req = urllib.request.Request(NE + name + ".geojson", headers={"User-Agent": "industry-dashboard-build-places/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return [f["properties"] for f in json.load(r)["features"]]


def city_name(p):
    if p["NAME"] in CITY_NAME:
        return CITY_NAME[p["NAME"]]
    n = p["NAME_KO"].strip()
    if n.endswith(" 시"):
        n = n[:-2]
    if p["ISO_A2"] in EAST_ASIA and len(n) > 2:
        n = SUFFIX.sub("", n)
    return n


def build():
    countries = []
    for p in fetch("ne_110m_admin_0_countries"):
        name = COUNTRY_NAME.get(p["NAME"], p["NAME_KO"])
        if not name:
            continue
        countries.append({"n": name, "lat": round(p["LABEL_Y"], 2), "lon": round(p["LABEL_X"], 2),
                          "r": COUNTRY_RANK.get(p["NAME"], p["LABELRANK"])})
    countries += EXTRA_COUNTRIES

    cities = []
    for p in fetch("ne_50m_populated_places"):
        capital = p["FEATURECLA"].startswith("Admin-0 cap")
        if p["SCALERANK"] > 4 and not capital:
            continue
        t = 0 if p["SCALERANK"] <= 1 else 1 if p["SCALERANK"] <= 3 or capital or p["ISO_A2"] == "KR" else 2
        row = {"n": city_name(p), "lat": round(p["LATITUDE"], 3), "lon": round(p["LONGITUDE"], 3), "t": t, "pop": p["POP_MAX"]}
        if capital:
            row["cap"] = 1
        cities.append(row)
    cities += [{"n": n, "lat": lat, "lon": lon, "t": 1, "pop": pop} for n, lat, lon, pop in EXTRA_CITIES]
    # 화면에서 겹치면 앞선 도시가 남는다(globe.js declutter): 단계 → 수도 → 인구 순.
    cities.sort(key=lambda c: (c["t"], -c.get("cap", 0), -c["pop"], c["n"]))
    for c in cities:
        del c["pop"]

    seas = [{"n": n, "lat": lat, "lon": lon, "t": t} for n, lat, lon, t in SEAS]
    return {
        "source": "Natural Earth 1:110m 국가·1:50m 도시(퍼블릭 도메인), 바다 이름·위치는 직접 입력",
        "source_url": "https://www.naturalearthdata.com/",
        "countries": countries, "cities": cities, "seas": seas,
    }


def main():
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: 국가 {len(doc['countries'])} · 도시 {len(doc['cities'])} · 바다 {len(doc['seas'])}")


if __name__ == "__main__":
    main()

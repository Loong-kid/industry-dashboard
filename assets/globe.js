/* 🌐 지구본: 등록한 사이트(LNG 터미널·ESS 공장·내 사이트)를 3D 지구 위에 찍는다.
   data/sites/sites.json (scripts/build_sites.py) + 이 브라우저에 임시 저장한 사이트(localStorage). */
const LIBS = [
  "https://cdn.jsdelivr.net/npm/globe.gl@2.46.2/dist/globe.gl.min.js",
  "https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js",
];
const COUNTRIES = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json";
const LAYER_COLORS = {lng_export: "#eb6834", lng_import: "#2a78d6", ess_system: "#1baf7a", ess_cell: "#eda100",
  dc_kr: "#4a3aa7", dc_kr_candidate: "#9085e9", user: "#e34948"};
const STATUS_ORDER = ["operating", "construction", "planned", "inactive"];
const LOCAL_KEY = "globe_local_sites";
const LABELS_KEY = "globe_labels";
const PLACES = "data/sites/places.json"; // scripts/build_places.py (Natural Earth 한국어 지명)
// scripts/build_korea_admin.py. 시·도는 처음부터, 시·군·구는 그만큼 다가갔을 때 받는다.
const KOREA_SIDO = "data/sites/korea_sido.json";
const KOREA_SIGUNGU = "data/sites/korea_sigungu.json";
const ADM1_ALT = 0.8, ADM2_ALT = 0.22; // 이 고도 아래에서 시·도 / 시·군·구를 보여 준다
const KOREA_ID = "410"; // world-atlas의 대한민국: 110m 해안선이 거칠어 확대하면 통계청 경계로 바꿔 그린다
const prefs = {layers: new Set(["lng_export", "lng_import", "ess_system", "ess_cell", "dc_kr", "user"]),
  statuses: new Set(["operating", "construction", "planned"]), query: ""};

const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const fmt = v => v == null ? "" : v.toLocaleString("ko-KR", {maximumFractionDigits: 2});

let libsPromise = null;
function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src; s.async = true; s.onload = resolve; s.onerror = () => reject(new Error(src));
    document.head.appendChild(s);
  });
}
function loadLibs() {
  libsPromise ||= Promise.all(LIBS.map(loadScript)).then(() => fetch(COUNTRIES).then(r => r.json()))
    .then(topo => topojson.feature(topo, topo.objects.countries).features)
    .catch(e => { libsPromise = null; throw e; });
  return libsPromise;
}

function readLocal() {
  try { return JSON.parse(localStorage.getItem(LOCAL_KEY) || "[]"); } catch { return []; }
}
function writeLocal(rows) {
  try { localStorage.setItem(LOCAL_KEY, JSON.stringify(rows)); return true; } catch { return false; }
}
function readLabelsPref() {
  try { return localStorage.getItem(LABELS_KEY) !== "off"; } catch { return true; }
}
function writeLabelsPref(on) {
  try { localStorage.setItem(LABELS_KEY, on ? "on" : "off"); } catch { /* 저장 못 하면 이번 방문만 */ }
}

// 지명 라벨: 멀리서는 대양·큰 나라만, 다가갈수록 바다·작은 나라·도시를 더한다. 지평선 너머는 뺀다.
const toRad = d => d * Math.PI / 180;
function angDist(lat1, lon1, lat2, lon2) {
  const a = Math.sin(toRad(lat2 - lat1) / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(toRad(lon2 - lon1) / 2) ** 2;
  return 2 * Math.asin(Math.min(1, Math.sqrt(a))) * 180 / Math.PI;
}
function wantedPlaces(places, pov) {
  const alt = pov.altitude;
  const horizon = Math.acos(1 / (1 + alt)) * 180 / Math.PI * 0.85;
  const countryRank = alt > 2.2 ? 2 : alt > 1.5 ? 3 : alt > 0.9 ? 5 : 9;
  const cityTier = alt < 0.45 ? 2 : alt < 0.9 ? 1 : alt < 1.6 ? 0 : -1;
  const seaTier = alt < 2.8 ? 1 : 0;
  return [...places.seas.filter(p => p.t <= seaTier), ...places.countries.filter(p => p.r <= countryRank),
    ...places.cities.filter(p => p.t <= cityTier), ...(alt < ADM1_ALT ? places.adm1 : []), ...(alt < ADM2_ALT ? places.adm2 : [])]
    .filter(p => angDist(pov.lat, pov.lng, p.lat, p.lon) < horizon);
}
// 화면에서 겹치면 중요도가 낮은 라벨을 뺀다: 대양 → 큰 나라 → 큰 도시 → 수도 → 작은 나라 → 바다 → 나머지 도시.
function placePriority(p) {
  if (p.kind === "sea") return p.t === 0 ? 0 : 3.5;
  if (p.kind === "adm1") return 1.9;
  if (p.kind === "adm2") return 3.7;
  if (p.kind === "country") return (p.r <= 3 ? 1 : 3) + p.r / 100;
  return p.t === 0 ? 2 : p.cap ? 2.5 : 3.8 + p.t;
}
function labelBox(p, x, y) {
  const fs = p.kind === "country" ? 12.3 : p.kind === "sea" ? (p.t === 0 ? 16 : 11.5) : p.kind === "adm2" ? 10 : 11; // 한글 한 자 폭 + 자간
  const w = p.n.length * fs + 4, h = 15;
  return p.kind === "city" ? [x - 4, y - h / 2, x + 6 + w, y + h / 2] : [x - w / 2, y - h / 2, x + w / 2, y + h / 2];
}
function declutter(rows, globe, width, height) {
  const placed = [], kept = [];
  for (const p of rows.slice().sort((a, b) => placePriority(a) - placePriority(b))) {
    const {x, y} = globe.getScreenCoords(p.lat, p.lon, 0.008);
    if (!(x > -40 && y > -20 && x < width + 40 && y < height + 20)) continue;
    const b = labelBox(p, x, y);
    if (placed.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1])) continue;
    placed.push(b); kept.push(p);
  }
  return kept;
}
function placeElement(p) {
  if (p.el) return p.el;
  const el = document.createElement("div");
  el.className = `gl-pl gl-pl-${p.kind}${p.kind === "sea" && p.t === 0 ? " gl-pl-ocean" : ""}${p.cap ? " gl-pl-cap" : ""}`;
  el.innerHTML = `<span>${esc(p.n)}</span>`;
  return (p.el = el);
}

function localToSite(row) {
  return {id: "local:" + row.id, layer: "user", name: row.name, company: row.company || null, country: row.country || null,
    lat: row.lat, lon: row.lon, accuracy: "facility", status: row.status || "operating", category: row.category,
    detail: row.note ? [["메모", row.note]] : [], local: true, source: "이 브라우저"};
}

function theme() {
  const css = getComputedStyle(document.documentElement);
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  return {
    dark, ink: css.getPropertyValue("--ink").trim(), muted: css.getPropertyValue("--muted").trim(),
    ocean: dark ? "#132538" : "#a9c6e2", land: dark ? "#34372f" : "#fbfaf5", border: dark ? "#5b6057" : "#a8a79c",
    atmosphere: dark ? "#3987e5" : "#9cc2ea", adminFine: dark ? "rgba(255,255,255,.28)" : "rgba(60,60,50,.3)",
  };
}

export function mount(root) {
  root.innerHTML = `
    <div class="gl-root">
      <section class="gl-intro">
        <h2>등록한 사이트를 지구본 위에서 본다</h2>
        <p>지구를 끌어서 돌리고, 휠·두 손가락으로 확대한다. 점을 누르면 상세가 열린다. 막대 높이는 LNG 가동·건설 용량(Mtpa)이나 ESS 설치 능력(GWh/년)에 비례한다.</p>
      </section>
      <div class="gl-layout">
        <aside class="gl-panel" aria-label="사이트 필터">
          <fieldset class="gl-group"><legend>레이어</legend><div id="gl-layers"></div></fieldset>
          <fieldset class="gl-group"><legend>상태</legend><div id="gl-statuses"></div></fieldset>
          <p class="gl-note">막대 높이는 규모다(제곱근 눈금, 막대에 마우스를 올리면 값이 나온다). LNG는 Mtpa, ESS는 GWh/년, 데이터센터는 수전용량 MW이고 단위가 달라 서로 비교하지 않는다. 규모 자료가 없으면 가장 낮게 그린다.</p>
          <label class="gl-search">찾기<input id="gl-query" type="search" placeholder="이름·회사·국가" autocomplete="off"></label>
          <div id="gl-detail" class="gl-detail" hidden></div>
          <p id="gl-count" class="gl-count" aria-live="polite"></p>
          <ol id="gl-list" class="gl-list"></ol>
        </aside>
        <div class="gl-stage">
          <div id="gl-globe" class="gl-globe" role="application" aria-label="사이트 지구본. 끌어서 회전, 확대 가능"></div>
          <p id="gl-status" class="page-loading gl-loading">지구본 불러오는 중…</p>
          <div class="gl-tools">
            <button type="button" id="gl-labels" aria-pressed="true">지명</button>
            <button type="button" id="gl-spin" aria-pressed="true">자동 회전</button>
            <button type="button" id="gl-home">전체 보기</button>
            <button type="button" id="gl-add" aria-pressed="false">＋ 사이트 추가</button>
          </div>
          <form id="gl-form" class="gl-form" hidden>
            <p class="gl-form-hint">지구본에서 위치를 누르면 위도·경도가 채워진다.</p>
            <div class="gl-form-grid">
              <label>이름<input name="name" required maxlength="80"></label>
              <label>회사<input name="company" maxlength="80"></label>
              <label>분류<select name="category"></select></label>
              <label>위도<input name="lat" type="number" step="0.0001" min="-90" max="90" required></label>
              <label>경도<input name="lon" type="number" step="0.0001" min="-180" max="180" required></label>
              <label class="gl-wide">메모<input name="note" maxlength="200"></label>
            </div>
            <div class="gl-form-actions">
              <button type="submit">이 브라우저에 저장</button>
              <button type="button" id="gl-cancel">닫기</button>
            </div>
          </form>
        </div>
      </div>
      <section class="gl-foot">
        <h3>이 브라우저에 저장한 사이트</h3>
        <p class="gl-note">임시 저장은 이 브라우저에만 남는다. 모든 기기에서 보려면 아래 JSON을 복사해 <code>manual/sites.json</code>의 <code>sites</code>에 붙여 넣는다(또는 Claude·Codex에게 등록을 부탁).</p>
        <div id="gl-local"></div>
        <p id="gl-sources" class="gl-note"></p>
      </section>
    </div>`;

  const $ = id => root.querySelector("#" + id);
  let doc = null, globe = null, selected = null, addMode = false, pending = null, disposed = false;
  let places = null, labelsOn = readLabelsPref(), shownPlaces = [], labelFrame = 0;
  // 한국 행정구역: 경계선(mesh)과 지금 그리는 단계. 막대 굵기도 고도 단계에 맞춘다.
  let sidoLines = [], sigunguLines = [], sigunguReq = null, adminLevel = 0, radiusScale = 1, heightScale = 1;
  let localRows = readLocal(), localSites = localRows.map(localToSite);
  const cleanups = [];
  const setLocal = rows => { localRows = rows; localSites = rows.map(localToSite); return writeLocal(rows); };

  const allSites = () => [...(doc?.sites || []), ...localSites];
  const visible = () => {
    const q = prefs.query.trim().toLowerCase();
    return allSites().filter(s => prefs.layers.has(s.layer) && prefs.statuses.has(s.status)
      && (!q || [s.name, s.company, s.country].some(v => v && v.toLowerCase().includes(q))));
  };
  const layerName = id => doc?.layers.find(l => l.id === id)?.name || id;
  const statusName = id => doc?.status_labels?.[id] || id;

  function chips() {
    const counts = {};
    for (const s of allSites()) counts[s.layer] = (counts[s.layer] || 0) + 1;
    $("gl-layers").innerHTML = doc.layers.map(l => `
      <label class="gl-chip"><input type="checkbox" value="${l.id}" ${prefs.layers.has(l.id) ? "checked" : ""}>
        <span class="gl-dot" style="--c:${LAYER_COLORS[l.id]}"></span>${esc(l.name)} <small>${fmt(counts[l.id] || 0)}</small></label>`).join("");
    $("gl-statuses").innerHTML = STATUS_ORDER.map(s => `
      <label class="gl-chip"><input type="checkbox" value="${s}" ${prefs.statuses.has(s) ? "checked" : ""}>
        <span class="gl-status-mark gl-st-${s}"></span>${esc(statusName(s))}</label>`).join("");
  }

  function siteHeight(s) {
    if (!s.size) return 0.012 * heightScale;
    const k = s.size_unit === "Mtpa" ? 0.012 : s.size_unit === "MW" ? 0.006 : 0.004; // 대형 액화 77Mtpa≈0.1, ESS 40GWh≈0.04, 데이터센터 100MW≈0.07
    return Math.min(0.12, 0.012 + Math.sqrt(s.size) * k) * heightScale;
  }
  function siteColor(s) {
    const c = LAYER_COLORS[s.layer] || "#888";
    const alpha = {operating: "ff", construction: "dd", planned: "99", inactive: "55"}[s.status] || "ff";
    return s === selected ? (theme().dark ? "#ffffff" : "#0b0b0b") : c + alpha;
  }
  // 막대 높이가 뜻하는 값. 규모 자료가 없으면 가장 낮게 그린다.
  function heightMeaning(s) {
    if (!s.size) return "규모 자료 없음 (가장 낮게 표시)";
    const what = s.layer === "lng_export" ? "액화 능력" : s.layer === "lng_import" ? "재기화 능력" : s.size_unit === "MW" ? "수전용량" : "연간 생산능력";
    return `${what} ${fmt(s.size)} ${s.size_unit}`;
  }
  function tooltip(s) {
    return `<div class="gl-tip"><b>${esc(s.name)}</b><span>${esc(layerName(s.layer))} · ${esc(statusName(s.status))}</span>${s.company ? `<span>${esc(s.company)}</span>` : ""}<span class="gl-tip-height">막대 높이: ${esc(heightMeaning(s))}</span></div>`;
  }
  const pointRadius = s => (s.layer === "user" || s.local ? 0.42 : s.layer.startsWith("ess") ? 0.34 : s.layer.startsWith("dc_") ? 0.3 : 0.26) * radiusScale;

  function drawPoints() {
    if (!globe) return;
    const rows = visible();
    globe.pointsData(rows);
    $("gl-count").textContent = `${fmt(rows.length)}곳 표시 중`;
    const list = rows.slice().sort((a, b) => (b.layer === "user") - (a.layer === "user") || (b.size || 0) - (a.size || 0) || a.name.localeCompare(b.name, "ko"));
    const shown = list.slice(0, 200);
    $("gl-list").innerHTML = shown.map((s, i) => `
      <li><button type="button" data-i="${i}" ${s === selected ? 'aria-current="true"' : ""}>
        <span class="gl-dot" style="--c:${LAYER_COLORS[s.layer]}"></span>
        <span class="gl-li-main"><b>${esc(s.name)}</b><small>${esc([s.company, s.country].filter(Boolean).join(" · "))}</small></span>
        <small class="gl-li-st">${esc(statusName(s.status))}</small></button></li>`).join("")
      + (list.length > shown.length ? `<li class="gl-more">외 ${fmt(list.length - shown.length)}곳 — 찾기로 좁히기</li>` : "");
    $("gl-list").querySelectorAll("button[data-i]").forEach(b => b.addEventListener("click", () => select(shown[+b.dataset.i], true)));
  }

  function select(s, fly) {
    selected = s;
    const box = $("gl-detail");
    if (!s) { box.hidden = true; drawPoints(); return; }
    const near = allSites().filter(o => o !== s && Math.abs(o.lat - s.lat) < 0.02 && Math.abs(o.lon - s.lon) < 0.02);
    const acc = doc.accuracy_labels?.[s.accuracy] || s.accuracy;
    box.hidden = false;
    box.innerHTML = `
      <div class="gl-detail-head"><span class="gl-dot" style="--c:${LAYER_COLORS[s.layer]}"></span>
        <div><h3>${esc(s.name)}</h3><p>${esc(layerName(s.layer))} · ${esc(statusName(s.status))}${s.status_detail ? ` (${esc(s.status_detail)})` : ""}</p></div>
        <button type="button" class="gl-close" aria-label="상세 닫기">×</button></div>
      <dl><dt>막대 높이</dt><dd>${esc(heightMeaning(s))}</dd>${s.company ? `<dt>회사</dt><dd>${esc(s.company)}</dd>` : ""}${s.country ? `<dt>국가</dt><dd>${esc(s.country)}</dd>` : ""}
        ${(s.detail || []).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}
        <dt>좌표</dt><dd>${s.lat.toFixed(4)}, ${s.lon.toFixed(4)} · ${esc(acc)}</dd></dl>
      ${s.url ? `<p><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url_label || "원문 보기")} ↗</a></p>` : ""}
      ${near.length ? `<p class="gl-near">같은 위치 ${near.length}곳: ${near.slice(0, 6).map((o, i) => `<button type="button" data-near="${i}">${esc(o.name)}</button>`).join("")}</p>` : ""}
      ${s.local ? `<p><button type="button" class="gl-remove">이 브라우저에서 삭제</button></p>` : ""}`;
    box.querySelector(".gl-close").addEventListener("click", () => select(null));
    box.querySelectorAll("[data-near]").forEach(b => b.addEventListener("click", () => select(near[+b.dataset.near], false)));
    box.querySelector(".gl-remove")?.addEventListener("click", () => {
      setLocal(localRows.filter(r => "local:" + r.id !== s.id)); select(null); chips(); renderLocal();
    });
    if (fly && globe) globe.pointOfView({lat: s.lat, lng: s.lon, altitude: Math.min(globe.pointOfView().altitude, 1.4)}, 900);
    if (fly) stopSpin();
    drawPoints();
  }

  // 고도에 따라 행정구역 경계와 막대 굵기를 바꾼다. 단계가 바뀔 때만 다시 그린다.
  function applyZoom() {
    const alt = globe.pointOfView().altitude;
    if (alt < ADM2_ALT * 2 && labelsOn) loadSigungu();
    const level = !labelsOn ? 0 : alt < ADM2_ALT && sigunguLines.length ? 2 : alt < ADM1_ALT ? 1 : 0;
    if (level !== adminLevel) { adminLevel = level; drawAdminLines(); }
    // 막대는 지구 기준 크기라 그대로 두면 다가갈수록 화면을 덮는다. 굵기와 높이를 함께 줄인다.
    const scale = alt < 0.08 ? 0.12 : alt < 0.22 ? 0.25 : alt < 0.5 ? 0.45 : alt < 1 ? 0.7 : 1;
    if (scale !== radiusScale) {
      radiusScale = scale; heightScale = scale * (alt < 0.22 ? 0.7 : 1);
      globe.pointRadius(pointRadius).pointAltitude(siteHeight);
    }
  }
  function drawAdminLines() {
    globe.pathsData(adminLevel === 2 ? [...sigunguLines, ...sidoLines] : adminLevel === 1 ? sidoLines : []);
  }
  // 시·도 경계와 겹치는 선은 빼지 않는다. 시·도 선을 위에 더 진하게 그려 구분한다.
  const meshLines = (topology, kind) => {
    const object = Object.values(topology.objects)[0];
    return topojson.mesh(topology, object, (a, b) => a !== b).coordinates.map(pts => ({pts, kind}));
  };
  function loadSigungu() {
    sigunguReq ||= fetch(KOREA_SIGUNGU).then(r => r.ok ? r.json() : null).then(d => {
      if (disposed || !d) return;
      sigunguLines = meshLines(d.topology, "sigungu");
      if (places) places.adm2 = d.labels.map(p => ({...p, kind: "adm2"}));
      queueLabels();
    }).catch(() => {});
  }

  function drawLabels() {
    labelFrame = 0;
    if (!globe) return;
    applyZoom();
    const el = $("gl-globe");
    const rows = labelsOn && places ? declutter(wantedPlaces(places, globe.pointOfView()), globe, el.clientWidth, el.clientHeight) : [];
    if (rows.length === shownPlaces.length && rows.every((p, i) => p === shownPlaces[i])) return;
    shownPlaces = rows;
    globe.htmlElementsData(rows);
  }
  const queueLabels = () => { labelFrame ||= requestAnimationFrame(drawLabels); };

  function stopSpin() {
    if (!globe) return;
    globe.controls().autoRotate = false;
    $("gl-spin").setAttribute("aria-pressed", "false");
  }

  function applyTheme() {
    if (!globe) return;
    const t = theme();
    globe.backgroundColor("rgba(0,0,0,0)").atmosphereColor(t.atmosphere).atmosphereAltitude(0.16)
      .polygonCapColor(() => t.land).polygonSideColor(() => "rgba(0,0,0,0)").polygonStrokeColor(() => t.border)
      .pathColor(d => d.kind === "sido" ? t.border : t.adminFine);
    globe.globeMaterial().color.set(t.ocean);
    drawPoints();
  }

  function renderLocal() {
    const box = $("gl-local");
    if (!localRows.length) { box.innerHTML = `<p class="gl-note">아직 없음. 지구본 오른쪽 위 ‘＋ 사이트 추가’로 등록한다.</p>`; return; }
    const json = JSON.stringify(localRows.map(({id, name, company, category, lat, lon, note}) =>
      Object.fromEntries(Object.entries({id, name, company, category, lat, lon, accuracy: "facility", status: "operating", note}).filter(([, v]) => v != null && v !== ""))), null, 1);
    box.innerHTML = `<ul class="gl-local-list">${localRows.map(r => `<li>${esc(r.name)} <small>${r.lat.toFixed(3)}, ${r.lon.toFixed(3)}</small></li>`).join("")}</ul>
      <textarea class="gl-json" readonly rows="6" aria-label="manual/sites.json에 붙여 넣을 JSON">${esc(json.slice(1, -1).trim())}</textarea>
      <button type="button" id="gl-copy">JSON 복사</button> <span id="gl-copied" class="gl-note" aria-live="polite"></span>`;
    $("gl-copy").addEventListener("click", async () => {
      const ta = box.querySelector("textarea");
      try { await navigator.clipboard.writeText(ta.value); $("gl-copied").textContent = "복사함"; }
      catch { ta.select(); $("gl-copied").textContent = "선택됨 — Ctrl+C로 복사"; }
    });
  }

  function pickLocation(coords) {
    if (!addMode || !coords) return;
    const f = $("gl-form").elements;
    f.lat.value = coords.lat.toFixed(4); f.lon.value = coords.lng.toFixed(4);
    pending = {lat: coords.lat, lng: coords.lng}; globe.ringsData([pending]);
  }

  function setAddMode(on) {
    addMode = on;
    $("gl-add").setAttribute("aria-pressed", String(on));
    $("gl-form").hidden = !on;
    $("gl-globe").classList.toggle("gl-picking", on);
    if (on) { stopSpin(); $("gl-form").elements.name.focus(); }
    else { pending = null; globe?.ringsData([]); }
  }

  // ── 이벤트 ──
  $("gl-layers").addEventListener("change", e => { e.target.checked ? prefs.layers.add(e.target.value) : prefs.layers.delete(e.target.value); drawPoints(); });
  $("gl-statuses").addEventListener("change", e => { e.target.checked ? prefs.statuses.add(e.target.value) : prefs.statuses.delete(e.target.value); drawPoints(); });
  $("gl-query").addEventListener("input", e => { prefs.query = e.target.value; drawPoints(); });
  $("gl-spin").addEventListener("click", () => {
    if (!globe) return;
    const on = !globe.controls().autoRotate;
    globe.controls().autoRotate = on; $("gl-spin").setAttribute("aria-pressed", String(on));
  });
  const labelsBtn = $("gl-labels");
  labelsBtn.setAttribute("aria-pressed", String(labelsOn));
  labelsBtn.addEventListener("click", () => {
    labelsOn = !labelsOn; writeLabelsPref(labelsOn);
    labelsBtn.setAttribute("aria-pressed", String(labelsOn)); drawLabels();
  });
  // 좁은 화면은 지구가 폭을 넘지 않게 더 멀리서 본다.
  const homeView = () => ({lat: 25, lng: 125, altitude: $("gl-globe").clientWidth < 600 ? 3.4 : 2.4});
  $("gl-home").addEventListener("click", () => { select(null); globe?.pointOfView(homeView(), 900); });
  $("gl-add").addEventListener("click", () => setAddMode(!addMode));
  $("gl-cancel").addEventListener("click", () => setAddMode(false));
  $("gl-form").addEventListener("input", () => {
    const f = $("gl-form").elements, lat = +f.lat.value, lon = +f.lon.value;
    if (f.lat.value && f.lon.value && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) { pending = {lat, lng: lon}; globe?.ringsData([pending]); }
  });
  $("gl-form").addEventListener("submit", e => {
    e.preventDefault();
    const f = $("gl-form").elements;
    const base = f.name.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "site";
    const row = {id: `${base}_${Date.now().toString(36)}`, name: f.name.value.trim(), company: f.company.value.trim(),
      category: f.category.value, lat: +(+f.lat.value).toFixed(4), lon: +(+f.lon.value).toFixed(4), note: f.note.value.trim()};
    const saved = setLocal([...localRows, row]);
    $("gl-form").reset(); setAddMode(false);
    prefs.layers.add("user"); prefs.statuses.add("operating");
    chips(); renderLocal(); select(localSites.at(-1), true);
    if (!saved) $("gl-local").insertAdjacentHTML("afterbegin", `<p class="gl-note">이 브라우저가 저장을 막고 있어 새로고침하면 사라진다. JSON을 복사해 두자.</p>`);
  });

  const darkMq = window.matchMedia("(prefers-color-scheme: dark)");
  darkMq.addEventListener("change", applyTheme);
  cleanups.push(() => darkMq.removeEventListener("change", applyTheme));

  // ── 데이터 + 지구본 ──
  // 지명은 없어도 지구본은 뜨게, 실패하면 라벨만 빠진다.
  const placesReq = fetch(PLACES).then(r => r.ok ? r.json() : null).catch(() => null);
  const sidoReq = fetch(KOREA_SIDO).then(r => r.ok ? r.json() : null).catch(() => null);
  Promise.all([fetch(`data/sites/sites.json?v=${Date.now()}`).then(r => { if (!r.ok) throw new Error("sites " + r.status); return r.json(); }), loadLibs(), placesReq, sidoReq])
    .then(([sites, countries, placeDoc, sidoDoc]) => {
      if (disposed) return;
      doc = sites;
      if (placeDoc) {
        places = {countries: placeDoc.countries.map(p => ({...p, kind: "country"})),
          cities: placeDoc.cities.map(p => ({...p, kind: "city"})), seas: placeDoc.seas.map(p => ({...p, kind: "sea"})),
          adm2: []};
        // 광역시는 도시 지명이 이미 있다. 같은 이름을 두 번 쓰지 않는다.
        const cityNames = new Set(places.cities.map(p => p.n));
        places.adm1 = (sidoDoc?.labels || []).filter(p => !cityNames.has(p.n)).map(p => ({...p, kind: "adm1"}));
      } else {
        labelsBtn.hidden = true;
      }
      $("gl-form").elements.category.innerHTML = Object.entries(doc.user_categories || {}).map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("");
      $("gl-sources").innerHTML = "출처: " + doc.layers.map(l => l.source_url ? `<a href="${esc(l.source_url)}" target="_blank" rel="noopener">${esc(l.source)}</a>` : esc(l.source))
        .filter((v, i, a) => a.indexOf(v) === i).join(" · ") + ` · 국경·지명 Natural Earth${sidoDoc ? ` · 한국 행정구역 <a href="${esc(sidoDoc.source_url)}" target="_blank" rel="noopener">${esc(sidoDoc.source)}</a>(이후 개편은 경계에 미반영)` : ""} · 집계 ${esc(doc.updated)}. ${esc(doc.note)}`
        + (doc.missing_coords?.length ? ` 좌표가 없어 지도에서 빠진 원장 행 ${doc.missing_coords.length}곳: ${esc(doc.missing_coords.map(m => m.id).join(", "))} — manual/site_coords.json 또는 data/sites/dc_coords.json에 추가하면 표시된다.` : "");
      document.getElementById("last-updated").textContent = `사이트 목록 집계 ${doc.updated}`;
      chips(); renderLocal();

      // 대한민국만 통계청 경계로 바꿔 그려 확대해도 해안선이 거칠지 않게 한다.
      const korea = sidoDoc && {type: "Feature", id: KOREA_ID, properties: {name: "South Korea"},
        geometry: topojson.merge(sidoDoc.topology, Object.values(sidoDoc.topology.objects)[0].geometries)};
      if (sidoDoc) sidoLines = meshLines(sidoDoc.topology, "sido");
      const el = $("gl-globe");
      globe = Globe({animateIn: true})(el)
        .showGraticules(true)
        .polygonsData(korea ? [...countries.filter(c => String(c.id) !== KOREA_ID), korea] : countries).polygonAltitude(0.004)
        .pathPoints("pts").pathPointLat(p => p[1]).pathPointLng(p => p[0]).pathPointAlt(0.0048)
        .pathStroke(null).pathTransitionDuration(0)
        .pointLat("lat").pointLng("lon").pointColor(siteColor).pointAltitude(siteHeight)
        .pointRadius(pointRadius)
        .pointResolution(8).pointsTransitionDuration(300)
        .pointLabel(tooltip)
        .onPointClick(s => { if (addMode) { pending = null; } select(s, false); stopSpin(); })
        // 육지를 누르면 국가 면(polygon)이 클릭을 받으므로 두 곳 모두에서 좌표를 받는다.
        .onGlobeClick(pickLocation)
        .onPolygonClick((country, event, coords) => pickLocation(coords))
        .ringColor(() => t => `rgba(227,73,72,${1 - t})`).ringMaxRadius(3).ringPropagationSpeed(2).ringRepeatPeriod(900)
        .htmlLat("lat").htmlLng("lon").htmlAltitude(0.008).htmlElement(placeElement).htmlTransitionDuration(0)
        .onZoom(queueLabels);
      const controls = globe.controls();
      controls.autoRotate = true; controls.autoRotateSpeed = 0.35;
      el.addEventListener("pointerdown", stopSpin, {once: true});
      globe.pointOfView(homeView());
      applyTheme();
      drawLabels();

      const fit = () => { if (globe) { globe.width(el.clientWidth).height(el.clientHeight); queueLabels(); } };
      const ro = new ResizeObserver(fit); ro.observe(el); fit();
      cleanups.push(() => ro.disconnect());
      $("gl-status").remove();
    })
    .catch(err => {
      if (disposed) return;
      $("gl-status").classList.remove("page-loading");
      $("gl-status").textContent = `지구본을 불러오지 못했다 (${err.message}). 네트워크를 확인하고 새로고침해 주세요.`;
    });

  return () => {
    disposed = true;
    cancelAnimationFrame(labelFrame);
    cleanups.forEach(fn => fn());
    if (globe) { globe.pauseAnimation(); globe._destructor?.(); globe = null; }
  };
}

/* 산업 KPI 대시보드 */
"use strict";

// ── 팔레트 (dataviz reference palette, 슬롯 순서 고정) ─────────────
const SERIES_COLORS = {
  light: ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"],
  dark: ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9", "#e66767", "#d55181", "#d95926"],
};

const state = {
  catalog: null,
  industry: null,
  subtab: null,
  range: "1y",
  tableRange: {}, // 테이블(수주내역·오더북)별 독립 기간필터. indicator id → range. 전역 range와 분리
  charts: [], // 렌더된 Chart 인스턴스 (재렌더 시 destroy)
  docs: new Map(), // indicator id → data json 캐시
  docErrors: new Map(), // indicator id → 불러오기 실패 사유. 404(아직 수집 전)는 여기 안 담김
};

// ── 수집 상태(stale) 판정 ────────────────────────────────────────
// doc.fetched = 수집 스크립트가 실제로 돌아간 날(어느 스크립트든 항상 '오늘'로 기록).
// doc.updated는 스크립트에 따라 데이터 날짜(공시 접수일 등)를 담기도 해서 stale 판정에 쓰면 오탐이 난다.
// 워크플로는 매일 KST 07:30 1회 실행 — 실행 실패·주말 슬랙을 감안해 3일부터 지연으로 본다.
const STALE_DAYS = 3;

function daysSince(isoDate) {
  if (!isoDate) return null;
  const t = Date.parse(`${isoDate}T00:00:00`);
  if (Number.isNaN(t)) return null;
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((midnight - t) / 86400000);
}

// fetched가 없는 문서(다음 수집 전까지 남아있는 기존 파일)는 판정 보류 — 오탐보다 침묵이 낫다.
// doc.stale_days = 그 지표만의 기준(주간 PDF 추출물 등 매일 돌지 않는 소스). 수기입력은 판정 제외.
function staleDays(doc) {
  if (!doc || doc.manual) return null;
  const d = daysSince(doc.fetched);
  const limit = doc.stale_days || STALE_DAYS;
  return d != null && d >= limit ? d : null;
}

const darkMq = window.matchMedia("(prefers-color-scheme: dark)");
const isDark = () => darkMq.matches;
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// ── 부트스트랩 ──────────────────────────────────────────────────
async function boot() {
  try {
    const res = await fetch("data/catalog.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.catalog = await res.json();
  } catch (e) {
    // catalog을 못 읽으면 렌더할 게 아무것도 없다 — 백지 대신 사유를 남긴다
    showBootError(e);
    return;
  }
  renderNav();
  document.querySelectorAll("#range-picker button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.range = btn.dataset.range;
      document.querySelectorAll("#range-picker button").forEach((b) => b.classList.toggle("active", b === btn));
      renderIndustry();
    });
  });
  darkMq.addEventListener("change", renderIndustry);
  window.addEventListener("hashchange", route);
  route();
}

function showBootError(e) {
  document.getElementById("page-title").textContent = "오류";
  const box = document.createElement("div");
  box.className = "card-empty is-error";
  box.textContent = "대시보드를 불러오지 못했습니다.";
  const why = document.createElement("span");
  why.className = "err-detail";
  why.textContent = `data/catalog.json — ${(e && e.message) || e}`;
  const hint = document.createElement("span");
  hint.className = "err-detail";
  hint.textContent = "새로고침해도 같으면 수집 워크플로(update-data.yml)가 실패했을 수 있습니다.";
  box.append(why, hint);
  const content = document.getElementById("content");
  content.innerHTML = "";
  content.appendChild(box);
}

function route() {
  const [id, subtab] = location.hash.replace("#/", "").split("/");
  const prev = state.industry;
  state.industry = state.catalog.industries.find((i) => i.id === id) || state.catalog.industries[0];
  state.subtab = state.industry.tabs?.find((tab) => tab.id === subtab)?.id || state.industry.tabs?.[0]?.id || null;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.id === state.industry.id));
  // 산업마다 적정 기본 기간이 다르다(전력은 월간·연간 계열이라 1년으로는 점이 몇 개 안 남는다).
  // 탭을 바꿀 때만 적용 — 같은 탭에서 사용자가 고른 기간은 유지.
  if (state.industry !== prev && state.industry.default_range) setRange(state.industry.default_range);
  renderIndustry();
}

function setRange(range) {
  state.range = range;
  document.querySelectorAll("#range-picker button").forEach((b) => b.classList.toggle("active", b.dataset.range === range));
}

function renderNav() {
  const nav = document.getElementById("nav");
  nav.innerHTML = "";
  for (const ind of state.catalog.industries) {
    const a = document.createElement("a");
    a.href = `#/${ind.id}`;
    a.dataset.id = ind.id;
    a.innerHTML = `<span>${ind.icon}</span><span>${ind.name}</span>`;
    nav.appendChild(a);
  }
}

// ── 산업 페이지 렌더 ─────────────────────────────────────────────
// 렌더 세대: 무거운 탭 로딩(await) 중 다른 탭을 클릭하면, 이전 렌더의 await가
// 뒤늦게 끝나며 새 탭 화면에 옛 카드를 붙이는 경쟁이 있었다. mySeq로 stale 렌더를 중단.
let renderSeq = 0;
async function renderIndustry() {
  const ind = state.industry;
  if (!ind) return;
  const mySeq = ++renderSeq;
  const selectedTab = ind.tabs?.find((tab) => tab.id === state.subtab);
  document.getElementById("page-title").textContent = `${ind.icon} ${ind.name}${selectedTab ? " · " + selectedTab.name : ""}`;
  // 갱신 버튼: 조선(수주)·기관수급·증여 탭에 노출(같은 update-data.yml이 갱신, 라벨은 refresh.js).
  // 테이블 전용 탭(기관수급·증여)은 차트가 없어 전역 기간필터를 뺀다.
  const tableTab = ind.id === "institution" || ind.id === "gifts";
  document.querySelector(".refresh-wrap").style.display = (ind.id === "shipbuilding" || tableTab) ? "" : "none";
  document.getElementById("range-picker").style.display = tableTab || selectedTab?.id === "mineral_supply" ? "none" : "";
  if (window.setRefreshLabel) window.setRefreshLabel();
  state.charts.forEach((c) => c.destroy());
  state.charts = [];

  const content = document.getElementById("content");
  content.innerHTML = "";

  if (ind.tabs) {
    const tabs = document.createElement("nav");
    tabs.className = "commodity-tabs";
    tabs.setAttribute("aria-label", `${ind.name} 세부 분류`);
    for (const tab of ind.tabs) {
      const link = document.createElement("a");
      link.href = `#/${ind.id}/${tab.id}`;
      link.textContent = tab.name;
      if (tab.id === state.subtab) {
        link.className = "active";
        link.setAttribute("aria-current", "page");
      }
      tabs.appendChild(link);
    }
    content.appendChild(tabs);
  }

  if (selectedTab?.description) {
    const intro = document.createElement("p");
    intro.className = "tab-description";
    intro.textContent = selectedTab.description;
    content.appendChild(intro);
  }

  // 빈 대시보드와 '아직 불러오는 중'을 구분한다. 카드는 아래 루프에서 하나씩 채워지고,
  // 이 줄은 전부 끝난 뒤 제거된다.
  const loading = document.createElement("div");
  loading.className = "page-loading";
  loading.textContent = "데이터 불러오는 중…";
  content.appendChild(loading);

  let latestUpdate = "";
  const collected = []; // 수집 상태 판정용 { name, fetched }
  for (const section of ind.sections) {
    if (ind.tabs && section.tab !== state.subtab) continue;
    const h = document.createElement("div");
    h.className = "section-title";
    h.textContent = section.title;
    content.appendChild(h);

    if (section.type === "table") {
      const renderer = section.table_kind === "asiasis" ? renderAsiasisTable
        : section.table_kind === "major_holdings" ? renderMajorHoldings
        : section.table_kind === "stock_trajectory" ? renderStockTrajectory
        : section.table_kind === "inst_holdings" ? renderInstHoldings
        : section.table_kind === "power_pipeline" ? renderPowerPipeline
        : section.table_kind === "power_fleet" ? renderPowerFleet
        : section.table_kind === "ba_detail" ? renderBADetail
        : section.table_kind === "gifts" ? renderGifts
        : section.table_kind === "ir_disclosure" ? renderIRDisclosure
        : section.table_kind === "ti_fixtures" ? renderTIFixtures
        : section.table_kind === "mineral_supply" ? renderMineralSupply
        : renderOrderTable;
      for (const indicatorId of section.indicators) {
        const doc = await loadDoc(ind.id, indicatorId);
        if (mySeq !== renderSeq) return; // 새 탭 렌더가 시작됨 → stale 렌더 중단
        const err = state.docErrors.get(indicatorId);
        content.appendChild(err ? errorCard(ind.id, indicatorId, err) : renderer(doc));
        if (doc && doc.updated > latestUpdate) latestUpdate = doc.updated;
        if (doc) collected.push({ name: doc.name || indicatorId, fetched: doc.fetched, stale: staleDays(doc) });
      }
      continue;
    }

    const grid = document.createElement("div");
    grid.className = "grid";
    content.appendChild(grid);

    for (const indicatorId of section.indicators) {
      const doc = await loadDoc(ind.id, indicatorId);
      if (mySeq !== renderSeq) return; // 새 탭 렌더가 시작됨 → stale 렌더 중단
      const err = state.docErrors.get(indicatorId);
      grid.appendChild(err ? errorCard(ind.id, indicatorId, err) : renderCard(doc, indicatorId));
      if (doc && doc.updated > latestUpdate) latestUpdate = doc.updated;
      if (doc) collected.push({ name: doc.name || indicatorId, fetched: doc.fetched, stale: staleDays(doc) });
    }
  }
  loading.remove();
  renderFootStatus(latestUpdate, collected, ind);
}

// 불러오기 실패 카드 — '아직 데이터가 없습니다'(정상)와 반드시 구분되어야 한다.
// 이게 없으면 파이프라인이 깨진 건지 원래 없는 지표인지 화면상 알 수 없다.
function errorCard(industryId, indicatorId, msg) {
  const card = document.createElement("div");
  card.className = "card";
  const head = document.createElement("div");
  head.className = "card-head";
  const name = document.createElement("div");
  name.className = "card-name";
  name.textContent = indicatorId;
  head.appendChild(name);
  const box = document.createElement("div");
  box.className = "card-empty is-error";
  box.textContent = "불러오기 실패";
  const why = document.createElement("span");
  why.className = "err-detail";
  why.textContent = `data/${industryId}/${indicatorId}.json — ${msg}`;
  box.appendChild(why);
  card.append(head, box);
  return card;
}

// 사이드바 하단: 데이터 날짜 + 수집이 실제로 돌고 있는지 + 이 탭의 갱신 주기
function renderFootStatus(latestUpdate, collected, ind) {
  const foot = document.getElementById("last-updated");
  foot.textContent = "";

  const dataLine = document.createElement("div");
  dataLine.textContent = latestUpdate ? `데이터 갱신: ${latestUpdate}` : "";
  foot.appendChild(dataLine);

  const withFetch = collected.filter((c) => c.fetched);
  const fetchLine = document.createElement("div");
  if (!withFetch.length) {
    // 기존 데이터 파일에는 fetched가 없다 — 다음 수집부터 채워진다
    fetchLine.textContent = "수집 시각: 기록 없음";
  } else {
    const stale = withFetch
      .map((c) => ({ name: c.name, fetched: c.fetched, age: c.stale }))
      .filter((c) => c.age != null)
      .sort((a, b) => b.age - a.age);
    if (stale.length) {
      fetchLine.className = "foot-warn";
      fetchLine.textContent = `⚠ 수집 지연 ${stale.length}개 (최장 ${stale[0].age}일)`;
      fetchLine.title = stale.map((c) => `${c.name}: ${c.fetched} (${c.age}일 전)`).join("\n");
    } else {
      const newest = withFetch.map((c) => c.fetched).sort().pop();
      fetchLine.textContent = `수집 정상 · 최종 ${newest}`;
    }
  }
  foot.appendChild(fetchLine);

  // 갱신 주기 안내: 워크플로는 매일 돌지만 소스마다 '새 값이 생기는 주기'가 다르다.
  // (예: 관세청은 월 1회 확정) — 이걸 모르면 정상 동작을 수집 실패로 오해하게 된다.
  // 탭별 문구는 catalog.json의 industry.cadence에 둔다(데이터·설명을 한곳에서 관리).
  const cad = document.createElement("details");
  cad.className = "foot-cadence";
  const sum = document.createElement("summary");
  sum.textContent = "갱신 주기";
  cad.appendChild(sum);
  const body = document.createElement("div");
  body.innerHTML =
    `<div>자동 수집: <b>매일 07:30</b>(KST) · GitHub Actions</div>` +
    (ind && ind.cadence ? `<div class="cad-tab">${escapeHtml(ind.name)}: ${escapeHtml(ind.cadence)}</div>` : "");
  cad.appendChild(body);
  foot.appendChild(cad);
}

async function loadDoc(industryId, indicatorId) {
  if (state.docs.has(indicatorId)) return state.docs.get(indicatorId);
  let doc = null;
  state.docErrors.delete(indicatorId);
  try {
    const url = `data/${industryId}/${indicatorId}.json` + (state.bust ? `?t=${state.bust}` : "");
    const res = await fetch(url);
    if (res.ok) doc = await res.json();
    else if (res.status !== 404) state.docErrors.set(indicatorId, `HTTP ${res.status}`);
    // 404는 아직 수집 전인 지표 — 정상적인 빈 카드로 둔다
  } catch (e) {
    // 네트워크 오류 또는 JSON 파싱 실패(= 파일이 깨짐). 빈 카드로 삼키면 안 되는 경우다.
    state.docErrors.set(indicatorId, (e && e.message) || "네트워크 오류");
  }
  state.docs.set(indicatorId, doc);
  return doc;
}

// refresh.js가 갱신 완료 후 호출: 캐시 무효화 + 재렌더 (Pages CDN 우회용 캐시버스트)
async function reloadData() {
  state.bust = Date.now();
  state.docs.clear();
  state.docErrors.clear();
  try {
    state.catalog = await (await fetch(`data/catalog.json?t=${state.bust}`)).json();
  } catch (e) { /* 유지 */ }
  await renderIndustry();
}
window.dashboard = { reloadData, state, GH_REPO: "Loong-kid/industry-dashboard" };

// ── 기간 필터 ───────────────────────────────────────────────────
function cutoffFor(range) {
  if (range === "all") return "0000-00-00";
  const months = { "3m": 3, "1y": 12, "3y": 36 }[range];
  const d = new Date();
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
}
function rangeCutoff() { return cutoffFor(state.range); } // 전역(차트용)

// 정렬 헤더 클릭 3단계 순환: (미정렬) → 내림차순 → 오름차순 → 미정렬(원래 순서)
function cycleSortState(filt, key) {
  if (filt.sortKey !== key) { filt.sortKey = key; filt.sortDir = -1; }
  else if (filt.sortDir === -1) filt.sortDir = 1;
  else if (filt.sortDir === 1) { filt.sortKey = null; filt.sortDir = 0; }
  else filt.sortDir = -1;
}

// 테이블 우측 상단 미니 기간필터. 전역 range와 독립적으로 동작.
const TABLE_RANGE_DEFAULT = "all";
function buildTableRangePicker(current, onPick) {
  const wrap = document.createElement("div");
  wrap.className = "range-picker table-range";
  [["3m", "3개월"], ["1y", "1년"], ["3y", "3년"], ["all", "전체"]].forEach(([r, label]) => {
    const b = document.createElement("button");
    b.textContent = label;
    if (r === current) b.classList.add("active");
    b.addEventListener("click", () => {
      wrap.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      onPick(r);
    });
    wrap.appendChild(b);
  });
  return wrap;
}

// ── 지표 카드 ───────────────────────────────────────────────────
function renderCard(doc, indicatorId) {
  // Alternate views keep physical levels and growth rates on separate axes.
  if (doc?.series_views) {
    state.cardViews ??= {};
    const key = state.cardViews[indicatorId] || doc.default_view || Object.keys(doc.series_views)[0];
    const view = doc.series_views[key] || Object.values(doc.series_views)[0];
    const display = {...doc, ...view};
    delete display.series_views;
    const before = new Set(state.charts);
    const card = renderCard(display, indicatorId);
    const owned = state.charts.filter(chart => !before.has(chart));
    const controls = document.createElement("div");
    controls.className = "series-view-controls";
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", `${doc.name} 표시 기준`);
    for (const [value, option] of Object.entries(doc.series_views)) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = option.label;
      button.className = value === key ? "active" : "";
      button.setAttribute("aria-pressed", String(value === key));
      button.addEventListener("click", () => {
        if (value === key) return;
        state.cardViews[indicatorId] = value;
        owned.forEach(chart => chart.destroy());
        state.charts = state.charts.filter(chart => !owned.includes(chart));
        card.replaceWith(renderCard(doc, indicatorId));
      });
      controls.appendChild(button);
    }
    card.insertBefore(controls, card.children[1] || null);
    return card;
  }
  const card = document.createElement("div");
  card.className = "card" + (doc?.point_sources ? " ir-chart" : "");
  const dateLabel = date => (doc?.quarter_labels
    ? `${date.slice(0, 4)} Q${Math.ceil(Number(date.slice(5, 7)) / 3)}`
    : doc?.year_labels ? date.slice(0, 4) : date)
    + (doc?.forecast_from && date >= doc.forecast_from ? " · 전망" : "");

  if (!doc || !doc.series || Object.values(doc.series).every((s) => s.length === 0)) {
    const name = doc?.name || indicatorId;
    card.innerHTML = `
      <div class="card-head"><div class="card-name">${name}</div></div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      ${doc?.manual ? `<code>manual/</code> 폴더의 CSV에 값을 입력하면 표시됩니다.` : `페처 실행 후 표시됩니다.`}</div>`;
    return card;
  }

  // full_range: 전역 기간 버튼을 무시하고 전체를 그린다. 연 단위로 듬성듬성한 지표(LNG 프로젝트
  // 준공연도 등)는 '3년'을 걸면 과거 실적 시리즈가 통째로 비어 사라진다 — 그 카드의 요점이 긴 궤적인데.
  const cutoff = doc.full_range ? "0000-00-00" : rangeCutoff();
  const seriesNames = Object.keys(doc.series);
  let filtered = {};
  for (const s of seriesNames) {
    filtered[s] = doc.series[s].filter((p) => p[0] >= cutoff);
  }
  // 선택 기간에 데이터가 하나도 없으면(오래된 지표) 전체 기간으로 대체
  if (seriesNames.every((s) => filtered[s].length === 0)) {
    filtered = Object.fromEntries(seriesNames.map((s) => [s, doc.series[s]]));
  }

  // 대표 시리즈: default_series의 첫 항목 (칩 토글 시 체크된 첫 시리즈로 갱신됨)
  const mainName = (doc.default_series && doc.default_series[0]) || seriesNames[0];

  const head = document.createElement("div");
  head.className = "card-head";
  // 수집이 멈춘 지표를 카드 단위로 지목 — 사이드바 요약만으로는 어느 건지 알 수 없다
  const sd = staleDays(doc);
  head.innerHTML = `
    <div class="card-name">${doc.name}</div>
    <div class="card-freq">${{ daily: "일간", weekly: "주간", monthly: "월간", quarterly: "분기", semiannual: "반기", yearly: "연간" }[doc.frequency] || ""}${doc.manual ? " · 수기입력" : ""}${doc.full_range ? " · 전체기간" : ""}${
      sd ? `<span class="stale-badge" title="마지막 수집: ${doc.fetched}">수집 ${sd}일 전</span>` : ""
    }</div>`;
  card.appendChild(head);

  if (doc.data_stale_days && daysSince(doc.updated) >= doc.data_stale_days) {
    const warning = document.createElement("div");
    warning.className = "card-empty is-error";
    warning.textContent = `최신 자료 미확보 · 아래는 ${doc.updated} 기준 과거 자료입니다.`;
    card.appendChild(warning);
  }

  // 헤드라인: 다중 시리즈 카드는 체크된 첫 시리즈를 따라감 (칩 토글 시 갱신)
  if (doc.collection_status) {
    const status = document.createElement("p");
    status.className = "card-foot";
    status.textContent = `${doc.collection_status.checked} · ${doc.collection_status.message}`;
    if (!doc.collection_status.ok) status.style.color = "var(--warn)";
    card.appendChild(status);
  }
  const stat = document.createElement("div");
  stat.className = "card-stat";
  card.appendChild(stat);
  const setStat = (seriesName) => {
    const s = (seriesName && doc.series[seriesName]) || [];
    const last = s[s.length - 1];
    const prev = s[s.length - 2];
    if (!last) {
      stat.innerHTML = `<span class="stat-unit">표시할 시리즈를 선택하세요</span>`;
      return;
    }
    if (doc.quarterly_revenue_summary) {
      const values = new Map(s);
      const year = Number(last[0].slice(0, 4));
      const q = Math.ceil(Number(last[0].slice(5, 7)) / 3);
      const ends = ["03-31", "06-30", "09-30", "12-31"];
      const priorQuarter = `${q === 1 ? year - 1 : year}-${ends[(q + 2) % 4]}`;
      const priorYear = `${year - 1}${last[0].slice(4)}`;
      const change = date => {
        const base = values.get(date);
        return last[1] != null && base != null && base > 0
          ? `${last[1] >= base ? "+" : ""}${((last[1] / base - 1) * 100).toFixed(1)}%` : "자료 없음";
      };
      stat.innerHTML = `<span class="stat-value">${fmt(last[1])}</span>
        <span class="stat-unit">${escapeHtml(doc.unit || "")}</span>
        <span class="stat-date">${dateLabel(last[0])}</span>
        <span class="stat-unit">YoY ${change(priorYear)} · QoQ ${change(priorQuarter)}</span>`;
      return;
    }
    if (doc.monthly_trade_summary) {
      const values = new Map(s);
      const year = Number(last[0].slice(0, 4));
      const month = Number(last[0].slice(5, 7));
      const previousMonth = `${month === 1 ? year - 1 : year}-${String(month === 1 ? 12 : month - 1).padStart(2, "0")}-01`;
      const previousYear = `${year - 1}${last[0].slice(4)}`;
      const change = date => {
        const base = values.get(date);
        return last[1] != null && base != null && base > 0
          ? `${last[1] >= base ? "+" : ""}${((last[1] / base - 1) * 100).toFixed(1)}%` : "자료 없음";
      };
      stat.innerHTML = `
        ${seriesNames.length > 1 ? `<span class="stat-series">${escapeHtml(seriesName)}</span>` : ""}
        <span class="stat-value">${last[1] == null ? "—" : fmt(last[1])}</span>
        <span class="stat-unit">${doc.unit || ""}</span>
        <span class="stat-date">${last[0]}</span>
        <span class="stat-unit">YoY ${change(previousYear)} · MoM ${change(previousMonth)}</span>`;
      return;
    }
    const reportedChange = doc.inventory_summary || doc.stock_summary;
    const pointsChange = doc.change_mode === "percentage_points";
    const monthOffset = date => Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7));
    const delta = pointsChange && (!prev || monthOffset(last[0]) - monthOffset(prev[0]) !== 1) ? null : reportedChange
      ? (new Map(doc.inventory_summary ? doc.weekly_changes || [] : doc.daily_changes || []).get(last[0]) ?? null)
      : doc.change_mode === "none" ? null : prev ? last[1] - prev[1] : null;
    const previousValue = reportedChange && delta !== null ? last[1] - delta : prev?.[1];
    const pct = !pointsChange && previousValue ? (delta / previousValue) * 100 : null;
    const dir = delta > 0 ? "up" : delta < 0 ? "down" : "";
    const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "";
    stat.innerHTML = `
      ${seriesNames.length > 1 ? `<span class="stat-series">${seriesName}</span>` : ""}
      <span class="stat-value">${fmt(last[1])}</span>
      <span class="stat-unit">${doc.unit || ""}</span>
      ${delta !== null ? `<span class="stat-delta ${dir}">${arrow} ${fmt(Math.abs(delta))}${pointsChange ? "p · 전월 대비" : ""}${pct !== null ? ` (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)` : ""}</span>` : ""}
      <span class="stat-date">${doc.cumulative_since ? `${doc.cumulative_since}년부터 누적 · ${last[0].slice(0, 7)}` : doc.cumulative ? `${last[0].slice(0, 4)}년 1~${Number(last[0].slice(5, 7))}월 누적` : doc.month_labels ? periodLabel(doc, last[0]) : dateLabel(last[0])}${doc.point_annotations?.[last[0]] ? " · 추정" : ""}</span>
      ${doc.sample_counts ? `<span class="stat-unit">표본 ${new Map(doc.sample_counts[seriesName] || []).get(last[0]) ?? 0}건</span>` : ""}`;
  };
  setStat(mainName);

  if (doc.inventory_summary || doc.stock_summary) {
    const points = doc.series[mainName];
    const last = points[points.length - 1];
    const target = new Date(`${last[0]}T00:00:00Z`);
    target.setUTCDate(target.getUTCDate() - 28);
    const base = points.find(p => p[0] === target.toISOString().slice(0, 10));
    const reported = new Map(doc.inventory_summary ? doc.weekly_changes || [] : doc.daily_changes || []).get(last[0]);
    const describe = value => value == null ? "자료 없음" : `${value > 0 ? "+" : ""}${fmt(value)} 톤`;
    const summary = document.createElement("p");
    summary.className = "card-foot";
    summary.textContent = `${doc.inventory_summary ? "전주" : "전 거래일"} 대비 ${describe(reported)} · 4주 변화 ${describe(base ? last[1] - base[1] : null)}`;
    card.appendChild(summary);
  }

  if (doc.snapshot_history) {
    const historyNote = document.createElement("p");
    historyNote.className = "card-foot";
    const count = doc.series[mainName].length;
    historyNote.textContent = count === 1
      ? "현재는 최신값 1개입니다. 새 기준일의 자료가 쌓이면 추이 그래프가 이어집니다."
      : `수집된 기준일 ${count}개 · ${doc.history_note || "수집 시작 전 과거 이력은 포함하지 않습니다."}`;
    card.appendChild(historyNote);
    if (doc.history_source_url) {
      const historySource = document.createElement("p");
      historySource.className = "card-foot";
      historySource.innerHTML = `과거 자료: <a href="${doc.history_source_url}" target="_blank" rel="noopener">${doc.history_source}</a> · <a href="${doc.history_csv}" download>원단위 CSV</a>`;
      card.appendChild(historySource);
    }
  }

  if (doc.forecast_from) {
    const legend = document.createElement("div");
    legend.className = "forecast-legend";
    legend.innerHTML = `<span><i class="forecast-key" aria-hidden="true"></i>실적·추정</span>
      <span><i class="forecast-key is-forecast" aria-hidden="true"></i>${escapeHtml(doc.forecast_label || "전망")} · ${escapeHtml(doc.forecast_from.slice(0, 4))}년부터</span>`;
    card.appendChild(legend);
  }

  const wrap = document.createElement("div");
  wrap.className = "chart-wrap";
  const canvas = document.createElement("canvas");
  wrap.appendChild(canvas);
  card.appendChild(wrap);

  const chipsDiv = document.createElement("div");
  card.appendChild(chipsDiv);

  // 지표 설명(desc)과 주의사항(note). 지표 JSON에 있으면 카드에 그대로 노출한다.
  // 없으면 아무것도 안 그리므로 기존 카드에는 영향 없음.
  if (doc.description || doc.note) {
    const info = document.createElement("div");
    info.style.cssText = "font-size:12px;color:var(--muted);line-height:1.55;margin-top:8px";
    const parts = [];
    if (doc.description) parts.push(escapeHtml(doc.description));
    if (doc.note) parts.push(`<span style="opacity:.85">※ ${escapeHtml(doc.note)}</span>`);
    info.innerHTML = parts.join("<br>");
    card.appendChild(info);
  }

  const basisDetails = doc.basis_details || doc.price_details;
  if (basisDetails?.length) {
    const details = document.createElement("details");
    details.className = "price-details";
    details.innerHTML = `<summary>${doc.basis_details ? "집계 기준 자세히" : "가격 기준 자세히"}</summary><dl>${basisDetails.map(item =>
      `<dt>${escapeHtml(item.label)}</dt><dd>${escapeHtml(item.value)}</dd>`).join("")}</dl>${doc.methodology_url ?
      `<a href="${escapeHtml(doc.methodology_url)}" target="_blank" rel="noopener">기준 해설 원문 ↗</a>` : ""}`;
    card.appendChild(details);
  }

  const foot = document.createElement("div");
  foot.className = "card-foot";
  foot.innerHTML = `
    <span>출처: ${doc.source_url ? `<a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a>` : doc.source || ""}</span>
    <button class="table-btn">표 보기</button>`;
  card.appendChild(foot);

  if (doc.license_url) {
    const credit = document.createElement("div");
    credit.className = "card-foot";
    const licenseLink = document.createElement("a");
    licenseLink.href = doc.license_url;
    licenseLink.target = "_blank";
    licenseLink.rel = "noopener";
    licenseLink.textContent = `${doc.history_source ? "The Vault Report 수집분 이용" : "데이터 이용"}: ${doc.license}`;
    credit.appendChild(licenseLink);
    card.appendChild(credit);
  }

  const tableDiv = document.createElement("div");
  tableDiv.className = "data-table";
  tableDiv.style.display = "none";
  card.appendChild(tableDiv);
  foot.querySelector(".table-btn").addEventListener("click", () => {
    const open = tableDiv.style.display !== "none";
    tableDiv.style.display = open ? "none" : "block";
    foot.querySelector(".table-btn").textContent = open ? "표 보기" : "표 닫기";
    if (!open) tableDiv.innerHTML = buildTable(doc, filtered);
  });

  const chart = drawChart(canvas, doc, filtered);
  // 헤드라인은 방금 켠 시리즈를 따라가고, 헤드라인 시리즈를 끄면 남은 것 중 첫 번째로
  let headline = mainName;
  buildChips(chipsDiv, chart, (label, checked) => {
    if (checked) {
      headline = label;
    } else if (label === headline) {
      const first = chart.data.datasets.find((d, i) => chart.isDatasetVisible(i));
      headline = first ? first.label : null;
    } else {
      return; // 헤드라인과 무관한 시리즈 해제는 그대로 둠
    }
    setStat(headline);
  });
  return card;
}

// 시리즈 토글 체크박스 칩 (Chart.js 기본 범례의 취소선 표기 대체)
function buildChips(container, chart, onToggle) {
  const datasets = chart.data.datasets;
  if (datasets.length < 2) return;
  container.className = "chips";
  datasets.forEach((ds, i) => {
    if (ds.isReference) return;
    const label = document.createElement("label");
    label.className = "chip" + (ds.hidden ? " off" : "");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !ds.hidden;
    const dot = document.createElement("span");
    dot.className = "chip-dot";
    dot.style.background = ds.borderColor;
    label.append(cb, dot, document.createTextNode(ds.label));
    cb.addEventListener("change", () => {
      chart.setDatasetVisibility(i, cb.checked);
      label.classList.toggle("off", !cb.checked);
      chart.update();
      if (onToggle) onToggle(ds.label, cb.checked);
    });
    container.appendChild(label);
  });
}

function escapeHtml(t) {
  return String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function fmt(v) {
  if (v == null) return "-";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: Math.abs(v) < 1000 ? 2 : 0 });
}

function periodLabel(doc, date) {
  if (doc.year_labels) return date.slice(0, 4);
  if (doc.month_labels) return date.slice(0, 7);
  return doc.quarter_labels ? `${date.slice(0, 4)} Q${Math.ceil(Number(date.slice(5, 7)) / 3)}` : date;
}

function mineralSupplyChart(doc, mineral, field) {
  const available = Object.values(mineral.countries).filter(country => country[field].length);
  const latest = available.length ? available.flatMap(country => country[field].map(point => point[0])).sort().at(-1) : null;
  const atLatest = country => country[field].find(point => point[0] === latest)?.[1] ?? -1;
  available.sort((a, b) => atLatest(b) - atLatest(a) || a.name.localeCompare(b.name, "ko"));
  const title = field === "production" ? "국가별 생산량" : "국가별 매장량";
  return {
    id: `${mineral.id}_${field}`, name: `${mineral.label} · ${title}`, unit: "톤",
    frequency: "yearly", year_labels: true, annual_axis: true, full_range: true,
    span_gaps: false, table_limit: 100, updated: latest, fetched: doc.fetched,
    source: doc.source, source_url: doc.source_url, methodology_url: mineral.reference_page
      ? `${doc.methodology_url}#page=${mineral.reference_page}` : doc.methodology_url,
    default_series: available.filter(country => atLatest(country) >= 0).slice(0, 3).map(country => country.name),
    series: Object.fromEntries(available.map(country => [country.name, country[field]])),
    description: field === "production" ? mineral.production_basis : mineral.reserve_basis,
    note: field === "production" ? "연간 생산량에는 추정치가 포함됩니다. 국가 칩으로 비교 대상을 선택하세요."
      : "경제적으로 채굴 가능한 공표 매장량 추정입니다. 자원량(Resources)·창고 재고와 다르며, 탐사·가격·평가 기준에 따라 바뀝니다.",
    basis_details: [
      {label: "원문 광종", value: mineral.komis_name},
      {label: "생산품 기준", value: field === "production" ? mineral.production_basis : mineral.reserve_basis},
      {label: "자료연도", value: "KOMIS 기준연도입니다. 생산은 해당 연도 물량, 매장량은 해당 연도에 연결된 공표시점 추정치이며 생산일·공표일과 같지 않습니다."},
      {label: "단위", value: "KOMIS 지도 수량은 미터톤으로 제공됩니다. 원문 단위 코드(kg·ton·k ton)를 수량에 다시 곱하거나 나누지 않았습니다."},
      {label: "자료 범위", value: "공개된 국가만 표시합니다. 미공개·0 값의 의미를 구분할 수 없어 관측치에서 제외하며, 기타 국가 물량을 추정하지 않습니다."},
      {label: "원자료 한계", value: "USGS의 추정·비공개·하한 표시 등 각주가 KOMIS 숫자 응답에 모두 보존되지는 않습니다. 게시 숫자를 원문과 임의로 이어 붙이지 않습니다."},
    ],
  };
}

function renderMineralSupply(doc) {
  const panel = document.createElement("div");
  panel.className = "mineral-supply";
  if (!doc?.minerals?.length) {
    panel.textContent = "광물 생산량·매장량 자료를 불러오지 못했습니다.";
    return panel;
  }
  state.mineralSupply ??= {mineral: doc.default_mineral, year: null, sort: "production", query: ""};
  const view = state.mineralSupply;
  if (!doc.minerals.some(mineral => mineral.id === view.mineral)) view.mineral = doc.default_mineral;
  const controls = document.createElement("div");
  controls.className = "mineral-supply-controls";
  const searchLabel = document.createElement("label");
  searchLabel.textContent = "광종 검색";
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "구리, 리튬, 흑연…";
  search.value = view.query;
  searchLabel.appendChild(search);
  const mineralLabel = document.createElement("label");
  mineralLabel.textContent = "광종 / 생산품";
  const select = document.createElement("select");
  mineralLabel.appendChild(select);
  controls.append(searchLabel, mineralLabel);
  panel.appendChild(controls);
  const coverage = document.createElement("p");
  coverage.className = "ir-scope-note";
  coverage.textContent = `자료 제공 ${doc.available_count}개 광종 / 생산품 · ${doc.years[0]}–${doc.years.at(-1)}년 · 매일 새 공표·정정 확인 · 수집 ${doc.fetched}`;
  panel.appendChild(coverage);
  const detail = document.createElement("div");
  panel.appendChild(detail);
  let owned = [];
  function options() {
    select.innerHTML = "";
    const query = view.query.trim().toLocaleLowerCase();
    const choices = doc.minerals.filter(mineral => !query || `${mineral.label} ${mineral.komis_name}`.toLocaleLowerCase().includes(query) || mineral.id === view.mineral);
    for (const mineral of choices) {
      const option = document.createElement("option");
      option.value = mineral.id;
      option.textContent = mineral.label + (!mineral.available ? " · 자료 미공개" : mineral.updated.slice(0, 4) < String(doc.years.at(-1)) ? ` · 최신 ${mineral.updated.slice(0, 4)}년` : "");
      select.appendChild(option);
    }
    select.value = view.mineral;
  }
  function draw() {
    owned.forEach(chart => chart.destroy());
    state.charts = state.charts.filter(chart => !owned.includes(chart));
    owned = [];
    detail.innerHTML = "";
    const mineral = doc.minerals.find(item => item.id === view.mineral);
    const heading = document.createElement("h3");
    heading.textContent = mineral.label;
    detail.appendChild(heading);
    if (!mineral.available) {
      const empty = document.createElement("p");
      empty.className = "card-empty";
      empty.textContent = "KOMIS 광종 목록에는 있으나 국가별 생산량·매장량 수치가 공개되지 않았습니다.";
      detail.appendChild(empty);
      return;
    }
    if (mineral.updated.slice(0, 4) < String(doc.years.at(-1)) || mineral.source_warning) {
      const warning = document.createElement("p");
      warning.className = "mineral-source-warning";
      warning.textContent = mineral.source_warning || `최신 자료는 ${mineral.updated.slice(0, 4)}년입니다. 이후 미공개 연도를 추정하지 않습니다.`;
      detail.appendChild(warning);
    }
    const grid = document.createElement("div");
    grid.className = "grid";
    detail.appendChild(grid);
    const before = new Set(state.charts);
    for (const field of ["production", "reserves"]) {
      const chartDoc = mineralSupplyChart(doc, mineral, field);
      if (Object.keys(chartDoc.series).length) grid.appendChild(renderCard(chartDoc, chartDoc.id));
      else {
        const empty = document.createElement("div");
        empty.className = "card";
        const title = document.createElement("div");
        title.className = "card-name";
        title.textContent = chartDoc.name;
        const note = document.createElement("p");
        note.className = "card-empty";
        note.textContent = "국가별 수치 미공개 · 0으로 표시하지 않습니다.";
        empty.append(title, note);
        grid.appendChild(empty);
      }
    }
    owned = state.charts.filter(chart => !before.has(chart));
    const table = document.createElement("div");
    table.className = "card mineral-country-table";
    const title = document.createElement("div");
    title.className = "card-name";
    title.textContent = "국가별 비교 · 공개 국가 합계 기준";
    table.appendChild(title);
    const yearLabel = document.createElement("label");
    yearLabel.className = "mineral-year-control";
    yearLabel.textContent = "비교 연도 ";
    const yearSelect = document.createElement("select");
    const years = [...new Set(Object.values(mineral.countries).flatMap(country => ["production", "reserves"].flatMap(field => country[field].map(point => point[0].slice(0, 4)))))].sort().reverse();
    if (!years.includes(view.year)) view.year = years[0];
    for (const year of years) {
      const option = document.createElement("option");
      option.value = year;
      option.textContent = `${year}년`;
      yearSelect.appendChild(option);
    }
    yearSelect.value = view.year;
    yearLabel.appendChild(yearSelect);
    table.appendChild(yearLabel);
    const sort = document.createElement("div");
    sort.className = "series-view-controls";
    for (const [key, name] of [["production", "생산량 순"], ["reserves", "매장량 순"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = name;
      button.className = view.sort === key ? "active" : "";
      button.setAttribute("aria-pressed", String(view.sort === key));
      button.addEventListener("click", () => {
        view.sort = key;
        for (const child of sort.children) {
          child.classList.toggle("active", child === button);
          child.setAttribute("aria-pressed", String(child === button));
        }
        rows();
      });
      sort.appendChild(button);
    }
    table.appendChild(sort);
    const summary = document.createElement("p");
    summary.className = "ir-scope-note";
    table.appendChild(summary);
    const wrap = document.createElement("div");
    wrap.className = "order-table-wrap";
    table.appendChild(wrap);
    const note = document.createElement("p");
    note.className = "ir-scope-note";
    note.textContent = doc.note + " 비중은 선택 연도에 수치가 공개된 국가들만을 분모로 계산합니다. 표의 —는 미공개 또는 구분 불가 값입니다.";
    table.appendChild(note);
    detail.appendChild(table);
    function rows() {
      const date = `${view.year}-12-31`;
      const values = Object.values(mineral.countries).map(country => ({name: country.name,
        production: country.production.find(point => point[0] === date)?.[1],
        reserves: country.reserves.find(point => point[0] === date)?.[1],
      })).filter(country => country.production != null || country.reserves != null);
      values.sort((a, b) => (b[view.sort] ?? -1) - (a[view.sort] ?? -1) || a.name.localeCompare(b.name, "ko"));
      const total = field => values.reduce((sum, country) => sum + (country[field] || 0), 0);
      const production = total("production"), reserves = total("reserves");
      summary.textContent = `${view.year}년 공개 국가 합계 · 생산량 ${production ? fmt(production) + "톤" : "미공개"} · 매장량 ${reserves ? fmt(reserves) + "톤" : "미공개"}`;
      const share = (value, sum) => value != null && sum > 0 ? `${(value / sum * 100).toFixed(1)}%` : "—";
      wrap.innerHTML = `<table><caption class="blind">${escapeHtml(mineral.label)} ${view.year}년 국가별 생산량·매장량</caption><thead><tr><th>국가</th><th>생산량(톤)</th><th>공개국가 비중</th><th>매장량(톤)</th><th>공개국가 비중</th></tr></thead><tbody>${values.map(country => `<tr><td>${escapeHtml(country.name)}</td><td>${country.production == null ? "—" : fmt(country.production)}</td><td>${share(country.production, production)}</td><td>${country.reserves == null ? "—" : fmt(country.reserves)}</td><td>${share(country.reserves, reserves)}</td></tr>`).join("")}</tbody></table>`;
    }
    yearSelect.addEventListener("change", () => {view.year = yearSelect.value; rows();});
    rows();
  }
  search.addEventListener("input", () => {view.query = search.value; options();});
  select.addEventListener("change", () => {view.mineral = select.value; view.year = null; draw();});
  options();
  draw();
  return panel;
}

function renderIRDisclosure(doc) {
  const card = document.createElement("div");
  card.className = "card ir-disclosure";
  if (!doc) return card;
  const esc = escapeHtml;
  card.innerHTML = `<div class="card-name">${esc(doc.name)}</div>
    <p class="ir-scope-note">${esc(doc.description)}</p>
    <div class="order-table-wrap"><table><thead><tr>
      <th>회사</th><th>블랭크마스크 분기 매출액</th><th>직접 공개된 지표</th><th>별도 참고 그래프</th>
    </tr></thead><tbody>${doc.rows.map(r => `<tr>
      <td><a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.company)} ↗</a></td>
      <td>${esc(r.quarterly)}</td><td>${esc(r.direct)}</td><td>${esc(r.reference)}</td>
    </tr>`).join("")}</tbody></table></div>
    <p class="ir-scope-note">${esc(doc.note)}</p>`;
  return card;
}

function buildTable(doc, filtered) {
  const names = Object.keys(filtered);
  const dates = [...new Set(names.flatMap((n) => filtered[n].map((p) => p[0])))].sort().reverse().slice(0, doc.table_limit || (doc.point_sources ? 100 : 15));
  const map = {};
  for (const n of names) map[n] = Object.fromEntries(filtered[n]);
  const hasSources = doc.point_sources || doc.period_sources;
  let html = `<table><thead><tr><th>${doc.quarter_labels ? "달력 분기" : doc.year_labels ? "연도" : doc.month_labels ? "관측월" : "날짜"}</th>${names.map((n) => `<th>${escapeHtml(n)}</th>`).join("")}${hasSources ? "<th>공식 원문</th>" : ""}</tr></thead><tbody>`;
  for (const d of dates) {
    const ref = doc.point_sources?.[d] || doc.period_sources?.[d];
    const sourceCell = hasSources ? `<td>${ref ? `<a href="${escapeHtml(ref.url)}${ref.pdf_page ? `#page=${ref.pdf_page}` : ""}" target="_blank" rel="noopener">${ref.pdf_page ? `PDF p.${ref.pdf_page}` : ref.label ? escapeHtml(ref.label) : `${escapeHtml(ref.issue)} 월보`} ↗</a>` : "미확인"}</td>` : "";
    const forecastTag = doc.forecast_from && d >= doc.forecast_from ? ` <span class="forecast-tag">전망</span>` : "";
    const estimateTag = doc.point_annotations?.[d] ? ` <span title="${escapeHtml(doc.point_annotations[d])}">· 추정</span>` : "";
    html += `<tr><td>${periodLabel(doc, d)}${forecastTag}${estimateTag}</td>${names.map((n) => `<td>${map[n][d] != null ? fmt(map[n][d]) : ""}</td>`).join("")}${sourceCell}</tr>`;
  }
  return html + "</tbody></table>";
}

// ── 차트 (Chart.js) ─────────────────────────────────────────────
// 크로스헤어: 호버 지점에 세로 안내선
const crosshair = {
  id: "crosshair",
  afterDraw(chart) {
    const active = chart.tooltip?.getActiveElements();
    if (!active || !active.length) return;
    const x = active[0].element.x;
    const { top, bottom } = chart.chartArea;
    const ctx = chart.ctx;
    ctx.save();
    ctx.strokeStyle = css("--baseline");
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    ctx.restore();
  },
};

function drawChart(canvas, doc, filtered) {
  const palette = SERIES_COLORS[isDark() ? "dark" : "light"];
  const names = Object.keys(filtered);
  const visible = new Set(doc.default_series || names.slice(0, 1));

  // 모든 시리즈의 날짜 합집합을 라벨로
  let labels = [...new Set(names.flatMap((n) => filtered[n].map((p) => p[0])))].sort();
  // 연간 시장규모: 미공표 연도도 축에 남겨 실제 공백을 표시한다.
  if (doc.annual_axis && labels.length) {
    const firstYear = Number(labels[0].slice(0, 4));
    const lastYear = Number(labels.at(-1).slice(0, 4));
    labels = Array.from({length: lastYear - firstYear + 1}, (_, i) => `${firstYear + i}-12-31`);
  }
  if (doc.monthly_axis && labels.length) {
    const offset = date => Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7)) - 1;
    const first = offset(labels[0]), last = offset(labels.at(-1));
    labels = Array.from({length: last - first + 1}, (_, i) => {
      const month = first + i;
      return new Date(Date.UTC(Math.floor(month / 12), month % 12 + 1, 0)).toISOString().slice(0, 10);
    });
  }
  const idx = Object.fromEntries(labels.map((d, i) => [d, i]));

  const datasets = names.map((n, i) => {
    const data = new Array(labels.length).fill(null);
    for (const [d, v] of filtered[n]) data[idx[d]] = v;
    // Chart.js style callbacks also visit skipped points. Resolve both ends to
    // the surrounding observed values so the whole missing interval is styled.
    const gapBounds = ctx => {
      let start = ctx.p0DataIndex, end = ctx.p1DataIndex;
      while (start > 0 && data[start] == null) start--;
      while (end < data.length - 1 && data[end] == null) end++;
      return [labels[start], labels[end]];
    };
    const gapMonths = ctx => {
      const offset = date => Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7));
      const [start, end] = gapBounds(ctx);
      return offset(end) - offset(start);
    };
    const januaryBridge = ctx => {
      const [start, end] = gapBounds(ctx);
      return gapMonths(ctx) === 2 && start.slice(5, 7) === "12" && end.slice(5, 7) === "02";
    };
    const color = palette[i % palette.length];
    const count = data.filter((v) => v != null).length;
    return {
      label: n,
      data,
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      pointRadius: count < 8 ? 3 : 0, // 점이 적을 땐(수집 초기) 마커로 표시

      pointHoverRadius: 5,
      pointHoverBorderColor: css("--surface"),
      pointHoverBorderWidth: 2,
      spanGaps: doc.bridge_missing_january ? true : doc.span_gaps ?? true,
      segment: doc.forecast_from || doc.highlight_gaps || doc.bridge_missing_january ? {
        borderColor: ctx => doc.bridge_missing_january && gapMonths(ctx) > 1 && !januaryBridge(ctx)
          ? "transparent" : undefined,
        borderDash: (ctx) => {
          if (doc.bridge_missing_january && januaryBridge(ctx)) return [5, 4];
          // The connector into the first projected value is forecast too.
          if (doc.forecast_from && labels[ctx.p1DataIndex] >= doc.forecast_from) return [6, 4];
          if (!doc.highlight_gaps) return undefined;
          const start = Date.parse(labels[ctx.p0DataIndex]);
          const end = Date.parse(labels[ctx.p1DataIndex]);
          return end - start > 7 * 86400000 ? [5, 5] : undefined;
        },
      } : undefined,
      hidden: !visible.has(n),
    };
  });

  if (Number.isFinite(doc.reference_value)) {
    datasets.push({label: doc.reference_label || `기준 ${doc.reference_value}`,
      data: labels.map(() => doc.reference_value), borderColor: css("--muted"),
      borderWidth: 1, borderDash: [5, 5], pointRadius: 0, pointHoverRadius: 0,
      hidden: false, isReference: true});
  }

  const chart = new Chart(canvas, {
    type: doc.chart_type || "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false }, // 범례는 체크박스 칩(buildChips)으로 대체

        tooltip: {
          backgroundColor: isDark() ? "#2c2c2a" : "#ffffff",
          titleColor: css("--ink"),
          bodyColor: css("--ink-2"),
          borderColor: css("--grid"),
          borderWidth: 1,
          padding: 10,
          usePointStyle: true,
          boxWidth: 8, boxHeight: 8,
          callbacks: {
            title: (items) => items.length ? periodLabel(doc, items[0].label)
              + (doc.forecast_from && items[0].label >= doc.forecast_from ? ` · ${doc.forecast_label || "전망"}` : "") : "",
            label: (c) => ` ${c.dataset.label}: ${fmt(c.parsed.y)}${doc.unit ? " " + doc.unit : ""}${doc.point_annotations?.[c.label] ? " · 추정" : ""}`,
            afterBody: (items) => {
              const dates = doc.source_dates?.[items[0]?.label];
              const report = doc.series_sources?.[items[0]?.dataset?.label]?.[items[0]?.label] || doc.period_sources?.[items[0]?.label];
              const samples = items.filter(item => doc.sample_counts?.[item.dataset?.label]).map(item =>
                `${item.dataset.label}: 표본 ${new Map(doc.sample_counts[item.dataset.label]).get(item.label) ?? 0}건`);
              return [...(doc.point_annotations?.[items[0]?.label] ? [doc.point_annotations[items[0].label]] : []), ...(dates ? ["구성 자료 기준일", ...Object.entries(dates).map(([name, date]) => `${name}: ${date}`)] : []), ...samples,
                ...(report ? [report.label ? `${report.label}${report.published ? ` · 공표 ${report.published}` : ""}` : `WFE 원문: ${report.issue} 월보 (발행월)`] : [])];
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: css("--muted"),
            maxTicksLimit: doc.komis_info || doc.month_labels || doc.compact_ticks ? ctx => ctx.chart.width < 420 ? 3 : 6 : 6,
            maxRotation: 0, autoSkip: true,
            font: { size: 11 },
            callback: function(value) { return periodLabel(doc, this.getLabelForValue(value)); },
          },
          grid: { display: false },
          border: { color: css("--baseline") },
        },
        y: {
          beginAtZero: doc.zero_baseline || false,
          ticks: {
            color: css("--muted"),
            maxTicksLimit: 5,
            font: { size: 11 },
            callback: (v) => fmt(v),
          },
          grid: { color: css("--grid") },
          border: { display: false },
        },
      },
    },
    plugins: [crosshair],
  });
  state.charts.push(chart);
  return chart;
}

// ── 수주 테이블 (DART 공시 기반, 시계열이 아니라 건별 표) ───────────────
function renderOrderTable(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";

  if (!doc || !doc.orders || doc.orders.length === 0) {
    card.innerHTML = `<div class="card-name">${doc?.name || "국내 조선 수주"}</div>
      <div class="card-empty">아직 데이터가 없습니다.</div>`;
    return card;
  }

  // 칩 목록은 전체 데이터 기준(기간필터와 무관하게 안정적으로 유지)
  const companies = doc.companies || [...new Set(doc.orders.map((o) => o.corp_name))];
  const catFreq = {};
  doc.orders.forEach((o) => { catFreq[o.vessel_category] = (catFreq[o.vessel_category] || 0) + 1; });
  const categories = Object.keys(catFreq).sort((a, b) => catFreq[b] - catFreq[a]); // 빈도순 → 대표=최다

  // 디폴트: 각 칩 그룹에서 대표(첫) 하나만 켜짐 (전부 켜고 끄는 방식이 불편하다는 피드백)
  const filt = {
    companies: new Set(companies.slice(0, 1)),
    categories: new Set(categories.slice(0, 1)),
    search: "",
    sortKey: "rcept_dt",
    sortDir: -1,
  };
  if (state.tableRange[doc.id] == null) state.tableRange[doc.id] = TABLE_RANGE_DEFAULT;

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">${doc.name}</span>
      <span class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></span>
    </div>`;
  head.appendChild(buildTableRangePicker(state.tableRange[doc.id], (r) => { state.tableRange[doc.id] = r; renderRows(); }));
  card.appendChild(head);

  const filterBar = document.createElement("div");
  filterBar.className = "order-filters";
  card.appendChild(filterBar);

  const companyChips = document.createElement("div");
  companyChips.className = "chips";
  filterBar.appendChild(companyChips);

  const categoryChips = document.createElement("div");
  categoryChips.className = "chips";
  filterBar.appendChild(categoryChips);

  const searchWrap = document.createElement("div");
  searchWrap.className = "order-search";
  searchWrap.innerHTML = `<input type="text" placeholder="선종·상대방·계약명 검색" />`;
  filterBar.appendChild(searchWrap);

  const countLine = document.createElement("div");
  countLine.className = "order-count";
  card.appendChild(countLine);

  const tableWrap = document.createElement("div");
  tableWrap.className = "order-table-wrap";
  card.appendChild(tableWrap);

  const COLS = [
    { key: "rcept_dt", label: "공시일" },
    { key: "corp_name", label: "회사" },
    { key: "vessel_type", label: "선종" },
    { key: "size", label: "사이즈", align: "right" },
    { key: "count", label: "척수", align: "right" },
    { key: "amount_krw", label: "계약금액(억원)", align: "right" },
    { key: "per_vessel_usd", label: "척당단가(M$)", align: "right" },
    { key: "counterparty", label: "상대방" },
    { key: "region", label: "지역" },
    { key: "contract_end", label: "인도(종료)일" },
    { key: "_link", label: "" },
  ];

  function buildChip(container, label, active, onToggle) {
    const chipLabel = document.createElement("label");
    chipLabel.className = "chip" + (active ? "" : " off");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = active;
    chipLabel.append(cb, document.createTextNode(label));
    cb.addEventListener("change", () => {
      chipLabel.classList.toggle("off", !cb.checked);
      onToggle(cb.checked);
      renderRows();
    });
    container.appendChild(chipLabel);
  }

  companies.forEach((c, i) => buildChip(companyChips, c, i === 0, (on) => (on ? filt.companies.add(c) : filt.companies.delete(c))));
  categories.forEach((c, i) => buildChip(categoryChips, c, i === 0, (on) => (on ? filt.categories.add(c) : filt.categories.delete(c))));

  searchWrap.querySelector("input").addEventListener("input", (e) => {
    filt.search = e.target.value.trim().toLowerCase();
    renderRows();
  });

  function krwEok(v) {
    return v == null ? "-" : Math.round(v / 1e8).toLocaleString("ko-KR");
  }
  function usdM(v) {
    return v == null ? "-" : (v / 1e6).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  }
  function cellValue(o, key) {
    switch (key) {
      case "count": return o.count ? `${o.count}${o.unit}` : "-";
      case "size":
        if (!o.size) return "-";
        // 추정값(선종 클래스 표준)은 muted, 공시 명시값은 일반 텍스트
        return o.size_inferred
          ? `<span class="size-inferred" title="선종 클래스 표준값(공시 미명시)">${o.size}</span>`
          : o.size;
      case "amount_krw": return krwEok(o.amount_krw);
      case "per_vessel_usd": return usdM(o.per_vessel_usd);
      case "_link": return `<a href="${o.viewer_url}" target="_blank" rel="noopener">원문</a>`;
      default: return o[key] || "-";
    }
  }

  function renderRows() {
    const cutoff = cutoffFor(state.tableRange[doc.id] || TABLE_RANGE_DEFAULT);
    const allOrders = doc.orders.filter((o) => o.rcept_dt >= cutoff);
    const rows = allOrders.filter((o) => {
      if (!filt.companies.has(o.corp_name)) return false;
      if (!filt.categories.has(o.vessel_category)) return false;
      if (filt.search) {
        const hay = `${o.vessel_type} ${o.counterparty} ${o.contract_name}`.toLowerCase();
        if (!hay.includes(filt.search)) return false;
      }
      return true;
    });
    if (filt.sortKey) {
      rows.sort((a, b) => {
        const av = a[filt.sortKey], bv = b[filt.sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
      });
    }

    countLine.textContent = `${rows.length.toLocaleString("ko-KR")}건 표시 중 (전체 ${allOrders.length.toLocaleString("ko-KR")}건)`;

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const htr = document.createElement("tr");
    COLS.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col.label;
      th.style.textAlign = col.align === "right" ? "right" : "left";
      if (col.key !== "_link") {
        th.classList.add("sortable");
        if (filt.sortKey === col.key && filt.sortDir !== 0) th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
        th.addEventListener("click", () => {
          cycleSortState(filt, col.key);
          renderRows();
        });
      }
      htr.appendChild(th);
    });
    thead.appendChild(htr);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const o of rows) {
      const tr = document.createElement("tr");
      if (o.is_correction) tr.classList.add("is-correction");
      COLS.forEach((col) => {
        const td = document.createElement("td");
        td.style.textAlign = col.align === "right" ? "right" : "left";
        td.innerHTML = cellValue(o, col.key);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);

    tableWrap.innerHTML = "";
    tableWrap.appendChild(table);
  }

  renderRows();
  return card;
}

// ── TI VLCC 성약: 상태·항로·선박 사양별 조회 ────────────────────
function renderTIFixtures(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card ti-fixtures";
  if (!doc?.fixtures?.length) {
    card.innerHTML = `<div class="card-name">${escapeHtml(doc?.name || "TI VLCC 성약 내역")}</div><div class="card-empty">아직 데이터가 없습니다.</div>`;
    return card;
  }
  const head = document.createElement("div");
  head.className = "card-head";
  const title = document.createElement("div");
  title.className = "card-name";
  title.textContent = doc.name;
  head.appendChild(title);
  state.tableRange[doc.id] ??= TABLE_RANGE_DEFAULT;
  head.appendChild(buildTableRangePicker(state.tableRange[doc.id], range => {
    state.tableRange[doc.id] = range;
    renderRows();
  }));
  card.appendChild(head);
  const note = document.createElement("p");
  note.className = "ir-scope-note";
  note.textContent = `${doc.description} 최신 공개: ${doc.updated} · 수집: ${doc.fetched}`;
  card.appendChild(note);
  const sd = staleDays(doc);
  if (sd != null) {
    const stale = document.createElement("p");
    stale.className = "card-empty is-error";
    stale.textContent = `수집 ${sd}일 전 · 마지막 수집: ${doc.fetched}`;
    card.appendChild(stale);
  }
  const filters = document.createElement("div");
  filters.className = "order-filters";
  card.appendChild(filters);
  const filt = {status: "Fixed", route: "", category: "", search: "", sortKey: "reported_time", sortDir: -1};
  const statusNames = {Fixed: "확정", "On Subs": "조건부", Failed: "실패", Unknown: "미확인"};
  function selectFilter(label, key, values, display = value => value) {
    const wrap = document.createElement("label");
    wrap.className = "ti-filter";
    wrap.appendChild(document.createTextNode(label));
    const select = document.createElement("select");
    select.setAttribute("aria-label", label);
    for (const value of ["", ...values]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value ? display(value) : "전체";
      option.selected = value === filt[key];
      select.appendChild(option);
    }
    select.addEventListener("change", () => { filt[key] = select.value; renderRows(); });
    wrap.appendChild(select);
    filters.appendChild(wrap);
  }
  selectFilter("상태", "status", [...new Set(doc.fixtures.map(row => row.status))].sort(), value => statusNames[value] || value);
  selectFilter("항로", "route", [...new Set(doc.fixtures.map(row => row.route))].sort());
  selectFilter("선령·연료", "category", [...new Set(doc.fixtures.map(row => row.category))].sort());
  const searchWrap = document.createElement("label");
  searchWrap.className = "order-search";
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "선박·운항사·용선사 검색";
  search.setAttribute("aria-label", search.placeholder);
  search.addEventListener("input", () => { filt.search = search.value.trim().toLowerCase(); renderRows(); });
  searchWrap.appendChild(search);
  filters.appendChild(searchWrap);
  const count = document.createElement("div");
  count.className = "order-count";
  card.appendChild(count);
  const wrap = document.createElement("div");
  wrap.className = "order-table-wrap";
  card.appendChild(wrap);
  const columns = [
    ["reported_time", "발표 시각"], ["vessel", "선박"], ["route", "항로"],
    ["category", "선령·연료"], ["tce", "TCE ($/day)"], ["cargo_tonnes", "화물 (톤)"],
    ["status", "상태"], ["operator", "운항사"], ["charterer", "용선사"], ["source_url", "원문"],
  ];
  function renderRows() {
    const cutoff = cutoffFor(state.tableRange[doc.id]);
    const rows = doc.fixtures.filter(row => row.reported_date >= cutoff
      && (!filt.status || row.status === filt.status) && (!filt.route || row.route === filt.route)
      && (!filt.category || row.category === filt.category)
      && (!filt.search || `${row.vessel} ${row.operator} ${row.charterer}`.toLowerCase().includes(filt.search)));
    if (filt.sortKey) rows.sort((a, b) => {
      const value = row => filt.sortKey === "reported_time"
        ? `${row.reported_date} ${row.reported_time.split(" ").at(-1) || ""}` : row[filt.sortKey];
      const av = value(a), bv = value(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
    });
    count.textContent = `${rows.length.toLocaleString("ko-KR")}건 표시 · TCE 공개 ${rows.filter(row => row.tce != null).length}건 · 전체 누적 ${doc.fixtures.length}건`;
    wrap.innerHTML = "";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const header = document.createElement("tr");
    for (const [key, label] of columns) {
      const th = document.createElement("th");
      th.textContent = label;
      if (key !== "source_url") {
        th.classList.add("sortable");
        if (key === filt.sortKey) th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
        th.addEventListener("click", () => { cycleSortState(filt, key); renderRows(); });
      }
      if (["tce", "cargo_tonnes"].includes(key)) th.style.textAlign = "right";
      header.appendChild(th);
    }
    thead.appendChild(header);
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const row of rows) {
      const tr = document.createElement("tr");
      for (const [key] of columns) {
        const td = document.createElement("td");
        if (key === "source_url") {
          const link = document.createElement("a");
          link.href = `https://app.tankersinternational.com/fixtures/${encodeURIComponent(row.fixture_id)}`;
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = "TI ↗";
          td.appendChild(link);
        } else if (["tce", "cargo_tonnes"].includes(key)) {
          td.style.textAlign = "right";
          td.textContent = row[key] == null ? "—" : fmt(row[key]);
        } else td.textContent = key === "status" ? statusNames[row.status] || row.status : row[key] || "—";
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    if (!rows.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = columns.length;
      td.textContent = "선택한 조건에 해당하는 성약이 없습니다.";
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    wrap.appendChild(table);
  }
  const foot = document.createElement("div");
  foot.className = "card-foot";
  foot.innerHTML = `출처: <a href="https://app.tankersinternational.com/" target="_blank" rel="noopener">Tankers International</a> · <a href="https://app.tankersinternational.com/terms" target="_blank" rel="noopener">이용 조건</a>`;
  card.appendChild(foot);
  renderRows();
  return card;
}

// ── 글로벌 신조프로젝트 오더북 (asiasis) ─────────────────────────
// 국내 4사 DART 테이블과 스키마가 달라(전세계·국적·발주처) 별도 렌더러.
// CSS 클래스는 order-table-* 를 그대로 재사용한다.
function renderAsiasisTable(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";

  if (!doc || !doc.orders || doc.orders.length === 0) {
    card.innerHTML = `<div class="card-name">${doc?.name || "글로벌 신조프로젝트 오더북"}</div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      <code>scripts/aggregate_asiasis_orders.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const RENDER_CAP = 600; // DOM 부담 방지: 필터 후 상위 N건만 렌더
  // 칩 목록은 전체 데이터 기준(빈도순, 기간필터와 무관하게 안정 유지)
  const nationalities = doc.nationalities || [...new Set(doc.orders.map((o) => o.nationality))];
  const categories = doc.categories || [...new Set(doc.orders.map((o) => o.category))];

  // 디폴트: 각 칩 그룹에서 대표(첫=최다) 하나만 켜짐
  const filt = {
    nationalities: new Set(nationalities.slice(0, 1)),
    categories: new Set(categories.slice(0, 1)),
    search: "",
    sortKey: "report_date",
    sortDir: -1,
  };
  if (state.tableRange[doc.id] == null) state.tableRange[doc.id] = TABLE_RANGE_DEFAULT;

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">${doc.name}</span>
      <span class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></span>
    </div>`;
  head.appendChild(buildTableRangePicker(state.tableRange[doc.id], (r) => { state.tableRange[doc.id] = r; renderRows(); }));
  card.appendChild(head);

  if (doc.note) {
    const note = document.createElement("div");
    note.className = "order-count";
    note.textContent = doc.note;
    card.appendChild(note);
  }

  const filterBar = document.createElement("div");
  filterBar.className = "order-filters";
  card.appendChild(filterBar);

  const natChips = document.createElement("div");
  natChips.className = "chips";
  filterBar.appendChild(natChips);

  const catChips = document.createElement("div");
  catChips.className = "chips";
  filterBar.appendChild(catChips);

  const searchWrap = document.createElement("div");
  searchWrap.className = "order-search";
  searchWrap.innerHTML = `<input type="text" placeholder="선종·조선소·발주처·제목 검색" />`;
  filterBar.appendChild(searchWrap);

  const countLine = document.createElement("div");
  countLine.className = "order-count";
  card.appendChild(countLine);

  const tableWrap = document.createElement("div");
  tableWrap.className = "order-table-wrap";
  card.appendChild(tableWrap);

  const COLS = [
    { key: "report_date", label: "보고일" },
    { key: "builder", label: "조선소", filter: true },
    { key: "nationality", label: "국적" },
    { key: "vessel_type", label: "선종", trunc: 170 },
    { key: "size", label: "사이즈", trunc: 130 },
    { key: "count", label: "척수", align: "right" },
    { key: "price_m", label: "선가(M$)", align: "right" },
    { key: "buyer", label: "발주처", filter: true },
    { key: "delivery", label: "납기" },
    { key: "_link", label: "" },
  ];
  filt.colFilters = {}; // 컬럼별 부분일치 필터 (조선소·발주처)

  function buildChip(container, label, active, onToggle) {
    const chipLabel = document.createElement("label");
    chipLabel.className = "chip" + (active ? "" : " off");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = active;
    chipLabel.append(cb, document.createTextNode(label));
    cb.addEventListener("change", () => {
      chipLabel.classList.toggle("off", !cb.checked);
      onToggle(cb.checked);
      renderRows();
    });
    container.appendChild(chipLabel);
  }

  nationalities.forEach((n, i) => buildChip(natChips, n, i === 0, (on) => (on ? filt.nationalities.add(n) : filt.nationalities.delete(n))));
  categories.forEach((c, i) => buildChip(catChips, c, i === 0, (on) => (on ? filt.categories.add(c) : filt.categories.delete(c))));

  searchWrap.querySelector("input").addEventListener("input", (e) => {
    filt.search = e.target.value.trim().toLowerCase();
    renderRows();
  });

  function priceCell(o) {
    if (o.price_m == null) return "-";
    const v = o.price_m.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
    const basis = o.price_basis === "총액" ? ` <span class="size-inferred">(총)</span>` : "";
    return `<span title="${(o.price_raw || "").replace(/"/g, "&quot;")}">${v}${basis}</span>`;
  }
  function cellValue(o, key) {
    switch (key) {
      case "count": return o.count ? `${o.count}척` : "-";
      case "price_m": return priceCell(o);
      case "vessel_type":
        if (!o.vessel_type) return "-";
        return o.vessel_type_raw && o.vessel_type_raw !== o.vessel_type
          ? `<span title="원문: ${o.vessel_type_raw.replace(/"/g, "&quot;")}">${o.vessel_type}</span>`
          : o.vessel_type;
      case "_link": return o.url ? `<a href="${o.url}" target="_blank" rel="noopener">원문</a>` : "";
      default: return o[key] || "-";
    }
  }
  // 말줄임(trunc) 컬럼용 평문 값 + 호버 툴팁 전체값
  function plainCell(o, key) {
    if (key === "vessel_type") {
      const v = o.vessel_type || "-";
      const full = o.vessel_type_raw && o.vessel_type_raw !== o.vessel_type ? `${v} (원문: ${o.vessel_type_raw})` : v;
      return { text: v, title: full };
    }
    const t = o[key] || "-";
    return { text: t, title: t };
  }

  // 테이블 골격(헤더행 + 컬럼필터 입력행)은 1회만 생성 → 필터 입력 중 포커스 유지.
  // 이후 renderRows()는 tbody만 다시 그린다.
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  const ths = {};
  COLS.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    th.style.textAlign = col.align === "right" ? "right" : "left";
    if (col.key !== "_link") {
      th.classList.add("sortable");
      th.title = "클릭: 내림차순 → 오름차순 → 정렬 해제";
      th.addEventListener("click", () => { cycleSortState(filt, col.key); renderRows(); });
    }
    ths[col.key] = th;
    htr.appendChild(th);
  });
  thead.appendChild(htr);

  const ftr = document.createElement("tr");
  ftr.className = "col-filter-row";
  COLS.forEach((col) => {
    const th = document.createElement("th");
    if (col.filter) {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.placeholder = `${col.label} 필터…`;
      inp.addEventListener("input", () => {
        filt.colFilters[col.key] = inp.value.trim().toLowerCase();
        renderRows();
      });
      // 헤더 정렬 클릭이 입력칸까지 전파되지 않도록
      th.addEventListener("click", (e) => e.stopPropagation());
      th.appendChild(inp);
    }
    ftr.appendChild(th);
  });
  thead.appendChild(ftr);

  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  tableWrap.appendChild(table);

  function updateSortIndicators() {
    COLS.forEach((col) => {
      const th = ths[col.key];
      if (!th) return;
      th.classList.remove("sort-asc", "sort-desc");
      if (filt.sortKey === col.key && filt.sortDir !== 0) {
        th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
      }
    });
  }

  function renderRows() {
    const cutoff = cutoffFor(state.tableRange[doc.id] || TABLE_RANGE_DEFAULT);
    const allOrders = doc.orders.filter((o) => o.report_date >= cutoff);
    const rows = allOrders.filter((o) => {
      if (!filt.nationalities.has(o.nationality)) return false;
      if (!filt.categories.has(o.category)) return false;
      for (const key in filt.colFilters) {
        const q = filt.colFilters[key];
        if (q && !String(o[key] || "").toLowerCase().includes(q)) return false;
      }
      if (filt.search) {
        const hay = `${o.vessel_type} ${o.vessel_type_raw} ${o.builder} ${o.buyer} ${o.title}`.toLowerCase();
        if (!hay.includes(filt.search)) return false;
      }
      return true;
    });
    if (filt.sortKey) {
      rows.sort((a, b) => {
        const av = a[filt.sortKey], bv = b[filt.sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
      });
    }
    updateSortIndicators();

    const shown = rows.slice(0, RENDER_CAP);
    const capped = rows.length > RENDER_CAP;
    countLine.textContent =
      `${rows.length.toLocaleString("ko-KR")}건 (전체 ${allOrders.length.toLocaleString("ko-KR")}건)` +
      (capped ? ` — 상위 ${RENDER_CAP}건만 표시, 필터·검색으로 좁히세요` : "");

    tbody.innerHTML = "";
    for (const o of shown) {
      const tr = document.createElement("tr");
      COLS.forEach((col) => {
        const td = document.createElement("td");
        td.style.textAlign = col.align === "right" ? "right" : "left";
        if (col.trunc) {
          // 긴 값은 최대 너비로 자르고(말줄임표) 전체는 호버 툴팁으로
          const { text, title } = plainCell(o, col.key);
          const span = document.createElement("span");
          span.className = "trunc";
          span.style.maxWidth = col.trunc + "px";
          span.textContent = text;
          span.title = title;
          td.appendChild(span);
        } else {
          td.innerHTML = cellValue(o, col.key);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }

  renderRows();
  return card;
}

// Institution directory: watchlist membership is independent of coverage and taxonomy.
function renderInstitutionProfiles(institutions, onSelect) {
  const panel = document.createElement("details");
  panel.className = "institution-profiles";
  if (!institutions.length) return panel;
  const esc = escapeHtml;
  const link = (url, label = "공식 근거 ↗") => /^https:\/\//.test(url || "")
    ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : "";
  const pct = (v) => v == null ? "미확인" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
  const amount = (a) => a?.value == null ? "미확인" : a.currency === "KRW"
    ? `${(a.value / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억원`
    : `${a.currency} ${(a.value / 1e9).toLocaleString("ko-KR", { maximumFractionDigits: 3 })}B`;
  const options = (values) => values.map((v)=>`<option value="${esc(v)}">${esc(v)}</option>`).join("");
  const styles = [...new Set(institutions.flatMap((i)=>i.styles || []))].sort();
  panel.innerHTML = `<summary>기관 분류 · 연도별 AUM · 추적 이유 <span>${institutions.length}개 기관</span></summary>
    <p>관심기관 8곳을 별도로 유지하며 DART 운용·자문사와 금융투자협회 통계에 수록된 기관을 함께 조회합니다. 국내 전체 인허가 명부는 아니며, 과거 명칭과 현재 명칭은 근거 없이 합치지 않습니다. 유형은 명칭 기준이고, 지역·스타일이 확인되지 않으면 미확인·미분류로 표시합니다.</p>
    <div class="profile-controls">
      <input type="search" aria-label="기관 목록 검색" placeholder="기관명·별칭 검색" />
      <select aria-label="관심기관 구분"><option value="watch">관심기관 8곳</option><option value="all">등록기관 전체</option></select>
      <select aria-label="기관 지역"><option value="">지역 전체</option>${options(["국내","해외","미확인"])}</select>
      <select aria-label="기관 유형"><option value="">유형 전체</option>${options([...new Set(institutions.map(i=>i.kind))].sort())}</select>
      <select aria-label="DART 연결 여부"><option value="">DART 연결 전체</option><option value="yes">저장 공시 있음</option><option value="no">저장 공시 미확인</option></select>
      <select aria-label="투자 스타일"><option value="">스타일 전체</option>${options(styles)}<option value="unknown">스타일 미분류</option></select>
    </div>
    <p class="profile-update">기본 AUM은 금융투자협회 순자산총액+평가액입니다. 협회 자료가 없는 기관은 확인된 운용사 공식 AUM을 표시합니다. 설정원본은 보조 자료로 보존합니다. AUM은 DART와 별도로 확인해 갱신합니다. 연말과 연중 값을 구분하며, 미확인은 0이나 미보유를 뜻하지 않습니다. USD B는 10억 달러입니다.</p>
    <div class="profile-directory"></div><div class="profile-pages"><button type="button" class="profile-prev">이전</button><span aria-live="polite"></span><button type="button" class="profile-next">다음</button></div>
    <div class="profile-detail" aria-live="polite"></div>`;
  const controls = panel.querySelector(".profile-controls");
  const [watch, region, kind, dart, style] = controls.querySelectorAll("select");
  const search = controls.querySelector("input");
  const directory = panel.querySelector(".profile-directory");
  const detail = panel.querySelector(".profile-detail");
  let page = 0, selected = null;
  const PAGE_SIZE = 20;

  function history(inst) {
    return inst.aum_history || (inst.profile?.aum || []).map((a)=>({...a,series:a.scope,period:"observation",basis:"운용사 공식 발표"}));
  }
  function primaryHistory(inst) {
    const points = history(inst);
    const nav = points.filter(a=>a.series==="kofia_nav");
    return nav.some(a=>a.value!=null) ? nav : points.filter(a=>a.series!=="kofia_nav" && a.series!=="kofia_principal");
  }
  function aumSections(inst) {
    const points = history(inst), primary = primaryHistory(inst);
    const principal = points.filter(a=>a.series==="kofia_principal");
    const otherOfficial = primary.some(a=>a.series==="kofia_nav")
      ? points.filter(a=>a.series!=="kofia_nav" && a.series!=="kofia_principal") : [];
    return `<h4>연도별 AUM</h4>${annualSeries(primary)}
      ${principal.length ? `<details class="aum-secondary"><summary>보조 자료 · 기존 설정원본 보기</summary><p>기존에 수집한 설정원본 기준 자료입니다. 위 AUM과 평가기준·집계 범위가 달라 직접 연결하거나 차이를 수익률로 해석하지 않습니다.</p>${annualSeries(principal)}</details>` : ""}
      ${otherOfficial.length ? `<details class="aum-secondary"><summary>보조 자료 · 운용사 공식 발표 AUM</summary>${annualSeries(otherOfficial)}</details>` : ""}`;
  }
  function renderDirectory() {
    const query = search.value.trim().toLowerCase();
    const entries = institutions.filter((i)=>(watch.value!=="watch" || i.watchlist) && (!region.value || i.region===region.value)
      && (!kind.value || i.kind===kind.value) && (!dart.value || (dart.value==="yes")===Boolean(i.dart_reports))
      && (!style.value || (style.value==="unknown" ? !i.styles?.length : i.styles?.includes(style.value)))
      && (!query || [i.name,...i.aliases].join(" ").toLowerCase().includes(query)));
    const pages = Math.max(1, Math.ceil(entries.length/PAGE_SIZE));
    page = Math.min(page,pages-1);
    directory.innerHTML = `<div class="profile-table-scroll"><table class="profile-table"><thead><tr><th>기관 · 분류</th><th>추적 이유 / 등록 근거</th><th>연도별 AUM 자료</th><th>DART 공시</th></tr></thead><tbody>${entries.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE).map((i)=>{
      const years = [...new Set(primaryHistory(i).filter(a=>a.value!=null).map(a=>a.date.slice(0,4)))].sort();
      return `<tr><td><button type="button" data-profile="${esc(i.id)}" aria-pressed="${i.id===selected}">${esc(i.name)}</button><small>${esc(i.region)} · ${esc(i.kind)}${i.watchlist ? " · 관심기관" : ""}</small></td>
        <td>${esc(i.profile?.reason || i.origins.join(" · "))}<small>${esc(i.styles?.join(" · ") || "투자 스타일 미분류")}</small></td>
        <td>${years.length ? `${years.join(" · ")}년<small>연도별 표·그래프 보기</small>` : (history(i).some(a=>a.series==="kofia_principal") ? "AUM 미확인<small>설정원본 보조 자료 있음</small>" : "공식 수치 미확인")}</td><td>${i.dart_reports ? `${i.dart_reports.toLocaleString("ko-KR")}건` : "저장 공시 미확인"}</td></tr>`;
    }).join("") || `<tr><td colspan="4">조건에 맞는 기관이 없습니다.</td></tr>`}</tbody></table></div>`;
    panel.querySelector(".profile-pages span").textContent = `${entries.length}개 기관 · ${page+1}/${pages}페이지`;
    panel.querySelector(".profile-prev").disabled = page===0;
    panel.querySelector(".profile-next").disabled = page===pages-1;
    directory.querySelectorAll("[data-profile]").forEach(b=>b.addEventListener("click",()=>{show(b.dataset.profile);detail.scrollIntoView({block:"start",behavior:"smooth"});}));
    if (!entries.some(i=>i.id===selected)) {
      if (entries.length) show(entries[0].id);
      else { selected=null; detail.innerHTML=""; }
    }
  }
  function annualSeries(points) {
    const groups = new Map();
    for (const a of points) {
      const key = `${a.series}|${a.currency}|${a.scope}|${a.basis}`;
      if (!groups.has(key)) groups.set(key,[]);
      groups.get(key).push(a);
    }
    if (!groups.size) return `<p>연도별 공식 AUM 자료 미확인. 확인되지 않은 연도는 추정하지 않습니다.</p>`;
    return [...groups.values()].map(rows=>{
      rows.sort((a,b)=>a.date.localeCompare(b.date));
      const byYear = new Map();
      for (const a of rows) byYear.set(Number(a.date.slice(0,4)),a);
      const first = Math.min(2022,...byYear.keys()), last = Math.max(new Date().getFullYear(),...byYear.keys());
      const years = Array.from({length:last-first+1},(_,i)=>first+i);
      const max = Math.max(1,...rows.map(a=>a.value || 0));
      const basis = rows[0];
      const kofia = basis.series === "kofia_nav" || basis.series === "kofia_principal";
      const kofiaPath = basis.series === "kofia_nav"
        ? "회사별설정규모 → AUM(펀드+투자일임)"
        : "투자신탁/회사/일임/기관전용 사모펀드";
      const bars = years.map(year=>{
        const a=byYear.get(year), usable=a?.value!=null;
        return `<div class="aum-bar-item"><span class="aum-bar-value">${usable ? amount(a) : "미확인"}</span><div class="aum-bar-track"><div class="aum-bar ${a?.period==="year_end" ? "" : "aum-bar-partial"}" style="height:${usable ? Math.max(1,a.value/max*100) : 0}%"></div></div><span>${year}${a && a.period!=="year_end" ? "*" : ""}</span></div>`;
      }).join("");
      return `<section class="aum-series"><h5>${esc(basis.series==="kofia_nav" ? "금융투자협회 AUM · 순자산총액+평가액" : basis.series==="kofia_principal" ? "금융투자협회 · 기존 설정원본" : "운용사 공식 AUM")}</h5>
        <p>${esc(basis.scope)} · ${esc(basis.basis)} · ${esc(basis.currency)}</p>
        ${kofia ? `<p class="profile-update">공통 출처: ${link(basis.source,"금융투자협회 종합통계포털 ↗")}<br>조회 경로: 펀드 → 회사 → 운용사통계 → ${esc(kofiaPath)}. 위 조회 조건과 아래 표의 실제 기준일을 선택하세요.</p>` : ""}
        <div class="aum-chart-scroll"><div class="aum-bars" role="img" aria-label="연도별 운용규모. 정확한 수치와 기준일은 아래 표에 표시합니다.">${bars}</div></div>
        <div class="profile-table-scroll"><table class="profile-table"><thead><tr><th>연도</th><th>실제 기준일</th><th>규모</th><th>전년 말 대비</th>${kofia ? "" : "<th>출처</th>"}</tr></thead><tbody>${years.map(year=>{
          const a=byYear.get(year), prev=byYear.get(year-1);
          const change=a?.value!=null && prev?.value>0 && prev.period==="year_end" && (a.period==="year_end" || a.period==="ytd") ? (a.value/prev.value-1)*100 : null;
          return `<tr><td>${year}${a && a.period!=="year_end" ? " (연중)" : ""}</td><td>${esc(a?.date || "미확인")}</td><td>${amount(a)}</td><td>${pct(change)}${change!=null && a.period!=="year_end" ? " (연중)" : ""}</td>${kofia ? "" : `<td>${a ? link(a.source,"출처 ↗") : "—"}</td>`}</tr>`;
        }).join("")}</tbody></table></div>
        <p class="profile-update">* 연중 관측값은 연말 값이 아닙니다. 연도 안에 여러 자료가 있으면 마지막 확인값을 표시합니다. 서로 다른 범위·통화·평가기준은 별도 그래프로 표시합니다. 규모 증감률은 투자 수익률이 아닙니다.</p></section>`;
    }).join("");
  }
  function show(id) {
    const inst = institutions.find(i=>i.id===id);
    if (!inst) return;
    selected=id;
    const p=inst.profile;
    directory.querySelectorAll("[data-profile]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.profile===id)));
    detail.innerHTML=`<div class="profile-title"><h3>${esc(inst.name)}</h3><button type="button" class="profile-filter" ${inst.dart_reports ? "" : "disabled"}>${inst.dart_reports ? "이 기관 공시 보기" : "저장 공시 미확인"}</button></div>
      <p>${esc(inst.region)} · ${esc(inst.kind)} · ${esc(inst.styles?.join(" · ") || "스타일 미분류")} · ${inst.watchlist ? "관심기관" : "일반 등록기관"}</p>
      ${p ? `<dl><dt>공식 자료에서 확인한 특징</dt><dd>${esc(p.fact)} ${link(p.source)}</dd><dt>선정 이유 · 관찰 목적</dt><dd>${esc(p.reason)}</dd><dt>관찰 포인트</dt><dd>${esc(p.watch)}</dd><dt>자료 해석</dt><dd>${esc(p.caution)}</dd></dl><p class="profile-update">설명 확인일 ${esc(p.checked)}</p>` : `<p>등록 근거: ${esc(inst.origins.join(" · "))}. 관심기관 선정이나 투자 추천을 뜻하지 않습니다. 투자 스타일은 검증한 자료가 없으면 미분류로 둡니다.</p>`}
      ${aumSections(inst)}
      ${performanceSections(p)}
      <p class="profile-update">AUM은 한국 보유액이 아닙니다. 설정원본과 순자산 평가액은 다를 수 있습니다. 공시 미확인은 미보유를 뜻하지 않습니다.</p>`;
    detail.querySelector(".profile-filter").addEventListener("click",()=>onSelect(id));
  }
  function performanceSections(profile) {
    const perf=profile?.performance || {};
    const renderRecord=(f)=>`<section class="profile-fund"><strong>${esc(f.name)}${f.class ? ` · ${esc(f.class)}` : ""}</strong>
      <p>${esc(f.coverage || "해당 자료에 명시된 운용 범위만 포함합니다.")}</p>
      <p>${esc(f.currency)} · ${esc(f.basis)}</p><p>비교지수: ${esc(f.benchmark || "미확인")}</p>
      ${(f.annual || []).length ? `<h5>연도별 수익률 (1~12월)</h5>${performanceTable(f.annual.map(r=>({...r,label:r.year+"년"})))}` : "<p>역년 기준 연간 수익률 미확인</p>"}
      ${(f.rolling || []).length ? `<h5>기간별 수익률 · 역년 성과와 구분</h5>${performanceTable(f.rolling.map(r=>({...r,label:r.period+" · "+r.date})))}` : ""}
      ${f.checked ? `<p class="profile-update">자료 확인일 ${esc(f.checked)} · 실제 성과 기준일은 표를 참고하세요.</p>` : ""}</section>`;
    const company=(perf.company || []).filter(f=>f.coverage_verified===true);
    const korea=(perf.korea_equity || []).filter(f=>f.coverage_verified===true);
    const funds=profile?.funds || [];
    return `<section class="institution-performance"><h4>투자성과 · 운용 범위별</h4>
      <p>AUM 증감은 고객 자금 유출입을 포함하므로 투자수익률로 사용하지 않습니다. 아래 성과는 공식 발표 자료이며 서로 다른 범위의 수익률을 합산·평균하지 않습니다.</p>
      <h5>1. 운용사 전체 연간 성과</h5>
      ${company.length ? company.map(renderRecord).join("") : "<p>전체 성과 미확인 · 모든 펀드·일임계좌의 포함 범위와 산출 기준이 확인된 공식 자료가 아직 등록되지 않았습니다.</p>"}
      <h5>2. 한국 주식 전략 종합 성과</h5>
      ${korea.length ? korea.map(renderRecord).join("") : "<p>전략 종합 성과 미확인 · 한국 주식 전략의 포함 계좌와 산출 기준이 확인된 공식 자료가 아직 등록되지 않았습니다.</p>"}
      <h5>3. 확인된 개별 펀드 성과 · ${funds.length}개 펀드·클래스</h5>
      <p>확인된 일부 상품만 표시합니다. 전체 상품 목록이나 운용사 전체 성과가 아닙니다.</p>
      ${funds.length ? funds.map(renderRecord).join("") : "<p>펀드·클래스·기간·산출 기준을 확인한 성과 자료 미확인</p>"}
      <p class="profile-update">초과수익은 같은 행의 수익률과 공식 비교지수 수익률의 차이(%p)입니다. 위험을 조정한 알파가 아니며, 비교지수가 없으면 계산하지 않습니다. 과거 성과가 미래 성과를 보장하지 않습니다.</p></section>`;
  }
  function performanceTable(rows) {
    return `<div class="profile-table-scroll"><table class="profile-table"><thead><tr><th>기간 · 기준일</th><th>수익률</th><th>비교지수</th><th>초과수익 (%p)</th><th>출처</th></tr></thead><tbody>${rows.map(r=>{
      const excess=Number.isFinite(r.return) && Number.isFinite(r.benchmark_return) ? r.return-r.benchmark_return : null;
      return `<tr><td>${esc(r.label)}</td><td>${pct(r.return)}</td><td>${pct(r.benchmark_return)}</td><td>${excess==null ? "—" : `${excess>0 ? "+" : ""}${excess.toFixed(2)}%p`}</td><td>${link(r.source)}</td></tr>`;
    }).join("")}</tbody></table></div>`;
  }
  controls.querySelectorAll("select").forEach(s=>s.addEventListener("change",()=>{page=0;renderDirectory();}));
  search.addEventListener("input",()=>{page=0;renderDirectory();});
  panel.querySelector(".profile-prev").addEventListener("click",()=>{page--;renderDirectory();});
  panel.querySelector(".profile-next").addEventListener("click",()=>{page++;renderDirectory();});
  renderDirectory();
  return panel;
}


// ── 기관 수급: 대량보유 공시 (major_holdings) ────────────────────
// 시장·보고자유형 칩 + 종목·보고자 컬럼필터. 기본은 '개인' 숨김.
function renderMajorHoldings(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card institution-events";

  if (!doc || !doc.orders || doc.orders.length === 0) {
    card.innerHTML = `<div class="card-name">${doc?.name || "대량보유 공시"}</div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      <code>fetch_major_holdings.py</code> → <code>aggregate_major_holdings.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const RENDER_CAP = 600;
  const markets = doc.markets || [...new Set(doc.orders.map((o) => o.market))];
  const types = doc.reporter_types || [...new Set(doc.orders.map((o) => o.reporter_type))];

  // 기본: 시장 전부 ON, 유형은 '개인'만 OFF, 지분율 변동 없는 보고(담보·계약변경 등) 숨김
  const filt = {
    markets: new Set(markets),
    types: new Set(types.filter((t) => t !== "개인")),
    movedOnly: true,
    institution: "",
    year: "",
    colFilters: {},
    search: "",
    sortKey: "rcept_dt",
    sortDir: -1,
  };
  if (state.tableRange[doc.id] == null) state.tableRange[doc.id] = TABLE_RANGE_DEFAULT;

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">${doc.name}</span>
      <span class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></span>
    </div>`;
  head.appendChild(buildTableRangePicker(state.tableRange[doc.id], (r) => { state.tableRange[doc.id] = r; filt.year = ""; yearSelect.value = ""; renderRows(); }));
  card.appendChild(head);

  if (doc.note) {
    const note = document.createElement("div");
    note.className = "order-count";
    note.textContent = doc.note + (doc.history
      ? ` 저장 범위: ${doc.history.start}~ · 지분율 확인 ${doc.history.with_ratio.toLocaleString("ko-KR")}/${doc.history.reports.toLocaleString("ko-KR")}건.`
      : "");
    card.appendChild(note);
  }

  const filterBar = document.createElement("div");
  filterBar.className = "order-filters";
  card.appendChild(filterBar);

  const marketChips = document.createElement("div");
  marketChips.className = "chips";
  filterBar.appendChild(marketChips);

  const typeChips = document.createElement("div");
  typeChips.className = "chips";
  filterBar.appendChild(typeChips);

  const optChips = document.createElement("div");
  optChips.className = "chips";
  filterBar.appendChild(optChips);

  const searchWrap = document.createElement("div");
  searchWrap.className = "order-search";
  searchWrap.innerHTML = `<input type="text" placeholder="종목·보고자 검색" />`;
  filterBar.appendChild(searchWrap);

  const countLine = document.createElement("div");
  countLine.className = "order-count";
  card.appendChild(countLine);

  const tableWrap = document.createElement("div");
  tableWrap.className = "order-table-wrap";
  card.appendChild(tableWrap);

  const COLS = [
    { key: "rcept_dt", label: "공시일" },
    { key: "corp_name", label: "종목", filter: true },
    { key: "market", label: "시장" },
    { key: "reporter", label: "보고자", filter: true },
    { key: "reporter_type", label: "유형" },
    { key: "stkrt", label: "지분율(직전→현재)", align: "right" },
    { key: "shares_chg", label: "주식등 수량 증감", align: "right" },
    { key: "event", label: "변화", filter: true },
    { key: "report_reason", label: "보고사유", filter: true },
    { key: "report_short", label: "공시" },
    { key: "_link", label: "" },
  ];

  function buildChip(container, label, active, onToggle) {
    const chipLabel = document.createElement("label");
    chipLabel.className = "chip" + (active ? "" : " off");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = active;
    chipLabel.append(cb, document.createTextNode(label));
    cb.addEventListener("change", () => {
      chipLabel.classList.toggle("off", !cb.checked);
      onToggle(cb.checked);
      renderRows();
    });
    container.appendChild(chipLabel);
  }

  markets.forEach((m) => buildChip(marketChips, m, true, (on) => (on ? filt.markets.add(m) : filt.markets.delete(m))));
  types.forEach((t) => buildChip(typeChips, t, t !== "개인", (on) => (on ? filt.types.add(t) : filt.types.delete(t))));
  buildChip(optChips, "지분율 변동만", true, (on) => { filt.movedOnly = on; });

  const instSelect = document.createElement("select");
  instSelect.className = "institution-filter";
  instSelect.setAttribute("aria-label", "기관 공시 필터");
  const institutionMap = new Map((doc.institutions || []).map(i=>[i.id,i]));
  const institutionCounts = new Map();
  doc.orders.forEach(o=>institutionCounts.set(o.institution_id,(institutionCounts.get(o.institution_id)||0)+1));
  instSelect.innerHTML = `<option value="">모든 보고자</option><option value="watch">관심기관 전체</option><option value="managers">자산운용사 전체</option><option value="domestic_managers">국내 자산운용사</option><option value="registered">등록기관 전체</option>` +
    (doc.institutions || []).filter(i=>i.dart_reports || i.watchlist).map((inst) => {
      const count = institutionCounts.get(inst.id) || 0;
      return `<option value="${escapeHtml(inst.id)}">${escapeHtml(inst.name)} (${count ? count + "건" : "자료 미확인"})</option>`;
    }).join("");
  instSelect.addEventListener("change", () => {
    filt.institution = instSelect.value;
    optChips.querySelector("input").disabled = Boolean(filt.institution);
    renderRows();
  });
  filterBar.prepend(instSelect);
  const yearSelect = document.createElement("select");
  yearSelect.className = "institution-filter";
  yearSelect.setAttribute("aria-label", "공시연도 필터");
  yearSelect.innerHTML = `<option value="">모든 연도</option>` +
    [...new Set(doc.orders.map((o) => o.rcept_dt.slice(0, 4)))].sort().reverse()
      .map((year) => `<option value="${year}">${year}년</option>`).join("");
  yearSelect.addEventListener("change", () => {
    filt.year = yearSelect.value;
    state.tableRange[doc.id] = "all";
    head.querySelectorAll(".table-range button").forEach((button) => button.classList.toggle("active", button.textContent === "전체"));
    renderRows();
  });
  filterBar.prepend(yearSelect);
  const profiles = renderInstitutionProfiles(doc.institutions || [], (id) => {
    instSelect.value = id;
    yearSelect.value = "";
    filt.year = "";
    state.tableRange[doc.id] = "all";
    head.querySelectorAll(".table-range button").forEach((b) => b.classList.toggle("active", b.textContent === "전체"));
    filt.search = "";
    searchWrap.querySelector("input").value = "";
    filt.colFilters = {};
    instSelect.dispatchEvent(new Event("change"));
    filterBar.scrollIntoView({ block: "center", behavior: "smooth" });
  });
  if ((doc.institutions || []).some((i) => i.profile)) card.insertBefore(profiles, filterBar);


  searchWrap.querySelector("input").addEventListener("input", (e) => {
    filt.search = e.target.value.trim().toLowerCase();
    renderRows();
  });

  function cellValue(o, key) {
    switch (key) {
      case "shares_chg":
        return o.shares_chg == null ? "-" : `${o.shares_chg > 0 ? "+" : ""}${o.shares_chg.toLocaleString("ko-KR")}`;
      case "report_reason":
        return escapeHtml(o.report_reason || "상세 미확인");
      case "event":
        return escapeHtml(o.event || "상세 미확인");
      case "corp_name":
        return o.stock_code ? `<span title="${o.stock_code}">${o.corp_name}</span>` : (o.corp_name || "-");
      case "reporter_type":
        return o.reporter_type === "개인" ? `<span class="size-inferred">개인</span>` : o.reporter_type;
      case "stkrt": {
        if (o.stkrt == null) return "-";
        const now = o.stkrt.toFixed(2);
        if (o.chg == null) return `${now}%`;
        const prev = (o.stkrt - o.chg).toFixed(2);
        const dir = o.chg > 0 ? "up" : o.chg < 0 ? "down" : "";
        const arrow = o.chg > 0 ? "▲" : o.chg < 0 ? "▼" : "";
        const sign = o.chg > 0 ? "+" : "";
        return `${prev}→${now}% <span class="chg ${dir}">${arrow}${sign}${o.chg.toFixed(2)}</span>`;
      }
      case "report_short":
        return o.is_correction ? `<span class="size-inferred">${o.report_short}</span>` : o.report_short;
      case "_link":
        return o.rcept_no
          ? `<a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${o.rcept_no}" target="_blank" rel="noopener">원문</a>`
          : "";
      default: return o[key] || "-";
    }
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  const ths = {};
  COLS.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    if (col.key !== "_link") {
      th.classList.add("sortable");
      th.title = "클릭: 내림차순 → 오름차순 → 정렬 해제";
      th.addEventListener("click", () => { cycleSortState(filt, col.key); renderRows(); });
    }
    ths[col.key] = th;
    htr.appendChild(th);
  });
  thead.appendChild(htr);

  const ftr = document.createElement("tr");
  ftr.className = "col-filter-row";
  COLS.forEach((col) => {
    const th = document.createElement("th");
    if (col.filter) {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.placeholder = `${col.label} 필터…`;
      inp.addEventListener("input", () => {
        filt.colFilters[col.key] = inp.value.trim().toLowerCase();
        renderRows();
      });
      th.addEventListener("click", (e) => e.stopPropagation());
      th.appendChild(inp);
    }
    ftr.appendChild(th);
  });
  thead.appendChild(ftr);

  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  tableWrap.appendChild(table);

  function updateSortIndicators() {
    COLS.forEach((col) => {
      const th = ths[col.key];
      if (!th) return;
      th.classList.remove("sort-asc", "sort-desc");
      if (filt.sortKey === col.key && filt.sortDir !== 0) {
        th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
      }
    });
  }

  function renderRows() {
    const cutoff = cutoffFor(state.tableRange[doc.id] || TABLE_RANGE_DEFAULT);
    const allOrders = doc.orders.filter((o) => o.rcept_dt >= cutoff && (!filt.year || o.rcept_dt.startsWith(filt.year + "-")));
    const rows = allOrders.filter((o) => {
      const institution = institutionMap.get(o.institution_id);
      if (filt.institution === "watch" && !institution?.watchlist) return false;
      if (filt.institution === "registered" && !institution) return false;
      if (filt.institution === "managers" && institution?.kind !== "자산운용사") return false;
      if (filt.institution === "domestic_managers" && !(institution?.region === "국내" && institution.kind === "자산운용사")) return false;
      if (filt.institution && !["watch","registered","managers","domestic_managers"].includes(filt.institution) && o.institution_id !== filt.institution) return false;
      if (!filt.markets.has(o.market)) return false;
      if (!filt.types.has(o.reporter_type)) return false;
      // 기관 필터 사용 시 목적·계약 변경과 상세 누락도 보여준다.
      if (!filt.institution && filt.movedOnly && !(o.chg != null && o.chg !== 0)) return false;
      for (const key in filt.colFilters) {
        const q = filt.colFilters[key];
        if (q && !String(o[key] || "").toLowerCase().includes(q)) return false;
      }
      if (filt.search) {
        const inst = institutionMap.get(o.institution_id);
        const hay = `${o.corp_name} ${o.reporter} ${inst?.name || ""}`.toLowerCase();
        if (!hay.includes(filt.search)) return false;
      }
      return true;
    });
    if (filt.sortKey) {
      rows.sort((a, b) => {
        const av = a[filt.sortKey], bv = b[filt.sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
      });
    }
    updateSortIndicators();

    const shown = rows.slice(0, RENDER_CAP);
    const capped = rows.length > RENDER_CAP;
    countLine.textContent =
      `${rows.length.toLocaleString("ko-KR")}건 (전체 ${allOrders.length.toLocaleString("ko-KR")}건)` +
      (filt.institution ? " · 선택한 기관의 지분율 동일·상세 미확인 공시도 표시" : "") +
      (capped ? ` — 상위 ${RENDER_CAP}건만 표시, 필터·검색으로 좁히세요` : "");

    tbody.innerHTML = "";
    for (const o of shown) {
      const tr = document.createElement("tr");
      if (o.is_correction) tr.classList.add("is-correction");
      COLS.forEach((col) => {
        const td = document.createElement("td");
        td.innerHTML = cellValue(o, col.key);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }

  renderRows();
  return card;
}

// ── 종목별 지분 추이 (보고자별 보유비율 차트) ────────────────────
// 어느 기관이 어디서부터 매집/매도했는지: x=보고일, y=보유비율%, 시리즈=보고자.
function renderStockTrajectory(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";

  const stocksMap = (doc && doc.stocks) || {};
  const stockNames = Object.keys(stocksMap);
  if (!stockNames.length) {
    card.innerHTML = `<div class="card-name">종목별 지분 추이</div>
      <div class="card-empty">지분율 상세가 아직 없습니다.<br>
      <code>fetch_holding_details.py</code> → <code>aggregate_major_holdings.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }
  // 기본 선택용: 보고자 많은(멀티라인) 종목 우선, 동수면 포인트 많은 순
  const repCount = (n) => Object.keys(stocksMap[n].s).length;
  const ptCount = (n) => Object.values(stocksMap[n].s).reduce((a, p) => a + p.length, 0);
  stockNames.sort((a, b) => repCount(b) - repCount(a) || ptCount(b) - ptCount(a));

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">종목별 지분 추이 (보고자별 보유비율)</span>
      <span class="card-freq">저장된 공시 기준 · 지분율 변동이 모두 매매를 뜻하지는 않습니다</span>
    </div>`;
  card.appendChild(head);

  const picker = document.createElement("div");
  picker.className = "order-search";
  picker.style.margin = "8px 0 12px";
  const dlId = "stk-" + Math.random().toString(36).slice(2, 8);
  picker.innerHTML = `<input list="${dlId}" placeholder="종목명 입력·선택 (지분율 데이터 있는 종목)" />
    <datalist id="${dlId}">${stockNames.map((n) => `<option value="${n}"></option>`).join("")}</datalist>`;
  card.appendChild(picker);

  const overlap = document.createElement("details");
  overlap.className = "institution-overlap";
  const matches = stockNames.map((stock) => {
    const byInstitution = new Map();
    for (const [rep, pts] of Object.entries(stocksMap[stock].s)) {
      const id = doc.reporter_institutions?.[rep];
      if (!id || !(doc.institutions || []).some(i=>i.id===id && i.watchlist)) continue;
      const last = pts[pts.length - 1];
      if (last[1] < 5) continue;
      const inst = (doc.institutions || []).find((i) => i.id === id);
      if (!byInstitution.has(id)) byInstitution.set(id, []);
      byInstitution.get(id).push(`${inst?.name || rep} ${last[1].toFixed(2)}% (${last[0]})`);
    }
    return { stock, count: byInstitution.size, reports: [...byInstitution.values()].flat() };
  }).filter((it) => it.count >= 2).sort((a, b) => b.count - a.count || a.stock.localeCompare(b.stock, "ko"));
  const overlapTitle = document.createElement("summary");
  overlapTitle.textContent = `관심기관 2곳 이상이 마지막 공시에서 5% 이상을 보고한 종목 (${matches.length})`;
  overlap.appendChild(overlapTitle);
  const overlapNote = document.createElement("p");
  overlapNote.className = "order-count";
  overlapNote.textContent = "기관별 보고일이 다릅니다. 현재 동시 보유를 확인한 목록이 아니며, 지분율을 합산하지 않습니다. 종목을 누르면 아래 추이를 표시합니다.";
  overlap.appendChild(overlapNote);
  for (const it of matches) {
    const row = document.createElement("div");
    const button = document.createElement("button");
    button.textContent = it.stock;
    button.addEventListener("click", () => show(it.stock));
    row.append(button, document.createTextNode(" " + it.reports.join(" · ")));
    overlap.appendChild(row);
  }
  card.appendChild(overlap);

  const chartWrap = document.createElement("div");
  chartWrap.className = "chart-wrap";
  const canvas = document.createElement("canvas");
  chartWrap.appendChild(canvas);
  card.appendChild(chartWrap);

  const chipsDiv = document.createElement("div");
  card.appendChild(chipsDiv);

  const summary = document.createElement("div");
  summary.className = "data-table";
  summary.style.marginTop = "10px";
  card.appendChild(summary);

  const pickerInput = picker.querySelector("input");
  let chart = null;
  function show(stock) {
    const entry = stocksMap[stock];
    if (!entry) return;
    pickerInput.value = stock; // 현재 보고 있는 종목 표시
    const series = entry.s; // {보고자: [[date, stkrt], ...]} (aggregate에서 정렬·압축됨)
    const reporters = Object.keys(series);

    const pseudo = { name: stock, unit: "%", default_series: reporters, series };
    if (chart) chart.destroy();
    chart = drawChart(canvas, pseudo, series);
    chipsDiv.innerHTML = "";
    buildChips(chipsDiv, chart);

    const sum = reporters.map((r) => {
      const pts = series[r];
      const first = pts[0][1], last = pts[pts.length - 1][1];
      return { r, first, last, net: last - first, n: entry.meta?.[r]?.reports ?? pts.length,
        status: entry.meta?.[r]?.status || "보고 상태 미확인", lastDt: pts[pts.length - 1][0] };
    }).sort((a, b) => b.last - a.last);
    summary.style.display = "block";
    summary.innerHTML =
      `<table><thead><tr><th>보고자</th><th>첫 관측</th><th>마지막 보고</th><th>순증감(%p)</th><th>보고</th><th>최근보고일</th><th>마지막 공시 상태</th></tr></thead><tbody>` +
      sum.map((s) => `<tr><td>${s.r}</td><td>${s.first.toFixed(2)}%</td><td>${s.last.toFixed(2)}%</td>` +
        `<td class="${s.net > 0 ? "up" : s.net < 0 ? "down" : ""}">${s.net > 0 ? "+" : ""}${s.net.toFixed(2)}</td>` +
        `<td>${s.n}</td><td>${s.lastDt}</td><td>${escapeHtml(s.status)}</td></tr>`).join("") +
      `</tbody></table>`;
  }

  pickerInput.addEventListener("change", (e) => {
    const v = e.target.value.trim();
    if (stocksMap[v]) show(v);
  });
  show(stockNames[0]); // 기본: 보고 건수 많은 종목
  return card;
}

// ── 기관별 종목 증감 추이 (보고자 선택 → 메이저 종목 스몰멀티플) ──
// holdings_traj를 보고자→종목으로 피벗. 상위 N개 미니차트 + 전체 표.
function renderInstHoldings(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";
  const stocksMap = (doc && doc.stocks) || {};
  if (!Object.keys(stocksMap).length) {
    card.innerHTML = `<div class="card-name">기관별 종목 증감 추이</div>
      <div class="card-empty">지분율 상세가 아직 없습니다.</div>`;
    return card;
  }

  // 피벗: 보고자 → {종목: [[날짜, 보유비율]]}
  const byRep = new Map();
  for (const [stock, obj] of Object.entries(stocksMap)) {
    for (const [rep, pts] of Object.entries(obj.s)) {
      if (!byRep.has(rep)) byRep.set(rep, {});
      byRep.get(rep)[stock] = pts;
    }
  }
  // 2종목 이상 보유한 보고자만(포트폴리오 홀더), 보유종목 많은 순
  const reps = [...byRep.keys()]
    .filter((r) => Object.keys(byRep.get(r)).length >= 2 || doc.reporter_institutions?.[r])
    .sort((a, b) => Object.keys(byRep.get(b)).length - Object.keys(byRep.get(a)).length);
  if (!reps.length) {
    card.innerHTML = `<div class="card-name">기관별 종목 증감 추이</div>
      <div class="card-empty">2종목 이상 보유한 보고자가 없습니다.</div>`;
    return card;
  }

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">기관별 종목 증감 추이</span>
      <span class="card-freq">최대 30개 차트 · 마지막 공시 이후 실제 보유량은 확인되지 않습니다</span>
    </div>`;
  card.appendChild(head);

  const picker = document.createElement("div");
  picker.className = "order-search";
  picker.style.margin = "8px 0 12px";
  const dlId = "rep-" + Math.random().toString(36).slice(2, 8);
  picker.innerHTML = `<input list="${dlId}" placeholder="기관·보고자 입력·선택 (등록기관은 1종목도 표시)" />
    <datalist id="${dlId}">${reps.map((r) => `<option value="${r}"></option>`).join("")}</datalist>`;
  card.appendChild(picker);
  const pickerInput = picker.querySelector("input");

  const shortcuts = document.createElement("div");
  shortcuts.className = "institution-shortcuts";
  for (const inst of (doc.institutions || []).filter(i=>i.watchlist)) {
    const reporters = [...byRep.keys()].filter((r) => doc.reporter_institutions?.[r] === inst.id);
    if (!reporters.length) {
      const missing = document.createElement("span");
      missing.className = "card-freq";
      missing.textContent = `${inst.name} · 자료 미확인`;
      shortcuts.appendChild(missing);
    }
    for (const rep of reporters) {
      const button = document.createElement("button");
      button.textContent = reporters.length > 1 ? `${inst.name} · ${rep}` : inst.name;
      button.title = rep;
      button.addEventListener("click", () => show(rep));
      shortcuts.appendChild(button);
    }
  }
  card.appendChild(shortcuts);

  const selWrap = document.createElement("div"); // 종목 멀티셀렉트가 들어갈 자리
  card.appendChild(selWrap);

  const countLine = document.createElement("div");
  countLine.className = "order-count";
  card.appendChild(countLine);

  const grid = document.createElement("div");
  grid.className = "mini-grid";
  card.appendChild(grid);

  const tableWrap = document.createElement("div");
  tableWrap.className = "data-table";
  tableWrap.style.marginTop = "12px";
  card.appendChild(tableWrap);

  const CAP = 30;       // 차트로 볼 수 있는 최대 종목 수
  const DEFAULT_N = 9;  // 기본 선택(현재 지분율 상위)
  let charts = [];

  function show(rep) {
    pickerInput.value = rep;
    const stocks = byRep.get(rep);
    const items = Object.entries(stocks).map(([s, pts]) => ({
      s, pts, first: pts[0][1], last: pts[pts.length - 1][1],
      net: pts[pts.length - 1][1] - pts[0][1], lastDt: pts[pts.length - 1][0],
      n: stocksMap[s].meta?.[rep]?.reports ?? pts.length,
      meta: stocksMap[s].meta?.[rep] || {},
    })).sort((a, b) => b.last - a.last); // 메이저=현재 지분율 큰 순
    const itemMap = new Map(items.map((it) => [it.s, it]));
    let selected = items.slice(0, Math.min(DEFAULT_N, items.length)).map((it) => it.s);

    // ── 종목 멀티셀렉트 (검색박스 + 드롭다운, 최대 CAP개) ──
    selWrap.innerHTML = "";
    const ms = document.createElement("div"); ms.className = "ms";
    const box = document.createElement("div"); box.className = "ms-box";
    const chipsSpan = document.createElement("span"); chipsSpan.className = "ms-chips";
    const input = document.createElement("input"); input.className = "ms-input";
    input.placeholder = "종목 검색·추가";
    box.append(chipsSpan, input);
    const drop = document.createElement("div"); drop.className = "ms-drop"; drop.hidden = true;
    ms.append(box, drop);
    selWrap.appendChild(ms);

    function renderChips() {
      chipsSpan.innerHTML = "";
      selected.forEach((s) => {
        const chip = document.createElement("span");
        chip.className = "ms-chip";
        chip.append(document.createTextNode(s + " "));
        const x = document.createElement("b"); x.textContent = "×";
        x.addEventListener("mousedown", (e) => { e.preventDefault(); selected = selected.filter((v) => v !== s); refresh(); });
        chip.appendChild(x);
        chipsSpan.appendChild(chip);
      });
    }
    function renderDrop() {
      const q = input.value.trim().toLowerCase();
      const opts = items.filter((it) => !q || it.s.toLowerCase().includes(q)).slice(0, 300);
      drop.innerHTML = "";
      const cnt = document.createElement("div"); cnt.className = "ms-count";
      cnt.textContent = `선택 ${selected.length}/${CAP} · 클릭해 추가/제거`;
      drop.appendChild(cnt);
      opts.forEach((it) => {
        const on = selected.includes(it.s);
        const o = document.createElement("div"); o.className = "ms-opt" + (on ? " on" : "");
        const dir = it.net > 0 ? "up" : it.net < 0 ? "down" : "";
        o.innerHTML = `<span>${it.s}</span><span class="card-freq">${it.last.toFixed(2)}% <span class="chg ${dir}">${it.net > 0 ? "+" : ""}${it.net.toFixed(2)}</span></span>`;
        o.addEventListener("mousedown", (e) => {
          e.preventDefault();
          if (on) selected = selected.filter((v) => v !== it.s);
          else if (selected.length < CAP) selected.push(it.s);
          refresh(); input.focus();
        });
        drop.appendChild(o);
      });
    }
    function refresh() { renderChips(); renderDrop(); renderCharts(); }

    box.addEventListener("click", () => input.focus());
    input.addEventListener("focus", () => { drop.hidden = false; renderDrop(); });
    input.addEventListener("input", renderDrop);
    ms.addEventListener("focusout", (e) => { if (!ms.contains(e.relatedTarget)) drop.hidden = true; });

    function renderCharts() {
      charts.forEach((c) => c.destroy());
      charts = [];
      grid.innerHTML = "";
      const sel = selected.map((s) => itemMap.get(s)).filter(Boolean).sort((a, b) => b.last - a.last);
      countLine.textContent = `${items.length.toLocaleString("ko-KR")}개 종목 공시 이력 · ${sel.length}개 차트 표시 (최대 ${CAP}) · 5% 미만 보고도 포함`;
      for (const it of sel) {
        const mc = document.createElement("div"); mc.className = "mini-hold";
        const dir = it.net > 0 ? "up" : it.net < 0 ? "down" : "";
        const arrow = it.net > 0 ? "▲" : it.net < 0 ? "▼" : "";
        mc.innerHTML = `<div class="mini-head"><span class="mini-name">${it.s}</span>
          <span class="card-freq">${it.last.toFixed(2)}% <span class="chg ${dir}">${arrow}${it.net > 0 ? "+" : ""}${it.net.toFixed(2)}</span></span></div>
          <div class="card-freq">${it.lastDt} · ${escapeHtml(it.meta.status || "보고 상태 미확인")}</div>`;
        const w = document.createElement("div"); w.className = "chart-wrap mini";
        const cv = document.createElement("canvas"); w.appendChild(cv); mc.appendChild(w);
        grid.appendChild(mc);
        charts.push(drawChart(cv, { name: it.s, unit: "%", default_series: [rep], series: { [rep]: it.pts } }, { [rep]: it.pts }));
      }
    }

    // 전체 보유종목 표 — 행 클릭으로도 차트 토글
    tableWrap.innerHTML =
      `<table><thead><tr><th>종목</th><th>첫 관측</th><th>마지막 보고</th><th>순증감(%p)</th><th>보고</th><th>최근보고일</th><th>마지막 공시 상태</th><th>보고사유</th><th>원문</th></tr></thead><tbody>` +
      items.map((it) => `<tr data-s="${it.s}"><td>${it.s}</td><td>${it.first.toFixed(2)}%</td><td>${it.last.toFixed(2)}%</td>` +
        `<td class="${it.net > 0 ? "up" : it.net < 0 ? "down" : ""}">${it.net > 0 ? "+" : ""}${it.net.toFixed(2)}</td>` +
        `<td>${it.n}</td><td>${it.lastDt}</td><td>${escapeHtml(it.meta.status || "보고 상태 미확인")}</td>` +
        `<td>${escapeHtml(it.meta.report_reason || "-")}</td><td>${/^\d{14}$/.test(it.meta.rcept_no || "") ? `<a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${it.meta.rcept_no}" target="_blank" rel="noopener">원문</a>` : "-"}</td></tr>`).join("") +
      `</tbody></table>`;
    tableWrap.querySelectorAll("tr[data-s]").forEach((tr) => tr.addEventListener("click", () => {
      const s = tr.getAttribute("data-s");
      if (selected.includes(s)) selected = selected.filter((v) => v !== s);
      else if (selected.length < CAP) selected.push(s);
      refresh();
    }));
    tableWrap.querySelectorAll("a").forEach((a) => a.addEventListener("click", (e) => e.stopPropagation()));

    renderChips();
    renderCharts();
  }

  pickerInput.addEventListener("change", (e) => {
    const v = e.target.value.trim();
    if (byRep.has(v)) show(v);
  });
  show(reps[0]); // 기본: 보유종목 최다 보고자
  return card;
}

// ── 전력: 발전 프로젝트 파이프라인 (EIA-860M) ────────────────────
// 기술 칩은 전부 켜고(전 발전원을 필터로 보는 게 목적), 상태 칩은 '착공 이상'만 켠 채로 시작한다.
// 인허가 전 단계(①②③)까지 켜면 서류상 물량이 대부분이라 실제 진행 물량이 묻힌다.
function renderPowerPipeline(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";

  if (!doc || !doc.rows || doc.rows.length === 0) {
    card.innerHTML = `<div class="card-name">${doc?.name || "발전 프로젝트 파이프라인"}</div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      <code>scripts/fetch_eia860m.py --backfill</code> → <code>scripts/aggregate_eia860m.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const RENDER_CAP = 600;
  const techs = doc.techs || [...new Set(doc.rows.map((r) => r.tech))];
  const statuses = doc.statuses || [...new Set(doc.rows.map((r) => r.status_label))];
  const BUILDING = new Set(doc.rows.filter((r) => ["U", "V", "TS"].includes(r.status)).map((r) => r.status_label));

  const filt = {
    techs: new Set(techs),
    statuses: new Set(statuses.filter((s) => BUILDING.has(s))),
    search: "",
    sortKey: "mw",
    sortDir: -1,
    colFilters: {},
  };
  if (filt.statuses.size === 0) statuses.forEach((s) => filt.statuses.add(s));

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">${doc.name}</span>
      <span class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></span>
    </div>`;
  card.appendChild(head);

  if (doc.note) {
    const note = document.createElement("div");
    note.className = "order-count";
    note.textContent = doc.note;
    card.appendChild(note);
  }

  const filterBar = document.createElement("div");
  filterBar.className = "order-filters";
  card.appendChild(filterBar);
  const techChips = document.createElement("div");
  techChips.className = "chips";
  const statusChips = document.createElement("div");
  statusChips.className = "chips";
  const searchWrap = document.createElement("div");
  searchWrap.className = "order-search";
  searchWrap.innerHTML = `<input type="text" placeholder="사업자·발전소 검색" />`;
  filterBar.append(techChips, statusChips, searchWrap);

  const countLine = document.createElement("div");
  countLine.className = "order-count";
  card.appendChild(countLine);

  const tableWrap = document.createElement("div");
  tableWrap.className = "order-table-wrap";
  card.appendChild(tableWrap);

  const COLS = [
    { key: "entity", label: "사업자", filter: true, trunc: 190 },
    { key: "plant", label: "발전소", trunc: 160 },
    { key: "state", label: "주", filter: true },
    { key: "ba", label: "계통(BA)", filter: true },
    { key: "tech", label: "발전원" },
    { key: "mw", label: "용량(MW)", align: "right" },
    { key: "status_label", label: "상태" },
    { key: "cod", label: "준공예정" },
    { key: "slip", label: "지연(개월)", align: "right" },
    { key: "since", label: "최초등재" },
  ];

  function chip(container, label, active, onToggle) {
    const l = document.createElement("label");
    l.className = "chip" + (active ? "" : " off");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = active;
    l.append(cb, document.createTextNode(label));
    cb.addEventListener("change", () => {
      l.classList.toggle("off", !cb.checked);
      onToggle(cb.checked);
      renderRows();
    });
    container.appendChild(l);
  }
  techs.forEach((t) => chip(techChips, t, true, (on) => (on ? filt.techs.add(t) : filt.techs.delete(t))));
  statuses.forEach((s) => chip(statusChips, s, filt.statuses.has(s), (on) => (on ? filt.statuses.add(s) : filt.statuses.delete(s))));

  searchWrap.querySelector("input").addEventListener("input", (e) => {
    filt.search = e.target.value.trim().toLowerCase();
    renderRows();
  });

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  const ths = {};
  COLS.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    th.style.textAlign = col.align === "right" ? "right" : "left";
    th.classList.add("sortable");
    th.title = "클릭: 내림차순 → 오름차순 → 정렬 해제";
    th.addEventListener("click", () => { cycleSortState(filt, col.key); renderRows(); });
    ths[col.key] = th;
    htr.appendChild(th);
  });
  thead.appendChild(htr);

  const ftr = document.createElement("tr");
  ftr.className = "col-filter-row";
  COLS.forEach((col) => {
    const th = document.createElement("th");
    if (col.filter) {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.placeholder = `${col.label} 필터…`;
      inp.addEventListener("input", () => {
        filt.colFilters[col.key] = inp.value.trim().toLowerCase();
        renderRows();
      });
      th.addEventListener("click", (e) => e.stopPropagation());
      th.appendChild(inp);
    }
    ftr.appendChild(th);
  });
  thead.appendChild(ftr);

  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  tableWrap.appendChild(table);

  function cellHtml(r, key) {
    if (key === "mw") return r.mw == null ? "-" : fmt(r.mw);
    if (key === "slip") {
      if (r.slip == null) return "-";
      if (r.slip === 0) return `<span class="size-inferred">0</span>`;
      // 밀림(+)은 빨강, 앞당김(-)은 초록. 기존 지분율 증감과 같은 색 규약.
      const cls = r.slip > 0 ? "chg down" : "chg up";
      return `<span class="${cls}" title="최초 등재 시 준공예정: ${r.first_cod || "-"}">${r.slip > 0 ? "+" : ""}${r.slip}</span>`;
    }
    return r[key] || "-";
  }

  function updateSortIndicators() {
    COLS.forEach((col) => {
      const th = ths[col.key];
      th.classList.remove("sort-asc", "sort-desc");
      if (filt.sortKey === col.key && filt.sortDir !== 0) th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
    });
  }

  function renderRows() {
    const rows = doc.rows.filter((r) => {
      if (!filt.techs.has(r.tech)) return false;
      if (!filt.statuses.has(r.status_label)) return false;
      for (const key in filt.colFilters) {
        const q = filt.colFilters[key];
        if (q && !String(r[key] || "").toLowerCase().includes(q)) return false;
      }
      if (filt.search && !`${r.entity} ${r.plant}`.toLowerCase().includes(filt.search)) return false;
      return true;
    });
    if (filt.sortKey) {
      rows.sort((a, b) => {
        const av = a[filt.sortKey], bv = b[filt.sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
      });
    }
    updateSortIndicators();

    const gw = rows.reduce((s, r) => s + (r.mw || 0), 0) / 1000;
    const capped = rows.length > RENDER_CAP;
    countLine.textContent =
      `${rows.length.toLocaleString("ko-KR")}건 · ${gw.toLocaleString("ko-KR", { maximumFractionDigits: 1 })} GW` +
      (capped ? ` — 용량 상위 ${RENDER_CAP}건만 표시, 필터로 좁히세요` : "");

    tbody.innerHTML = "";
    for (const r of rows.slice(0, RENDER_CAP)) {
      const tr = document.createElement("tr");
      COLS.forEach((col) => {
        const td = document.createElement("td");
        td.style.textAlign = col.align === "right" ? "right" : "left";
        if (col.trunc) {
          const span = document.createElement("span");
          span.className = "trunc";
          span.style.maxWidth = col.trunc + "px";
          span.textContent = r[col.key] || "-";
          span.title = r[col.key] || "";
          td.appendChild(span);
        } else {
          td.innerHTML = cellHtml(r, col.key);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }

  renderRows();
  return card;
}

// ── 대주주 증여 공시 (gifts) ─────────────────────────────────────
// 임원·주요주주 소유보고 중 증여/수증. 기본: 소액임원(비주요주주) 숨김.
function renderGifts(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";
  if (!doc || !doc.orders || !doc.orders.length) {
    card.innerHTML = `<div class="card-name">${doc?.name || "대주주 증여 공시"}</div>
      <div class="card-empty">아직 데이터가 없습니다.<br><code>fetch_gifts.py</code> → <code>aggregate_gifts.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const RENDER_CAP = 600;
  const markets = doc.markets || [...new Set(doc.orders.map((o) => o.market))];
  const holders = doc.holder_types || [...new Set(doc.orders.map((o) => o.holder_type))];
  const directions = doc.directions || [...new Set(doc.orders.map((o) => o.direction))];

  const filt = {
    markets: new Set(markets),
    holders: new Set(holders.filter((h) => h !== "소액임원")), // 기본 소액임원 숨김
    directions: new Set(directions),
    colFilters: {},
    search: "",
    sortKey: "rcept_dt",
    sortDir: -1,
  };
  if (state.tableRange[doc.id] == null) state.tableRange[doc.id] = TABLE_RANGE_DEFAULT;

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">${doc.name}</span>
      <span class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></span>
    </div>`;
  head.appendChild(buildTableRangePicker(state.tableRange[doc.id], (r) => { state.tableRange[doc.id] = r; renderRows(); }));
  card.appendChild(head);

  if (doc.note) {
    const note = document.createElement("div");
    note.className = "order-count";
    note.textContent = doc.note;
    card.appendChild(note);
  }

  const filterBar = document.createElement("div");
  filterBar.className = "order-filters";
  card.appendChild(filterBar);
  const marketChips = document.createElement("div"); marketChips.className = "chips"; filterBar.appendChild(marketChips);
  const holderChips = document.createElement("div"); holderChips.className = "chips"; filterBar.appendChild(holderChips);
  const dirChips = document.createElement("div"); dirChips.className = "chips"; filterBar.appendChild(dirChips);
  const searchWrap = document.createElement("div"); searchWrap.className = "order-search";
  searchWrap.innerHTML = `<input type="text" placeholder="종목·보고자·상대방 검색" />`;
  filterBar.appendChild(searchWrap);

  const countLine = document.createElement("div"); countLine.className = "order-count"; card.appendChild(countLine);
  const tableWrap = document.createElement("div"); tableWrap.className = "order-table-wrap"; card.appendChild(tableWrap);

  const COLS = [
    { key: "rcept_dt", label: "공시일" },
    { key: "corp_name", label: "종목", filter: true },
    { key: "market", label: "시장" },
    { key: "reporter", label: "보고자", filter: true },
    { key: "position", label: "직위" },
    { key: "holder_type", label: "유형" },
    { key: "direction", label: "방향" },
    { key: "gift_shares", label: "규모(주식)", align: "right" },
    { key: "before_rate", label: "지분율(전→후)", align: "right" },
    { key: "counterparty", label: "상대방", filter: true },
    { key: "_link", label: "" },
  ];

  function buildChip(container, label, active, onToggle) {
    const cl = document.createElement("label");
    cl.className = "chip" + (active ? "" : " off");
    const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = active;
    cl.append(cb, document.createTextNode(label));
    cb.addEventListener("change", () => { cl.classList.toggle("off", !cb.checked); onToggle(cb.checked); renderRows(); });
    container.appendChild(cl);
  }
  markets.forEach((m) => buildChip(marketChips, m, true, (on) => (on ? filt.markets.add(m) : filt.markets.delete(m))));
  holders.forEach((h) => buildChip(holderChips, h, h !== "소액임원", (on) => (on ? filt.holders.add(h) : filt.holders.delete(h))));
  directions.forEach((d) => buildChip(dirChips, d, true, (on) => (on ? filt.directions.add(d) : filt.directions.delete(d))));
  searchWrap.querySelector("input").addEventListener("input", (e) => { filt.search = e.target.value.trim().toLowerCase(); renderRows(); });

  function cellValue(o, key) {
    switch (key) {
      case "corp_name": return o.stock_code ? `<span title="${o.stock_code}">${o.corp_name}</span>` : (o.corp_name || "-");
      case "holder_type": return o.holder_type === "소액임원" ? `<span class="size-inferred">소액임원</span>` : o.holder_type;
      case "direction": {
        const cls = o.direction && o.direction.indexOf("증여") === 0 ? "down" : "up"; // 증여(줌)=빨강, 수증(받음)=초록
        return `<span class="chg ${cls}">${o.direction}</span>`;
      }
      case "gift_shares":
        return o.gift_shares != null ? o.gift_shares.toLocaleString("ko-KR") + "주" : "-";
      case "before_rate": {
        if (o.before_rate == null || o.after_rate == null) return o.gift_rate != null ? `(${o.gift_rate}%)` : "-";
        const cls = o.after_rate < o.before_rate ? "down" : "up"; // 줄면 빨강, 늘면 초록
        return `${o.before_rate}% <span class="chg ${cls}">→ ${o.after_rate}%</span>`;
      }
      case "_link":
        return o.rcept_no ? `<a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${o.rcept_no}" target="_blank" rel="noopener">원문</a>` : "";
      default: return o[key] || "-";
    }
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  const ths = {};
  COLS.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    th.style.textAlign = col.align === "right" ? "right" : "left";
    if (col.key !== "_link") {
      th.classList.add("sortable");
      th.addEventListener("click", () => { cycleSortState(filt, col.key); renderRows(); });
    }
    ths[col.key] = th; htr.appendChild(th);
  });
  thead.appendChild(htr);
  const ftr = document.createElement("tr"); ftr.className = "col-filter-row";
  COLS.forEach((col) => {
    const th = document.createElement("th");
    if (col.filter) {
      const inp = document.createElement("input"); inp.type = "text"; inp.placeholder = `${col.label} 필터…`;
      inp.addEventListener("input", () => { filt.colFilters[col.key] = inp.value.trim().toLowerCase(); renderRows(); });
      th.addEventListener("click", (e) => e.stopPropagation());
      th.appendChild(inp);
    }
    ftr.appendChild(th);
  });
  thead.appendChild(ftr);
  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  tableWrap.appendChild(table);

  function updateSortIndicators() {
    COLS.forEach((col) => {
      const th = ths[col.key]; if (!th) return;
      th.classList.remove("sort-asc", "sort-desc");
      if (filt.sortKey === col.key && filt.sortDir !== 0) th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
    });
  }

  function renderRows() {
    const cutoff = cutoffFor(state.tableRange[doc.id] || TABLE_RANGE_DEFAULT);
    const all = doc.orders.filter((o) => o.rcept_dt >= cutoff);
    const rows = all.filter((o) => {
      if (!filt.markets.has(o.market)) return false;
      if (!filt.holders.has(o.holder_type)) return false;
      if (!filt.directions.has(o.direction)) return false;
      for (const key in filt.colFilters) {
        const q = filt.colFilters[key];
        if (q && !String(o[key] || "").toLowerCase().includes(q)) return false;
      }
      if (filt.search) {
        const hay = `${o.corp_name} ${o.reporter} ${o.counterparty}`.toLowerCase();
        if (!hay.includes(filt.search)) return false;
      }
      return true;
    });
    if (filt.sortKey) {
      rows.sort((a, b) => {
        const av = a[filt.sortKey], bv = b[filt.sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
      });
    }
    updateSortIndicators();
    const shown = rows.slice(0, RENDER_CAP);
    const capped = rows.length > RENDER_CAP;
    countLine.textContent = `${rows.length.toLocaleString("ko-KR")}건 (전체 ${all.length.toLocaleString("ko-KR")}건)` +
      (capped ? ` — 상위 ${RENDER_CAP}건만 표시, 필터·검색으로 좁히세요` : "");
    tbody.innerHTML = "";
    for (const o of shown) {
      const tr = document.createElement("tr");
      COLS.forEach((col) => {
        const td = document.createElement("td");
        td.style.textAlign = col.align === "right" ? "right" : "left";
        td.innerHTML = cellValue(o, col.key);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }

  renderRows();
  return card;
}

// ── 전력: 현재 가동중 발전설비 구성 (EIA-860M Operating 스냅샷) ──
// 파이프라인(미래)이 아니라 지금 돌고 있는 설비의 스톡. 칩·검색 없이 정렬만 되는 요약표.
function renderPowerFleet(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";

  if (!doc || !doc.rows || doc.rows.length === 0) {
    card.innerHTML = `<div class="card-name">${doc?.name || "현재 가동중 발전설비 구성"}</div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      <code>scripts/aggregate_eia860m.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const filt = { sortKey: null, sortDir: -1 };

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">${doc.name}</span>
      <span class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></span>
    </div>`;
  card.appendChild(head);

  if (doc.note) {
    const note = document.createElement("div");
    note.className = "order-count";
    note.textContent = doc.note;
    card.appendChild(note);
  }

  const tableWrap = document.createElement("div");
  tableWrap.className = "order-table-wrap";
  card.appendChild(tableWrap);

  // 지표 JSON이 cols를 주면 그걸 쓴다(전력구역표 등). 없으면 설비 구성표 기본 컬럼.
  const COLS = doc.cols || [
    { key: "tech", label: "발전원" },
    { key: "gw", label: "용량(GW)", align: "right" },
    { key: "share", label: "비중", align: "right" },
    { key: "summer_gw", label: "여름피크(GW)", align: "right" },
    { key: "n", label: "기수", align: "right" },
    { key: "avg_year", label: "평균 준공", align: "right" },
    { key: "recent_share", label: "2020년 이후", align: "right" },
  ];
  const sortDefault = COLS.find((c) => c.align === "right");

  filt.sortKey = sortDefault ? sortDefault.key : null;

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  const ths = {};
  COLS.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    th.style.textAlign = col.align === "right" ? "right" : "left";
    th.classList.add("sortable");
    th.title = "클릭: 내림차순 → 오름차순 → 정렬 해제";
    th.addEventListener("click", () => { cycleSortState(filt, col.key); renderRows(); });
    ths[col.key] = th;
    htr.appendChild(th);
  });
  thead.appendChild(htr);
  const tbody = document.createElement("tbody");
  const tfoot = document.createElement("tfoot");
  table.append(thead, tbody, tfoot);
  tableWrap.appendChild(table);

  // 비중은 막대를 겹쳐 한눈에 크기 비교가 되게 한다(전체 대비 %).
  function cellHtml(r, key) {
    const col = COLS.find((c) => c.key === key);
    if (col && col.fmt) {
      const v = r[key];
      if (v == null) return "-";
      if (col.fmt === "int") return Number(v).toLocaleString("ko-KR");
      if (col.fmt === "pct") return `${Number(v).toFixed(1)}%`;
      return fmt(v);
    }
    if (key === "gw") return r.gw == null ? "-" : fmt(r.gw);
    if (key === "summer_gw") return r.summer_gw == null ? "-" : fmt(r.summer_gw);
    if (key === "n") return r.n.toLocaleString("ko-KR");
    if (key === "avg_year") return r.avg_year == null ? "-" : `${r.avg_year}년`;
    if (key === "recent_share") {
      if (r.recent_share == null) return "-";
      const cls = r.recent_share >= 50 ? "chg up" : "";
      return `<span class="${cls}">${r.recent_share.toFixed(1)}%</span>`;
    }
    if (key === "share") {
      // 스타일을 인라인으로 두는 이유: 이 막대 하나 때문에 style.css를 건드리지 않으려고.
      const w = Math.max(1, Math.round(r.share * 3));
      const bar = `display:inline-block;width:${w}px;height:8px;background:var(--accent);`
        + `opacity:.35;border-radius:2px;margin-right:5px;vertical-align:middle`;
      return `<span style="${bar}"></span><span>${r.share.toFixed(1)}%</span>`;
    }
    return r[key] || "-";
  }

  function updateSortIndicators() {
    COLS.forEach((col) => {
      const th = ths[col.key];
      th.classList.remove("sort-asc", "sort-desc");
      if (filt.sortKey === col.key && filt.sortDir !== 0) th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
    });
  }

  function renderRows() {
    const rows = doc.rows.slice();
    if (filt.sortKey) {
      rows.sort((a, b) => {
        const av = a[filt.sortKey], bv = b[filt.sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
      });
    }
    updateSortIndicators();

    tbody.innerHTML = "";
    for (const r of rows) {
      const tr = document.createElement("tr");
      COLS.forEach((col) => {
        const td = document.createElement("td");
        td.style.textAlign = col.align === "right" ? "right" : "left";
        td.innerHTML = cellHtml(r, col.key);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
    tfoot.innerHTML = doc.total_gw == null ? "" :
      `<tr><td><b>합계</b></td><td style="text-align:right"><b>${fmt(doc.total_gw)}</b></td>`
      + `<td style="text-align:right">100%</td><td></td>`
      + `<td style="text-align:right">${doc.total_n.toLocaleString("ko-KR")}</td><td></td><td></td></tr>`;
  }

  renderRows();
  return card;
}

// ── 전력: 구역 하나를 골라 그 안의 발전원 구성 보기 ──────────────
// 구역 선택 하나로 파이프라인·가동중·누적준공·누적은퇴 4개 차트를 동시에 갈아끼운다.
// (기관수급 탭의 종목 선택 뷰와 같은 패턴 — drawChart/buildChips 재사용)
function renderBADetail(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";

  if (!doc || !doc.bas || doc.bas.length === 0) {
    card.innerHTML = `<div class="card-name">${doc?.name || "전력구역별 발전원 구성"}</div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      <code>scripts/aggregate_eia860m.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">${doc.name}</span>
      <span class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></span>
    </div>`;
  card.appendChild(head);

  const picker = document.createElement("div");
  picker.className = "order-filters";
  const sel = document.createElement("select");
  sel.style.cssText = "padding:5px 8px;font-size:13px;border-radius:6px;"
    + "border:1px solid var(--baseline);background:var(--card);color:var(--ink);min-width:260px";
  doc.bas.forEach((b) => {
    const o = document.createElement("option");
    o.value = b.code;
    o.textContent = `${b.label} — ${b.live_gw.toLocaleString("ko-KR")} GW`;
    sel.appendChild(o);
  });
  picker.appendChild(sel);
  card.appendChild(picker);

  if (doc.note) {
    const n = document.createElement("div");
    n.className = "order-count";
    n.textContent = doc.note;
    card.appendChild(n);
  }

  // 4개 차트 그리드
  const grid = document.createElement("div");
  grid.className = "grid";
  grid.style.marginTop = "4px";
  card.appendChild(grid);

  const panes = doc.metrics.map((m) => {
    const box = document.createElement("div");
    box.className = "card";
    const title = document.createElement("div");
    title.className = "card-name";
    title.textContent = m.label;
    const stat = document.createElement("div");
    stat.className = "card-stat";
    const wrap = document.createElement("div");
    wrap.className = "chart-wrap";
    const canvas = document.createElement("canvas");
    wrap.appendChild(canvas);
    const chips = document.createElement("div");
    box.append(title, stat, wrap, chips);
    grid.appendChild(box);
    return { m, canvas, chips, stat, chart: null };
  });

  function show(code) {
    const entry = doc.data[code];
    if (!entry) return;
    panes.forEach((p) => {
      const series = entry[p.m.key] || {};
      const names = Object.keys(series);
      if (p.chart) p.chart.destroy();
      p.chips.innerHTML = "";
      if (names.length === 0) {
        p.stat.innerHTML = `<span class="stat-unit">해당 없음</span>`;
        return;
      }
      // 최신값 큰 순으로 정렬하고 상위 6개만 기본 표시(칩으로 나머지 토글)
      const ranked = names.slice().sort((a, b) =>
        series[b][series[b].length - 1][1] - series[a][series[a].length - 1][1]);
      const total = ranked.reduce((s, n) => s + series[n][series[n].length - 1][1], 0);
      p.stat.innerHTML = `<span class="stat-value">${fmt(total)}</span>`
        + `<span class="stat-unit">${p.m.unit} 합계</span>`;
      const pseudo = {
        name: p.m.label, unit: p.m.unit,
        default_series: ranked.slice(0, 6),
        series: Object.fromEntries(ranked.map((n) => [n, series[n]])),
      };
      p.chart = drawChart(p.canvas, pseudo, pseudo.series);
      buildChips(p.chips, p.chart);
    });
  }

  sel.addEventListener("change", () => show(sel.value));
  show(doc.bas[0].code);
  return card;
}

boot();

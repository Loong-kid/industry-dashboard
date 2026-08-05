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
  range: "1y",
  tableRange: {}, // 테이블(수주내역·오더북)별 독립 기간필터. indicator id → range. 전역 range와 분리
  charts: [], // 렌더된 Chart 인스턴스 (재렌더 시 destroy)
  docs: new Map(), // indicator id → data json 캐시
};

const darkMq = window.matchMedia("(prefers-color-scheme: dark)");
const isDark = () => darkMq.matches;
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// ── 부트스트랩 ──────────────────────────────────────────────────
async function boot() {
  state.catalog = await (await fetch("data/catalog.json")).json();
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

function route() {
  const id = location.hash.replace("#/", "") || state.catalog.industries[0].id;
  state.industry = state.catalog.industries.find((i) => i.id === id) || state.catalog.industries[0];
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.id === state.industry.id));
  renderIndustry();
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
async function renderIndustry() {
  const ind = state.industry;
  if (!ind) return;
  document.getElementById("page-title").textContent = `${ind.icon} ${ind.name}`;
  state.charts.forEach((c) => c.destroy());
  state.charts = [];

  const content = document.getElementById("content");
  content.innerHTML = "";

  let latestUpdate = "";
  for (const section of ind.sections) {
    const h = document.createElement("div");
    h.className = "section-title";
    h.textContent = section.title;
    content.appendChild(h);

    if (section.type === "table") {
      const renderer = section.table_kind === "asiasis" ? renderAsiasisTable
        : section.table_kind === "major_holdings" ? renderMajorHoldings
        : section.table_kind === "stock_trajectory" ? renderStockTrajectory
        : renderOrderTable;
      for (const indicatorId of section.indicators) {
        const doc = await loadDoc(ind.id, indicatorId);
        content.appendChild(renderer(doc));
        if (doc && doc.updated > latestUpdate) latestUpdate = doc.updated;
      }
      continue;
    }

    const grid = document.createElement("div");
    grid.className = "grid";
    content.appendChild(grid);

    for (const indicatorId of section.indicators) {
      const doc = await loadDoc(ind.id, indicatorId);
      grid.appendChild(renderCard(doc, indicatorId));
      if (doc && doc.updated > latestUpdate) latestUpdate = doc.updated;
    }
  }
  document.getElementById("last-updated").textContent = latestUpdate ? `데이터 갱신: ${latestUpdate}` : "";
}

async function loadDoc(industryId, indicatorId) {
  if (state.docs.has(indicatorId)) return state.docs.get(indicatorId);
  let doc = null;
  try {
    const url = `data/${industryId}/${indicatorId}.json` + (state.bust ? `?t=${state.bust}` : "");
    const res = await fetch(url);
    if (res.ok) doc = await res.json();
  } catch (e) { /* 파일 없음 → 빈 카드 */ }
  state.docs.set(indicatorId, doc);
  return doc;
}

// refresh.js가 갱신 완료 후 호출: 캐시 무효화 + 재렌더 (Pages CDN 우회용 캐시버스트)
async function reloadData() {
  state.bust = Date.now();
  state.docs.clear();
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
  const card = document.createElement("div");
  card.className = "card";

  if (!doc || !doc.series || Object.values(doc.series).every((s) => s.length === 0)) {
    const name = doc?.name || indicatorId;
    card.innerHTML = `
      <div class="card-head"><div class="card-name">${name}</div></div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      ${doc?.manual ? `<code>manual/</code> 폴더의 CSV에 값을 입력하면 표시됩니다.` : `페처 실행 후 표시됩니다.`}</div>`;
    return card;
  }

  const cutoff = rangeCutoff();
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
  head.innerHTML = `
    <div class="card-name">${doc.name}</div>
    <div class="card-freq">${{ daily: "일간", weekly: "주간", monthly: "월간" }[doc.frequency] || ""}${doc.manual ? " · 수기입력" : ""}</div>`;
  card.appendChild(head);

  // 헤드라인: 다중 시리즈 카드는 체크된 첫 시리즈를 따라감 (칩 토글 시 갱신)
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
    const delta = prev ? last[1] - prev[1] : null;
    const pct = prev && prev[1] !== 0 ? (delta / prev[1]) * 100 : null;
    const dir = delta > 0 ? "up" : delta < 0 ? "down" : "";
    const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "";
    stat.innerHTML = `
      ${seriesNames.length > 1 ? `<span class="stat-series">${seriesName}</span>` : ""}
      <span class="stat-value">${fmt(last[1])}</span>
      <span class="stat-unit">${doc.unit || ""}</span>
      ${delta !== null ? `<span class="stat-delta ${dir}">${arrow} ${fmt(Math.abs(delta))} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)</span>` : ""}
      <span class="stat-date">${last[0]}</span>`;
  };
  setStat(mainName);

  const wrap = document.createElement("div");
  wrap.className = "chart-wrap";
  const canvas = document.createElement("canvas");
  wrap.appendChild(canvas);
  card.appendChild(wrap);

  const chipsDiv = document.createElement("div");
  card.appendChild(chipsDiv);

  const foot = document.createElement("div");
  foot.className = "card-foot";
  foot.innerHTML = `
    <span>출처: ${doc.source_url ? `<a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a>` : doc.source || ""}</span>
    <button class="table-btn">표 보기</button>`;
  card.appendChild(foot);

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

function fmt(v) {
  if (v == null) return "-";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: Math.abs(v) < 1000 ? 2 : 0 });
}

function buildTable(doc, filtered) {
  const names = Object.keys(filtered);
  const dates = [...new Set(names.flatMap((n) => filtered[n].map((p) => p[0])))].sort().reverse().slice(0, 15);
  const map = {};
  for (const n of names) map[n] = Object.fromEntries(filtered[n]);
  let html = `<table><thead><tr><th>날짜</th>${names.map((n) => `<th>${n}</th>`).join("")}</tr></thead><tbody>`;
  for (const d of dates) {
    html += `<tr><td>${d}</td>${names.map((n) => `<td>${map[n][d] != null ? fmt(map[n][d]) : ""}</td>`).join("")}</tr>`;
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
  const labels = [...new Set(names.flatMap((n) => filtered[n].map((p) => p[0])))].sort();
  const idx = Object.fromEntries(labels.map((d, i) => [d, i]));

  const datasets = names.map((n, i) => {
    const data = new Array(labels.length).fill(null);
    for (const [d, v] of filtered[n]) data[idx[d]] = v;
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
      spanGaps: true,
      hidden: !visible.has(n),
    };
  });

  const chart = new Chart(canvas, {
    type: "line",
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
            label: (c) => ` ${c.dataset.label}: ${fmt(c.parsed.y)}${doc.unit ? " " + doc.unit : ""}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: css("--muted"),
            maxTicksLimit: 6, maxRotation: 0, autoSkip: true,
            font: { size: 11 },
          },
          grid: { display: false },
          border: { color: css("--baseline") },
        },
        y: {
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

// ── 기관 수급: 대량보유 공시 (major_holdings) ────────────────────
// 시장·보고자유형 칩 + 종목·보고자 컬럼필터. 기본은 '개인' 숨김.
function renderMajorHoldings(doc) {
  const card = document.createElement("div");
  card.className = "card order-table-card";

  if (!doc || !doc.orders || doc.orders.length === 0) {
    card.innerHTML = `<div class="card-name">${doc?.name || "대량보유 공시"}</div>
      <div class="card-empty">아직 데이터가 없습니다.<br>
      <code>fetch_major_holdings.py</code> → <code>aggregate_major_holdings.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const RENDER_CAP = 600;
  const markets = doc.markets || [...new Set(doc.orders.map((o) => o.market))];
  const types = doc.reporter_types || [...new Set(doc.orders.map((o) => o.reporter_type))];

  // 기본: 시장 전부 ON, 유형은 '개인'만 OFF(나머지 ON)
  const filt = {
    markets: new Set(markets),
    types: new Set(types.filter((t) => t !== "개인")),
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

  const marketChips = document.createElement("div");
  marketChips.className = "chips";
  filterBar.appendChild(marketChips);

  const typeChips = document.createElement("div");
  typeChips.className = "chips";
  filterBar.appendChild(typeChips);

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

  searchWrap.querySelector("input").addEventListener("input", (e) => {
    filt.search = e.target.value.trim().toLowerCase();
    renderRows();
  });

  function cellValue(o, key) {
    switch (key) {
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
    const allOrders = doc.orders.filter((o) => o.rcept_dt >= cutoff);
    const rows = allOrders.filter((o) => {
      if (!filt.markets.has(o.market)) return false;
      if (!filt.types.has(o.reporter_type)) return false;
      for (const key in filt.colFilters) {
        const q = filt.colFilters[key];
        if (q && !String(o[key] || "").toLowerCase().includes(q)) return false;
      }
      if (filt.search) {
        const hay = `${o.corp_name} ${o.reporter}`.toLowerCase();
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

  const withRt = (doc && doc.orders || []).filter((o) => o.stkrt != null);
  if (!withRt.length) {
    card.innerHTML = `<div class="card-name">종목별 지분 추이</div>
      <div class="card-empty">지분율 상세가 아직 없습니다.<br>
      <code>fetch_holding_details.py</code> → <code>aggregate_major_holdings.py</code> 실행 후 표시됩니다.</div>`;
    return card;
  }

  const byStock = new Map(); // corp_name → [orders]
  for (const o of withRt) {
    if (!byStock.has(o.corp_name)) byStock.set(o.corp_name, []);
    byStock.get(o.corp_name).push(o);
  }
  const stockNames = [...byStock.keys()].sort((a, b) => byStock.get(b).length - byStock.get(a).length);

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="order-head-left">
      <span class="card-name">종목별 지분 추이 (보고자별 보유비율)</span>
      <span class="card-freq">대량보유 보고 기준 · 상승=매집, 하락=매도</span>
    </div>`;
  card.appendChild(head);

  const picker = document.createElement("div");
  picker.className = "order-search";
  picker.style.margin = "8px 0 12px";
  const dlId = "stk-" + Math.random().toString(36).slice(2, 8);
  picker.innerHTML = `<input list="${dlId}" placeholder="종목명 입력·선택 (지분율 데이터 있는 종목)" />
    <datalist id="${dlId}">${stockNames.map((n) => `<option value="${n}"></option>`).join("")}</datalist>`;
  card.appendChild(picker);

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
    const rows = byStock.get(stock);
    if (!rows) return;
    pickerInput.value = stock; // 현재 보고 있는 종목 표시
    const series = {};
    for (const o of rows) (series[o.reporter] = series[o.reporter] || []).push([o.rcept_dt, o.stkrt]);
    for (const k in series) series[k].sort((a, b) => (a[0] < b[0] ? -1 : 1));
    const reporters = Object.keys(series);

    const pseudo = { name: stock, unit: "%", default_series: reporters, series };
    if (chart) chart.destroy();
    chart = drawChart(canvas, pseudo, series);
    chipsDiv.innerHTML = "";
    buildChips(chipsDiv, chart);

    const sum = reporters.map((r) => {
      const pts = series[r];
      const first = pts[0][1], last = pts[pts.length - 1][1];
      return { r, first, last, net: last - first, n: pts.length, lastDt: pts[pts.length - 1][0] };
    }).sort((a, b) => b.last - a.last);
    summary.style.display = "block";
    summary.innerHTML =
      `<table><thead><tr><th>보고자</th><th>최초</th><th>최신</th><th>순증감(%p)</th><th>보고</th><th>최근보고</th></tr></thead><tbody>` +
      sum.map((s) => `<tr><td>${s.r}</td><td>${s.first.toFixed(2)}%</td><td>${s.last.toFixed(2)}%</td>` +
        `<td class="${s.net > 0 ? "up" : s.net < 0 ? "down" : ""}">${s.net > 0 ? "+" : ""}${s.net.toFixed(2)}</td>` +
        `<td>${s.n}</td><td>${s.lastDt}</td></tr>`).join("") +
      `</tbody></table>`;
  }

  pickerInput.addEventListener("change", (e) => {
    const v = e.target.value.trim();
    if (byStock.has(v)) show(v);
  });
  show(stockNames[0]); // 기본: 보고 건수 많은 종목
  return card;
}

boot();

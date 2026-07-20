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
      for (const indicatorId of section.indicators) {
        const doc = await loadDoc(ind.id, indicatorId);
        content.appendChild(renderOrderTable(doc));
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
    const res = await fetch(`data/${industryId}/${indicatorId}.json`);
    if (res.ok) doc = await res.json();
  } catch (e) { /* 파일 없음 → 빈 카드 */ }
  state.docs.set(indicatorId, doc);
  return doc;
}

// ── 기간 필터 ───────────────────────────────────────────────────
function rangeCutoff() {
  if (state.range === "all") return "0000-00-00";
  const months = { "3m": 3, "1y": 12, "3y": 36 }[state.range];
  const d = new Date();
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
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

  const cutoff = rangeCutoff();
  const allOrders = doc.orders.filter((o) => o.rcept_dt >= cutoff);
  const companies = doc.companies || [...new Set(allOrders.map((o) => o.corp_name))];
  const categories = [...new Set(allOrders.map((o) => o.vessel_category))].sort();

  const filt = {
    companies: new Set(companies),
    categories: new Set(categories),
    search: "",
    sortKey: "rcept_dt",
    sortDir: -1,
  };

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="card-name">${doc.name}</div>
    <div class="card-freq">출처: <a href="${doc.source_url}" target="_blank" rel="noopener">${doc.source}</a></div>`;
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

  companies.forEach((c) => buildChip(companyChips, c, true, (on) => (on ? filt.companies.add(c) : filt.companies.delete(c))));
  categories.forEach((c) => buildChip(categoryChips, c, true, (on) => (on ? filt.categories.add(c) : filt.categories.delete(c))));

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
      case "amount_krw": return krwEok(o.amount_krw);
      case "per_vessel_usd": return usdM(o.per_vessel_usd);
      case "_link": return `<a href="${o.viewer_url}" target="_blank" rel="noopener">원문</a>`;
      default: return o[key] || "-";
    }
  }

  function renderRows() {
    const rows = allOrders.filter((o) => {
      if (!filt.companies.has(o.corp_name)) return false;
      if (!filt.categories.has(o.vessel_category)) return false;
      if (filt.search) {
        const hay = `${o.vessel_type} ${o.counterparty} ${o.contract_name}`.toLowerCase();
        if (!hay.includes(filt.search)) return false;
      }
      return true;
    });
    rows.sort((a, b) => {
      const av = a[filt.sortKey], bv = b[filt.sortKey];
      if (av == null) return 1;
      if (bv == null) return -1;
      return av > bv ? filt.sortDir : av < bv ? -filt.sortDir : 0;
    });

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
        if (filt.sortKey === col.key) th.classList.add(filt.sortDir > 0 ? "sort-asc" : "sort-desc");
        th.addEventListener("click", () => {
          filt.sortDir = filt.sortKey === col.key ? -filt.sortDir : -1;
          filt.sortKey = col.key;
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

boot();

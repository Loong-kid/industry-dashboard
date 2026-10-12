/* Industry-Based PPI Monitor: loaded only when the PPI tab is opened. */
const cache = new Map();
const prefs = {mode: "overview", sector: null, query: "", scope: "sector", period: "5Y", plot: "Level", top: 12, cols: 4,
  yoy: true, mom: true, months: 12, height: 1200, sort: "yoy", asc: false, selected: [], page: 0};
const colors = ["#2a78d6", "#1baf7a", "#eda100", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834", "#008300"];
export const title = s => (s.title || s.id).replace(/^(Producer Price Index by Industry: ?|PPI by Industry: )/, "");
export const matches = (s, query) => query.toLowerCase().trim().split(/\s+/).every(t => `${s.id} ${s.title}`.toLowerCase().includes(t));
export const shiftMonth = (date, offset) => {
  const n = Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7)) - 1 + offset;
  return `${Math.floor(n / 12)}-${String(n % 12 + 1).padStart(2, "0")}`;
};
export const change = (current, previous) => current != null && previous != null && previous !== 0 ? (current / previous - 1) * 100 : null;
export function stats(points, at = points.at(-1)?.[0]) {
  const values = new Map(points);
  const latest = values.get(at) ?? null;
  return {date: at, latest, yoy: at ? change(latest, values.get(shiftMonth(at, -12))) : null,
    mom: at ? change(latest, values.get(shiftMonth(at, -1))) : null};
}
export function transform(points, mode, period = "MAX", at = points.at(-1)?.[0]) {
  if (!at) return [];
  const cutoff = period === "MAX" ? "0000-01" : shiftMonth(at, -Number.parseInt(period) * 12);
  const values = new Map(points);
  const visible = points.filter(p => p[0] >= cutoff && p[0] <= at);
  const base = visible[0]?.[1];
  return visible.map(([date, value]) => [date, mode === "YoY %" ? change(value, values.get(shiftMonth(date, -12)))
    : mode === "MoM %" ? change(value, values.get(shiftMonth(date, -1)))
    : mode === "Indexed (=100)" ? (base ? value / base * 100 : null) : value]);
}
export function csvText(headers, rows) {
  const quote = v => `"${String(v ?? "").replaceAll('"', '""')}"`;
  return "\uFEFF" + [headers, ...rows].map(row => row.map(quote).join(",")).join("\r\n");
}
async function load(path, version = "") {
  const url = `data/ppi/${path}.json${version ? `?v=${encodeURIComponent(version)}` : ""}`;
  if (!cache.has(url)) {
    if (cache.size >= 96) cache.delete(cache.keys().next().value);
    cache.set(url, fetch(url).then(r => {
      if (!r.ok) throw new Error(`데이터를 불러오지 못했습니다 (HTTP ${r.status}).`);
      return r.json();
    }).catch(e => { cache.delete(url); throw e; }));
  }
  return cache.get(url);
}
const number = n => n == null || !Number.isFinite(n) ? "—" : n.toLocaleString("en-US", {maximumFractionDigits: 2});
const pct = n => n == null ? "—" : `${n > 0 ? "+" : ""}${number(n)}%`;
const element = (tag, className, text) => {
  const node = document.createElement(tag); if (className) node.className = className;
  if (text != null) node.textContent = text; return node;
};

export function mount(content) {
  let active = true, generation = 0, charts = [], timer, manifest, sectorData;
  const root = element("section", "ppi-monitor");
  const heading = element("h2", "", "📊 Industry-Based PPI Monitor");
  const caption = element("p", "ppi-caption", "카탈로그 불러오는 중…");
  const layout = element("div", "ppi-layout"), controls = element("aside", "ppi-controls"), body = element("div", "ppi-body");
  layout.append(controls, body); root.append(heading, caption, layout); content.append(root);
  const clearCharts = () => { charts.forEach(c => c.destroy()); charts = []; };
  const message = text => body.replaceChildren(element("p", "ppi-message", text));
  const button = (text, action, parent = controls) => {
    const b = element("button", "ppi-button", text); b.type = "button"; b.addEventListener("click", action); parent.append(b); return b;
  };
  const field = (text, input) => { const label = element("label", "ppi-field"); input.setAttribute("aria-label", text); label.append(element("span", "", text), input); controls.append(label); return input; };
  const select = (label, key, options, reset = false) => {
    const s = element("select");
    options.forEach(([value, text]) => { const o = element("option", "", text); o.value = value; s.append(o); });
    s.value = prefs[key]; field(label, s);
    s.addEventListener("change", () => { prefs[key] = s.value; if (reset) prefs.page = 0; draw(); }); return s;
  };
  const range = (label, key, min, max, step = 1, redrawControls = false) => {
    const input = element("input"); input.type = "range"; input.min = min; input.max = max; input.step = step; input.value = prefs[key];
    const value = element("output", "", String(prefs[key])); field(label, input).after(value);
    input.addEventListener("input", () => { prefs[key] = Number(input.value); value.textContent = input.value; });
    input.addEventListener("change", () => { prefs.page = 0; if (redrawControls) buildControls(); draw(); });
  };
  const checkbox = (label, key) => {
    const input = element("input"); input.type = "checkbox"; input.checked = prefs[key]; field(label, input);
    input.addEventListener("change", () => { prefs[key] = input.checked; draw(); });
  };
  function buildControls() {
    controls.replaceChildren();
    const modes = element("fieldset", "ppi-modes"); modes.append(element("legend", "", "보기 모드"));
    for (const [value, text] of [["overview", "Overview (그리드)"], ["detail", "Detail (개별 비교)"], ["table", "Table (스캐너)"]]) {
      const label = element("label"), input = element("input"); input.type = "radio"; input.name = "ppi-mode"; input.value = value; input.checked = prefs.mode === value;
      input.addEventListener("change", () => { prefs.mode = value; prefs.page = 0; history.replaceState(null, "", `#/ppi/${value}`); buildControls(); draw(); });
      label.append(input, document.createTextNode(text)); modes.append(label);
    }
    controls.append(modes);
    select("NAICS 섹터", "sector", manifest.sectors.map(s => [String(s.id), `${s.name} (${s.count.toLocaleString()})`]), true);
    if (prefs.mode === "detail") select("탐색 방식", "scope", [["sector", "트리 탐색"], ["all", "텍스트 검색 (전체 시리즈)"]], true);
    const query = element("input"); query.type = "search"; query.placeholder = "예: steel, cement, gasoline"; query.value = prefs.query;
    field("필터 (제목 / ID · 단어 AND 검색)", query);
    query.addEventListener("input", () => { prefs.query = query.value; prefs.page = 0; clearTimeout(timer); timer = setTimeout(draw, 180); });
    if (prefs.mode !== "table") {
      select("기간", "period", ["1Y", "3Y", "5Y", "10Y", "20Y", "MAX"].map(v => [v, v]));
      select("그래프 모드", "plot", ["Level", "YoY %", "MoM %", "Indexed (=100)"].map(v => [v, v]));
    }
    if (prefs.mode === "overview") {
      range("YoY / MoM 상위 N개", "top", 4, 24);
      select("열 개수", "cols", [2, 3, 4].map(v => [String(v), String(v)]));
      checkbox("YoY 상승률 상위 표시", "yoy"); checkbox("MoM 상승률 상위 표시", "mom");
    }
    if (prefs.mode === "table") {
      range("월별 컬럼 수", "months", 6, 36); range("테이블 높이 (px)", "height", 500, 3000, 100);
      const sort = select("정렬", "sort", [["yoy", "YoY %"], ["mom", "MoM %"], ["latest", "최신값"], ["title", "이름순"]], true);
      sort.addEventListener("change", () => { prefs.asc = prefs.sort === "title"; draw(); });
      checkbox("오름차순", "asc");
    }
    const info = element("details", "ppi-source"), summary = element("summary", "", "데이터 갱신 / 출처"); info.append(summary);
    info.append(element("p", "", `FRED 전체 이력 · 최근 관측월 ${manifest.data_through}`));
    info.append(element("p", "", `수집 ${new Date(manifest.updated).toLocaleString("ko-KR", {timeZone: "Asia/Seoul"})} (한국 시간)`));
    info.append(element("p", "", "매월 발표 기간과 매주 자동 갱신합니다. 상단 ‘PPI 갱신’으로 수동 갱신할 수 있습니다.")); controls.append(info);
  }
  function candidates() {
    return manifest.series.filter(s => (prefs.mode === "detail" && prefs.scope === "all" || s.category_ids.includes(Number(prefs.sector))) && matches(s, prefs.query))
      .sort((a, b) => (b.popularity || 0) - (a.popularity || 0) || title(a).localeCompare(title(b)));
  }
  function chart(parent, datasets, mini = false) {
    const frame = element("div", mini ? "ppi-chart-mini" : "ppi-chart-large"), canvas = element("canvas"); frame.append(canvas); parent.append(frame);
    const labels = [...new Set(datasets.flatMap(d => d.points.map(p => p[0])))].sort();
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (!window.Chart) { frame.textContent = "차트 라이브러리를 불러오지 못했습니다. 새로고침해 주세요."; return; }
    const instance = new window.Chart(canvas, {type: "line", data: {labels, datasets: datasets.map((d, i) => {
      const values = new Map(d.points); return {label: d.label, data: labels.map(date => values.get(date) ?? null), borderColor: colors[i % colors.length], borderWidth: mini ? 1.5 : 2, pointRadius: 0, spanGaps: false};
    })}, options: {responsive: true, maintainAspectRatio: false, animation: false, interaction: {mode: "index", intersect: false},
      plugins: {legend: {display: !mini, position: "bottom", labels: {color: dark ? "#ccc" : "#52514e"}}, tooltip: {callbacks: {label: c => `${c.dataset.label}: ${number(c.parsed.y)}`}}},
      scales: {x: {ticks: {maxTicksLimit: mini ? 3 : 10, color: dark ? "#aaa" : "#666", font: {size: mini ? 9 : 11}}, grid: {display: false}},
        y: {ticks: {maxTicksLimit: mini ? 4 : 8, color: dark ? "#aaa" : "#666"}, title: {display: !mini, text: prefs.plot, color: dark ? "#ccc" : "#52514e"}, grid: {color: dark ? "#333" : "#eee"}}}}});
    charts.push(instance);
  }
  function table(headers, rows, parent, onSort) {
    const wrap = element("div", "ppi-table-wrap"), t = element("table", "ppi-table"), head = element("thead"), tr = element("tr");
    headers.forEach((text, index) => { const th = element("th"); if (onSort) button(text, () => onSort(index), th); else th.textContent = text; tr.append(th); });
    head.append(tr); t.append(head); const tb = element("tbody");
    rows.forEach(row => { const r = element("tr"); row.forEach((value, i) => { const cell = element("td", "", typeof value === "number" ? number(value) : value ?? "—");
      if ((i === 3 || i === 4) && typeof value === "number") cell.className = value > 0 ? "ppi-rise" : value < 0 ? "ppi-fall" : ""; r.append(cell); }); tb.append(r); });
    t.append(tb); wrap.append(t); parent.append(wrap); return wrap;
  }
  async function overview(items, seq) {
    const ranked = items.map(s => ({s, ...stats(sectorData.series[s.id] || [], sectorData.data_through)}));
    for (const kind of ["yoy", "mom"]) {
      if (!prefs[kind]) continue;
      const top = ranked.filter(r => r[kind] != null).sort((a, b) => b[kind] - a[kind]).slice(0, prefs.top);
      body.append(element("h3", "", `${kind === "yoy" ? "🔥 YoY" : "⚡ MoM"} 상승률 상위 ${top.length}`));
      if (!top.length) { body.append(element("p", "ppi-message", "증감률을 계산할 데이터가 없습니다.")); continue; }
      const grid = element("div", "ppi-grid"); grid.style.setProperty("--ppi-cols", prefs.cols); body.append(grid);
      await Promise.all(top.map(async r => {
        const card = element("article", "ppi-mini-card"), link = element("a", "", title(r.s)); link.href = `https://fred.stlouisfed.org/series/${r.s.id}`; link.target = "_blank"; link.rel = "noopener";
        card.append(link, element("p", "ppi-caption", r.s.id), element("p", r[kind] > 0 ? "ppi-rise" : "ppi-fall", `${kind.toUpperCase()} ${pct(r[kind])}`)); grid.append(card);
        try { const doc = await load(`series/${r.s.id}`, manifest.updated); if (!active || seq !== generation) return;
          chart(card, [{label: title(r.s), points: transform(doc.points, prefs.plot, prefs.period, sectorData.data_through)}], true);
          card.append(element("p", "ppi-caption", `최신 ${number(r.latest)} · ${r.date}`));
        } catch (e) { if (active && seq === generation) card.append(element("p", "ppi-message", e.message)); }
      }));
      if (!active || seq !== generation) return;
    }
    if (!prefs.yoy && !prefs.mom) message("왼쪽에서 YoY 또는 MoM 표시를 켜 주세요.");
  }
  async function detail(items, seq) {
    const picker = element("div", "ppi-series-picker"), results = element("div", "ppi-series-results"), selected = element("div", "ppi-selected");
    picker.append(element("p", "ppi-caption", `검색 결과 ${items.length.toLocaleString()}개 · 최대 8개 비교 · 검색 결과 상위 200개 표시`), selected, results); body.append(picker);
    prefs.selected.forEach(id => { const s = manifest.series.find(s => s.id === id); button(`× ${title(s)}`, () => { prefs.selected = prefs.selected.filter(v => v !== id); draw(); }, selected); });
    for (const s of items.slice(0, 200)) {
      const label = element("label"), input = element("input"); input.type = "checkbox"; input.checked = prefs.selected.includes(s.id); input.disabled = !input.checked && prefs.selected.length >= 8;
      label.append(input, document.createTextNode(`${title(s)} (${s.id})`)); results.append(label);
      input.addEventListener("change", () => { prefs.selected = input.checked ? [...prefs.selected, s.id] : prefs.selected.filter(v => v !== s.id); draw(); });
    }
    if (!prefs.selected.length) { body.append(element("p", "ppi-message", "시리즈를 선택하면 최대 8개를 한 차트에서 비교할 수 있습니다.")); return; }
    const documents = await Promise.all(prefs.selected.map(async id => {
      try { return await load(`series/${id}`, manifest.updated); } catch (e) { return {id, points: [], error: e.message}; }
    }));
    if (!active || seq !== generation) return;
    const datasets = [], rows = [];
    const comparisonDate = documents.reduce((date, doc) => doc.points.at(-1)?.[0] > date ? doc.points.at(-1)[0] : date, "");
    for (const doc of documents) {
      const s = manifest.series.find(s => s.id === doc.id), st = stats(doc.points);
      if (!doc.points.length) body.append(element("p", "ppi-message", `${title(s)}: ${doc.error || "관측값 없음"}`));
      else datasets.push({label: `${title(s)} (${s.id})`, points: transform(doc.points, prefs.plot, prefs.period, comparisonDate)});
      rows.push([title(s), s.id, st.latest, st.yoy, st.mom, st.date, s.frequency]);
    }
    if (datasets.length) chart(body, datasets);
    body.append(element("h3", "", "📋 시리즈 요약")); table(["Title", "Code", "Latest", "YoY %", "MoM %", "Date", "Frequency"], rows, body);
    const details = element("details", "ppi-source"); details.append(element("summary", "", "선택된 시리즈 상세"));
    documents.forEach(doc => { const s = manifest.series.find(s => s.id === doc.id), p = element("p");
      const link = element("a", "", `${title(s)} (${s.id})`); link.href = `https://fred.stlouisfed.org/series/${s.id}`; link.target = "_blank"; link.rel = "noopener";
      p.append(link, document.createTextNode(` · ${s.units_short} · ${s.seasonal_adjustment_short} · ${doc.points[0]?.[0] || "—"} ~ ${doc.points.at(-1)?.[0] || "—"}`)); details.append(p); }); body.append(details);
  }
  function scanner(items) {
    const months = Array.from({length: prefs.months}, (_, i) => shiftMonth(sectorData.data_through, -i));
    const rows = items.map(s => { const points = sectorData.series[s.id] || [], st = stats(points, sectorData.data_through), values = new Map(points);
      return {s, id: s.id, ...st, values, title: title(s)}; }).filter(r => r.values.size);
    rows.sort((a, b) => {
      const av = prefs.sort.startsWith("month:") ? a.values.get(prefs.sort.slice(6)) : a[prefs.sort];
      const bv = prefs.sort.startsWith("month:") ? b.values.get(prefs.sort.slice(6)) : b[prefs.sort];
      if (av == null) return bv == null ? 0 : 1; if (bv == null) return -1;
      return (typeof av === "string" ? av.localeCompare(bv) : av - bv) * (prefs.asc ? 1 : -1);
    });
    const headers = ["Title", "Code", "Latest", "YoY %", "MoM %", ...months];
    const asRow = r => [r.title, r.s.id, r.latest, r.yoy, r.mom, ...months.map(m => r.values.get(m) ?? null)];
    body.append(element("h3", "", `${manifest.sectors.find(s => String(s.id) === prefs.sector).name} 스캐너`));
    body.append(element("p", "ppi-caption", `카탈로그 ${items.length.toLocaleString()} → 최근 관측값 ${rows.length.toLocaleString()}개 · 기준월 ${sectorData.data_through}`));
    button(`📥 CSV 다운로드 (${rows.length.toLocaleString()}행 · 필터·정렬 반영)`, () => {
      const url = URL.createObjectURL(new Blob([csvText(headers, rows.map(asRow))], {type: "text/csv;charset=utf-8"}));
      const a = element("a"); a.href = url; a.download = `ppi_${prefs.sector}_${sectorData.data_through}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, body);
    const pageSize = 100, pages = Math.max(1, Math.ceil(rows.length / pageSize)); prefs.page = Math.min(prefs.page, pages - 1);
    const pagination = element("div", "ppi-pagination");
    button("이전", () => { prefs.page--; draw(); }, pagination).disabled = prefs.page === 0;
    pagination.append(element("span", "", `${prefs.page + 1} / ${pages} 페이지 · ${rows.length.toLocaleString()}행`));
    button("다음", () => { prefs.page++; draw(); }, pagination).disabled = prefs.page >= pages - 1; body.append(pagination);
    const wrap = table(headers, rows.slice(prefs.page * pageSize, (prefs.page + 1) * pageSize).map(asRow), body, index => {
      const key = ["title", "id", "latest", "yoy", "mom"][index] || `month:${months[index - 5]}`;
      prefs.asc = prefs.sort === key ? !prefs.asc : key === "title" || key === "id"; prefs.sort = key; prefs.page = 0; draw();
    }); wrap.style.maxHeight = `${prefs.height}px`;
    body.append(element("p", "ppi-caption", "컬럼 제목을 눌러 정렬 · CSV에는 모든 페이지의 결과가 포함됩니다. 빈 관측값은 —로 표시합니다."));
    if (!rows.length) body.append(element("p", "ppi-message", "조건에 맞는 최근 관측값이 없습니다. 필터나 섹터를 바꿔 주세요."));
  }
  async function draw() {
    const seq = ++generation; clearCharts(); message("데이터 불러오는 중…");
    try {
      const items = candidates();
      if (prefs.mode !== "detail") sectorData = await load(`sectors/${prefs.sector}`, manifest.updated);
      if (!active || seq !== generation) return;
      body.replaceChildren();
      if (prefs.mode === "detail") await detail(items, seq);
      else { body.append(element("p", "ppi-caption", `카탈로그 매칭 ${items.length.toLocaleString()}개 · 최신 데이터 기준월 ${sectorData.data_through}`));
        if (prefs.mode === "table") scanner(items); else await overview(items, seq); }
    } catch (e) { if (active && seq === generation) { message(e.message); button("다시 불러오기", draw, body); } }
  }
  (async () => {
    try {
      manifest = await load("catalog", window.dashboard?.state?.bust ? String(window.dashboard.state.bust) : ""); if (!active) return;
      const hashMode = location.hash.split("/")[2]; if (["overview", "detail", "table"].includes(hashMode)) prefs.mode = hashMode;
      prefs.sector ||= String(manifest.sectors[0].id);
      caption.textContent = `FRED Producer Price Index by Industry · 카탈로그 ${manifest.series.length.toLocaleString()}개 시리즈 · 관측값 ${manifest.available.toLocaleString()}개 · 최근 관측월 ${manifest.data_through}`;
      buildControls(); draw();
    } catch (e) { if (active) { caption.textContent = "카탈로그 로딩 실패"; message(e.message); button("다시 불러오기", () => { cache.clear(); window.location.reload(); }, body); } }
  })();
  return () => { active = false; generation++; clearTimeout(timer); clearCharts(); };
}

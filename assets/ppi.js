/* Industry-Based PPI Monitor: loaded only when the PPI tab is opened. */
import {GROUPS, THEMES, classify, representatives, lifecycle, buildTree, rankIndustries, KIND_NAMES, themeRole} from "./ppi-classification.js";
const cache = new Map();
const prefs = {mode: "map", group: "all", sector: "all", status: "current", kind: "all", code: "", theme: "semiconductor",
  query: "", focusTheme: "", period: "5Y", plot: "YoY %", top: 12, cols: 4, yoy: true, mom: false, months: 12, height: 1200,
  sort: "yoy", asc: false, selected: [], page: 0, watch: new Set()};
const colors = ["#2a78d6", "#1baf7a", "#eda100", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834", "#008300"];
export const title = s => (s.title || s.id).replace(/^(Producer Price Index by Industry: ?|PPI by Industry: )/, "");
export const matches = (s, query) => query.toLowerCase().trim().split(/\s+/).every(t => `${s.id} ${s.title} ${s.label || ""}`.toLowerCase().includes(t));
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
export function yoyAcceleration(points, at) {
  const now = stats(points, at).yoy, previous = stats(points, shiftMonth(at, -1)).yoy;
  return now != null && previous != null ? now - previous : null;
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
export function indexedComparison(documents, period, at) {
  const cutoff = period === "MAX" ? "0000-01" : shiftMonth(at, -Number.parseInt(period) * 12);
  const valid = documents.filter(d => d.points.length);
  if (!valid.length) return {baseDate: null, points: []};
  const maps = valid.map(d => new Map(d.points));
  const baseDate = valid[0].points.map(p => p[0]).find(date => date >= cutoff && date <= at && maps.every(m => m.get(date) != null && m.get(date) !== 0));
  return {baseDate: baseDate || null, points: baseDate ? valid.map((doc, i) => ({id: doc.id, points: doc.points.filter(p => p[0] >= baseDate && p[0] <= at).map(([date, value]) => [date, value / maps[i].get(baseDate) * 100])})) : []};
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
  let active = true, generation = 0, charts = [], timer, manifest, navigation, records, representativeIds, sectorData;
  try { prefs.watch = new Set(JSON.parse(localStorage.getItem("industry_ppi_watchlist_v1") || "[]")); } catch { prefs.watch = new Set(); }
  const root = element("section", "ppi-monitor");
  const heading = element("h2", "", "📊 Industry-Based PPI Monitor");
  const caption = element("p", "ppi-caption", "카탈로그 불러오는 중…");
  const layout = element("div", "ppi-layout"), controls = element("aside", "ppi-controls"), body = element("div", "ppi-body");
  const options = element("details", "ppi-options"), optionsSummary = element("summary", "", "분류·보기 설정");
  const mobile = window.matchMedia("(max-width: 760px)"); options.open = !mobile.matches; options.append(optionsSummary, controls);
  const resizeOptions = e => { options.open = !e.matches; }; mobile.addEventListener("change", resizeOptions);
  const notice = element("p", "ppi-notice"); notice.setAttribute("role", "status"); notice.setAttribute("aria-live", "polite");
  layout.append(options, body); root.append(heading, caption, notice, layout); content.append(root);
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
    s.addEventListener("change", () => { prefs[key] = s.value; if (reset) { prefs.page = 0; prefs.code = ""; if (["group", "sector"].includes(key)) prefs.focusTheme = ""; } draw(); }); return s;
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
    for (const [value, text] of [["map", "대표 산업 지도"], ["themes", "관심 테마"], ["explore", "산업 계층 탐색"], ["detail", "Detail (개별 비교)"], ["table", "Table (전체 스캐너)"], ["ranking", "변화 탐지"], ["watchlist", "내 관심 목록"]]) {
      const label = element("label"), input = element("input"); input.type = "radio"; input.name = "ppi-mode"; input.value = value; input.checked = prefs.mode === value;
      input.addEventListener("change", () => switchMode(value));
      label.append(input, document.createTextNode(text)); modes.append(label);
    }
    controls.append(modes);
    if (prefs.mode !== "themes" && prefs.mode !== "watchlist") select("대분류", "group", [["all", "전체 대분류"], ...GROUPS.map(g => [g.id, `${g.name} (${records.filter(s => s.group === g.id).length.toLocaleString()})`])], true);
    if (["explore", "detail", "table", "ranking"].includes(prefs.mode)) {
      select("관측 상태", "status", [["current", "기준월 관측값 있음"], ["recent", "최근 3개월 관측값 있음"], ["all", "전체 이력 포함"], ["historical", "과거·공백 시리즈"]], true);
      select("NAICS 섹터", "sector", [["all", "전체 섹터"], ...manifest.sectors.map(s => [String(s.id), `${s.name} (${s.count.toLocaleString()})`])], true);
      if (prefs.mode !== "ranking") select("지표 종류", "kind", [["all", "전체 종류"], ...Object.entries(KIND_NAMES)], true);
    }
    if (prefs.mode === "themes") select("테마 선택", "theme", THEMES.map(t => [t.id, t.name]), true);
    const query = element("input"); query.type = "search"; query.placeholder = "예: steel, cement, gasoline"; query.value = prefs.query;
    field("필터 (제목 / ID · 단어 AND 검색)", query);
    query.addEventListener("input", () => { prefs.query = query.value; prefs.page = 0; clearTimeout(timer); timer = setTimeout(draw, 180); });
    if (["detail", "ranking"].includes(prefs.mode)) {
      select("기간", "period", ["1Y", "3Y", "5Y", "10Y", "20Y", "MAX"].map(v => [v, v]));
      select("그래프 모드", "plot", ["Level", "YoY %", "MoM %", "Indexed (=100)"].map(v => [v, v]));
    }
    if (prefs.mode === "ranking") {
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
    const guide = element("p", "ppi-caption", "미국 산업별 판매가격 · 도·소매는 유통 마진 · 계절조정 없음 (NSA). YoY를 기본으로 비교하고 MoM은 계절성에 유의해 확인하세요."); controls.append(guide);
  }
  function candidates() {
    return records.filter(s => {
      if (!matches(s, prefs.query)) return false;
      if (prefs.mode === "watchlist") return prefs.watch.has(s.id);
      if (prefs.mode === "themes") return s.themes.includes(prefs.theme);
      if (prefs.focusTheme && !s.themes.includes(prefs.focusTheme)) return false;
      if (prefs.group !== "all" && s.group !== prefs.group) return false;
      if (prefs.mode === "map") return representativeIds.has(s.id);
      if (prefs.sector !== "all" && !s.category_ids.includes(Number(prefs.sector))) return false;
      if (prefs.mode !== "ranking" && prefs.kind !== "all" && s.kind !== prefs.kind) return false;
      const status = lifecycle(navigation.latest_dates[s.id], manifest.data_through);
      return prefs.status === "all" || prefs.status === "recent" && status !== "historical" || prefs.status === status;
    })
      .sort((a, b) => (b.popularity || 0) - (a.popularity || 0) || title(a).localeCompare(title(b)));
  }
  function switchMode(mode, {code = "", theme = ""} = {}) {
    prefs.mode = mode; prefs.page = 0; prefs.code = code; prefs.focusTheme = theme; notice.textContent = "";
    history.replaceState(null, "", `#/ppi/${mode}${code ? `/${encodeURIComponent(code)}` : ""}`); buildControls(); draw();
  }
  function compare(s) {
    if (!prefs.selected.includes(s.id)) {
      if (prefs.selected.length >= 8) { notice.textContent = "최대 8개까지 비교할 수 있습니다. 비교 화면에서 기존 선택을 해제해 주세요."; return; }
      prefs.selected.push(s.id);
    }
    switchMode("detail");
  }
  function watch(s, parent) {
    const selected = prefs.watch.has(s.id);
    const b = button(selected ? "★" : "☆", () => {
      if (prefs.watch.has(s.id)) prefs.watch.delete(s.id); else prefs.watch.add(s.id);
      try { localStorage.setItem("industry_ppi_watchlist_v1", JSON.stringify([...prefs.watch])); }
      catch { notice.textContent = "이 브라우저에서 관심 목록을 저장할 수 없습니다. 현재 화면에서는 선택을 유지합니다."; }
      draw();
    }, parent);
    b.classList.add("ppi-watch"); b.setAttribute("aria-label", `${s.label} 관심 ${selected ? "해제" : "추가"}`); b.setAttribute("aria-pressed", String(selected));
  }
  function inspect(s) { prefs.group = s.group; prefs.sector = "all"; prefs.kind = "all"; prefs.status = navigation.latest_dates[s.id] === manifest.data_through ? "current" : "all"; prefs.query = ""; switchMode("explore", {code: s.code}); }
  async function recentData(items) {
    const sectors = [...new Set(items.flatMap(s => s.category_ids))];
    const docs = await Promise.all(sectors.map(id => load(`sectors/${id}`, manifest.updated)));
    const result = {data_through: manifest.data_through, series: {}};
    docs.forEach(doc => Object.assign(result.series, doc.series)); return result;
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
  function actions(s, parent, withInspect = true) {
    const wrap = element("span", "ppi-row-actions"); watch(s, wrap);
    button("비교", () => compare(s), wrap);
    if (withInspect) button("세부", () => inspect(s), wrap);
    parent.append(wrap);
  }
  function statusLabel(s) {
    const date = navigation.latest_dates[s.id], status = lifecycle(date, manifest.data_through);
    return status === "current" ? date : `${date || "관측값 없음"} · ${status === "lagged" ? "지연" : /DISCONTINUED/i.test(s.title) ? "종료 표기" : "과거·공백"}`;
  }
  async function heatmap(items, seq, {recent = false, headingText = "대표 산업 지도"} = {}) {
    body.append(element("h3", "", headingText));
    body.append(element("p", "ppi-caption", `${items.length.toLocaleString()}개 지표 · 기준월 ${manifest.data_through} · 최근 12개월 YoY · 빈 값은 —`));
    body.append(element("p", "ppi-caption", "대분류는 탐색용 묶음입니다. 지수들을 평균 내지 않고 각 공식 산업지수를 보여줍니다. ΔYoY는 전월 대비 전년비 변화폭(%p)입니다."));
    body.append(element("p", "ppi-caption ppi-scroll-hint", "표를 좌우로 스크롤하면 월별 변화와 비교·관심 버튼을 볼 수 있습니다."));
    if (!items.length) { body.append(element("p", "ppi-message", prefs.mode === "watchlist" ? "지표 옆 ☆를 눌러 관심 목록을 만들어 보세요. 이 브라우저에 저장됩니다." : "조건에 맞는 대표 지표가 없습니다. 검색어 또는 대분류를 바꿔 주세요.")); return; }
    let points;
    if (recent) {
      const data = await recentData(items); points = data.series;
    } else {
      const docs = await Promise.all(items.map(s => load(`series/${s.id}`, manifest.updated)));
      points = Object.fromEntries(docs.map(d => [d.id, d.points]));
    }
    if (!active || seq !== generation) return;
    const months = Array.from({length: 12}, (_, i) => shiftMonth(manifest.data_through, i - 11));
    const exportRows = [];
    for (const group of GROUPS) {
      const rows = items.filter(s => s.group === group.id).sort((a, b) => a.code.localeCompare(b.code));
      if (!rows.length) continue;
      const section = element("section", "ppi-heatmap-group"); section.dataset.group = group.id;
      section.append(element("h4", "", `${group.name} · ${rows.length}개`));
      const wrap = element("div", "ppi-table-wrap"), t = element("table", "ppi-table ppi-heatmap");
      const head = element("thead"), tr = element("tr");
      ["대표 산업 / 지표", "관측월", "YoY %", "ΔYoY %p", ...months, "보기"].forEach(label => tr.append(element("th", "", label)));
      head.append(tr); t.append(head); const tb = element("tbody");
      for (const s of rows) {
        const p = points[s.id] || [], st = stats(p, manifest.data_through), delta = yoyAcceleration(p, manifest.data_through);
        const r = element("tr"); r.dataset.series = s.id;
        const label = element("td"), name = button(s.label, () => inspect(s), label); name.classList.add("ppi-industry-link"); name.title = `${title(s)} (${s.id})`;
        label.append(element("span", "ppi-series-code", `${s.code} · ${prefs.mode === "themes" ? themeRole(s) : KIND_NAMES[s.kind]}`)); r.append(label, element("td", "ppi-date", statusLabel(s)));
        const growth = element("td", st.yoy > 0 ? "ppi-rise" : st.yoy < 0 ? "ppi-fall" : "", pct(st.yoy)); r.append(growth);
        r.append(element("td", delta > 0 ? "ppi-rise" : delta < 0 ? "ppi-fall" : "", delta == null ? "—" : `${delta > 0 ? "+" : ""}${number(delta)}`));
        const monthly = months.map(month => stats(p, month).yoy);
        monthly.forEach((value, i) => {
          const cell = element("td", "ppi-heat-cell", value == null ? "—" : number(value));
          if (value != null && value !== 0) cell.style.backgroundColor = `rgba(${value > 0 ? "214,39,40" : "36,149,67"},${Math.min(.35, .06 + Math.abs(value) / 100)})`;
          cell.title = `${months[i]} YoY ${pct(value)}`; r.append(cell);
        });
        const actionCell = element("td"); actions(s, actionCell); r.append(actionCell); tb.append(r);
        exportRows.push([group.name, s.label, s.id, navigation.latest_dates[s.id], st.yoy, delta, ...monthly]);
      }
      t.append(tb); wrap.append(t); section.append(wrap); body.append(section);
    }
    button("CSV 다운로드 (표시된 지표 전체)", () => downloadCsv(["Group", "Title", "Code", "Date", "YoY %", "Delta YoY pp", ...months], exportRows, `ppi_${prefs.mode}_${manifest.data_through}.csv`), body);
  }
  function downloadCsv(headers, rows, filename) {
    const url = URL.createObjectURL(new Blob([csvText(headers, rows)], {type: "text/csv;charset=utf-8"}));
    const a = element("a"); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function themeView(items, seq) {
    const theme = THEMES.find(t => t.id === prefs.theme);
    body.append(element("h3", "", theme.name), element("p", "ppi-theme-description", theme.description));
    body.append(element("p", "ppi-caption", "서로 다른 산업의 판매가격·재료·설비 지표를 함께 보는 참고 묶음입니다. 가격 차이를 이익률로 계산하지 않습니다."));
    const current = items.filter(s => s.kind === "industry" && navigation.latest_dates[s.id] === manifest.data_through);
    button("이 테마의 전체 시리즈 탐색", () => { prefs.group = "all"; prefs.sector = "all"; prefs.kind = "all"; prefs.status = "current"; switchMode("explore", {theme: theme.id}); }, body);
    await heatmap(current, seq, {recent: true, headingText: "테마의 현재 산업지수"});
    if (!active || seq !== generation) return;
    const past = items.filter(s => s.kind === "industry" && navigation.latest_dates[s.id] !== manifest.data_through);
    if (past.length) {
      const details = element("details", "ppi-past"); details.append(element("summary", "", `과거·지연 산업지수 ${past.length}개`));
      past.forEach(s => { const row = element("div", "ppi-tree-series"); row.append(element("span", "", `${s.label} · ${statusLabel(s)}`)); actions(s, row); details.append(row); }); body.append(details);
    }
  }
  function explorer(items) {
    const tree = buildTree(items, records);
    body.append(element("h3", "", "산업 계층 탐색"));
    body.append(element("p", "ppi-caption", `${items.length.toLocaleString()}개 시리즈 · 산업 코드의 상위·하위 관계와 세부 품목을 펼쳐 보세요. 산업 전체 / 주력제품 / 세부 품목을 구분합니다.`));
    if (prefs.focusTheme) {
      const t = THEMES.find(t => t.id === prefs.focusTheme); body.append(element("p", "ppi-caption", `테마 필터: ${t.name}`));
      button("테마 필터 해제", () => { prefs.focusTheme = ""; draw(); }, body);
    }
    let roots = tree.roots;
    if (prefs.code) {
      const node = tree.nodes.get(prefs.code); roots = node ? [node] : [];
      body.append(element("p", "ppi-breadcrumb", `${GROUPS.find(g => g.id === prefs.group)?.name || "전체 대분류"} / ${node?.industry?.label || prefs.code}`));
      button("대분류 전체로", () => { prefs.code = ""; draw(); }, body);
    }
    if (!roots.length) { body.append(element("p", "ppi-message", "조건에 맞는 산업이 없습니다. 관측 상태·지표 종류·검색어를 바꿔 주세요.")); return; }
    function nodeElement(node, open = false) {
      const d = element("details", "ppi-tree-node"), summary = element("summary"), children = element("div", "ppi-tree-children");
      d.dataset.code = node.code;
      summary.append(element("span", "ppi-tree-name", `${node.industry?.label || node.code}`), element("span", "ppi-tree-count", `${node.code} · ${node.count}개`)); d.append(summary, children);
      let built = false;
      const populate = () => {
        if (!d.open || built) return; built = true;
        const order = {industry: 0, primary: 1, product: 2, secondary: 3, misc: 4};
        node.series.sort((a, b) => order[a.kind] - order[b.kind] || a.id.localeCompare(b.id)).forEach(s => {
          const row = element("div", "ppi-tree-series"); row.dataset.series = s.id;
          const text = element("div"); text.append(element("span", "ppi-kind", KIND_NAMES[s.kind]), element("span", "", s.kind === "industry" ? "산업 전체 지수" : title(s)), element("small", "ppi-caption", `${s.id} · ${statusLabel(s)}`));
          row.append(text); actions(s, row, false); children.append(row);
        });
        node.children.forEach(child => children.append(nodeElement(child)));
      };
      d.addEventListener("toggle", populate); if (open) { d.open = true; populate(); } return d;
    }
    for (const group of GROUPS) {
      const nodes = roots.filter(n => n.group === group.id); if (!nodes.length) continue;
      const section = element("section", "ppi-tree-group"); section.append(element("h4", "", group.name)); nodes.forEach(n => section.append(nodeElement(n, Boolean(prefs.code)))); body.append(section);
    }
  }
  async function overview(items, seq) {
    if (items.length && items.every(s => s.group === "aggregate")) { body.append(element("p", "ppi-message", "산업 종합 지수는 대표 산업 지도에서 비교해 주세요. 변화 탐지는 개별 산업을 비교합니다.")); return; }
    const ranked = items.map(s => ({s, ...stats(sectorData.series[s.id] || [], sectorData.data_through)}));
    for (const kind of ["yoy", "mom"]) {
      if (!prefs[kind]) continue;
      const top = rankIndustries(ranked, kind, prefs.top);
      body.append(element("h3", "", `${kind === "yoy" ? "🔥 YoY" : "⚡ MoM"} 상승률 상위 ${top.length}`));
      if (!top.length) { body.append(element("p", "ppi-message", "증감률을 계산할 데이터가 없습니다.")); continue; }
      const grid = element("div", "ppi-grid"); grid.style.setProperty("--ppi-cols", prefs.cols); body.append(grid);
      await Promise.all(top.map(async r => {
        const card = element("article", "ppi-mini-card"), link = element("a", "", title(r.s)); link.href = `https://fred.stlouisfed.org/series/${r.s.id}`; link.target = "_blank"; link.rel = "noopener";
        card.append(link, element("p", "ppi-caption", `${r.s.label} · ${r.s.code}`), element("p", r[kind] > 0 ? "ppi-rise" : "ppi-fall", `${kind.toUpperCase()} ${pct(r[kind])}`)); actions(r.s, card); grid.append(card);
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
    button("전체 카탈로그에서 검색", () => { prefs.group = "all"; prefs.sector = "all"; prefs.kind = "all"; prefs.status = "all"; prefs.focusTheme = ""; buildControls(); draw(); }, body);
    const picker = element("div", "ppi-series-picker"), results = element("div", "ppi-series-results"), selected = element("div", "ppi-selected");
    picker.append(element("p", "ppi-caption", `검색 결과 ${items.length.toLocaleString()}개 · 최대 8개 비교 · 검색 결과 상위 200개 표시`), selected, results); body.append(picker);
    prefs.selected.forEach(id => { const s = records.find(s => s.id === id); button(`× ${s.label}`, () => { prefs.selected = prefs.selected.filter(v => v !== id); draw(); }, selected); });
    for (const s of items.slice(0, 200)) {
      const label = element("label"), input = element("input"); input.type = "checkbox"; input.checked = prefs.selected.includes(s.id); input.disabled = !input.checked && prefs.selected.length >= 8;
      label.append(input, document.createTextNode(`${s.label} (${s.id}) · ${KIND_NAMES[s.kind]} · ${statusLabel(s)}`)); results.append(label);
      input.addEventListener("change", () => { prefs.selected = input.checked ? [...prefs.selected, s.id] : prefs.selected.filter(v => v !== s.id); draw(); });
    }
    if (!prefs.selected.length) { body.append(element("p", "ppi-message", "시리즈를 선택하면 최대 8개를 한 차트에서 비교할 수 있습니다.")); return; }
    const documents = await Promise.all(prefs.selected.map(async id => {
      try { return await load(`series/${id}`, manifest.updated); } catch (e) { return {id, points: [], error: e.message}; }
    }));
    if (!active || seq !== generation) return;
    const datasets = [], rows = [];
    const comparisonDate = documents.reduce((date, doc) => doc.points.at(-1)?.[0] > date ? doc.points.at(-1)[0] : date, "");
    const indexed = prefs.plot === "Indexed (=100)" ? indexedComparison(documents, prefs.period, comparisonDate) : null;
    if (indexed) body.append(element("p", "ppi-caption", indexed.baseDate ? `모든 시리즈의 공통 기준월 ${indexed.baseDate} = 100` : "선택 기간에 공통 기준월이 없습니다. 기간을 늘리거나 비교 시리즈를 바꿔 주세요."));
    for (const doc of documents) {
      const s = records.find(s => s.id === doc.id), st = stats(doc.points);
      if (!doc.points.length) body.append(element("p", "ppi-message", `${title(s)}: ${doc.error || "관측값 없음"}`));
      else { const points = indexed ? indexed.points.find(d => d.id === doc.id)?.points : transform(doc.points, prefs.plot, prefs.period, comparisonDate);
        if (points) datasets.push({label: `${s.label} (${s.id})`, points}); }
      rows.push([title(s), s.id, st.latest, st.yoy, st.mom, st.date, s.frequency]);
    }
    if (datasets.length) chart(body, datasets);
    body.append(element("h3", "", "📋 시리즈 요약")); table(["Title", "Code", "Latest", "YoY %", "MoM %", "Date", "Frequency"], rows, body);
    const details = element("details", "ppi-source"); details.append(element("summary", "", "선택된 시리즈 상세"));
    documents.forEach(doc => { const s = records.find(s => s.id === doc.id), p = element("p");
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
    const label = prefs.sector !== "all" ? manifest.sectors.find(s => String(s.id) === prefs.sector)?.name : GROUPS.find(g => g.id === prefs.group)?.name || "전체 산업";
    body.append(element("h3", "", `${label} 스캐너`));
    body.append(element("p", "ppi-caption", `카탈로그 ${items.length.toLocaleString()} → 최근 관측값 ${rows.length.toLocaleString()}개 · 기준월 ${sectorData.data_through}`));
    button(`📥 CSV 다운로드 (${rows.length.toLocaleString()}행 · 필터·정렬 반영)`, () => {
      downloadCsv(headers, rows.map(asRow), `ppi_${prefs.group}_${prefs.sector}_${sectorData.data_through}.csv`);
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
      if (["table", "ranking"].includes(prefs.mode)) sectorData = await recentData(items);
      if (!active || seq !== generation) return;
      body.replaceChildren();
      if (prefs.mode === "map" || prefs.mode === "watchlist") await heatmap(items, seq, {headingText: prefs.mode === "map" ? "대표 산업 지도" : "내 관심 목록"});
      else if (prefs.mode === "themes") await themeView(items, seq);
      else if (prefs.mode === "explore") explorer(items);
      else if (prefs.mode === "detail") await detail(items, seq);
      else if (prefs.mode === "table") scanner(items);
      else { body.append(element("p", "ppi-caption", "산업 전체 지수만 비교합니다. 같은 중분류에서는 한 지표만 표시해 상위·하위 지수의 반복을 줄였습니다.")); await overview(items, seq); }
    } catch (e) { if (active && seq === generation) { message(e.message); button("다시 불러오기", draw, body); } }
  }
  (async () => {
    try {
      manifest = await load("catalog", window.dashboard?.state?.bust ? String(window.dashboard.state.bust) : ""); if (!active) return;
      navigation = await load("navigation", manifest.updated); if (!active) return;
      if (navigation.updated !== manifest.updated) throw new Error("분류와 관측값의 갱신 시점이 다릅니다. 잠시 후 다시 불러와 주세요.");
      records = manifest.series.map(classify);
      representativeIds = new Set(representatives(records, navigation.latest_dates, manifest.data_through).map(s => s.id));
      const hashMode = location.hash.split("/")[2];
      prefs.mode = hashMode === "overview" ? "ranking" : ["map", "themes", "explore", "detail", "table", "ranking", "watchlist"].includes(hashMode) ? hashMode : "map";
      if (prefs.mode === "explore" && location.hash.split("/")[3]) { const code = decodeURIComponent(location.hash.split("/")[3]); const s = records.find(s => s.code === code); if (s) { prefs.code = code; prefs.group = s.group; } }
      const current = records.filter(s => navigation.latest_dates[s.id] === manifest.data_through).length;
      caption.textContent = `12개 대분류 · 대표 ${representativeIds.size}개 · 전체 ${records.length.toLocaleString()}개 · 기준월 ${manifest.data_through} 관측 ${current.toLocaleString()}개`;
      buildControls(); draw();
    } catch (e) { if (active) { caption.textContent = "카탈로그 로딩 실패"; message(e.message); button("다시 불러오기", () => { cache.clear(); window.location.reload(); }, body); } }
  })();
  return () => { active = false; generation++; clearTimeout(timer); clearCharts(); mobile.removeEventListener("change", resizeOptions); };
}

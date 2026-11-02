/* 🛰️ DARPA 예산: 예산서(PB FY2016~) 프로그램을 산업 분야로 묶어 연도별 요청액·실적, 신규 프로그램을 본다.
   data/darpa/budget.json (scripts/build_darpa_budget.py) */
const SVGNS = "http://www.w3.org/2000/svg";
const prefs = {basis: "request", sort: "amount", sameScale: false, hideOverhead: false};

const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
function money(v) {
  if (v == null) return "–";
  const a = Math.abs(v);
  if (a >= 1000) return `$${(v / 1000).toFixed(2)}B`;
  if (a >= 10) return `$${Math.round(v).toLocaleString("en-US")}M`;
  return `$${v.toFixed(1)}M`;
}
const pct = v => v == null || !isFinite(v) ? "–" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
function cagr(series, from, to) {
  const a = series[from], b = series[to];
  if (!(a > 0) || b == null) return null;
  return Math.pow(b / a, 1 / (to - from)) - 1;
}

// 막대 차트(SVG): 4px 둥근 끝, 막대 사이 2px 이상 간격, 눈금은 최댓값 한 줄만.
function bars(values, years, {height = 92, width = 300, max, highlight, compact = true, tip, onPick, unit} = {}) {
  const pad = {l: 2, r: 2, t: 14, b: 16};
  const top = max ?? Math.max(1e-9, ...years.map(y => values[y] || 0));
  const slot = (width - pad.l - pad.r) / years.length, bw = Math.max(3, slot - (compact ? 3 : 5));
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.setAttribute("class", "dp-bars");
  svg.setAttribute("role", "img");
  const plotH = height - pad.t - pad.b;
  const base = document.createElementNS(SVGNS, "line");
  Object.entries({x1: pad.l, x2: width - pad.r, y1: pad.t + plotH, y2: pad.t + plotH, class: "dp-base"}).forEach(([k, v]) => base.setAttribute(k, v));
  svg.append(base);
  years.forEach((y, i) => {
    const v = values[y] || 0, h = top > 0 ? Math.max(v > 0 ? 1.5 : 0, (v / top) * plotH) : 0;
    const x = pad.l + i * slot + (slot - bw) / 2, yTop = pad.t + plotH - h, r = Math.min(4, bw / 2, h);
    const path = document.createElementNS(SVGNS, "path");
    path.setAttribute("d", `M${x},${pad.t + plotH} V${yTop + r} Q${x},${yTop} ${x + r},${yTop} H${x + bw - r} Q${x + bw},${yTop} ${x + bw},${yTop + r} V${pad.t + plotH} Z`);
    path.setAttribute("class", "dp-bar" + (y === highlight ? " dp-bar-on" : ""));
    svg.append(path);
    const hit = document.createElementNS(SVGNS, "rect");   // 막대보다 넓은 마우스 영역
    Object.entries({x: pad.l + i * slot, y: pad.t, width: slot, height: plotH + pad.b, class: "dp-hit"}).forEach(([k, val]) => hit.setAttribute(k, val));
    hit.dataset.year = y;
    if (tip) { hit.addEventListener("pointerenter", e => tip.show(e, y)); hit.addEventListener("pointermove", e => tip.move(e)); hit.addEventListener("pointerleave", () => tip.hide()); }
    if (onPick) hit.addEventListener("click", () => onPick(y));
    svg.append(hit);
    const showLabel = compact ? (i === 0 || i === years.length - 1 || y % 4 === 0) : true;
    if (showLabel) {
      const t = document.createElementNS(SVGNS, "text");
      t.setAttribute("x", x + bw / 2); t.setAttribute("y", height - 3); t.setAttribute("class", "dp-axis");
      t.textContent = compact ? `'${String(y).slice(2)}` : String(y).slice(2); svg.append(t);
    }
  });
  const label = document.createElementNS(SVGNS, "text");
  label.setAttribute("x", width - pad.r); label.setAttribute("y", 10); label.setAttribute("class", "dp-axis dp-max");
  label.textContent = `최대 ${unit ? top + unit : money(top)}`; svg.append(label);
  return svg;
}

export function mount(root) {
  root.innerHTML = `<div class="dp-root"><p class="page-loading">DARPA 예산 불러오는 중…</p></div>`;
  const box = root.querySelector(".dp-root");
  let disposed = false, doc = null, sectorSel = null, sectorYear = null, newYear = null, newSector = "all";
  const tipEl = document.createElement("div"); tipEl.className = "dp-tip"; tipEl.hidden = true;

  function tipFor(render) {
    return {
      show(e, y) { tipEl.innerHTML = render(y); tipEl.hidden = false; this.move(e); },
      move(e) {
        const r = box.getBoundingClientRect(), w = tipEl.offsetWidth;
        let x = e.clientX - r.left + 14; if (x + w > r.width) x = e.clientX - r.left - w - 14;
        tipEl.style.left = Math.max(0, x) + "px"; tipEl.style.top = (e.clientY - r.top + 14) + "px";
      },
      hide() { tipEl.hidden = true; },
    };
  }

  const years = () => doc.years[prefs.basis];
  const series = s => s[prefs.basis];
  const basisName = () => prefs.basis === "request" ? "요청액" : "실적";
  const lastYear = () => years().at(-1);
  const sectorName = id => doc.sectors.find(s => s.id === id)?.name || id;
  const progValue = (p, y) => p[prefs.basis][y] || 0;
  const newIn = (sid, y) => doc.programs.filter(p => p.new_fy === y && (sid === "all" || p.sector === sid));
  const visibleSectors = () => doc.sectors.filter(s => !(prefs.hideOverhead && (s.id === "classified" || s.id === "support")));

  function sortedSectors() {
    const L = lastYear(), rows = visibleSectors().slice();
    if (prefs.sort === "growth") return rows.sort((a, b) => (cagr(series(b), L - 3, L) ?? -9) - (cagr(series(a), L - 3, L) ?? -9));
    if (prefs.sort === "name") return rows.sort((a, b) => a.name.localeCompare(b.name, "ko"));
    return rows.sort((a, b) => (series(b)[L] || 0) - (series(a)[L] || 0));
  }

  function renderKpis() {
    const T = doc.totals[prefs.basis], ys = years(), L = ys.at(-1), F = ys[0];
    const newCount = doc.programs.filter(p => p.new_fy === L).length;
    const tiles = [
      [`FY${L} ${basisName()} 총액`, money(T[L]), prefs.basis === "request" ? "대통령 예산안(PB) 기준" : "의회 증액분 포함 집행액"],
      [`FY${L - 1} 대비`, pct(T[L] / T[L - 1] - 1), `FY${L - 1} ${money(T[L - 1])}`],
      [`FY${F}→${L} 연평균`, pct(cagr(T, F, L)), `${L - F}년간 ${money(T[F])} → ${money(T[L])}`],
      [`FY${L} 신규 프로그램`, `${newCount}개`, "그 해 처음 돈이 붙은 프로그램"],
    ];
    return `<div class="dp-kpis">${tiles.map(([k, v, s]) => `<div class="dp-kpi"><span>${esc(k)}</span><b>${esc(v)}</b><small>${esc(s)}</small></div>`).join("")}</div>`;
  }

  function renderCards() {
    const grid = box.querySelector("#dp-grid"); grid.innerHTML = "";
    const ys = years(), L = ys.at(-1), total = doc.totals[prefs.basis][L];
    const rows = sortedSectors();
    const shared = prefs.sameScale ? Math.max(...rows.flatMap(s => ys.map(y => series(s)[y] || 0))) : undefined;
    for (const s of rows) {
      const v = series(s), g3 = cagr(v, L - 3, L), share = total ? (v[L] || 0) / total : 0;
      const card = document.createElement("button");
      card.type = "button"; card.className = "dp-card" + (s.id === sectorSel ? " dp-card-on" : "");
      card.setAttribute("aria-pressed", String(s.id === sectorSel));
      card.innerHTML = `<span class="dp-card-head"><b>${esc(s.name)}</b><span class="dp-card-val">${money(v[L])}</span></span>
        <span class="dp-card-sub">비중 ${(share * 100).toFixed(1)}% · 3년 연평균 <em class="${g3 > 0 ? "dp-up" : g3 < 0 ? "dp-down" : ""}">${pct(g3)}</em></span>`;
      const tip = tipFor(y => {
        const n = newIn(s.id, y).length;
        return `<b>${esc(s.name)} · FY${y}</b><span>${basisName()} ${money(v[y] || 0)}</span>${prefs.basis === "request" ? `<span>프로그램 ${s.count[y] || 0}개 · 신규 ${n}개</span>` : ""}`;
      });
      card.append(bars(v, ys, {max: shared, highlight: L, tip}));
      card.addEventListener("click", () => openSector(s.id));
      // 너비 조절 손잡이가 버튼 안에 들어가지 않도록 감싼다.
      const item = document.createElement("div");
      item.className = "dp-card-wrap";
      item.append(card);
      grid.append(item);
    }
  }

  // firstYear: 신규 목록에서는 그 해 요청액 대신 첫해 금액(실적·추정 포함)을 보여 준다.
  function programRow(p, y, sectorTotal, firstYear) {
    const v = firstYear ? (p.first_amount || 0) : progValue(p, y), ys = years();
    const li = document.createElement("li"); li.className = "dp-prog";
    const det = document.createElement("details");
    det.innerHTML = `<summary><span class="dp-prog-main"><b>${esc(p.title)}</b>
        <small>${esc(sectorName(p.sector))}${p.new_fy ? ` · FY${p.new_fy} 신규` : ""}${p.first_fy && !p.new_fy ? ` · FY${p.first_fy} 이전부터` : ""}${p.last_fy && p.last_fy < lastYear() ? ` · FY${p.last_fy} 종료` : ""}</small></span>
      <span class="dp-prog-val">${money(v)}${sectorTotal ? `<small>${(v / sectorTotal * 100).toFixed(1)}%</small>` : ""}${firstYear ? `<small>첫해 · 최근 요청 ${money(p.request[doc.years.request.at(-1)] || 0)}</small>` : ""}</span></summary>`;
    const body = document.createElement("div"); body.className = "dp-prog-body";
    body.innerHTML = `${p.desc ? `<p>${esc(p.desc)}</p>` : `<p class="dp-muted">${p.kind === "classified" ? "기밀(SAP) 사업이라 내용은 공개되지 않는다. 금액만 예산서에 나온다." : p.kind === "adds" ? "대통령 요청에는 없고 의회가 추가로 배정한 금액(실적에만 나타난다)." : "세부 프로그램 설명 없이 프로젝트 금액만 나온다."}</p>`}
      <p class="dp-muted">프로젝트 ${esc(p.projects.join(", "))} · 예산서 FY${p.books[0]}~${p.books.at(-1)} 수록</p>`;
    const tip = tipFor(yy => `<b>FY${yy}</b><span>${basisName()} ${money(progValue(p, yy))}</span>`);
    body.append(bars(p[prefs.basis], ys, {height: 80, width: 560, highlight: y, compact: false, tip}));
    det.append(body); li.append(det);
    return li;
  }

  function openSector(id, keepYear) {
    sectorSel = id; if (!keepYear) sectorYear = lastYear();
    renderCards();
    const s = doc.sectors.find(x => x.id === id), panel = box.querySelector("#dp-detail");
    panel.hidden = false;
    const ys = years(), y = sectorYear, v = series(s);
    const progs = doc.programs.filter(p => p.sector === id && progValue(p, y) > 0).sort((a, b) => progValue(b, y) - progValue(a, y));
    const fresh = ys.map(yy => [yy, newIn(id, yy)]).filter(([, L]) => L.length).reverse();
    panel.innerHTML = `<div class="dp-detail-head"><h3>${esc(s.name)}</h3><p>${basisName()} 추이 — 막대를 누르면 그 해 프로그램 구성을 본다.</p>
      <button type="button" class="dp-close" aria-label="분야 상세 닫기">×</button></div>
      <div class="dp-detail-chart"></div>
      <div class="dp-detail-cols">
        <section><h4>FY${y} 프로그램 ${progs.length}개 <small>${money(v[y] || 0)}</small></h4><ol class="dp-prog-list" id="dp-sector-progs"></ol></section>
        <section><h4>연도별 신규 프로그램</h4>${fresh.length ? fresh.map(([yy, L]) => `<div class="dp-new-year"><b>FY${yy}</b> ${L.map(p => `<span class="dp-chip">${esc(p.acronym || p.title)}</span>`).join("")}</div>`).join("") : `<p class="dp-muted">이 기간 신규 없음</p>`}</section>
      </div>`;
    const tip = tipFor(yy => `<b>FY${yy}</b><span>${basisName()} ${money(v[yy] || 0)}</span>${prefs.basis === "request" ? `<span>프로그램 ${s.count[yy] || 0}개 · 신규 ${newIn(id, yy).length}개</span>` : ""}`);
    panel.querySelector(".dp-detail-chart").append(bars(v, ys, {height: 170, width: 760, highlight: y, compact: false, tip, onPick: yy => { sectorYear = yy; openSector(id, true); }}));
    const list = panel.querySelector("#dp-sector-progs");
    progs.slice(0, 30).forEach(p => list.append(programRow(p, y, v[y])));
    if (progs.length > 30) list.insertAdjacentHTML("beforeend", `<li class="dp-muted">외 ${progs.length - 30}개 — 아래 ‘프로그램 찾기’로 검색</li>`);
    panel.querySelector(".dp-close").addEventListener("click", () => { sectorSel = null; panel.hidden = true; renderCards(); });
    if (!keepYear) panel.scrollIntoView({behavior: "smooth", block: "start"});
  }

  function renderNew() {
    const ys = doc.years.request, sec = box.querySelector("#dp-new");
    newYear ??= ys.at(-1);
    const counts = Object.fromEntries(ys.map(y => [y, newIn(newSector, y).length]));
    const firstMoney = Object.fromEntries(ys.map(y => [y, newIn(newSector, y).reduce((a, p) => a + (p.first_amount || 0), 0)]));
    const rows = newIn(newSector, newYear).sort((a, b) => (b.first_amount || 0) - (a.first_amount || 0));
    const bySector = {};
    rows.forEach(p => (bySector[p.sector] ||= []).push(p));
    sec.querySelector(".dp-new-chart").replaceChildren(bars(counts, ys, {height: 120, width: 760, highlight: newYear, compact: false, unit: "개",
      tip: tipFor(y => `<b>FY${y} 신규</b><span>${counts[y]}개 · 첫해 ${money(firstMoney[y])}</span>`), onPick: y => { newYear = y; renderNew(); }}));
    sec.querySelector(".dp-new-years").innerHTML = ys.map(y => `<button type="button" data-y="${y}" aria-pressed="${y === newYear}">FY${String(y).slice(2)} <small>${counts[y]}</small></button>`).join("");
    sec.querySelectorAll(".dp-new-years button").forEach(b => b.addEventListener("click", () => { newYear = +b.dataset.y; renderNew(); }));
    const listBox = sec.querySelector(".dp-new-list");
    listBox.innerHTML = rows.length ? "" : `<p class="dp-muted">FY${newYear}에 새로 돈이 붙은 프로그램이 없다.</p>`;
    Object.entries(bySector).sort((a, b) => b[1].length - a[1].length).forEach(([sid, L]) => {
      const g = document.createElement("section"); g.className = "dp-new-group";
      g.innerHTML = `<h4>${esc(sectorName(sid))} <small>${L.length}개</small></h4>`;
      const ol = document.createElement("ol"); ol.className = "dp-prog-list";
      L.forEach(p => ol.append(programRow(p, newYear, null, true))); g.append(ol); listBox.append(g);
    });
  }

  function renderTable() {
    const ys = years(), rows = sortedSectors(), T = doc.totals[prefs.basis];
    const max = Math.max(...rows.flatMap(s => ys.map(y => series(s)[y] || 0)));
    box.querySelector("#dp-table").innerHTML = `<table class="dp-table"><caption>분야 × 연도 ${basisName()} (백만 달러)</caption>
      <thead><tr><th scope="col">분야</th>${ys.map(y => `<th scope="col">FY${String(y).slice(2)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(s => `<tr><th scope="row">${esc(s.name)}</th>${ys.map(y => {
        const v = series(s)[y] || 0;
        return `<td style="--h:${(v / max).toFixed(3)}">${v ? Math.round(v).toLocaleString("en-US") : "–"}</td>`;
      }).join("")}</tr>`).join("")}
      <tr class="dp-total"><th scope="row">합계</th>${ys.map(y => `<td>${Math.round(T[y]).toLocaleString("en-US")}</td>`).join("")}</tr></tbody></table>`;
  }

  function renderStages() {
    const ys = doc.years.request, wrap = box.querySelector("#dp-stages");
    wrap.innerHTML = "";
    const order = ["기초연구", "응용연구", "첨단기술개발", "관리·지원"];
    const shared = Math.max(...doc.budget_activity.flatMap(b => ys.map(y => b.request[y] || 0)));
    order.map(n => doc.budget_activity.find(b => b.name === n)).filter(Boolean).forEach(b => {
      const card = document.createElement("div"); card.className = "dp-stage";
      const L = ys.at(-1);
      card.innerHTML = `<span class="dp-card-head"><b>${esc(b.name)}</b><span class="dp-card-val">${money(b.request[L])}</span></span>
        <span class="dp-card-sub">비중 ${(b.request[L] / doc.totals.request[L] * 100).toFixed(1)}% · FY${ys[0]} ${money(b.request[ys[0]])}</span>`;
      card.append(bars(b.request, ys, {max: shared, highlight: L, tip: tipFor(y => `<b>${esc(b.name)} · FY${y}</b><span>요청액 ${money(b.request[y] || 0)}</span>`)}));
      wrap.append(card);
    });
  }

  function renderSearch() {
    const q = box.querySelector("#dp-q").value.trim().toLowerCase(), list = box.querySelector("#dp-results");
    list.innerHTML = "";
    if (q.length < 2) { box.querySelector("#dp-q-count").textContent = "두 글자 이상 입력 (예: hypersonic, QBI, 양자)"; return; }
    const hits = doc.programs.filter(p => [p.title, p.acronym, p.desc, sectorName(p.sector)].some(v => v && v.toLowerCase().includes(q)));
    box.querySelector("#dp-q-count").textContent = `${hits.length}개`;
    hits.slice(0, 40).forEach(p => list.append(programRow(p, lastYear())));
  }

  function renderAll() {
    box.querySelector("#dp-kpi-wrap").innerHTML = renderKpis();
    box.querySelectorAll("[data-basis]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.basis === prefs.basis)));
    box.querySelector("#dp-basis-note").textContent = prefs.basis === "request"
      ? `요청액: 그 해 대통령 예산안(PB)이 요청한 금액 (FY${doc.years.request[0]}~${doc.years.request.at(-1)})`
      : `실적: 2년 뒤 예산서에 실린 집행액, 의회 증액분 포함 (FY${doc.years.actual[0]}~${doc.years.actual.at(-1)})`;
    renderCards(); renderTable();
    if (sectorSel) openSector(sectorSel, true);
    renderSearch();
  }

  fetch(`data/darpa/budget.json?v=${Date.now()}`).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(d => {
    if (disposed) return;
    doc = d;
    const ys = doc.years.request;
    box.innerHTML = `
      <section class="dp-intro">
        <h2>DARPA는 어디에 돈을 거는가</h2>
        <p>미국 국방고등연구계획국(DARPA) 예산서 ${doc.books.length}권(PB FY${ys[0]}~FY${ys.at(-1)})의 프로그램 ${doc.programs.length}개를 산업 분야로 묶었다. 분야별 막대는 연도별 금액이고, 카드를 누르면 그 분야의 프로그램과 신규 사업이 열린다.</p>
      </section>
      <div id="dp-kpi-wrap"></div>
      <div class="dp-controls" role="group" aria-label="보기 설정">
        <div class="dp-seg" role="group" aria-label="금액 기준"><button type="button" data-basis="request">요청액</button><button type="button" data-basis="actual">실적</button></div>
        <label>정렬 <select id="dp-sort"><option value="amount">최근 금액순</option><option value="growth">3년 증가율순</option><option value="name">가나다순</option></select></label>
        <label class="dp-check"><input type="checkbox" id="dp-same"> 같은 눈금으로 비교</label>
        <label class="dp-check"><input type="checkbox" id="dp-hide"> 기밀·운영 빼기</label>
        <span id="dp-basis-note" class="dp-muted"></span>
      </div>
      <section class="dp-block"><h3>분야별 연도 추이</h3><div id="dp-grid" class="dp-grid"></div></section>
      <section id="dp-detail" class="dp-detail" hidden></section>
      <section class="dp-block" id="dp-new"><h3>연도별 신규 프로그램</h3>
        <p class="dp-muted">그 해 처음 금액이 붙은 프로그램. 막대·연도를 누르면 목록이 바뀐다.</p>
        <div class="dp-new-top"><div class="dp-new-chart"></div>
          <label>분야 <select id="dp-new-sector"><option value="all">전체</option>${doc.sectors.filter(s => s.id !== "classified" && s.id !== "support").map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("")}</select></label></div>
        <div class="dp-new-years" role="group" aria-label="연도"></div>
        <div class="dp-new-list"></div></section>
      <section class="dp-block"><h3>분야 × 연도 표</h3><div id="dp-table" class="dp-table-wrap" tabindex="0" role="region" aria-label="분야별 연도 금액 표, 가로 스크롤"></div></section>
      <section class="dp-block"><h3>연구 단계별 요청액</h3><p class="dp-muted">기초연구(6.1) → 응용연구(6.2) → 첨단기술개발(6.3). 뒤로 갈수록 실전 시제품에 가깝다. PB2026 개편으로 일부 사업이 단계를 옮겼다.</p><div id="dp-stages" class="dp-grid dp-grid-4"></div></section>
      <section class="dp-block"><h3>프로그램 찾기</h3>
        <label class="dp-search">제목·약어·설명·분야<input id="dp-q" type="search" autocomplete="off" placeholder="예: hypersonic, QBI, 반도체"></label>
        <p id="dp-q-count" class="dp-muted"></p><ol id="dp-results" class="dp-prog-list"></ol></section>
      <section class="dp-foot"><h3>읽는 법·출처</h3><ul>${doc.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul>
        <p class="dp-muted">출처: ${esc(doc.source)} — ${doc.books.map(b => `<a href="${esc(b.url)}" target="_blank" rel="noopener">FY${b.fy}</a>`).join(" · ")} (국방부 회계감사관 예산자료). 단위 ${esc(doc.unit)}.</p></section>`;
    box.append(tipEl);
    document.getElementById("last-updated").textContent = `DARPA 예산서 PB FY${ys.at(-1)} (${doc.books.at(-1).date || ""})`;
    box.querySelectorAll("[data-basis]").forEach(b => b.addEventListener("click", () => { prefs.basis = b.dataset.basis; renderAll(); }));
    const sort = box.querySelector("#dp-sort"); sort.value = prefs.sort;
    sort.addEventListener("change", () => { prefs.sort = sort.value; renderCards(); renderTable(); });
    const same = box.querySelector("#dp-same"); same.checked = prefs.sameScale;
    same.addEventListener("change", () => { prefs.sameScale = same.checked; renderCards(); });
    const hide = box.querySelector("#dp-hide"); hide.checked = prefs.hideOverhead;
    hide.addEventListener("change", () => { prefs.hideOverhead = hide.checked; renderCards(); renderTable(); });
    box.querySelector("#dp-new-sector").addEventListener("change", e => { newSector = e.target.value; renderNew(); });
    box.querySelector("#dp-q").addEventListener("input", renderSearch);
    renderAll(); renderNew(); renderStages();
  }).catch(err => {
    if (disposed) return;
    box.innerHTML = `<p class="page-loading">DARPA 예산을 불러오지 못했다 (${esc(err.message)}). 새로고침해 주세요.</p>`;
  });

  return () => { disposed = true; tipEl.remove(); };
}

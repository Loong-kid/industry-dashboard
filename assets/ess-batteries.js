/* Reviewed issuer history. Physical output and financial scope stay separate. */
function renderESSBatteries(doc, {view = "companies"} = {}) {
  const root = document.createElement("div");
  root.className = "ess-batteries";
  root.dataset.batteryView = view;
  if (!doc) return root;
  const physical = view === "physical";
  const eligible = doc.cards.filter(c => physical ? c.stage !== "finance" : c.stage === "finance");
  const available = doc.companies;
  state.essBatteryFilters ||= {};
  const filters = state.essBatteryFilters[view] ||= {company: "focus"};
  const esc = escapeHtml;
  root.innerHTML = `<p class="ir-scope-note">${physical ? "생산능력·실제 생산·판매·출하는 서로 다른 지표입니다. 공시된 제품 범위와 단위를 카드마다 표시합니다. 셀 개수를 GWh로 환산하지 않습니다." : esc(doc.description)} 검토일 ${esc(doc.reviewed)}.</p>
    <p class="ess-battery-rule">${esc(doc.note)}</p>
    <div class="ess-battery-controls">
      <label>기업 <select aria-label="ESS 배터리 ${physical ? "물량" : "재무"} 기업"><option value="focus">CATL + 국내 3사</option><option value="all">전체 ${available.length}개사</option>${available.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("")}</select></label>
      <span class="ess-battery-count" role="status" aria-live="polite"></span>
    </div>
    <div class="ess-battery-history"></div><div class="ess-battery-charts"></div>${physical ? "" : `<details class="ess-battery-coverage"><summary>10개사 사업 범위 · CAPA 공시 · 미공개 항목 비교</summary>
      <h3>배터리 제품 · 셀/모듈 미분리</h3><p class="ir-scope-note">CATL·EVE·REPT 등의 회사별 ESS 배터리 집계는 셀·모듈 등 제품 범위가 분리되지 않습니다. 확인된 판매·출하 이력은 위의 셀·모듈 추이에서 표시합니다.</p>
      <h3>시스템 · 모듈/컨테이너 조립</h3><p class="ir-scope-note">DC 컨테이너와 PCS·EMS가 포함된 완제품을 구분합니다. 이력 없는 CAPA·공급 계약은 차트에서 제외하며, 아래 비교표에는 공시 범위만 남깁니다.</p>
      <div class="order-table-wrap" tabindex="0" role="region" aria-label="ESS 배터리 기업 비교표 · 가로 스크롤">
        <table><caption>미공개·미분리는 0이 아닙니다. 시스템 판매량·CAPA와 셀 출하량·CAPA는 합산하지 않습니다.</caption>
          <thead><tr><th scope="col">기업</th><th scope="col">셀 / 시스템 사업</th><th scope="col">CAPA 범위</th><th scope="col">재무 공시 범위</th><th scope="col">검토 자료에서 미공개·미분리</th><th scope="col">공식 원문</th></tr></thead><tbody></tbody></table>
      </div>
    </details>`}`;
  const companySelect = root.querySelector("select");
  const area = root.querySelector(".ess-battery-charts");
  companySelect.value = ["all", "focus"].includes(filters.company) || available.some(c => c.id === filters.company) ? filters.company : "focus";
  const sourceLink = (point) => {
    const s = doc.sources[point.source];
    const page = point.pdf_page || s.pdf_page;
    return `<a href="${esc(s.url)}${page ? `#page=${page}` : ""}" target="_blank" rel="noopener" title="${esc(s.label)}${page ? ` · PDF ${page}쪽` : ""}">${esc(point.label)} ↗</a>`;
  };
  const draw = () => {
    // View buttons replace charts: destroy the current canvases owned by this group.
    const owned = state.charts.filter(chart => chart.canvas && area.contains(chart.canvas));
    owned.forEach(chart => chart.destroy());
    state.charts = state.charts.filter(chart => !owned.includes(chart));
    area.replaceChildren();
    const company = companySelect.value;
    filters.company = company;
    const accepts = id => company === "all" || (company === "focus" ? doc.focus_companies.includes(id) : id === company);
    const companies = available.filter(c => accepts(c.id));
    const rows = (doc.focus_history || []).filter(r => accepts(r.company) && r.kind === (physical ? "capacity" : "revenue"));
    const targets = physical ? (doc.focus_targets || []).filter(t => accepts(t.company)) : [];
    root.querySelector(".ess-battery-history").innerHTML = rows.length ? `<div class="order-table-wrap" tabindex="0" role="region" aria-label="ESS ${physical ? "생산능력" : "매출"} 연도별 공시 비교 · 가로 스크롤"><table>
      <caption>${esc(doc.focus_note)}</caption><thead><tr><th scope="col">기업 · 지표 / 단위</th>${[2021,2022,2023,2024,2025].map(y => `<th scope="col">${y}</th>`).join("")}<th scope="col">공시 범위</th></tr></thead>
      <tbody>${rows.map(r => `<tr data-history-company="${esc(r.company)}"><th scope="row">${esc(doc.companies.find(c => c.id === r.company).name)}<br>${esc(r.label)}${r.unit ? ` · ${esc(r.unit)}` : ""}</th>${Object.values(r.periods).map(p => `<td class="${p.status === "actual" ? "ess-history-actual" : "ess-history-gap"}">${sourceLink(p)}</td>`).join("")}<td>${esc(r.note)}</td></tr>`).join("")}</tbody></table></div>${targets.length ? `<details class="ess-battery-targets"><summary>증설 목표 · 실제 CAPA와 별도</summary><div class="order-table-wrap" tabindex="0"><table><thead><tr><th scope="col">기업 · 범위</th><th scope="col">목표 시점</th><th scope="col">목표 CAPA</th><th scope="col">발표 기준</th></tr></thead><tbody>${targets.map(t => `<tr><th scope="row">${esc(doc.companies.find(c => c.id === t.company).name)} · ${esc(t.label)}</th><td>${esc(t.target_period)}</td><td>${sourceLink({...t,label:t.value})}</td><td>${esc(t.note)}</td></tr>`).join("")}</tbody></table></div></details>` : ""}` : "";
    if (!physical) root.querySelector(".ess-battery-coverage tbody").innerHTML = companies.map(c => `<tr data-battery-company="${esc(c.id)}">
      <th scope="row">${esc(c.name)}</th><td>${esc(c.role)}</td><td>${esc(c.capacity_note)}</td><td>${esc(c.financial_note)}</td>
      <td>${c.gaps.map(esc).join("<br>")}</td><td>${c.sources.map(key => {
        const s = doc.sources[key]; return `<a href="${esc(s.url)}${s.pdf_page ? `#page=${s.pdf_page}` : ""}" target="_blank" rel="noopener">${esc(s.label)} ↗</a>`;
      }).join("<br>")}</td></tr>`).join("");
    const selected = eligible.filter(c => accepts(c.company));
    root.querySelector(".ess-battery-count").textContent = `${companies.length}개사 · ${selected.length}개 지표`;
    const groups = physical ? [["physical", null]] : companies.map(c => [c.id, c.name]);
    for (const [key,label] of groups) {
      const cards = physical ? selected : selected.filter(c => c.company === key);
      if (!cards.length) continue;
      const group = document.createElement("section");
      group.className = "ess-battery-group";
      group.dataset.group = key;
      if (label) { const heading = document.createElement("h3"); heading.textContent = label; group.appendChild(heading); }
      const grid = document.createElement("div"); grid.className = "grid";
      for (const cardDoc of cards) {
        const display = {...cardDoc, note: undefined, scope_summary: {label: doc.statuses[cardDoc.status], text: cardDoc.scope, detail: cardDoc.note}};
        if (Object.keys(display.series_views).length === 1) {
          Object.assign(display, Object.values(display.series_views)[0]);
          delete display.series_views;
        }
        const card = renderCard(display, cardDoc.id);
        card.dataset.batteryMetric = cardDoc.id;
        grid.appendChild(card);
      }
      group.appendChild(grid); area.appendChild(group);
    }
    if (!selected.length) {
      const empty = document.createElement("p"); empty.className = "ess-battery-empty";
      empty.textContent = "같은 기준으로 비교할 수 있는 공시 이력이 2개 기간 이상인 지표가 없습니다. 위의 연도별 표와 기업 비교표에서 확인된 공시 범위를 표시합니다.";
      area.appendChild(empty);
    }
  };
  companySelect.addEventListener("change", draw);
  draw();
  return root;
}

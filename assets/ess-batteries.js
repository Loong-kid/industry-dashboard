/* Reviewed issuer data. Cell output and system assembly never share a chart. */
function renderESSBatteries(doc) {
  const root = document.createElement("div");
  root.className = "ess-batteries";
  if (!doc) return root;
  const esc = escapeHtml;
  root.innerHTML = `<p class="ir-scope-note">${esc(doc.description)} 검토일 ${esc(doc.reviewed)}.</p>
    <p class="ess-battery-rule">${esc(doc.note)}</p>
    <div class="ess-battery-controls">
      <label>기업 <select aria-label="ESS 배터리 기업"><option value="all">전체 10개사</option>${doc.companies.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("")}</select></label>
      <label>지표 범위 <select aria-label="ESS 배터리 지표 범위"><option value="all">셀 · 배터리 · 시스템 · 재무 전체</option>${Object.entries(doc.stages).map(([key,label]) => `<option value="${esc(key)}">${esc(label)}</option>`).join("")}</select></label>
      <span class="ess-battery-count" role="status" aria-live="polite"></span>
    </div>
    <details class="ess-battery-coverage"><summary>10개사 사업 범위 · CAPA 공시 · 미공개 항목 비교</summary>
      <div class="order-table-wrap" tabindex="0" role="region" aria-label="ESS 배터리 기업 비교표 · 가로 스크롤">
        <table><caption>미공개·미분리는 0이 아닙니다. 시스템 판매량·CAPA는 셀 출하량·CAPA와 합산하지 않습니다.</caption>
          <thead><tr><th scope="col">기업</th><th scope="col">셀 / 시스템 사업</th><th scope="col">CAPA 범위</th><th scope="col">재무 공시 범위</th><th scope="col">검토 자료에서 미공개·미분리</th><th scope="col">공식 원문</th></tr></thead><tbody></tbody></table>
      </div>
    </details><div class="ess-battery-charts"></div>`;
  const [companySelect, stageSelect] = root.querySelectorAll("select");
  const area = root.querySelector(".ess-battery-charts");
  companySelect.value = state.essBatteryCompany || "all";
  stageSelect.value = state.essBatteryStage || "all";
  const draw = () => {
    // Series-view buttons can replace individual charts, so inspect current canvases.
    const owned = state.charts.filter(chart => chart.canvas && area.contains(chart.canvas));
    owned.forEach(chart => chart.destroy());
    state.charts = state.charts.filter(chart => !owned.includes(chart));
    area.replaceChildren();
    const company = companySelect.value, stage = stageSelect.value;
    state.essBatteryCompany = company;
    state.essBatteryStage = stage;
    const companies = doc.companies.filter(c => company === "all" || c.id === company);
    root.querySelector("tbody").innerHTML = companies.map(c => `<tr data-battery-company="${esc(c.id)}">
      <th scope="row">${esc(c.name)}</th><td>${esc(c.role)}</td><td>${esc(c.capacity_note)}</td><td>${esc(c.financial_note)}</td>
      <td>${c.gaps.map(esc).join("<br>")}</td><td>${c.sources.map(key => {
        const s = doc.sources[key]; return `<a href="${esc(s.url)}${s.pdf_page ? `#page=${s.pdf_page}` : ""}" target="_blank" rel="noopener">${esc(s.label)} ↗</a>`;
      }).join("<br>")}</td></tr>`).join("");
    const selected = doc.cards.filter(c => (company === "all" || c.company === company) && (stage === "all" || c.stage === stage));
    root.querySelector(".ess-battery-count").textContent = `${companies.length}개사 · ${selected.length}개 지표`;
    for (const [key,label] of Object.entries(doc.stages)) {
      const cards = selected.filter(c => c.stage === key);
      if (!cards.length) continue;
      const group = document.createElement("section");
      group.className = "ess-battery-group";
      group.dataset.stage = key;
      const heading = document.createElement("h3"); heading.textContent = label;
      const grid = document.createElement("div"); grid.className = "grid";
      for (const cardDoc of cards) {
        const display = {...cardDoc, note: undefined, scope_summary: {label: doc.statuses[cardDoc.status], text: cardDoc.scope, detail: cardDoc.note}};
        // A sole view needs no period selector; retain source and scope details.
        if (Object.keys(display.series_views).length === 1) {
          Object.assign(display, Object.values(display.series_views)[0]);
          delete display.series_views;
        }
        const card = renderCard(display, cardDoc.id);
        card.dataset.batteryMetric = cardDoc.id;
        grid.appendChild(card);
      }
      group.append(heading, grid); area.appendChild(group);
    }
    if (!selected.length) {
      const empty = document.createElement("p"); empty.className = "ess-battery-empty";
      empty.textContent = "선택한 범위의 정량 공시는 확인되지 않았습니다. 기업 비교표에서 미공개·미분리 항목을 확인하세요.";
      area.appendChild(empty);
    }
  };
  companySelect.addEventListener("change", draw);
  stageSelect.addEventListener("change", draw);
  draw();
  return root;
}

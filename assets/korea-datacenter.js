"use strict";

function dcElement(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text != null) el.textContent = String(text);
  return el;
}

function dcLink(url, label) {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) return dcElement("span", "", label);
    const a = dcElement("a", "", label);
    a.href = parsed.href; a.target = "_blank"; a.rel = "noopener noreferrer";
    return a;
  } catch { return dcElement("span", "", label); }
}

function dcDate(info) {
  if (!info?.text) return "—";
  const label = info.date || info.text;
  return label + (info.kind === "planned" ? " · 예정" : info.kind === "uncertain" ? " · 날짜 미확정" : "");
}

function dcStage(row) {
  const d = row.dates;
  if (d.completion.kind === "confirmed") return "준공";
  if (d.completion.text === "준공 완료") return "준공 · 날짜 미확인";
  if (d.start.kind === "confirmed") return "착공";
  if (d.alteration.kind === "confirmed") return "증축·대수선";
  if (d.start.kind === "planned") return "착공 예정";
  if (d.permit.kind === "confirmed") return "허가";
  return "일정 미확인";
}

function dcCard(doc, title) {
  const card = dcElement("div", "card order-table-card dc-card");
  card.appendChild(dcElement("div", "card-name", title || doc?.name || "국내 데이터센터"));
  if (!doc) card.appendChild(dcElement("p", "card-empty", "자료를 불러올 수 없습니다."));
  return card;
}

function renderKoreaDataCenterSummary(doc) {
  const card = dcCard(doc, "국내 데이터센터 추적 현황");
  if (!doc) return card;
  const summary = dcElement("div", "dc-summary");
  for (const [label, value] of [["기준 정리 목록", doc.summary.baseline_rows], ["확인된 센터·공사 단계", doc.summary.tracked_rows],
    ["검토 후보", doc.summary.candidate_rows], ["공식 자료로 보완한 항목", doc.summary.applied]]) {
    const item = dcElement("div", "dc-summary-item");
    item.append(dcElement("span", "card-freq", label), dcElement("strong", "", value.toLocaleString("ko-KR")));
    summary.appendChild(item);
  }
  card.appendChild(summary);
  card.appendChild(dcElement("p", "card-foot", `기준자료 ${doc.baseline.snapshot_date} · 공개 목록 확인 ${doc.collection_status?.checked || "미확인"} · 최신 공개일 ${doc.updated}`));
  card.appendChild(dcElement("p", "card-foot", "같은 센터의 증축·별도 허가·공사 단계가 포함됩니다. 전국 전체 시설 수가 아닌 추적 목록이며, 수전용량과 IT Load는 기존 정리 값을 유지합니다."));
  if (doc.collection_status) card.appendChild(dcElement("p", doc.collection_status.ok ? "card-foot" : "card-empty is-error", doc.collection_status.message));
  const details = dcElement("details", "dc-sources");
  details.appendChild(dcElement("summary", "", "수집 자료와 확인 범위"));
  for (const source of doc.manifest || []) {
    const p = dcElement("p", "card-foot", `${source.published} · ${source.title} · 날짜 확인 ${source.date_min || "미확인"}~${source.date_max || "미확인"} · `);
    p.appendChild(dcLink(source.url, "공개 목록")); details.appendChild(p);
  }
  details.appendChild(dcElement("p", "card-foot", "맞춤형 공개 자료는 요청에 따라 게시됩니다. 새 자료가 없으면 마지막 확인 기간을 유지하며, 미수집 기간을 0건으로 채우지 않습니다. 날짜의 확정은 원자료에 유효한 과거 날짜가 있다는 의미이며 실제 현장 공사 여부를 보증하지 않습니다."));
  card.appendChild(details);
  return card;
}

function renderKoreaDataCenters(doc) {
  const card = dcCard(doc);
  if (!doc) return card;
  const rows = doc.records || [];
  state.dcFilters ??= {classification: "confirmed", region: "", type: "", stage: "", search: "", sort: "permit", direction: -1};
  const filter = state.dcFilters;
  const controls = dcElement("div", "order-filters");
  const count = dcElement("p", "order-count");
  const wrap = dcElement("div", "order-table-wrap dc-table");
  const option = (parent, value, label) => { const o = dcElement("option", "", label); o.value = value; parent.appendChild(o); };
  const region = row => row.location.split(/\s+/)[0];
  function select(label, key, options) {
    const control = dcElement("label", "ti-filter", label);
    const input = dcElement("select"); input.setAttribute("aria-label", label);
    for (const [value, name] of options) option(input, value, name);
    input.value = filter[key];
    input.addEventListener("change", () => { filter[key] = input.value; renderRows(); });
    control.appendChild(input); controls.appendChild(control);
  }
  select("분류", "classification", [["confirmed", "확인 목록"], ["candidate", "검토 후보"], ["", "전체"]]);
  for (const [label, key, values] of [["지역", "region", rows.map(region)], ["건축구분", "type", rows.map(r => r.type)], ["상태", "stage", rows.map(dcStage)]]) {
    select(label, key, [["", "전체"], ...[...new Set(values)].filter(Boolean).sort().map(v => [v, v])]);
  }
  const searchWrap = dcElement("label", "order-search");
  const search = dcElement("input"); search.type = "search"; search.placeholder = "센터·주소·소유자·메모 검색";
  search.setAttribute("aria-label", "데이터센터 검색"); search.value = filter.search;
  search.addEventListener("input", () => { filter.search = search.value; renderRows(); });
  searchWrap.appendChild(search); controls.appendChild(searchWrap);
  card.append(controls, count, wrap);
  card.appendChild(dcElement("p", "card-foot", "센터명을 펼치면 기존 메모·참고 URL·연결된 원자료를 볼 수 있습니다. 검토 후보는 위 차트 집계에서 제외됩니다."));
  const columns = [["name", "센터명·메모"], ["location", "주소"], ["type", "건축구분"], ["stage", "진행 상태"],
    ["permit", "허가일"], ["start", "착공일"], ["alteration", "증축·대수선일"], ["completion", "준공일"],
    ["area", "연면적(㎡)"], ["capacity", "수전용량(MW)"], ["it_load", "IT Load"], ["owner", "소유자"], ["contractor", "시공사"]];
  function sortValue(row, key) {
    if (["permit", "start", "alteration", "completion"].includes(key)) return row.dates[key]?.date || null;
    if (key === "stage") return dcStage(row);
    return row[key] ?? null;
  }
  function renderRows() {
    wrap.replaceChildren();
    const q = filter.search.trim().toLocaleLowerCase();
    const selected = rows.filter(row => (!filter.classification || row.classification === filter.classification)
      && (!filter.region || region(row) === filter.region) && (!filter.type || row.type === filter.type)
      && (!filter.stage || dcStage(row) === filter.stage)
      && (!q || [row.name,row.location,row.owner,row.contractor,row.notes].join(" ").toLocaleLowerCase().includes(q)));
    selected.sort((a, b) => {
      const x = sortValue(a, filter.sort), y = sortValue(b, filter.sort);
      if (x == null || x === "") return y == null || y === "" ? a.id.localeCompare(b.id) : 1;
      if (y == null || y === "") return -1;
      return (typeof x === "number" ? x - y : String(x).localeCompare(String(y), "ko")) * filter.direction || a.id.localeCompare(b.id);
    });
    count.textContent = `${selected.length}개 센터·공사 단계 표시 / 전체 ${rows.length}개 · 용량 미확인 항목은 공란으로 표시`;
    const table = dcElement("table"), head = dcElement("thead"), tr = dcElement("tr"), body = dcElement("tbody");
    table.appendChild(dcElement("caption", "blind", "국내 데이터센터 센터·공사 단계별 현황"));
    for (const [key, label] of columns) {
      const th = dcElement("th"), button = dcElement("button", "dc-sort", label + (filter.sort === key ? filter.direction === -1 ? " ▼" : " ▲" : " ⇅"));
      th.setAttribute("scope", "col");
      if (filter.sort === key) th.setAttribute("aria-sort", filter.direction === -1 ? "descending" : "ascending");
      button.addEventListener("click", () => { filter.direction = filter.sort === key ? -filter.direction : -1; filter.sort = key; renderRows(); });
      th.appendChild(button); tr.appendChild(th);
    }
    head.appendChild(tr); table.append(head, body);
    for (const row of selected) {
      const tr = dcElement("tr");
      for (const [key] of columns) {
        const td = dcElement("td");
        if (key === "name") {
          const details = dcElement("details"), summary = dcElement("summary", "", row.name);
          details.appendChild(summary);
          details.appendChild(dcElement("p", "card-foot", `${row.origin === "baseline" ? "기준 정리자료" : "연결된 원자료"} · ${row.classification_reason}`));
          if (row.notes) details.appendChild(dcElement("p", "card-foot", row.notes));
          if (row.tenant) details.appendChild(dcElement("p", "card-foot", `이용자: ${row.tenant}`));
          for (const note of Object.values(row.cell_notes || {})) details.appendChild(dcElement("p", "card-foot", note));
          for (const [field, d] of Object.entries(row.original_dates || {})) details.appendChild(dcElement("p", "card-foot", `보완 전 ${columns.find(c => c[0] === field)?.[1] || field}: ${d.text || "미기재"}`));
          if (row.url) details.appendChild(dcLink(row.url, "기존 참고 자료 ↗"));
          for (const source of row.sources || []) {
            const p = dcElement("p", "card-foot", `${source.published} · ${source.title} `);
            if (source.url) p.appendChild(dcLink(source.url, "원자료 목록 ↗"));
            details.appendChild(p);
          }
          if (row.permit_ids?.length) details.appendChild(dcElement("p", "card-foot", `허가 식별자: ${row.permit_ids.join(", ")}`));
          td.appendChild(details);
        } else if (row.dates[key]) td.textContent = dcDate(row.dates[key]);
        else if (key === "stage") td.textContent = dcStage(row);
        else if (["area","capacity"].includes(key)) td.textContent = row[key] == null ? (key === "capacity" && row.capacity_text ? row.capacity_text : "—") : row[key].toLocaleString("ko-KR", {maximumFractionDigits: 2});
        else td.textContent = row[key] || "—";
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    if (!selected.length) { const tr = dcElement("tr"), td = dcElement("td", "", "조건에 맞는 데이터센터가 없습니다."); td.colSpan = columns.length; tr.appendChild(td); body.appendChild(tr); }
    wrap.appendChild(table);
  }
  renderRows();
  return card;
}

function renderKoreaDataCenterChanges(doc) {
  const card = dcCard(doc, "보완 내역 · 검토할 변경");
  if (!doc) return card;
  const info = dcElement("p", "card-foot", "기존 확정 날짜와 면적이 다르면 기준 값을 유지합니다. 빈 날짜·예정 날짜는 연결이 확실한 원자료로 보완하고 이전 표기를 남깁니다.");
  card.appendChild(info);
  const controls = dcElement("div", "order-filters"), label = dcElement("label", "ti-filter", "변경 분류"), select = dcElement("select");
  select.setAttribute("aria-label", "변경 분류");
  for (const [value, name] of [["review", "검토 필요"], ["applied", "보완 완료"], ["all", "전체"]]) {
    const option = dcElement("option", "", name); option.value = value; select.appendChild(option);
  }
  select.value = "review"; label.appendChild(select); controls.appendChild(label); card.appendChild(controls);
  const wrap = dcElement("div", "order-table-wrap"); card.appendChild(wrap);
  function render() {
    wrap.replaceChildren();
    const changes = (doc.changes || []).filter(c => select.value === "all" || c.applied === (select.value === "applied"));
    const table = dcElement("table"), head = dcElement("thead"), hr = dcElement("tr"), body = dcElement("tbody");
    for (const name of ["센터명","항목","기준 값","원자료 값","처리","출처"]) hr.appendChild(dcElement("th", "", name));
    head.appendChild(hr); table.append(head, body);
    const names = {permit:"허가일",start:"착공일",completion:"준공일",area:"연면적(㎡)",match:"매칭"};
    for (const c of changes) {
      const tr = dcElement("tr");
      for (const v of [c.name,names[c.field] || c.field,c.before,c.after,c.action]) tr.appendChild(dcElement("td", "", v));
      const td = dcElement("td");
      for (const s of c.sources || []) { const p = dcElement("p", "", `${s.published} · ${s.title} `); if (s.url) p.appendChild(dcLink(s.url, "목록")); td.appendChild(p); }
      tr.appendChild(td); body.appendChild(tr);
    }
    if (!changes.length) { const tr = dcElement("tr"), td = dcElement("td", "", "해당 변경 내역이 없습니다."); td.colSpan = 6; tr.appendChild(td); body.appendChild(tr); }
    wrap.appendChild(table);
  }
  select.addEventListener("change", render); render();
  return card;
}

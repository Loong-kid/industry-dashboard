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

const dcRoles = {owner: "소유자", developer: "시행사", project_company: "사업법인", operator: "운영사", client: "발주처", contractor: "시공사", tenant: "임차인"};
const dcFields = {permit: "허가일", start: "착공일", alteration: "증축·대수선", completion: "준공일", area: "연면적", match: "연결 후보"};
function dcProvenance(source) {
  return source.provenance === "user_raw" || source.id?.startsWith("baseline-") ? "사용자 엑셀 · Raw 탭" : source.provenance === "research" ? "기업·공공기관 조사" : "국토부 · 신규 다운로드";
}
function dcOwnerKnown(row) { return Boolean((row.owner && !["", "?", "미확인", "-"].includes(row.owner.trim())) || row.research?.stakeholders?.some(s => s.role === "owner")); }
function dcParty(row) {
  const parties = row.research?.stakeholders || [];
  const found = ["owner", "project_company", "developer", "client", "operator"].map(role => parties.find(s => s.role === role)).find(Boolean);
  return found ? {name: found.name, role: dcRoles[found.role]} : dcOwnerKnown(row) ? {name: row.owner, role: "기존 소유자", existing: true} : {name: "미확인", role: "소유자·사업주체"};
}
function dcDisplayStage(row) { return row.research?.update?.stage || dcStage(row); }
function dcIsActive(row) { const stage = dcDisplayStage(row); return !/^(운영|준공)/.test(stage) && /착공|허가|증축|대수선|공사|전환/.test(stage); }
function dcStorage(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }
function dcSave(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Read-only/private storage remains usable. */ } }

function dcDetail(row, trigger, reviews) {
  const dialog = dcElement("dialog", "dc-detail");
  dialog.setAttribute("aria-label", `${row.name} 상세 현황`);
  const heading = dcElement("div", "dc-dialog-heading"), close = dcElement("button", "dc-action", "닫기");
  close.type = "button"; heading.append(dcElement("h2", "", row.name), close); dialog.appendChild(heading);
  dialog.appendChild(dcElement("p", "dc-secondary", `${row.location} · ${row.type} · ${dcDisplayStage(row)}`));
  const section = title => { dialog.appendChild(dcElement("h3", "", title)); };
  const sourceLine = source => {
    const p = dcElement("p");
    p.appendChild(dcElement("span", "dc-provenance", `${dcProvenance(source)} · `));
    p.appendChild(dcElement("span", "", `${source.published || "게시일 미기재"} · `));
    p.appendChild(dcLink(source.url, source.title || "근거 자료"));
    dialog.appendChild(p);
  };
  section("소유자 · 사업주체");
  dialog.appendChild(dcElement("p", "", `기존 정리자료 소유자: ${row.owner || "미기재"}`));
  for (const s of row.research?.stakeholders || []) dialog.appendChild(dcElement("p", "", `${dcRoles[s.role] || s.role}: ${s.name}${s.note ? " · " + s.note : ""}`));
  if (!dcOwnerKnown(row)) dialog.appendChild(dcElement("p", "", "소유권은 미확인입니다. 시행사·운영사·발주처 확인과 구분합니다."));
  if (row.research) {
    dialog.appendChild(dcElement("p", "dc-secondary", `조사 확인 ${row.research.checked} · ${row.research.result || "근거 확인"}`));
    if (row.research.note) dialog.appendChild(dcElement("p", "", row.research.note));
    for (const source of row.research.sources || []) sourceLine(source);
  }
  if (row.research?.update) {
    section("추가로 확인한 현황");
    const u = row.research.update;
    dialog.appendChild(dcElement("p", "", `${u.as_of || "자료 기준일 미기재"} · ${u.text}`));
    dialog.appendChild(dcElement("p", "dc-secondary", "개장·보도된 진행 상황은 행정상 착공·사용승인 날짜와 별도로 관리합니다."));
  }
  section("행정 일정 · 규모");
  const dl = dcElement("dl");
  const values = [["허가", dcDate(row.dates.permit)], ["착공", dcDate(row.dates.start)], ["증축·대수선", dcDate(row.dates.alteration)], ["준공 / 사용승인", dcDate(row.dates.completion)],
    ["연면적", row.area == null ? "미확인" : row.area.toLocaleString("ko-KR") + " ㎡"], ["수전용량", row.capacity == null ? row.capacity_text || "미확인" : row.capacity + " MW"],
    ["IT Load", row.it_load || "미확인"], ["기존 시공사", row.contractor || "미기재"], ["기존 이용자", row.tenant || "미기재"]];
  for (const [label, value] of values) dl.append(dcElement("dt", "", label), dcElement("dd", "", value));
  dialog.appendChild(dl);
  for (const [field, d] of Object.entries(row.original_dates || {})) dialog.appendChild(dcElement("p", "dc-secondary", `보완 전 ${dcFields[field] || field}: ${d.text || "미기재"}`));
  if (reviews.length) {
    section("대조 시 검토할 항목");
    for (const c of reviews) {
      dialog.appendChild(dcElement("p", "", `${dcFields[c.field] || c.field} · 기준 ${c.before} → 원자료 ${c.after} · ${c.action}`));
      for (const source of c.sources || []) sourceLine(source);
    }
  }
  section("기존 메모 · 참고 자료");
  dialog.appendChild(dcElement("p", "", row.notes || "별도 메모 없음"));
  for (const note of Object.values(row.cell_notes || {})) dialog.appendChild(dcElement("p", "", note));
  if (row.url) dialog.appendChild(dcLink(row.url, "기존 참고 자료 ↗"));
  section("연결된 행정 자료");
  dialog.appendChild(dcElement("p", "dc-secondary", row.origin === "baseline" ? "사용자 엑셀 · 데이터센터(정리)" : row.classification_reason));
  for (const source of row.sources || []) sourceLine(source);
  if (row.permit_ids?.length) dialog.appendChild(dcElement("p", "dc-secondary", `허가 식별자: ${row.permit_ids.join(", ")}`));
  document.body.appendChild(dialog);
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { dialog.remove(); trigger?.focus(); });
  dialog.addEventListener("click", e => { if (e.target === dialog) { const b = dialog.getBoundingClientRect(); if (e.clientX < b.left || e.clientX > b.right || e.clientY < b.top || e.clientY > b.bottom) dialog.close(); } });
  dialog.showModal();
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
  if (doc.research_summary?.checked) {
    const r = doc.research_summary;
    card.appendChild(dcElement("p", "card-foot", `추가 조사 ${r.checked} · ${r.examined}개 행 대조 · ${r.stakeholders_found}개 행의 사업 관계자 확인 · ${r.status_updates}개 행의 별도 진행 현황 추가. 소유권을 확인하지 못한 항목은 미확인으로 유지합니다.`));
  }
  return card;
}

function renderKoreaDataCenters(doc) {
  const card = dcCard(doc);
  if (!doc) return card;
  card.className += " dc-monitor";
  const rows = doc.records || [];
  state.dcFilters ??= {...{classification: "confirmed", region: "", type: "", stage: "", search: "", sort: "permit", direction: -1, view: "overview", quick: "all", compact: false}, ...dcStorage("dc-monitor-view-v1", {})};
  const filter = state.dcFilters;
  filter.view ||= "overview"; filter.quick ||= "all";
  const favorites = new Set(dcStorage("dc-monitor-favorites-v1", []));
  const reviewMap = new Map();
  for (const change of doc.changes || []) if (!change.applied && change.facility_id) { if (!reviewMap.has(change.facility_id)) reviewMap.set(change.facility_id, []); reviewMap.get(change.facility_id).push(change); }
  const controls = dcElement("div", "order-filters dc-toolbar");
  const count = dcElement("p", "order-count");
  count.setAttribute("role", "status"); count.setAttribute("aria-live", "polite");
  const wrap = dcElement("div", "order-table-wrap dc-table");
  wrap.setAttribute("tabindex", "0"); wrap.setAttribute("aria-label", "센터별 현황 표, 가로로 스크롤할 수 있습니다");
  const option = (parent, value, label) => { const o = dcElement("option", "", label); o.value = value; parent.appendChild(o); };
  const region = row => row.location.split(/\s+/)[0];
  function select(label, key, options) {
    const control = dcElement("label", "ti-filter", label);
    const input = dcElement("select"); input.setAttribute("aria-label", label);
    for (const [value, name] of options) option(input, value, name);
    input.value = filter[key];
    input.addEventListener("change", () => { filter[key] = input.value; if (key === "view") filter.sort = "permit"; renderRows(); });
    control.appendChild(input); controls.appendChild(control);
  }
  select("분류", "classification", [["confirmed", "확인 목록"], ["candidate", "검토 후보"], ["", "전체"]]);
  for (const [label, key, values] of [["지역", "region", rows.map(region)], ["건축구분", "type", rows.map(r => r.type)], ["상태", "stage", rows.map(dcDisplayStage)]]) {
    select(label, key, [["", "전체"], ...[...new Set(values)].filter(Boolean).sort().map(v => [v, v])]);
  }
  select("표 보기", "view", [["overview", "핵심 현황"], ["schedule", "전체 일정·규모"], ["parties", "사업주체·조사 근거"]]);
  const searchWrap = dcElement("label", "order-search", "검색");
  const search = dcElement("input"); search.type = "search"; search.placeholder = "센터·주소·사업주체·메모";
  search.setAttribute("aria-label", "데이터센터 검색"); search.value = filter.search;
  search.addEventListener("input", () => { filter.search = search.value; renderRows(); });
  searchWrap.appendChild(search); controls.appendChild(searchWrap);
  const quick = dcElement("div", "dc-quick"), quickButtons = [];
  for (const [key, label] of [["all", "전체 현황"], ["active", "착공·허가"], ["missing", "소유자 미확인"], ["review", "대조 검토"], ["favorites", "관심 센터"]]) {
    const button = dcElement("button", "dc-action", label); button.type = "button";
    button.addEventListener("click", () => { filter.quick = key; renderRows(); }); quick.appendChild(button); quickButtons.push([key, button]);
  }
  const meta = dcElement("div", "dc-table-meta"), density = dcElement("button", "dc-action"); density.type = "button";
  density.addEventListener("click", () => { filter.compact = !filter.compact; renderRows(); }); meta.append(count, density);
  card.append(controls, quick, meta, wrap);
  card.appendChild(dcElement("p", "card-foot", "센터명을 누르면 일정·메모·조사 출처를 볼 수 있습니다. ☆ 관심 표시와 보기 설정은 이 브라우저에 저장됩니다. 소유자·사업법인·시행사·운영사를 구분합니다."));
  const columnsByView = {
    overview: [["name", "센터 · 소재지", 260], ["stage", "현황", 112], ["party", "소유자 / 사업주체", 172], ["permit", "허가일", 116], ["start", "착공일", 108], ["capacity", "수전 MW", 88], ["update", "추가 확인 · 검토", 180]],
    schedule: [["name", "센터 · 소재지", 260], ["stage", "현황", 112], ["permit", "허가일", 108], ["start", "착공일", 108], ["alteration", "증축·대수선", 116], ["completion", "준공 표기", 116], ["area", "연면적 ㎡", 110], ["capacity", "수전 MW", 88], ["it_load", "IT Load", 100]],
    parties: [["name", "센터 · 소재지", 260], ["stage", "현황", 112], ["party", "소유자 / 사업주체", 180], ["operator", "운영사", 150], ["contractor", "시공사", 150], ["update", "조사 결과 · 확인일", 244]]
  };
  function sortValue(row, key) {
    if (["permit", "start", "alteration", "completion"].includes(key)) return row.dates[key]?.date || null;
    if (key === "stage") return dcDisplayStage(row);
    if (key === "party") return dcParty(row).name === "미확인" ? null : dcParty(row).name;
    if (key === "update") return row.research?.checked || null;
    if (key === "operator") return row.research?.stakeholders?.find(s => s.role === "operator")?.name || null;
    if (key === "contractor") return row.research?.stakeholders?.find(s => s.role === "contractor")?.name || row.contractor || null;
    return row[key] ?? null;
  }
  function renderRows() {
    dcSave("dc-monitor-view-v1", {...filter, search: ""});
    card.className = "card order-table-card dc-card dc-monitor" + (filter.compact ? " is-compact" : "");
    density.textContent = filter.compact ? "행 간격: 촘촘" : "행 간격: 기본"; density.setAttribute("aria-pressed", String(Boolean(filter.compact)));
    for (const [key, button] of quickButtons) button.setAttribute("aria-pressed", String(filter.quick === key));
    wrap.replaceChildren();
    const columns = columnsByView[filter.view] || columnsByView.overview;
    const q = filter.search.trim().toLocaleLowerCase();
    const selected = rows.filter(row => (!filter.classification || row.classification === filter.classification)
      && (!filter.region || region(row) === filter.region) && (!filter.type || row.type === filter.type)
      && (!filter.stage || dcDisplayStage(row) === filter.stage)
      && (filter.quick !== "favorites" || favorites.has(row.id)) && (filter.quick !== "missing" || !dcOwnerKnown(row))
      && (filter.quick !== "review" || reviewMap.has(row.id))
      && (filter.quick !== "active" || dcIsActive(row))
      && (!q || [row.name,row.location,row.owner,row.contractor,row.notes,...(row.research?.stakeholders || []).map(s => s.name),row.research?.update?.text].join(" ").toLocaleLowerCase().includes(q)));
    selected.sort((a, b) => {
      const x = sortValue(a, filter.sort), y = sortValue(b, filter.sort);
      if (x == null || x === "") return y == null || y === "" ? a.id.localeCompare(b.id) : 1;
      if (y == null || y === "") return -1;
      return (typeof x === "number" ? x - y : String(x).localeCompare(String(y), "ko")) * filter.direction || a.id.localeCompare(b.id);
    });
    count.textContent = `${selected.length}개 표시 · 확인 목록 ${doc.summary?.tracked_rows ?? rows.length}개 · 센터·공사 단계 기준`;
    const table = dcElement("table"), head = dcElement("thead"), tr = dcElement("tr"), body = dcElement("tbody");
    table.appendChild(dcElement("caption", "blind", "국내 데이터센터 센터·공사 단계별 현황"));
    const colgroup = dcElement("colgroup");
    for (const width of [44, ...columns.map(c => c[2])]) { const col = dcElement("col"); col.setAttribute("width", width); colgroup.appendChild(col); } table.appendChild(colgroup);
    const watchHead = dcElement("th", "dc-watch-heading", "관심"); watchHead.setAttribute("scope", "col"); tr.appendChild(watchHead);
    for (const [key, label] of columns) {
      const th = dcElement("th"), button = dcElement("button", "dc-sort", label + (filter.sort === key ? filter.direction === -1 ? " ▼" : " ▲" : " ⇅"));
      button.setAttribute("data-sort", key);
      button.type = "button";
      if (["area", "capacity"].includes(key)) th.className = "dc-numeric";
      th.setAttribute("scope", "col");
      if (filter.sort === key) th.setAttribute("aria-sort", filter.direction === -1 ? "descending" : "ascending");
      button.addEventListener("click", () => { filter.direction = filter.sort === key ? -filter.direction : -1; filter.sort = key; renderRows(); wrap.querySelector?.(`[data-sort="${key}"]`)?.focus(); });
      th.appendChild(button); tr.appendChild(th);
    }
    head.appendChild(tr); table.append(head, body);
    for (const row of selected) {
      const tr = dcElement("tr");
      tr.setAttribute("data-id", row.id);
      const watchCell = dcElement("td"), watch = dcElement("button", "dc-watch", favorites.has(row.id) ? "★" : "☆"); watch.type = "button";
      watch.setAttribute("aria-label", `${row.name} 관심 센터`); watch.setAttribute("aria-pressed", String(favorites.has(row.id)));
      watch.addEventListener("click", () => { favorites.has(row.id) ? favorites.delete(row.id) : favorites.add(row.id); dcSave("dc-monitor-favorites-v1", [...favorites]); if (filter.quick === "favorites") renderRows(); else { watch.textContent = favorites.has(row.id) ? "★" : "☆"; watch.setAttribute("aria-pressed", String(favorites.has(row.id))); } });
      watchCell.appendChild(watch); tr.appendChild(watchCell);
      for (const [key] of columns) {
        const td = dcElement("td");
        if (key === "name") {
          const button = dcElement("button", "dc-name", row.name); button.type = "button";
          button.addEventListener("click", () => dcDetail(row, button, reviewMap.get(row.id) || []));
          td.append(button, dcElement("span", "dc-secondary", `${row.location} · ${row.type}`),
            dcElement("span", "dc-mobile-meta", `${dcDisplayStage(row)} · 허가 ${row.dates.permit.date || "미확인"} · 수전 ${row.capacity == null ? "미확인" : row.capacity + " MW"}`));
        } else if (row.dates[key]) td.textContent = dcDate(row.dates[key]);
        else if (key === "stage") { const label = dcDisplayStage(row), status = dcElement("span", "dc-status", label); status.setAttribute("data-stage", label.startsWith("운영") ? "운영" : label); td.appendChild(status); if (row.research?.update?.stage) td.appendChild(dcElement("span", "dc-secondary", `행정: ${dcStage(row)}`)); }
        else if (key === "party") { const party = dcParty(row); td.append(dcElement("span", "", party.name), dcElement("span", "dc-secondary", party.name === "미확인" ? "공개 근거 미확보" : party.role + (!party.existing && !dcOwnerKnown(row) ? " · 소유권 미확인" : ""))); }
        else if (key === "operator") td.textContent = row.research?.stakeholders?.filter(s => s.role === "operator").map(s => s.name).join(" · ") || "—";
        else if (key === "update") {
          const research = row.research, review = reviewMap.get(row.id);
          td.appendChild(dcElement("span", "", research?.update?.headline || (review ? `${review.length}개 대조 항목 검토` : research?.result || "추가 조사 전")));
          if (research) td.appendChild(dcElement("span", "dc-secondary", `조사 확인 ${research.checked}`));
          if (review && research?.update) td.appendChild(dcElement("span", "dc-secondary", `${review.length}개 대조 항목 검토`));
        }
        else if (["area","capacity"].includes(key)) { td.className = "dc-numeric"; td.textContent = row[key] == null ? (key === "capacity" && row.capacity_text ? row.capacity_text : "—") : row[key].toLocaleString("ko-KR", {maximumFractionDigits: 2}); }
        else if (key === "contractor") td.textContent = row.research?.stakeholders?.find(s => s.role === "contractor")?.name || row.contractor || "—";
        else td.textContent = row[key] || "—";
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    if (!selected.length) { const tr = dcElement("tr"), td = dcElement("td", "dc-empty", filter.quick === "favorites" ? "조건에 맞는 관심 센터가 없습니다. ☆를 눌러 관심 목록에 추가하세요." : "조건에 맞는 데이터센터가 없습니다. 검색어와 필터를 확인하세요."); td.colSpan = columns.length + 1; tr.appendChild(td); body.appendChild(tr); }
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
  card.appendChild(dcElement("p", "card-foot", "‘사용자 엑셀 · Raw 탭’은 구글 드라이브에 있던 Raw 탭과 데이터센터(정리)를 비교한 내역입니다. ‘국토부 · 신규 다운로드’는 이번 수집에서 직접 받은 공개 엑셀입니다."));
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
      for (const s of c.sources || []) { const p = dcElement("p", "", `${dcProvenance(s)} · ${s.published} · ${s.title} `); if (s.url) p.appendChild(dcLink(s.url, "목록")); td.appendChild(p); }
      tr.appendChild(td); body.appendChild(tr);
    }
    if (!changes.length) { const tr = dcElement("tr"), td = dcElement("td", "", "해당 변경 내역이 없습니다."); td.colSpan = 6; tr.appendChild(td); body.appendChild(tr); }
    wrap.appendChild(table);
  }
  select.addEventListener("change", render); render();
  return card;
}

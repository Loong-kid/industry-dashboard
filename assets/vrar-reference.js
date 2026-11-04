function node(tag, cls = "", text) {
  const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e;
}
function link(text, url) {
  const a = node("a", "", text);
  try { const u = new URL(url); if (!["https:", "http:"].includes(u.protocol)) return node("span", "", text); a.href = u.href; }
  catch { return node("span", "", text); }
  a.target = "_blank"; a.rel = "noopener noreferrer"; return a;
}
function region(label) {
  const wrap = node("div", "xrr-scroll"); wrap.tabIndex = 0; wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", label); return wrap;
}
function table(headers, cls = "") {
  const t = node("table", "xrr-table " + cls), head = node("thead"), row = node("tr");
  for (const h of headers) { const th = node("th", "", h); th.scope = "col"; row.append(th); }
  head.append(row); t.append(head); return t;
}
function definition(fields) {
  const dl = node("dl", "xrr-specs");
  for (const f of fields) { dl.append(node("dt", "", f.label + (f.column ? ` (${f.column}열)` : "")), node("dd", "", f.value || "—")); }
  return dl;
}
function detail(summary) { const d = node("details", "xrr-detail"); d.append(node("summary", "", summary)); return d; }
const money = value => value == null ? "미기재" : new Intl.NumberFormat("ko-KR", {maximumFractionDigits: 2}).format(value);
function price(record) {
  return record.price && /^\d/.test(record.price) ? "USD " + record.price : record.price || "—";
}

export function renderDevices(doc) {
  const root = node("section", "xrr-reference"); root.id = "vrar-device-tables";
  root.append(node("h2", "", "VR/AR 기기·부품 비교"), node("p", "xrr-intro", doc.description));
  const source = node("p", "xrr-source", `시트 반영 ${doc.fetched} · `); source.append(link("산업(VR)_밸류에이션", doc.source_url)); root.append(source);
  const controls = node("div", "xrr-controls"), choices = node("div", "xrr-choices"); choices.setAttribute("aria-label", "기기·부품 분류");
  const label = node("label", "xrr-maker-label", "제조사 "), select = node("select"); label.append(select);
  controls.append(choices, label); root.append(controls);
  const output = node("div"); root.append(output); let selected = doc.categories[0].id;
  function render(resetMaker = false) {
    const category = doc.categories.find(c => c.id === selected); if (!category) return;
    for (const button of choices.children) { const active = button.dataset.category === selected; button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active)); }
    if (resetMaker) {
      select.replaceChildren(node("option", "", "전체 제조사")); select.firstChild.value = "";
      for (const maker of [...new Set(category.rows.map(r => r.maker))]) { const option = node("option", "", maker); option.value = maker; select.append(option); }
    }
    const rows = category.rows.filter(r => !select.value || r.maker === select.value);
    output.replaceChildren(node("p", "xrr-count", `${category.title} · ${rows.length}개`));
    const wrap = region(category.title + " 사양 비교"), t = table(["제품 / 제조사", "시트 일정", "가격 (원문)", "무게", "칩·디스플레이 등 기재", "세부 사양", "출처"], "xrr-products");
    const body = node("tbody");
    for (const r of rows) {
      const row = node("tr"), model = node("th", "xrr-model", r.model); model.scope = "row"; model.append(node("small", "", r.maker + (r.variant ? " / " + r.variant : "")));
      const main = node("td", "xrr-device-main"); main.append(node("span", "", [r.chip, r.display].filter(Boolean).join(" / ") || "미기재"));
      const specs = node("td"), d = detail("사양 보기");
      d.append(definition(r.specs));
      for (const component of r.components) { d.append(node("h4", "", "보조칩 " + component.chip), definition(component.specs)); }
      for (const url of r.links) { const p = node("p"); p.append(link("시트에 연결한 참고 자료", url)); d.append(p); }
      if (!r.specs.length && !r.components.length) d.append(node("p", "", "제품명 외 사양은 시트에 미기재되어 있습니다."));
      specs.append(d); const original = node("td"); original.append(link("시트 행", r.source_url));
      row.append(model, node("td", "xrr-date", r.release || "—"), node("td", "xrr-price", price(r)), node("td", "", r.weight || "—"), main, specs, original); body.append(row);
    }
    t.append(body); wrap.append(t); output.append(wrap);
    if (category.notes.length) { const notes = detail("시트 메모"); for (const n of category.notes) { const p = node("p", "", n.text + " · "); p.append(link("원본", n.source_url)); notes.append(p); } output.append(notes); }
  }
  for (const c of doc.categories) { const b = node("button", "", `${c.title} ${c.rows.length}`); b.type = "button"; b.dataset.category = c.id; b.addEventListener("click", () => { selected = c.id; render(true); }); choices.append(b); }
  select.addEventListener("change", () => render()); render(true); return root;
}

function amount(row) {
  const td = node("td", "xrr-amount"); td.append(node("strong", "", row.amount_krw == null ? "미기재" : money(row.amount_krw / 1e6) + " 백만원"));
  if (row.amount_usd != null) td.append(node("small", "", "USD " + money(row.amount_usd))); return td;
}
function historyView(contract) {
  const d = detail(`이력 ${contract.history.length}건`), wrap = region("동일 계약 공시 이력"), t = table(["공시일", "원문", "공시 금액", "시작 / 종료", "정정 사유"], "xrr-history");
  const body = node("tbody");
  for (const r of [...contract.history].reverse()) {
    const tr = node("tr"), source = node("td"); source.append(link(r.title, r.url));
    tr.append(node("td", "xrr-date", r.filed), source, amount(r), node("td", "xrr-date", (r.start || "미기재") + " ~ " + (r.end || "미기재")), node("td", "xrr-history-reason", r.correction_reason || "최초 공시")); body.append(tr);
  }
  t.append(body); wrap.append(t); d.append(wrap);
  const latest = contract.latest, fields = detail("최신 공시 상세");
  fields.append(definition(Object.entries(latest.fields).map(([label, value]) => ({label: label.replaceAll("_", " / "), value})))); d.append(fields);
  return d;
}

export function renderContracts(doc) {
  const root = node("section", "xrr-reference"); root.id = "vrar-sapien-contracts";
  root.append(node("h2", "", "사피엔반도체 계약 공시 팔로업"), node("p", "xrr-intro", doc.description));
  const due = doc.contracts.filter(c => c.status_code === "due").length, elapsed = doc.contracts.filter(c => c.status_code === "elapsed").length;
  root.append(node("p", "xrr-source", `공시 확인 ${doc.checked} · 계약 ${doc.contracts.length}건 · 30일 내 종료 예정 ${due}건 · 종료일 경과 ${elapsed}건`));
  if (!doc.collection_status.ok) root.append(node("p", "xrr-review", "일부 공시 원문 확인이 필요합니다. 확인된 이력과 마지막 성공 자료를 유지합니다."));
  const wrap = region("사피엔반도체 최신 계약 조건과 시트 메모"), t = table(["최근 공시", "공시 계약 / 공식 상대방", "공시 계약금액", "기간 / 확인할 일정", "변경·공시 이력", "시트 메모·추정", "출처"], "xrr-contracts");
  const body = node("tbody");
  for (const c of doc.contracts) {
    const r = c.latest, row = node("tr"), when = node("td", "xrr-date", r.filed); if (r.is_correction) when.append(node("small", "xrr-revision", "정정 공시"));
    const contract = node("th", "xrr-contract-title", r.description); contract.scope = "row"; contract.append(node("small", "", r.counterparty));
    const period = node("td", "xrr-period"); period.append(node("span", "xrr-date", (r.start || "미기재") + " ~ " + (r.end || "미기재")), node("small", "xrr-status is-" + c.status_code, c.status));
    if (c.days_to_end != null && c.days_to_end >= 0) period.append(node("small", "", c.days_to_end === 0 ? "종료 예정일 오늘" : "종료 예정일까지 " + c.days_to_end + "일"));
    const changes = node("td", "xrr-change"); if (c.changed_fields.length) changes.append(node("p", "", c.changed_fields.join(" · ") + " 변경")); changes.append(historyView(c));
    const memo = node("td", "xrr-memo");
    if (!c.sheet_notes.length) memo.append(node("span", "", "시트 메모 없음"));
    for (const n of c.sheet_notes) {
      const d = detail(n.memo || "기존 시트 기재");
      d.append(node("p", "xrr-memo-label", "사용자 시트 메모 · 공식 거래처 실명 확인과 구분"));
      d.append(definition([{label: "시트 일정", value: `${n.start} ~ ${n.end}`}, {label: "시트 계약일 기재", value: n.sheet_date}, {label: "시트 상대방 기재", value: n.counterparty}, {label: "시트 금액 기재", value: `USD ${n.usd_display} / ${n.krw_million_display} 백만원`}, {label: "3년 동종계약 기재", value: n.same_type}]));
      d.append(link("시트 원본 행", n.source_url)); memo.append(d);
    }
    const sources = node("td", "xrr-links"); sources.append(link("최신 공시", r.url)); if (r.receipt !== c.original.receipt) sources.append(link("최초 공시", c.original.url));
    row.append(when, contract, amount(r), period, changes, memo, sources); body.append(row);
  }
  t.append(body); wrap.append(t); root.append(wrap);
  if (doc.unmatched_sheet_notes.length) { const notes = detail("공시 연결을 추가 확인할 시트 항목 " + doc.unmatched_sheet_notes.length + "건"); for (const n of doc.unmatched_sheet_notes) { const p = node("p", "", n.description + " / " + n.counterparty + " · "); p.append(link("시트 원본", n.source_url)); notes.append(p); } root.append(notes); }
  return root;
}

/* DART investment plans: current projects and separately inspectable amendments. */
export const money = value => value == null ? '미확인' : `${(value / 100000000).toLocaleString('ko-KR', {maximumFractionDigits: 2})}억원`;
const categoryMatch = (category, filter) => filter === 'all' || (filter === 'capacity' ? ['expansion', 'new_facility'].includes(category) : filter === category);
export function selectRows(doc, {view = 'projects', category = 'capacity', market = '', query = '', from = '', to = '', sort = 'date'} = {}) {
  const keyword = query.trim().toLocaleLowerCase();
  const projects = new Map(doc.projects.map(p => [p.id, p]));
  const rows = (view === 'changes' ? doc.changes : doc.projects).filter(row => {
    const p = view === 'changes' ? projects.get(row.project_id) : row;
    const date = view === 'changes' ? row.date : row.last_disclosed;
    return categoryMatch(row.category, category) && (!market || row.market === market) &&
      (!from || date >= from) && (!to || date <= to) &&
      (!keyword || [row.corp_name, row.stock_code, p?.investor, p?.target, p?.purpose, p?.investment_type, row.reason].join(' ').toLocaleLowerCase().includes(keyword));
  });
  return rows.sort((a, b) => sort === 'amount' ? (b.amount_krw ?? -1) - (a.amount_krw ?? -1) :
    sort === 'ratio' ? (b.equity_ratio ?? -1) - (a.equity_ratio ?? -1) :
    (b.last_disclosed || b.date || '').localeCompare(a.last_disclosed || a.date || '') || (b.id || b.rcept_no).localeCompare(a.id || a.rcept_no));
}
export function statusLabel(project, now) {
  if (project.record_status !== 'announced') return project.status_label;
  return project.end_date && project.end_date < now ? '예정일 경과 · 완료 미확인' : '공시 계획';
}
export function changesLabel(row) {
  return row.withdrawn ? '투자 철회' : row.changes.length ? row.changes.map(c => `${c.label}: ${c.field === 'amount_krw' ? money(c.before) : c.before || '미확인'} → ${c.field === 'amount_krw' ? money(c.after) : c.after || '미확인'}`).join(' / ') : row.reason || '기타 내용 정정';
}
function el(tag, value, cls) {
  const n = document.createElement(tag); if (value != null) n.textContent = value; if (cls) n.className = cls; return n;
}
function link(url, label) {
  const n = el('a', label);
  if (/^https:\/\/dart\.fss\.or\.kr\/dsaf001\/main\.do\?rcpNo=\d{14}$/.test(url || '')) { n.href = url; n.target = '_blank'; n.rel = 'noopener'; }
  return n;
}
function csvValue(v) {
  let text = String(v ?? ''); if (/^[=+@\-]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}
export function render(doc) {
  const root = el('section', null, 'expansion-root');
  const coverage = doc.coverage || {};
  root.append(el('p', '공장·생산라인의 증설 및 신설 공시를 모았습니다. 투자별 최신 계획과 정정 이력을 확인할 수 있습니다.', 'ex-intro'));
  root.append(el('p', `${coverage.from_date ? `시장 조회 ${coverage.from_date} ~ ${coverage.through_date}` : '초기 원문 표본 · 시장 전체 조회 준비 중'} · 원문 ${coverage.listed_receipts || 0}건 · 공시회사별 투자 ${doc.projects.length}건 · 수집 확인 ${doc.fetched || '미확인'}`, 'ex-coverage'));
  if (coverage.pending) root.append(el('p', `원문 확인·재수집 대기 ${coverage.pending}건이 있습니다. ‘확인 필요’ 분류에서 확인할 수 있습니다.`, 'ex-notice'));
  const criteria = el('details', null, 'ex-criteria'); criteria.append(el('summary', '수집 범위와 분류 기준'));
  for (const line of [
    '생산 증설: 투자구분·대상·목적에 생산능력 확대가 명시된 투자입니다. 신공장·신규사업 양산은 신설·신사업으로 구분합니다.',
    '증설과 노후설비 교체·비생산시설이 섞인 경우 또는 본문을 확인하지 못한 경우는 확인 필요로 남깁니다. 분류 근거와 투자목적 원문을 상세에서 제공합니다.',
    '금액은 공시된 총 투자계획액입니다. 분기별 실제 CAPEX가 아니며, 완료 예정일이 지나도 준공으로 처리하지 않습니다. 생산능력 증가량은 공시에 기재된 경우에만 표시합니다.',
    '공식 공시 연결 관계로 같은 공시회사의 원공시와 정정본을 묶습니다. 모회사·자회사가 같은 투자를 각각 공시할 수 있어 전체 금액을 단순 합산하지 않습니다.',
    '조회기간 밖의 원공시도 정정 관계 확인에 필요한 경우 함께 수집합니다. 개별 공시되지 않은 투자는 포함하지 않습니다.',
  ]) criteria.append(el('p', line)); root.append(criteria);
  const tabs = el('div', null, 'ex-tabs'); tabs.setAttribute('role', 'group'); tabs.setAttribute('aria-label', '증설 투자 보기');
  const views = [['projects', '투자목록'], ['changes', '변경이력']];
  const controls = el('div', null, 'ex-controls');
  const makeSelect = (label, options) => {
    const holder = el('label'); holder.append(el('span', label)); const s = el('select'); s.setAttribute('aria-label', label);
    options.forEach(([v, t]) => { const o = el('option', t); o.value = v; s.append(o); }); holder.append(s); controls.append(holder); return s;
  };
  const category = makeSelect('투자 분류', [['capacity', '증설·신설'], ['expansion', '생산 증설'], ['new_facility', '신설·신사업'], ['review', '확인 필요'], ['excluded', '기타 시설투자'], ['all', '전체 원문']]);
  const market = makeSelect('시장', [['', '전체'], ['코스피', '코스피'], ['코스닥', '코스닥']]);
  const sort = makeSelect('정렬', [['date', '최근 공시순'], ['amount', '투자금액순'], ['ratio', '자본 대비 비율순']]);
  const searchLabel = el('label', null, 'ex-search'); searchLabel.append(el('span', '기업·제품 검색'));
  const query = el('input'); query.type = 'search'; query.placeholder = '기업명, 종목코드, 반도체, 생산라인…'; query.setAttribute('aria-label', '기업·제품 검색'); searchLabel.append(query); controls.append(searchLabel);
  const dates = el('div', null, 'ex-dates'); const dateInputs = [];
  for (const name of ['공시 시작일', '공시 종료일']) { const label = el('label'); label.append(el('span', name)); const input = el('input'); input.type = 'date'; input.setAttribute('aria-label', name); label.append(input); dates.append(label); dateInputs.push(input); }
  controls.append(dates);
  const csv = el('button', '조회 결과 CSV'); csv.type = 'button'; controls.append(csv);
  const count = el('p', '', 'ex-count'); count.setAttribute('aria-live', 'polite');
  const wrapper = el('div', null, 'ex-table-wrap'); wrapper.tabIndex = 0; wrapper.setAttribute('role', 'region'); wrapper.setAttribute('aria-label', '증설 투자 목록');
  const table = el('table'); const head = el('thead'); const body = el('tbody'); table.append(head, body); wrapper.append(table);
  const pager = el('div', null, 'ex-pager'); const prev = el('button', '이전'), next = el('button', '다음'), pageInfo = el('span'); prev.type = next.type = 'button'; pager.append(prev, pageInfo, next);
  root.append(tabs, controls, count, wrapper, pager);
  let view = 'projects', page = 0, filtered = [];
  const pageSize = 40;
  const now = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Seoul'}).format(new Date());
  const projectMap = new Map(doc.projects.map(p => [p.id, p]));
  const viewButtons = [];
  const td = (tr, value, cls) => { const cell = el('td', value, cls); tr.append(cell); return cell; };
  const appendDetails = (parent, project) => {
    const dl = el('dl', null, 'ex-details');
    for (const [label, value] of [ ['최초 공시', project.first_disclosed], ['최근 공시', project.last_disclosed], ['투자주체', project.investor], ['투자구분', project.investment_type], ['투자대상', project.target], ['투자목적 원문', project.purpose], ['분류 근거', project.classification_evidence], ['투자 소재지', project.location], ['생산규모 원문', project.capacity_text], ['이사회 결정일', project.decision_date], ['기타 투자판단 원문', project.notes], ['확인 사항', project.warnings?.join(' / ')] ]) {
      if (value) { dl.append(el('dt', label), el('dd', value)); }
    }
    parent.append(dl);
    const history = el('ol', null, 'ex-history');
    for (const h of project.history) {
      const item = el('li'); item.append(link(h.url, h.date), el('span', ` ${money(h.amount_krw)} · 완료 예정 ${h.end_date || '미확인'}${h.reason ? ' · ' + h.reason : ''}`)); history.append(item);
    }
    parent.append(el('h4', '공시 이력'), history);
  };
  function draw() {
    filtered = selectRows(doc, {view, category: category.value, market: market.value, query: query.value, from: dateInputs[0].value, to: dateInputs[1].value, sort: sort.value});
    page = Math.min(page, Math.max(0, Math.ceil(filtered.length / pageSize) - 1));
    viewButtons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === view)));
    head.replaceChildren(); body.replaceChildren(); const hrow = el('tr');
    for (const label of view === 'projects' ? ['최근 공시', '기업 / 투자주체', '투자내용', '투자계획액', '투자기간', '상태 / 원문'] : ['정정 공시', '기업 / 투자주체', '변경 내용', '정정 후 투자액', '완료 예정일', '원문 / 상세']) { const th = el('th', label); th.scope = 'col'; hrow.append(th); } head.append(hrow);
    count.textContent = `${view === 'projects' ? '투자' : '변경 공시'} ${filtered.length.toLocaleString('ko-KR')}건 · ${category.selectedOptions[0].textContent}${market.value ? ' · ' + market.value : ''}`;
    if (!filtered.length) { const row = el('tr'); const empty = td(row, '조건에 맞는 공시가 없습니다. 투자 분류·검색어·공시 기간을 확인해 주세요.', 'ex-empty'); empty.colSpan = 6; body.append(row); }
    for (const row of filtered.slice(page * pageSize, (page + 1) * pageSize)) {
      const project = view === 'projects' ? row : projectMap.get(row.project_id); const tr = el('tr');
      td(tr, view === 'projects' ? row.last_disclosed : row.date, 'ex-date');
      const company = td(tr, null); company.append(el('strong', row.corp_name), el('small', `${row.stock_code} · ${row.market}`));
      if (project?.is_subsidiary) company.append(el('small', '투자주체 ' + project.investor));
      const scope = td(tr, null, 'ex-scope');
      scope.append(el('span', project?.category_label || '', 'ex-category'));
      scope.append(el('p', view === 'projects' ? project.target || project.purpose || project.investment_type || '원문 확인 필요' : changesLabel(row)));
      if (view === 'projects' && project.target && project.purpose) scope.append(el('small', project.purpose));
      const amount = td(tr, null, 'ex-number');
      amount.append(el('strong', money(row.amount_krw)));
      if (view === 'projects') {
        if (row.equity_ratio != null) amount.append(el('small', `자기자본 대비 ${row.equity_ratio}%`));
        if (row.facts_rcept_no !== row.source_rcept_no) amount.append(el('small', '종전 확인 금액'));
      }
      const period = td(tr, null, 'ex-date');
      if (view === 'projects') period.append(el('small', row.start_date || '시작 미확인'), el('span', '→ ' + (row.end_date || '종료 미확인')));
      else period.textContent = row.end_date || '미확인';
      const action = td(tr, null); if (view === 'projects') action.append(el('small', statusLabel(row, now), row.record_status === 'announced' ? 'ex-status' : 'ex-status ex-attention'));
      action.append(link(view === 'projects' ? row.latest_url : row.url, 'DART 원문'));
      const toggle = el('button', '상세'); toggle.type = 'button'; toggle.className = 'ex-detail-toggle'; toggle.setAttribute('aria-expanded', 'false'); action.append(toggle);
      const expanded = el('tr', null, 'ex-detail-row'); expanded.hidden = true; const cell = td(expanded, null); cell.colSpan = 6;
      toggle.addEventListener('click', () => {
        expanded.hidden = !expanded.hidden; toggle.setAttribute('aria-expanded', String(!expanded.hidden));
        if (!expanded.hidden && !cell.firstChild) appendDetails(cell, project);
      }); body.append(tr, expanded);
    }
    prev.disabled = page === 0; next.disabled = (page + 1) * pageSize >= filtered.length;
    pageInfo.textContent = `${page + 1} / ${Math.max(1, Math.ceil(filtered.length / pageSize))}`;
  }
  for (const [id, label] of views) { const b = el('button', label); b.type = 'button'; b.dataset.view = id; b.addEventListener('click', () => {view = id; page = 0; draw();}); tabs.append(b); viewButtons.push(b); }
  for (const control of [category, market, sort, query, ...dateInputs]) control.addEventListener(control === query ? 'input' : 'change', () => {page = 0; draw();});
  prev.addEventListener('click', () => {page--; draw();}); next.addEventListener('click', () => {page++; draw();});
  csv.addEventListener('click', () => {
    const fields = view === 'projects' ? ['corp_name','stock_code','investor','last_disclosed','category_label','amount_krw','equity_ratio','purpose','start_date','end_date','status_label','latest_url'] : ['corp_name','stock_code','investor','date','amount_krw','end_date','reason','url'];
    const labels = {corp_name:'기업명',stock_code:'종목코드',investor:'투자주체',last_disclosed:'최근 공시일',category_label:'투자분류',amount_krw:'투자계획액(원)',equity_ratio:'자기자본 대비(%)',purpose:'투자목적 원문',start_date:'투자 시작일',end_date:'완료 예정일',status_label:'공시 상태',latest_url:'DART 원문',date:'정정 공시일',reason:'정정 사유',url:'DART 원문'};
    const header = fields.map(f => labels[f]); if (view === 'changes') header.push('변경 내용');
    const rows = filtered.map(row => { const values = fields.map(f => row[f]); if (view === 'changes') values.push(changesLabel(row)); return values; });
    const lines = [header, ...rows].map(row => row.map(csvValue).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff' + lines], {type: 'text/csv;charset=utf-8'})); const a = el('a'); a.href = url; a.download = `증설투자-${view}-${now}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  draw(); return root;
}

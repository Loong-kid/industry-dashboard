function node(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

export function renderCleanroom(doc) {
  const card = node('section', 'cleanroom-guide');
  card.append(node('p', 'cleanroom-meta', '국내 4사 · 대만 3사 · 말레이시아 1사 / 금액은 각국 통화 백만 단위'));
  const wrap = node('div', 'cleanroom-table-wrap'); wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', '클린룸·공조 기업과 확보 이력');
  const table = node('table', 'cleanroom-table'), thead = node('thead'), heading = node('tr');
  for (const [text, cls] of [['기업', ''], ['시장·코드', ''], ['주력 분야', 'cleanroom-role'], ['최근 단독 분기', 'cleanroom-quarter'], ['최신 누적 공시', 'cleanroom-latest'], ['출처', '']]) { const th = node('th', cls, text); th.scope = 'col'; heading.append(th); }
  thead.append(heading); table.append(thead); const tbody = node('tbody');
  for (const c of doc.companies) {
    const tr = node('tr'), firm = node('th'); firm.scope = 'row';
    const jump = node('a', '', c.name); jump.href = '#cleanroom-' + c.id;
    jump.addEventListener('click', event => { event.preventDefault(); document.getElementById('cleanroom-' + c.id)?.scrollIntoView({behavior: 'smooth', block: 'start'}); });
    firm.append(jump, node('small', '', c.country));
    const code = node('td', 'cleanroom-code', c.ticker); code.append(node('small', '', c.market || 'KRX'));
    const source = node('td'), link = node('a', '', '공시'); link.href = c.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; source.append(link);
    tr.append(firm, code, node('td', 'cleanroom-role', c.role), node('td', 'cleanroom-quarter', c.quarter_end), node('td', 'cleanroom-latest', c.latest_basis === '누적 YTD' ? c.latest_date + ' YTD' : '—'), source); tbody.append(tr);
  }
  table.append(tbody); wrap.append(table); card.append(wrap);
  const detail = node('details', 'cleanroom-method'); detail.append(node('summary', '', '기업별 사업 범위·확보 기간'));
  for (const c of doc.companies) detail.append(node('p', '', `${c.name} · ${c.role}. ${c.note} 분기 ${c.quarter_start}부터 / 연간 ${c.annual_start.slice(0, 4)}년부터. ${c.ok ? '' : '일부 조회 실패 · 확보한 자료 유지.'}`));
  detail.append(node('p', '', 'YTD는 연초 이후 누적 공시로, 단독 분기와 다릅니다. 켈링톤의 PBT는 영업이익이 아닌 세전이익입니다. CAPEX는 시공사의 자체 유형자산 취득 현금지출이며 고객사의 팹 투자나 수주액이 아닙니다. 통화·연결 범위가 달라 회사 간 금액을 합산하지 않습니다.'));
  card.append(detail); return card;
}

function node(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
export function renderGuide(doc, tab) {
  const group = tab === 'osat_korea' ? 'domestic' : tab === 'osat_global' ? 'global' : null;
  const companies = doc.companies.filter(c => !group || c.group === group);
  const section = node('section', 'osat-guide'); section.id = 'osat-company-guide';
  section.append(node('h2', '', '패키징·테스트 서비스 기업 비교'));
  section.append(node('p', 'osat-intro', '패키징은 칩을 보호하고 외부 회로에 연결하는 공정, 테스트는 칩의 전기적 동작을 검사하는 공정입니다. 아래 기업은 이 공정을 위탁받는 서비스 기업이며, 장비 판매사 실적은 장비 분야에서 볼 수 있습니다.'));
  section.append(node('p', 'osat-meta', `${companies.length}개 기업 · 원통화 백만 단위 · 매일 09:15 KST 공시 확인 · 자료 확인 ${doc.fetched}`));
  const wrap = node('div', 'osat-table-wrap'); wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', '패키징·테스트 기업별 사업 역할과 실적 범위');
  const table = node('table', 'osat-table'), head = node('thead'), header = node('tr');
  for (const label of ['기업', '주력 역할', '실적 범위·비교 기준', '확보 기간', '원문']) { const th = node('th', '', label); th.scope = 'col'; header.append(th); }
  head.append(header); table.append(head); const body = node('tbody');
  for (const c of companies) {
    const tr = node('tr'), firm = node('th', '', c.name); firm.scope = 'row'; firm.append(node('small', '', `${c.country} / ${c.ticker} / ${c.currency}`));
    const scope = node('td', 'osat-scope', c.scope), detail = node('details'), summary = node('summary', '', '범위·중복 확인'); detail.append(summary, node('p', '', c.note)); scope.append(detail);
    const coverage = node('td', 'osat-period', `분기 ${c.quarter_start.slice(0,4)} Q${Math.ceil(Number(c.quarter_start.slice(5,7))/3)}부터`);
    coverage.append(node('small', '', `연간 ${c.annual_start.slice(0,4)}부터`), node('small', '', `최근 분기 ${c.quarter_end}`));
    if (c.id === 'ase') coverage.append(node('small', 'osat-definition', 'CAPEX: 연간 총취득 / 분기 순지출 별도'));
    if (!c.ok) coverage.append(node('small', 'osat-review', '조회 실패 · 기존 성공 자료 유지'));
    const sources = node('td'), a = node('a', '', '사업·공시'); a.href = c.source_url; a.target = '_blank'; a.rel = 'noopener noreferrer'; sources.append(a);
    tr.append(firm, node('td', 'osat-role', c.role), scope, coverage, sources); body.append(tr);
  }
  table.append(body); wrap.append(table); section.append(wrap);
  section.append(node('p', 'osat-meta', '네패스·네패스아크 등 모회사와 자회사는 연결 범위가 겹칠 수 있습니다. 국가별 통화와 공시 범위가 달라 기업 실적을 단순 합산하지 않습니다.'));
  const details = node('details', 'osat-method'), summary = node('summary', '', '기업 선정·자료 기준'); details.append(summary, node('p', '', doc.selection_basis), node('p', '', '2014년부터 공시 확보 기간을 표시합니다. 분할·통합 법인은 해당 법인의 공시 범위부터 시작하며 없는 기간을 0이나 연간의 1/4로 채우지 않습니다. 각 그래프의 분기·연간 선택과 출처·기준에서 계산 방법을 확인할 수 있습니다.')); section.append(details);
  return section;
}

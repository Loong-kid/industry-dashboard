const GROUPS = {atom: '이온트랩·중성원자', superconducting: '초전도·어닐링', photonics: '광자·소프트웨어'};

function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text != null) el.textContent = text;
  return el;
}

function external(label, url) {
  const a = node('a', '', label + ' ↗');
  a.href = url; a.target = '_blank'; a.rel = 'noopener';
  return a;
}

function ordinary(etf, ticker) {
  const position = etf?.positions?.find(p => p.kind === 'equity' && p.ticker === ticker);
  if (position) return position.weight.toFixed(2) + '%';
  return etf?.positions?.length ? '보유 내역 없음' : '미확인';
}

export function renderOverview(doc) {
  const root = node('div', 'qt-overview');
  if (!doc) {
    root.append(node('p', 'card-empty', '양자컴퓨터 추적 대상 자료를 아직 확보하지 못했습니다.'));
    return root;
  }
  const heading = node('h2', 'qt-heading', 'ETF에서 찾고, 기업 실적으로 확인');
  root.append(heading, node('p', 'ir-scope-note', 'ETF 편입은 추적 대상을 찾는 기준입니다. 아래 기업의 전체 연결 매출을 양자 컴퓨터 판매액이나 시장 TAM으로 합산하지 않습니다.'));
  const etfs = node('div', 'qt-etfs');
  for (const etf of doc.etfs) {
    const box = node('article', 'card qt-etf');
    box.append(node('div', 'qt-market', etf.market), node('h3', '', etf.ticker), external(etf.name, etf.url),
      node('p', '', etf.scope), node('p', 'qt-note', etf.note));
    if (etf.isin) box.append(node('p', 'qt-note', 'ISIN ' + etf.isin));
    if (etf.holdings_url) {
      const foot = node('p', 'qt-note');
      foot.append(external('보유 내역', etf.holdings_url), document.createTextNode(' · 기준 ' + (etf.asof || '미확인') + ' · 조회 ' + etf.checked));
      box.append(foot);
      if (etf.status !== 'ok') box.append(node('p', 'qt-warn', etf.status));
    }
    etfs.append(box);
  }
  root.append(etfs, node('h2', 'qt-heading', `실적 추적 ${doc.companies.length}개사`));
  const qtum = doc.etfs.find(e => e.id === 'qtum'), qtup = doc.etfs.find(e => e.id === 'qtup');
  root.append(node('p', 'ir-scope-note', `비중은 보통주 현물 기준입니다. QTUM ${qtum?.asof || '미확인'} / QTUP ${qtup?.asof || '미확인'}. QTUP의 스왑은 이 비중에 합산하지 않습니다. WQTM·QNTM의 비중은 현재 미연결입니다.`));
  const wrap = node('div', 'qt-table-wrap');
  wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', '기업별 기술·ETF 보유·실적 확보 범위');
  const table = node('table', 'qt-table');
  const head = node('thead'), tr = node('tr');
  for (const label of ['기업', '접근 방식', '매출 범위', 'QTUM', 'QTUP', '실적 확보']) {
    const th = node('th', '', label); th.scope = 'col'; tr.append(th);
  }
  head.append(tr); table.append(head);
  const body = node('tbody');
  for (const company of doc.companies) {
    const row = node('tr');
    const name = node('td'), link = node('a', '', company.name);
    link.href = '#/quantum/' + company.group;
    link.setAttribute('aria-label', company.name + ' 실적 보기 · ' + GROUPS[company.group]);
    name.append(link, node('small', '', company.ticker));
    const coverage = node('td', 'qt-coverage');
    const counts = company.periods;
    coverage.append(node('div', '', company.financial_end || '미확보'),
      node('small', '', [['quarter', '분기'], ['half', '반기'], ['annual', '연간']].filter(([k]) => counts[k]).map(([k, l]) => l + ' ' + counts[k] + '개').join(' · ')));
    if (company.status !== 'ok') coverage.append(node('small', 'qt-warn', '최신 조회·공시 검토 필요'));
    row.append(name, node('td', '', company.technology), node('td', 'qt-scope', company.scope),
      node('td', 'qt-weight', ordinary(qtum, company.ticker)), node('td', 'qt-weight', ordinary(qtup, company.ticker)), coverage);
    body.append(row);
  }
  table.append(body); wrap.append(table); root.append(wrap);
  const exclusions = node('section', 'qt-exclusions');
  exclusions.append(node('h2', 'qt-heading', '추적 범위를 나눈 이유'),
    node('p', '', 'IBM·Alphabet·Microsoft·Amazon 등은 양자 매출을 별도로 분리하기 어려워 이 산업의 기업 실적 목록에서 제외했습니다.'),
    node('p', '', 'Arqit(ARQQ)·BTQ Technologies(BTQ)·Quantum eMotion(QNC)은 양자 내성 보안·난수 등 주변 기술로 구분했습니다. ETF에 포함되어 있어도 양자 컴퓨터 제조·소프트웨어 기업과 같은 매출로 묶지 않습니다.'),
    node('p', 'qt-note', '신규 상장사의 전신 운영기업 이력은 포함하되 SPAC·신설 지주회사의 설립 비용, 가상 IPO 재무제표, 매출 전망과 수주잔고는 실제 매출 시계열에 넣지 않습니다. 미확보 실적은 0으로 채우지 않습니다.'));
  root.append(exclusions);
  return root;
}

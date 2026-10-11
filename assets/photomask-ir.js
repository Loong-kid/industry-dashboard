/* Official document reader. No excerpts, generated summaries, or search. */
function renderPhotomaskViews(view) {
  const nav = document.createElement('nav');
  nav.className = 'photomask-views';
  nav.setAttribute('aria-label', '포토마스크 보기');
  for (const [id, name, hash] of [
    ['indicators', '지표', '#/semicon/snstech'],
    ['ir', 'IR · Q&A 도서관', '#/semicon/snstech/ir'],
  ]) {
    const link = document.createElement('a');
    link.href = hash;
    link.textContent = name;
    if (view === id) link.setAttribute('aria-current', 'page');
    nav.appendChild(link);
  }
  return nav;
}

function renderPhotomaskLibrary(doc) {
  const root = document.createElement('section');
  root.className = 'photomask-library';
  if (!doc?.documents?.length) {
    root.textContent = '등록된 IR · Q&A 자료가 없습니다.';
    return root;
  }
  const esc = escapeHtml;
  root.innerHTML = `<header class="pm-library-head"><h2>IR · Q&A 도서관</h2>
    <p>회사와 분기를 선택해 공식 원문을 읽습니다. 컨콜 전문과 후속 FAQ는 각각 별도 자료입니다.</p></header>
    <div class="pm-companies" role="group" aria-label="회사 선택"></div>
    <div class="pm-library-layout"><nav class="pm-periods" aria-label="분기 선택"></nav>
      <article class="pm-reader" aria-label="선택한 자료"></article></div>
    <p class="pm-reviewed">공식 PDF 확인: ${esc(doc.fetched)} · 회사별 최근 8개 분기 · 자료 목록은 수기 갱신</p>`;
  const companies = root.querySelector('.pm-companies');
  const periods = root.querySelector('.pm-periods');
  const reader = root.querySelector('.pm-reader');
  let company = doc.companies[0];
  let period;
  let selected;
  // Stay on the same selected company/quarter when a theme or range rerenders.
  const remembered = window.photomaskLibrarySelection || {};
  if (doc.companies.some(c => c.id === remembered.company)) {
    company = doc.companies.find(c => c.id === remembered.company);
    period = remembered.period;
    selected = remembered.document;
  }
  const safeURL = url => {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' && ['www.hoya.com', 'www.agc.com', 'www.shinetsu.co.jp', 'ssl4.eir-parts.net'].includes(parsed.hostname) ? parsed.href : null;
    } catch { return null; }
  };
  const remember = () => { window.photomaskLibrarySelection = {company: company.id, period, document: selected}; };

  const renderReader = () => {
    const records = doc.documents.filter(d => d.company === company.id && d.period_end === period)
      .sort((a, b) => (a.kind === 'transcript') - (b.kind === 'transcript'));
    const record = records.find(d => d.id === selected) || records[0];
    if (!record) return;
    selected = record.id;
    remember();
    const url = safeURL(record.url);
    reader.innerHTML = `<div class="pm-reader-heading"><h3>${esc(company.name)} ${esc(record.fiscal_label)}</h3>
      <p>실적 대상 기간 ${esc(record.period_label)} · ${esc(company.fiscal_note)}</p></div>
      <label class="pm-source-picker">자료 <select aria-label="자료 선택"></select></label>
      <dl class="pm-document-meta">
        <div><dt>자료 종류</dt><dd>${esc(record.kind_label)}</dd></div>
        <div><dt>${record.published_date ? '공개일' : '회의일'}</dt><dd>${esc(record.published_date || record.event_date || '미확인')}</dd></div>
        <div><dt>원문</dt><dd>${esc(record.language)} · ${esc(record.pages)}쪽</dd></div>
      </dl>
      <p class="pm-translation-state">한국어 직역본 미등록 · 현재는 공식 원문을 제공합니다.</p>
      <div class="pm-document-actions">${url ? `<a class="pm-original-link" href="${esc(url)}" target="_blank" rel="noopener">원문 PDF 열기</a>
        <button type="button" class="pm-inline-toggle" aria-expanded="false">여기서 원문 보기</button>` : '<p>원문 링크를 확인해 주세요.</p>'}</div>
      <div class="pm-pdf-area" hidden></div>
      <p class="pm-reader-note">화면에서 PDF가 보이지 않으면 ‘원문 PDF 열기’를 이용하세요. PDF 저장은 원문 뷰어의 다운로드 기능을 이용할 수 있습니다.</p>
      ${safeURL(record.source_index) ? `<a class="pm-archive-link" href="${esc(safeURL(record.source_index))}" target="_blank" rel="noopener">${esc(company.name)} 공식 자료실</a>` : ''}`;
    const picker = reader.querySelector('select');
    for (const d of records) {
      const option = document.createElement('option');
      option.value = d.id;
      option.textContent = `${d.kind_label} · ${d.published_date || d.event_date || ''}`;
      option.selected = d.id === selected;
      picker.appendChild(option);
    }
    picker.addEventListener('change', () => { selected = picker.value; renderReader(); });
    reader.querySelector('.pm-inline-toggle')?.addEventListener('click', event => {
      const area = reader.querySelector('.pm-pdf-area');
      const open = area.hidden;
      if (open && !area.firstChild) {
        const frame = document.createElement('iframe');
        frame.src = url + '#view=FitH';
        frame.title = `${company.name} ${record.fiscal_label} ${record.kind_label} 공식 원문`;
        frame.referrerPolicy = 'no-referrer';
        area.appendChild(frame);
      }
      area.hidden = !open;
      event.currentTarget.setAttribute('aria-expanded', String(open));
      event.currentTarget.textContent = open ? '원문 닫기' : '여기서 원문 보기';
    });
  };

  const renderPeriods = () => {
    const records = doc.documents.filter(d => d.company === company.id);
    const ends = [...new Set(records.map(d => d.period_end))].sort().reverse();
    if (!ends.includes(period)) period = ends[0];
    companies.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.company === company.id)));
    periods.innerHTML = '';
    for (const end of ends) {
      const d = records.find(record => record.period_end === end);
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(end === period));
      button.innerHTML = `<strong>${esc(d.fiscal_label)}</strong><span>${esc(d.period_label)}</span><small>${records.filter(r => r.period_end === end).length}개 자료</small>`;
      button.addEventListener('click', () => { period = end; selected = null; renderPeriods(); });
      periods.appendChild(button);
    }
    renderReader();
  };
  for (const c of doc.companies) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = c.name;
    button.dataset.company = c.id;
    button.addEventListener('click', () => { company = c; period = null; selected = null; renderPeriods(); });
    companies.appendChild(button);
  }
  renderPeriods();
  return root;
}

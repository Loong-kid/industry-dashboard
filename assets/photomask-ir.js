/* Official originals and user-supplied translations. No generated summaries or search. */
function renderPhotomaskMarkdown(text, originalURL) {
  const root = document.createElement('div');
  const inline = (element, value) => {
    // Treat source HTML as text; only support the formatting used by these files.
    const pattern = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^\s)]+)\)/g;
    let start = 0;
    for (const match of value.matchAll(pattern)) {
      element.append(document.createTextNode(value.slice(start, match.index)));
      if (match[1]) {
        const strong = document.createElement('strong');
        strong.textContent = match[1];
        element.append(strong);
      } else {
        // Local PDF paths in supplied Markdown refer to the download folder.
        const target = /\.pdf$/i.test(match[3]) && !/^https:\/\//.test(match[3]) ? originalURL : match[3];
        if (target && /^https:\/\//.test(target)) {
          const link = document.createElement('a');
          link.textContent = match[2];
          link.href = target;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          element.append(link);
        } else element.append(document.createTextNode(match[2]));
      }
      start = match.index + match[0].length;
    }
    element.append(document.createTextNode(value.slice(start)));
  };
  for (const block of text.replace(/\r\n/g, '\n').trim().split(/\n\s*\n/)) {
    const heading = block.match(/^(#{1,6}) (.+)$/);
    if (heading) {
      const h = document.createElement(`h${Math.min(6, heading[1].length + 2)}`);
      inline(h, heading[2]);
      if (/^원문 \d+쪽/.test(heading[2])) h.className = 'pm-page-heading';
      root.append(h);
    } else if (block.split('\n').every(line => /^[-*] /.test(line))) {
      const list = document.createElement('ul');
      for (const line of block.split('\n')) {
        const item = document.createElement('li');
        inline(item, line.slice(2));
        list.append(item);
      }
      root.append(list);
    } else if (/^> ?/.test(block)) {
      const quote = document.createElement('blockquote');
      inline(quote, block.replace(/^> ?/gm, ''));
      root.append(quote);
    } else if (/^---+$/.test(block)) root.append(document.createElement('hr'));
    else {
      const paragraph = document.createElement('p');
      inline(paragraph, block);
      if (/^\*\*Q/.test(block)) paragraph.className = 'pm-question';
      root.append(paragraph);
    }
  }
  return root;
}

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
    <p>회사와 분기를 선택해 한국어 번역본과 공식 원문을 읽습니다. 컨콜 Q&A와 후속 FAQ는 각각 별도 자료입니다.</p></header>
    <div class="pm-companies" role="group" aria-label="회사 선택"></div>
    <div class="pm-library-layout"><nav class="pm-periods" aria-label="분기 선택"></nav>
      <article class="pm-reader" aria-label="선택한 자료"></article></div>
    <p class="pm-reviewed">${esc(doc.coverage?.start_period_end || '')} ~ ${esc(doc.coverage?.end_period_end || '')} · ${doc.documents.length}개 자료 · 번역본 등록: ${esc(doc.updated)} · 자료 목록은 수기 갱신</p>`;
  const companies = root.querySelector('.pm-companies');
  const periods = root.querySelector('.pm-periods');
  const reader = root.querySelector('.pm-reader');
  let company = doc.companies[0];
  let period;
  let selected;
  let readingSequence = 0;
  const translationCache = new Map();
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
    const sequence = ++readingSequence;
    const records = doc.documents.filter(d => d.company === company.id && d.period_end === period)
      .sort((a, b) => (a.kind === 'transcript') - (b.kind === 'transcript'));
    const record = records.find(d => d.id === selected) || records[0];
    if (!record) return;
    selected = record.id;
    remember();
    const url = safeURL(record.url);
    const translation = record.translation;
    const translationPath = translation && /^data\/semicon\/photomask-ir-ko\/[a-z0-9_-]+\.md$/.test(translation.path) ? translation.path : null;
    reader.innerHTML = `<div class="pm-reader-heading"><h3>${esc(company.name)} ${esc(record.fiscal_label)}</h3>
      <p>실적 대상 기간 ${esc(record.period_label)} · ${esc(company.fiscal_note)}</p></div>
      <label class="pm-source-picker">자료 <select aria-label="자료 선택"></select></label>
      <dl class="pm-document-meta">
        <div><dt>자료 종류</dt><dd>${esc(record.kind_label)}</dd></div>
        <div><dt>${record.published_date ? '공개일' : '회의일'}</dt><dd>${esc(record.published_date || record.event_date || '미확인')}</dd></div>
        <div><dt>원문</dt><dd>${esc(record.language)} · ${esc(record.pages)}쪽</dd></div>
      </dl>
      <div class="pm-translation-state">${translationPath ? `<strong>한국어 번역 초안</strong><p>번역 범위: ${esc(translation.scope)}</p><p>${esc(translation.note)}</p>` : '한국어 번역본 미등록 · 공식 원문을 제공합니다.'}</div>
      <div class="pm-document-actions">${translationPath ? `<a class="pm-translation-download" href="${esc(translationPath)}" download>번역 파일 받기</a>` : ''}${url ? `<a class="pm-original-link" href="${esc(url)}" target="_blank" rel="noopener">원문 PDF 열기</a>
        <button type="button" class="pm-inline-toggle" aria-expanded="false">여기서 원문 보기</button>` : '<p>원문 링크를 확인해 주세요.</p>'}</div>
      <div class="pm-pdf-area" hidden></div>
      ${translationPath ? '<section class="pm-translation-body" aria-label="한국어 번역문" aria-busy="true"><p role="status">번역문을 불러오는 중입니다.</p></section>' : ''}
      <p class="pm-reader-note">‘원문 N쪽’은 PDF 페이지입니다. PDF가 보이지 않으면 ‘원문 PDF 열기’를 이용하세요.</p>
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
    const loadTranslation = async () => {
      const body = reader.querySelector('.pm-translation-body');
      if (!body) return;
      body.setAttribute('aria-busy', 'true');
      body.textContent = '번역문을 불러오는 중입니다.';
      try {
        let text = translationCache.get(translationPath);
        if (text === undefined) {
          const response = await fetch(`${translationPath}?v=${encodeURIComponent(translation.sha256)}`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          text = await response.text();
          if (!text.includes('## 원문 ')) throw new Error('번역 파일 형식 확인 필요');
          translationCache.set(translationPath, text);
        }
        if (sequence !== readingSequence) return;
        body.replaceChildren();
        // Keep file notes available without repeating the reader's metadata.
        const split = text.search(/^## 원문 /m);
        if (split > 0) {
          const notes = document.createElement('details');
          const summary = document.createElement('summary');
          summary.textContent = '번역 파일 안내';
          notes.append(summary, renderPhotomaskMarkdown(text.slice(0, split), url));
          body.append(notes);
        }
        body.append(renderPhotomaskMarkdown(text.slice(Math.max(0, split)), url));
        body.setAttribute('aria-busy', 'false');
      } catch {
        if (sequence !== readingSequence) return;
        body.textContent = '번역문을 불러오지 못했습니다. 다시 시도하거나 ‘번역 파일 받기’를 이용하세요.';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.textContent = '다시 불러오기';
        retry.addEventListener('click', loadTranslation);
        body.append(retry);
        body.setAttribute('aria-busy', 'false');
      }
    };
    if (translationPath) loadTranslation();
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
      button.addEventListener('click', () => {
        period = end; selected = null; renderPeriods();
        if (reader.getBoundingClientRect().top < 0) reader.scrollIntoView({block: 'start'});
      });
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

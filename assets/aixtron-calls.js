/* Reviewed local transcripts. Fetch only the selected quarter; keep raw PDFs intact. */
let selection = null;
const cache = new Map();
const localPath = path => /^data\/semicon\/aixtron-calls\/202[56]-q[1-4](?:-original\.pdf|-ko\.md|\.json)$/.test(path || '') ? path : null;

function text(tag, value, className) {
  const node = document.createElement(tag);
  node.textContent = value;
  if (className) node.className = className;
  return node;
}

export function render(doc) {
  const root = document.createElement('section');
  root.className = 'aixtron-calls';
  root.append(text('h2', '아익스트론 컨콜'));
  root.append(text('p', '분기를 선택해 한국어 전문을 읽습니다. 원문 함께 보기를 켜면 같은 PDF 페이지의 영어와 번역문을 나란히 볼 수 있습니다.', 'ax-intro'));
  if (!doc?.documents?.length) {
    root.append(text('p', '등록된 컨콜 자료가 없습니다.'));
    return root;
  }
  root.append(text('p', `${doc.documents.at(-1).label} ~ ${doc.documents[0].label} · ${doc.documents.length}개 자료 · 원문 ${doc.documents.reduce((n, d) => n + d.page_count, 0)}쪽 · 번역 검수 ${doc.updated}`, 'ax-meta'));
  const layout = document.createElement('div'); layout.className = 'ax-layout';
  const periods = document.createElement('nav'); periods.className = 'ax-periods'; periods.setAttribute('aria-label', '컨콜 분기 선택');
  const reader = document.createElement('article'); reader.className = 'ax-reader'; reader.setAttribute('aria-label', '컨콜 전문');
  layout.append(periods, reader); root.append(layout);
  let selected = doc.documents.find(d => d.id === selection)?.id || doc.documents[0].id;
  let bilingual = false, sequence = 0;
  const buttons = [];

  async function open(record, scroll = false) {
    const ticket = ++sequence;
    selected = selection = record.id;
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === selected)));
    reader.replaceChildren(text('p', '번역문을 불러오는 중입니다.', 'ax-status'));
    reader.setAttribute('aria-busy', 'true');
    try {
      const path = localPath(record.path);
      if (!path) throw new Error('Invalid document path');
      const key = path + '?v=' + encodeURIComponent(record.content_sha256);
      let detail = cache.get(key);
      if (!detail) {
        const response = await fetch(key);
        if (!response.ok) throw new Error('HTTP ' + response.status);
        detail = await response.json();
        if (detail.id !== record.id || detail.pages?.length !== record.page_count || detail.pages.some((p, i) => p.page !== i + 1 || !p.en || !p.ko)) throw new Error('Incomplete document');
        cache.set(key, detail);
      }
      if (ticket !== sequence || !root.isConnected) return;
      reader.replaceChildren();
      reader.append(text('h3', `AIXTRON ${record.label}`));
      reader.append(text('p', `${record.date} · ${record.kind_label} · ${record.source.provider} · 원문 ${record.page_count}쪽`, 'ax-meta'));
      const actions = document.createElement('div'); actions.className = 'ax-actions';
      for (const [path, label, download] of [[record.source.path, '원문 PDF 열기', false], [record.translation_path, '한국어 번역 받기', true]]) {
        if (!localPath(path)) continue;
        const link = text('a', label); link.href = path;
        if (download) link.download = ''; else { link.target = '_blank'; link.rel = 'noopener'; }
        actions.append(link);
      }
      const toggle = text('button', '원문 함께 보기'); toggle.type = 'button';
      toggle.setAttribute('aria-pressed', String(bilingual)); actions.append(toggle);
      const picker = document.createElement('label'); picker.append(text('span', '페이지 이동'));
      const select = document.createElement('select'); select.setAttribute('aria-label', '원문 페이지 이동');
      for (const p of detail.pages) { const option = text('option', `${p.page}쪽`); option.value = p.page; select.append(option); }
      picker.append(select); actions.append(picker); reader.append(actions);
      const method = document.createElement('details'); method.className = 'ax-method'; method.append(text('summary', '번역 범위와 검수 기준'), text('p', doc.review_method));
      method.append(text('p', record.kind === 'transcript' ? '제공된 PDF의 발표와 질의응답을 모두 수록했습니다.' : '제공된 PDF는 경영진 발표문입니다. 끝의 질문 접수 안내 뒤에 실제 Q&A 내용은 포함돼 있지 않습니다.'));
      reader.append(method);
      const body = document.createElement('div'); body.className = 'ax-pages';
      body.classList.toggle('ax-bilingual', bilingual);
      for (const p of detail.pages) {
        const section = document.createElement('section'); section.className = 'ax-page'; section.id = `ax-${record.id}-p${p.page}`;
        section.append(text('h4', `원문 ${p.page}쪽`));
        const columns = document.createElement('div'); columns.className = 'ax-columns';
        const english = document.createElement('div'); english.className = 'ax-english'; english.lang = 'en'; english.hidden = !bilingual;
        english.append(text('h5', '영어 원문'));
        for (const paragraph of p.en.split(/\n\s*\n/)) english.append(text('p', paragraph));
        const korean = document.createElement('div'); korean.className = 'ax-korean'; korean.lang = 'ko'; korean.append(text('h5', '한국어 번역'));
        // The existing safe Markdown renderer treats source HTML as text.
        korean.append(renderPhotomaskMarkdown(p.ko, record.source.path));
        columns.append(english, korean); section.append(columns);
        if (p.notes.length) { const notes = document.createElement('aside'); notes.className = 'ax-notes'; notes.append(text('h5', '번역 검수 주')); p.notes.forEach(n => notes.append(text('p', n))); section.append(notes); }
        body.append(section);
      }
      toggle.addEventListener('click', () => {
        bilingual = !bilingual; toggle.setAttribute('aria-pressed', String(bilingual)); body.classList.toggle('ax-bilingual', bilingual);
        body.querySelectorAll('.ax-english').forEach(e => { e.hidden = !bilingual; });
      });
      select.addEventListener('change', () => body.querySelector(`#ax-${record.id}-p${select.value}`)?.scrollIntoView({block: 'start'}));
      reader.append(body);
      reader.setAttribute('aria-busy', 'false');
      if (scroll && reader.getBoundingClientRect().top < 0) reader.scrollIntoView({block: 'start'});
    } catch {
      if (ticket !== sequence || !root.isConnected) return;
      reader.replaceChildren(text('p', '번역문을 불러오지 못했습니다. 다시 불러오기를 눌러 주세요.', 'ax-status'));
      const retry = text('button', '다시 불러오기'); retry.type = 'button'; retry.addEventListener('click', () => open(record)); reader.append(retry);
      reader.setAttribute('aria-busy', 'false');
    }
  }
  for (const record of doc.documents) {
    const button = document.createElement('button'); button.type = 'button'; button.dataset.id = record.id;
    button.append(text('strong', record.label), text('span', record.kind === 'transcript' ? '발표 + Q&A' : '경영진 발표문'), text('small', `${record.date} · ${record.page_count}쪽`));
    button.addEventListener('click', () => open(record, true)); periods.append(button); buttons.push(button);
  }
  // render() returns synchronously; defer until its root is mounted.
  queueMicrotask(() => open(doc.documents.find(d => d.id === selected)));
  return root;
}

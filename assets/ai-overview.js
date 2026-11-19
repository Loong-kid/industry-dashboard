/* Public model snapshot and read-only comparisons from the user's sheets. */
export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const safeURL = value => /^https?:\/\//i.test(String(value || '')) ? String(value) : '';
export function valueOf(row, key, table) {
  return key === table.provider_key ? row.provider : row.cells[key]?.text ?? '';
}
export function selectRows(table, {provider = '', search = '', sort = '', direction = 1} = {}) {
  const query = search.trim().toLocaleLowerCase();
  const rows = table.rows.filter(row => (!provider || row.provider === provider) && (!query ||
    [row.provider, row.model, ...Object.values(row.cells).map(cell => cell.text)].join(' ').toLocaleLowerCase().includes(query)));
  if (sort) rows.sort((a, b) => {
    const av = valueOf(a, sort, table), bv = valueOf(b, sort, table);
    if (av === '' || bv === '') return av === bv ? 0 : av === '' ? 1 : -1;
    const an = a.cells[sort]?.number, bn = b.cells[sort]?.number;
    return direction * (typeof an === 'number' && typeof bn === 'number' ? an - bn : String(av).localeCompare(String(bv), 'ko', {numeric:true}));
  });
  return rows;
}
export function csvText(table, rows, columns) {
  const quote = value => '"' + String(value ?? '').replace(/^[=+@-]/, "'$&").replace(/"/g, '""') + '"';
  return '\ufeff' + [columns.map(c => c.label), ...rows.map(row => columns.map(c => valueOf(row, c.key, table)))].map(row => row.map(quote).join(',')).join('\r\n');
}
const link = (url, label) => safeURL(url) ? `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(label)}</a>` : escapeHTML(label);

export function publicModelTable(doc) {
  const columns = [
    {key:'provider', label:'기업', width:104},
    {key:'model', label:'모델', width:210},
    {key:'input', label:'입력 $/100만', width:100},
    {key:'output', label:'출력 $/100만', width:100},
    {key:'score', label:'AA 종합 지수', width:108, note:'Artificial Analysis Intelligence Index ' + doc.index_version},
    {key:'effort', label:'평가 설정', width:86},
    {key:'cost', label:'AA 과제당 $', width:106, note:'동일 평가 설정의 과제당 비용. 토큰 소비량과 평가 환경을 반영한 AA 수치입니다.'},
    {key:'cache', label:'캐시 읽기 $/100만', width:108},
    {key:'release', label:'공개일', width:112},
    {key:'basis', label:'가격 조건', width:180},
  ];
  const dollars = new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits:4});
  const money = (value, note, url) => value == null ? {text:'', note, links:[url]} :
    {text:dollars.format(value), number:value, note, links:[url]};
  const rows = [...doc.models].sort((a,b) => b.release.localeCompare(a.release)).map(model => {
    const {price, benchmark} = model;
    const benchNote = benchmark
      ? `AA ${doc.index_version} · ${benchmark.effort}${benchmark.note ? ' · ' + benchmark.note : ''}`
      : '이 스냅샷에서 확인한 AA 지수 없음';
    const benchLinks = [benchmark?.url || doc.source.tab_url];
    return {id:model.id, provider:model.provider, model:model.name, cells:{
      model:{text:model.name, note:model.api_id, links:[model.release_url]},
      input:money(price.input, price.note, price.url),
      cache:money(price.cache, price.note, price.url),
      output:money(price.output, price.note, price.url),
      score:{text:benchmark ? String(benchmark.score) : '', number:benchmark?.score, note:benchNote, links:benchLinks},
      effort:{text:benchmark?.effort || '', note:benchNote, links:benchLinks},
      cost:money(benchmark?.cost, benchNote, benchLinks[0]),
      release:{text:model.release, note:model.release_note, links:[model.release_url]},
      basis:{text:price.basis, note:price.note, links:[price.url]},
    }};
  });
  const common = ['provider','model'];
  return {
    id:'recent-models', title:'최근 공개 언어모델', provider_key:'provider', model_key:'model',
    unit_note:'텍스트 API 가격은 USD/100만 토큰 기준입니다. 할인·긴 문맥·가격 구간은 해당 값을 눌러 확인할 수 있습니다. AA 과제당 비용은 표시된 평가 설정의 공개 측정치입니다.',
    columns, rows, views:[
      {id:'all',label:'가격·벤치마크',keys:columns.map(c=>c.key)},
      {id:'price',label:'토큰 가격',keys:[...common,'input','output','cache','basis','release']},
      {id:'bench',label:'벤치마크',keys:[...common,'score','effort','cost','release']},
    ],
  };
}

export function renderAIOverview(doc) {
  if (!document.querySelector('link[data-ai-overview]')) {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = new URL('./ai-overview.css', import.meta.url).href; css.dataset.aiOverview = '';
    document.head.insertBefore(css, document.querySelector('link[href$="theme-mercury.css"]'));
  }
  const root = document.createElement('div'); root.className = 'ai-overview';
  if (!doc) { root.textContent = '비교표를 불러오지 못했습니다.'; return root; }
  const publicData = Array.isArray(doc.models);
  if (publicData) doc = {...doc, tables:[publicModelTable(doc)]};
  const e = escapeHTML;
  root.innerHTML = `<div class="aio-heading"><div><h2>${e(doc.name)}</h2><p>${doc.tables.reduce((sum, t) => sum + t.rows.length, 0)}개 모델 · ${publicData ? `공개 자료 · AA ${e(doc.index_version)}` : '시트 기재값'}</p></div><div>${link(doc.source.tab_url, publicData ? 'AA 평가 방법' : '원본 시트 열기')}<small>${publicData ? `확인일 ${e(doc.imported)}` : `가져온 날 ${e(doc.imported)}<br>시트 최종 수정 ${e(doc.source.modified_at.slice(0, 10))}`}</small></div></div>
    <p class="aio-note">${e(doc.note)}</p><div class="aio-tables"></div>
    <dialog class="aio-dialog" aria-label="모델 상세 정보"><div class="aio-dialog-head"><h2></h2><button type="button" data-close>닫기</button></div><div class="aio-dialog-body"></div></dialog>`;
  const dialog = root.querySelector('dialog');
  dialog.querySelector('[data-close]').onclick = () => dialog.close();
  dialog.addEventListener('click', event => { if (event.target === dialog) { const b=dialog.getBoundingClientRect(); if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom) dialog.close(); } });
  function details(table, row, key) {
    dialog.querySelector('h2').textContent = row ? row.model : table.columns.find(c => c.key === key).label;
    const fields = table.columns.filter(c => key ? c.key === key : true);
    const field = column => {
      const cell = row?.cells[column.key] || {}, value = row ? valueOf(row, column.key, table) : column.source_label;
      const cellURL = doc.source.tab_url + '&range=' + column.key + (row?.source_row || 1);
      return `<div class="aio-field"><dt>${e(column.label)}</dt><dd>${e(value || '—')}${cell.note ? `<p class="aio-cell-note">${e(cell.note)}</p>` : ''}${column.note ? `<p class="aio-field-note">${e(column.note)}</p>` : ''}${(cell.links || []).map(url => `<p>${link(url, publicData ? '출처 열기' : url)}</p>`).join('')}${publicData ? '' : `<small>${link(cellURL, `시트 ${column.key}${row?.source_row || 1} 확인`)}</small>`}</dd></div>`;
    };
    dialog.querySelector('.aio-dialog-body').innerHTML = `${row ? `<p class="aio-detail-provider">${e(row.provider || '기업 미기재')}${row.provider_derived ? ' · 같은 시트 블록의 기업명으로 표시' : ''}</p>` : ''}<dl>${fields.map(field).join('')}</dl>`;
    dialog.showModal();
  }
  for (const table of doc.tables) {
    const panel = document.createElement('section'); panel.className = 'aio-panel'; panel.dataset.table = table.id;
    const providers = [...new Set(table.rows.map(r => r.provider).filter(Boolean))];
    panel.innerHTML = `<div class="aio-panel-head"><h3>${e(table.title)}</h3><span>${table.columns.length}개 열</span></div><p class="aio-unit">${e(table.unit_note)}</p>
      <div class="aio-controls"><label>기업<select data-provider aria-label="${e(table.title)} 기업"><option value="">전체 기업</option>${providers.map(p=>`<option value="${e(p)}">${e(p)}</option>`).join('')}</select></label>
      <label class="aio-search">검색<input type="search" placeholder="모델·기업·사양 검색" aria-label="${e(table.title)} 검색"></label>
      ${table.views.length > 1 ? `<label>열 보기<select data-view aria-label="${e(table.title)} 열 보기">${table.views.map(v => `<option value="${e(v.id)}">${e(v.label)}</option>`).join('')}</select></label>` : ''}
      <button type="button" data-reset>초기화</button><button type="button" data-csv>CSV 저장</button></div>
      <div class="aio-status"><span role="status" aria-live="polite"></span><span>열 제목으로 정렬 · 설명이 있는 값은 클릭해서 확인</span></div>
      <div class="aio-scroll" tabindex="0" role="region" aria-label="${e(table.title)} 비교표, 가로·세로 스크롤 가능"><table></table></div>`;
    root.querySelector('.aio-tables').append(panel);
    const provider = panel.querySelector('[data-provider]'), search = panel.querySelector('input'), view = panel.querySelector('[data-view]'), element = panel.querySelector('table');
    const byID = new Map(table.rows.map(row => [row.id, row]));
    let sort = '', direction = 1, visible = [], columns = [];
    function draw() {
      const keys = table.views.find(v => v.id === view?.value)?.keys || table.views[0].keys;
      columns = keys.map(k => table.columns.find(c => c.key === k));
      visible = selectRows(table, {provider:provider.value, search:search.value, sort, direction});
      const fixed = column => column.key === table.provider_key ? 'aio-provider' : column.key === table.model_key ? 'aio-model' : column.key === table.date_key ? 'aio-date' : '';
      element.innerHTML = `<caption class="aio-sr">${e(table.title)}. ${publicData ? '대시는 확인되지 않은 값입니다.' : '빈칸은 미기재이며 가격과 점수는 원본 단위입니다.'}</caption><colgroup>${columns.map(c => `<col style="width:${c.key === table.model_key ? "var(--aio-model-width,210px)" : c.width+"px"}">`).join('')}<col style="width:64px"></colgroup><thead><tr>${columns.map(c => `<th scope="col" class="${fixed(c)}" aria-sort="${sort === c.key ? direction === 1 ? 'ascending' : 'descending' : 'none'}"><div><button type="button" data-sort="${e(c.key)}">${e(c.label)}${sort === c.key ? direction === 1 ? ' ↑' : ' ↓' : ''}</button>${c.note ? `<button type="button" class="aio-info" data-header="${e(c.key)}" aria-label="${e(c.label)} 설명">ⓘ</button>` : ''}</div></th>`).join('')}<th scope="col" class="aio-details">상세</th></tr></thead><tbody>${visible.length ? visible.map((row, index) => {
        const group = !sort && row.group && (index === 0 || visible[index-1].group !== row.group) ? `<tr class="aio-group"><th colspan="${columns.length+1}" scope="rowgroup">${e(row.group)}</th></tr>` : '';
        return group + `<tr data-row="${e(row.id)}">${columns.map(c => {
          const cell = row.cells[c.key] || {}, value = valueOf(row, c.key, table), actionable = c.key === table.model_key || cell.note || cell.links?.length;
          return `<td class="${fixed(c)}${typeof cell.number === 'number' ? ' aio-number' : ''}">${actionable ? `<button type="button" class="aio-value${cell.note || cell.links?.length ? ' aio-annotated' : ''}" data-field="${e(c.key)}" aria-label="${e(row.model+' · '+c.label+' 상세')}">${e(value || '—')}</button>` : `<span>${e(value || '—')}</span>`}</td>`;
        }).join('')}<td class="aio-details"><button type="button" data-detail aria-label="${e(row.model)} 전체 상세">상세</button></td></tr>`;
      }).join('') : `<tr><td colspan="${columns.length+1}" class="aio-empty">검색 결과가 없습니다. 검색어나 기업 필터를 바꿔 주세요.</td></tr>`}</tbody>`;
      element.style.width = `calc(${columns.reduce((s,c) => s + (c.key === table.model_key ? 0 : c.width), 64)}px + var(--aio-model-width,210px))`;
      panel.querySelector('[role="status"]').textContent = `${visible.length} / ${table.rows.length}개 모델 · ${columns.length}개 열 표시`;
    }
    element.onclick = event => {
      const button = event.target.closest('button'); if (!button) return;
      if (button.dataset.sort) { direction = sort === button.dataset.sort ? -direction : 1; sort = button.dataset.sort; draw(); element.querySelector(`[data-sort="${sort}"]`).focus({preventScroll:true}); return; }
      if (button.dataset.header) { details(table, null, button.dataset.header); return; }
      const row = byID.get(button.closest('tr')?.dataset.row); if (row) details(table, row, button.hasAttribute('data-detail') || button.dataset.field === table.model_key ? null : button.dataset.field);
    };
    provider.onchange = draw; search.oninput = draw;
    if (view) view.onchange = () => { panel.querySelector('.aio-scroll').scrollLeft = 0; draw(); };
    panel.querySelector('[data-reset]').onclick = () => { provider.value = ''; search.value = ''; if(view) view.selectedIndex = 0; sort = ''; direction = 1; panel.querySelector('.aio-scroll').scrollLeft = 0; draw(); };
    panel.querySelector('[data-csv]').onclick = () => {
      const url = URL.createObjectURL(new Blob([csvText(table, visible, columns)], {type:'text/csv;charset=utf-8'}));
      const a = document.createElement('a'); a.href = url; a.download = `${doc.id}-${table.id}-${doc.imported}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    draw();
  }
  return root;
}

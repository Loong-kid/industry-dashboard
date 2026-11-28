/* Head-to-head matrix for one process (전공정 세부): rows = application groups, columns = makers.
   Reads the same official-spec doc as the detail table below it (rows[].reviews, groups, company_order, countries). */
const value = (row, key) => row.reviews?.[key]?.value || '';

export function renderProcessMatrix(doc) {
  const card = document.createElement('div');
  card.className = 'card process-matrix';
  if (!doc) return card;
  card.dataset.processMatrix = doc.id;
  const esc = window.escapeHtml || (s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])));
  const groups = doc.groups || [...new Set(doc.rows.map(r => r.group))];
  const companies = doc.company_order || [...new Set(doc.rows.map(r => r.company))];
  const countries = doc.countries || {};
  const year = row => (value(row, 'launched').match(/^\d{4}/) || [''])[0];
  const status = row => value(row, 'status');
  const item = row => {
    const y = year(row), s = status(row), dev = s && s !== '판매 중';
    const tag = dev ? `<small class="process-matrix-tag">${esc(s.replace(/\s*\(.*\)$/, ''))}</small>` : y ? `<small>${esc(y)}</small>` : '<small class="process-matrix-none">출시 미확인</small>';
    const title = [value(row, 'method'), value(row, 'apps')].filter(Boolean).join(' · ');
    return `<li title="${esc(title)}"><span>${esc(row.name)}</span>${tag}</li>`;
  };
  const sortKey = row => year(row) || '0000';
  const cell = (group, company) => {
    const items = doc.rows.filter(r => r.group === group && r.company === company).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
    return items.length ? `<ul>${items.map(item).join('')}</ul>` : '<span class="process-matrix-empty" aria-label="없음">—</span>';
  };
  const counts = Object.fromEntries(companies.map(c => [c, doc.rows.filter(r => r.company === c).length]));
  card.innerHTML = `<div class="process-matrix-head"><div class="card-name">${esc(doc.short_name || doc.name)} · 업체별 대결표</div>
    <p>분야(줄)마다 각 업체가 내놓은 장비와 출시 연도입니다. 최신 장비가 위에 옵니다. 장비 이름에 마우스를 올리면 방식·용도가, 아래 표에서 세부 내용과 근거가 나옵니다.</p></div>
    <div class="process-matrix-scroll" role="region" tabindex="0" aria-label="${esc(doc.short_name || doc.name)} 업체별 대결표 · 가로 스크롤">
    <table><thead><tr><th scope="col">분야</th>${companies.map(c => `<th scope="col"><span>${esc(c)}</span><small>${esc(countries[c] || '')} · ${counts[c]}개</small></th>`).join('')}</tr></thead>
    <tbody>${groups.map(g => `<tr><th scope="row">${esc(g)}</th>${companies.map(c => `<td>${cell(g, c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  return card;
}

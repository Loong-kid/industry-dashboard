/* MOCVD disclosure tables: preserve announced plans and exact source scope. */
function renderMOCVDGuide() {
  const guide = document.createElement('section');
  guide.className = 'mocvd-guide';
  guide.setAttribute('aria-label', 'MOCVD 투자와 장비 수주의 연결');
  guide.innerHTML = `<h2>광학·전력 투자에서 장비 수주까지</h2>
    <ol class="mocvd-cycle">
      <li><strong>투자·증설 계획</strong><span>고객 CAPEX 전망·생산능력 목표</span></li>
      <li><strong>장비 발주</strong><span>공급사 수주액·선수금·잔고</span></li>
      <li><strong>인도·검수</strong><span>장비 매출·공개된 인도 기록</span></li>
      <li><strong>생산 확대</strong><span>양산 시작·가동률·웨이퍼 직경</span></li>
    </ol>
    <p>현금 CAPEX는 여러 단계에 걸쳐 발생하므로 장비 수주보다 늦을 수 있습니다. 회사 전체 투자액과 InP·GaN 전용 투자를 구분해서 봅니다.</p>
    <details><summary>매출·대수를 비교하는 기준</summary>
      <p>InP·GaN MOCVD와 SiC CVD는 공정과 고객 수요가 다릅니다. AIXTRON 광전자 매출은 InP 단독이 아니며, Veeco Compound Semiconductor에는 MOCVD 외 장비도 포함됩니다.</p>
      <p>신규 출하·누적 설치·시스템·챔버 수를 섞지 않습니다. 확인되지 않은 출하대수는 매출÷임의 단가로 채우지 않습니다. 통화가 다른 매출을 합산해 시장 규모로 표시하지 않습니다.</p>
    </details>`;
  return guide;
}

function renderMOCVDTable(doc) {
  const card = document.createElement('div');
  card.className = 'card mocvd-table';
  if (!doc) return card;
  const esc = escapeHtml;
  card.innerHTML = `<div class="card-name">${esc(doc.name)}</div>
    <p class="ir-scope-note">${esc(doc.description)}</p>
    <div class="mocvd-table-controls">
      <label>회사 <select aria-label="${esc(doc.name)} 회사"><option value="">전체</option></select></label>
      <label>검색 <input type="search" aria-label="${esc(doc.name)} 검색" placeholder="InP, 300mm, 발주…"></label>
      <span class="mocvd-count" aria-live="polite"></span>
    </div>
    <div class="order-table-wrap" tabindex="0" role="region" aria-label="${esc(doc.name)} 표">
      <table><thead><tr>${doc.columns.map(([,label])=>`<th scope="col">${esc(label)}</th>`).join('')}<th scope="col">공식 원문</th></tr></thead><tbody></tbody></table>
    </div>
    <p class="ir-scope-note">${esc(doc.note)}</p>
    <p class="ir-scope-note">원문 검토: ${esc(doc.fetched)} · 기록표는 전체 이력이며 상단 기간 선택은 그래프에 적용됩니다.</p>`;
  const select = card.querySelector('select');
  for (const name of [...new Set(doc.rows.map(r=>r.company))]) {
    const option = document.createElement('option');
    option.value = option.textContent = name;
    select.appendChild(option);
  }
  const search = card.querySelector('input');
  const render = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const rows = doc.rows.filter(r=>(!select.value || r.company === select.value) &&
      (!query || doc.columns.map(([key])=>r[key]||'').join(' ').toLocaleLowerCase().includes(query)));
    card.querySelector('.mocvd-count').textContent = `${rows.length} / ${doc.rows.length}건`;
    card.querySelector('tbody').innerHTML = rows.length ? rows.map(r=>`<tr>
      ${doc.columns.map(([key])=>`<td>${esc(r[key]||'—')}</td>`).join('')}
      <td>${/^https:\/\//.test(r.url||'') ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">원문 ↗</a>` : '미확인'}${/^https:\/\//.test(r.supporting_url||'') ? `<br><a href="${esc(r.supporting_url)}" target="_blank" rel="noopener">추가 원문 ↗</a>` : ''}</td>
    </tr>`).join('') : `<tr><td colspan="${doc.columns.length+1}">검색 결과가 없습니다.</td></tr>`;
  };
  select.addEventListener('change', render);
  search.addEventListener('input', render);
  render();
  return card;
}

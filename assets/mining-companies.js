"use strict";

function renderMiningCompanies(doc) {
  if (!document.querySelector('link[data-mining-style]')) {
    const link = document.createElement('link'); link.rel = 'stylesheet'; link.href = 'assets/mining-companies.css'; link.dataset.miningStyle = 'true'; document.head.appendChild(link);
  }
  const root = document.createElement('section'); root.className = 'mining-overview';
  const heading = document.createElement('h2'); heading.textContent = '글로벌 광산기업 · 시가총액 상위 10'; root.appendChild(heading);
  const method = document.createElement('p'); method.className = 'mining-method'; method.textContent = doc.methodology; root.appendChild(method);
  const wrap = document.createElement('div'); wrap.className = 'order-table-wrap';
  const table = document.createElement('table'); table.className = 'order-table mining-table';
  const caption = document.createElement('caption'); caption.textContent = `시가총액 조회 ${doc.ranking_date} · 광물 비중은 행별 공시 기간·분모 기준`; table.appendChild(caption);
  const head = document.createElement('thead'); const hr = document.createElement('tr');
  for (const text of ['순위', '기업', '시가총액', '광물·사업별 매출 구성', '비중 기준', '원문']) { const th = document.createElement('th'); th.scope = 'col'; th.textContent = text; hr.appendChild(th); }
  head.appendChild(hr); table.appendChild(head); const body = document.createElement('tbody');
  const colors = {copper:'#b76d44',gold:'#b59c39',iron:'#657b88',silver:'#8d9dab',molybdenum:'#8774a6',zinc:'#61947f',aluminium:'#649cb3',coal:'#62686f',energy:'#797b52',other:'#95918b',mining:'#a67d50'};
  for (const company of doc.companies) {
    const row = document.createElement('tr'); row.dataset.company = company.id;
    const rank = document.createElement('td'); rank.textContent = company.rank; row.appendChild(rank);
    const name = document.createElement('th'); name.scope = 'row';
    const jump = document.createElement('button'); jump.type = 'button'; jump.className = 'mining-jump'; jump.textContent = company.name;
    jump.addEventListener('click', () => document.getElementById(`mining-${company.id}`)?.scrollIntoView({behavior:'auto',block:'start'}));
    const ticker = document.createElement('span'); ticker.className = 'mining-ticker'; ticker.textContent = company.ticker; name.append(jump,ticker); row.appendChild(name);
    const cap = document.createElement('td'); cap.className = 'mining-cap'; cap.textContent = `$${company.market_cap_usd_billion.toFixed(2)}B`; row.appendChild(cap);
    const mix = document.createElement('td'); const bar = document.createElement('div'); bar.className = 'mining-mix-bar'; bar.setAttribute('aria-hidden','true');
    const labels = document.createElement('div'); labels.className = 'mining-mix-labels';
    for (const part of company.mix.parts) {
      const color=colors[part.key] || colors.other;
      const segment=document.createElement('span'); segment.style.width=`${part.percent}%`; segment.style.backgroundColor=color; bar.appendChild(segment);
      const label=document.createElement('span'); const dot=document.createElement('i'); dot.style.backgroundColor=color; label.append(dot,document.createTextNode(`${part.label} ${part.percent.toFixed(1)}%`)); labels.appendChild(label);
    }
    if (company.mix.parts.length) mix.append(bar,labels);
    else mix.textContent='광물별 매출 비중 미공시';
    const note=document.createElement('p'); note.className='mining-row-note'; note.textContent=company.mix.note || ''; mix.appendChild(note); row.appendChild(mix);
    const basis=document.createElement('td'); const period=document.createElement('strong'); period.textContent=company.mix.period;
    const scope=document.createElement('p'); scope.textContent=company.mix.basis; basis.append(period,scope); row.appendChild(basis);
    const source=document.createElement('td');
    for (const [i,item] of company.mix.sources.entries()) {
      if (!/^https:\/\//.test(item.url)) continue;
      const a=document.createElement('a'); a.href=item.url; a.target='_blank'; a.rel='noopener'; a.textContent=item.label || `공시 ${i+1}`; source.appendChild(a);
    }
    row.appendChild(source); body.appendChild(row);
  }
  table.appendChild(body); wrap.appendChild(table); root.appendChild(wrap);
  const note=document.createElement('p'); note.className='mining-method'; note.textContent=doc.ownership_note; root.appendChild(note);
  const a=document.createElement('a'); a.href=doc.ranking_source_url; a.target='_blank'; a.rel='noopener'; a.textContent=`시가총액 순위 출처 · 조회일 ${doc.ranking_date}`; root.appendChild(a);
  return root;
}

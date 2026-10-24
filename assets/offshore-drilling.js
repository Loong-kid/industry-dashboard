"use strict";

// Offshore watch: issuer snapshots, physical assets, contracts, and ownership
// remain separate. Source month/quarter precision is preserved in every view.
const OF_TYPES = {drillship: "드릴십", semi: "반잠수식", jackup: "잭업"};
const OF_KINDS = {firm: "확정", option: "선택권", contingent: "조건부", loa: "LOA", maintenance: "정비·준비"};
const OF_LOCATIONS = {USGOM: "미국 멕시코만", "US Gulf": "미국 멕시코만", "U.S. Gulf": "미국 멕시코만", "Gulf of America": "미국 멕시코만", Norway: "노르웨이", "United Kingdom": "영국", UK: "영국", Brazil: "브라질", Guyana: "가이아나", Suriname: "수리남", Angola: "앙골라", Namibia: "나미비아", Mexico: "멕시코", Malaysia: "말레이시아", Vietnam: "베트남", Thailand: "태국", "Saudi Arabia": "사우디아라비아", "United Arab Emirates": "아랍에미리트", Netherlands: "네덜란드", "Ivory Coast": "코트디부아르", "Cote d'Ivoire": "코트디부아르", Australia: "호주", India: "인도", Nigeria: "나이지리아", Gabon: "가봉", Singapore: "싱가포르", Brunei: "브루나이", Libya: "리비아", Romania: "루마니아", Ghana: "가나", Colombia: "콜롬비아", Trinidad: "트리니다드", Egypt: "이집트", Poland: "폴란드", "South America": "남미", "Asia Pac": "아시아·태평양", "Eastern Med": "동지중해", Spain: "스페인", "Las Palmas": "스페인 라스팔마스", "United States of America": "미국", Undisclosed: "미공개"};
function ofEl(tag, cls, text) { const el = document.createElement(tag); if (cls) el.className = cls; if (text != null) el.textContent = String(text); return el; }
function ofNum(value, suffix = "", digits = 1) { return value == null ? "—" : Number(value).toLocaleString("ko-KR", {maximumFractionDigits: digits}) + suffix; }
function ofLocation(value) { return OF_LOCATIONS[value] || value || "미공개"; }
function ofLink(url, title) { try { const u = new URL(url); if (!['http:', 'https:'].includes(u.protocol)) throw new Error(); const a = ofEl('a', '', title); a.href = u.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; } catch { return ofEl('span', '', title); } }
function ofStorage(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }
function ofSave(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} }
function ofDate(value) { if (!value?.min) return value?.text || "미공개"; return value.precision === 'month' ? value.min.slice(0, 7) : value.precision === 'quarter' ? `${value.min.slice(0, 4)} Q${Math.ceil(Number(value.min.slice(5, 7))/3)}` : value.precision === 'half_year' ? `${value.min.slice(0,4)} ${value.min.slice(5,7)==='01'?'상반기':'하반기'}` : value.text; }
function ofCard(title) { const card = ofEl('section', 'card of-panel'); card.appendChild(ofEl('h2', 'card-name', title)); return card; }
function ofNote(parent, text, warning = false) { parent.appendChild(ofEl('p', warning ? 'of-note of-warning' : 'of-note', text)); }
function ofSource(parent, source) { if (!source) return; const p = ofEl('p', 'of-source'); p.append(`${source.as_of || '기준일 미기재'} · `, ofLink(source.url, source.title || '공식 원문')); parent.appendChild(p); }
function ofButton(label, fn, cls = 'of-button') { const b = ofEl('button', cls, label); b.type = 'button'; b.addEventListener('click', fn); return b; }
function ofSelect(parent, label, options, value, change) { const field = ofEl('label', 'of-field', label), input = ofEl('select'); input.setAttribute('aria-label', label); for (const [id, name] of options) { const o = ofEl('option', '', name); o.value = id; input.appendChild(o); } input.value = value; input.addEventListener('change', () => change(input.value)); field.appendChild(input); parent.appendChild(field); return input; }
function ofStatusNote(parent, doc) { if (doc.collection_status && !doc.collection_status.ok) ofNote(parent, `${doc.collection_status.checked} 확인 · 일부 출처는 마지막 자료를 유지합니다. 설비별 기준일과 아래 확인 범위를 참고하세요.`, true); }

function renderOffshoreMarket(doc) {
  const card = ofCard('세계 선대와 공개 계약');
  if (!doc) { ofNote(card, '자료를 불러오지 못했습니다. 새로고침해 주세요.', true); return card; }
  const latest = [...new Set(doc.rows.map(r => r.date))].sort().pop();
  ofNote(card, `${latest?.slice(0, 7) || '미확보'} 활동 기준 · 계약 확보에는 미래 일감이 포함됩니다. 실제 작업 중인 대수와 구분합니다.`);
  const wrap = ofEl('div', 'of-scroll'), table = ofEl('table', 'of-market-table'), head = ofEl('thead'), body = ofEl('tbody'), hr = ofEl('tr');
  for (const name of ['리그 유형', '계약 확보', '영업 중 대기', '장기 계선', '영업 대상 확보율']) hr.appendChild(ofEl('th', '', name)); head.appendChild(hr);
  for (const [type, label] of Object.entries(OF_TYPES)) {
    const r = doc.rows.find(r => r.type === type && r.date === latest); if (!r) continue;
    const tr = ofEl('tr'); tr.append(ofEl('th', '', label), ...['committed', 'available', 'cold_stacked'].map(k => ofEl('td', 'of-number', ofNum(r[k], '기', 0))));
    const td = ofEl('td', 'of-number'); td.appendChild(ofEl('strong', '', ofNum(r.committed_utilization, '%'))); const bar = ofEl('div', 'of-meter'); bar.setAttribute('aria-hidden', 'true'); const fill = ofEl('span'); fill.style.width = `${Math.max(0, Math.min(100, r.committed_utilization))}%`; bar.appendChild(fill); td.appendChild(bar); tr.appendChild(td); body.appendChild(tr);
  }
  table.append(head, body); wrap.appendChild(table); card.appendChild(wrap);
  ofNote(card, '확보율 = 공개 대수의 계약 확보 ÷ (계약 확보 + 영업 중 대기). 원문에 제시된 반올림 비율과 다를 수 있습니다. 장기 계선은 분모에서 제외합니다.');
  ofSource(card, doc.market_source);
  if (doc.market_status && !doc.market_status.ok) ofNote(card, `${doc.market_status.checked} · ${doc.market_status.message}`, true);
  const title = ofEl('h3', 'of-subhead', '요율이 공개된 신규 계약 표본'); card.appendChild(title);
  ofNote(card, '공개된 개별 계약 사례입니다. 글로벌 평균 요율 지수로 해석하지 않습니다. 총 계약금액을 기간으로 나눠 비공개 요율을 추정하지 않습니다.');
  const fixtures = ofEl('div', 'of-fixtures');
  for (const f of doc.fixtures || []) {
    const row = ofEl('article', 'of-fixture'); row.append(ofEl('strong', '', f.rig), ofEl('span', 'of-secondary', `${OF_TYPES[f.type]} · ${ofLocation(f.location)} · ${f.customer}`), ofEl('strong', 'of-fixture-rate', ofNum(f.dayrate_usd, ' USD/일', 0)), ofEl('span', 'of-secondary', `발표 ${f.date} · 개시 ${f.start}`), ofLink(f.source?.url, '계약 원문')); fixtures.appendChild(row);
  }
  card.appendChild(fixtures); return card;
}

function ofRigDetail(row, trigger, companies) {
  const dialog = ofEl('dialog', 'of-dialog'); dialog.setAttribute('aria-label', `${row.name} 리그 상세`);
  const heading = ofEl('div', 'of-dialog-head'); heading.append(ofEl('h2', '', row.name), ofButton('닫기', () => dialog.close())); dialog.appendChild(heading);
  const dl = ofEl('dl');
  for (const [label, text] of [
    ['운영 그룹', companies[row.company]?.name], ['유형', OF_TYPES[row.type]], ['소유 그룹·법인', row.owner_group], ['소유 지분', row.ownership_pct == null ? '미공개 · 100%로 간주하지 않음' : row.ownership_pct+'%'],
    ['운영·관리', row.manager], ['소유 기준', row.ownership_basis], ['보고서 작업 해역', ofLocation(row.location)], ['웹 공시 고객', row.customer_reported || '—'], ['공시 기준 상태', row.status], ['기준일', row.as_of], ['건조연도', row.built || '미확인'], ['설계', row.design || '미확인'], ['최대 작업수심', ofNum(row.water_depth_ft, ' ft', 0)],
    ['12개월 커버리지', ofNum(row.coverage_12m, '%')], ['24개월 커버리지', ofNum(row.coverage_24m, '%')]
  ]) dl.append(ofEl('dt', '', label), ofEl('dd', '', text || '미확인'));
  dialog.appendChild(dl); ofNote(dialog, row.coverage_basis); ofNote(dialog, '작업 해역은 보고서·계약의 표기입니다. 실시간 AIS 위치가 아니며, 과거 공시만으로 오늘의 실제 작업 여부를 단정하지 않습니다.');
  if (row.notes) ofNote(dialog, row.notes);
  dialog.appendChild(ofEl('h3', 'of-subhead', '공개된 계약 일정'));
  if (!row.contracts.length) ofNote(dialog, '개별 계약 기간·요율이 공개되지 않았거나 이번 자료에서 확인되지 않았습니다.');
  for (const c of row.contracts) {
    const box = ofEl('article', 'of-contract-detail'); box.append(ofEl('strong', '', `${OF_KINDS[c.kind] || c.kind} · ${c.customer || '고객 미공개'}`), ofEl('p', '', `${ofLocation(c.location)} · ${ofDate(c.start)} ~ ${ofDate(c.end)}`), ofEl('p', '', c.dayrate_usd == null ? '일당 요율 미공개' : ofNum(c.dayrate_usd, ' USD/일', 0)));
    if (c.note) box.appendChild(ofEl('p', 'of-secondary', c.note)); dialog.appendChild(box);
  }
  dialog.appendChild(ofEl('h3', 'of-subhead', '확인 자료'));
  for (const s of row.sources) ofSource(dialog, s);
  document.body.appendChild(dialog); dialog.addEventListener('close', () => { dialog.remove(); trigger?.focus(); });
  dialog.addEventListener('click', event => { if (event.target === dialog) { const b = dialog.getBoundingClientRect(); if (event.clientX < b.left || event.clientX > b.right || event.clientY < b.top || event.clientY > b.bottom) dialog.close(); } }); dialog.showModal();
}

function ofFiltered(rows, filter, favorites) {
  const q = filter.search.trim().toLocaleLowerCase();
  return rows.filter(r => (!filter.company || r.company === filter.company) && (!filter.type || r.type === filter.type)
    && (!filter.location || ofLocation(r.location) === filter.location) && (!filter.status || r.status === filter.status)
    && (filter.showRetired || !['매각·퇴역','매각 대기'].includes(r.status)) && (!filter.favorites || favorites.has(r.id))
    && (!q || [r.name,r.location,ofLocation(r.location),r.manager,r.owner_group,r.current_contract?.customer,r.next_contract?.customer,...r.contracts.map(c => c.customer)].join(' ').toLocaleLowerCase().includes(q)));
}

function renderOffshoreFleet(doc, timeline = false) {
  const card = ofCard(timeline ? '리그별 계약 일정' : '글로벌 리그 목록'); card.className += ' of-monitor';
  if (!doc) { ofNote(card, '자료를 불러오지 못했습니다. 새로고침해 주세요.', true); return card; }
  const defaults = {company:'',type:'',location:'',status:'',search:'',favorites:false,showRetired:false,compact:false,sort:'name',direction:1};
  const saved = ofStorage('offshore-view-v1', {}); const filter = {...defaults, ...(saved && typeof saved === 'object' ? saved : {}), search:''};
  const storedFavorites = ofStorage('offshore-favorites-v1', []), favorites = new Set(Array.isArray(storedFavorites) ? storedFavorites : []);
  const rows = doc.rows, controls = ofEl('div', 'of-controls'), output = ofEl('p', 'of-count'); output.setAttribute('role', 'status');
  ofNote(card, '소유 그룹·관리사·고객을 구분합니다. 각 행의 공시 기준 상태이며 오늘의 실제 가동 상태는 달라질 수 있습니다.');
  ofSelect(controls, '운영 그룹', [['','전체 6개 그룹'],...Object.entries(doc.companies).map(([id,c]) => [id,c.name])], filter.company, v => { filter.company=v;render(); });
  ofSelect(controls, '리그 유형', [['','전체 유형'],...Object.entries(OF_TYPES)], filter.type, v => { filter.type=v;render(); });
  ofSelect(controls, '작업 해역', [['','전체 해역'],...[...new Set(rows.map(r => ofLocation(r.location)))].sort().map(v => [v,v])], filter.location, v => { filter.location=v;render(); });
  ofSelect(controls, '공시 기준 상태', [['','전체 상태'],...[...new Set(rows.map(r => r.status))].sort().map(v => [v,v])], filter.status, v => { filter.status=v;render(); });
  const searchLabel = ofEl('label', 'of-field of-search', '검색'), search = ofEl('input'); search.type='search'; search.placeholder='리그·소유사·고객 검색'; search.setAttribute('aria-label','리그·소유사·고객 검색'); search.addEventListener('input', () => { filter.search=search.value;render(); }); searchLabel.appendChild(search); controls.appendChild(searchLabel);
  const toolbar = ofEl('div', 'of-toolbar');
  const watchOnly = ofButton('관심 리그', () => { filter.favorites=!filter.favorites;render(); });
  const retired = ofButton('매각·퇴역 이력 포함', () => { filter.showRetired=!filter.showRetired;render(); });
  const compact = ofButton('행 간격: 기본', () => { filter.compact=!filter.compact;render(); });
  toolbar.append(watchOnly, retired, compact); card.append(controls, toolbar, output);
  const wrap = ofEl('div', 'of-scroll of-fleet-scroll'); wrap.tabIndex=0; wrap.setAttribute('aria-label', timeline ? '계약 일정표, 가로로 스크롤할 수 있습니다' : '리그 목록, 가로로 스크롤할 수 있습니다'); card.appendChild(wrap);
  if (timeline) ofNote(card, '파란 막대는 확정 계약, 점선은 선택권·조건부 계약, 회색은 정비·준비입니다. 월·분기 표기는 해당 기간 범위를 그리며 정확한 시작·종료일을 뜻하지 않습니다. 막대를 누르면 원문 표기를 볼 수 있습니다.');
  else ofNote(card, '일당은 공개 계약 요율(USD)입니다. —는 미공개이며 0이 아닙니다. ☆ 관심 목록과 필터 설정은 이 브라우저에 저장됩니다.');
  const details = ofEl('details', 'of-provenance'); details.appendChild(ofEl('summary', '', '6개사 수집·확인 범위'));
  for (const [id,status] of Object.entries(doc.company_status || {})) {
    const p = ofEl('p', status.ok && !status.review_needed ? '' : 'of-warning');
    p.appendChild(ofEl('strong','',doc.companies[id]?.name || id)); p.append(` · 선대 기준 ${status.as_of || '미기재'} · 확인 ${status.checked || '미기재'} · ${status.mode === 'reviewed_transcription' ? '공식 FSR 대조 입력·새 보고서 검토' : '공개 원문 수집'}`);
    if (!status.ok) p.append(' · 출처 확인 실패, 마지막 자료 유지');
    if (status.review_needed) p.append(' · 새 공시 검토 필요');
    details.appendChild(p);
    for (const pending of status.pending_reports || []) { const line=ofEl('p');line.append(`${pending.date} · `,ofLink(pending.url,pending.title));details.appendChild(line); }
  }
  ofNote(details, doc.scope); ofNote(details, doc.coverage_note); card.appendChild(details);
  function sortValue(row, key) {
    if (key==='rate') return row.current_contract?.dayrate_usd;
    if (key==='end') return row.current_contract?.end.min;
    if (key==='next') return row.next_contract?.start.min;
    if (key==='location') return ofLocation(row.location);
    return row[key];
  }
  function render() {
    ofSave('offshore-view-v1', {...filter,search:''});
    watchOnly.setAttribute('aria-pressed',String(filter.favorites)); retired.setAttribute('aria-pressed',String(filter.showRetired)); compact.setAttribute('aria-pressed',String(filter.compact)); compact.textContent=filter.compact?'행 간격: 촘촘':'행 간격: 기본';
    card.classList.toggle('of-compact',filter.compact);
    const selected=ofFiltered(rows,filter,favorites).sort((a,b) => { const x=sortValue(a,filter.sort),y=sortValue(b,filter.sort); if (x==null || x==='')return y==null||y===''?a.name.localeCompare(b.name):1;if(y==null||y==='')return -1;return (typeof x==='number'?x-y:String(x).localeCompare(String(y),'ko'))*filter.direction; });
    output.textContent=`${selected.length}기 표시 · 전체 기록 ${rows.length}기 · 타사 관리·JV 포함 · 공시일 기준`;
    wrap.replaceChildren();
    if (timeline) { renderTimeline(wrap,selected,doc,filter); return; }
    const table=ofEl('table','of-fleet-table'),colgroup=ofEl('colgroup'),head=ofEl('thead'),hr=ofEl('tr'),body=ofEl('tbody');
    const columns=[['watch','관심',44],['name','리그 · 운영 그룹',235],['type','유형·상태',120],['owner_group','소유 그룹 / 관리사',180],['location','작업 해역',130],['rate','계약 일당',122],['end','현재 계약 종료',118],['next','다음 계약 개시',118],['as_of','자료 기준',106]];
    for (const [key,label,width] of columns) { const col=ofEl('col');col.style.width=width+'px';colgroup.appendChild(col);const th=ofEl('th'); th.scope='col';
      if(key==='watch')th.textContent=label; else {const button=ofButton(label+(filter.sort===key?(filter.direction===1?' ↑':' ↓'):''),()=>{filter.direction=filter.sort===key?-filter.direction:1;filter.sort=key;render();wrap.querySelector(`[data-sort="${key}"]`)?.focus();},'of-sort');button.dataset.sort=key;th.appendChild(button);if(filter.sort===key)th.setAttribute('aria-sort',filter.direction===1?'ascending':'descending');} hr.appendChild(th); }
    head.appendChild(hr);table.append(colgroup,head,body);
    for (const row of selected) {
      const tr=ofEl('tr');tr.dataset.rigId=row.id;
      const td=ofEl('td'),watch=ofButton(favorites.has(row.id)?'★':'☆',()=>{favorites.has(row.id)?favorites.delete(row.id):favorites.add(row.id);ofSave('offshore-favorites-v1',[...favorites]);if(filter.favorites)render();else{watch.textContent=favorites.has(row.id)?'★':'☆';watch.setAttribute('aria-pressed',String(favorites.has(row.id)));}},'of-watch');watch.setAttribute('aria-label',`${row.name} 관심 리그`);watch.setAttribute('aria-pressed',String(favorites.has(row.id)));td.appendChild(watch);tr.appendChild(td);
      const name=ofEl('td'),nameButton=ofButton(row.name,()=>ofRigDetail(row,nameButton,doc.companies),'of-name');name.append(nameButton,ofEl('span','of-secondary',doc.companies[row.company]?.name));name.appendChild(ofEl('span','of-mobile-meta',`${OF_TYPES[row.type]} · ${ofLocation(row.location)} · ${row.status}`));tr.appendChild(name);
      const typ=ofEl('td');typ.append(ofEl('span','',OF_TYPES[row.type]),ofEl('span','of-secondary',row.status));tr.appendChild(typ);
      const owner=ofEl('td');owner.append(ofEl('span','',row.owner_group || '미확인'),ofEl('span','of-secondary',`관리 ${row.manager}${row.ownership_pct!=null?' · 지분 '+row.ownership_pct+'%':''}`));tr.appendChild(owner);
      tr.appendChild(ofEl('td','',ofLocation(row.location)));const rate=ofEl('td','of-number',ofNum(row.current_contract?.dayrate_usd,'',0));rate.appendChild(ofEl('span','of-secondary',row.current_contract?.dayrate_usd==null?'미공개':'USD/일'));tr.appendChild(rate);
      const end=ofEl('td','',ofDate(row.current_contract?.end));end.appendChild(ofEl('span','of-secondary',row.current_contract?.customer || ''));tr.appendChild(end);
      const next=ofEl('td','',ofDate(row.next_contract?.start));next.appendChild(ofEl('span','of-secondary',row.next_contract?.customer || ''));tr.appendChild(next);
      tr.appendChild(ofEl('td','',row.as_of));body.appendChild(tr);
    }
    if (!selected.length) {const tr=ofEl('tr'),td=ofEl('td','of-empty',filter.favorites?'조건에 맞는 관심 리그가 없습니다. ☆를 눌러 저장하세요.':'조건에 맞는 리그가 없습니다. 검색어나 필터를 바꿔 주세요.');td.colSpan=columns.length;tr.appendChild(td);body.appendChild(tr);}
    wrap.appendChild(table);
  }
  render();return card;
}

function renderTimeline(wrap, rows, doc) {
  const startYear=2026, start=Date.UTC(startYear,0,1), finish=Date.UTC(startYear+4,0,1), duration=finish-start;
  const table=ofEl('div','of-timeline');table.setAttribute('role','table');table.setAttribute('aria-label','2026~2029 계약 일정');
  const heading=ofEl('div','of-time-row of-time-heading'),name=ofEl('div','of-time-name','리그 · 공시 기준일'),axis=ofEl('div','of-time-axis');
  for (let m=0;m<48;m++) { const label=ofEl('span','',m%12===0?String(startYear+m/12):String(m%12+1));axis.appendChild(label); } heading.append(name,axis);table.appendChild(heading);
  for (const row of rows) {
    const line=ofEl('div','of-time-row'),label=ofEl('div','of-time-name'),button=ofButton(row.name,()=>ofRigDetail(row,button,doc.companies),'of-name');label.append(button,ofEl('span','of-secondary',`${doc.companies[row.company]?.name} · ${row.as_of}`));
    const track=ofEl('div','of-time-track');let shown=0;
    for (const c of row.contracts) {
      if (!c.start.min)continue;
      const openEnd=!c.end.max;
      const a=Math.max(start,Date.parse(c.start.min+'T00:00:00Z')),b=Math.min(finish,Date.parse((c.end.max || c.start.max)+'T00:00:00Z'));
      if(b<=a)continue;
      const bar=ofButton(`${openEnd?'개시 범위':OF_KINDS[c.kind] || c.kind} · ${c.customer || '미공개'}`,()=>ofRigDetail(row,bar,doc.companies),'of-time-bar of-kind-'+c.kind+(openEnd?' of-open-end':''));
      bar.style.left=`${(a-start)/duration*100}%`;bar.style.width=`${Math.max(.35,(b-a)/duration*100)}%`;bar.style.top=(shown%2?30:6)+'px';
      bar.title=`${row.name} · ${OF_KINDS[c.kind]} · ${c.customer} · ${ofDate(c.start)}~${ofDate(c.end)} · ${ofNum(c.dayrate_usd,' USD/일',0)}`;
      bar.setAttribute('aria-label',bar.title);track.appendChild(bar);shown++;
    }
    if(!shown)track.appendChild(ofEl('span','of-time-unavailable','공개 계약 기간 없음'));
    line.append(label,track);table.appendChild(line);
  }
  if(!rows.length)table.appendChild(ofEl('p','of-empty','조건에 맞는 계약 일정이 없습니다. 필터를 바꿔 주세요.'));
  wrap.appendChild(table);
}

function renderOffshoreFinancials(doc) {
  const panel=ofEl('section','of-financials');
  if(!doc) {ofNote(panel,'실적 자료를 불러오지 못했습니다. 새로고침해 주세요.',true);return panel;}
  const card=ofCard('운영사 최신 분기 실적');panel.appendChild(card);ofNote(card,doc.note);
  const wrap=ofEl('div','of-scroll'),table=ofEl('table','of-financial-table'),head=ofEl('thead'),hr=ofEl('tr'),body=ofEl('tbody');
  for(const label of ['회사 / 분기','매출','EBITDA¹','영업현금흐름','FCF²','순부채³','계약잔고³'])hr.appendChild(ofEl('th','',label));head.appendChild(hr);table.append(head,body);
  for(const company of doc.companies) {
    const last=[...company.quarters].reverse().find(q=>q.revenue!=null);if(!last)continue;
    const tr=ofEl('tr'),name=ofEl('th');name.scope='row';name.append(ofEl('strong','',company.name),ofEl('span','of-secondary',`${last.date.slice(0,4)} Q${Math.ceil(Number(last.date.slice(5,7))/3)}`));tr.appendChild(name);
    for(const key of ['revenue','ebitda','operating_cash','fcf','net_debt','backlog']) {const td=ofEl('td','of-number',ofNum(last[key]));
      if(key==='ebitda')td.appendChild(ofEl('span','of-secondary',last.ebitda_label || '미확보'));
      if(key==='backlog' && last.backlog_date)td.appendChild(ofEl('span','of-secondary',last.backlog_date));
      if(key==='fcf' && last.fcf!=null)td.appendChild(ofEl('span','of-secondary',company.id==='noble'?'회사 공시':'CFO−PPE 현금취득'));
      tr.appendChild(td);}
    if(last.note)tr.title=last.note;body.appendChild(tr);
  }
  wrap.appendChild(table);card.appendChild(wrap);
  ofNote(card,'단위: USD 백만. ¹ Odfjell은 공시 EBITDA, 나머지는 조정 EBITDA입니다. ² 회사 공시 FCF와 계산 FCF를 구분합니다. ³ 회사 정의의 순부채·계약잔고이며 일괄 합산하지 않습니다. Borr 잔고는 Dayrate Equivalent 기준입니다.');
  const controls=ofEl('div','of-controls'),chartHost=ofEl('div','grid of-financial-charts'),notes=ofEl('div','of-financial-notes');panel.append(controls,chartHost,notes);
  const metrics={revenue:'매출',operating_profit:'영업이익',net_income:'순이익',ebitda:'EBITDA / 조정 EBITDA',operating_cash:'영업현금흐름',capex:'유형자산 현금취득',fcf:'잉여현금흐름',dayrate:'평균 계약 일당',efficiency_pct:'매출 효율 / 경제적 가동률'};
  const saved=ofStorage('offshore-financial-view-v1',{});
  let companyId=doc.companies.some(c=>c.id===saved?.companyId)?saved.companyId:'',ownedCharts=[];
  ofSelect(controls,'실적 비교 대상',[['','6개사 비교'],...doc.companies.map(c=>[c.id,c.name])],companyId,v=>{companyId=v;render();});
  function render() {
    ofSave('offshore-financial-view-v1',{companyId});
    for(const c of ownedCharts)c.destroy();if(typeof state!=='undefined')state.charts=state.charts.filter(c=>!ownedCharts.includes(c));ownedCharts=[];
    chartHost.replaceChildren();notes.replaceChildren();const selected=doc.companies.filter(c=>!companyId||c.id===companyId);
    const dates=[...new Set(selected.flatMap(c=>c.quarters.map(q=>q.date)))].sort();
    for(const [metric,label] of Object.entries(metrics)) {
      const series={};for(const c of selected) {if(c.quarters.some(q=>q[metric]!=null))series[c.name]=dates.map(date=>[date,c.quarters.find(q=>q.date===date)?.[metric]??null]);}
      if(!Object.keys(series).length){const empty=ofCard(label);ofNote(empty,'해당 기업의 공시 수치를 아직 확보하지 못했습니다.');chartHost.appendChild(empty);continue;}
      const unit=metric==='dayrate'?'USD/일':metric==='efficiency_pct'?'%':'USD 백만';
      const synthetic={id:'offshore-financial-'+metric,name:label,unit,frequency:'quarterly',quarter_labels:true,series,default_series:Object.keys(series),span_gaps:false,change_mode:'none',
        source:'SEC·기업 공식 분기 실적',source_url:selected[0]?.status?.source_url || selected[0]?.index,
        updated:dates.at(-1),description:'확보한 분기만 표시하며 누락 분기는 선을 끊습니다. 인수합병·연결 범위 변화가 포함됩니다. EBITDA·가동률은 아래 회사별 정의를 함께 확인하세요.'};
      const before=typeof state!=='undefined'?state.charts.length:0;chartHost.appendChild(renderCard(synthetic,synthetic.id));if(typeof state!=='undefined')ownedCharts.push(...state.charts.slice(before));
    }
    for(const c of selected) {
      const detail=ofEl('details','of-company-note');detail.appendChild(ofEl('summary','',`${c.name} · 수치·공시 확인`));
      const last=[...c.quarters].reverse().find(q=>q.revenue!=null);
      if(last?.note)ofNote(detail,last.note);
      const efficiency=[...c.quarters].reverse().find(q=>q.efficiency_pct!=null);
      if(efficiency)ofNote(detail,`${efficiency.efficiency_label || '회사 공시 효율'} · 계약 확보율·작업 가동률과 다른 지표입니다.`);
      if(c.quarters.some(q=>q.dayrate!=null))ofNote(detail,'평균 계약 일당은 회사 공시 기준입니다. 유형·연결 선대 범위가 달라 글로벌 시장 요율 평균으로 합산하지 않습니다.');
      if(last?.source)ofSource(detail,last.source);if(c.status?.source_url){const line=ofEl('p','of-source');line.appendChild(ofLink(c.status.source_url,'SEC 공시 재무 데이터'));detail.appendChild(line);}
      if(c.status?.ok===false)ofNote(detail,'재무 원문 확인·추출 일부 실패: 마지막 성공 자료와 확보 분기를 유지합니다.',true);
      for(const [metric,label] of Object.entries(metrics)) {
        const available=c.quarters.filter(q=>q[metric]!=null);
        ofNote(detail,`${label}: ${available.length}개 분기 · ${available.at(-1)?.date || '미확보'} 기준`);
      }
      notes.appendChild(detail);
    }
  }
  render();return panel;
}

function renderOffshoreOverview(doc) {
  const card=ofCard('해양 시추 추적 범위'); if(!doc)return card;
  const active=doc.rows.filter(r=>!['매각·퇴역','매각 대기'].includes(r.status));const counts=Object.entries(OF_TYPES).map(([type,label])=>`${label} ${active.filter(r=>r.type===type).length}기`).join(' · ');
  card.appendChild(ofEl('p','of-scope-line',`6개 운영 그룹 · 현역·대기·계선 ${active.length}기`));ofNote(card,counts);
  ofNote(card,'회사 공시를 기준으로 리그·소유·계약과 실적을 연결합니다. 아래 세계 시장 통계와 이 추적 목록의 범위는 다릅니다.');
  const wrap=ofEl('div','of-scroll'),table=ofEl('table','of-coverage-table'),head=ofEl('thead'),hr=ofEl('tr'),body=ofEl('tbody');
  for(const label of ['운영 그룹','추적 리그','12개월 하한','24개월 하한','계약 표본'])hr.appendChild(ofEl('th','',label));head.appendChild(hr);
  for(const [id,company] of Object.entries(doc.companies)) { const selected=active.filter(r=>r.company===id),known=selected.filter(r=>r.coverage_12m!=null);const tr=ofEl('tr');tr.append(ofEl('th','',company.name),ofEl('td','of-number',ofNum(selected.length,'기',0)),...['coverage_12m','coverage_24m'].map(key=>ofEl('td','of-number',ofNum(known.length?known.reduce((sum,r)=>sum+r[key],0)/known.length:null,'%'))),ofEl('td','of-number',`${known.length}/${selected.length}기`));body.appendChild(tr); }
  table.append(head,body);wrap.appendChild(table);card.appendChild(wrap);ofNote(card,'커버리지는 각 설비 공시일 이후 공개된 확정 계약의 보수적 하한을 단순 평균한 값입니다. 기간 미공개 설비는 표본에서 제외하므로 전체 선대 가동률로 해석하지 않습니다.');
  for(const event of doc.events || []) {const p=ofEl('p','of-event');p.append(ofEl('span','of-secondary',event.date),ofLink(event.url,event.title),ofEl('span','of-secondary',event.text));card.appendChild(p);}
  ofStatusNote(card,doc);return card;
}

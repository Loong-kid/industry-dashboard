/* HYBE: entity financials and exclusive-contract evidence remain distinct. */
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt=(v,digits=1)=>v==null?'—':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:digits});
export const growth=(value,prior)=>value==null||!(prior>0)?null:(value/prior-1)*100;
export function filterContracts(rows,{label='',query='',scope='current',category='group'}={}){
  const q=query.trim().toLowerCase();
  return rows.filter(r=>(!label||r.label===label)&&(scope==='all'||(scope==='current'?r.current:!r.current))&&(category==='all'||r.category===category||(category==='group'&&r.category==='unreviewed'&&r.members.length>1)))
    .filter(r=>!q||[r.name,r.label_original,...r.members].join(' ').toLowerCase().includes(q));
}
export function periodName(date,basis){return basis==='annual'?date.slice(0,4)+'년':`${date.slice(0,4)} Q${Math.ceil(Number(date.slice(5,7))/3)}${basis==='cumulative'?' 누적':''}`;}
export function financialMatrix(doc,basis='quarter',limit=8){
  const rows=doc.financial_views[basis]||[],dates=rows.map(r=>r.date).sort(),periods=[];
  if(dates.length){
    const first=Number(dates[0].slice(0,4)),last=Number(dates.at(-1).slice(0,4));
    for(let year=first;year<=last;year++)for(const q of basis==='annual'?[4]:[1,2,3,4]){
      const date=`${year}-${String(q*3).padStart(2,'0')}-${q===1||q===4?'31':'30'}`;
      if(date>=dates[0]&&date<=dates.at(-1))periods.push(date);
    }
  }
  periods.reverse();const shown=limit>0?periods.slice(0,limit):periods;
  const lookup=new Map(rows.map(r=>[`${r.entity}:${r.date}`,r]));
  const groups=[['label','레이블'],['regional','지역법인'],['unreviewed','분류 검토']].map(([kind,name])=>({kind,name,rows:doc.labels.filter(l=>(l.kind||'unreviewed')===kind).map(l=>({...l,values:shown.map(date=>({date,...lookup.get(`${l.id}:${date}`)}))}))})).filter(g=>g.rows.length);
  return {periods:shown,totalPeriods:periods.length,groups};
}
const source=(url,text='원문')=>`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)}</a>`;
export function render(doc,{createFinancialCard}={}){
  const root=document.createElement('section');root.className='hb-root';
  const labels=new Map(doc.labels.map(l=>[l.id,l]));
  let basis='quarter',matrixLimit=8,label='',scope='current',category='group',query='',selected=null;
  root.innerHTML=`<div class="hb-heading"><h2>하이브 레이블 매출</h2><span>레이블 공시 ${esc(periodName(doc.roster.report_date,'quarter'))} · 확인 ${esc(doc.fetched)}</span></div><p class="hb-note">${esc(doc.note)}</p>${!doc.ok?'<p class="hb-warning">일부 원문 확인 실패 · 확인된 이력과 마지막 성공 자료를 유지합니다.</p>':''}<div class="grid financial-grid hb-charts"></div><section class="hb-block hb-financials" aria-label="레이블·지역법인 기간별 실적"><div class="hb-head"><h3>레이블·지역법인별 실적</h3><div class="hb-financial-controls"><div class="hb-frequency" role="group" aria-label="레이블 실적 기간">${[['quarter','분기'],['annual','연간'],['cumulative','누적']].map(([v,n])=>`<button type="button" data-basis="${v}" aria-pressed="${basis===v}">${n}</button>`).join('')}</div><label>표시 기간 <select class="hb-window" aria-label="실적 표 표시 기간"><option value="8">최근 8개 기간</option><option value="12">최근 12개 기간</option><option value="0">전체 기간</option></select></label></div></div><p class="hb-note">단위 억원 · 최신 기간부터 표시합니다. 각 기간의 매출·당기순손익을 나란히 비교하고, 숫자를 누르면 해당 공시를 볼 수 있습니다. 법인 설립·편입 첫해는 일부 기간만 포함될 수 있습니다.</p><p class="hb-matrix-range hb-note"></p><div class="hb-matrices"></div></section><section class="hb-block hb-contracts"><div class="hb-head"><h2>레이블별 아티스트 계약</h2><span class="hb-note">전속 명단 ${esc(doc.roster.report_date)} · 계약 정보 검토 ${esc(doc.contracts_reviewed)}</span></div><p class="hb-note">최초 체결일·재계약 발표일·계약 만료일을 구분합니다. 미공개 날짜는 추정하지 않으며, 발표일이 실제 서명일과 같다는 뜻은 아닙니다.</p><div class="hb-filters"><label>레이블 <select class="hb-label" aria-label="계약 레이블 필터"><option value="">전체 레이블</option>${doc.labels.map(l=>`<option value="${esc(l.id)}">${esc(l.name)}</option>`).join('')}</select></label><label>분류 <select class="hb-category" aria-label="계약 아티스트 분류"><option value="group">그룹</option><option value="all">그룹·솔로 전체</option></select></label><label>명단 <select class="hb-scope" aria-label="계약 명단 범위"><option value="current">최신 공시 명단</option><option value="all">종료 이력 포함</option><option value="former">종료 이력</option></select></label><label class="hb-search">검색 <input type="search" aria-label="그룹·멤버 검색" placeholder="그룹명·멤버명"></label></div><p class="hb-count" aria-live="polite"></p><div class="hb-table-wrap" tabindex="0" role="region" aria-label="그룹별 전속계약 표 가로 스크롤"><table class="hb-contract-table"><thead><tr><th>레이블</th><th>그룹·아티스트</th><th>최초 체결일</th><th>최근 계약 관련 발표</th><th>계약 만료일</th><th>확인 상태</th><th>상세</th></tr></thead><tbody></tbody></table></div><section class="hb-inspector" hidden aria-label="계약 상세 근거"></section><details class="hb-method"><summary>집계 기준·계약 날짜 읽는 법</summary><p>${esc(doc.contract_method)}</p><p>최신 보고서의 주요 전속계약 명단 기준입니다. 이후 신규 그룹·해외 매니지먼트 및 음반 계약이 모두 포함된 전 세계 전체 명단은 아닙니다. 미국 지역 매출은 산하 아티스트의 매출로 배분하지 않습니다.</p><p>새 전속 명단은 자동 갱신하고 계약·재계약 조건은 공식 발표와 공시를 검토해 보완합니다. 계약 검토일과 재무 수집일은 별도입니다.</p><p>${source(doc.roster.source_url,'DART 주요 아티스트 전속계약 명단')}</p></details></section>`;
  if(createFinancialCard){const grid=root.querySelector('.hb-charts');for(const chart of doc.charts){const card=createFinancialCard(chart,chart.id);grid.append(card.element);}}

  function financialTable(){
    const matrix=financialMatrix(doc,basis,matrixLimit);
    for(const button of root.querySelectorAll('[data-basis]'))button.setAttribute('aria-pressed',button.dataset.basis===basis);
    root.querySelector('.hb-matrix-range').textContent=matrix.periods.length?`${periodName(matrix.periods.at(-1),basis)} ~ ${periodName(matrix.periods[0],basis)} · ${matrix.periods.length}개 기간 / 전체 ${matrix.totalPeriods}개 · 가로로 스크롤하면 이전 기간을 볼 수 있습니다.`:'공개된 실적이 없습니다.';
    root.querySelector('.hb-matrices').innerHTML=matrix.groups.map(group=>{
      const widths=`<col class="hb-entity-col">${matrix.periods.map(()=>'<col class="hb-number-col"><col class="hb-number-col">').join('')}`;
      const headers=matrix.periods.map((date,i)=>`<th colspan="2" scope="colgroup" class="hb-period-heading${i===0?' hb-latest':''}">${esc(periodName(date,basis))}</th>`).join('');
      const subheaders=matrix.periods.map((date,i)=>`<th scope="col" class="hb-metric-start${i===0?' hb-latest':''}">매출</th><th scope="col" title="당기순손익" class="${i===0?'hb-latest':''}">순손익</th>`).join('');
      const body=group.rows.map(l=>{
        const artists=doc.contracts.filter(r=>r.current&&r.category==='group'&&r.label===l.id).map(r=>r.name).join(', ');
        const ref=l.values.find(r=>r.source_url)?.source_url||doc.source_url;
        const cells=l.values.map((r,i)=>['revenue','net_income'].map((metric,j)=>{
          const v=r[metric],shown=v==null?null:v/100,name=metric==='revenue'?'매출':'당기순손익';
          const note=`${l.name} ${periodName(r.date,basis)} ${name} ${shown==null?'미공개':fmt(shown)+'억원'}`;
          return `<td data-period="${r.date}" data-metric="${metric}" class="${j===0?'hb-metric-start ':''}${i===0?'hb-latest ':''}${v<0?'hb-negative':''}" title="${esc(note)}">${shown==null?'—':`<a class="hb-matrix-value" href="${esc(r.source_url)}" target="_blank" rel="noopener" aria-label="${esc(note+' 공시 원문')}">${fmt(shown)}</a>`}</td>`;
        }).join('')).join('');
        return `<tr data-entity="${esc(l.id)}"><th scope="row" title="${esc([l.name,l.note,artists].filter(Boolean).join(' / '))}"><span class="hb-entity-name">${source(ref,l.name)}</span>${artists?`<button type="button" data-label="${esc(l.id)}" aria-label="${esc(l.name)} 그룹 계약 보기">그룹</button>`:''}</th>${cells}</tr>`;
      }).join('');
      return `<section class="hb-matrix-group" data-kind="${group.kind}"><div class="hb-matrix-heading"><h4>${group.name}</h4><span>${group.rows.length}개 법인</span></div>${group.kind==='regional'?'<p class="hb-note">지역법인은 산하 회사를 포함할 수 있어 레이블 매출과 합산하지 않습니다.</p>':''}<div class="hb-table-wrap hb-matrix-wrap" tabindex="0" role="region" aria-label="${group.name} ${basis==='quarter'?'분기별':'기간별'} 매출·당기순손익 표"><table class="hb-matrix-table" style="width:calc(var(--hb-company-width,152px) + ${matrix.periods.length*124}px)"><caption>${esc(group.name+' '+(basis==='quarter'?'분기별':basis==='annual'?'연간':'누적')+' 실적 · 억원')}</caption><colgroup>${widths}</colgroup><thead><tr><th rowspan="2" scope="col">${group.kind==='regional'?'지역법인':'레이블'}</th>${headers}</tr><tr>${subheaders}</tr></thead><tbody>${body}</tbody></table></div></section>`;
    }).join('');
    for(const wrap of root.querySelectorAll('.hb-matrix-wrap'))wrap.onscroll=()=>{for(const other of root.querySelectorAll('.hb-matrix-wrap'))if(other!==wrap&&Math.abs(other.scrollLeft-wrap.scrollLeft)>.5)other.scrollLeft=wrap.scrollLeft;};
    for(const b of root.querySelectorAll('[data-label]'))b.onclick=()=>{label=b.dataset.label;scope='current';category='group';query='';root.querySelector('.hb-label').value=label;root.querySelector('.hb-scope').value=scope;root.querySelector('.hb-category').value=category;root.querySelector('.hb-search input').value='';renderContracts();root.querySelector('.hb-contracts').scrollIntoView({block:'start'});};
  }

  function renderContracts(){
    const rows=filterContracts(doc.contracts,{label,scope,query,category});
    root.querySelector('.hb-count').textContent=`${rows.length}개 ${category==='group'?'그룹':'그룹·아티스트'} · 행 높이 고정 · 긴 내용은 상세에서 확인`;
    root.querySelector('.hb-contract-table tbody').innerHTML=rows.map(r=>{
      // A lineup announcement is not a renewal; show its type explicitly.
      const event=r.events.at(-1),expiry=r.expires||(r.current?'미공개':'—');
      return `<tr><th>${esc(labels.get(r.label)?.name||r.label_original||r.label)}</th><td class="hb-ellipsis" title="${esc(r.name)}">${esc(r.name)}</td><td>${esc(r.first_signed||'미공개')}</td><td class="hb-ellipsis" title="${esc(event?event.date+' '+event.kind:'공개된 계약·재계약 발표 미확인')}">${event?esc(event.date+' '+event.kind):'미공개'}</td><td title="${esc(r.expiry_scope||'')}">${esc(expiry)}${r.expiry_scope?' *':''}</td><td><span class="hb-status${r.current?'':' hb-ended'}">${esc(r.review_needed?'추가 검토':r.status)}</span></td><td><button type="button" data-artist="${esc(r.id)}" aria-label="${esc(r.name)} 계약 상세" aria-expanded="${selected===r.id}">상세</button></td></tr>`;
    }).join('')||'<tr><td colspan="7">조건에 맞는 아티스트가 없습니다.</td></tr>';
    for(const b of root.querySelectorAll('[data-artist]'))b.onclick=()=>{selected=selected===b.dataset.artist?null:b.dataset.artist;renderContracts();if(selected)root.querySelector('.hb-inspector').scrollIntoView({block:'nearest'});};
    if(selected&&!rows.some(r=>r.id===selected))selected=null;
    renderInspector();
  }

  function renderInspector(){
    const panel=root.querySelector('.hb-inspector'),r=doc.contracts.find(r=>r.id===selected);panel.hidden=!r;if(!r){panel.innerHTML='';return;}
    panel.innerHTML=`<div class="hb-head"><h3>${esc(r.name)} · 계약 근거</h3><button type="button" class="hb-close">닫기</button></div><p>${esc(r.note||'주요 전속계약 명단에서 소속을 확인했습니다. 구체적인 체결일·만료일은 공개 확인되지 않았습니다.')}</p>${r.expiry_scope?`<p class="hb-warning">${esc(r.expiry_scope)}</p>`:''}<dl><dt>최초 계약 체결</dt><dd>${esc(r.first_signed||'미공개')}${r.date_source?' · '+source(r.date_source.url,r.date_source.name):''}</dd><dt>효력 개시</dt><dd>${esc(r.effective_note||'정확한 개시일 미공개')}</dd><dt>만료일</dt><dd>${esc(r.expires||'미공개')}</dd><dt>공시 명단</dt><dd>${esc(r.members.join(', ')||'종료 이력')} ${r.current?'· '+source(r.roster_source,'보고서 전속계약 명단'):''}</dd></dl>${r.events.length?`<table class="hb-events"><thead><tr><th>발표·확인일</th><th>내용</th><th>근거</th></tr></thead><tbody>${r.events.map(e=>`<tr><td>${esc(e.date)}</td><td>${esc(e.kind)}</td><td>${source(e.source_url,e.evidence==='official_notice'?'공식 공지':'회사 발표 인용 보도')}</td></tr>`).join('')}</tbody></table>`:''}<p class="hb-note">계약 정보 검토 ${esc(r.reviewed)}. ‘미공개’는 계약 없음이나 만료를 뜻하지 않습니다.</p>`;
    panel.querySelector('.hb-close').onclick=()=>{selected=null;renderContracts();};
  }

  for(const b of root.querySelectorAll('[data-basis]'))b.onclick=()=>{basis=b.dataset.basis;financialTable();};
  root.querySelector('.hb-window').onchange=e=>{matrixLimit=Number(e.target.value);financialTable();};
  root.querySelector('.hb-label').onchange=e=>{label=e.target.value;renderContracts();};
  root.querySelector('.hb-category').onchange=e=>{category=e.target.value;renderContracts();};
  root.querySelector('.hb-scope').onchange=e=>{scope=e.target.value;renderContracts();};
  root.querySelector('.hb-search input').oninput=e=>{query=e.target.value;renderContracts();};
  financialTable();renderContracts();return root;
}

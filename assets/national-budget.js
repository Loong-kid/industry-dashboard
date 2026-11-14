/* National budgets: explicit accounting bases, fiscal years and forecast vintages. */
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const preferences={};
export const change=(value,prior)=>value==null||!(prior>0)?null:value/prior-1;
export const format=(value,digits=1)=>value==null?'—':Number(value).toLocaleString('ko-KR',{maximumFractionDigits:digits,minimumFractionDigits:0});
const percent=value=>value==null?'—':`${value>=0?'+':''}${format(value*100)}%`;
export function yearsFor(doc,basis){return Object.keys(doc.totals[basis]||{}).map(Number).sort((a,b)=>a-b);}
export function statusFor(doc,basis,year,accounts=false){
  if(doc.id==='kr')return basis==='approved'?'국회확정 본예산':basis==='proposal'?'정부안':'결산';
  const cutoff=accounts?doc.account_actual_through:doc.actual_through[basis];
  return year<=cutoff?'실적':'정부요청·추계';
}
export function rowsFor(programs,basis,year,sector,query=''){
  const search=query.trim().toLocaleLowerCase();
  return programs.filter(r=>(!r.basis||r.basis===basis)&&(!sector||r.sector===sector)&&(r.basis?r.values[year]!=null:r.values[basis]?.[year]!=null))
    .filter(r=>!search||[r.name,r.agency,r.program,r.bureau,r.account].join(' ').toLocaleLowerCase().includes(search))
    .map(r=>({...r,value:r.basis?r.values[year]:r.values[basis][year],prior:r.basis?r.values[year-1]:r.values[basis][year-1]}))
    .sort((a,b)=>b.value-a.value||a.name.localeCompare(b.name,'ko'));
}

function bars(doc,basis,values,years,selected,onPick){
  const width=330,height=112,pad=15,plot=height-2*pad;
  const valid=years.map(y=>values[y]).filter(v=>v!=null);const lo=Math.min(0,...valid),hi=Math.max(0.001,...valid);
  const y=v=>pad+(hi-v)/(hi-lo)*plot,zero=y(0),slot=(width-8)/years.length;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.classList.add('nb-bars');svg.setAttribute('role','group');svg.setAttribute('aria-label','연도별 금액. 막대를 선택하면 해당 연도 상세를 표시합니다.');
  svg.innerHTML=`<line x1="4" x2="326" y1="${zero}" y2="${zero}" class="nb-zero"/>`+years.map((year,i)=>{
    const value=values[year],x=4+i*slot+2,w=Math.max(1,slot-4),top=value==null?zero:Math.min(zero,y(value)),h=value==null?0:Math.max(value===0?0:1,Math.abs(y(value)-zero));
    const forecast=statusFor(doc,basis,year).includes('추계')||basis==='proposal';
    return `<g class="nb-bar-item${year===selected?' nb-selected':''}" data-year="${year}" tabindex="0" role="button" aria-label="${year}년 ${format(value)} ${doc.unit} ${statusFor(doc,basis,year)}"><title>${year}년 · ${format(value)} ${doc.unit}\n${statusFor(doc,basis,year)}</title><rect class="nb-bar${forecast?' nb-estimate':''}${value<0?' nb-negative':''}" x="${x}" y="${top}" width="${w}" height="${h}" rx="2"/><rect class="nb-hit" x="${x-2}" y="0" width="${slot}" height="${height}"/>${i===0||i===years.length-1||year===selected?`<text x="${x+w/2}" y="${height-1}" text-anchor="middle">${String(year).slice(2)}</text>`:''}</g>`;
  }).join('');
  for(const item of svg.querySelectorAll('[data-year]')){
    item.onclick=()=>onPick(Number(item.dataset.year));item.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();item.onclick();}};
  }
  return svg;
}

export function mount(root,{country='kr',tabsRoot}={}){
  let disposed=false,doc=null,accounts=null,charts=[],selected=null,page=0,query='',timer=null,accountLoading=false,accountError='';
  const accountCache=new Map();
  const prefs=preferences[country]??={basis:null,year:null,sort:'amount',forecast:null};
  const box=document.createElement('div');box.className='nb-root';root.append(box);
  box.innerHTML='<p class="page-loading">공식 국가예산 자료를 불러오는 중…</p>';
  if(tabsRoot){tabsRoot.innerHTML='';const nav=document.createElement('nav');nav.className='commodity-tabs nb-country-tabs';nav.setAttribute('aria-label','국가예산 국가');tabsRoot.append(nav);for(const [id,label] of [['kr','한국'],['us','미국']]){const a=document.createElement('a');a.href=`#/national_budget/${id}`;a.className='nb-country'+(country===id?' nb-country-on active':'');a.textContent=label;if(country===id)a.setAttribute('aria-current','page');nav.append(a);}}
  const destroyCharts=()=>{for(const c of charts)c.destroy();charts=[];};
  const base=()=>doc.basis.find(b=>b.id===prefs.basis);
  const source=()=>doc.sources.find(s=>s.id===(country==='us'?'omb':'budget'));
  const year=()=>Number(prefs.year);
  const years=()=>yearsFor(doc,prefs.basis);
  const sectors=()=>doc.sectors.filter(s=>s.values[prefs.basis]&&Object.values(s.values[prefs.basis]).some(v=>v!=null));
  const fiscal=y=>country==='us'?'FY'+y:y+'년';

  function chart(canvas,series,unit){
    if(!window.Chart)return;
    const axis=[...new Set(series.flatMap(s=>Object.keys(s.values)))].map(Number).sort((a,b)=>a-b);
    const colors=['#2878d4','#15866e','#ba7823','#8c70c9'];
    const c=new window.Chart(canvas,{
      type:'line',
      data:{labels:axis.map(fiscal),datasets:series.map((s,i)=>({label:s.label,data:axis.map(y=>s.values[y]??null),borderColor:colors[i%colors.length],backgroundColor:colors[i%colors.length],borderDash:s.forecast?[6,4]:[],borderWidth:2,pointRadius:axis.length>16?0:2,spanGaps:false,tension:0}))},
      options:{responsive:true,maintainAspectRatio:false,animation:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{position:'bottom',labels:{boxWidth:12}},tooltip:{callbacks:{label:ctx=>`${ctx.dataset.label}: ${format(ctx.parsed.y)} ${unit}`}}},
        scales:{x:{grid:{display:false},ticks:{maxTicksLimit:6}},y:{ticks:{callback:v=>format(v,unit==='%'?1:0)},grid:{color:'rgba(130,130,130,.15)'}}}
      }
    });charts.push(c);
  }

  function renderMacro(){
    const plan=doc.outlooks.find(o=>o.id===prefs.forecast)||doc.outlooks.at(-1);
    const intro=box.querySelector('#nb-macro-note');intro.textContent=(plan.base_note||'독립기관 CBO의 현행법 기준선 전망입니다. OMB 정부 요청안과 별개입니다.')+' 발표: '+plan.publication_date;
    const grid=box.querySelector('#nb-macro-grid');grid.innerHTML='';
    for(const metric of ['spending','revenue','balance']){
      const card=document.createElement('section');card.className='nb-chart-card';card.innerHTML=`<h3>${esc(doc.metric_labels[metric])}</h3><div class="nb-chart"><canvas role="img" aria-label="${esc(doc.metric_labels[metric])} 연도별 실적과 전망"></canvas></div>`;grid.append(card);
      const forecast=Object.fromEntries(Object.entries(plan.series[metric]||{}).filter(([y])=>Number(y)>=Number(plan.publication_date.slice(0,4))));
      const actualYears=Object.keys(doc.macro[metric]||{}).map(Number).sort((a,b)=>a-b);
      const note=document.createElement('p');note.className='nb-note';note.textContent=`실적 ${fiscal(actualYears[0])}–${fiscal(actualYears.at(-1))} · ${doc.unit}`;card.append(note);
      chart(card.querySelector('canvas'),[{label:'연간 실적',values:doc.macro[metric]||{}},{label:plan.label,values:forecast,forecast:true}],doc.unit);
    }
    const metrics=country==='kr'?['mandatory','discretionary','debt_gdp']:['interest','debt_gdp'];
    for(const metric of metrics){
      if(!plan.series[metric])continue;
      const card=document.createElement('section');card.className='nb-chart-card';card.innerHTML=`<h3>${esc(doc.metric_labels[metric])} · 전망</h3><div class="nb-chart"><canvas role="img" aria-label="${esc(doc.metric_labels[metric])} 전망"></canvas></div>`;grid.append(card);chart(card.querySelector('canvas'),[{label:plan.label,values:plan.series[metric],forecast:true}],metric.endsWith('_gdp')?'%':doc.unit);
    }
  }

  function renderCards(){
    let items=sectors().slice();
    items.sort((a,b)=>prefs.sort==='growth'?( (b.values[prefs.basis][year()]??0)-(b.values[prefs.basis][year()-1]??0))-((a.values[prefs.basis][year()]??0)-(a.values[prefs.basis][year()-1]??0)):(b.values[prefs.basis][year()]??-Infinity)-(a.values[prefs.basis][year()]??-Infinity));
    const total=doc.totals[prefs.basis][year()],grid=box.querySelector('#nb-sector-grid');grid.innerHTML='';
    for(const s of items){
      const v=s.values[prefs.basis],amount=v[year()],growth=change(amount,v[year()-1]);const card=document.createElement('section');card.className='nb-sector'+(s.id===selected?' nb-sector-on':'');
      card.innerHTML=`<button type="button" class="nb-sector-pick" aria-pressed="${s.id===selected}"><b>${esc(s.name)}</b><strong>${format(amount)}<small> ${esc(doc.unit)}</small></strong></button><p>비중 ${amount!=null&&total?format(amount/total*100)+'%':'—'} <span>전년대비 ${percent(growth)}</span></p>`;
      card.querySelector('button').onclick=()=>pickSector(s.id);
      card.append(bars(doc,prefs.basis,v,years(),year(),y=>{prefs.year=y;selected=s.id;accounts=accountCache.get(s.id)||null;accountError='';page=0;query='';render();box.querySelector('#nb-detail').scrollIntoView({block:'nearest'});}));grid.append(card);
    }
  }

  function renderMatrix(){
    const ys=years(),items=sectors();const wrap=box.querySelector('#nb-matrix');
    wrap.innerHTML=`<table><caption>${esc(base().label)} · ${esc(doc.unit)}</caption><thead><tr><th>분야</th>${ys.map(y=>`<th>${fiscal(y)}${statusFor(doc,prefs.basis,y).includes('추계')?' 추계':''}</th>`).join('')}</tr></thead><tbody>${items.map(s=>`<tr><th><button type="button" data-sector="${esc(s.id)}">${esc(s.name)}</button></th>${ys.map(y=>`<td>${format(s.values[prefs.basis]?.[y])}</td>`).join('')}</tr>`).join('')}<tr class="nb-total"><th>공식 합계</th>${ys.map(y=>`<td>${format(doc.totals[prefs.basis][y])}</td>`).join('')}</tr></tbody></table>`;
    for(const b of wrap.querySelectorAll('[data-sector]'))b.onclick=()=>pickSector(b.dataset.sector);
  }

  async function loadAccounts(){
    if(accounts||accountLoading)return;
    accountLoading=true;accountError='';renderDetail();
    const requested=selected;
    try{const path=doc.account_files[requested];if(!path)throw Error('상세 사업 미공개');const r=await fetch(`data/national-budget/${path}`);if(!r.ok)throw Error('HTTP '+r.status);const data=await r.json();if(disposed)return;accountCache.set(requested,data.programs);if(selected===requested)accounts=data.programs;}
    catch(e){if(!disposed&&selected===requested)accountError='상세 자료를 불러오지 못했습니다. 버튼을 눌러 다시 확인해 주세요.';}
    finally{accountLoading=false;if(!disposed)renderDetail();}
  }

  function renderDetail(){
    const panel=box.querySelector('#nb-detail');if(!selected){panel.hidden=true;return;}panel.hidden=false;
    const sector=doc.sectors.find(s=>s.id===selected);
    panel.innerHTML=`<div class="nb-detail-head"><h3>${esc(sector.name)} · ${fiscal(year())}</h3><button type="button" aria-label="분야 상세 닫기">닫기</button></div><p class="nb-note">${esc(statusFor(doc,prefs.basis,year(),true))} · ${esc(base().label)}. ${country==='us'&&year()>doc.account_actual_through?'계정별 상세는 OMB 발표 당시 추계입니다. 재무부 결산으로 갱신한 분야 총괄과 다를 수 있습니다.':''}</p><div id="nb-account-state" role="status"></div><div id="nb-account-controls"></div><div id="nb-agencies" class="nb-table-wrap"></div><div id="nb-programs"></div>`;
    panel.querySelector('.nb-detail-head button').onclick=()=>{selected=null;renderDetail();renderCards();};
    if(country==='kr'&&prefs.basis==='actual'){panel.querySelector('#nb-account-state').textContent='결산은 공식 16대 분야 합계로 제공합니다. 부처·세부사업은 본예산 또는 정부 제출안 기준에서 확인할 수 있습니다.';return;}
    if(!accounts){panel.querySelector('#nb-account-state').textContent=accountError;const b=document.createElement('button');b.type='button';b.className='nb-load';b.textContent=accountLoading?'상세 사업을 불러오는 중…':'부처·세부사업 펼치기';b.disabled=accountLoading;b.onclick=loadAccounts;panel.querySelector('#nb-account-controls').append(b);return;}
    const all=rowsFor(accounts,prefs.basis,year(),selected),agency=new Map();for(const r of all)agency.set(r.agency,(agency.get(r.agency)||0)+r.value);
    panel.querySelector('#nb-agencies').innerHTML=`<table><caption>소관 부처 · 동일 상세 원문 기준</caption><thead><tr><th>부처</th><th>${esc(doc.unit)}</th></tr></thead><tbody>${[...agency].sort((a,b)=>b[1]-a[1]).slice(0,10).map(([a,v])=>`<tr><th>${esc(a)}</th><td>${format(v)}</td></tr>`).join('')}</tbody></table>`;
    panel.querySelector('#nb-account-controls').innerHTML=`<label class="nb-search">사업·기관 검색 <input type="search" aria-label="사업·기관 검색" placeholder="예: 반도체, AI, NASA" value="${esc(query)}"></label>`;
    const input=panel.querySelector('input');input.oninput=()=>{query=input.value;page=0;clearTimeout(timer);timer=setTimeout(renderPrograms,100);};renderPrograms();
  }

  function renderPrograms(){
    if(disposed||!accounts||!selected||!box.querySelector('#nb-programs'))return;
    const result=rowsFor(accounts,prefs.basis,year(),selected,query),limit=30,pages=Math.max(1,Math.ceil(result.length/limit));page=Math.min(page,pages-1);
    const target=box.querySelector('#nb-programs');
    target.innerHTML=`<div class="nb-page-controls"><span>${result.length.toLocaleString('ko-KR')}개 상세 항목</span><button type="button" data-page="-1" ${page===0?'disabled':''}>이전</button><span>${page+1} / ${pages}</span><button type="button" data-page="1" ${page+1===pages?'disabled':''}>다음</button></div><div class="nb-table-wrap" tabindex="0" role="region" aria-label="세부사업 표, 가로 스크롤"><table class="nb-program-table"><thead><tr><th>사업·예산계정</th><th>소관</th><th>${fiscal(year())}<br>${esc(doc.unit)}</th><th>전년대비</th><th>출처</th></tr></thead><tbody>${result.slice(page*limit,(page+1)*limit).map(r=>`<tr><th title="${esc([r.name,r.program,r.account,r.bureau].filter(Boolean).join(' / '))}">${esc(r.name)}</th><td title="${esc(r.agency)}">${esc(r.agency)}</td><td>${format(r.value,3)}</td><td>${percent(change(r.value,r.prior))}</td><td><a href="${esc(source().url)}" target="_blank" rel="noopener">원문</a></td></tr>`).join('')||'<tr><td colspan="5">해당 기준·연도의 공개 항목이 없습니다.</td></tr>'}</tbody></table></div><p class="nb-note">사업명·기관명은 말줄임으로 표시합니다. 셀에 마우스를 올리면 전체 내용을 볼 수 있습니다. 명칭 변경·기관 이동을 신규 사업으로 단정하지 않습니다.</p>`;
    for(const b of target.querySelectorAll('[data-page]'))b.onclick=()=>{page+=Number(b.dataset.page);renderPrograms();};
  }

  function pickSector(id){selected=id;accounts=accountCache.get(id)||null;accountError='';page=0;query='';renderCards();renderDetail();box.querySelector('#nb-detail').scrollIntoView({block:'nearest'});}

  function render(){
    destroyCharts();const ys=years();if(!ys.includes(year()))prefs.year=ys.at(-1);
    const total=doc.totals[prefs.basis][year()],prior=doc.totals[prefs.basis][year()-1];
    box.innerHTML=`<div class="nb-intro"><h2>${esc(doc.name)} 국가예산</h2><p>${esc(doc.scope)} · ${esc(doc.fiscal_note)}</p></div>${!doc.ok?`<p class="nb-warning">최근 확인 실패 · ${esc(doc.fetched)} 마지막 성공 자료를 표시합니다.</p>`:''}<div class="nb-controls"><label>기준 <select id="nb-basis" aria-label="예산 기준">${doc.basis.map(b=>`<option value="${b.id}" ${b.id===prefs.basis?'selected':''}>${esc(b.label)}</option>`).join('')}</select></label><label>연도 <select id="nb-year" aria-label="예산 연도">${ys.map(y=>`<option value="${y}" ${y===year()?'selected':''}>${fiscal(y)} · ${statusFor(doc,prefs.basis,y)}</option>`).join('')}</select></label><label>정렬 <select id="nb-sort" aria-label="분야 정렬"><option value="amount" ${prefs.sort==='amount'?'selected':''}>규모순</option><option value="growth" ${prefs.sort==='growth'?'selected':''}>증가액순</option></select></label></div><p class="nb-note">${esc(base().note)}</p><div class="nb-summary"><div><span>${fiscal(year())} ${esc(statusFor(doc,prefs.basis,year()))}</span><strong>${format(total)} <small>${esc(doc.unit)}</small></strong></div><div><span>같은 기준 전년대비</span><strong>${percent(change(total,prior))}</strong></div><div><span>공식 분야</span><strong>${sectors().length}<small>개</small></strong></div></div><section class="nb-block"><h3>분야별 연도 추이</h3><p class="nb-note">분야 또는 막대를 선택하면 해당 연도의 부처·사업을 펼칠 수 있습니다. 옅은 막대는 정부안·추계입니다.</p><div id="nb-sector-grid" class="nb-sector-grid"></div><section id="nb-detail" class="nb-detail" hidden></section></section><section class="nb-block"><h3>분야 × 연도</h3><div id="nb-matrix" class="nb-table-wrap nb-matrix" tabindex="0" role="region" aria-label="분야별 연도 예산 표, 가로 스크롤"></div></section><section class="nb-block"><div class="nb-plan-head"><h3>총괄 실적과 중장기 계획·전망</h3><label>발표본 <select id="nb-forecast" aria-label="전망 발표본">${doc.outlooks.map(o=>`<option value="${o.id}" ${o.id===prefs.forecast?'selected':''}>${esc(o.label)}</option>`).join('')}</select></label></div><p class="nb-note" id="nb-macro-note"></p><div id="nb-macro-grid" class="nb-macro-grid"></div></section>${doc.progress?`<p class="nb-progress">${esc(doc.progress.year)}년 ${Number(doc.progress.month)}월 누적 실적 · 지출 ${format(doc.progress.values.spending)} / 수입 ${format(doc.progress.values.revenue)} ${esc(doc.unit)}. 연간 결산과 구분합니다.</p>`:''}<details class="nb-sources"><summary>집계 기준과 출처</summary><ul>${doc.notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul>${doc.sources.map(s=>`<p><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a></p>`).join('')}<p class="nb-note">마지막 성공 확인 ${esc(doc.fetched)} · 최근 확인 ${esc(doc.checked)}. 원문 발표·정정 확인 후 갱신합니다.</p></details>`;
    box.querySelector('#nb-basis').onchange=e=>{prefs.basis=e.target.value;page=0;render();};
    box.querySelector('#nb-year').onchange=e=>{prefs.year=Number(e.target.value);page=0;render();};
    box.querySelector('#nb-sort').onchange=e=>{prefs.sort=e.target.value;renderCards();};
    box.querySelector('#nb-forecast').onchange=e=>{prefs.forecast=e.target.value;destroyCharts();renderMacro();};
    renderCards();renderMatrix();renderDetail();renderMacro();
  }

  fetch(`data/national-budget/${country}.json`).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(data=>{
    if(disposed)return;doc=data;prefs.basis=doc.basis.some(b=>b.id===prefs.basis)?prefs.basis:doc.default_basis;prefs.forecast=doc.outlooks.some(o=>o.id===prefs.forecast)?prefs.forecast:doc.outlooks.at(-1).id;
    // Open on the budget year, rather than the last far-future estimate.
    prefs.year??=country==='us'?doc.omb_edition:yearsFor(doc,prefs.basis).at(-1);render();
    const foot=document.getElementById('last-updated');if(foot)foot.textContent=`국가예산 · 확인 ${doc.checked}${doc.ok?'':' · 이전 자료 유지'}`;
  }).catch(e=>{if(!disposed)box.innerHTML=`<p class="page-loading">국가예산 자료를 불러오지 못했습니다. 새로고침해 주세요. (${esc(e.message)})</p>`;});
  return ()=>{disposed=true;clearTimeout(timer);destroyCharts();box.remove();};
}

const dataCache=new Map();
let cacheEpoch;
const fmt=(v,d=2)=>Number.isFinite(v)?new Intl.NumberFormat('ko-KR',{maximumFractionDigits:d}).format(v):'—';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function valueAt(rows,date,maxAge=460){
  let lo=0,hi=rows.length-1,found=-1;
  while(lo<=hi){const mid=(lo+hi)>>1;if(rows[mid][0]<=date){found=mid;lo=mid+1;}else hi=mid-1;}
  return found>=0&&(Date.parse(date)-Date.parse(rows[found][0]))/86400000<=maxAge?rows[found]:null;
}

export function basisValue(doc,field,date){
  const r=valueAt(doc.fundamentals?.[field]||[],date);if(!r)return null;
  if(r[2]===doc.currency)return r[1];
  const fx=valueAt(doc.fx?.[r[2]+doc.currency]||[],date,7);return fx?r[1]*fx[1]:null;
}

export function sampleRows(rows,limit=640){
  if(rows.length<=limit)return rows;
  const selected=new Map([[0,rows[0]],[rows.length-1,rows.at(-1)]]),size=Math.ceil(rows.length/Math.floor(limit/4));
  for(let start=0;start<rows.length;start+=size){
    const end=Math.min(rows.length,start+size);let low=start,high=start;
    for(let i=start+1;i<end;i++){if(rows[i][1]<rows[low][1])low=i;if(rows[i][1]>rows[high][1])high=i;}
    for(const i of [start,low,high,end-1])selected.set(i,rows[i]);
  }
  return [...selected].sort((a,b)=>a[0]-b[0]).map(([,r])=>r);
}

export function createSession(index,{state,range}){
  if(cacheEpoch!==state.bust){dataCache.clear();cacheEpoch=state.bust;}
  if(!document.querySelector('[data-semicon-valuation-style]')){
    const link=document.createElement('link');link.rel='stylesheet';link.href=new URL('./semicon-valuation.css',import.meta.url).href;link.dataset.semiconValuationStyle='true';document.head.append(link);
  }
  let alive=true,zoom=null;const chartSet=new Set(),panels=new Map();
  const companies=new Map((index?.companies||[]).map(c=>[c.id,c]));
  const destroy=chart=>{if(chart.canvas)chart.destroy();chartSet.delete(chart);state.charts=state.charts.filter(c=>c!==chart);};
  const observer=new IntersectionObserver(entries=>{for(const entry of entries){const p=panels.get(entry.target);if(!p)continue;p.visible=entry.isIntersecting;if(p.visible)load(p);else for(const chart of [...p.charts]){destroy(chart);p.charts.delete(chart);}}},{rootMargin:'180px 0px'});
  function filter(doc,choice=range){
    const all=doc.prices||[];if(choice==='all'||!all.length)return all;
    if(choice==='custom')return all.filter(r=>(!state.rangeFrom||r[0]>=state.rangeFrom)&&(!state.rangeTo||r[0]<=state.rangeTo));
    const end=new Date(all.at(-1)[0]+'T00:00:00Z');const cutoff=new Date(end);if(choice==='3m')cutoff.setUTCMonth(end.getUTCMonth()-3);else cutoff.setUTCFullYear(end.getUTCFullYear()-(choice==='5y'?5:choice==='3y'?3:1));
    return all.filter(r=>r[0]>=cutoff.toISOString().slice(0,10));
  }
  async function load(panel){
    if(!alive||panel.loading||panel.charts.size)return;
    panel.loading=true;
    try{
      const cacheKey=panel.company.id+':'+(state.bust||'');
      if(!dataCache.has(cacheKey))dataCache.set(cacheKey,fetch(`data/semicon/valuation/${panel.company.id}.json${state.bust?'?t='+state.bust:''}`).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).catch(e=>{dataCache.delete(cacheKey);throw e;}));
      const doc=await dataCache.get(cacheKey);panel.doc=doc;
      if(alive&&panel.visible&&panel.root.isConnected)draw(panel,doc);
    }catch(e){if(alive)for(const c of panel.cards)c.querySelector('.chart-wrap').textContent='주가·밴드를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.';}
    finally{panel.loading=false;}
  }
  function draw(panel,doc){
    const all=filter(doc);
    for(let k=0;k<panel.cards.length;k++){
      const card=panel.cards[k],metric=['price','per','pbr'][k],field=metric==='per'?'eps':'bps',wrap=card.querySelector('.chart-wrap');wrap.replaceChildren();
      const metricRows=rowsForMetric(doc,metric,all);
      const canvas=document.createElement('canvas');wrap.append(canvas);canvas.setAttribute('aria-label',panel.company.name+' '+({price:'주가',per:'PER 밴드',pbr:'PBR 밴드'}[metric]));canvas.setAttribute('role','img');
      const chart=makeChart(canvas,doc,metric,metricRows);panel.charts.add(chart);
      const enlarge=card.querySelector('.sv-enlarge');enlarge.disabled=false;enlarge.onclick=()=>openZoom(doc,metric,panel.company,enlarge);
      card.querySelector('.sv-chart-caption').textContent=metric==='price'?`${doc.currency} · ${all[0]?.[0]||'—'} ~ ${all.at(-1)?.[0]||'—'} · 일별 종가`:`주가 ${doc.currency} · 실적 기준 참고 밴드 · ${metric==='per'?doc.fundamentals?.eps_basis:doc.fundamentals?.bps_basis}`;
      const tableButton=card.querySelector('.sv-table-button');tableButton.onclick=()=>showTable(card,doc,metric,metricRows,tableButton);
      card.querySelector('.sv-details-body').textContent=doc.methodology+(doc.note?' '+doc.note:'')+(doc.errors?.length?' 최근 수집 확인 필요: '+doc.errors.join(' / '):'');
    }
  }
  function rowsForMetric(doc,metric,rows){
    const field=metric==='per'?'eps':'bps';return metric==='price'?rows:rows.filter(r=>r[0]>=(doc.fundamentals?.[field]?.[0]?.[0]||'9999'));
  }
  function makeChart(canvas,doc,metric,rows,large=false){
    const field=metric==='per'?'eps':'bps',colors=['#575e70','#7d8494','#a4a9b4','#bfc3cc','#d6d9df'];
    const selected=new Map((large?rows:sampleRows(rows)).map(r=>[r[0],r]));
    if(!large&&metric!=='price')for(const f of doc.fundamentals?.[field]||[]){const i=rows.findIndex(r=>r[0]>=f[0]);if(i>=0)for(const j of [Math.max(0,i-1),i])selected.set(rows[j][0],rows[j]);}
    const points=[...selected.values()].sort((a,b)=>a[0].localeCompare(b[0]));
    const datasets=[{label:'주가',data:points.map(r=>r[1]),borderColor:'#18bf53',borderWidth:large?1.8:1.6,pointRadius:points.length<8?3:0,pointHoverRadius:3,order:0}];
    if(metric!=='price')for(const [i,multiple] of (doc.bands?.[metric]||[]).entries())datasets.push({label:fmt(multiple)+'배',data:points.map(r=>{const v=basisValue(doc,field,r[0]);return Number.isFinite(v)&&v>0?v*multiple:null;}),borderColor:colors[i],borderWidth:1,pointRadius:points.length<8?2:0,stepped:!Object.keys(doc.fx||{}).length,spanGaps:false,order:i+1});
    const style=getComputedStyle(document.documentElement),ink=style.getPropertyValue('--muted').trim(),border=style.getPropertyValue('--border').trim();
    const chart=new Chart(canvas,{type:'line',data:{labels:points.map(r=>r[0]),datasets},options:{responsive:true,maintainAspectRatio:false,animation:false,normalized:true,
      interaction:{intersect:false,mode:'index'},
      plugins:{legend:{display:metric!=='price',position:'bottom',labels:{color:ink,boxWidth:large?20:13,boxHeight:2,font:{size:large?12:10},padding:large?16:8}},
        tooltip:{callbacks:{title:items=>items[0]?.label||'',label:c=>`${c.dataset.label}: ${fmt(c.parsed.y)} ${doc.currency}`}}},
      scales:{x:{grid:{display:false},ticks:{color:ink,maxTicksLimit:large?Math.max(3,Math.min(8,Math.floor(canvas.parentElement.clientWidth/90))):5,maxRotation:0,callback:function(value){return this.getLabelForValue(value).slice(large?0:2,7);}}},
        y:{grid:{color:border},ticks:{color:ink,maxTicksLimit:large?8:5,callback:v=>Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(v)}}}
    }});
    chartSet.add(chart);state.charts.push(chart);return chart;
  }
  function closeZoom(){if(zoom){const current=zoom;current.dialog.close();current.finish();}}
  function openZoom(doc,metric,company,opener){
    if(!alive)return;closeZoom();
    const all=rowsForMetric(doc,metric,doc.prices||[]),dialog=document.createElement('dialog'),label=metric==='price'?'주가':metric.toUpperCase()+' 밴드';
    dialog.className='sv-zoom-dialog';dialog.id='sv-zoom-window';dialog.setAttribute('aria-labelledby','sv-zoom-title');
    dialog.innerHTML=`<div class="sv-zoom-head"><div><h2 id="sv-zoom-title">${esc(company.name)} · ${label}</h2><p class="sv-caption">${esc(doc.symbol)} · 주가 ${esc(doc.currency)}</p></div><button type="button" class="sv-zoom-close" aria-label="확대 창 닫기" autofocus>✕</button></div><div class="sv-zoom-controls"><div class="sv-zoom-ranges" role="group" aria-label="확대 차트 기간">${[['3m','3개월'],['1y','1년'],['3y','3년'],['5y','5년'],['all','전체']].map(([value,text])=>`<button type="button" data-zoom-range="${value}" aria-pressed="false">${text}</button>`).join('')}</div><div class="sv-zoom-dates"><label>시작 <input type="date" class="sv-zoom-from" aria-label="확대 차트 시작일"></label><label>종료 <input type="date" class="sv-zoom-to" aria-label="확대 차트 종료일"></label></div></div><p class="sv-zoom-status sv-caption" role="status"></p><div class="sv-zoom-chart"></div><div class="sv-zoom-foot"><span class="sv-caption">일별 종가${metric==='price'?'':' · 실적 기준 참고 밴드'}</span><a href="${esc(metric==='price'?doc.price_source:doc.financial_source)}" target="_blank" rel="noopener">출처 ↗</a></div>`;
    const start=dialog.querySelector('.sv-zoom-from'),end=dialog.querySelector('.sv-zoom-to'),status=dialog.querySelector('.sv-zoom-status'),wrap=dialog.querySelector('.sv-zoom-chart');
    const current=metric==='price'?doc.prices?.at(-1)?.[1]:doc.latest?.[metric];
    dialog.querySelector('.sv-zoom-head .sv-caption').textContent=metric==='price'?`${doc.symbol} · 종가 ${fmt(current)} ${doc.currency}`:`${doc.symbol} · ${metric.toUpperCase()} ${current==null?'N/M':fmt(current)+'배'} · 주가축 ${doc.currency}`;
    for(const input of [start,end]){input.min=all[0]?.[0]||'';input.max=all.at(-1)?.[0]||'';}
    const previousOverflow=document.body.style.overflow;let chart=null,ended=false;
    const finish=()=>{if(ended)return;ended=true;if(chart)destroy(chart);dialog.remove();document.body.style.overflow=previousOverflow;if(zoom?.dialog===dialog)zoom=null;if(alive&&opener.isConnected)opener.focus({preventScroll:true});};
    zoom={dialog,finish};dialog.addEventListener('close',finish);dialog.querySelector('.sv-zoom-close').onclick=closeZoom;
    dialog.addEventListener('keydown',event=>{
      if(event.key!=='Tab'||event.ctrlKey||event.metaKey)return;
      const items=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),a[href]')].filter(e=>e.getClientRects().length),first=items[0],last=items.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    });
    dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closeZoom();});
    const render=()=>{
      if(!start.value||!end.value||start.value>end.value||!start.checkValidity()||!end.checkValidity()){status.textContent='조회 가능한 기간 안에서 시작일과 종료일을 확인해 주세요.';return;}
      const rows=all.filter(r=>r[0]>=start.value&&r[0]<=end.value);if(chart){destroy(chart);chart=null;}wrap.replaceChildren();
      status.textContent=rows.length?`${rows[0][0]} ~ ${rows.at(-1)[0]} · ${fmt(rows.length,0)}거래일`:'선택한 기간에는 거래일 데이터가 없습니다.';
      if(rows.length){const canvas=document.createElement('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',company.name+' '+label+' 확대 차트');wrap.append(canvas);chart=makeChart(canvas,doc,metric,rows,true);}
    };
    const setRange=choice=>{const rows=rowsForMetric(doc,metric,filter(doc,choice));start.value=rows[0]?.[0]||all[0]?.[0]||'';end.value=rows.at(-1)?.[0]||all.at(-1)?.[0]||'';dialog.querySelectorAll('[data-zoom-range]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.zoomRange===choice)));render();};
    for(const input of [start,end])input.onchange=()=>{dialog.querySelectorAll('[data-zoom-range]').forEach(b=>b.setAttribute('aria-pressed','false'));render();};
    dialog.querySelectorAll('[data-zoom-range]').forEach(b=>b.onclick=()=>setRange(b.dataset.zoomRange));
    document.body.append(dialog);document.body.style.overflow='hidden';dialog.showModal();setRange(range);
  }
  function showTable(card,doc,metric,rows,button){
    const target=card.querySelector('.sv-table-area');if(!target.hidden){target.hidden=true;button.textContent='표 보기';return;}
    target.hidden=false;button.textContent='표 닫기';let page=0;const data=rows.slice().reverse(),size=50;
    const render=()=>{
      const field=metric==='pbr'?'bps':'eps';
      target.innerHTML=`<div class="sv-table-wrap"><table class="sv-table"><thead><tr><th>일자</th><th>종가 (${esc(doc.currency)})</th>${metric==='price'?'':`<th>${metric.toUpperCase()}</th><th>${field.toUpperCase()}</th><th>실적 기준</th>`}</tr></thead><tbody>${data.slice(page*size,(page+1)*size).map(([date,price])=>{const value=basisValue(doc,field,date),ref=valueAt(doc.fundamentals?.[field]||[],date),ratio=value>0?price/value:null;return `<tr><td>${date}</td><td>${fmt(price)}</td>${metric==='price'?'':`<td>${ratio==null?'N/M':fmt(ratio)+'배'}</td><td>${fmt(value)}</td><td>${ref?.[0]||'—'}</td>`}</tr>`;}).join('')}</tbody></table></div><div class="sv-pages"><button class="sv-prev" ${page===0?'disabled':''}>이전</button><span>${page+1} / ${Math.max(1,Math.ceil(data.length/size))}</span><button class="sv-next" ${(page+1)*size>=data.length?'disabled':''}>다음</button></div>`;
      target.querySelector('.sv-prev').onclick=()=>{page--;render();};target.querySelector('.sv-next').onclick=()=>{page++;render();};
    };render();
  }
  function company(id){
    const c=companies.get(id),root=document.createElement('section');root.className='sv-company';root.id='sv-'+id;root.dataset.svCompany=id;
    if(!c){root.textContent='기업 등록 정보를 확인할 수 없습니다.';return root;}
    if(c.status!=='listed'){root.innerHTML=`<p class="sv-note">${esc(c.name)} · ${esc(c.note)}</p>`;return root;}
    root.innerHTML=`<div class="sv-company-title">${esc(c.name)} · 주가와 밸류에이션</div><div class="grid financial-grid"></div>`;
    const cards=[];
    for(const metric of ['price','per','pbr']){
      const card=document.createElement('div');card.className='sv-card';card.dataset.svMetric=metric;
      const value=metric==='price'?c.price:c[metric],reason=c[metric==='per'?'eps_reason':'bps_reason'];
      card.innerHTML=`<div class="sv-head"><h3>${metric==='price'?'주가':metric.toUpperCase()+' 밴드'}</h3><span class="sv-caption">${esc(c.symbol)}</span></div><div class="sv-value"><span class="sv-number">${value==null?(metric==='price'?'—':'N/M'):fmt(value)}</span> <span class="sv-caption">${metric==='price'?esc(c.currency):value==null?'':'배'}</span></div><div class="sv-caption">${esc(c.price_date||'자료 없음')}${value==null&&reason?' · '+esc(reason):''}</div><div class="chart-wrap"><span class="sv-placeholder">화면에 들어오면 차트를 불러옵니다</span></div><div class="sv-caption sv-chart-caption"></div><div class="sv-actions"><a href="${esc(metric==='price'?c.price_source:c.financial_source||c.source_url)}" target="_blank" rel="noopener">출처 ↗</a><button class="sv-table-button">표 보기</button></div><details class="sv-details"><summary>계산 기준 자세히</summary><p class="sv-details-body">실적 TTM·기말 BPS 기준. 과거 밴드는 회계기간 기준 참고치이며 공시일 당시 투자 가능 정보를 재현하지 않습니다.</p></details><div class="sv-table-area" hidden></div>`;
      const tools=document.createElement('div');tools.className='sv-head-tools';tools.append(card.querySelector('.sv-head > .sv-caption'));
      const enlarge=document.createElement('button');enlarge.type='button';enlarge.className='sv-enlarge';enlarge.disabled=true;enlarge.setAttribute('aria-label',c.name+' '+(metric==='price'?'주가':metric.toUpperCase()+' 밴드')+' 확대 보기');enlarge.innerHTML='<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/><path d="m12 12 5 5"/></svg><span>확대</span>';tools.append(enlarge);card.querySelector('.sv-head').append(tools);
      enlarge.setAttribute('aria-haspopup','dialog');enlarge.setAttribute('aria-controls','sv-zoom-window');
      root.querySelector('.grid').append(card);cards.push(card);
    }
    const panel={root,company:c,cards,charts:new Set(),visible:false,loading:false};panels.set(root,panel);observer.observe(root);return root;
  }
  function summary(ids){
    const root=document.createElement('section');root.className='sv-summary';root.dataset.svSummary='true';
    root.innerHTML=`<div class="sv-tools"><input type="search" aria-label="주가·밸류에이션 기업 검색" placeholder="기업명·종목 검색"><span class="sv-caption">실적 TTM · 거래 통화 기준 · 수집 ${esc(index?.checked||'—')}</span></div><div class="sv-table-wrap"></div><p class="sv-note">PER은 실적 EPS, PBR은 기말 BPS 기준입니다. 적자·0 이하 순자산은 N/M으로 표시합니다. 기업 이름을 누르면 해당 차트로 이동합니다. 자동 수집: 매일 08:10 KST.</p>`;
    let sortKey=null,ascending=true;
    const render=()=>{
      const q=root.querySelector('input').value.trim().toLowerCase();let rows=ids.map(id=>companies.get(id)).filter(Boolean).filter(c=>(c.name+' '+(c.symbol||'')).toLowerCase().includes(q));
      if(sortKey)rows=rows.slice().sort((a,b)=>a[sortKey]==null?1:b[sortKey]==null?-1:(a[sortKey]-b[sortKey])*(ascending?1:-1));
      root.querySelector('.sv-table-wrap').innerHTML=`<table class="sv-table"><thead><tr><th>기업</th><th>종목</th><th>통화</th><th>종가</th><th>가격 기준일</th><th><button data-sort="per">PER(TTM) ↕</button></th><th><button data-sort="pbr">PBR ↕</button></th><th>EPS 기준일</th><th>BPS 기준일</th><th>상태</th></tr></thead><tbody>${rows.map(c=>`<tr data-company="${c.id}"><td><button data-jump="${c.id}">${esc(c.name)}</button></td><td>${esc(c.symbol||'—')}</td><td>${esc(c.currency||'—')}</td><td>${fmt(c.price)}</td><td>${esc(c.price_date||'—')}</td><td>${c.per==null?(c.status==='listed'?'N/M':'—'):fmt(c.per)+'배'}</td><td>${c.pbr==null?(c.status==='listed'?'N/M':'—'):fmt(c.pbr)+'배'}</td><td>${esc(c.eps_date||'—')}</td><td>${esc(c.bps_date||'—')}</td><td>${c.status==='listed'?(c.ok?'수집 정상':'확인 필요'):{unlisted:'비상장',delisted:'상장폐지',review:'법인 검토'}[c.status]}</td></tr>`).join('')}</tbody></table>`;
      root.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>document.getElementById('sv-'+b.dataset.jump)?.scrollIntoView({behavior:'smooth',block:'start'}));
      root.querySelectorAll('[data-sort]').forEach(b=>b.onclick=()=>{ascending=b.dataset.sort===sortKey?!ascending:true;sortKey=b.dataset.sort;render();});
    };root.querySelector('input').oninput=render;render();return root;
  }
  return {company,summary,destroy(){alive=false;closeZoom();observer.disconnect();for(const chart of [...chartSet])destroy(chart);panels.clear();}};
}

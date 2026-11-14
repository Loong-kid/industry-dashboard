/* Compact comparisons preserve source cells and carry reviewed evidence separately. */
"use strict";
function renderCPUSpecs(doc) {
  const card=document.createElement('div');card.className='card cpu-specs';
  if(!doc)return card;
  card.dataset.cpuSpecs=doc.id;
  const esc=escapeHtml,companies=[...new Set(doc.rows.map(r=>r.values[0]))],uses=[...new Set(doc.rows.map(r=>r.values[1]))];
  const displayIndices=doc.display_indices;
  const columnCategories=doc.column_views.filter(v=>!['overview','all'].includes(v.id));
  const multiFilter=(key,label,items,checked=true)=>`<div class="cpu-specs-filter-field"><span>${label}</span><details class="cpu-specs-filter" data-filter="${key}"><summary aria-label="CPU 사양 ${label} 선택"></summary><div class="cpu-specs-filter-options"><fieldset><legend>${label} 선택</legend><div class="cpu-specs-filter-actions">${key==='columns'?'<button type="button" data-selection="overview">한눈에 보기</button>':''}<button type="button" data-selection="all">전체 선택</button><button type="button" data-selection="none">전체 해제</button></div>${items.map(([id,name])=>`<label><input type="checkbox" value="${esc(id)}" ${checked?'checked':''}><span>${esc(name)}</span></label>`).join('')}</fieldset>${key==='columns'?'<p>선택한 카테고리의 열을 합쳐 표시합니다. 겹치는 열은 한 번만 표시하며 기업·용도·CPU 이름은 유지합니다.</p>':''}</div></details></div>`;
  const link=(url,label,title='')=>/^https:\/\//.test(url)?`<a href="${esc(url)}" target="_blank" rel="noopener" title="${esc(title)}">${esc(label)}</a>`:esc(label);
  card.innerHTML=`<div class="cpu-specs-panel"><div class="cpu-specs-head"><div><div class="card-name">${esc(doc.name)}</div><p>${doc.rows.length}개 CPU·SoC · ${companies.length}개 기업 · Geekbench 6·7 · 전체 사양 ${displayIndices.length}개 열</p></div><div class="cpu-specs-head-actions"><div>${link(doc.source_url,'시트 원본 ↗')}<small>가져온 날 ${esc(doc.fetched)}</small></div><button type="button" class="cpu-specs-expand" aria-haspopup="dialog" aria-expanded="false">전체화면</button></div></div>
    <div class="cpu-specs-controls">
      ${multiFilter('company','기업',companies.map(v=>[v,v]))}
      ${multiFilter('use','제품군·용도',uses.map(v=>[v,v]))}
      <label class="cpu-specs-search">검색<input type="search" aria-label="CPU 사양 검색" placeholder="CPU 이름·세대·아키텍처"></label>
      ${multiFilter('columns','열 카테고리',columnCategories.map(v=>[v.id,v.label]),false)}
      <label>값 표시<select aria-label="CPU 사양 값 표시"><option value="enriched">보완 포함</option><option value="original">시트 원본</option></select></label>
      <label class="cpu-specs-only"><input type="checkbox" aria-label="보완한 CPU만">보완한 CPU만</label><button type="button" class="cpu-specs-reset">초기화</button>
    </div><div class="cpu-specs-status"><span role="status" aria-live="polite"></span><span>오른쪽으로 CPU 구성·L1·L2·L3 캐시 → · 40px 고정 행 · 마우스 메모 / 상세</span></div>
    <div class="order-table-wrap cpu-specs-scroll" tabindex="0" role="region" aria-label="CPU 사양·Geekbench 표 · 가로·세로 스크롤"><table><caption>Geekbench는 같은 버전끼리 비교 · 싱글 / 멀티 순서 · 빈칸은 —</caption><colgroup></colgroup><thead></thead><tbody></tbody></table></div>
    <p class="ir-scope-note">${esc(doc.note)}</p>
    <details class="cpu-specs-evidence"><summary>출처와 보완 기준 · ${doc.supplement_count}개 값 / ${doc.supplemented_products}개 CPU · M 시리즈 공정 ${doc.foundry_review_count}개</summary>
      <p>시트 기재값을 보존하고 보완값과 제품별 파운드리 확인을 따로 표시합니다. ‘시트 원본’은 표시 중인 사양의 원래 값을 보여줍니다. Geekbench는 6·7만 표시하며 이전 버전은 원본 시트에서 확인할 수 있습니다. Apple M 시리즈는 설계사 Apple과 제조사 TSMC를 구분합니다. H2·R1은 제조사를 임의로 채우지 않았습니다.</p>
      ${Object.values(doc.sources).map(s=>`<p>${link(s.url,s.title+' ↗')}<small>${esc(s.note)} 확인 ${esc(s.checked)}</small></p>`).join('')}<p>${esc(doc.update_note)}</p></details>
    <div class="cpu-specs-memo" role="tooltip" hidden></div>
    <dialog class="cpu-specs-dialog" aria-label="CPU 상세 사양"><div class="cpu-specs-dialog-head"><h2></h2><button type="button" aria-label="CPU 상세 닫기">닫기</button></div><div class="cpu-specs-dialog-body"></div></dialog></div><dialog class="cpu-specs-fullscreen" aria-label="CPU 표 전체화면"></dialog>`;
  const mode=card.querySelector('select'),search=card.querySelector('input[type="search"]'),only=card.querySelector('.cpu-specs-only input');
  const region=card.querySelector('.cpu-specs-scroll'),table=region.querySelector('table'),memo=card.querySelector('.cpu-specs-memo'),dialog=card.querySelector('.cpu-specs-dialog');
  const filters=Object.fromEntries([...card.querySelectorAll('[data-filter]')].map(el=>[el.dataset.filter,el]));
  const boxes=key=>[...filters[key].querySelectorAll('input[type="checkbox"]')];
  const selected=key=>new Set(boxes(key).filter(input=>input.checked).map(input=>input.value));
  let compactView=(doc.default_view||'overview')==='overview';
  if(!compactView)boxes('columns').forEach(input=>input.checked=doc.default_view==='all'||input.value===doc.default_view);
  const updateFilters=()=>{
    for(const [key,filter] of Object.entries(filters)){
      const inputs=boxes(key),on=inputs.filter(input=>input.checked);
      filter.querySelector('summary').textContent=key==='columns'&&compactView?'한눈에 보기':!on.length?(key==='columns'?'기본정보만':'선택 없음'):on.length===inputs.length?(key==='company'?'전체 기업':key==='use'?'전체 용도':'전체 사양'):on.length===1?on[0].nextElementSibling.textContent:`${on.length}개 선택`;
      filter.querySelector('[data-selection="overview"]')?.setAttribute('aria-pressed',String(compactView));
    }
  };
  const byId=new Map(doc.rows.map(row=>[row.id,row]));
  let sortIndex=null,sortDirection=1,memoTarget=null,hideTimer=null,memoItems=new Map();
  const evidence=(row,i)=>mode.value==='original'?null:i===7&&row.foundry?{source:row.foundry.source,note:row.foundry.note}:row.supplements[i];
  const value=(row,i)=>mode.value==='original'?row.values[i]:i===7&&row.foundry?`${row.foundry.foundry} ${row.foundry.node} · ${row.foundry.process_nm} nm`:row.supplements[i]?.value??row.values[i];
  const format=v=>v&&/^\d+$/.test(v)?Number(v).toLocaleString('ko-KR'):v||'—';
  const fieldsHTML=(row,indices)=>indices.map(i=>{const extra=evidence(row,i),source=extra&&doc.sources[extra.source];return `<div><dt>${esc(doc.columns[i].label)}</dt><dd>${esc(value(row,i)||'—')}${extra?`<small>${esc(extra.note)} ${link(source.url,source.title+' ↗')}</small>`:doc.columns[i].numeric&&row.values[i]?'<small>시트 기재 점수 · 실측 링크 미포함</small>':''}</dd></div>`;}).join('');
  const hideMemo=()=>{clearTimeout(hideTimer);memo.hidden=true;memoTarget=null;};
  const delayHide=()=>{clearTimeout(hideTimer);hideTimer=setTimeout(hideMemo,160);};
  const showMemo=target=>{
    clearTimeout(hideTimer);if(target===memoTarget)return;
    const item=memoItems.get(target.dataset.memo);if(!item)return;
    memoTarget=target;memo.innerHTML=`<strong>${esc(item.row.values[2])} · ${esc(item.label)}</strong><dl>${fieldsHTML(item.row,item.indices)}</dl>`;memo.hidden=false;
    const box=target.getBoundingClientRect(),size=memo.getBoundingClientRect();
    memo.style.left=Math.max(8,Math.min(box.left,innerWidth-size.width-8))+'px';
    memo.style.top=Math.max(8,box.bottom+size.height+12>innerHeight?box.top-size.height-8:box.bottom+8)+'px';
  };
  const detailButton=row=>`<button type="button" class="cpu-row-details" data-row="${row.id}" aria-label="${esc(row.values[2])} 상세 사양">상세</button>`;
  const overview=[
    {key:'chip',label:'CPU · 제조사 / 용도',indices:[2,0,1,3,12],sort:2,width:184},
    {key:'released',label:'출시일',indices:[6],sort:6,width:102},
    {key:'process',label:'파운드리·공정',indices:[7],sort:7,width:118},
    {key:'cores',label:'코어 / 스레드',indices:[23,8],sort:23,width:83},
    {key:'clock',label:'최대 클럭',indices:[10],sort:10,width:76},
    {key:'memory',label:'최대 메모리',indices:[16],sort:16,width:81},
    {key:'bandwidth',label:'메모리 대역폭',indices:[15],sort:15,width:96},
    {key:'gb6',label:'GB6 · 싱글 / 멀티',indices:[31,32],sort:32,width:116,numeric:true},
    {key:'gb7',label:'GB7 · 싱글 / 멀티',indices:[33,34],sort:34,width:116,numeric:true},
    {key:'composition',label:'CPU 구성',indices:[8],sort:8,width:200},
    {key:'architecture',label:'아키텍처 / 코드명',indices:[12],sort:12,width:150},
    {key:'l1',label:'L1 캐시',indices:[18],sort:18,width:120},
    {key:'l2',label:'L2 캐시',indices:[19],sort:19,width:140},
    {key:'l3',label:'L3 캐시',indices:[20],sort:20,width:140},
    {key:'detail',label:'상세',indices:[],width:48}
  ];
  const cell=(row,col,compact)=>{
    if(col.key==='detail')return `<td data-column="detail"><div class="cpu-specs-cell">${detailButton(row)}</div></td>`;
    const index=col.indices[0],extra=evidence(row,index),source=extra&&doc.sources[extra.source],id=row.id+':'+col.key;
    memoItems.set(id,{row,label:col.label,indices:col.indices});
    let body;
    if(compact&&col.key==='chip')body=`<span class="cpu-specs-identity"><b>${esc(row.values[2])}</b><small>${esc(row.values[0]+' · '+row.values[1])}</small></span>`;
    else if(compact&&['gb6','gb7'].includes(col.key))body=col.indices.map(i=>esc(format(value(row,i)))).join(' <span class="cpu-specs-slash">/</span> ');
    else if(compact&&col.key==='cores')body=esc(value(row,23)||value(row,8).match(/(?:최대\s*)?\d+\s*코어/)?.[0]||value(row,8)||'—');
    else body=index===36&&value(row,index)?link(value(row,index),'공식 원문 ↗',value(row,index)):esc(value(row,index)||'—');
    const mark=extra?`<a class="cpu-specs-ref" href="${esc(source.url)}" target="_blank" rel="noopener" aria-label="${esc(row.values[2]+' '+col.label+' 보완 출처')}">↗</a>`:'';
    const isName=compact?col.key==='chip':index===2;
    const classes=[isName?'cpu-specs-name':'',col.numeric?'cpu-specs-number':'',extra?(index===7&&row.foundry?'cpu-specs-reviewed':'cpu-specs-added'):''].join(' ');
    return `<${isName?'th scope="row"':'td'} class="${classes}" data-column="${compact?col.key:doc.columns[index].id}"><div class="cpu-specs-cell" data-memo="${id}"><span class="cpu-specs-value">${body}</span>${mark}</div></${isName?'th':'td'}>`;
  };
  const draw=()=>{
    hideMemo();memoItems=new Map();
    const compact=compactView,chosen=selected('columns'),indices=new Set([0,1,2]);
    columnCategories.filter(v=>chosen.has(v.id)).forEach(v=>v.indices.forEach(i=>indices.add(i)));
    const visible=compact?overview:[...displayIndices.filter(i=>indices.has(i)).map(i=>({key:String(i),indices:[i],sort:i,label:doc.columns[i].label,width:i===2?190:i===0?80:i===1?110:doc.columns[i].numeric?100:i===22||i===35?170:115,numeric:doc.columns[i].numeric})),{key:'detail',label:'상세',indices:[],width:48}];
    const query=search.value.trim().toLocaleLowerCase();
    const chosenCompanies=selected('company'),chosenUses=selected('use');
    const rows=doc.rows.filter(row=>chosenCompanies.has(row.values[0])&&chosenUses.has(row.values[1])&&(!only.checked||Object.keys(row.supplements).length)&&(!query||displayIndices.some(i=>String(value(row,i)).toLocaleLowerCase().includes(query))));
    if(sortIndex!==null)rows.sort((a,b)=>{const av=value(a,sortIndex),bv=value(b,sortIndex);if(!av||!bv)return av?-1:bv?1:a.sheet_row-b.sheet_row;const result=doc.columns[sortIndex].numeric?Number(av)-Number(bv):String(av).localeCompare(String(bv),'ko',{numeric:true});return result*sortDirection||a.sheet_row-b.sheet_row;});
    table.classList.toggle('cpu-specs-overview',compact);table.style.width=visible.reduce((sum,c)=>sum+c.width,0)+'px';
    table.querySelector('colgroup').innerHTML=visible.map(c=>`<col class="${c.key==='chip'||c.indices[0]===2?'cpu-specs-col-name':''}" style="width:${c.width}px">`).join('');
    table.querySelector('thead').innerHTML=`<tr>${visible.map(c=>`<th scope="col" class="${c.key==='chip'||c.indices[0]===2?'cpu-specs-name ':''}${c.numeric?'cpu-specs-number':''}" data-column="${compact||c.key==='detail'?c.key:doc.columns[c.indices[0]].id}" aria-sort="${sortIndex===c.sort?(sortDirection===1?'ascending':'descending'):'none'}">${c.sort==null?esc(c.label):`<button type="button" data-sort="${c.sort}" title="${esc(c.label)}">${esc(c.label)}<span aria-hidden="true">${sortIndex===c.sort?(sortDirection===1?' ▲':' ▼'):' ↕'}</span></button>`}</th>`).join('')}</tr>`;
    table.querySelector('tbody').innerHTML=rows.length?rows.map(row=>`<tr data-sheet-row="${row.sheet_row}">${visible.map(c=>cell(row,c,compact)).join('')}</tr>`).join(''):`<tr><td colspan="${visible.length}"><div class="cpu-specs-cell">조건에 맞는 CPU가 없습니다. 검색어나 필터를 변경해 주세요.</div></td></tr>`;
    card.querySelector('[role="status"]').textContent=`${rows.length} / ${doc.rows.length}개 CPU · ${compact?'요약·구성·캐시 ':''}${visible.length}개 열 · ${mode.value==='enriched'?'보완 포함':'시트 원본'}`;
  };
  const resetScroll=()=>{region.scrollLeft=!compactView&&innerWidth<=600?190:0;region.scrollTop=0;};
  table.addEventListener('click',event=>{
    const sort=event.target.closest('[data-sort]'),detail=event.target.closest('[data-row]');
    if(sort){const index=Number(sort.dataset.sort);sortDirection=sortIndex===index?-sortDirection:doc.columns[index].numeric?-1:1;sortIndex=index;draw();}
    if(detail){hideMemo();const row=byId.get(detail.dataset.row);dialog.querySelector('h2').textContent=row.values[2];dialog.querySelector('.cpu-specs-dialog-body').innerHTML=`<p>${esc(row.values[0]+' · '+row.values[1])} · 시트 ${row.sheet_row}행</p><dl>${fieldsHTML(row,displayIndices)}</dl>`;dialog.showModal();}
  });
  dialog.querySelector('button').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  table.addEventListener('pointerover',event=>{if(event.pointerType!=='touch'){const target=event.target.closest('[data-memo]');if(target)showMemo(target);}});
  table.addEventListener('pointerout',event=>{if(!memo.contains(event.relatedTarget))delayHide();});
  table.addEventListener('focusin',event=>{const target=event.target.closest('[data-memo]');if(target)showMemo(target);});
  table.addEventListener('focusout',delayHide);memo.addEventListener('pointerenter',()=>clearTimeout(hideTimer));memo.addEventListener('pointerleave',delayHide);memo.addEventListener('focusin',()=>clearTimeout(hideTimer));memo.addEventListener('focusout',delayHide);
  card.addEventListener('keydown',event=>{
    if(event.key!=='Escape'||dialog.open)return;
    hideMemo();
    const open=Object.values(filters).find(filter=>filter.open);
    if(open){event.preventDefault();event.stopPropagation();open.open=false;open.querySelector('summary').focus();}
  });region.addEventListener('scroll',hideMemo,{passive:true});
  for(const [key,filter] of Object.entries(filters)){
    filter.addEventListener('toggle',()=>{
      if(!filter.open)return;
      Object.values(filters).forEach(other=>{if(other!==filter)other.open=false;});
      const menu=filter.querySelector('.cpu-specs-filter-options');menu.style.translate='0';menu.style.top='calc(100% + 6px)';menu.style.bottom='auto';
      const below=innerHeight-menu.getBoundingClientRect().top-12,above=filter.getBoundingClientRect().top-12;
      const upwards=below<144&&above>below;
      if(upwards){menu.style.top='auto';menu.style.bottom='calc(100% + 6px)';}
      menu.style.maxHeight=Math.max(48,Math.min(400,innerHeight*.5,upwards?above:below))+'px';
      const box=menu.getBoundingClientRect(),shift=Math.min(0,innerWidth-12-box.right);
      menu.style.translate=Math.max(12-box.left,shift)+'px';
    });
    const changed=(overview=false)=>{if(key==='columns')compactView=overview;updateFilters();draw();if(key==='columns')resetScroll();else region.scrollTop=0;};
    filter.addEventListener('change',()=>changed());
    filter.addEventListener('click',event=>{
      const action=event.target.closest('[data-selection]');if(!action)return;
      boxes(key).forEach(input=>input.checked=action.dataset.selection==='all');
      changed(action.dataset.selection==='overview');
    });
  }
  card.addEventListener('click',event=>{if(!event.target.closest('[data-filter]'))Object.values(filters).forEach(filter=>filter.open=false);});
  [mode,only].forEach(control=>control.addEventListener('change',()=>{if(control===mode){only.disabled=mode.value==='original';if(only.disabled)only.checked=false;}draw();region.scrollTop=0;}));
  search.addEventListener('input',()=>{region.scrollTop=0;draw();});
  card.querySelector('.cpu-specs-reset').addEventListener('click',()=>{boxes('company').forEach(input=>input.checked=true);boxes('use').forEach(input=>input.checked=true);compactView=(doc.default_view||'overview')==='overview';boxes('columns').forEach(input=>input.checked=!compactView&&(doc.default_view==='all'||input.value===doc.default_view));Object.values(filters).forEach(filter=>filter.open=false);mode.value='enriched';search.value='';only.checked=only.disabled=false;sortIndex=null;sortDirection=1;updateFilters();draw();resetScroll();});
  const panel=card.querySelector('.cpu-specs-panel'),fullscreen=card.querySelector('.cpu-specs-fullscreen'),expand=card.querySelector('.cpu-specs-expand');
  let pagePosition={left:0,top:0};
  expand.addEventListener('click',()=>{
    hideMemo();Object.values(filters).forEach(filter=>filter.open=false);
    if(fullscreen.open){fullscreen.close();return;}
    pagePosition={left:window.scrollX,top:window.scrollY};
    const position={left:region.scrollLeft,top:region.scrollTop};
    fullscreen.append(panel);fullscreen.showModal();
    expand.textContent='전체화면 닫기';expand.setAttribute('aria-expanded','true');
    region.scrollTo(position);expand.focus({preventScroll:true});
  });
  fullscreen.addEventListener('close',()=>{
    const position={left:region.scrollLeft,top:region.scrollTop};
    card.insertBefore(panel,fullscreen);expand.textContent='전체화면';expand.setAttribute('aria-expanded','false');
    if(card.isConnected){region.scrollTo(position);expand.focus({preventScroll:true});window.scrollTo({...pagePosition,behavior:'instant'});}
  });
  updateFilters();draw();resetScroll();return card;
}

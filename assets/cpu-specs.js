/* Compact comparisons preserve source cells and carry reviewed evidence separately. */
"use strict";
function renderCPUSpecs(doc) {
  const card=document.createElement('div');card.className='card cpu-specs';
  if(!doc)return card;
  card.dataset.cpuSpecs=doc.id;
  const esc=escapeHtml,companies=[...new Set(doc.rows.map(r=>r.values[0]))],uses=[...new Set(doc.rows.map(r=>r.values[1]))];
  const options=items=>items.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  const link=(url,label,title='')=>/^https:\/\//.test(url)?`<a href="${esc(url)}" target="_blank" rel="noopener" title="${esc(title)}">${esc(label)}</a>`:esc(label);
  card.innerHTML=`<div class="cpu-specs-head"><div><div class="card-name">${esc(doc.name)}</div><p>${doc.rows.length}개 CPU·SoC · ${companies.length}개 기업 · 요약 / 원본 ${doc.columns.length}개 열</p></div><div>${link(doc.source_url,'시트 원본 ↗')}<small>가져온 날 ${esc(doc.fetched)}</small></div></div>
    <div class="cpu-specs-controls">
      <label>기업<select aria-label="CPU 사양 기업"><option value="all">전체 기업</option>${options(companies)}</select></label>
      <label>제품군·용도<select aria-label="CPU 사양 용도"><option value="all">전체 용도</option>${options(uses)}</select></label>
      <label class="cpu-specs-search">검색<input type="search" aria-label="CPU 사양 검색" placeholder="CPU 이름·세대·아키텍처"></label>
      <label>열 보기<select aria-label="CPU 사양 열 보기">${doc.column_views.map(v=>`<option value="${esc(v.id)}">${esc(v.label)}</option>`).join('')}</select></label>
      <label>값 표시<select aria-label="CPU 사양 값 표시"><option value="enriched">보완 포함</option><option value="original">시트 원본</option></select></label>
      <label class="cpu-specs-only"><input type="checkbox" aria-label="보완한 CPU만">보완한 CPU만</label><button type="button" class="cpu-specs-reset">초기화</button>
    </div><div class="cpu-specs-status"><span role="status" aria-live="polite"></span><span>40px 고정 행 · 긴 값은 마우스 메모 · 전체 내용은 상세</span></div>
    <div class="order-table-wrap cpu-specs-scroll" tabindex="0" role="region" aria-label="CPU 사양·Geekbench 표 · 가로·세로 스크롤"><table><caption>Geekbench는 같은 버전끼리 비교 · 싱글 / 멀티 순서 · 빈칸은 —</caption><colgroup></colgroup><thead></thead><tbody></tbody></table></div>
    <p class="ir-scope-note">${esc(doc.note)}</p>
    <details class="cpu-specs-evidence"><summary>출처와 보완 기준 · ${doc.supplement_count}개 값 / ${doc.supplemented_products}개 CPU · M 시리즈 공정 ${doc.foundry_review_count}개</summary>
      <p>시트 기재값을 보존하고 보완값과 제품별 파운드리 확인을 따로 표시합니다. ‘시트 원본’과 ‘전체 열’을 선택하면 원본 표를 볼 수 있습니다. Apple M 시리즈는 설계사 Apple과 제조사 TSMC를 구분합니다. H2·R1은 제조사를 임의로 채우지 않았습니다.</p>
      ${Object.values(doc.sources).map(s=>`<p>${link(s.url,s.title+' ↗')}<small>${esc(s.note)} 확인 ${esc(s.checked)}</small></p>`).join('')}<p>${esc(doc.update_note)}</p></details>
    <div class="cpu-specs-memo" role="tooltip" hidden></div>
    <dialog class="cpu-specs-dialog" aria-label="CPU 상세 사양"><div class="cpu-specs-dialog-head"><h2></h2><button type="button" aria-label="CPU 상세 닫기">닫기</button></div><div class="cpu-specs-dialog-body"></div></dialog>`;
  const [company,use,columns,mode]=card.querySelectorAll('select'),search=card.querySelector('input[type="search"]'),only=card.querySelector('input[type="checkbox"]');
  const region=card.querySelector('.cpu-specs-scroll'),table=region.querySelector('table'),memo=card.querySelector('.cpu-specs-memo'),dialog=card.querySelector('dialog');
  const byId=new Map(doc.rows.map(row=>[row.id,row]));
  let sortIndex=null,sortDirection=1,memoTarget=null,hideTimer=null,memoItems=new Map();
  columns.value=doc.default_view||'overview';
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
    {key:'process',label:'파운드리·공정',indices:[7],sort:7,width:118},
    {key:'cores',label:'코어 / 스레드',indices:[23,8],sort:23,width:83},
    {key:'clock',label:'최대 클럭',indices:[10],sort:10,width:76},
    {key:'memory',label:'최대 메모리',indices:[16],sort:16,width:81},
    {key:'bandwidth',label:'메모리 대역폭',indices:[15],sort:15,width:96},
    {key:'gb6',label:'GB6 · 싱글 / 멀티',indices:[31,32],sort:32,width:116,numeric:true},
    {key:'gb7',label:'GB7 · 싱글 / 멀티',indices:[33,34],sort:34,width:116,numeric:true},
    {key:'detail',label:'상세',indices:[],width:48}
  ];
  const cell=(row,col,compact)=>{
    if(col.key==='detail')return `<td><div class="cpu-specs-cell">${detailButton(row)}</div></td>`;
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
    return `<${isName?'th scope="row"':'td'} class="${classes}" data-column="${compact?col.key:doc.columns[index].id}"><div class="cpu-specs-cell" data-memo="${id}"><span class="cpu-specs-value">${body}</span>${mark}${!compact&&isName?detailButton(row):''}</div></${isName?'th':'td'}>`;
  };
  const draw=()=>{
    hideMemo();memoItems=new Map();
    const view=doc.column_views.find(v=>v.id===columns.value),compact=view.id==='overview';
    const visible=compact?overview:view.indices.map(i=>({key:String(i),indices:[i],sort:i,label:doc.columns[i].label,width:i===2?190:i===0?80:i===1?110:doc.columns[i].numeric?100:i===22||i===35?170:115,numeric:doc.columns[i].numeric}));
    const query=search.value.trim().toLocaleLowerCase();
    const rows=doc.rows.filter(row=>(company.value==='all'||row.values[0]===company.value)&&(use.value==='all'||row.values[1]===use.value)&&(!only.checked||Object.keys(row.supplements).length)&&(!query||doc.columns.some((_,i)=>String(value(row,i)).toLocaleLowerCase().includes(query))));
    if(sortIndex!==null)rows.sort((a,b)=>{const av=value(a,sortIndex),bv=value(b,sortIndex);if(!av||!bv)return av?-1:bv?1:a.sheet_row-b.sheet_row;const result=doc.columns[sortIndex].numeric?Number(av)-Number(bv):String(av).localeCompare(String(bv),'ko',{numeric:true});return result*sortDirection||a.sheet_row-b.sheet_row;});
    table.classList.toggle('cpu-specs-overview',compact);table.style.width=visible.reduce((sum,c)=>sum+c.width,0)+'px';
    table.querySelector('colgroup').innerHTML=visible.map(c=>`<col class="${c.key==='chip'||c.indices[0]===2?'cpu-specs-col-name':''}" style="width:${c.width}px">`).join('');
    table.querySelector('thead').innerHTML=`<tr>${visible.map(c=>`<th scope="col" class="${c.key==='chip'||c.indices[0]===2?'cpu-specs-name ':''}${c.numeric?'cpu-specs-number':''}" data-column="${compact?c.key:doc.columns[c.indices[0]].id}" aria-sort="${sortIndex===c.sort?(sortDirection===1?'ascending':'descending'):'none'}">${c.sort==null?esc(c.label):`<button type="button" data-sort="${c.sort}" title="${esc(c.label)}">${esc(c.label)}<span aria-hidden="true">${sortIndex===c.sort?(sortDirection===1?' ▲':' ▼'):' ↕'}</span></button>`}</th>`).join('')}</tr>`;
    table.querySelector('tbody').innerHTML=rows.length?rows.map(row=>`<tr data-sheet-row="${row.sheet_row}">${visible.map(c=>cell(row,c,compact)).join('')}</tr>`).join(''):`<tr><td colspan="${visible.length}"><div class="cpu-specs-cell">조건에 맞는 CPU가 없습니다. 검색어나 필터를 변경해 주세요.</div></td></tr>`;
    card.querySelector('[role="status"]').textContent=`${rows.length} / ${doc.rows.length}개 CPU · ${compact?'요약 9열':visible.length+'개 열'} · ${mode.value==='enriched'?'보완 포함':'시트 원본'}`;
  };
  const resetScroll=()=>{region.scrollLeft=columns.value!=='overview'&&innerWidth<=600?190:0;region.scrollTop=0;};
  table.addEventListener('click',event=>{
    const sort=event.target.closest('[data-sort]'),detail=event.target.closest('[data-row]');
    if(sort){const index=Number(sort.dataset.sort);sortDirection=sortIndex===index?-sortDirection:doc.columns[index].numeric?-1:1;sortIndex=index;draw();}
    if(detail){hideMemo();const row=byId.get(detail.dataset.row);dialog.querySelector('h2').textContent=row.values[2];dialog.querySelector('.cpu-specs-dialog-body').innerHTML=`<p>${esc(row.values[0]+' · '+row.values[1])} · 시트 ${row.sheet_row}행</p><dl>${fieldsHTML(row,doc.columns.map((_,i)=>i))}</dl>`;dialog.showModal();}
  });
  dialog.querySelector('button').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  table.addEventListener('pointerover',event=>{if(event.pointerType!=='touch'){const target=event.target.closest('[data-memo]');if(target)showMemo(target);}});
  table.addEventListener('pointerout',event=>{if(!memo.contains(event.relatedTarget))delayHide();});
  table.addEventListener('focusin',event=>{const target=event.target.closest('[data-memo]');if(target)showMemo(target);});
  table.addEventListener('focusout',delayHide);memo.addEventListener('pointerenter',()=>clearTimeout(hideTimer));memo.addEventListener('pointerleave',delayHide);memo.addEventListener('focusin',()=>clearTimeout(hideTimer));memo.addEventListener('focusout',delayHide);
  card.addEventListener('keydown',event=>{if(event.key==='Escape')hideMemo();});region.addEventListener('scroll',hideMemo,{passive:true});
  [company,use,columns,mode,only].forEach(control=>control.addEventListener('change',()=>{if(control===mode){only.disabled=mode.value==='original';if(only.disabled)only.checked=false;}draw();if(control===columns)resetScroll();else region.scrollTop=0;}));
  search.addEventListener('input',()=>{region.scrollTop=0;draw();});
  card.querySelector('.cpu-specs-reset').addEventListener('click',()=>{company.value=use.value='all';columns.value=doc.default_view||'overview';mode.value='enriched';search.value='';only.checked=only.disabled=false;sortIndex=null;sortDirection=1;draw();resetScroll();});
  draw();resetScroll();return card;
}

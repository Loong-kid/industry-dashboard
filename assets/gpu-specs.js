/* GPU and AI comparisons share the dashboard's compact, fixed-height table. */
"use strict";
function renderGPUSpecs(doc) {
  const card=document.createElement('div');card.className='card cpu-specs gpu-specs';
  if(!doc)return card;
  card.dataset.gpuSpecs=doc.id;
  const esc=escapeHtml,byId=new Map(doc.rows.map(r=>[r.id,r])),columns=new Map(doc.columns.map(c=>[c.id,c]));
  const options=items=>items.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
  const link=(url,label)=>/^https:\/\//.test(url)?`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`:esc(label);
  const ai=doc.id==='nvidia_ai_specs',prefix=ai?'AI 가속기':'GPU';
  card.innerHTML=`<div class="cpu-specs-head"><div><div class="card-name">${esc(doc.name)}</div><p>${esc(doc.evidence_summary)}</p></div><div>${link(doc.source_url,'시트 원본 ↗')}<small>가져온 날 ${esc(doc.fetched)} · 공개 자료 확인 ${esc(doc.updated)}</small></div></div>
    <div class="cpu-specs-controls">
      <label>기업<select aria-label="${prefix} 기업"><option value="all">전체 기업</option>${options([...new Set(doc.rows.map(r=>r.company))])}</select></label>
      <label>${ai?'제품 단위':'형태·용도'}<select aria-label="${prefix} 제품 단위"><option value="all">전체 단위</option>${options([...new Set(doc.rows.map(r=>r.group))])}</select></label>
      <label class="cpu-specs-search">검색<input type="search" aria-label="${prefix} 검색" placeholder="${ai?'제품·HBM·프로파일':'GPU 이름·아키텍처·메모리'}"></label>
      <label>열 보기<select aria-label="${prefix} 열 보기">${doc.views.map(v=>`<option value="${esc(v.id)}">${esc(v.label)}</option>`).join('')}</select></label>
      <label>값 표시<select aria-label="${prefix} 값 표시"><option value="reviewed">보완·검토 포함</option><option value="original">시트 원본</option></select></label>
      <button type="button" class="cpu-specs-reset">초기화</button>
    </div><div class="cpu-specs-status"><span role="status" aria-live="polite"></span><span>${esc(doc.scroll_hint)}</span></div>
    <div class="order-table-wrap cpu-specs-scroll" role="region" tabindex="0" aria-label="${prefix} 비교표 · 가로·세로 스크롤"><table><caption>${ai?'Dense / Sparse 순서 · 제조사 이론 성능 · GPU·시스템·랙 단위 확인':'Geekbench 7 · API별 비교 · Time Spy는 원본 대표값'} · 빈칸은 —</caption><colgroup></colgroup><thead></thead><tbody></tbody></table></div>
    <p class="ir-scope-note">${esc(doc.note)}</p>
    <details class="cpu-specs-evidence"><summary>출처와 보완·검토 기준</summary><p>원본 기재값은 보존합니다. 색이 있는 셀의 ↗는 해당 보완·검토값의 근거입니다. 출처 표시가 없는 원본 값은 이번에 개별 검증한 값이 아닙니다. ‘시트 원본’을 선택하면 추가 프로파일을 제외한 원본 기재값을 확인할 수 있습니다.</p>${Object.values(doc.sources).map(s=>`<p>${link(s.url,s.title+' ↗')}<small>${esc(s.note)} 확인 ${esc(s.checked)}</small></p>`).join('')}<p>${esc(doc.update_note)}</p></details>
    <div class="cpu-specs-memo" role="tooltip" hidden></div>
    <dialog class="cpu-specs-dialog" aria-label="${prefix} 상세 사양"><div class="cpu-specs-dialog-head"><h2></h2><button type="button" aria-label="${prefix} 상세 닫기">닫기</button></div><div class="cpu-specs-dialog-body"></div></dialog>`;
  const [company,group,view,mode]=card.querySelectorAll('select'),search=card.querySelector('input');
  const region=card.querySelector('.cpu-specs-scroll'),table=region.querySelector('table'),dialog=card.querySelector('dialog'),memo=card.querySelector('[role="tooltip"]');
  let sortKey=null,direction=1,memoTarget=null,hideTimer=null;
  const reviewed=()=>mode.value==='reviewed';
  const evidence=(row,key)=>reviewed()?row.reviews[key]:null;
  const value=(row,key)=>evidence(row,key)?.value??row.original[key]??'';
  const name=row=>value(row,doc.name_key)||row.name;
  const format=(row,c)=>{const v=value(row,c.id);if(ai&&['fp4','fp8','fp16'].includes(c.id)&&v&&!evidence(row,c.id))return v+' · 원본 D/S 미검증';return c.numeric&&/^\d+$/.test(v)?Number(v).toLocaleString('ko-KR'):v||'—';};
  const sortValue=(row,c)=>{
    const v=String(value(row,c.id));if(!v)return null;
    if(c.numeric)return Number(v.replaceAll(',',''));
    if(!ai&&c.id==='N')return Number(v.match(/[\d.]+/)?.[0])||null;
    if(ai&&['fp4','fp8','fp16','fp32','power','memory','bandwidth','nvlink'].includes(c.id)){
      if(['fp4','fp8','fp16'].includes(c.id)&&(!evidence(row,c.id)||v.includes('비 Tensor')))return null;
      const number=Number(v.replaceAll(',','').match(/[\d.]+/)?.[0]);if(!Number.isFinite(number)||!number)return null;
      const factors=c.id==='power'?{kw:1000,w:1}:c.id.startsWith('fp')?{pflops:1000,tflops:1}:{tb:1000,gb:1,mb:.001,kb:.000001};
      const unit=v.toLowerCase().match(c.id==='power'?/kw|w/:c.id.startsWith('fp')?/pflops|tflops/:/tb|gb|mb|kb/)?.[0];
      return unit?number*factors[unit]:null;
    }
    return v;
  };
  const fieldHTML=(row,key)=>{
    const c=columns.get(key),extra=evidence(row,key),source=extra&&doc.sources[extra.source];
    return `<div><dt>${esc(c.label)}</dt><dd>${c.url&&value(row,key)?link(value(row,key),'원문 ↗'):esc(format(row,c))}${extra?`<small>${esc(extra.note)} ${link(source.url,source.title+' ↗')}${row.original[key]&&row.original[key]!==extra.value?`<br>시트 원본: ${esc(row.original[key])}`:''}</small>`:value(row,key)?'<small>시트 기재값 · 이번 보완에서 개별 검증하지 않은 항목</small>':''}</dd></div>`;
  };
  const hideMemo=()=>{clearTimeout(hideTimer);memo.hidden=true;memoTarget=null;};
  const delayHide=()=>{clearTimeout(hideTimer);hideTimer=setTimeout(hideMemo,160);};
  const showMemo=target=>{
    clearTimeout(hideTimer);if(target===memoTarget)return;
    const row=byId.get(target.dataset.row),key=target.dataset.field;if(!row||!columns.has(key))return;
    memoTarget=target;memo.innerHTML=`<strong>${esc(name(row))}</strong><dl>${fieldHTML(row,key)}</dl>`;memo.hidden=false;
    const box=target.getBoundingClientRect(),size=memo.getBoundingClientRect();
    memo.style.left=Math.max(8,Math.min(box.left,innerWidth-size.width-8))+'px';
    memo.style.top=Math.max(8,box.bottom+size.height+12>innerHeight?box.top-size.height-8:box.bottom+8)+'px';
  };
  const detailButton=row=>`<button type="button" class="cpu-row-details" data-detail="${esc(row.id)}" aria-label="${esc(name(row))} 상세 사양">상세</button>`;
  const draw=()=>{
    hideMemo();
    let visible=doc.views.find(v=>v.id===view.value).keys.map(k=>columns.get(k));
    if(ai&&group.value==='네트워크'&&view.value==='overview')visible=['name','network','architecture','configuration','scope_note'].map(k=>columns.get(k));
    const query=search.value.trim().toLocaleLowerCase();
    const rows=doc.rows.filter(row=>(reviewed()||row.sheet_row!==null)&&(company.value==='all'||row.company===company.value)&&(group.value==='all'||row.group===group.value)&&(!query||[name(row),row.group,...doc.columns.map(c=>value(row,c.id))].some(v=>String(v).toLocaleLowerCase().includes(query))));
    if(sortKey)rows.sort((a,b)=>{const c=columns.get(sortKey),av=sortValue(a,c),bv=sortValue(b,c);if(av===null||bv===null)return av!==null?-1:bv!==null?1:0;const result=typeof av==='number'?av-bv:String(av).localeCompare(String(bv),'ko',{numeric:true});return result*direction;});
    table.style.width=visible.reduce((sum,c)=>sum+c.width,48)+'px';
    table.querySelector('colgroup').innerHTML=visible.map(c=>`<col class="${c.id===doc.name_key?'cpu-specs-col-name':''}" style="width:${c.width}px">`).join('')+'<col style="width:48px">';
    table.querySelector('thead').innerHTML='<tr>'+visible.map(c=>`<th scope="col" data-column="${esc(c.id)}" class="${c.id===doc.name_key?'cpu-specs-name ':''}${c.numeric?'cpu-specs-number':''}" aria-sort="${sortKey===c.id?(direction===1?'ascending':'descending'):'none'}"><button type="button" data-sort="${esc(c.id)}" title="${esc(c.label)}">${esc(c.label)} ${sortKey===c.id?(direction===1?'▲':'▼'):'↕'}</button></th>`).join('')+'<th scope="col" data-column="detail">상세</th></tr>';
    table.querySelector('tbody').innerHTML=rows.length?rows.map(row=>`<tr data-row-id="${esc(row.id)}">${visible.map(c=>{const extra=evidence(row,c.id),isName=c.id===doc.name_key;return `<${isName?'th scope="row"':'td'} data-column="${esc(c.id)}" class="${isName?'cpu-specs-name ':''}${c.numeric?'cpu-specs-number ':''}${extra?'cpu-specs-added':''}"><div class="cpu-specs-cell" data-row="${esc(row.id)}" data-field="${esc(c.id)}"><span class="cpu-specs-value">${isName?`<span class="cpu-specs-identity"><b>${esc(name(row))}</b><small>${esc(row.company+' · '+row.group)}</small></span>`:c.url&&value(row,c.id)?link(value(row,c.id),'원문 ↗'):esc(format(row,c))}</span>${extra?`<a class="cpu-specs-ref" href="${esc(doc.sources[extra.source].url)}" target="_blank" rel="noopener" aria-label="${esc(name(row)+' '+c.label+' 검토 출처')}">↗</a>`:''}</div></${isName?'th':'td'}>`;}).join('')}<td><div class="cpu-specs-cell">${detailButton(row)}</div></td></tr>`).join(''):`<tr><td colspan="${visible.length+1}"><div class="cpu-specs-cell">조건에 맞는 제품이 없습니다. 검색어나 필터를 변경해 주세요.</div></td></tr>`;
    card.querySelector('[role="status"]').textContent=`${rows.length}개 ${ai?'프로파일':'GPU'} · ${group.value==='all'?'전체 단위':group.value} · ${reviewed()?'보완·검토 포함':'시트 원본'}`;
  };
  const reset=()=>{company.value='all';group.value=doc.default_group;view.value=doc.default_view;mode.value='reviewed';search.value='';sortKey=null;draw();region.scrollLeft=region.scrollTop=0;};
  card.querySelector('.cpu-specs-reset').addEventListener('click',reset);
  [company,group,view,mode].forEach(control=>control.addEventListener('change',()=>{draw();region.scrollTop=0;if(control===view||control===group)region.scrollLeft=0;}));
  search.addEventListener('input',()=>{draw();region.scrollTop=0;});
  table.addEventListener('click',event=>{
    const sort=event.target.closest('[data-sort]'),detail=event.target.closest('[data-detail]');
    if(sort){direction=sortKey===sort.dataset.sort?-direction:columns.get(sort.dataset.sort).numeric?-1:1;sortKey=sort.dataset.sort;draw();}
    if(detail){hideMemo();const row=byId.get(detail.dataset.detail);dialog.querySelector('h2').textContent=name(row);dialog.querySelector('.cpu-specs-dialog-body').innerHTML=`<p>${esc(row.company+' · '+row.group)} · ${row.sheet_row?'시트 '+row.sheet_row+'행':'공식 자료 추가 프로파일'}</p>${reviewed()&&row.review_note?`<p>${esc(row.review_note)}</p>`:''}<dl>${doc.columns.map(c=>fieldHTML(row,c.id)).join('')}</dl>${ai&&row.sheet_row?`<details><summary>시트 원본 행 · 셀 좌표</summary><dl>${row.source_values.map((v,i)=>v?`<div><dt>${String.fromCharCode(65+Math.floor(i/26)-1).replace('@','')}${String.fromCharCode(65+i%26)}${row.sheet_row}</dt><dd>${esc(v)}</dd></div>`:'').join('')}</dl></details>`:''}`;dialog.showModal();}
  });
  dialog.querySelector('button').addEventListener('click',()=>dialog.close());
  table.addEventListener('pointerover',event=>{if(event.pointerType!=='touch'){const target=event.target.closest('[data-field]');if(target)showMemo(target);}});
  table.addEventListener('pointerout',event=>{if(!memo.contains(event.relatedTarget))delayHide();});
  table.addEventListener('focusin',event=>{const target=event.target.closest('[data-field]');if(target)showMemo(target);});
  table.addEventListener('focusout',delayHide);memo.addEventListener('pointerenter',()=>clearTimeout(hideTimer));memo.addEventListener('pointerleave',delayHide);memo.addEventListener('focusin',()=>clearTimeout(hideTimer));memo.addEventListener('focusout',delayHide);
  card.addEventListener('keydown',event=>{if(event.key==='Escape')hideMemo();});region.addEventListener('scroll',hideMemo,{passive:true});
  reset();return card;
}

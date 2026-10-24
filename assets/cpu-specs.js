/* The worksheet values remain intact; reviewed additions fill blank cells only. */
"use strict";

function renderCPUSpecs(doc) {
  const card=document.createElement("div");
  card.className="card cpu-specs";
  if (!doc) return card;
  card.dataset.cpuSpecs=doc.id;
  const esc=escapeHtml;
  const companies=[...new Set(doc.rows.map(row=>row.values[0]))];
  const uses=[...new Set(doc.rows.map(row=>row.values[1]))];
  const options=values=>values.map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join("");
  const sourceLink=(url,label,title="")=>/^https:\/\//.test(url)
    ? `<a href="${esc(url)}" target="_blank" rel="noopener" title="${esc(title)}">${esc(label)}</a>` : esc(label);
  card.innerHTML=`<div class="cpu-specs-head"><div><div class="card-name">${esc(doc.name)}</div>
    <p>${doc.rows.length}개 CPU·SoC · ${companies.length}개 기업 · ${doc.columns.length}개 열</p></div>
    <div>${sourceLink(doc.source_url,"시트 원본 ↗")}<small>가져온 날 ${esc(doc.fetched)}</small></div></div>
    <p class="ir-scope-note">${esc(doc.description)}</p>
    <div class="cpu-specs-controls">
      <label>기업<select aria-label="CPU 사양 기업"><option value="all">전체 기업</option>${options(companies)}</select></label>
      <label>제품군·용도<select aria-label="CPU 사양 용도"><option value="all">전체 용도</option>${options(uses)}</select></label>
      <label class="cpu-specs-search">검색<input type="search" aria-label="CPU 사양 검색" placeholder="CPU 이름·세대·아키텍처"></label>
      <label>열 보기<select aria-label="CPU 사양 열 보기">${doc.column_views.map(view=>`<option value="${esc(view.id)}">${esc(view.label)}</option>`).join("")}</select></label>
      <label>값 표시<select aria-label="CPU 사양 값 표시"><option value="enriched">보완 포함</option><option value="original">시트 원본</option></select></label>
      <label class="cpu-specs-only"><input type="checkbox" aria-label="보완한 CPU만">보완한 CPU만</label>
      <button type="button" class="cpu-specs-reset">초기화</button>
    </div>
    <div class="cpu-specs-status"><span role="status" aria-live="polite"></span><span>표 안에서 좌우·상하 스크롤 · 열 제목으로 정렬</span></div>
    <div class="order-table-wrap cpu-specs-scroll" tabindex="0" role="region" aria-label="CPU 사양·Geekbench 표 · 가로·세로 스크롤">
      <table><caption>CPU 시트 ${esc(doc.source_range)} · 빈칸은 — · 보완 링크에서 출처·조건 확인</caption><thead></thead><tbody></tbody></table>
    </div><p class="ir-scope-note">${esc(doc.note)}</p>
    <details class="cpu-specs-evidence"><summary>보완 기준과 출처 · ${doc.supplement_count}개 값 / ${doc.supplemented_products}개 CPU</summary>
      <p>원본 셀을 덮어쓰지 않고 빈칸에만 보완했습니다. ‘시트 원본’을 선택하면 가져온 값 그대로 볼 수 있습니다. 원래 Google 시트는 수정하지 않았습니다.</p>
      ${Object.values(doc.sources).map(source=>`<p>${sourceLink(source.url,source.title+" ↗")}<small>${esc(source.note)} 확인 ${esc(source.checked)}</small></p>`).join("")}
      <p>${esc(doc.update_note)}</p>
    </details>`;
  const [company,use,columns,mode]=card.querySelectorAll("select");
  const search=card.querySelector('input[type="search"]');
  const only=card.querySelector('input[type="checkbox"]');
  const region=card.querySelector(".cpu-specs-scroll");
  const resetScroll=()=>{region.scrollLeft=innerWidth<=600?240:0;region.scrollTop=0;};
  let sortIndex=null,sortDirection=1;
  const value=(row,index)=>mode.value==="enriched" && row.supplements[index] ? row.supplements[index].value : row.values[index];
  const cell=(row,index)=>{
    const text=value(row,index),extra=mode.value==="enriched" ? row.supplements[index] : null;
    const cls=[index===2?"cpu-specs-name":"",doc.columns[index].numeric?"cpu-specs-number":"",index===22?"cpu-specs-note":"",index===35?"cpu-specs-basis":""].join(" ");
    const body=index===36 && text ? sourceLink(text,"공식 원문 ↗",text) : esc(text || "—");
    const source=extra && doc.sources[extra.source];
    const addition=extra ? ` ${sourceLink(source.url,"보완 ↗",source.title+" · "+extra.note)}` : "";
    const tag=index===2?"th":"td";
    return `<${tag} ${index===2?'scope="row"':''} data-column="${doc.columns[index].id}" class="${cls}${extra?" cpu-specs-added":""}"${doc.columns[index].numeric && text && !extra?' title="시트 기재 점수 · 실측 링크 미포함"':''}>${body}${addition}</${tag}>`;
  };
  const draw=()=>{
    const view=doc.column_views.find(view=>view.id===columns.value);
    const query=search.value.trim().toLocaleLowerCase();
    let rows=doc.rows.filter(row=>(company.value==="all" || row.values[0]===company.value)
      && (use.value==="all" || row.values[1]===use.value)
      && (!only.checked || Object.keys(row.supplements).length)
      && (!query || doc.columns.some((_,i)=>String(value(row,i)).toLocaleLowerCase().includes(query))));
    if (sortIndex!==null) rows.sort((a,b)=>{
      const av=value(a,sortIndex),bv=value(b,sortIndex);
      if (!av || !bv) return av? -1 : bv? 1 : a.sheet_row-b.sheet_row;
      const result=doc.columns[sortIndex].numeric ? Number(av)-Number(bv) : String(av).localeCompare(String(bv),"ko",{numeric:true});
      return result*sortDirection || a.sheet_row-b.sheet_row;
    });
    card.querySelector("thead").innerHTML=`<tr>${view.indices.map(index=>`<th scope="col" data-column="${doc.columns[index].id}" class="${index===2?'cpu-specs-name ':''}${doc.columns[index].numeric?'cpu-specs-number':''}" aria-sort="${sortIndex===index?(sortDirection===1?'ascending':'descending'):'none'}"><button type="button" data-sort="${index}">${esc(doc.columns[index].label)}<span aria-hidden="true">${sortIndex===index?(sortDirection===1?' ▲':' ▼'):' ↕'}</span></button></th>`).join("")}</tr>`;
    card.querySelector("tbody").innerHTML=rows.length ? rows.map(row=>`<tr data-sheet-row="${row.sheet_row}">${view.indices.map(index=>cell(row,index)).join("")}</tr>`).join("")
      : `<tr><td colspan="${view.indices.length}">조건에 맞는 CPU가 없습니다. 검색어나 필터를 변경해 주세요.</td></tr>`;
    card.querySelector('[role="status"]').textContent=`${rows.length} / ${doc.rows.length}개 CPU · ${view.indices.length}개 열 · ${mode.value==="enriched"?'보완 포함':'시트 원본'}`;
    card.querySelectorAll("[data-sort]").forEach(button=>button.addEventListener("click",()=>{
      const index=Number(button.dataset.sort);
      sortDirection=sortIndex===index?-sortDirection:doc.columns[index].numeric?-1:1;
      sortIndex=index;draw();
    }));
  };
  [company,use,columns,mode,only].forEach(control=>control.addEventListener("change",()=>{
    if (control===mode) {only.disabled=mode.value==="original";if(only.disabled)only.checked=false;}
    region.scrollTop=0;draw();
    if (control===columns) resetScroll();
  }));
  search.addEventListener("input",()=>{region.scrollTop=0;draw();});
  card.querySelector(".cpu-specs-reset").addEventListener("click",()=>{
    company.value=use.value="all";columns.value="all";mode.value="enriched";search.value="";only.checked=only.disabled=false;
    sortIndex=null;sortDirection=1;draw();resetScroll();
  });
  draw();
  resetScroll();
  return card;
}

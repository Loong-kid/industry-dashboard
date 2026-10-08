/* Source-reviewed copper mine register. Units and equity bases stay visible. */
"use strict";

const CopperMines = (() => {
  const STATUS = {operating:"가동", ramp_up:"시운전·증산", suspended:"휴광·중단", closed:"폐광", construction:"건설", development:"개발", unconfirmed:"상태 미확인"};
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const number = (n, digits=1) => n == null ? "미확인" : Number(n).toLocaleString("ko-KR", {maximumFractionDigits:digits});
  const owners = row => row.owners.map(o => `${o.name} ${o.pct == null ? "지분 미확인" : o.pct + "%"}`).join(" · ");
  const dateLabel = (row, field) => `${row[field + "_date"]} ${row[field + "_date_kind"] === "checked" ? "확인" : "공시 기준"}`;
  const annual = (row, year) => year === "latest" ? row.production.at(-1) : row.production.find(f => String(f.year) === year);
  const lifetime = row => row.cumulative || (row.period_total?.lifetime ? row.period_total : null);
  function filter(rows, f) {
    const words = (f.search || "").toLocaleLowerCase().split(/\s+/).filter(Boolean);
    return rows.filter(r => (!f.region || r.region === f.region) && (!f.country || r.country === f.country)
      && (!f.status || r.status === f.status) && (!f.owner || r.owners.some(o => o.name === f.owner))
      && (!f.coverage || (f.coverage === "production" ? !!annual(r,f.year) : f.coverage === "cumulative" ? !!lifetime(r) : !!r[f.coverage]))
      && words.every(w => `${r.name} ${r.country} ${r.region} ${r.operator} ${owners(r)} ${r.note} ${r.id}`.toLocaleLowerCase().includes(w)));
  }
  function sort(rows, f) {
    const value = r => f.sort === "production" ? annual(r,f.year)?.cu_tonnes
      : f.sort === "reserves" || f.sort === "resources" ? r[f.sort]?.cu_tonnes
      : f.sort === "start_year" ? r.start_year : r[f.sort];
    return [...rows].sort((a,b) => {
      const av=value(a), bv=value(b);
      if (av == null) return bv == null ? a.name.localeCompare(b.name) : 1;
      if (bv == null) return -1;
      return (typeof av === "number" ? av-bv : String(av).localeCompare(String(bv),"ko")) * f.dir || a.name.localeCompare(b.name);
    });
  }
  const url = raw => { try { const u = new URL(raw); return u.protocol === "https:" ? u.href : ""; } catch { return ""; } };
  function refs(doc, ids) {
    return [...new Set(ids || [])].map(id => {
      const s=doc.sources[id], href=url(s?.url);
      return href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer" title="${esc(s.title)}">${esc(s.title)}</a>` : "";
    }).filter(Boolean).join(" · ");
  }
  function factHtml(doc, f, unit="kt") {
    if (!f) return '<span class="mine-missing">미확인</span>';
    const value = f.cu_tonnes != null ? `${number(f.cu_tonnes / (unit === "Mt" ? 1e6 : 1e3), unit === "Mt" ? 3 : 1)} ${unit} Cu`
      : `${number(f.value,2)} ${esc(f.unit)}`;
    const period = f.from_year ? `${f.from_year}–${f.to_year} · 연속 연간 이력 합계` : `${f.date}${f.period ? ` · ${f.period === "fiscal" ? "FY" : "CY"}${f.year}` : ""}`;
    return `<strong>${value}</strong><small>${esc(period)}</small>
      <small>${esc(f.classification || "")}${f.classification ? " · " : ""}${esc(f.basis)}</small>`;
  }
  function csv(doc, rows, year) {
    const cols=["id","광산","국가","대륙","상태","상태기준일","운영사","소유·지분","소유기준","소유기준일","최초생산연도","종료·중단연도","채굴방식","생산연도","CY/FY","생산_t_Cu","생산원문값","생산원문단위","생산기준","매장량_t_Cu","매장량원문값","매장량원문단위","매장량기준일","매장량기준","자원량_t_Cu","자원량원문값","자원량원문단위","자원량기준일","자원량기준","전생애누적_t_Cu","확보기간합계_t_Cu","확보기간시작","확보기간끝","비고","출처","상태일자종류","소유일자종류","매장량분류","자원량분류","누적기준","누적시점","원광채굴량","원광단위","원광기준","채굴이력","연간생산이력_JSON"];
    const clean = v => { const s=String(v??""); return '"'+(/^[=+@\-\t\r]/.test(s) ? "'"+s : s).replace(/"/g,'""')+'"'; };
    const lines=rows.map(r => {
      const p=annual(r,year), reserve=r.reserves, resource=r.resources, cum=lifetime(r);
      const ids=[...r.sources,...r.ownership_sources,...r.status_sources,...r.history_sources,...r.production.flatMap(f=>f.sources),...(reserve?.sources||[]),...(resource?.sources||[]),...(cum?.sources||[]),...(r.ore_mined?.sources||[])];
      return [r.id,r.name,r.country,r.region,STATUS[r.status],r.status_date,r.operator,owners(r),r.ownership_basis,r.ownership_date,r.start_year,r.end_year,r.method,
        p?.year,p?.period,p?.cu_tonnes,p?.value,p?.unit,p?.basis,reserve?.cu_tonnes,reserve?.value,reserve?.unit,reserve?.date,reserve?.basis,
        resource?.cu_tonnes,resource?.value,resource?.unit,resource?.date,resource?.basis,cum?.cu_tonnes,
        r.period_total?.cu_tonnes,r.period_total?.from_year,r.period_total?.to_year,r.note,
        [...new Set(ids)].map(id=>doc.sources[id]?.url).filter(Boolean).join(" | "),
        r.status_date_kind,r.ownership_date_kind,reserve?.classification,resource?.classification,cum?.basis,
        cum?.date || (cum ? `${cum.from_year}–${cum.to_year}` : ""),r.ore_mined?.value,r.ore_mined?.unit,r.ore_mined?.basis,r.history_note,JSON.stringify(r.production)].map(clean).join(",");
    });
    return "\uFEFF"+[cols.map(clean).join(","),...lines].join("\r\n");
  }
  function render(doc) {
    const card=document.createElement("section"); card.className="card order-table-card copper-mines";
    if (!doc?.rows?.length) {card.innerHTML='<div class="card-name">세계 구리 광산 명부</div><div class="card-empty">아직 데이터가 없습니다.</div>';return card;}
    const f={search:"", region:"", country:"", owner:"", status:"", coverage:"", year:"latest", sort:"production", dir:-1};
    const openIds=new Set();
    card.innerHTML=`<div class="card-head"><div><h2 class="card-name">${esc(doc.name)}</h2><p class="card-freq">자료 검토 ${esc(doc.reviewed)} · 각 항목의 공시 기준일 별도</p></div><button type="button" class="mine-download">현재 표 CSV ↓</button></div>
      <p class="mine-scope">${esc(doc.scope_note)}</p><div class="mine-summary"></div>
      <details class="mine-method"><summary>단위·지분·매장량·누적 계산 기준</summary><ul>${doc.methodology.map(t=>`<li>${esc(t)}</li>`).join("")}</ul><p>CY = 1–12월, FY = 회사 회계연도. 1 kt Cu = 구리 1,000톤, 1 Mt Cu = 구리 100만톤, Mt ore = 원광 100만톤.</p><p>전체 지분 구성 확보 ${doc.coverage.with_complete_ownership}개 · 최초 생산연도 확보 ${doc.coverage.with_start_year}개 · 원광 채굴량 확보 ${doc.coverage.with_ore_mined}개. ‘확인’ 날짜는 공시일이 없는 운영사 페이지를 검토한 날이며, 공시 기준일과 구분합니다. 생산·매장량·자원량은 지분과 분류가 달라 전체 합산하지 않습니다.</p></details>
      <div class="mine-filters"><label class="mine-search">광산·기업 검색<input type="search" placeholder="예: Escondida, BHP, 칠레" aria-label="광산·기업 검색"></label></div>
      <div class="order-count" aria-live="polite"></div><div class="order-table-wrap" tabindex="0" role="region" aria-label="세계 구리 광산 비교표 · 가로 스크롤"></div>`;
    const filters=card.querySelector(".mine-filters");
    function select(key,label,options) {
      const wrap=document.createElement("label");wrap.textContent=label;
      const sel=document.createElement("select");sel.dataset.filter=key;sel.setAttribute("aria-label",label);
      for (const [value,text] of options) {const opt=document.createElement("option");opt.value=value;opt.textContent=text;sel.appendChild(opt);}
      sel.value=f[key];sel.addEventListener("change",()=>{f[key]=sel.value;draw();});wrap.appendChild(sel);filters.appendChild(wrap);
    }
    const values=key=>[...new Set(doc.rows.map(r=>r[key]))].sort((a,b)=>a.localeCompare(b,"ko")).map(v=>[v,v]);
    select("region","대륙",[["","전체 대륙"],...values("region")]);
    select("country","국가",[["","전체 국가"],...values("country")]);
    select("status","운영 상태",[["","전체 상태"],...Object.entries(STATUS)]);
    select("owner","소유주",[["","전체 소유주"],...[...new Set(doc.rows.flatMap(r=>r.owners.map(o=>o.name)))].filter(n=>!n.startsWith("기타")).sort().map(n=>[n,n])]);
    const years=[...new Set(doc.rows.flatMap(r=>r.production.map(p=>p.year)))].sort((a,b)=>b-a);
    select("year","생산 기준연도",[["latest","광산별 최신 연간"],...years.map(y=>[String(y),String(y)])]);
    select("coverage","확보 자료",[["","전체 항목"],["production","생산량 확보"],["reserves","매장량 확보"],["resources","자원량 확보"],["cumulative","전 생애 누적 확보"]]);
    const reset=document.createElement("button");reset.type="button";reset.className="mine-reset";reset.textContent="필터 초기화";reset.addEventListener("click",()=>{
      Object.assign(f,{search:"",region:"",country:"",owner:"",status:"",coverage:"",year:"latest",sort:"production",dir:-1});
      card.querySelector("input").value="";filters.querySelectorAll("select").forEach(s=>{s.value=f[s.dataset.filter];});draw();
    });filters.appendChild(reset);
    card.querySelector("input").addEventListener("input",e=>{f.search=e.target.value;draw();});
    card.querySelector(".mine-download").addEventListener("click",()=>{
      const rows=sort(filter(doc.rows,f),f), blob=new Blob([csv(doc,rows,f.year)],{type:"text/csv;charset=utf-8"});
      const href=URL.createObjectURL(blob), a=document.createElement("a");a.href=href;a.download=`copper-mines-${doc.reviewed}-${f.year}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
    });
    function detail(r) {
      return `<td colspan="12"><div class="mine-detail"><div><h3>소유·운영 이력</h3><p>${esc(owners(r))}</p><p>${esc(r.ownership_basis)} · ${esc(dateLabel(r,"ownership"))}</p><p>${esc(r.history_note)}</p><p>${esc(r.note)}</p><p>${refs(doc,[...r.ownership_sources,...r.status_sources,...r.history_sources,...r.sources])}</p></div>
        <div><h3>연도별 구리 생산</h3>${r.production.length ? `<table class="mine-history"><thead><tr><th>기간</th><th>kt Cu</th><th>원문·산정 기준</th></tr></thead><tbody>${r.production.map(p=>`<tr><td>${p.period==="fiscal"?"FY":"CY"}${p.year}</td><td>${number(p.cu_tonnes/1000)}</td><td>${number(p.value,3)} ${esc(p.unit)} · ${esc(p.basis)}<small>${esc(p.locator)} · ${refs(doc,p.sources)}</small></td></tr>`).join("")}</tbody></table>`:'<p>연간 구리 생산량 미확인</p>'}
        <p>${r.period_total ? `${r.period_total.lifetime?"최초 생산부터 누적":"확보 기간 생산 합계"}: ${r.period_total.from_year}–${r.period_total.to_year} · ${number(r.period_total.cu_tonnes/1000)} kt Cu` : "연속된 동일 기준 생산 이력 부족으로 기간 합계 미산출"}</p>
        ${r.ore_mined?`<h3>원광 채굴량</h3><p>${factHtml(doc,r.ore_mined)} · ${refs(doc,r.ore_mined.sources)}</p>`:""}</div>
        <div><h3>매장량</h3><p>${factHtml(doc,r.reserves,"Mt")}</p><p>${r.reserves?esc(r.reserves.locator)+" · "+refs(doc,r.reserves.sources):""}</p><h3>자원량</h3><p>${factHtml(doc,r.resources,"Mt")}</p><p>${r.resources?esc(r.resources.locator)+" · "+refs(doc,r.resources.sources):""}</p><h3>전 생애 누적 생산</h3><p>${lifetime(r)?factHtml(doc,lifetime(r)):"미확인 · 연간 생산량 × 가동연수로 추정하지 않음"}</p></div></div></td>`;
    }
    function draw() {
      const rows=sort(filter(doc.rows,f),f), c=doc.coverage;
      card.querySelector(".mine-summary").innerHTML=[
        ["등록 광산·자산",`${c.mines}개 / ${c.countries}개국`], ["연간 생산 확보",`${c.with_production}개`],
        ["매장량 / 자원량 확보",`${c.with_reserves} / ${c.with_resources}개`], ["전 생애 누적 확보",`${c.with_lifetime}개`],
      ].map(([label,v])=>`<div><span>${label}</span><strong>${v}</strong></div>`).join("");
      card.querySelector(".order-count").textContent=`${rows.length} / ${doc.rows.length}개 표시 · ↔ 좌우로 스크롤하여 매장량·누적·출처 확인 · 생산 ${f.year==="latest"?"광산별 최신 연간 (연도 혼합)":f.year+"년"} · 매장량·자원량 정렬은 Cu 금속량 기준 (ore·미확인은 뒤에 표시)`;
      const cols=[["name","광산 / 상세"],["country","국가"],["status","상태 / 기준일"],["operator","운영사"],[null,"소유·지분"],["production","연간 생산 (kt Cu)"],["reserves","매장량 (Mt Cu / ore)"],["resources","자원량 (Mt Cu / ore)"],[null,"전 생애 누적 / 확보 기간"],["start_year","최초 생산 / 중단"],[null,"채굴 방식"],[null,"출처"]];
      const table=document.createElement("table");
      table.innerHTML=`<caption class="mine-sr-only">세계 구리 광산 · 소유·생산·매장량 비교</caption><thead><tr>${cols.map(([key,label])=>`<th scope="col" ${key?`data-sort="${key}" aria-sort="${f.sort===key?(f.dir===1?"ascending":"descending"):"none"}"`:""}>${key?`<button type="button">${esc(label)}${f.sort===key?(f.dir===1?" ↑":" ↓"):" ↕"}</button>`:esc(label)}</th>`).join("")}</tr></thead>`;
      const tbody=document.createElement("tbody");
      for (const r of rows) {
        const tr=document.createElement("tr");tr.dataset.mineId=r.id;
        const cum=lifetime(r), partial=r.period_total;
        tr.innerHTML=`<th scope="row"><strong>${esc(r.name)}</strong><button type="button" class="mine-detail-toggle" aria-expanded="${openIds.has(r.id)}" aria-controls="mine-detail-${esc(r.id)}">${openIds.has(r.id)?"상세 닫기 −":"상세 보기 +"}</button></th>
          <td>${esc(r.country)}<small>${esc(r.region)}</small></td><td><span class="mine-status status-${r.status}">${STATUS[r.status]}</span><small>${esc(dateLabel(r,"status"))}</small></td><td>${esc(r.operator)}</td>
          <td class="mine-owners">${r.owners.map(o=>`<span>${esc(o.name)} <b>${o.pct==null?"미확인":o.pct+"%"}</b></span>`).join("")}<small>${esc(dateLabel(r,"ownership"))}</small></td>
          <td>${factHtml(doc,annual(r,f.year))}</td><td>${factHtml(doc,r.reserves,"Mt")}</td><td>${factHtml(doc,r.resources,"Mt")}</td>
          <td>${cum?`<strong>${number(cum.cu_tonnes/1000)} kt Cu</strong><small>전 생애 누적 · ${esc(cum.date || `${cum.from_year}–${cum.to_year}`)}</small>`:'<span class="mine-missing">전 생애 미확인</span>'}${partial&&!partial.lifetime?`<small>${partial.from_year}–${partial.to_year} 합계<br>${number(partial.cu_tonnes/1000)} kt Cu · 부분 기간</small>`:""}</td>
          <td>${r.start_year??"미확인"}${r.end_year?`<small>${r.end_year} 중단/종료</small>`:""}</td><td>${esc(r.method)}</td><td>${refs(doc,r.sources)}</td>`;
        const dtr=document.createElement("tr");dtr.id=`mine-detail-${r.id}`;dtr.className="mine-detail-row";dtr.hidden=!openIds.has(r.id);
        const toggle=tr.querySelector("button");
        function expand() {dtr.hidden=!openIds.has(r.id);toggle.setAttribute("aria-expanded",String(!dtr.hidden));toggle.textContent=dtr.hidden?"상세 보기 +":"상세 닫기 −";if(!dtr.hidden&&!dtr.children.length)dtr.innerHTML=detail(r);}
        toggle.addEventListener("click",()=>{if(openIds.has(r.id))openIds.delete(r.id);else openIds.add(r.id);expand();});
        expand();tbody.append(tr,dtr);
      }
      if (!rows.length) tbody.innerHTML='<tr><td colspan="12" class="mine-empty">조건에 맞는 광산이 없습니다. 검색어 또는 필터를 변경하세요.</td></tr>';
      table.appendChild(tbody);
      table.querySelectorAll("th[data-sort] button").forEach(btn=>btn.addEventListener("click",()=>{const key=btn.parentElement.dataset.sort;f.dir=f.sort===key?-f.dir:(key==="production"||key==="reserves"||key==="resources"?-1:1);f.sort=key;draw();}));
      card.querySelector(".order-table-wrap").replaceChildren(table);
    }
    draw();return card;
  }
  return {render, filter, sort, annual, csv};
})();

function renderCopperMines(doc) { return CopperMines.render(doc); }
if (typeof module !== "undefined") module.exports = CopperMines;

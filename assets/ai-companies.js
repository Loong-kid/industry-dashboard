import {escapeHTML as esc, safeURL} from './ai-overview.js';

export const BASIS_LABELS = {
  available_compute:'사용 가능 컴퓨팅', campus_planned:'센터 전체 계획', cluster_planned:'클러스터 계획',
  energized_buildings:'가동 건물 용량', power_available:'가용 전력', contracted_compute:'컴퓨팅 이용 계약',
  additional_contract:'추가 용량 계약', hardware_deployment:'하드웨어 구축', program_planned:'프로그램 계획',
  program_secured:'프로그램 확보', shared_sites_planned:'복수 사이트 합계 계획', delivery_progress:'인도 진행률',
  investment_program:'투자 프로그램', delivery_schedule:'고객 공급 일정', chip_count:'칩 개수 발표'
};
export const KIND_LABELS = {site:'센터 계획', supply:'공급 계약', program:'전체 프로그램', operations:'가동·진행 현황'};
export function quantity(value, qualifier='eq', unit='') {
  if (value == null) return '미공개';
  const prefix = {gt:'>',ge:'≥',le:'≤',approx:'약 ',eq:''}[qualifier] || '';
  return `${prefix}${Number(value).toLocaleString('ko-KR',{maximumFractionDigits:3})}${unit ? ' '+unit : ''}`;
}
export function arrRows(doc, company='', calculated=false) {
  return doc.arr.filter(row => (!company || row.company===company) && (calculated || row.basis==='reported'))
    .sort((a,b) => a.plot_date.localeCompare(b.plot_date) || a.id.localeCompare(b.id));
}
export function periodBounds(period) {
  if (/^\d{4}$/.test(period)) return [period+'-01-01',period+'-12-31'];
  if (/^\d{4}-\d{2}$/.test(period)) {
    const [year,month]=period.split('-').map(Number);
    return [period+'-01',new Date(Date.UTC(year,month,0)).toISOString().slice(0,10)];
  }
  return [period,period];
}
export function filterEvents(doc, {company='',kind='',query='',from='',to=''}={}) {
  const q=query.trim().toLocaleLowerCase();
  return doc.events.filter(row => {
    const [first,last]=periodBounds(row.date);
    return (!company || row.company===company) && (!kind || row.kind===kind) && (!from || last>=from) && (!to || first<=to) &&
      (!q || [row.title,row.note,row.target,...row.source_ids.map(id=>doc.sources.find(s=>s.id===id)?.publisher || '')].join(' ').toLocaleLowerCase().includes(q));
  }).sort((a,b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
}
const link=(url,label) => safeURL(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : esc(label);

export function renderAICompanies(doc, {registerChart=()=>{}}={}) {
  if (!document.querySelector('link[data-ai-companies]')) {
    const css=document.createElement('link');css.rel='stylesheet';css.href=new URL('./ai-companies.css',import.meta.url).href;css.dataset.aiCompanies='';document.head.append(css);
  }
  const root=document.createElement('div');root.className='ai-companies';
  if (!doc) {root.textContent='AI 기업 자료를 불러오지 못했습니다.';return root;}
  const companies=new Map(doc.companies.map(c=>[c.id,c])),sources=new Map(doc.sources.map(s=>[s.id,s]));
  const sourceHTML=ids=>ids.map(id=>{const s=sources.get(id);return `<p>${link(s.url,s.publisher+' · '+s.title)}<small>발표 ${esc(s.published || '게시일 미공개')} · 확인 ${esc(s.checked)}</small></p>`;}).join('');
  root.innerHTML=`<div class="aic-heading"><div><h2>AI 기업 · ARR와 인프라</h2><p>Anthropic · OpenAI</p></div><span>공식 자료 검토 ${esc(doc.reviewed)}</span></div>
    <p class="aic-note">${esc(doc.scope_note)}</p>
    <div class="aic-controls"><label>기업<select data-company aria-label="AI 기업 선택"><option value="">전체 기업</option>${doc.companies.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select></label><label class="aic-check"><input type="checkbox" data-calculated>월 매출 × 12 계산값 포함</label><button type="button" data-method>집계 기준·출처</button></div>
    <div class="aic-snapshot" aria-label="회사별 최근 공식 발표"></div>
    <div class="aic-charts"><section class="aic-chart"><h3>회사 발표 ARR 비교</h3><p>USD 십억 · 기준 시점 · 기업 이름을 눌러 선을 선택</p><div class="aic-canvas"><canvas data-arr aria-label="Anthropic과 OpenAI의 발표 ARR 이력" role="img"></canvas></div><small>점 사이의 선은 비교용 연결선입니다. ≥·&gt;·약 표기는 상세와 표에서 유지합니다.</small></section>
      <section class="aic-chart"><h3>사용 가능 컴퓨팅 이력</h3><p>MW · 회사 전체 공개값 · 실측 수전과 구분</p><div class="aic-canvas"><canvas data-compute aria-label="회사에서 공개한 사용 가능 컴퓨팅 이력" role="img"></canvas><p class="aic-chart-empty" hidden>회사 전체 컴퓨팅 공개값이 없습니다.</p></div><small>OpenAI CFO의 2023~2025년 회고 자료입니다. Anthropic 전체 총계는 미확인입니다.</small></section></div>
    <section class="aic-panel"><h3>센터·클러스터별 현황</h3><p class="aic-note">가동·가용 전력·계획의 기준일을 확인하세요. 실제 회사 전체 수전은 미공개이며, 아래 항목을 합산하지 않습니다.</p><div class="aic-project-controls"><label>프로젝트·지역·파트너 검색<input type="search" data-project-search placeholder="Abilene, Fluidstack, Texas…"></label><span data-project-count role="status"></span></div><div class="aic-scroll aic-projects" tabindex="0" role="region" aria-label="센터별 공개 용량과 계획"><table></table></div></section>
    <section class="aic-panel"><h3>발표일별 계획·변경 이력</h3><div class="aic-event-controls"><label>유형<select data-kind><option value="">전체 유형</option>${Object.entries(KIND_LABELS).map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</select></label><label>발표 시작<input type="date" data-from aria-label="계획 발표 시작일"></label><label>발표 종료<input type="date" data-to aria-label="계획 발표 종료일"></label><label class="aic-search">발표 검색<input type="search" data-event-search placeholder="계약·프로젝트·공급사"></label><button type="button" data-reset-events>초기화</button></div><p class="aic-status" data-event-count role="status"></p><div class="aic-scroll" tabindex="0" role="region" aria-label="발표일별 인프라 변경 이력"><table data-events></table></div></section>
    <section class="aic-panel"><h3>ARR 발표 원장</h3><p class="aic-note">기준 시점과 발표일이 다릅니다. 월·연 단위 자료는 정확한 일자를 임의로 채우지 않았습니다.</p><div class="aic-scroll" tabindex="0" role="region" aria-label="회사별 ARR 발표와 출처"><table data-arr-table></table></div></section>
    <dialog class="aic-dialog" aria-label="AI 기업 자료 상세"><div class="aic-dialog-head"><h2></h2><button type="button" data-close>닫기</button></div><div class="aic-dialog-body"></div></dialog>`;
  const company=root.querySelector('[data-company]'),calc=root.querySelector('[data-calculated]'),projectSearch=root.querySelector('[data-project-search]');
  const kind=root.querySelector('[data-kind]'),from=root.querySelector('[data-from]'),to=root.querySelector('[data-to]'),eventSearch=root.querySelector('[data-event-search]'),dialog=root.querySelector('dialog');
  let charts=[],arrVisible=[];
  const fieldsHTML=fields=>`<dl>${fields.map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value ?? '미공개')}</dd></div>`).join('')}</dl>`;
  function show(title,fields,ids=[],extra='') {
    dialog.querySelector('h2').textContent=title;
    dialog.querySelector('.aic-dialog-body').innerHTML=fieldsHTML(fields)+extra+`<div class="aic-sources">${sourceHTML(ids)}</div>`;
    dialog.showModal();
  }
  function detail(type,id) {
    if(type==='arr') {
      const r=doc.arr.find(r=>r.id===id);
      show(companies.get(r.company).name+' · ARR',[
        ['기준 시점',r.period_label],['발표일',r.announced_on],['연환산 매출',quantity(r.usd_bn,r.qualifier,'USD 십억')],
        ['구분',r.basis==='reported'?'회사 직접 발표':'계산값 · 월 매출 × 12'],['범위','회사 전체'],['설명',r.note || doc.definitions.reported]
      ],r.source_ids);return;
    }
    if(type==='compute') {
      const r=doc.compute_history.find(r=>r.id===id);
      show(companies.get(r.company).name+' · 컴퓨팅',[['기준 시점',r.period_label],['발표일',r.announced_on],['공개값',quantity(r.mw,r.qualifier,'MW')],['기준',BASIS_LABELS[r.basis]],['설명',r.note]],r.source_ids);return;
    }
    if(type==='project') {
      const r=doc.projects.find(r=>r.id===id);
      show(r.name,[['기업',companies.get(r.company).name],['위치',r.location],['개발·운영 역할',r.partners],['기록된 발표일',r.announced_on],['진행 상태',r.status+' · '+r.status_as_of],
        ['확인된 공개 용량',quantity(r.known_mw,'eq','MW')],['공개 용량 기준',r.known_basis?BASIS_LABELS[r.known_basis]+' · '+r.known_as_of:'미공개'],['센터 실제 수전 MW',r.grid_mw],
        ['계획·계약 용량',quantity(r.planned_mw,r.plan_qualifier,'MW')],['계획 기준',BASIS_LABELS[r.plan_basis]],['인도 진행률',r.delivery_pct==null?'미공개':r.delivery_pct+'% · '+r.delivery_as_of],['가동·공급 목표',r.target],['설명',r.note]],r.source_ids);return;
    }
    const r=doc.events.find(r=>r.id===id);
    show(r.title,[['기업',companies.get(r.company).name],['발표·공개 기준',r.date+(r.date.length===7?' · 정확한 게시일 미공개':'')],['유형',KIND_LABELS[r.kind]],
      ['공개 규모',quantity(r.capacity_mw,r.qualifier,'MW')],['용량 기준',BASIS_LABELS[r.capacity_basis]],['목표 시점',r.target],['설명',r.note],['합산',doc.definitions.overlap]],r.source_ids);
  }
  root.querySelector('[data-close]').onclick=()=>dialog.close();
  dialog.onclick=event=>{if(event.target===dialog){const b=dialog.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)dialog.close();}};
  root.querySelector('[data-method]').onclick=()=>show('집계 기준과 출처',Object.entries(doc.definitions).map(([key,value])=>[{reported:'ARR',monthly_annualized:'계산값',capacity:'용량 기준',overlap:'중복',dates:'날짜',update:'갱신 방식'}[key],value]),[],doc.companies.map(c=>`<p>${esc(c.name+': '+c.arr_note)}</p>`).join('')+sourceHTML(doc.sources.map(s=>s.id)));
  const dual=(value,sub)=>`<span class="aic-dual"><strong>${esc(value)}</strong><small>${esc(sub)}</small></span>`;
  const button=(type,id,text)=>`<button type="button" class="aic-row" data-type="${type}" data-id="${esc(id)}">${esc(text)}</button>`;
  function tableHTML(columns,rows,caption) {
    return `<caption class="aic-sr">${esc(caption)}</caption><colgroup>${columns.map(c=>`<col style="width:${c[1]}px">`).join('')}</colgroup><thead><tr>${columns.map(c=>`<th scope="col">${esc(c[0])}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${columns.length}" class="aic-empty">조건에 맞는 자료가 없습니다. 필터를 바꿔 주세요.</td></tr>`}</tbody>`;
  }
  const sourceCell=ids=>link(sources.get(ids[0]).url,'원문 ↗');
  function drawProjects() {
    const q=projectSearch.value.trim().toLocaleLowerCase();
    const rows=doc.projects.filter(r=>(!company.value||r.company===company.value)&&(!q||[r.name,r.location,r.partners,r.note].join(' ').toLocaleLowerCase().includes(q)));
    root.querySelector('[data-project-count]').textContent=rows.length+'개 프로젝트';
    root.querySelector('.aic-projects table').innerHTML=tableHTML([
      ['기업 · 프로젝트',240],['위치',200],['개발·운영 파트너',230],['상태 · 기준',160],['확인된 공개 용량',190],['계획·계약 MW',150],['가동·공급 목표',250],['출처',65],['상세',60]
    ],rows.map(r=>[
      button('project',r.id,companies.get(r.company).name+' · '+r.name),esc(r.location),esc(r.partners),dual(r.status,(r.delivery_pct!=null?'인도 '+r.delivery_pct+'% · ':'')+r.status_as_of),
      dual(quantity(r.known_mw,'eq','MW'),r.known_basis?BASIS_LABELS[r.known_basis]+' · '+r.known_as_of:'실측 수전으로 추정하지 않음'),dual(quantity(r.planned_mw,r.plan_qualifier,'MW'),BASIS_LABELS[r.plan_basis]),esc(r.target),sourceCell(r.source_ids),button('project',r.id,'상세')
    ]),'공식 자료에서 확인한 대표 센터. 용량 기준과 날짜를 구분하며 합산하지 않습니다.');
  }
  function drawEvents() {
    const invalid=from.value&&to.value&&from.value>to.value;
    to.setCustomValidity(invalid?'종료일은 시작일 이후로 선택해 주세요.':'');
    const rows=invalid?[]:filterEvents(doc,{company:company.value,kind:kind.value,query:eventSearch.value,from:from.value,to:to.value});
    root.querySelector('[data-event-count]').textContent=invalid?'종료일은 시작일 이후로 선택해 주세요.':rows.length+'개 발표 · 최신순 · 계약·프로그램 간 중복 합산 없음';
    root.querySelector('[data-events]').innerHTML=tableHTML([
      ['발표·기준 시점',115],['기업',105],['유형',120],['발표·변경 내용',350],['공개 규모',170],['목표 시점',230],['출처',65],['상세',60]
    ],rows.map(r=>[esc(r.date),esc(companies.get(r.company).name),esc(KIND_LABELS[r.kind]),button('event',r.id,r.title),dual(quantity(r.capacity_mw,r.qualifier,'MW'),BASIS_LABELS[r.capacity_basis]),esc(r.target),sourceCell(r.source_ids),button('event',r.id,'상세')]),'발표일별 센터 계획·계약·가동 현황. 월 단위는 정확한 게시일이 공개되지 않았습니다.');
  }
  function draw() {
    arrVisible=arrRows(doc,company.value,calc.checked);
    const computeVisible=doc.compute_history.filter(r=>!company.value||r.company===company.value);
    root.querySelector('.aic-chart-empty').hidden=computeVisible.length>0;
    root.querySelector('[data-compute]').style.visibility=computeVisible.length?'visible':'hidden';
    const selected=doc.companies.filter(c=>!company.value||c.id===company.value);
    root.querySelector('.aic-snapshot').innerHTML='<table>'+tableHTML([['기업',120],['마지막 공식 ARR',220],['사용 가능 컴퓨팅',250],['회사 전체 실제 수전',250]],selected.map(c=>{
      const last=arrRows(doc,c.id).at(-1),compute=doc.compute_history.filter(r=>r.company===c.id).at(-1);
      return [esc(c.name),last?dual(quantity(last.usd_bn,last.qualifier,'USD 십억'),last.period_label):'미공개',compute?dual(quantity(compute.mw,compute.qualifier,'MW'),compute.period_label+' · 수전 총량 아님'):'회사 전체 총계 미확인',esc(c.grid_total_mw==null?'미공개':quantity(c.grid_total_mw,'eq','MW'))];
    }),'회사별 마지막 공식 발표와 전체 실제 수전 공개 여부')+'</table>';
    root.querySelector('[data-arr-table]').innerHTML=tableHTML([['기업',110],['기준 시점',190],['발표일',110],['연환산 매출',170],['구분',190],['출처',65],['상세',60]],arrVisible.slice().reverse().map(r=>[
      esc(companies.get(r.company).name),esc(r.period_label),esc(r.announced_on),quantity(r.usd_bn,r.qualifier,'USD 십억'),esc(r.basis==='reported'?'회사 직접 발표':'계산값 · 월 매출 × 12'),sourceCell(r.source_ids),button('arr',r.id,'상세')
    ]),'회사 전체 ARR 발표 원장. 계산값은 선택할 때만 포함됩니다.');
    if(charts.length) {
      const all=[arrVisible,computeVisible];
      charts.forEach((chart,index)=>{
        chart.data.datasets=selected.map(c=>({label:c.name,borderColor:c.color,backgroundColor:c.color,borderWidth:2,pointRadius:4,pointHoverRadius:6,borderDash:index===0?[4,3]:[],
          pointStyle:context=>context.raw?.row?.basis==='monthly_annualized'?'rectRot':context.raw?.row?.qualifier==='gt'?'triangle':'circle',
          data:all[index].filter(r=>r.company===c.id).map(r=>({x:Date.parse(r.plot_date+'T00:00:00Z'),y:index===0?r.usd_bn:r.mw,row:r})),fill:false,tension:0}));
        chart.update('none');
      });
    }
    drawProjects();drawEvents();
  }
  root.addEventListener('click',event=>{const b=event.target.closest('[data-type][data-id]');if(b)detail(b.dataset.type,b.dataset.id);});
  company.onchange=draw;calc.onchange=draw;projectSearch.oninput=drawProjects;
  [kind,from,to].forEach(input=>input.onchange=drawEvents);eventSearch.oninput=drawEvents;
  root.querySelector('[data-reset-events]').onclick=()=>{kind.value='';from.value='';to.value='';eventSearch.value='';drawEvents();};
  draw();
  queueMicrotask(()=>{
    if(!root.isConnected)return;
    if(!globalThis.Chart){root.querySelectorAll('.aic-canvas').forEach(el=>el.textContent='차트를 불러오지 못했습니다. 아래 표에서 수치를 확인하세요.');return;}
    const dark=matchMedia('(prefers-color-scheme: dark)').matches,ink=dark?'#c3c2b7':'#52514e',grid=dark?'#2c2c2a':'#e1e0d9';
    charts=[root.querySelector('[data-arr]'),root.querySelector('[data-compute]')].map((canvas,index)=>{
      const chart=new globalThis.Chart(canvas,{type:'line',data:{datasets:[]},options:{responsive:true,maintainAspectRatio:false,animation:false,normalized:true,
        interaction:{mode:'nearest',intersect:true},scales:{x:{type:'linear',grid:{display:false},ticks:{color:ink,maxTicksLimit:5,callback:v=>new Date(v).toISOString().slice(0,7)}},y:{beginAtZero:true,grid:{color:grid},ticks:{color:ink,maxTicksLimit:5}}},
        plugins:{legend:{position:'bottom',labels:{color:ink,usePointStyle:true,boxWidth:8,font:{size:11}}},tooltip:{callbacks:{title:items=>items[0]?.raw?.row?.period_label||'',label:item=>item.dataset.label+': '+quantity(item.raw.y,item.raw.row.qualifier,index===0?'USD 십억':'MW'),afterLabel:item=>'발표 '+item.raw.row.announced_on+(item.raw.row.basis==='monthly_annualized'?' · 계산값':'')}}},
        onClick:(_event,points)=>{if(points.length){const point=points[0],row=chart.data.datasets[point.datasetIndex].data[point.index].row;detail(index===0?'arr':'compute',row.id);}}
      }});registerChart(chart);return chart;
    });draw();
  });
  return root;
}

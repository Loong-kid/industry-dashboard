/* Movie identities preserve release events, territories and lifetime gross scope. */
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
export const usd=value=>value==null?'—':(value/1e6).toLocaleString('ko-KR',{minimumFractionDigits:1,maximumFractionDigits:2});
const link=(url,label)=>{const a=node('a',label);if(/^https:\/\/(?:www\.the-numbers\.com|investors\.imax\.com|www\.sec\.gov)\//.test(url||'')){a.href=url;a.target='_blank';a.rel='noopener';}return a;};
export function filmState(film,today,year){
  const known=film.events.filter(e=>e.date),past=known.filter(e=>e.date<=today),future=known.filter(e=>e.date>today);
  const performance=film.domestic_usd!=null||film.worldwide_usd!=null;
  const upcoming=future.length>0||(!known.length&&year>=Number(today.slice(0,4)));
  return {released:past.length>0||(!known.length&&performance&&year<=Number(today.slice(0,4))),upcoming,
    date:known[0]?.date||null,next_date:future[0]?.date||null,
    label:future.length?(past.length?'추가 개봉 예정':'개봉 예정'):past.length?'개봉':year>Number(today.slice(0,4))?'일자 미정':performance?'흥행 확인 · 일자 미확인':'일정 확인 필요'};
}
export function selectFilms(doc,{view='all',major=true,imax=false,distributor='',query='',sort='date',today}={}){
  const q=query.trim().toLocaleLowerCase();
  return doc.films.filter(f=>{
    const s=filmState(f,today,doc.year);
    return (!major||f.major_release)&&(!imax||f.imax_confirmed)&&(!distributor||f.distributors.includes(distributor))&&
      (view==='all'||view==='upcoming'&&s.upcoming||view==='released'&&s.released)&&
      (!q||[f.title,...f.distributors,...f.events.map(e=>e.release_type)].join(' ').toLocaleLowerCase().includes(q));
  }).sort((a,b)=>sort==='gross'?(a.worldwide_usd==null)!==(b.worldwide_usd==null)?(a.worldwide_usd==null?1:-1):(b.worldwide_usd??b.domestic_usd??-1)-(a.worldwide_usd??a.domestic_usd??-1)||a.title.localeCompare(b.title):
    ((view==='upcoming'?filmState(a,today,doc.year).next_date:filmState(a,today,doc.year).date)||'9999').localeCompare((view==='upcoming'?filmState(b,today,doc.year).next_date:filmState(b,today,doc.year).date)||'9999')||a.title.localeCompare(b.title));
}

export function renderMovies(index){
  const root=node('section',null,'movies-root');
  if(!index)return root;
  const panel=node('div',null,'movie-panel'),head=node('div',null,'movie-head');
  const title=node('div');title.append(node('h2','연도별 개봉 일정과 흥행 성적'),node('p','개봉일은 북미(미국·캐나다) 기준입니다. 다른 국가의 개봉일·IMAX 상영일과 다를 수 있습니다.'));
  const expand=node('button','전체화면');expand.type='button';expand.setAttribute('aria-haspopup','dialog');head.append(title,expand);
  const scope=node('details',null,'movie-scope');scope.append(node('summary','날짜·흥행액·IMAX 표시 기준'));
  for(const text of ['세계 흥행 상위 100편과 북미 공개 개봉 일정을 영화 원문 ID로 연결합니다. 세계 성적 미확보 작품도 북미 누적 실적이 있으면 표시하며, 미확보 값은 0으로 채우지 않습니다.',
    '금액은 작품의 누적 티켓 매출입니다. 재개봉 행은 기존 개봉의 매출을 포함할 수 있으며, 당해 연도나 해당 상영 회차만의 성적이 아닙니다. 제작사·극장·IMAX의 매출이나 영화의 순이익을 뜻하지 않습니다.',
    'IMAX는 공개 일정의 별도 IMAX 표기 또는 공식 IR 언급을 확인한 경우 표시합니다. 미표시는 비상영을 뜻하지 않습니다. IR의 예상 라인업은 확정·완전한 목록이 아니며 지역·날짜는 바뀔 수 있습니다. 작품별 IMAX 공시 성적은 오프닝·누적·공시일을 따로 표시하며 세계 누적액으로 나눠 비중을 추정하지 않습니다.',
    '동일 작품의 일반·확대·IMAX·재개봉 일정은 한 행으로 묶고 상세에 보존합니다. ‘개봉 예정’에는 이미 개봉한 작품의 추가 상영 일정도 포함합니다.'])scope.append(node('p',text));
  const controls=node('div',null,'movie-controls');
  const select=(label,options)=>{const holder=node('label');holder.append(node('span',label));const el=node('select');el.setAttribute('aria-label',label);for(const [value,text] of options){const o=node('option',text);o.value=value;el.append(o);}holder.append(el);controls.append(holder);return el;};
  const year=select('개봉 연도',index.years.map(y=>[String(y.year),`${y.year}년`]));year.value=String(index.default_year);
  if(!year.value)year.value=String(index.years[0].year);
  const distributor=select('배급사',[['','전체 배급사']]);
  const sort=select('정렬',[['date','개봉일순'],['gross','세계 흥행액순']]);
  const searchLabel=node('label',null,'movie-search');searchLabel.append(node('span','작품·배급사 검색'));const search=node('input');search.type='search';search.setAttribute('aria-label','작품·배급사 검색');search.placeholder='작품명, Disney, Warner…';searchLabel.append(search);controls.append(searchLabel);
  const check=(label,checked)=>{const l=node('label',null,'movie-check');const i=node('input');i.type='checkbox';i.checked=checked;l.append(i,node('span',label));controls.append(l);return i;};
  const major=check('주요 개봉작만',true),imax=check('IMAX 공개 라인업만',false);
  const csv=node('button','조회 결과 CSV');csv.type='button';controls.append(csv);
  const views=node('div',null,'movie-views');views.setAttribute('role','group');views.setAttribute('aria-label','개봉·흥행 보기');
  const count=node('p',null,'movie-count');count.setAttribute('role','status');count.setAttribute('aria-live','polite');
  const notice=node('p',null,'movie-notice');notice.hidden=true;
  const wrapper=node('div',null,'movie-table-wrap');wrapper.tabIndex=0;wrapper.setAttribute('role','region');wrapper.setAttribute('aria-label','영화 개봉·흥행 표');
  const table=node('table');const caption=node('caption','흥행액 단위: 백만 USD · 작품 누적 · 미확보 — · 좌우로 스크롤');const thead=node('thead'),tbody=node('tbody');table.append(caption,thead,tbody);wrapper.append(table);
  const pager=node('div',null,'movie-pager'),prev=node('button','이전'),next=node('button','다음'),pageLabel=node('span');prev.type=next.type='button';pager.append(prev,pageLabel,next);
  const source=node('p',null,'movie-source');
  panel.append(head,scope,controls,views,count,notice,wrapper,pager,source);
  const full=node('dialog',null,'movie-fullscreen');full.setAttribute('aria-label','영화 개봉·흥행 전체화면');root.append(panel,full);
  const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(new Date());
  let doc=null,view='all',page=0,filtered=[],requestId=0;const cache=new Map(),pageSize=40,viewButtons=[];
  const cell=(tr,value,cls)=>{const td=node('td',value,cls);tr.append(td);return td;};
  const closeDetails=()=>tbody.querySelectorAll('.movie-expanded').forEach(el=>el.remove());
  function draw(){
    if(!doc)return;
    filtered=selectFilms(doc,{view,major:major.checked,imax:imax.checked,distributor:distributor.value,query:search.value,sort:sort.value,today});
    page=Math.min(page,Math.max(0,Math.ceil(filtered.length/pageSize)-1));viewButtons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
    count.textContent=`${doc.year}년 ${filtered.length.toLocaleString('ko-KR')} / ${doc.films.length.toLocaleString('ko-KR')}편 · 북미 개봉 기준 · 수집 ${doc.fetched}`;
    thead.replaceChildren();tbody.replaceChildren();const hr=node('tr');for(const label of ['작품','북미 개봉 / 일정','배급사','IMAX / 공시 성적','전 세계','북미','해외','상태 / 원문']){const th=node('th',label);th.scope='col';hr.append(th);}thead.append(hr);
    if(!filtered.length){const tr=node('tr');cell(tr,'조건에 맞는 작품이 없습니다. 연도·보기·검색어·체크박스를 확인해 주세요.','movie-empty').colSpan=8;tbody.append(tr);}
    for(const f of filtered.slice(page*pageSize,(page+1)*pageSize)){
      const tr=node('tr'),s=filmState(f,today,doc.year);tr.dataset.movieId=f.id;
      const name=cell(tr,null,'movie-title');name.append(link(f.url,f.title));if(f.rerelease)name.append(node('small','재개봉 일정 포함 · 과거 누적 포함 가능'));
      const dates=cell(tr,null);dates.append(node('span',(view==='upcoming'?s.next_date:s.date)||f.events[0]?.date_text||'북미 일자 미확인'));if(f.events.length>1)dates.append(node('small',`${f.events.length}개 공개 일정`));
      cell(tr,f.distributors.join(' / ')||'미확인');
      const format=cell(tr,null);format.append(node('span',f.imax_confirmed?'IMAX 공개 라인업':'미확인'));
      if(f.imax_evidence.length)format.append(node('small',f.imax_evidence.some(e=>e.kind==='schedule')?'북미 일정에 IMAX 명시':`${f.imax_evidence[0].source_date||f.imax_evidence[0].checked} IR · ${f.imax_evidence[0].note}`));
      for(const e of f.imax_evidence.filter(e=>e.performance)){const p=e.performance;format.append(node('strong',`${p.basis}: ${p.comparator==='>'?'> ':''}${usd(p.amount_usd)} 백만 USD`,'movie-performance'),node('small',`${p.published} 공시`));}
      for(const field of ['worldwide_usd','domestic_usd','international_usd'])cell(tr,usd(f[field]),'movie-number');
      const action=cell(tr,null);action.append(node('small',s.label),link(f.box_office_url||f.url,'성적·원문'));
      const detail=node('button','상세');detail.type='button';detail.setAttribute('aria-expanded','false');action.append(detail);tbody.append(tr);
      detail.addEventListener('click',()=>{
        const existing=tr.nextElementSibling;
        if(existing?.classList.contains('movie-expanded')){existing.remove();detail.setAttribute('aria-expanded','false');return;}
        const extra=node('tr',null,'movie-expanded'),td=cell(extra,null);td.colSpan=8;detail.setAttribute('aria-expanded','true');
        td.append(node('h3',f.title));
        for(const event of f.events){const p=node('p',`${event.date||event.date_text||'일자 미확인'} · ${event.release_type} · ${event.distributor||'배급사 미확인'} `);p.append(link(event.source_url,'개봉 일정 원문'));td.append(p);}
        if(!f.events.length)td.append(node('p','세계 흥행 표에는 포함되지만 이 연도의 북미 개봉 일정과 연결하지 못했습니다.'));
        for(const e of f.imax_evidence){const p=node('p',`IMAX: ${e.note} · 자료 기준 ${e.source_date||e.checked}${e.performance?` · ${e.performance.basis} ${e.performance.comparator==='>'?'> ':''}${usd(e.performance.amount_usd)} 백만 USD`:''} `);p.append(link(e.source_url,'근거'));td.append(p);}
        td.append(node('p',`박스오피스 확인일 ${f.box_office_checked||'미확보'} · 누적 티켓 매출. 재개봉 이전 매출을 포함할 수 있습니다.`));tr.after(extra);
      });
    }
    prev.disabled=page===0;next.disabled=(page+1)*pageSize>=filtered.length;pageLabel.textContent=`${page+1} / ${Math.max(1,Math.ceil(filtered.length/pageSize))}`;
    source.replaceChildren(link(doc.sources[0],'개봉 일정 출처'),node('span',' · '));if(doc.sources[1])source.append(link(doc.sources[1],'세계 흥행 상위 100편 출처'));
  }
  async function loadYear(){
    const seq=++requestId,number=Number(year.value),entry=index.years.find(y=>y.year===number);doc=null;page=0;tbody.replaceChildren();thead.replaceChildren();count.textContent=`${number}년 자료를 불러오는 중…`;prev.disabled=next.disabled=true;
    notice.hidden=entry?.ok!==false;if(!notice.hidden)notice.textContent=`${entry.checked} 원문 갱신 실패 · ${entry.fetched}의 마지막 확인 자료를 표시합니다.`;
    try{
      if(!cache.has(number)){
        const response=await fetch(`data/movies/films_${number}.json?v=${encodeURIComponent(entry?.fetched||index.fetched)}`,{cache:'no-cache'});if(!response.ok)throw new Error('연도별 자료를 불러오지 못했습니다.');
        const result=await response.json();if(result.year!==number||!Array.isArray(result.films))throw new Error('연도별 자료 형식을 확인해 주세요.');cache.set(number,result);
      }
      if(seq!==requestId)return;doc=cache.get(number);
      distributor.replaceChildren();const all=node('option','전체 배급사');all.value='';distributor.append(all);
      for(const d of [...new Set(doc.films.flatMap(f=>f.distributors))].sort()){const option=node('option',d);option.value=d;distributor.append(option);}
      view=number>=Number(today.slice(0,4))?'upcoming':'released';sort.value=view==='released'?'gross':'date';draw();
    }catch(error){if(seq===requestId){count.textContent='자료를 표시하지 못했습니다.';notice.hidden=false;notice.textContent=error.message+' 다른 연도를 선택하거나 새로고침해 주세요.';}}
  }
  for(const [id,label] of [['upcoming','개봉 예정'],['released','흥행 성적'],['all','전체']]){const b=node('button',label);b.type='button';b.dataset.view=id;b.addEventListener('click',()=>{view=id;sort.value=id==='released'?'gross':'date';page=0;draw();});views.append(b);viewButtons.push(b);}
  year.addEventListener('change',loadYear);
  for(const el of [distributor,sort,major,imax,search])el.addEventListener(el===search?'input':'change',()=>{page=0;wrapper.scrollTop=0;draw();});
  prev.addEventListener('click',()=>{page--;wrapper.scrollTop=0;draw();});next.addEventListener('click',()=>{page++;wrapper.scrollTop=0;draw();});
  csv.addEventListener('click',()=>{
    if(!doc)return;
    const escape=v=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';
    const rows=[['작품','표시연도','북미 일정','배급사','IMAX 공개 근거','IMAX 공시 성적(범위·USD·공시일)','전세계 누적(USD)','북미 누적(USD)','해외 누적(USD)','확인일','원문'],...filtered.map(f=>[f.title,doc.year,f.events.map(e=>e.date||e.date_text).join(' / '),f.distributors.join(' / '),f.imax_evidence.map(e=>e.note).join(' / '),f.imax_evidence.filter(e=>e.performance).map(e=>`${e.performance.basis} ${e.performance.comparator} ${e.performance.amount_usd} USD (${e.performance.published})`).join(' / '),f.worldwide_usd,f.domestic_usd,f.international_usd,f.box_office_checked,f.box_office_url||f.url])];
    const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(r=>r.map(escape).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=node('a');a.href=url;a.download=`영화-${year.value}-${view}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  expand.setAttribute('aria-expanded','false');let scroll={left:0,top:0};expand.addEventListener('click',()=>{if(full.open){full.close();return;}scope.open=false;closeDetails();scroll={left:window.scrollX,top:window.scrollY};full.append(panel);full.showModal();expand.textContent='전체화면 닫기';expand.setAttribute('aria-expanded','true');expand.focus({preventScroll:true});});
  full.addEventListener('close',()=>{root.insertBefore(panel,full);expand.textContent='전체화면';expand.setAttribute('aria-expanded','false');if(root.isConnected){expand.focus({preventScroll:true});window.scrollTo({...scroll,behavior:'instant'});}});
  loadYear();return root;
}

export function renderMovieCompanies(doc){
  const root=node('section',null,'movie-company-overview');if(!doc)return root;root.append(node('p','기술·극장·광고의 사업 구조를 구분해 비교합니다. 아래 실적 그래프는 각 회사 전체 연결 기준입니다.'));
  const wrapper=node('div',null,'movie-company-wrap'),table=node('table');const head=node('thead'),hr=node('tr');
  for(const t of ['기업','영화 노출 경로','실적 범위·비교 기준']){const th=node('th',t);th.scope='col';hr.append(th);}head.append(hr);table.append(head);const body=node('tbody');
  for(const r of doc.companies){const tr=node('tr');for(const text of [r.name,r.scope,r.note])tr.append(node('td',text));body.append(tr);}table.append(body);wrapper.append(table);root.append(wrapper);return root;
}

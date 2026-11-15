/* USD millions throughout; source observations never become forecast facts. */
const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const fmt=(v,d=1)=>Number.isFinite(v)?v.toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
const percentKeys=new Set(['dmr_pct','jrsa_share_pct','jrsa_rate_pct','content_margin_pct','technology_margin_pct','other_margin_pct','odyssey_dmr_pct','odyssey_jrsa_share_pct','odyssey_jrsa_rate_pct','odyssey_content_margin_pct','odyssey_technology_margin_pct']);
const required=['dmr_pct','jrsa_share_pct','jrsa_rate_pct','content_margin_pct','technology_margin_pct','other_margin_pct','other_content','system_sales','maintenance','finance','other','opex','residual','multiple','debt','cash','shares'];
export function numeric(value){if(value==null||String(value).trim()==='')return null;const n=Number(value);return Number.isFinite(n)?n:null;}
const valid=(n,max=Infinity)=>Number.isFinite(n)&&n>=0&&n<=max;
export function filmEstimate(row){
  if(!row.include)return {included:false,gbo:0};
  const direct=numeric(row.direct_imax),world=numeric(row.worldwide),share=numeric(row.imax_pct),recognition=numeric(row.in_year_pct);
  if(!valid(recognition,100)||row.regional_only&&direct==null||row.direct_imax!=null&&String(row.direct_imax).trim()!==''&&!valid(direct)||direct==null&&(!valid(world)||!valid(share,100)))return {included:true,gbo:null};
  return {included:true,gbo:(direct??world*share/100)*recognition/100};
}
export function annualEstimate(period,rows,params,factor=1){
  const issues=[];
  for(const key of required)if(!valid(numeric(params[key]),percentKeys.has(key)?100:Infinity)||(key==='shares'||key==='multiple')&&numeric(params[key])===0)issues.push(key);
  for(const key of ['nci','price'])if(params[key]!=null&&String(params[key]).trim()!==''&&!valid(numeric(params[key])))issues.push(key);
  const selected=rows.filter(r=>r.include),missing=selected.filter(r=>filmEstimate(r).gbo==null);
  if(issues.length||missing.length||!valid(factor))return {issues,missing:missing.map(r=>r.title),complete:false};
  const p=Object.fromEntries(Object.entries(params).map(([k,v])=>[k,numeric(v)]));
  const filmGbo=selected.reduce((sum,r)=>sum+filmEstimate(r).gbo,0);
  const gbo=(filmGbo+p.residual)*factor,dmr=gbo*p.dmr_pct/100,rentals=gbo*p.jrsa_share_pct/100*p.jrsa_rate_pct/100;
  const content=dmr+p.other_content,technology=rentals+p.system_sales+p.maintenance+p.finance;
  const revenue=content+technology+p.other;
  const gross=content*p.content_margin_pct/100+technology*p.technology_margin_pct/100+p.other*p.other_margin_pct/100;
  const profit=gross-p.opex;
  const actual=period.actual,total={gbo:actual.gbo+gbo,revenue:actual.revenue+revenue,gross:actual.gross+gross,profit:actual.profit+profit};
  const ev=total.profit>0?total.profit*p.multiple:null;
  const equity=ev!=null&&p.nci!=null?ev-p.debt+p.cash-p.nci:null;
  const value=equity==null||equity<0?null:equity/p.shares;
  return {complete:true,issues:[],missing:[],selected:selected.length,filmGbo,dmr,rentals,content,technology,
    forecast:{gbo,revenue,gross,profit},actual,total,ev,equity,value,upside:value!=null&&p.price>0?value/p.price-1:null};
}
export function odysseyEstimate(facts,params){
  const gbo=facts.odyssey.imax_gbo,p=Object.fromEntries(Object.entries(params).map(([k,v])=>[k,numeric(v)]));
  if(['odyssey_dmr_pct','odyssey_jrsa_share_pct','odyssey_jrsa_rate_pct','odyssey_content_margin_pct','odyssey_technology_margin_pct'].some(k=>!valid(p[k],100))||!valid(p.odyssey_extra_cost))return null;
  const dmr=gbo*p.odyssey_dmr_pct/100,rentals=gbo*p.odyssey_jrsa_share_pct/100*p.odyssey_jrsa_rate_pct/100;
  const gross=dmr*p.odyssey_content_margin_pct/100+rentals*p.odyssey_technology_margin_pct/100;
  return {dmr,rentals,revenue:dmr+rentals,gross,profit:gross-p.odyssey_extra_cost,typicalDmr:gbo*facts.typical_dmr_pct/100};
}
const safeLink=(url,label)=>{const a=make('a',label);if(/^https:\/\/(?:www\.sec\.gov|investors\.imax\.com|www\.the-numbers\.com)\//.test(url||'')){a.href=url;a.target='_blank';a.rel='noopener';}return a;};
const download=(name,content,type)=>{const url=URL.createObjectURL(new Blob(['\ufeff',content],{type})),a=make('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
const csvEscape=v=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';
export function renderImaxModel(doc){
  const root=make('section',null,'imax-model');root.setAttribute('aria-label','IMAX 흥행·실적 추정 모델');if(!doc)return root;
  const facts=doc.facts,key='industry-dashboard:imax-model:v1';let stored={};
  try{stored=JSON.parse(localStorage.getItem(key)||'{}');if(!stored||typeof stored!=='object'||Array.isArray(stored))stored={};}catch{stored={};}
  const head=make('div',null,'imax-model-head'),heading=make('div');heading.append(make('h2','작품 흥행에서 IMAX 기업가치까지'),make('p','금액: 백만 USD · 입력 예시는 회사 전망·시장 컨센서스가 아닙니다.'));
  const yearLabel=make('label','추정 연도'),year=make('select');year.setAttribute('aria-label','IMAX 추정 연도');
  for(const y of Object.keys(doc.periods).sort()){const o=make('option',`${y}년`);o.value=y;year.append(o);}year.value=String(doc.default_year);yearLabel.append(year);head.append(heading,yearLabel);root.append(head);
  const periodNote=make('p',null,'imax-period-note'),status=make('p',null,'imax-save-status');status.setAttribute('role','status');root.append(periodNote);
  const fees=make('details',null,'imax-method');fees.append(make('summary','수수료 구조와 계산 기준'));
  fees.append(make('p','배급사 → IMAX: 통상 IMAX 상영관 티켓 매출의 약 12.5%를 리마스터링·배급 대가로 받습니다. 일반관 흥행액에는 적용하지 않습니다. 세금·중국 수입작 요율·정산 시점 때문에 공시 매출을 전체 IMAX 흥행액으로 나눈 실현율은 달라집니다.'),
    make('p','극장 → IMAX: JRSA(장비 수익배분 계약) 상영관의 흥행에서 장비 임대수익을 받습니다. 계약별 비율이 다르고, Hybrid는 전통형보다 수익배분율이 통상 낮습니다. 아래 모델은 2025년 실제 임대매출 ÷ JRSA 흥행액을 사용하며 이를 표준 계약요율로 해석하지 않습니다.'),
    make('p','작품 세계 흥행 × IMAX 비중 × 연내 반영률 → IMAX 흥행. 여기에 실효 DMR 요율과 [JRSA 흥행 비중 × 실현 임대율]을 각각 적용합니다. 장비 판매·유지보수 등은 별도로 더하고, 사업부별 매출총이익률을 적용한 뒤 영업비용을 차감합니다.'));
  const feeTable=make('div',null,'imax-small-table');fees.append(feeTable);root.append(fees);
  const filmSection=make('section',null,'imax-film-section'),filmHeading=make('div',null,'imax-section-head');filmHeading.append(make('h3','작품별 흥행 가정'));
  const reset=make('button','이 연도 가정 초기화'),csv=make('button','가정·결과 CSV'),add=make('button','작품·이월 흥행 직접 추가');reset.type=csv.type=add.type='button';filmHeading.append(add,csv,reset);filmSection.append(filmHeading);
  filmSection.append(make('p','체크된 작품만 합산합니다. 전작이 있는 일부 작품은 전작 누적 세계 흥행액을 입력 예시로 넣었습니다. IMAX 비중 10%, 연내 반영률 100%(11월 80%·12월 35%)도 수정할 가정입니다. 재개봉은 과거 세계 누적액을 그대로 쓰지 마세요.','imax-help'));
  const coverage=make('p',null,'imax-coverage');filmSection.append(coverage);
  const wrap=make('div',null,'imax-film-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','IMAX 작품별 가정 표');
  const table=make('table'),caption=make('caption','세계 흥행·IMAX 직접 입력은 전체 상영 기간 예상액. 연내 반영률로 해당 연도 금액을 계산합니다.'),thead=make('thead'),hr=make('tr');
  for(const t of ['반영','작품 / 북미 일정','참고작 세계 누적','세계 흥행 가정','IMAX 비중 %','연내 반영 %','IMAX 흥행 직접 입력','해당 연도 IMAX 흥행','DMR + 임대 매출 추정']){const th=make('th',t);th.scope='col';hr.append(th);}thead.append(hr);const body=make('tbody');table.append(caption,thead,body);wrap.append(table);filmSection.append(wrap);root.append(filmSection);
  const residualHolder=make('div',null,'imax-residual');root.append(residualHolder);
  const assumptions=make('details',null,'imax-assumptions');assumptions.append(make('summary','수수료·장비 매출·비용 가정 수정'));const inputsGrid=make('div',null,'imax-input-grid');assumptions.append(inputsGrid,make('p','초기 요율은 2025년 연간 실현값입니다. 비용에는 주식보상과 감가·상각, 손상 등 공시 영업비용이 포함됩니다. 작품 계약별 실제 요율·원가는 미공개이며, 공통 평균을 적용한 단순 모델입니다.','imax-help'));root.append(assumptions);
  const resultSection=make('section',null,'imax-results');resultSection.append(make('h3','연간 손익과 밸류에이션'));
  const issues=make('p',null,'imax-issues');issues.setAttribute('role','status');const result=make('div');resultSection.append(issues,result);root.append(resultSection);
  const valuation=make('details',null,'imax-valuation');valuation.open=true;valuation.append(make('summary','기업가치 → 주당가치 가정'));const valueInputs=make('div',null,'imax-input-grid');valuation.append(valueInputs);
  const book=make('button','비지배지분 장부가로 예시 계산');book.type='button';valuation.append(book,
    make('p','EV/영업이익 배수 15배는 입력 예시입니다. EV에서 차입금을 빼고 현금을 더하며, 비지배지분 가치도 차감해야 주주가치가 됩니다. 비지배지분 미입력 시 EV만 표시합니다. 장부가 버튼은 시장가치의 대용치이므로 실제 가치와 다를 수 있습니다.','imax-help'),
    make('p','차입금·현금·발행주식수 초기값은 2026-09-30 공시입니다. 차입금은 발행비 차감 장부가이며 전환사채를 부채로 유지합니다. 전환·추가 희석과 주가 실시간 연동은 반영하지 않았습니다. 거래가격·희석 가정은 직접 수정하세요.','imax-help'));
  const valuationResult=make('div',null,'imax-value-result');valuation.append(valuationResult);root.append(valuation);
  const caseSection=make('details',null,'imax-odyssey');caseSection.open=true;caseSection.append(make('summary','오디세이: 공시로 확인한 사실과 기여 추정'));
  caseSection.append(make('p','오디세이의 2026년 3분기 IMAX 흥행액은 538.0입니다. 11월 5일 공시의 누적 약 556.0을 3분기에 넣지 않습니다. 작품별 계약 매출·원가·영업이익은 별도 공개되지 않았습니다.'),make('p','이 분석의 초기 요율·이익률은 같은 2026년 3분기 전체 회사·사업부의 공시 평균입니다. 위 연간 모델의 2025년 요율과 별도로 조정할 수 있으며, 오디세이의 실제 계약 요율을 의미하지 않습니다.','imax-help'));
  const caseFacts=make('div',null,'imax-small-table');caseSection.append(caseFacts);const caseInput=make('div',null,'imax-input-grid');caseSection.append(caseInput);const caseResults=make('div',null,'imax-case-results');caseSection.append(caseResults,
    make('p','추정액은 오디세이 상영에 귀속시킨 총 기여입니다. 영화가 없었을 경우 다른 영화가 벌었을 대체 흥행과 상영관 점유 효과를 차감하지 않았으므로 순증 효과가 아닙니다. 회사 전체 전년 대비 증감액을 오디세이 단독 효과로 볼 수 없습니다.','imax-help'));root.append(caseSection);
  const references=make('details',null,'imax-references');references.append(make('summary','IMAX 실제 흥행 참고자료 · 기간 구분'));const refs=make('div',null,'imax-small-table');references.append(refs,make('p','여기 금액은 표에 적힌 기간의 IMAX 흥행입니다. 전작 세계 누적액과 기간이 달라 이 둘을 나눈 비율을 모델 기본값으로 쓰지 않습니다.','imax-help'));root.append(references);
  const sources=make('p',null,'imax-sources');sources.append(make('span',`수수료·실적 검토 ${doc.reviewed} · `));for(const source of Object.values(facts.sources))sources.append(safeLink(source.url,`${source.label} (${source.date})`),make('span',' '));root.append(sources,status);
  function smallTable(host,headers,rows){const w=make('div',null,'imax-table-scroll'),t=make('table'),h=make('thead'),r=make('tr');for(const label of headers){const th=make('th',label);th.scope='col';r.append(th);}h.append(r);const b=make('tbody');for(const row of rows){const tr=make('tr');for(const v of row){const td=make('td');if(v instanceof Node)td.append(v);else td.textContent=v;tr.append(td);}b.append(tr);}t.append(h,b);w.append(t);host.replaceChildren(w);}
  const a=facts.annual_2025,q=facts.q3_2026,q0=facts.q3_2025;
  smallTable(feeTable,['2025년 공시 실현값','계산','비율'],[
    ['DMR 실효율',`${fmt(a.dmr,3)} ÷ IMAX 흥행 ${fmt(a.gbo)}`,`${fmt(a.dmr/a.gbo*100,2)}%`],
    ['JRSA 흥행 비중',`${fmt(a.jrsa_gbo)} ÷ 전체 IMAX 흥행 ${fmt(a.gbo)}`,`${fmt(a.jrsa_gbo/a.gbo*100,2)}%`],
    ['JRSA 실현 임대율',`${fmt(a.rentals,3)} ÷ JRSA 흥행 ${fmt(a.jrsa_gbo)}`,`${fmt(a.rentals/a.jrsa_gbo*100,2)}%`],
    ['전체 IMAX 흥행 대비 임대매출','JRSA 흥행 비중 × 실현 임대율',`${fmt(a.rentals/a.gbo*100,2)}%`]]);
  smallTable(caseFacts,['3분기 전체 회사 공시','2025 Q3','2026 Q3','증감'],['gbo','revenue','profit'].map((k,i)=>[['IMAX 티켓 매출','IMAX 회사 매출','GAAP 영업이익'][i],fmt(q0[k]),fmt(q[k]),fmt(q[k]-q0[k])]));
  smallTable(refs,['작품','IMAX 흥행','성적 범위 / 원문'],facts.imax_references.map(f=>[f.title,fmt(f.gbo),safeLink(facts.sources[f.source].url,f.period)]));
  let period,params,rows,rowViews=[],paramInputs=[];
  function save(){try{stored[year.value]={params,rows:rows.map(r=>({id:r.id,title:r.title,custom:r.custom||false,include:r.include,worldwide:r.worldwide,imax_pct:r.imax_pct,in_year_pct:r.in_year_pct,direct_imax:r.direct_imax}))};localStorage.setItem(key,JSON.stringify(stored));status.textContent='가정은 이 브라우저에 저장됩니다. 다른 기기와 공유하려면 CSV를 내려받으세요.';}catch{status.textContent='브라우저 저장 공간을 사용할 수 없습니다. 가정·결과 CSV로 보관하세요.';}}
  function numberInput(label,value,onInput,max){const input=make('input');input.type='number';input.min='0';if(max!=null)input.max=String(max);input.step='any';input.inputMode='decimal';input.value=Number.isFinite(value)?Number(value.toFixed(6)):value??'';input.setAttribute('aria-label',label);input.addEventListener('input',()=>{onInput(input.value===''?null:Number(input.value));update();save();});return input;}
  function parameter(host,label,k,hint){const holder=make('label');holder.append(make('span',label));const input=numberInput(label,params[k],v=>{params[k]=v;if(k==='nci')params.nci_book_proxy=false;},percentKeys.has(k)?100:null);input.dataset.param=k;paramInputs.push([input,k]);holder.append(input);if(hint)holder.append(make('small',hint));host.append(holder);return input;}
  function drawRows(){
    body.replaceChildren();rowViews=[];
    for(const r of rows){const tr=make('tr');tr.dataset.filmId=r.id;const td=(value)=>{const c=make('td');if(value instanceof Node)c.append(value);else if(value!=null)c.textContent=value;tr.append(c);return c;};
      const check=make('input');check.type='checkbox';check.checked=!!r.include;check.setAttribute('aria-label',`${r.title} 반영`);check.addEventListener('change',()=>{r.include=check.checked;update();save();});td(check);
      const title=td(null);
      if(r.custom){const edit=make('input');edit.type='text';edit.value=r.title;edit.setAttribute('aria-label','추가 작품명');edit.addEventListener('input',()=>{r.title=edit.value||'직접 추가';save();});title.append(edit);}else title.append(safeLink(r.url,r.title));
      title.append(make('small',r.custom?'직접 추가한 시나리오':r.regional_only?'2027 중국 · 일자 미정':r.date||'북미 일자 미정'));
      if(r.regional_only)title.append(make('small','중국 IMAX 흥행만 직접 입력 · 세계 흥행 사용 불가'));
      const comp=td(null);if(r.comparable)comp.append(safeLink(r.comparable.url,r.comparable.title),make('strong',fmt(r.comparable.worldwide)),make('small',`세계 누적 · 확인 ${r.comparable.checked||'원문 참조'}`));else comp.append(make('span','직접 가정 필요'));
      const inputs=[];
      for(const [field,label,max] of [['worldwide','세계 흥행 가정',null],['imax_pct','IMAX 비중',100],['in_year_pct','연내 반영률',100],['direct_imax','IMAX 흥행 직접 입력',null]]){
        const input=numberInput(`${r.title} ${label}`,r[field],v=>r[field]=v,max);input.dataset.field=field;td(input);inputs.push([input,field]);}
      const gross=td(null),revenue=td(null);body.append(tr);rowViews.push({tr,r,gross,revenue,inputs});
    }
    if(!rows.length){const tr=make('tr'),td=make('td','이 연도의 공개 IMAX 라인업이 없습니다. 작품을 직접 추가하거나 기타 흥행 가정을 입력하세요.');td.colSpan=9;tr.append(td);body.append(tr);}
  }
  function lineChart(estimates){
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 640 190');svg.setAttribute('role','img');svg.setAttribute('aria-label','흥행 하락·기준·상승 시나리오별 연간 매출과 영업이익');svg.classList.add('imax-scenario-chart');
    const vals=estimates.flatMap(e=>[e.total.revenue,e.total.profit]),min=Math.min(0,...vals),max=Math.max(1,...vals),y=v=>150-(v-min)/(max-min)*125;
    const el=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text)n.textContent=text;svg.append(n);return n;};
    el('line',{x1:55,y1:y(0),x2:585,y2:y(0),stroke:'var(--border)'});
    for(const [field,color,label] of [['revenue','var(--accent)','매출'],['profit','#18836b','영업이익']]){el('polyline',{points:estimates.map((e,i)=>`${100+i*220},${y(e.total[field])}`).join(' '),fill:'none',stroke:color,'stroke-width':2.5});estimates.forEach((e,i)=>{el('circle',{cx:100+i*220,cy:y(e.total[field]),r:3,fill:color});el('text',{x:100+i*220,y:y(e.total[field])-9,'text-anchor':'middle',fill:color},`${label} ${fmt(e.total[field])}`);});}
    ['흥행 −20%','기준','흥행 +20%'].forEach((label,i)=>el('text',{x:100+i*220,y:180,'text-anchor':'middle',fill:'var(--muted)'},label));return svg;
  }
  function update(){
    const e=annualEstimate(period,rows,params),selected=rows.filter(r=>r.include).length;
    coverage.textContent=`공개 라인업 ${rows.filter(r=>!r.custom).length}편 중 선택 ${selected}편(직접 추가 포함) · 미선택 ${rows.length-selected}편은 작품 합계에서 제외. 이월·로컬작·누락 작품은 아래 기타 흥행 가정으로 보완합니다.`;
    const takeValid=['dmr_pct','jrsa_share_pct','jrsa_rate_pct'].every(k=>valid(numeric(params[k]),100));
    for(const v of rowViews){const f=filmEstimate(v.r);v.tr.classList.toggle('imax-row-excluded',!v.r.include);v.gross.textContent=v.r.include?fmt(f.gbo):'제외';const take=numeric(params.dmr_pct)/100+numeric(params.jrsa_share_pct)/100*numeric(params.jrsa_rate_pct)/100;v.revenue.textContent=v.r.include?fmt(f.gbo==null||!takeValid?null:f.gbo*take):'—';for(const [input,field] of v.inputs){input.disabled=!v.r.include||(field==='worldwide'||field==='imax_pct')&&(numeric(v.r.direct_imax)!=null||v.r.regional_only);input.setAttribute('aria-invalid',String(v.r.include&&f.gbo==null));}}
    for(const [input,k] of paramInputs)input.setAttribute('aria-invalid',String(e.issues?.includes(k)||k.startsWith('odyssey_')&&!valid(numeric(params[k]),percentKeys.has(k)?100:Infinity)));
    issues.hidden=e.complete;issues.textContent=e.complete?'':`계산 대기: ${e.missing.length?e.missing.join(', ')+'의 흥행 가정':''}${e.issues.length?' · 수수료·비용·가치 가정의 빈칸 또는 범위를 확인하세요.':''}`;
    result.replaceChildren();valuationResult.replaceChildren();
    if(e.complete){
      const forecastName=period.cutoff?'4분기 추정':'연간 추정';
      smallTable(result,['손익 연결','확정 1~3분기',forecastName,`${year.value}년 합계`],[['IMAX 티켓 매출','gbo'],['IMAX 회사 매출','revenue'],['매출총이익','gross'],['영업이익','profit']].map(([name,k])=>[name,period.cutoff?fmt(e.actual[k]):'해당 없음',fmt(e.forecast[k]),fmt(e.total[k])]));
      const detail=make('p',`추정 기간 회사 매출 = DMR ${fmt(e.dmr)} + 장비 임대 ${fmt(e.rentals)} + 기타 콘텐츠 ${fmt(numeric(params.other_content))} + 장비 판매 ${fmt(numeric(params.system_sales))} + 유지보수 ${fmt(numeric(params.maintenance))} + 금융수익 ${fmt(numeric(params.finance))} + 기타 ${fmt(numeric(params.other))}.`,'imax-help');result.append(detail);
      const scenarios=[.8,1,1.2].map(f=>annualEstimate(period,rows,params,f));result.append(lineChart(scenarios));const sensitivity=make('div');smallTable(sensitivity,['흥행 민감도','IMAX 연간 흥행','연간 회사 매출','연간 영업이익','EV / 영업이익'],scenarios.map((s,i)=>[['하락 −20%','기준','상승 +20%'][i],fmt(s.total.gbo),fmt(s.total.revenue),fmt(s.total.profit),fmt(s.ev)]));result.append(sensitivity,make('p','민감도는 추정 기간 티켓 매출만 ±20% 바꿉니다. 확정 실적·장비 매출·비용·이익률·배수는 고정합니다. 작품 편성·요율 변화를 별도로 반영하려면 가정을 수정하세요.','imax-help'));
      smallTable(valuationResult,['기업가치 연결','기준 시나리오'],[['영업이익 × EV/영업이익 배수',e.ev==null?'영업적자 · 배수법 계산 안 함':fmt(e.ev)],['− 차입금 + 현금',`${fmt(numeric(params.debt))} / ${fmt(numeric(params.cash))}`],[params.nci_book_proxy?'− 비지배지분 (장부가 대용)':'− 비지배지분 평가액',fmt(numeric(params.nci))],['보통주 주주가치',fmt(e.equity)],['발행주식수 (백만 주)',fmt(numeric(params.shares),3)],['가정상 주당가치 (USD)',e.equity!=null&&e.equity<0?'잔여가치 음수 · 주당가치 계산 안 함':fmt(e.value,2)],['입력 주가 대비',e.upside==null?'계산 가능한 주당가치·비교 주가 필요':`${fmt(e.upside*100,1)}%`]]);
    }else{result.append(make('p','선택 작품의 입력을 완료하거나 해당 작품을 제외하면 결과가 표시됩니다.','imax-help'));}
    const o=odysseyEstimate(facts,params);caseResults.replaceChildren();
    if(o)smallTable(caseResults,['오디세이 2026 Q3 기여 계산','금액 / 상태'],[['통상 DMR 12.5%만 단순 적용',`${fmt(o.typicalDmr,2)} · 계약상 실제 수취액 아님`],['사례 가정의 DMR + JRSA 매출',`${fmt(o.revenue,2)} = ${fmt(o.dmr,2)} + ${fmt(o.rentals,2)} · 추정`],['매출총이익 기여',`${fmt(o.gross,2)} · 공통 사업부 이익률 적용`],['추가 영업비용 차감 후 기여',`${fmt(o.profit,2)} · 추가 영업비용 ${fmt(numeric(params.odyssey_extra_cost))} 가정 · 실제 공시 이익 아님`]]);
    else caseResults.append(make('p','오디세이 사례의 요율·이익률(0~100%)과 추가 영업비용을 확인하세요.','imax-issues'));
  }
  function loadYear(){
    period=doc.periods[year.value];const saved=stored[year.value]||{};params={...period.params,...saved.params};rows=period.films.map(f=>({...f,...f.defaults,...(saved.rows||[]).find(r=>r.id===f.id)}));
    for(const r of saved.rows||[])if(r.custom&&!rows.some(f=>f.id===r.id))rows.push({...r});
    periodNote.textContent=period.cutoff?`2026년: 9월까지 IMAX 흥행 1,256.6·매출 358.8·영업이익 105.6은 공시 확정값으로 고정합니다. 아래는 10~12월 신규 개봉작의 추정입니다. 분기 이월·재개봉은 기타 흥행에 넣으세요.`:`${year.value}년: 연간 전체를 추정합니다. 장비·비용 초기값은 2025년 공시 규모를 유지한 가정입니다. 2025년 실제 IMAX 흥행 1,280.0·매출 410.2·영업이익 84.2와 비교하세요.`;
    periodNote.append(make('small',`라인업 확인 ${period.slate_fetched}${period.slate_ok?'':' · 최근 원문 갱신 실패, 이전 자료'} · 공시 기준 검토 ${doc.reviewed} · 북미 일정은 글로벌 상영기간과 다를 수 있으며 공개 목록은 불완전합니다.`));
    paramInputs=[];residualHolder.replaceChildren();parameter(residualHolder,'기타·이월·미선택 작품 IMAX 흥행', 'residual',period.cutoff?'초기 221.1: 2025 Q4 전체 333.1 − Avatar 연내 112.0을 가져온 가정. 선택 작품과 중복되지 않게 수정하세요.':'초기 732.0: 2025 전체 1,280.0 − 상위 5편 548.0. 선택 작품 이외의 잔여 가정으로 수정하세요.');
    inputsGrid.replaceChildren();
    for(const [label,k] of [['DMR 실효 요율 %','dmr_pct'],['JRSA 흥행 비중 %','jrsa_share_pct'],['JRSA 실현 임대율 %','jrsa_rate_pct'],['기타 콘텐츠 매출','other_content'],['장비 판매 매출','system_sales'],['유지보수 매출','maintenance'],['금융수익','finance'],['기타 사업 매출','other'],['콘텐츠 매출총이익률 %','content_margin_pct'],['기술 매출총이익률 %','technology_margin_pct'],['기타 매출총이익률 %','other_margin_pct'],['영업비용 합계','opex']])parameter(inputsGrid,label,k);
    valueInputs.replaceChildren();for(const [label,k] of [['EV/영업이익 배수','multiple'],['차입금 장부가','debt'],['현금','cash'],['비지배지분 가치','nci'],['발행주식수 (백만 주)','shares'],['비교 주가 (USD·선택)','price']])parameter(valueInputs,label,k);
    caseInput.replaceChildren();for(const [label,k] of [['오디세이 DMR 실효율 %','odyssey_dmr_pct'],['오디세이 JRSA 흥행 비중 %','odyssey_jrsa_share_pct'],['오디세이 JRSA 실현 임대율 %','odyssey_jrsa_rate_pct'],['오디세이 콘텐츠 매출총이익률 %','odyssey_content_margin_pct'],['오디세이 기술 매출총이익률 %','odyssey_technology_margin_pct']])parameter(caseInput,label,k);
    parameter(caseInput,'오디세이 추가 영업비용 가정','odyssey_extra_cost','초기 0.0은 추가 비용을 차감하지 않는 가정이며, 실제 비용이 0이라는 뜻이 아닙니다.');
    drawRows();update();status.textContent='가정은 이 브라우저에 저장됩니다. CSV로 보관할 수 있습니다.';
  }
  year.addEventListener('change',loadYear);reset.addEventListener('click',()=>{delete stored[year.value];loadYear();save();});
  book.addEventListener('click',()=>{params.nci=Number((facts.balance_2026_09_30.nci_equity_book+facts.balance_2026_09_30.nci_redeemable_book).toFixed(3));params.nci_book_proxy=true;for(const [input,k] of paramInputs)if(k==='nci')input.value=params.nci;update();save();});
  add.addEventListener('click',()=>{const n=rows.filter(r=>r.custom).length+1;rows.push({id:`custom:${Date.now()}:${n}`,title:`직접 추가 ${n}`,custom:true,include:true,worldwide:null,imax_pct:10,in_year_pct:100,direct_imax:null});drawRows();rowViews.at(-1).tr.querySelector('input[type=text]').focus();update();save();});
  csv.addEventListener('click',()=>{const e=annualEstimate(period,rows,params),records=[['IMAX 시나리오',year.value,'공시 검토',doc.reviewed],['분석 범위',period.cutoff?'확정 1~3분기 + 추정 4분기':'연간 추정'],['구분','값','단위/범위'],...Object.entries(params).map(([k,v])=>[k,v,percentKeys.has(k)?'%':'USD 백만 / 주가 USD / 주식수 백만 주 / 배수']),[],['작품','반영','세계 흥행 가정','IMAX 비중 %','연내 반영 %','IMAX 전체 런 직접 입력','연내 IMAX 흥행','참고작','참고작 세계 누적','원문'],...rows.map(r=>[r.title,r.include?'예':'아니오',r.worldwide,r.imax_pct,r.in_year_pct,r.direct_imax,filmEstimate(r).gbo,r.comparable?.title,r.comparable?.worldwide,r.url||'']),[],['계산 완료',e.complete],...['gbo','revenue','gross','profit'].map(k=>['연간 '+k,e.total?.[k]]),['EV',e.ev],['비지배지분 차감 주주가치',e.equity],['가정상 주당가치 USD',e.value],['주의','입력 예시는 전망이 아니며 작품별 실제 수취액·이익은 미공개']];download(`IMAX-${year.value}-scenario.csv`,records.map(r=>r.map(csvEscape).join(',')).join('\r\n'),'text/csv;charset=utf-8');});
  loadYear();return root;
}

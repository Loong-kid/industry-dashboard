const STATUS={listed:'상장',unlisted:'비상장',delisted:'상장폐지',review:'법인 확인 중'};
const MARKETS={KQ:'코스닥',KS:'코스피',T:'도쿄',TW:'대만 TWSE',TWO:'대만 TPEx',AS:'암스테르담',DE:'독일',SS:'상하이',SZ:'선전',ST:'스톡홀름',KL:'말레이시아'};
const REFERENCE=new Set(['lumentum','coherent']);
const nameOrder=new Intl.Collator('ko',{numeric:true,sensitivity:'base'});
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!=null)el.textContent=text;if(cls)el.className=cls;return el;};
const format=value=>Number.isFinite(value)?value.toLocaleString('ko-KR',{maximumFractionDigits:2}):'—';
const routeFor=tab=>`#/semicon/materials/${encodeURIComponent(tab.category)}/${encodeURIComponent(tab.route||tab.id)}`;

export function buildDirectory(industry,index){
 const categories=(industry?.material_categories||[]).filter(c=>c.id!=='overview');
 const categoryMap=new Map(categories.map(c=>[c.id,c]));
 const tabs=new Map((industry?.tabs||[]).filter(t=>categoryMap.has(t.category)).map(t=>[t.id,t]));
 const references=new Map();
 const add=(id,tab,target)=>{
  if(!id||!tabs.has(tab))return;
  if(!references.has(id))references.set(id,new Map());
  const destinations=references.get(id);
  if(!destinations.has(tab)||(target&&!target.startsWith('sv-')))destinations.set(tab,target||'sv-'+id);
 };
 for(const section of industry?.sections||[]){
  if(!tabs.has(section.tab))continue;
  if(section.valuation_company)add(section.valuation_company,section.tab,section.anchor||'financial-'+section.valuation_company);
  for(const id of section.valuation_companies||[])add(id,section.tab);
  for(const company of section.companies||[])if(company.valuation_company)add(company.valuation_company,section.tab,'sv-'+company.valuation_company);
 }
 const indexed=new Map((index?.companies||[]).map(c=>[c.id,c]));
 const redundant=(id,ids)=>(id==='equipment_summary'&&ids.some(t=>t!==id&&tabs.get(t).category==='equipment'))||(id==='osat_summary'&&ids.some(t=>t==='osat_korea'||t==='osat_global'));
 const companies=Array.from(references,([id,destinations])=>{
  const source=indexed.get(id)||{id,name:id,status:'review',note:'주가 목록에 기업 정보가 아직 없어 확인이 필요합니다.'};
  const ids=Array.from(destinations.keys());
  const areas=ids.filter(tab=>!redundant(tab,ids)).map(tab=>{
   const item=tabs.get(tab),category=categoryMap.get(item.category);
   return {id:tab,name:item.name,category:item.category,categoryName:category.name,route:routeFor(item),target:destinations.get(tab)};
  });
  const listed=source.status==='listed';
  const suffix=source.symbol?.split('.').at(-1);
  const domestic=listed&&(Boolean(source.naver_code)||suffix==='KS'||suffix==='KQ');
  return {...source,id,areas,categories:Array.from(new Set(areas.map(a=>a.category))),market:listed?(MARKETS[suffix]||(source.symbol?.includes('.')?'해외 시장':'미국')):STATUS[source.status]||'확인 중',
   listing:listed?(domestic?'domestic':'foreign'):'other',reference:REFERENCE.has(id),
   price:listed?source.price:null,per:listed?source.per:null,pbr:listed?source.pbr:null};
 }).sort((a,b)=>nameOrder.compare(a.name,b.name));
 const topics=Array.from(tabs.values()).filter(t=>!['equipment_summary','osat_summary'].includes(t.id)).map(tab=>({
  ...tab,route:routeFor(tab),label:categoryMap.get(tab.category).name+' · '+tab.name,
  count:companies.filter(c=>c.areas.some(a=>a.id===tab.id)).length
 }));
 return {companies,topics,categories:categories.map(c=>({...c,count:companies.filter(company=>company.categories.includes(c.id)).length})),
  counts:{all:companies.length,domestic:companies.filter(c=>c.listing==='domestic').length,foreign:companies.filter(c=>c.listing==='foreign').length,other:companies.filter(c=>c.listing==='other').length}};
}

export function filterCompanies(companies,{query='',category='all',topic='all',listing='all',status='all',sort='name',ascending=true}={}){
 const words=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
 return companies.filter(c=>(category==='all'||c.categories.includes(category))&&(topic==='all'||c.areas.some(a=>a.id===topic))
  &&(listing==='all'||c.listing===listing)&&(status==='all'||c.status===status)
  &&words.every(word=>[c.name,c.symbol,c.id,c.note,c.market,...c.areas.map(a=>a.categoryName+' '+a.name)].filter(Boolean).join(' ').toLocaleLowerCase().includes(word)))
  .sort((a,b)=>{
   if(sort==='name')return nameOrder.compare(a.name,b.name)*(ascending?1:-1);
   const x=a[sort],y=b[sort];if(!Number.isFinite(x))return Number.isFinite(y)?1:nameOrder.compare(a.name,b.name);if(!Number.isFinite(y))return -1;
   return (x-y)*(ascending?1:-1)||nameOrder.compare(a.name,b.name);
  });
}

let cancelJump=null;
function watchDestination(area,event){
 if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
 cancelJump?.();
 const initial=location.hash,container=document.getElementById('content');if(!container)return;
 let timer,observer;
 const done=()=>{observer?.disconnect();clearTimeout(timer);window.removeEventListener('hashchange',check);cancelJump=null;};
 const check=()=>{
  if(location.hash!==area.route){if(location.hash!==initial)done();return;}
  const target=document.getElementById(area.target);
  if(target&&!document.querySelector('.page-loading')){done();requestAnimationFrame(()=>target.isConnected&&target.scrollIntoView({block:'start',behavior:'auto'}));}
 };
 observer=new MutationObserver(check);observer.observe(container,{childList:true,subtree:true});timer=setTimeout(done,20000);window.addEventListener('hashchange',check);cancelJump=done;
}

export function renderMaterialsOverview(index,{industry}={}){
 const model=buildDirectory(industry,index),root=node('section',null,'materials-overview');root.setAttribute('aria-label','소부장 전체 요약과 등재 기업');
 const stats=node('div',null,'mo-stats');
 for(const [key,label] of [['all','등록 항목'],['domestic','국내 상장'],['foreign','해외 상장'],['other','비상장·상폐·검토']]){
  const stat=node('div',null,'mo-stat');stat.append(node('strong',String(model.counts[key])),node('span',label));stats.append(stat);
 }
 root.append(stats,node('p','같은 기업이 여러 분야에 있어도 전체 목록에는 한 번만 표시합니다. 분야별 기업 수에는 중복 소속을 포함합니다.','mo-note'));
 const preferences={query:'',category:'all',topic:'all',listing:'all',status:'all',sort:'name',ascending:true};
 const categories=node('div',null,'mo-categories');categories.setAttribute('aria-label','기업 분야 필터');
 const categoryButtons=[];
 for(const category of [{id:'all',name:'전체',count:model.counts.all},...model.categories]){
  const button=node('button',category.name+' '+category.count);button.type='button';button.dataset.category=category.id;
  button.addEventListener('click',()=>{preferences.category=category.id;preferences.topic='all';populateTopics();refresh();});categoryButtons.push(button);categories.append(button);
 }
 root.append(categories);
 const controls=node('div',null,'mo-filters');
 const search=node('input');search.type='search';search.placeholder='기업명 · 종목 · 등록 분야 검색';search.setAttribute('aria-label','소부장 기업 검색');
 const label=node('label','기업 검색');label.append(search);controls.append(label);
 const select=(caption,aria,options)=>{const field=node('label',caption),input=node('select');input.setAttribute('aria-label',aria);for(const [value,text] of options){const option=node('option',text);option.value=value;input.append(option);}field.append(input);controls.append(field);return input;};
 const topic=select('세부 분야','소부장 세부 분야',[]);
 const listing=select('상장 시장','소부장 상장 시장',[['all','전체 시장'],['domestic','국내 상장'],['foreign','해외 상장'],['other','비상장·상폐·검토']]);
 const status=select('등재 상태','소부장 등재 상태',[['all','전체 상태'],...Object.entries(STATUS)]);
 root.append(controls);
 const tools=node('div',null,'mo-result-tools'),result=node('p',null,'mo-result');result.setAttribute('aria-live','polite');
 const reset=node('button','필터 초기화');reset.type='button';tools.append(result,reset);root.append(tools);
 const wrap=node('div',null,'mo-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','소부장 등재 기업 목록');
 const table=node('table'),thead=node('thead'),head=node('tr'),tbody=node('tbody'),sortHeaders=new Map();
 for(const [text,key] of [['기업','name'],['등록 분야·이동',null],['시장·종목',null],['주가',null],['PER(TTM)','per'],['PBR','pbr'],['자료 범위',null]]){
  const th=node('th');th.scope='col';if(key){const button=node('button',text);button.type='button';button.setAttribute('aria-label',text);button.addEventListener('click',()=>{preferences.ascending=preferences.sort===key?!preferences.ascending:true;preferences.sort=key;refresh();});th.append(button);sortHeaders.set(key,th);}else th.textContent=text;head.append(th);
 }
 thead.append(head);table.append(thead,tbody);wrap.append(table);root.append(wrap);
 root.append(node('p',`주가 수집 확인 ${index?.checked||'—'} · PER은 실적 TTM, PBR은 공시 BPS 기준이며 0 이하·미확인 값은 N/M입니다. 주가·배수는 상장 법인 전체 기준으로, 세부탭의 사업부·추정 실적과 범위가 다를 수 있습니다.`,'mo-note'));
 root.append(node('p','MOCVD의 Lumentum·Coherent는 수요처·참고 기업입니다. 정전척처럼 무역 지표만 있고 기업 카드가 없는 분야는 기업 수에 포함하지 않습니다.','mo-note'));
 function populateTopics(){topic.replaceChildren();const all=node('option','전체 세부 분야');all.value='all';topic.append(all);for(const area of model.topics.filter(t=>preferences.category==='all'||t.category===preferences.category)){const option=node('option',`${area.label} (${area.count})`);option.value=area.id;topic.append(option);}topic.value=preferences.topic;}
 function companyLink(c,area,text){const link=node('a',text);link.href=area.route;link.dataset.companyOpen=c.id;link.addEventListener('click',event=>watchDestination(area,event));return link;}
 function refresh(){
  for(const button of categoryButtons)button.setAttribute('aria-pressed',String(button.dataset.category===preferences.category));
  for(const [key,th] of sortHeaders)th.setAttribute('aria-sort',preferences.sort===key?(preferences.ascending?'ascending':'descending'):'none');
  const rows=filterCompanies(model.companies,preferences);result.textContent=`${rows.length} / ${model.counts.all}개 표시`;tbody.replaceChildren();
  for(const company of rows){
   const tr=node('tr');tr.dataset.companyId=company.id;
   const cell=(text,cls)=>{const td=node('td',text,cls);tr.append(td);return td;};
   const name=cell(null,'mo-company');name.append(company.areas[0]?companyLink(company,company.areas[0],company.name):node('span',company.name));
   if(company.reference)name.append(node('small','수요처·참고','mo-badge'));
   if(company.status!=='listed')name.append(node('small',STATUS[company.status]||'확인 중','mo-badge'));
   const areas=cell(null,'mo-areas');for(const area of company.areas)areas.append(companyLink(company,area,area.categoryName+' · '+area.name));
   const market=cell(company.market,'mo-market');market.append(node('small',company.symbol||'종목 없음'));
   const price=cell(format(company.price),'mo-number');price.append(node('small',Number.isFinite(company.price)?company.currency+' · '+company.price_date:'—'));
   for(const key of ['per','pbr'])cell(Number.isFinite(company[key])?format(company[key])+'배':company.status==='listed'?'N/M':'—','mo-number');
   const scope=cell(null,'mo-scope'),details=node('details');details.append(node('summary','범위·기준'));
   details.append(node('p',company.note||'선택한 분야에서 전사·사업부·추정 실적의 범위를 확인해 주세요.'));
   if(company.status==='listed')details.append(node('small',`EPS ${company.eps_date||'미확인'} · BPS ${company.bps_date||'미확인'}`),node('small',company.ok?'최근 주가 수집 정상':'최근 수집 상태 확인 필요'));
   scope.append(details);tbody.append(tr);
  }
  if(!rows.length){const tr=node('tr'),td=node('td',null,'mo-empty');td.colSpan=7;td.append(node('p','조건에 맞는 등재 기업이 없습니다.'));
   const selected=model.topics.find(t=>t.id===preferences.topic);if(selected){const link=node('a',selected.name+' 자료 보기');link.href=selected.route;td.append(link);}tr.append(td);tbody.append(tr);}
 }
 search.addEventListener('input',()=>{preferences.query=search.value;refresh();});
 for(const [control,key] of [[topic,'topic'],[listing,'listing'],[status,'status']])control.addEventListener('change',()=>{preferences[key]=control.value;refresh();});
 reset.addEventListener('click',()=>{Object.assign(preferences,{query:'',category:'all',topic:'all',listing:'all',status:'all',sort:'name',ascending:true});search.value='';listing.value='all';status.value='all';populateTopics();refresh();});
 populateTopics();refresh();return root;
}

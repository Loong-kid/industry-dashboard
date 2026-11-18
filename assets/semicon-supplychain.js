const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const number=v=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:1}):'—';
const link=(url,label)=>{const a=node('a',label);try{const u=new URL(url);if(u.protocol==='https:'){a.href=u.href;a.target='_blank';a.rel='noopener';}}catch{}return a;};
export function companiesForTab(doc,tab){return (doc?.companies||[]).filter(c=>c.tabs.includes(tab)||tab==='equipment_summary'&&c.tabs.some(t=>t.startsWith('equipment_')));}
export function renderSupplychain(doc,{tab}={}){
 const root=node('section',null,'supplychain-overview');root.setAttribute('aria-label','국내 소부장 기업 사업·실적 비교');if(!doc)return root;
 const companies=companiesForTab(doc,tab);
 root.append(node('p',`${companies.length}개 추가 기업 · 금액 KRW 백만 · 회사 전체 공시. 아래 차트에서 분기·연간을 전환할 수 있습니다.`));
 const wrap=node('div',null,'supplychain-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','국내 소부장 기업 비교 표');
 const table=node('table'),head=node('thead'),hr=node('tr');
 for(const label of ['기업·공정','실적 범위 / 확보 기간','최근 분기 매출','영업이익','영업이익률','현금 CAPEX','사업 구성·출처']){const th=node('th',label);th.scope='col';hr.append(th);}head.append(hr);const body=node('tbody');
 for(const c of companies){const tr=node('tr');tr.dataset.company=c.id;const td=(text)=>{const e=node('td',text);tr.append(e);return e;};
  const name=td(null);name.append(link(c.source_url,c.name),node('small',c.ticker),node('small',c.role));
  const scope=td(null);scope.append(node('span',c.scope),node('small',`연간 ${c.annual_start} · 분기 ${c.quarter_start}부터`),node('small',c.note));
  for(const key of ['revenue','profit']){const cell=td(number(c.latest[key]));cell.append(node('small',c.latest.date));}
  td(c.latest.revenue>0?number(c.latest.profit/c.latest.revenue*100)+'%':'—');
  const cash=td(number(c.latest_capex?.capex));if(c.latest_capex)cash.append(node('small',c.latest_capex.date));
  const detail=td(null),more=node('details');more.append(node('summary','사업 구성·원문'));
  const mix=c.business_mix;
  if(mix){more.append(node('p',`${mix.period_label} · ${mix.scope}`));for(const r of mix.rows)more.append(node('p',`${r.label}: ${r.amount==null?'':number(r.amount)+' '+(mix.unit||'KRW 백만')}${r.share_pct==null?'':' · '+number(r.share_pct)+'%'}`));if(mix.note)more.append(node('small',mix.note));more.append(node('small',`사업 구성 표 확인 ${mix.reviewed} · 재무 갱신과 별도 검토`),link(mix.source_url,'제품·사업 매출 공시'));}
  else more.append(node('p','제품별 수치가 분리 공시됐는지 검토 중입니다. 회사 전체 매출을 특정 제품 매출로 추정하지 않습니다.'));
  more.append(link(c.latest.refs.revenue.url,'최근 분기 재무 공시'),node('small',`원문 확인 ${c.fetched}${c.ok?'':' · 최근 조회 실패, 마지막 성공 이력'}`));detail.append(more);body.append(tr);
 }
 table.append(head,body);wrap.append(table);root.append(wrap);return root;
}

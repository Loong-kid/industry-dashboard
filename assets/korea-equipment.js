const names={equipment_frontend:'전공정',equipment_packaging:'패키징·후공정',equipment_inspection:'검사·계측',equipment_testing:'테스트'};
function node(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;}
function external(label,url){const a=node('a','',label);a.href=url;a.target='_blank';a.rel='noopener';return a;}
export function renderGuide(doc,tab){
 const selected=doc.companies.filter(c=>tab==='equipment_summary'||c.tabs.includes(tab));if(!selected.length)return null;
 const root=node('details','ke-guide'),summary=node('summary','',`국내 장비 ${selected.length}개사 · 분류·선정 기준`);root.append(summary);
 root.append(node('p','ke-note','기존 한미반도체에 시가총액 상위권 장비사 10개를 추가했습니다. 원통화 KRW 백만으로 분기·연간 실적을 표시합니다. 아래 시가총액은 선정 시점의 제공자 표기이며 실시간 순위가 아닙니다.'));
 const wrap=node('div','ke-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','국내 반도체 장비 분류와 선정 시점 시가총액');
 const table=node('table','ke-table'),head=node('thead'),hr=node('tr');
 for(const text of ['기업','장비 분류','주력 공정·제품','선정 시점 시총','시총 표기 시점','원문']){const th=node('th','',text);th.scope='col';hr.append(th);}head.append(hr);table.append(head);
 const body=node('tbody');
 for(const c of selected){
  const tr=node('tr'),firm=node('td');firm.append(node('strong','',c.name),node('small','',c.ticker+(c.existing?' · 기존 등록':'')));
  const role=node('td','ke-role'),text=node('span','',c.role);text.title=c.role+' · '+c.note;role.append(text);
  const cap=node('td','ke-cap');cap.append(external(c.market_cap_label,c.market_source_url));
  const source=node('td');source.append(external('제품·사업',c.source_url));
  tr.append(firm,node('td','',c.tabs.map(t=>names[t]).join(' / ')),role,cap,node('td','ke-date',c.traded_at.slice(0,16).replace('T',' ')),source);body.append(tr);
 }
 table.append(body);wrap.append(table);root.append(wrap);
 for(const text of doc.scope_notes)root.append(node('p','ke-note',text));
 root.append(node('p','ke-note',doc.selection_basis));return root;
}

const GROUPS={platforms:'드론·비행체',components:'부품·FPV',expanded:'확장 방산·자율시스템'};
function element(tag,className,text){const e=document.createElement(tag);if(className)e.className=className;if(text!=null)e.textContent=text;return e;}
function link(label,url){const e=element('a','',label);e.href=url;e.target='_blank';e.rel='noopener';return e;}

export function renderOverview(doc){
 const root=element('div','dr-overview');
 if(!doc){root.append(element('p','card-empty','드론 추적 대상 자료를 불러오지 못했습니다.'));return root;}
 root.append(element('h2','dr-heading','드론 테마의 범위부터 확인'),element('p','ir-scope-note','비행체·핵심 부품 업체와 사업 범위가 넓어진 방산 업체를 구분합니다. 아래 재무는 각 회사의 연결 실적으로, 드론 단독 시장 규모로 합산하지 않습니다.'));
 const funds=element('div','dr-funds');
 for(const etf of doc.etfs){
  const card=element('article','card dr-fund');
  card.append(element('h3','',etf.ticker),link(etf.name,etf.source_url),element('p','',etf.scope),element('p','dr-note',etf.note),element('p','dr-note',`가격 이력 시작 ${etf.inception} · 총보수 연 ${etf.expense_ratio.toFixed(2)}% · 확인 ${doc.reviewed}`));funds.append(card);
 }
 root.append(funds,element('h2','dr-heading',`실적 추적 ${doc.companies.length}개사`));
 const wrap=element('div','dr-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','드론 기업별 사업 범위와 실적 · 가로 스크롤');
 const table=element('table','dr-table');const head=element('thead'),hr=element('tr');
 for(const name of ['기업','분류','연결 매출 범위','최근 실적','분기 이력','출처']){const th=element('th','',name);th.scope='col';hr.append(th);}head.append(hr);table.append(head);
 const body=element('tbody');
 for(const c of doc.companies){
  const row=element('tr'),name=element('td'),a=element('a','',c.name);a.href='#/drone/'+c.group;name.append(a,element('small','',c.ticker));
  const scope=element('td','dr-scope'),memo=element('span','',c.scope);memo.title=c.scope+' '+c.note;scope.append(memo);
  const source=element('td');source.append(link('기업 원문',c.source_url));
  row.append(name,element('td','',GROUPS[c.group]),scope,element('td','dr-date',c.financial_end),element('td','dr-count',c.quarters+'개'),source);
  if(!c.ok)row.title='최근 조회 실패 · 마지막 성공 공시를 표시합니다.';
  body.append(row);
 }
 table.append(body);wrap.append(table);root.append(wrap);
 const details=element('details','dr-scope-details');details.append(element('summary','','포함·제외 기준과 과거 이력'));
 details.append(element('p','','드론을 주력으로 하는 미국 상장 운영기업 중 공개 재무와 가격 이력을 함께 확인한 업체부터 등록했습니다. 다른 국가의 상장사까지 포함한 전 세계 기업 수를 뜻하지 않습니다.'));
 for(const item of doc.exclusions){const p=element('p');p.append(element('strong','',item.name+' '),document.createTextNode(item.reason+' '),link('원문',item.url));details.append(p);}
 details.append(element('p','','Red Cat과 AgEagle의 드론 전환 전 기업·티커 이력은 가격과 실적에서 제외했습니다. 최근 인수에 따른 사업 확대와 과거 회계연도 변경은 각 재무 카드의 집계 기준에서 확인합니다.'));
 root.append(details);return root;
}

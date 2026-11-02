function node(tag,className,text){const e=document.createElement(tag);if(className)e.className=className;if(text!=null)e.textContent=text;return e;}
export function renderOverview(doc){
 const root=node('div','xr-overview');
 root.append(node('h2','','VR/AR 기업 추적'),node('p','ir-scope-note','국내 디스플레이 반도체와 해외 기기·광학 업체 6개사를 추적합니다. 실적은 회사 전체 기준이며 Meta의 Reality Labs 사업부는 별도로 표시합니다.'));
 const wrap=node('div','xr-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','VR/AR 기업·사업 범위와 최근 실적');
 const table=node('table','xr-table'),head=node('thead'),hr=node('tr');
 for(const text of ['기업','핵심 분야','실적 범위','최근 분기','공시 이력','출처']){const th=node('th','',text);th.scope='col';hr.append(th);}head.append(hr);table.append(head);
 const body=node('tbody');
 for(const c of doc.companies){
  const row=node('tr'),name=node('td'),a=node('a','',c.name);a.href=`#/vrar/${c.group}`;name.append(a,node('small','',c.ticker));
  const scope=node('td','xr-scope'),text=node('span','',c.scope);text.title=c.scope+' '+c.note;scope.append(text);
  const source=node('td'),link=node('a','','공식 자료');link.href=c.source_url;link.target='_blank';link.rel='noopener';source.append(link);
  row.append(name,node('td','',c.role),scope,node('td','xr-date',c.financial_end),node('td','',`${c.quarters}분기 · 연간 ${c.annual_start.slice(0,4)}~`),source);
  if(!c.ok)row.title='최근 원문 일부 검토 필요 · 확인된 이력 유지';body.append(row);
 }
 table.append(body);wrap.append(table);root.append(wrap);
 const details=node('details','xr-watchlist');details.append(node('summary','','추후 추적 대상·선정 기준'));
 details.append(node('p','',doc.selection_basis));
 for(const item of doc.watchlist){const p=node('p'),link=node('a','',item.name);link.href=item.url;link.target='_blank';link.rel='noopener';p.append(link,document.createTextNode(' — '+item.reason));details.append(p);}
 root.append(details);return root;
}

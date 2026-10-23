/* Wafer macro evidence: original charts retain unlabelled axes and provenance. */
function renderWaferGuide() {
  const section = document.createElement('section');
  section.className = 'mocvd-guide';
  section.setAttribute('aria-label', '실리콘 웨이퍼 지표 읽는 순서');
  section.innerHTML = `<h2>출하에서 재고·투자까지</h2>
    <ol class="mocvd-cycle">
      <li><strong>글로벌 출하</strong><span>웨이퍼 구매 수요·사이클</span></li>
      <li><strong>고객 재고</strong><span>구매량과 생산 투입의 차이</span></li>
      <li><strong>공급사 실적</strong><span>매출·수익성·월별 변화</span></li>
      <li><strong>공급 확대</strong><span>투자·인증·가동 단계</span></li>
    </ol>
    <p>글로벌 출하는 웨이퍼 제조사가 고객에게 보낸 면적입니다. 팹의 실제 생산 투입과 다르므로 고객 재고를 함께 읽습니다. SUMCO 재고는 회사 추정이고 완성된 메모리 칩 재고가 아닙니다.</p>
    <details><summary>기간·투자액·갱신 기준</summary>
      <p>연간 실적은2014년부터, 분기는 확보한 구간만 제공합니다. 카드의 ‘연간 / 분기’ 버튼으로 전환하세요. GlobalWafers의2014~2015 CAPEX와 일부 과거 분기는 미확보이며 공백을 유지합니다.</p>
      <p>SUMCO의 검수 기준 투자액, Siltronic의 발생 기준 투자액, 현금 CAPEX를 구분합니다. 회사별 통화가 다르며 매출 합계로 시장 규모·점유율을 만들지 않습니다. 신에츠 전자재료는 웨이퍼 외 사업을 포함한 참고 지표입니다.</p>
      <p>GlobalWafers 월 매출은 매일 새 공표를 확인합니다. SEMI 통계·기업 재무제표·재고 원문·증설 기록은 새 자료 검토 후 갱신합니다. 수치 축이 없는 원문 그래프는 절대값으로 복원하지 않습니다.</p>
    </details>`;
  return section;
}

function renderWaferEvidence(doc) {
  const card = document.createElement('section');
  card.className = 'card wafer-evidence';
  const title = document.createElement('h3');
  title.className = 'card-name'; title.textContent = doc.name;
  const note = document.createElement('p');
  note.className = 'ir-scope-note'; note.textContent = doc.description;
  const controls = document.createElement('div');
  controls.className = 'series-view-controls'; controls.setAttribute('role', 'group');
  controls.setAttribute('aria-label', 'SUMCO 원문 그래프 선택');
  card.append(title, note, controls);
  const figures = doc.figures.map((item, index) => {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = item.title;
    const figure = document.createElement('figure');
    const imageLink = document.createElement('a');
    imageLink.href = item.image; imageLink.target = '_blank'; imageLink.rel = 'noopener';
    imageLink.setAttribute('aria-label', `${item.title} 원문 이미지 확대`);
    const image = document.createElement('img');
    image.src = item.image; image.alt = `${item.title} · SUMCO 2026년 2분기 설명자료 ${item.pdf_page}쪽`;
    image.loading = 'lazy'; imageLink.appendChild(image);
    const caption = document.createElement('figcaption'); caption.textContent = item.caption;
    const source = document.createElement('p'); source.className = 'card-foot';
    const link = document.createElement('a');
    link.href = `${item.url}#page=${item.pdf_page}`; link.target = '_blank'; link.rel = 'noopener';
    link.textContent = `공식 원문 PDF ${item.pdf_page}쪽`;
    source.append(`자료 기준 ${item.date} · 공표 ${item.published} · `, link, ' · 이미지를 누르면 확대');
    figure.append(imageLink, caption, source); card.appendChild(figure); controls.appendChild(button);
    button.addEventListener('click', () => select(index));
    return {button, figure};
  });
  function select(index) {
    figures.forEach((item, i) => {
      item.figure.hidden = i !== index;
      item.button.classList.toggle('active', i === index);
      item.button.setAttribute('aria-pressed', String(i === index));
    });
  }
  select(1);
  return card;
}

function renderWaferEvents(doc) {
  const card = renderMOCVDTable(doc);
  card.querySelector('input').placeholder = '300mm, 증설, 인증…';
  return card;
}

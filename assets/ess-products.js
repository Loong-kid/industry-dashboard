/* Manufacturer-authored ESS specifications. Values retain their measurement scopes. */
"use strict";

function renderESSProducts(doc) {
  const card = document.createElement("div");
  card.className = "card ess-products";
  if (!doc) return card;
  card.dataset.productRegister = doc.id;
  const esc = escapeHtml;
  const number = value => Number(value).toLocaleString("ko-KR", {maximumFractionDigits: 3});
  const fact = (item, divisor = 1) => {
    if (!item) return '<span class="factory-unknown">미공개</span>';
    const prefix = {approx: "약 ", up_to: "≤ ", greater_than: "> "}[item.qualifier] || "";
    return `<strong>${esc(prefix)}${number(item.min / divisor)}${item.qualifier === "range" ? `~${number(item.max / divisor)}` : ""}</strong>`;
  };
  const refs = product => product.references.map(ref => {
    const source = doc.sources[ref.source];
    return `<a href="${esc(source.url)}#page=${ref.page}" target="_blank" rel="noopener">${esc(source.author)} PDF ${ref.page}쪽 ↗</a><small>${esc(ref.fields)}</small>`;
  }).join("");
  const products = Object.entries(doc.products);
  const companies = [...new Map(products.map(([, p]) => [p.company, p.company_name])).entries()];
  card.innerHTML = `<div class="card-name">${esc(doc.name)}</div>
    <p class="ir-scope-note">${esc(doc.description)} 검토일 ${esc(doc.reviewed)}.</p>
    <p class="product-basis-note">테슬라는 개별 Megapack 사양, Gridstack Pro는 배터리 외함 사양, Smartstack은 팩 옵션 사양을 표기합니다. 플루언스 수치는 제조사가 명시한 설계 추정치입니다.</p>
    <div class="factory-controls">
      <label>기업 <select aria-label="ESS 제품 기업"><option value="all">전체 기업</option>${companies.map(([id, name]) => `<option value="${esc(id)}">${esc(name)}</option>`).join("")}</select></label>
      <label>제품 <select aria-label="ESS 제품 모델"><option value="all">전체 제품</option>${products.map(([id, p]) => `<option value="${esc(id)}">${esc(p.name)}</option>`).join("")}</select></label>
      <span class="product-count" role="status" aria-live="polite"></span>
    </div>
    <div class="order-table-wrap" tabindex="0" role="region" aria-label="ESS 제품 사양 비교표 · 가로·세로 스크롤">
      <table><caption>MWh · MW · RTE % · mm · kg / 표 안에서 좌우·상하 스크롤해 전체 사양·원문 확인</caption><thead><tr>
        <th scope="col">기업 / 제품 구성</th><th scope="col">에너지 MWh<br>측정 범위</th><th scope="col">AC 유효출력 MW<br>전압 / 최대 전류</th><th scope="col">방전 시간 / 셀 CP-rate</th><th scope="col">충·방전 효율 RTE %<br>시험 조건</th><th scope="col">작동 환경 / IP</th><th scope="col">외형 / 중량<br>대상 범위</th><th scope="col">PCS·변압기 / 제어 구성</th><th scope="col">안전·보증 / 기술자료</th>
      </tr></thead><tbody></tbody></table>
    </div><p class="ir-scope-note">${esc(doc.note)}</p>`;
  const [companySelect, productSelect] = card.querySelectorAll("select");
  const draw = () => {
    const rows = doc.rows.filter(row => (companySelect.value === "all" || doc.products[row.product].company === companySelect.value)
      && (productSelect.value === "all" || row.product === productSelect.value));
    card.querySelector(".product-count").textContent = `${rows.length}개 제품 구성`;
    card.querySelector("tbody").innerHTML = rows.length ? rows.map(row => {
      const p = doc.products[row.product];
      const source = doc.sources[p.references[0].source];
      return `<tr data-product="${esc(row.id)}">
        <th scope="row"><small>${esc(p.company_name)}</small>${esc(p.name)}<small>${esc(row.variant)}</small><span class="product-rating ${esc(p.rating_status)}">${esc(p.rating_label)}</span><small>${esc(source.revision)}</small></th>
        <td>${fact(row.energy_kwh, 1000)}<small>${esc(p.capacity_basis)}</small></td>
        <td>${fact(row.ac_power_kw, 1000)}<small>${esc(row.power_basis)}</small>${row.ac_current_a ? `<div>최대 AC 전류 ${fact(row.ac_current_a)} A</div>` : ""}<small>${esc(p.electrical)}</small></td>
        <td>${row.duration_hours.length ? `${row.duration_hours.join(" · ")}시간` : "옵션별 미분리"}<small>${esc(row.duration_basis)}</small><small>${esc(row.cell_rate)}</small></td>
        <td>${fact(row.rte_percent)}<small>${esc(p.rte_basis)}</small></td>
        <td>${esc(p.environment)}<small>${esc(p.protection)}</small><small>${esc(p.cooling)}</small></td>
        <td>${esc(row.dimensions).replace(/\n/g, "<br>")}<small>${esc(row.mass)}</small><small>${esc(row.mass_basis)}</small></td>
        <td>${esc(p.architecture)}<small>${esc(p.controls)}</small></td>
        <td><details><summary>안전·보증·사양 조건</summary>${[
          ["인증·설계 규격", p.certifications], ["화재 시험", p.fire_testing], ["가용성", p.availability],
          ["응답 시간", p.response_time], ["보증", p.warranty], ["셀 정보", p.chemistry], ["사양 조건", p.extra], ["구성별 조건", row.extra]
        ].map(([label, text]) => `<p><b>${esc(label)}</b><br>${esc(text)}</p>`).join("")}</details><small>${esc(source.host_note)}</small>${refs(p)}</td>
      </tr>`;
    }).join("") : '<tr><td colspan="9">선택한 기업·제품 조합에 해당하는 사양이 없습니다.</td></tr>';
  };
  [companySelect, productSelect].forEach(select => select.addEventListener("change", draw));
  draw();
  return card;
}

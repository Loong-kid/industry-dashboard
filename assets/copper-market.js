/* Copper report concepts, independent of chart and mine data loading. */
"use strict";
function renderCopperMarketGuide() {
  const section = document.createElement("section");
  section.className = "card copper-market-guide";
  section.setAttribute("aria-label", "구리 보고서 읽는 법");
  section.innerHTML = `
    <div class="card-head"><div class="card-name">구리 보고서 읽는 법</div><div class="card-freq">개념·해석 검토 2026-10-09</div></div>
    <p class="copper-guide-intro">TC는 정광의 수급, 수입 프리미엄은 정련동을 구하는 비용, LME 워런트는 거래소 인도에 쓸 수 있는 재고의 상태를 보여줍니다.</p>
    <ol class="copper-chain" aria-label="구리 공급 단계">
      <li><strong>광산·선광</strong><span>원광에서 정광 생산</span></li>
      <li><strong>제련·정련</strong><span>정광 → 정련동 · TC/RC</span></li>
      <li><strong>수입·보세창고</strong><span>B/L·보세창고 프리미엄</span></li>
      <li><strong>거래소 창고</strong><span>등록·취소·실제 입출고</span></li>
    </ol>
    <p class="copper-guide-caption">대표적인 정광 경로입니다. 거래소 창고 입고는 선택 사항이며, SX-EW·재활용 등 다른 생산 경로도 있습니다.</p>
    <div class="copper-guide-topics">
      <details><summary><strong>LME 워런트 · 등록과 취소</strong><span>취소해도 출고 전에는 창고에 남습니다.</span></summary>
        <p>워런트는 LME 승인 창고의 특정 금속 물량에 대해 발행하는 창고증권입니다. 소유권 이전과 선물 실물 인도에 사용합니다.</p>
        <p><b>등록(Live / Open)</b>은 유효한 워런트가 붙어 LME 인도에 사용할 수 있는 물량입니다. 개인 소유자의 매도 의사와 창고 출고 절차가 필요하므로 ‘누구나 즉시 구매·반출 가능’과는 다릅니다.</p>
        <p><b>취소(Cancelled)</b>는 소유자가 워런트를 취소해 LME 인도 대상에서 뺀 물량입니다. 보통 반출을 준비하지만, 취소만으로 반출 일정이 확정되거나 실제 출고된 것은 아닙니다. 조건이 허용하면 재등록될 수도 있습니다.</p>
        <p class="copper-guide-formula">보고 총재고 = 등록 + 취소<br>취소 비중 = 취소 ÷ (등록 + 취소) × 100</p>
        <p>취소 비중 상승은 다른 조건이 같을 때 거래소 인도 가능 물량의 축소를 시사합니다. 총재고·실제 출고량·입고량·지역별 재고와 함께 봐야 합니다. 분모인 총재고가 줄어도 비중이 오르며, 창고 이동·금융·차익거래도 영향을 줍니다. 별도 off-warrant 재고는 이 총재고에 포함되지 않습니다.</p>
        <p><b>예시:</b> 총재고 100톤에서 등록 80·취소 20이었다가, 추가로 20톤의 워런트만 취소하면 등록 60·취소 40이 됩니다. 비중은 20% → 40%(+20%p)지만 총재고와 실물 위치는 그대로입니다. 이후 10톤이 실제 출고되어야 총재고가 90톤으로 줄어듭니다.</p>
        <p>보고서의 ‘등록(반출 가능)’은 ‘등록(선물 인도 가능)’으로, ‘취소(반출 예약)’은 ‘취소(인도 대상 제외·반출 준비)’로 읽는 편이 정확합니다.</p>
        <p class="copper-guide-sources"><a href="https://www.lme.com/sustainability-and-physical-markets/warehousing/lme-warrants" target="_blank" rel="noopener noreferrer">LME 워런트</a> · <a href="https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/stock-breakdown-report" target="_blank" rel="noopener noreferrer">LME 등록·취소·입출고 보고서</a></p>
      </details>
      <details><summary><strong>정광 제련수수료 · TC / RC</strong><span>구리 금속톤과 건조 정광톤은 다릅니다.</span></summary>
        <p><b>정광</b>은 광석을 선광해 구리 함량을 높인 원료이고, 아직 고순도 정련동이 아닙니다. <b>TC(Treatment Charge)</b>는 정광을 제련하는 대가이며 보통 USD/건조정광톤(dmt)으로 표시합니다. <b>RC(Refining Charge)</b>는 구리를 정련하는 대가이며 지급대상 구리의 cents/lb로 표시합니다.</p>
        <p class="copper-guide-formula">정광 정산액 ≈ 지급대상 금속가치 − TC × 건조 정광톤 − RC × 지급대상 구리량 + 부산물 대가 − 기타 공제</p>
        <p><b>예시:</b> 10건조톤 정광의 TC가 +60달러/dmt면 TC 항목으로 600달러를 공제합니다. TC가 −50달러/dmt면 음수 공제를 빼므로 같은 금속가치 기준 정산액에 500달러가 가산됩니다. 실제 RC·금은 대가·불순물 공제 등은 계약별로 다릅니다.</p>
        <p>정광이 풍부하고 제련소가 적으면 광산이 더 높은 TC를 수용하기 쉽습니다. 정광이 부족하거나 제련능력이 과잉이면 제련소가 원료를 확보하려 경쟁해 TC가 낮아집니다. 음수 TC는 구리 가격 자체가 음수라는 뜻이 아니며, 제련소의 총손익도 장기계약·황산·귀금속·회수율·에너지 비용 등에 좌우됩니다.</p>
        <p>현물 주간 TC, 연간 장기계약 TC, 제련소 구매 TC와 트레이더 구매 TC를 구분하세요. ‘TC 50 / RC 5’ 같은 관행이 있어도 단위가 다르고 계약마다 달라 RC를 TC에서 자동 계산하지 않습니다.</p>
        <p class="copper-guide-sources"><a href="https://news.metal.com/en/newscontent/100979742-smm-notice-launch-of-smm-copper-concentrate-index" target="_blank" rel="noopener noreferrer">SMM TC 지수 방법론</a> · <a href="https://www-old.metal.com/Copper/201910240001" target="_blank" rel="noopener noreferrer">SMM 공식 주간 TC</a></p>
      </details>
      <details><summary><strong>선하증권 · B/L 프리미엄</strong><span>정련동 수입 계약에 붙는 추가 가격입니다.</span></summary>
        <p><b>B/L(Bill of Lading, 선하증권)</b>은 선사가 화물을 인수·선적했음을 증명하는 운송서류입니다. 구리 시장에서는 정련동을 선하증권 조건으로 거래하는 물량의 프리미엄을 봅니다. 운송 중·도착 예정 물량이 많지만, 도착 후에도 B/L로 거래될 수 있습니다.</p>
        <p>수입 구리 가격은 계약의 LME 기준가격에 해당 프리미엄을 더해 정합니다. SMM의 양산 B/L 프리미엄은 CIF 상하이 조건의 LME 등록 Grade A 브랜드를 대상으로 합니다. 프리미엄은 구리 전체 가격이나 정광 TC가 아닙니다.</p>
        <p>프리미엄 상승은 수입 물량에 더 높은 추가 가격을 지불하는 상황을 뜻합니다. 중국 수요뿐 아니라 운송·재고·수입 차익·환율·금융·도착일도 영향을 줍니다. 각 제공처의 품목·브랜드·가격 산정기간(QP) 기준을 먼저 맞춰야 합니다.</p>
        <p class="copper-guide-sources"><a href="https://data.metal.com/data/copper/cu_yangshan_copper_premium_bill_of_lading" target="_blank" rel="noopener noreferrer">SMM 양산 B/L 시리즈</a></p>
      </details>
      <details><summary><strong>보세창고 워런트 · 두 프리미엄의 차이</strong><span>LME 워런트와 별개의 창고증권입니다.</span></summary>
        <p><b>보세창고증권</b>은 중국 보세창고에 보관 중인 정련동 물량의 증권입니다. 보세 상태는 중국 내수로 정식 수입 통관되기 전의 상태이며, LME 선물 인도용 워런트나 SHFE 등록 창고증권과 동일하지 않습니다.</p>
        <p>보세창고 프리미엄은 이미 창고에 도착한 물량의 추가 가격, B/L 프리미엄은 선하증권 거래 조건의 추가 가격을 봅니다. 둘 다 정련동 1톤당 USD이며 창고 재고량이나 워런트 취소율이 아닙니다.</p>
        <p class="copper-guide-formula">보세창고 − B/L 차이 = 창고증권 프리미엄 − 선하증권 프리미엄</p>
        <p><b>보고서 예시:</b> 창고 120달러/톤, B/L 115달러/톤이면 차이는 +5달러/톤입니다. 도착 물량의 상대 가격이 높다는 뜻이지만, 두 계약의 QP·ETA·브랜드·금융·보관 조건도 다를 수 있어 ‘중국 수요가 반드시 강하다’거나 ‘5달러 확정 차익’으로 단정할 수 없습니다.</p>
        <p>대시보드의 차이는 같은 날짜·Mysteel 제공처·화법동 또는 습법동끼리 계산합니다. 보고서와 제공처가 다르면 수치가 같을 필요는 없습니다. 빠진 날짜를 직전 값으로 채우거나 SMM 값과 섞지 않습니다.</p>
        <p class="copper-guide-sources"><a href="https://www.metal.com/methodology/base-metals/smm_copper_price" target="_blank" rel="noopener noreferrer">SMM 구리 가격 방법론</a> · <a href="https://data.metal.com/data/copper/cu_yangshan_copper_premium_warehouse_warrant" target="_blank" rel="noopener noreferrer">SMM 보세창고 프리미엄</a></p>
      </details>
    </div>
    <details class="copper-guide-data"><summary>추가 지표의 출처·확보 범위</summary>
      <ul><li>LME 구성: Minmetals Financial Services의 공개 일별 LME PDF 아카이브에서 총재고·등록·취소를 검증하고, 취소 비중은 같은 날짜의 원문 물량에서 계산합니다. 실제 입고·출고도 검증된 행을 별도 보기로 제공합니다. 카드에서 최초 기준일·관측 개수·출처를 확인할 수 있습니다. 미확보 날짜는 채우지 않으며, 공식 LME의 더 오래된 전체 이력은 별도 유료 서비스입니다.</li>
      <li>정광 TC: Mysteel 정광 홈페이지의 공식 공개 TC 차트에서 2013-01-11부터 원문 발표일 기준 이력을 확보했습니다. 주간·일간 발표 간격이 바뀌는 점에 유의하세요. SMM 공식 주간 지수는 별도 참고 카드에 표시하며 서로 이어 붙이지 않습니다. 보고서의 SHMET 견적과도 제공처·기준이 달라 수치가 다를 수 있습니다.</li>
      <li>양산 두 프리미엄의 차이: 기존 Mysteel 원문 중간값을 같은 날짜·제조 경로로 대응시킨 계산값입니다. 기존 일일 확인 뒤 다시 계산합니다.</li></ul>
    </details>`;
  return section;
}

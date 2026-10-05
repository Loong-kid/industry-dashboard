# 광물별 기업 지표 후보안

2026-10-05 조사 당시의 확장 후보안. 이후 사용자 지정 범위인 **FCX·SCCO·ALB·MP·CCJ·AA 6개사 / 18개 카드**를 구현했다. 실제 수집 기준은 [MINERAL_COMPANIES.md](MINERAL_COMPANIES.md)를 따른다. 아래 나머지 기업은 후보이며 구현하지 않았다. 우선순위는 원자재 대시보드에 연결하기 쉬운 정도와 공개 자료의 가용성을 기준으로 한 판단이다.

각 광물 구간에 가격 → 생산·매장량 → 관련 기업 순으로 배치하고, 기업은 주가 / 회사 연결 영업이익 / 해당 광물 생산량을 기본으로 제안한다. 판매량만 공시하는 기업은 판매량으로 명확히 표시한다. 같은 기업이 여러 광물에 걸치면 회사 실적은 같은 원자료를 재사용하고 광물별 생산량만 바꾼다. 연결 영업이익을 광물별 이익이라고 부르지 않는다.

## 후보 매핑

| 광물 | 우선 후보 / 확장 후보 | 물량 지표 | 노출·공시의 특징 | 공식 자료 |
|---|---|---|---|---|
| 구리 | **Freeport-McMoRan (NYSE FCX)** / Southern Copper (NYSE SCCO) | 구리 생산량·판매량, lb 또는 톤 | 광산 생산자. FCX는 금·몰리브덴도 생산. 광산 총량과 귀속지분 물량 구분 | [FCX 2025 10-K](https://www.sec.gov/Archives/edgar/data/831259/000083125926000012/fcx-20251231.htm), [SCCO 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1001838/000110465926089169/scco-20260630x10q.htm) |
| 금 | **Newmont (NYSE NEM)** | 귀속 금 생산량, oz | 금 중심. 동반 생산 광물도 있으므로 연결 이익은 금 전용 이익이 아님 | [Newmont 2026 Q2](https://www.newmont.com/investors/news-release/news-details/2026/Newmont-Reports-Robust-Second-Quarter-2026-Results-Remains-on-Track-to-Achieve-Full-Year-Guidance/default.aspx) |
| 은 | **Pan American Silver (NYSE PAAS)** / 고려아연 (KRX 010130) | 귀속 은 생산량 oz / 제련 은 생산·판매량 | PAAS도 금 사업이 있음. 고려아연은 제련·회수 사업으로 광산업체와 구분 | [PAAS 2026 공시](https://panamericansilver.com/news/2026/), [고려아연 IR](https://investors.koreazinc.co.kr/) |
| 리튬 | **Albemarle (NYSE ALB)** / SQM (NYSE SQM) | 리튬 판매량 LCE·사업부 매출. 생산량 별도 공시가 있을 때만 추가 | 판매량을 생산량으로 바꾸지 않음. ALB는 브롬 등도 포함, SQM은 요오드·비료 사업도 포함 | [ALB 2026 Q2](https://www.albemarle.com/au/en/news/albemarle-reports-second-quarter-2026-results), [SQM 2026 Q2](https://www.sec.gov/Archives/edgar/data/909037/000090903726000034/a6-k_2q2026earningsrelease.htm) |
| 희토류·NdPr | **MP Materials (NYSE MP)** / Lynas Rare Earths (ASX LYC) | REO 정광 생산 / 분리 NdPr 생산, 톤 | REO 전체와 NdPr 분리제품을 별도 표시. 네오디뮴·프라세오디뮴 개별 생산으로 임의 분할하지 않음 | [MP 2026 Q2](https://investors.mpmaterials.com/investor-news/news-details/2026/MP-Materials-Reports-Second-Quarter-2026-Results/), [Lynas 보고서](https://lynasrareearths.com/investors-media/reporting-centre/annual-reports/) |
| 우라늄 | **Cameco (NYSE CCJ / TSX CCO)** | 귀속 U₃O₈ 생산량·인도량, lb | 원자로·연료 서비스 지분도 포함. 광산 총 생산량과 회사 귀속량, 생산·인도를 구분 | [Cameco 2026 Q2](https://www.cameco.com/media/news/cameco-reports-2026-second-quarter-results) |
| 알루미늄·알루미나 | **Alcoa (NYSE AA)** | 알루미늄 / 알루미나 생산량·출하량, 톤 | 서로 다른 제품 단위의 생산량을 분리. 알루미나를 금속 알루미늄과 더하지 않음 | [Alcoa 2026 Q2](https://news.alcoa.com/press-releases/press-release-details/2026/Alcoa-Corporation-Reports-Second-Quarter-2026-Results/default.aspx) |
| 아연·납 | **고려아연 (KRX 010130)** / Glencore (LSE GLEN) | 제련 아연·납 생산량 / 자체 광산 생산량, 톤 | 고려아연은 제련수수료·회수율·부산물·에너지에도 영향. 광물 가격 상승이 곧 영업이익 상승이라고 해석하지 않음 | [고려아연 IR](https://investors.koreazinc.co.kr/), [Glencore 2026 H1 생산](https://www.glencore.com/media-and-insights/news/half-year-production-report-2026) |
| 니켈 | Vale (NYSE VALE) / Glencore (LSE GLEN) | 니켈 생산량·판매량, 톤 | Vale는 철광석 비중도 큰 다광물 기업. 자체 원료 기준·제품 기준을 고정 | [Vale 2026 Q2 생산·판매](https://vale.com/ca/check-out-the-production-and-sales-in-2q26), [Glencore 2026 H1](https://www.glencore.com/media-and-insights/news/half-year-production-report-2026) |
| 코발트 | Glencore (LSE GLEN) | 자체 코발트 생산량, 톤 | 구리·석탄 등 및 마케팅 사업도 있어 코발트 전용 주식으로 분류하지 않음 | [Glencore 2026 H1](https://www.glencore.com/media-and-insights/news/half-year-production-report-2026) |
| 철광석 | Vale (NYSE VALE) / BHP (NYSE·ASX BHP) | 철광석 생산·판매/출하량, 톤 | 광산 생산자. BHP는 구리·석탄도 포함. 회계연도와 지분 기준에 주의 | [Vale 생산·판매](https://vale.com/ca/check-out-the-production-and-sales-in-2q26), [BHP 결과·생산 보고서](https://www.bhp.com/financial-results) |
| 백금·팔라듐·로듐 | Sibanye-Stillwater (NYSE SBSW / JSE SSW) | 광산 PGM 생산량, oz | 2E·4E 합계와 개별 금속을 구분하고 합계 생산량을 각 원소에 복제하지 않음. 금·재활용 사업도 포함 | [Sibanye 보고서](https://www.sibanyestillwater.com/newsinvestors/reports/), [2025 보고서](https://reports.sibanyestillwater.com/2025/) |
| 흑연 | Syrah Resources (ASX SYR) | Balama 천연흑연 생산·판매량, 톤 | Vidalia 음극재 제품과 광산 흑연을 구분. 분기 생산·현금흐름과 반기·연간 손익 공표가 다름 | [Syrah 보고서](https://www.syrahresources.com.au/investors/reports-presentations), [Balama 사업](https://www.syrahresources.com.au/our-business/balama-graphite-operation) |
| 몰리브덴 | Freeport-McMoRan (NYSE FCX) / Southern Copper (NYSE SCCO) | 몰리브덴 생산량, lb 또는 톤 | 구리 사업의 동반 생산물. 구리 구간의 주가·회사 실적을 재사용할 수 있음 | [FCX 10-K](https://www.sec.gov/Archives/edgar/data/831259/000083125926000012/fcx-20251231.htm), [SCCO 10-Q](https://www.sec.gov/Archives/edgar/data/1001838/000110465926089169/scco-20260630x10q.htm) |

Lynas·Syrah 등 호주 상장 기업은 분기 운영자료와 반기·연간 손익 자료가 달라 수집 난도가 더 높다. 후보 선정은 가능하지만 구체적인 생산 정의와 재무 항목은 실제 구현 때 원문 표 단위로 확정해야 한다.

## 국내 기업을 더 넣을 때

- **구리: LS (006260)**가 추가 후보. LS MnM의 전기동·금·은과 연결되지만 상장 지주사 LS의 주가·연결 이익과 자회사 LS MnM 생산량은 법인 범위가 다르므로 명확히 구분해야 한다. MnM의 별도 주가를 만들지 않는다. [LS 공식 투자 정보](https://www.lsholdings.com/ko/ir/investment), [LS MnM 실적 발표](https://www.lsholdings.com/ko/media/news/464f526c58797a38723558555332787a66594e5871354c7766487339754e6669).
- **철·리튬·니켈: POSCO홀딩스 (005490)**는 추가 후보. 철강·신소재를 아우르는 그룹이어서 광산업체와 다르다. 조강 생산량과 리튬 제품 생산량을 각각 확인하고, 계획 생산능력은 실생산량으로 쓰지 않는다. [포스코홀딩스 IR](https://www.posco-inc.com/hs91a1-front/app/ir/overview.html), [리튬 사업](https://www.posco-inc.com/hs91a1-front/app/company/lithium.html).
- 갈륨·게르마늄·인듐 등은 상장사 전체 실적에서 해당 광물의 물량·수익을 분리할 수 있는지 먼저 확인한다. 관련 사업이나 예정 설비가 있다는 이유만으로 현재 생산량 카드를 넣지 않는다.

## 작업 규모 제안

**1차는 8개사 / 기본 24개 지표**: FCX, NEM, PAAS, ALB, MP, CCJ, AA, 고려아연. 주가·연결 영업이익·해당 광물 물량 각 1개씩을 기준으로 한 화면 규모다. ALB의 물량은 생산량 대신 판매량 후보이며, MP는 REO/NdPr를 선택할 수 있는 별도 시리즈로 제안한다.

**확장은 16개사 / 기본 48개 지표**: 위 8개에 SCCO, SQM, LYC, VALE, BHP, GLEN, SBSW, SYR 추가. 여러 광물 구간에서 같은 기업이 다시 보이는 표시 횟수와 실제 수집 원자료 수는 구분한다. LS·POSCO홀딩스는 그 이후 국내 비교 후보로 둔다.

주가 일간 수집은 기존 가격 수집 방식의 재사용이 가능하다. 영업이익은 국내 DART / 미국 SEC / 각 사 재무제표에서 연결·기간·통화를 고정한다. 해외 issuer별 XBRL 항목 가용성은 별도 확인해야 하며, EBITDA·순이익·세전이익을 영업이익이라고 대체 표시하지 않는다. 생산량은 기업 IR 운영보고서 수집이 추가로 필요해 가장 많은 개별 작업이 들어간다.

손익이 누적 공시이면 같은 회계연도의 검증된 누적 차이로 단독 분기를 구한다. 공식 단독 분기값이 있으면 우선 사용한다. 반기만 공표하는 기업의 이익을 분기마다 임의 분배하지 않는다. 생산량의 gross/attributable, actual/guidance, production/sales, 원광/함유금속/환산제품 단위를 각 카드에 표시한다.

추가 지표로 실현 판매가격, 현금원가·AISC, 해당 사업 매출 비중을 넣으면 광물 가격과 회사 이익의 연결을 해석하는 데 도움이 된다. 이 세 가지는 기본 24/48개 지표 규모에는 포함하지 않는다.

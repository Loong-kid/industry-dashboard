# 광물 관련 기업 지표

사용자 지정 범위: 구리 FCX·SCCO, 리튬 ALB, 희토류 MP, 우라늄 CCJ, 알루미늄 AA. 기존 가격 → 생산·매장량 → 기업 순서이며 별도 탭을 추가하지 않는다. 각 회사에 주가·영업이익·물량 세 카드, 총 18개다. 원자재 가격은 광물 가격이며 회사 주가와 구분한다.

| 광물 / 기업 | 주가 | 연결 영업이익 | 실제 물량 |
|---|---|---|---|
| 구리 / Freeport-McMoRan FCX | NYSE USD | US GAAP OperatingIncomeLoss, 백만 USD | 연결 회수가능 구리, 백만 lb; 귀속 지분으로 환산하지 않음 |
| 구리 / Southern Copper SCCO | NYSE USD | US GAAP OperatingIncomeLoss, 백만 USD | 자체 광산 Mined copper, 백만 lb; 외부 정광 처리분 제외 |
| 리튬 / Albemarle ALB | NYSE USD | US GAAP OperatingIncomeLoss, 백만 USD | Energy Storage **판매량**, 천 톤 LCE; 생산량 아님 |
| 희토류 / MP Materials MP | NYSE USD | US GAAP OperatingIncomeLoss, 백만 USD | REO 정광 / 분리 NdPr, 톤; 합산 금지 |
| 우라늄 / Cameco CCJ | NYSE USD | IFRS Earnings from operations, 백만 **CAD** | 회사 지분 U₃O₈, 백만 lb; 매입으로 처리하는 JV Inkai 제외 |
| 알루미늄 / Alcoa AA | NYSE USD | **재구성** 영업이익, 백만 USD | 알루미늄 / 알루미나, 천 톤; 제품 간 합산 금지 |

영업이익은 기업 전체 연결 기준이다. FCX의 금·몰리브덴, ALB의 브롬, MP의 자석 등 다른 사업을 포함한다. 해당 광물 전용 이익으로 해석하지 않는다. Cameco의 Westinghouse 지분법 손익은 공시상 영업소계 아래에 있으므로 회사 순이익과 다르다.

Alcoa는 손익계산서에 Operating income 소계가 없다. 공식 부문 조정 EBITDA 조정표의 세전손익·이자비용·기타손익을 이용해 `세전이익 + 이자비용 + Other expenses (income), net`으로 계산한다. 기타손익 전체를 영업외로 분류한 계산값이며 GAAP 공표 소계나 조정 EBITDA가 아니다. 구조조정·영업권 손상은 포함한다. 카드 제목·설명·기간별 원자료에 이 정의와 계산 항목을 표시한다.

## 출처와 이력

- 주가: Yahoo Finance chart 공개 응답. 티커·USD·EQUITY 검증, 완료 거래일 종가만 사용. 분할 반영·배당 미조정; 배당 재투자 수익률 아님. 2015년 또는 상장 이후 이력.
  - AA는 [독립 회사 거래 시작](https://news.alcoa.com/press-releases/press-release-details/2016/Alcoa-Corporation-Launches-as-an-Independent-Industry-Leader-in-Bauxite-Alumina-and-Aluminum-Products/default.aspx)인 2016-11-01부터, MP는 [합병 후 MP 거래 시작](https://mpmaterials.com/news/press-release-11-17-2020/)인 2020-11-18부터 사용한다. 공급자 응답의 이전 모회사·SPAC 가격을 현재 기업의 주가 이력으로 붙이지 않는다.
- FCX·SCCO·ALB·MP 이익: SEC companyfacts의 USD OperatingIncomeLoss, 연결·기간이 일치하는 10-K/10-Q. 단독 분기 우선, 없을 때만 연간−9개월로 Q4 산출. 2015년 또는 공표 가능한 이후 이력.
- CCJ 이익: 공식 분기 MD&A / Financial Statements의 CAD 천 단위를 백만 CAD로 환산. 연간은 SEC 40-F IFRS ProfitLossFromOperatingActivities. Q4 연간−9개월. 연간 2015년 이후, 분기는 2023년 비교 공시 이후.
- FCX·ALB·AA 물량: 회사 공식 Q4 금융보고서 공개 피드에서 실제 실적발표·프레젠테이션 PDF. 2024년 이후 보고서와 전년 비교 공시.
- SCCO 물량: SEC 10-K/10-Q의 Total mined copper 공식 표. 원문 백만 lb 정밀도를 유지하며 다른 PDF의 톤 값으로 가짜 소수 정밀도를 만들지 않는다.
- MP 물량: 공식 PressRelease 피드 본문. 개별 뉴스 페이지가 불안정해도 동일 회사의 공식 피드 원문을 사용하며 사용자가 여는 출처는 해당 실적발표 페이지다. NdPr `N/A`는 null이고 0이 아니다.
- CCJ 물량: 공식 quarterly-reports의 MD&A Financial Statements and Notes PDF. 연말에는 연간과 Q4 표가 별도로 있으므로 각각 읽는다.

공식 출처: [FCX](https://investors.fcx.com), [SCCO SEC](https://www.sec.gov/edgar/browse/?CIK=1001838), [ALB](https://investors.albemarle.com), [MP](https://investors.mpmaterials.com), [Cameco](https://www.cameco.com/invest/financial-information/quarterly-reports), [Alcoa](https://investors.alcoa.com).

분기·연간 선택, 최신 값의 실제 기간, 단위·기준 설명과 기간별 출처 링크를 제공한다. MP·AA의 제품별 시리즈는 따로 선택한다. 음수·0 손익은 흑자전환/적자전환/적자축소/적자확대/손익분기로 표시하며 음수 기준 증감률을 만들지 않는다. 연간 합계는 공표값 우선, 없으면 네 분기 실제 값이 모두 있을 때만 합산한다. 공표 합계와 분기 합계를 반올림 단위 내에서 대조한다. 누락 분기는 null이며 안내·증가율·생산능력·가이던스로 채우지 않는다. ALB의 나중에 공표된 LCE 환산·반올림 정정을 반영한다.

## 자동 갱신과 검증

`scripts/fetch_mineral_companies.py`를 매일 KST 07:30 기존 update-data의 독립 단계에서 실행한다. 키는 필요 없다. 과거 운영보고서의 검증된 관측값은 `data/_mineral_companies/observations.json`에 저장하고 새 버전·현재 및 전년 보고서를 재조회한다. 원문 PDF나 HTML 전체는 저장하지 않는다. 이전 공시 소실·기존 관측값 누락·최신 기간 후퇴·회사/통화/표 단위 오류 시 해당 지표군을 교체하지 않는다. 다른 회사 수집은 계속하고 마지막에 실패를 보고한다.

로컬 `--raw-dir` / `--reuse-raw`는 파서 개발용이며 CI는 재사용 옵션을 쓰지 않는다. 기존 발표 관측값과 0을 보존하고 재공시 값의 수정은 허용한다. Python 파서 검증과 Node 카드·광물 배치·기간 전환·적자 표시 검증을 갱신 전에 실행한다. 브라우저에서 실제 18개 카드, 제품 전환, 분기/연간, 표·출처, 기간 변경, 모바일·다크 및 한국 수출입 회귀를 확인한다.

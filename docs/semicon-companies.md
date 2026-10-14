# 반도체 기업 분기 실적

검토일: 2026-10-14. 기업 공식 IR·공시의 확정 분기값을 사용한다.
제품별 실적으로 분리되지 않은 영업이익·CAPEX를 임의 배분하지 않는다.
현재 기업 실적은 검토 스냅샷이며 자동으로 새 분기를 수집하는 기능은 아니다.

## 화면과 기간

|탭|기업|확보 구간|
|---|---|---|
|메모리|삼성전자·SK하이닉스|2023 Q1–2026 Q2 · 각 14분기|
|메모리|Micron|FY2024 Q1–FY2026 Q4 · 12분기|
|파운드리|TSMC·SMIC·UMC|2023 Q1–2026 Q2 · 각 14분기|
|SSD|Sandisk|FY2025 Q3–FY2026 Q4 · 6분기; JV 포함 CAPEX는 FY2026 4분기|
|SSD|Kioxia|FY2024 Q1–FY2026 Q1 · 9분기|

주소는 `#/semicon/memory`, `#/semicon/foundry`, `#/semicon/ssd`.
기존 소부장 지표는 `#/semicon/materials/snstech`, `.../esc`, `.../mocvd`.
포토마스크 번역 도서관은 `#/semicon/materials/snstech/ir`.
기존 `#/semicon/snstech`, `#/semicon/snstech/ir`, `#/semicon/esc`,
`#/semicon/mocvd`도 같은 화면을 연다. 기간 버튼과 분류는 고정 헤더 안에 있다.

파운드리는 [TrendForce 2026 Q2 순위](https://www.trendforce.com/presscenter/news/20260909-13225.html)의
TSMC·삼성·SMIC·UMC 순서에서 요청대로 삼성을 제외한 1·3·4위로 선정했다.
SSD는 사용자 지정 Sandisk·Kioxia 두 회사다. SSD 시장 점유율 상위 2사라는 의미가 아니다.

## 공식 자료와 범위

- [삼성전자 분기 IR](https://www.samsung.com/global/ir/financial-information/earnings-release/):
  매출은 연결·DS·메모리 3계열, 영업이익은 연결·DS 2계열.
  메모리 단독 영업이익은 별도 분기 공시하지 않는다. DS는 파운드리·System LSI를 포함한다.
  CAPEX는 연결 분기 현금흐름표 `Purchase(s) of PP&E`로 무형자산을 제외한다.
  현금 지급액이므로 IR 설비투자 발표액과 시점이 다를 수 있다. 단위 조 원.
- [SK하이닉스 분기 IR](https://www.skhynix.com/ir/UI-FR-IR01/):
  Solidigm 포함 연결 매출·영업이익·분기 `Acquisition(s) of PP&E` 현금 지급액.
  무형자산을 제외하고 원표 십억 원을 조 원으로 나눈다.
- [Micron 분기 IR](https://investors.micron.com/quarterly-results):
  연결 매출·GAAP 영업이익·발표문에 기재된 순 CAPEX, 백만 USD.
  순 CAPEX는 정부 지원금·자산 매각 회수 등을 차감한 회사 정의다.
  발표문의 반올림된 금액을 유지한다. 52/53주 회계연도, 실제 종료일을 보존한다.
- [TSMC 분기 IR](https://investor.tsmc.com/english/quarterly-results):
  Management Report의 연결 매출·영업이익·현금흐름표 NT$ Capital Expenditures,
  십억 TWD. USD 투자계획과 섞지 않는다. 2023 Q4·2025 Q3·2026 Q1은
  다음 분기 원문의 동일 지표 비교 열에서 확보했다.
- [SMIC 분기 IR](https://www.smics.com/en/site/company_financialSummary):
  Earnings Release의 연결 매출·`Profit from operations`·분기 실제 CAPEX,
  백만 USD. 영업이익은 공시 기준 정부 지원금을 포함한다.
- [UMC 분기 IR](https://www.umc.com/en/Html/quarterly_results):
  연결 Operating Revenues·Operating Income·현금흐름표 Acquisition of PP&E,
  십억 TWD. 무형자산·연간 투자 예산은 CAPEX 계열에 넣지 않는다.
- [Sandisk 실적 발표](https://www.sandisk.com/company/newsroom/press-releases),
  [실적 설명자료](https://investor.sandisk.com/news-events/presentations):
  회사 전체 연결 매출·GAAP 영업이익, 백만 USD. FY2025 Q3 영업이익에는
  1,830백만 USD 영업권 손상차손이 포함된다. WDC의 HDD 포함 연결 실적은 연결하지 않는다.
  총 CAPEX = Sandisk 지분 JV Gross CAPEX + 자체 PP&E.
  현금 CAPEX는 외부 조달·웨이퍼 원가 감가상각 회수 등을 반영한 회사 발표 순지출.
  FY2026 Q1–Q3 PDF p.8, Q4 PDF p.14는 `Quarter Ended` 기준이다.
  FY2025 Q4 설명자료 p.9의 890백만 USD는 `Year Ended` 연간 총 CAPEX여서
  분기 그래프에서 제외한다. FY2025 Q3·Q4 JV 포함 분기값은 null로 남기고,
  별도 자체 PP&E 계열은 6분기를 제공한다. 공란을 0이나 추정값으로 채우지 않는다.
- [Kioxia 분기 IR](https://www.kioxia-holdings.com/en-jp/ir/library/presentation.html):
  발표자료 부록 IFRS 매출·영업이익·CAPEX, 십억 JPY. 총 CAPEX에는
  유형·무형자산 취득이 포함되며 정부 지원금 차감 Net CAPEX와 구분한다.
  이후 발표된 비교표가 있으면 같은 IFRS 범위의 정정값을 우선한다.
  FY2024 4분기는 FY2025 Q4 자료 p.28, FY2025–FY2026 Q1은 FY2026 Q1 자료 p.23.

## 갱신과 검증

`manual/semicon_companies.json`에 출처 URL·PDF 페이지와 숫자만 저장한다.
원문 PDF·HTML 전체는 사이트에 배포하지 않는다. 새 분기를 검토할 때 회사별
`quarters`에 실제 분기 종료일·FY·분기·값·출처를 추가하고 `reviewed`를 갱신한다.
연간·YTD 금액은 분기 원값과 섞지 않는다. 누적값만 있으면 이전 누적값과의 차분을
먼저 확인하고, 계산 근거를 기록한 뒤 분기값을 추가한다.

```sh
python scripts/aggregate_semicon_companies.py
python -m unittest discover -s scripts -p test_semicon_companies.py
python scripts/test_semicon_navigation.py --url http://127.0.0.1:8765/
```

빌더는 네트워크를 사용하지 않으며 24개 차트를 재현한다. 데이터 기준일과 검토일을
구분한다. YoY·QoQ는 FY·분기 매칭을 사용해 53주 결산과 달력 분기 이동을 처리한다.
각 차트의 펼침 데이터 표에서 분기별 공식 원문으로 이동할 수 있다.

# 반도체 기업 분기 실적

검토일: 2026-10-15. 기업 공식 IR·공시의 확정 분기값을 사용한다.
제품별 실적으로 분리되지 않은 영업이익·CAPEX를 임의 배분하지 않는다.
현재 기업 실적은 검토 스냅샷이며 자동으로 새 분기를 수집하는 기능은 아니다.

## 화면과 기간

|탭|기업|확보 구간|
|---|---|---|
|메모리|삼성전자·SK하이닉스|2014 Q1–2026 Q2 · 각 50분기|
|메모리|Micron|FY2014 Q1–FY2026 Q4 · 52분기|
|파운드리|TSMC·SMIC·UMC|2014 Q1–2026 Q2 · 각 50분기|
|파운드리|GlobalFoundries|2020 Q3–2026 Q2 · 24분기; 비상장 시기 미확인 분기는 미수록|
|SSD|Sandisk|구 SanDisk FY2014 Q1–FY2016 Q1 · 9분기 / WDC Flash FY2018 Q1–FY2025 Q2 · 30분기 / 재분사 후 FY2025 Q3–FY2026 Q4 · 6분기|
|SSD|Kioxia|도시바 Memory FY2014 Q1–FY2017 Q4 · 16분기 / Toshiba Memory·Kioxia IFRS FY2018 Q3–FY2026 Q1 · 31분기|

주소는 `#/semicon/memory`, `#/semicon/foundry`, `#/semicon/ssd`.
기존 소부장 지표는 `#/semicon/materials/snstech`, `.../esc`, `.../mocvd`.
포토마스크 번역 도서관은 `#/semicon/materials/snstech/ir`.
기존 `#/semicon/snstech`, `#/semicon/snstech/ir`, `#/semicon/esc`,
`#/semicon/mocvd`도 같은 화면을 연다. 기간 버튼과 분류는 고정 헤더 안에 있다.

파운드리는 TSMC·SMIC·UMC에 사용자 요청으로 GlobalFoundries를 추가했다.
SSD는 사용자 지정 Sandisk·Kioxia 두 회사다. SSD 시장 점유율 상위 2사라는 의미가 아니다.

## 공식 자료와 범위

- [삼성전자 분기 IR](https://www.samsung.com/global/ir/financial-information/earnings-release/):
  매출은 연결·DS·메모리 3계열, 영업이익은 연결·DS 2계열.
  메모리 단독 영업이익은 별도 분기 공시하지 않는다. DS는 파운드리·System LSI를 포함한다.
  2014~2021년은 당시 Semiconductor 사업부, 2022년부터는 DS다.
  Display를 포함했던 과거 DS 전체를 반도체 실적으로 사용하지 않는다.
  CAPEX는 연결 분기 현금흐름표 `Purchase(s) of PP&E`로 무형자산을 제외한다.
  현금 지급액이므로 IR 설비투자 발표액과 시점이 다를 수 있다. 단위 조 원.
- [SK하이닉스 분기 IR](https://www.skhynix.com/ir/UI-FR-IR01/):
  Solidigm 포함 연결 매출·영업이익·분기 `Acquisition(s) of PP&E` 현금 지급액.
  무형자산을 제외하고 원표 십억 원을 조 원으로 나눈다.
- [Micron 분기 IR](https://investors.micron.com/quarterly-results):
  연결 매출·GAAP 영업이익·발표문에 기재된 순 CAPEX, 백만 USD.
  순 CAPEX는 정부 지원금·자산 매각 회수 등을 차감한 회사 정의다.
  발표문의 반올림된 금액을 유지한다. 52/53주 회계연도, 실제 종료일을 보존한다.
  FY2014~FY2016 Q3 초기 발표 CAPEX는 차감 기준이 명시되지 않아 별도 계열이다.
  FY2016 Q4부터 파트너 부담액 차감 순액을 연결한다. FY2014 Q1 종료일은 2013-11-28이다.
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
- [GlobalFoundries 공식 실적](https://investors.gf.com/financial-information/quarterly-results):
  IFRS 연결 매출·영업이익, 백만 USD. 2024 Q4 자산손상차손을 포함한다.
  CAPEX는 유형·무형자산 현금 취득액이며 정부 보조금 차감 전 금액이다.
  확인 가능한 공개 비교표는 2020 Q3부터이며 과거 비상장 분기를 추정하지 않는다.
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
  구 SanDisk는 SEC 실적 발표문의 천 USD 단위 연결 매출·GAAP 영업이익 및
  `Acquisition of property and equipment, net`의 **3개월** 현금흐름을 사용한다.
  이를 백만 USD로 변환하며 JV 투자·장비 리스가 포함된 총투자로 간주하지 않는다.
  WDC 시기는 공식 Quarterly Financial/Financial Metrics 표의 **Flash Revenue**만
  사용한다. HDD 매출과 WDC 전체 영업이익·CAPEX는 포함하지 않는다.
  표의 Flash gross profit은 영업이익으로 바꾸지 않는다. 2016년 인수 전후부터
  FY2017까지의 미확보 기간은 비어 있으며 분사 전후 서로 다른 FY·계열을 연결하지 않는다.
  공식 표끼리 겹치는 FY2018~FY2025 구간을 대조했다. 모든 기간별 원문 URL과 PDF
  페이지는 `history_groups`의 개별 분기에 보관한다.
- [Kioxia 분기 IR](https://www.kioxia-holdings.com/en-jp/ir/library/presentation.html):
  발표자료 부록 IFRS 매출·영업이익·CAPEX, 십억 JPY. 총 CAPEX에는
  유형·무형자산 취득이 포함되며 정부 지원금 차감 Net CAPEX와 구분한다.
  이후 발표된 비교표가 있으면 같은 IFRS 범위의 정정값을 우선한다.
  FY2024 4분기는 FY2025 Q4 자료 p.28, FY2025–FY2026 Q1은 FY2026 Q1 자료 p.23.
  상장 전 Financial Results Overview의 Sales·IFRS Operating Income/Profit을
  FY2018 Q3부터 추가했다. 매출·영업이익은 동일 보고서의 이전/현재 분기 열을 사용한다.
  FY2022 Q4와 FY2023의 CAPEX는 FY2024 Q3 발표 p.17의 IFRS 분기 원표에서 확인했다.
  더 이전 발표자료에 수록되지 않은 단일 분기 CAPEX는 null이며 `missing_reasons`에
  이유를 기록한다. 연간·투자 약정·향후 계획을 분기로 나누지 않는다.
  도시바 시기는 회사 전체·HDD 포함 Storage 사업부가 아닌 **Memory/Memories**
  제품·사업의 매출을 사용한다. FY2014는 FY2015 발표 비교표의 기존 분류,
  FY2015~FY2017은 FY2016부터 공개한 사업별 분류의 비교값을 우선하므로 계열을 나눈다.
  FY2014 Q4 매출은 연간 860.6−9개월 누적 638.3=222.3십억 엔이다.
  사업별 영업이익은 FY2015 비교값부터만 확보했다. FY2017 도시바 Memory 영업이익
  479.1십억 엔을 후속 Former TMC IFRS 연간 영업이익 456.8과 동일 범위로 취급하지 않는다.
  Toshiba Memory 인수 전후 FY2018 Q1·Q2는 미확보 구간이다.

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

빌더는 네트워크를 사용하지 않으며 27개 차트를 재현한다. 데이터 기준일과 검토일을
구분한다. YoY·QoQ는 FY·분기 매칭을 사용해 53주 결산과 달력 분기 이동을 처리한다.
각 차트의 펼침 데이터 표에서 분기별 공식 원문으로 이동할 수 있다.

전신·사업부 자료는 `history_groups`에 통화·계열·공시 범위·분기를 명시한다.
빌더는 원래 연결 실적과 별도 계열로 그리며, 서로 다른 분류 사이의 YoY·QoQ를
계산하지 않는다. 이전 분기 값만으로 누락 분기를 채우거나 기간 사이를 보간하지 않는다.

## 포토마스크 실적 확장

|기업/지표|기간|기준|
|---|---|---|
|에스앤에스텍 매출·영업이익·CAPEX|2014 Q1–2026 Q2 · 50분기|DART 연결 재무제표, 백만 원|
|HOYA IT 사업부 매출|2014 Q1–2026 Q2 · 50분기|회사 공식 IR, 제품별 추정 매출과 분리|
|AGC 전자부재 매출|2015 Q1–2026 Q2 · 46분기|공식 Data Book Excel, 백만 엔을 억 엔으로 변환|
|신에츠 전자재료 매출|2014 Q1–2026 Q2|2021 Q1까지 이전 두 사업부 합계를 별도 계열로 표시|
|Photronics IC·FPD 합계|FY2014 Q1–FY2026 Q3 · 51분기|FY2020까지 공식 분기 발표의 0.1백만 USD 반올림값; 이후 SEC 제품별 주석|
|Mycronic PG 수주·매출·매출총이익률|2014 Q1–2026 Q2 · 50분기|공식 8개 분기 원표; 초기 미구분 PG EBIT·잔고는 null|

JEOL의 현재 공식 Data Book에서 확보한 분기 사업부 실적은 2016년부터,
NuFlare는 기존 공식 연간 그래프 구간, Tekscend는 독립 법인 공시 구간을 유지한다.
상장 전 모기업 전체 실적·연간 실적을 분기 사업부 실적으로 바꾸지 않는다.
HOYA·AGC의 사용자 시트 제품별 추정치는 원래 시트 기간을 유지한다.

에스앤에스텍 정규화 원장은 `data/_snstech/financial_quarters.json`이다.
2014 및 2015년 초기 공시는 DART 공개 HTML, 이후 공시는 OpenDART 원문 계정을 확인했다.
원 단위 금액·회계기간·원문 접수번호를 보관하고 차트 생성 시 백만 원으로 나눈다.
매출·영업이익은 공시된 3개월 금액, Q4는 연간−Q3 누적이다.
CAPEX는 CF 유형자산 취득 누적액의 차분이며 무형자산은 제외한다.
후속 비교표 재분류를 보존하며 분기 합계를 맞추려고 임의 보정하지 않는다.
연간 대조 차이는 원장 `annual_checks`, 각 카드 설명과 검증 테스트에 기록했다.
2015 매출 +95,217원, 영업이익 −26,329,076원; 2025 매출 −42,035,269원이다.

`aggregate_snstech.py` 다음에 `aggregate_snstech_financials.py`를 실행한다.
자동 갱신 작업도 이 순서를 지켜 과거 연결 재무 차트를 짧은 CSV로 덮어쓰지 않는다.
새 공시의 연결 범위·재분류를 검토해 원장을 갱신한 뒤 빌더를 실행한다.
API 키는 CI Secret으로만 사용하며 공개 원장·산출물·출처 링크에는 넣지 않는다.

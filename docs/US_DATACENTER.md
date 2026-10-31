# 데이터센터 → 한국 / 미국

한국은 기존 국내 허가·착공·센터별 현황과 검토·갱신 내역을 유지한다. 미국은 미국 본사 하이퍼스케일러의 **글로벌 연결 실적과 공시 사업 실적**이다. 미국 내 데이터센터 개수·위치·전력 용량, 미국 내 매출·투자만의 통계는 아니다.

## 기업과 지표

| 기업 | 클라우드 매출 범위 | 클라우드 영업이익 |
| --- | --- | --- |
| Amazon | AWS | AWS 사업부 실제 공시 |
| Microsoft | Microsoft Cloud, Azure·Microsoft 365 상업용 등 포함 | 같은 범위의 단독 이익 미공개 |
| Alphabet | Google Cloud, GCP·Workspace 등 포함 | Google Cloud 사업부 실제 공시 |
| Oracle | 공시된 Cloud 서비스 IaaS·SaaS 등 | 클라우드 단독 이익 미공개 |
| Meta | 외부 퍼블릭 클라우드 판매 사업 없음 | 해당 없음 |
| SpaceX / xAI | AI/SI 전체: Grok·X·Cursor·클라우드 서비스 등 | AI/SI 사업부 실제 공시, 순수 클라우드 이익과 다름 |

전사 매출·영업이익, 클라우드 매출·전사 매출 대비 비중, 클라우드 영업이익, 전사 현금 PP&E CAPEX를 분기·완결 회계연도로 나열한다. Microsoft·Oracle은 공시 범위가 더 넓은 사업부 이익을 클라우드 이익으로 대체하지 않는다. Meta는 자체 AI·서비스 인프라 투자 비교용으로 전사 실적과 투자만 표시한다. 비공개·해당 없음은 0으로 계산하지 않는다.

Microsoft의 예전 Intelligent Cloud·현재 Agents and Infra는 Microsoft Cloud와 다른 범위다. Oracle의 Cloud services and license support, Cloud and software도 유지보수·라이선스 등 다른 매출을 포함한다. 이 큰 부문의 매출·이익을 클라우드 단독 수치로 쓰지 않는다.

클라우드 비중은 **동일 실제 기간의 클라우드 매출 / 전사 매출 × 100**이다. 연간 비중은 연간 실적끼리 계산하며 분기 비중을 평균하지 않는다. Microsoft는 6월, Oracle은 5월 결산이며 FY는 끝나는 해를 따른다.

미국 탭 앞쪽에는 **클라우드 매출·영업이익·영업이익률·CAPEX를 각각 비교하는 선 그래프 4개**가 있다. 각 그래프에서 기업 이름을 클릭해 여러 회사를 동시에 켜거나 끈다. 선택은 분기·연간 전환과 기간 변경에도 유지한다. Microsoft·Oracle의 클라우드 단독 영업이익·이익률과 Meta의 외부 클라우드 사업은 빈값과 비활성 항목으로 표시한다.

비교 축은 분기의 경우 실제 결산 종료일이 속하는 달력 분기, 연간은 FY 결산연도다. Microsoft·Oracle의 실제 회계기간은 다른 회사와 달라 숫자·차트 메모·표에 원래 FY·분기와 시작·종료일을 보존한다. 같은 표시 분기나 FY가 완전히 동일한 사업 기간을 뜻하지 않는다. 연간 이익률은 연간 영업이익 / 연간 매출이며 분기 이익률을 평균하지 않는다. 미공개·중간 공백을 0으로 채우거나 연결하지 않는다.

CAPEX 비교에서 Amazon·Microsoft·Alphabet·Oracle·Meta는 전사 현금 PP&E 투자 대리지표이며 회사명에도 `전사`를 표시한다. xAI는 실제 AI/SI 사업부 CAPEX로 범위가 다르다. xAI는 모든 비교에서 선택할 수 있지만 순수 클라우드가 아닌 AI/SI 범위이므로 기본 선택에서는 제외한다. 기존 회사별 상세 카드는 비교 그래프 아래에 유지한다.

### SpaceX / xAI

2026년 2월 2일 SpaceX가 인수한 xAI는 AI 사업부이며, 2026년 3분기 공시에서는 SI(Super Intelligence)로 명칭이 바뀌었다. 순수 클라우드만의 실적이 아니므로 기존 회사의 클라우드 실적과 명칭을 구분한다. SpaceX 전사 연결 매출·영업이익·현금 CAPEX와 AI/SI 사업부의 매출·영업이익·SpaceX 매출 대비 비중·CAPEX를 별도 카드로 표시한다. 지표별 기업 비교에서는 AI/SI 범위의 수치를 사용한다.

[2026-06-01 상장신고서](https://www.sec.gov/Archives/edgar/data/1181412/000162828026039276/spaceexplorationtechnologi.htm)의 완전한 사업부 표에서 2023~2025년 연간, 2025·2026년 1분기를 추출하고, 이후 10-Q·10-K의 실제 USD XBRL을 수집한다. 상장신고서에는 XBRL instance가 없어 이 초기 표를 별도 검증한다. 분기 자료는 2025년부터이며 연간 자료를 4등분하지 않는다. 4분기는 연간−9개월 누적으로 계산한다. 공통지배 합병의 소급 재작성으로 X의 과거 실적도 포함하며, 2026년 8월 Cursor 인수 전후는 사업 범위가 다르다. AI/SI CAPEX는 실제 공시된 사업부 금액으로, 우주·Starlink 등 전사 투자와 구분한다.

## CAPEX 정의

데이터센터 전용·미국 내 전용 CAPEX를 따로 공시하지 않는 경우가 많아 전사 현금 유형자산 취득을 공통 투자 대리지표로 사용한다. 물류·사무실·기타 사업 투자도 포함할 수 있다. 자산 매각·인센티브를 차감한 회사 발표 net cash CAPEX와 다를 수 있다. Amazon의 공시 태그 전환(PP&E → productive assets)을 포함해 실제 현금흐름표 금액을 사용한다.

- Microsoft 보충 지표: 현금 PP&E + 금융리스 취득자산(ROU). 재무제표 보충 공시를 합한 계산값으로, 콘퍼런스콜에서 발표하는 CAPEX·신규 리스 원금과 시점·포함 범위가 달라 일치하지 않을 수 있다.
- Meta 보충 지표: 현금 PP&E + 금융리스 원금 지급. 회사가 정의한 현금 CAPEX 기준이며 신규 ROU 취득을 더한 Microsoft 지표와 다르다.

리스 부채 잔액·향후 약정·계약 잔량·미래 투자 계획·가이던스는 실제 분기 지출에 더하지 않는다. Amazon의 rolling TTM 현금흐름도 완결 회계연도나 분기로 오인하지 않도록 제외한다. 두 구성 항목의 실제 시작일·종료일이 같은 경우만 더한다.

## 출처와 이력

전사 지표는 SEC Company Facts, 클라우드는 개별 SEC XBRL instance의 실제 USD 단위·기간·사업 차원을 읽는다. Company Facts에는 사업 차원이 없으므로 클라우드 태그가 보이지 않는다고 바로 미공개로 취급하지 않는다. 중복 차원은 더하지 않고 수치가 일치하는지 확인한다. 음수 Google Cloud 영업손익도 보존한다.

전사 이력은 2014년부터 가용 공시를 연결한다. Alphabet의 초기 2014년 분기는 지주회사 전환 전 Google Inc.(CIK 1288776) 실제 공시로 보완하고 원문 법인·출처를 보존한다. 클라우드는 현재와 같은 범위로 실제 공시한 기간만 사용하며 다른 사업부나 연간화 run-rate를 연결하지 않는다. 분기 단독 값이 없는 4분기는 같은 회계연도 누적 차분으로 보완한다. 기간 재작성·사업 재분류 때문에 후속 연간과 예전 분기 합계가 다를 수 있다.

각 포인트에 원문·실제 기간·태그·차원·계산 구성 자료를 보존한다. 단위는 USD 백만 또는 %다. 공시 반올림과 환산되지 않은 보고 USD를 그대로 사용한다. 미공개·미확보를 추정하거나 0으로 채우지 않는다.

공식 출처: [Amazon IR](https://ir.aboutamazon.com/), [Microsoft IR](https://www.microsoft.com/en-us/investor/), [Alphabet IR](https://abc.xyz/investor/), [Oracle IR](https://investor.oracle.com/), [Meta IR](https://investor.atmeta.com/), [SEC API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

## 갱신

`update-us-datacenter.yml`은 매일 KST 09:50에 SEC 연결 공시와 새 사업 공시를 조회한다. 실제 발표 후 반영되며 예측치를 섞지 않는다. 사업별 원문을 파싱하지 못하면 기존 이력을 유지하고 검토 상태를 표시한다. 한국 데이터 수집·정리 파일은 이 작업에서 변경하지 않는다.

```sh
python scripts/fetch_us_datacenter.py
python -m unittest discover -s scripts -p test_us_datacenter.py -v
```

`--full-history`는 최초 전체 XBRL 이식·파서 보완용이며 캐시를 재사용한다. 원문은 `.cache/us-datacenter/`에만 저장한다. 공개 `us_hyperscalers_state.json`은 정규화한 원문 근거와 기간을 보존하며 일일 자동 커밋은 `us_dc_*.json`과 이 상태 파일만 포함한다.

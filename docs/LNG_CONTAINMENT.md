# LNG 화물창·보냉재

천연가스 → **보냉재**. GTT·동성화인텍·한국카본을 기업별로 묶고 각 기업의 매출·영업이익·순이익 다음에 수주·운영 지표를 표시한다. 기존 수주·운영 KPI 탭은 통합했으며 이전 링크도 보냉재 탭으로 연결한다.

## 기업 실적

- GTT: 멤브레인 화물창 설계·라이선스 기업. 디지털·해양 서비스·Elogen 등 연결 전체이며 보냉재 생산업체와 구분한다.
- 동성화인텍(033500): PU단열재·초저온 보냉재·가스 등 연결 전체.
- 한국카본(017960): LNG 보냉재 외 산업재·일반재·종속기업을 포함한 연결 전체.

공시된 실제 연결 전체 매출·영업손익·당기순손익을 사용한다. 국내 기업은 연결 우선, 미공시 기간은 별도임을 표시한다. 지배주주 귀속 순이익을 전체 순이익으로 대체하지 않는다. 원화 실적은 OpenDART 전체 손익계산서에서 가져오며, 누적 차감은 동일 연도·연결/별도 기준에서만 수행한다. 구형 IFRS 태그, 실제 비교기간, 연간−9개월의 4분기는 기존 조선 기자재 파서를 재사용한다.

GTT 공식 보도자료 49건의 연결 손익계산서 행·열·단위·공표일·SHA256을 검토해 `manual/lng-containment/gtt-reviewed.json`에 보존했다. 연간은 2014년부터, 매출은 실제 분기 또는 같은 연도 누적 차감이다. 영업이익·순이익은 반기·연간만 제공하며 H2는 FY−H1이다. 회사가 제공한 후속 실제 비교기간·IFRS 15 proforma 비교기간은 최신 공표 자료를 우선한다. 각 차감의 두 출처를 보존한다. 공시 반기 손익을 분기별로 나누지 않는다.

GTT 영업이익은 **비경상 항목 포함 전체 영업손익**이다. 2025년 예: current EBIT €521.3m, 비경상 −€48.7m, 전체 영업손익 €472.6m. 순이익 €413.6m. 요약표의 EBIT·EBITDA를 전체 영업손익으로 쓰지 않는다.

재무 그래프는 백만 USD. 실제 분기·반기·연간 보고기간의 ECB 일별 local/USD 산술평균으로 환산하며, 원화/EUR 금액·환율·관측기간을 메모에 유지한다. 현재 값으로 과거를 환산하지 않는다.

## 별도 KPI

|회사|표시 지표|정의|
|---|---|---|
|GTT|화물창 수주잔고|기말 핵심사업 전체 기수, 그중 LNG선 기수, 별도 LNG연료용 기수. 부분집합·별도 범위를 합산하지 않는다. 러시아 프로젝트 제외 영향 유의.|
|GTT|신규 수주|실제 공시의 연초 이후 누적(YTD) 핵심사업 기수 및 그중 LNG선. 분기 YTD를 합산하지 않는다.|
|동성화인텍|초저온보냉재 수주잔고|DART 사업의 내용에서 원화 백만원. 기말 ECB 환율로 백만 USD 환산, 원자료와 환율 메모 보존.|
|동성화인텍|PU단열재 가동률|해당 보고기간 누적 실제시간/가동가능시간. 분기 단독 값으로 차감하지 않는다.|
|한국카본|LNG 화물창 판넬 수주잔고|DART 사업의 내용에서 천 USD, 백만 USD로 단위만 변환.|
|한국카본|LNG 포함 산업재 매출 비중|절연적층물·LNG·GPD/F 등을 포함한 산업재 전체. LNG 단독 비중이 아니다.|

국내 KPI는 2022년부터 실제 확보한 분기 말 공시로 시작한다. API가 내려준 ZIP에는 사업보고서 외 감사보고서·첨부 XML이 함께 있다. 파일 순서나 receipt prefix로 고르지 않고 `DOCUMENT-NAME`이 사업/반기/분기보고서인 XML을 유일하게 선택한다. EUC-KR/UTF-8을 모두 처리한다. 수주잔고는 수주총액·기납품액 옆 **최종 잔고 금액 열**만 선택하고 원문 단위를 강제한다. 단일판매 공시 금액을 더해 잔고를 추정하지 않는다.

생산능력은 동성화인텍의 금액 기준 능력과 한국카본의 면적·장수·개수 등 품목 단위가 달라 직접 합산하지 않는다. 특허 수·선급 승인·증설은 비정기 정성 이벤트이므로 월별 생산량 KPI로 만들지 않는다.

## 수집·검증

`update-lng-containment.yml`이 매일 09:40 KST에 독립 실행된다. DART_API_KEY는 CI Secret만 사용하며 공개 JSON·로그에 키가 없다. GTT IR의 새 미검토 실적은 수치 확인 필요 상태로 표시한다. 검토된 이력은 보존하고, 원문 해시/행이 달라지면 성공 상태로 덮어쓰지 않는다. 기존 천연가스 가격·미드스트림 작업과 데이터 경로를 분리한다.

```sh
python scripts/fetch_lng_containment.py
python scripts/build_lng_containment_kpis.py
python scripts/validate_lng_containment.py
python -m unittest discover -s scripts -p test_lng_containment.py
```

최초 전체 이력은 `--full-history`, 공개 상태에서 재현은 `--offline`. 원문 캐시는 `.cache/lng-containment/`이고 사이트에는 `assets/`, `data/`만 배포한다.

원문: [GTT IR](https://www.gtt.fr/finance/investor-relations/investors-pack), [OpenDART](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020), [동성화인텍 IR](https://dsfinetec.co.kr/kr/sub/ir/finance.php), [한국카본 IR](https://www.hcarbon.com/ko/media/ir.do).

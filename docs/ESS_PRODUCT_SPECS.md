# ESS 완제품 사양 비교

검토일 2026-10-10. ESS 시장·배치·수주 지표 다음, 시스템 공장 및 배터리 셀 지표 앞에 하나의 비교표를 둔다. 제품 사양은 시계열 지표와 별도로 표시한다.

## 제조사 자료와 범위

| 제품 | 구성 수 | 사용 자료 | 사양의 대상 |
|---|---:|---|---|
| Tesla Megapack 3 / Megablock | 3 | Tesla Megablock Datasheet Rev. 1.7, 2026-06-29, 1~3쪽 | 2/4/8시간 Tesla-Standard 개별 Megapack. MV 블록 전체 수치 아님 |
| Fluence Gridstack Pro | 3 | BR-042-04-EN, ©2024, 2/5/6쪽 | 2000 3XX Ah / 5000 3XX Ah / 5000 5XX Ah 배터리 외함·팩 옵션 |
| Fluence Smartstack | 2 | BR-061-03-EN, ©2026, 2/4/5쪽 | 7.5 / 10 MWh 팩 옵션; 물리적 사양은 Skid·단일 Pod 각각 |

원문은 `manual/ess_products.json`의 `sources`에 URL·작성자·자료판·호스팅 위치·PDF SHA-256을 기록했다. Fluence는 공식 호스팅 PDF, Tesla는 제조사가 작성한 데이터시트의 Carpenter Hill 공개 프로젝트 문서 재게시본이다. 원문 다운로드·표 페이지 이미지 대조를 거쳤다. 저작권 연도를 발행일로 바꾸지 않았으며 PDF 파일 메타데이터의 저장일도 공표일로 사용하지 않는다.

화이트페이퍼는 계통 제어·안전 등의 설명을 다루므로 수치 비교에는 해당 제품의 기술 데이터시트와 브로슈어를 사용한다. 보증 계약·인증서·화재 시험 성적서 원문을 확보했다는 의미는 아니다. 이전 Megapack 2/2 XL이나 구형 Gridstack Cube의 수치를 최신 제품에 섞지 않는다.

## 비교에서 지킨 조건

- Tesla 표준 2시간 구성의 출력은 2,186 kW AC, 에너지는 4,372 kWh이다. 같은 PDF의 BM 옵션별 **최대** 2,385 kW / 4,770 kWh 및 인버터 3,180 kVA와 혼합하지 않는다. 4시간 표준 4,826 kWh / 1,206 kW, 8시간 4,824 kWh / 603 kW를 별도 행으로 둔다.
- Megablock은 Megapack 3 두 대 이상과 MV 변압기·개폐기 등의 조립체이다. 개별 장치 사양을 고정된 20 MWh 블록이나 전체 블록 외형·운송 중량으로 바꾸지 않는다.
- Tesla RTE는 25°C, 전체 방전 깊이의 사이클에서 전력 변환과 열관리 손실을 포함한다. MV 변압기를 포함한 계통 접속점 효율로 확대하지 않는다. Gridstack Pro의 >87%는 경계·조건이 미표기인 설계 추정치이며 Smartstack은 RTE를 공개하지 않는다.
- Fluence의 기술표 각주는 **design estimates only and are not guaranteed**라고 명시한다. 수치에 이 표지를 유지한다. 가용성도 실제 운영 실적과 구분한다.
- Gridstack Pro 5000의 3XX Ah 옵션은 4,872~5,016 kWh, 5XX Ah는 5,644 kWh이다. 플랫폼 공통 2/4/6/8시간 설명을 각 옵션이 전부 지원한다는 보장으로 바꾸지 않는다. 특히 5XX Ah의 최대 CP-rate는 0.25다.
- Smartstack 10 MWh 옵션은 약 10,000 kWh이고 지원 시간은 4/6/8시간이다. 7.5 MWh 옵션의 2시간 구성을 물려받지 않는다. 최대 AC 전류 3,762 A 이하 / 2,508 A는 AC 유효출력 MW와 구분한다. 셀 CP-rate·전류·전압·에너지/시간으로 미공개 MW를 추정하지 않는다.
- Smartstack의 Skid 약 10,000 kg 및 단일 Pod 약 15,000/20,000 kg를 전체 시스템 중량으로 합산하지 않는다. Gridstack Pro 중량은 냉각수 제외 배터리 외함 기준이다.
- Smartstack 최대 25년 용량 보장은 선택 Smart Service Plans에 해당한다. 기본 제품 보증·설계 수명으로 바꾸지 않는다. 사이클 수와 잔존 용량 계약 조건은 미공개다.
- 셀 화학계·셀 공급사·정확한 3XX/5XX Ah 값을 추측하지 않는다. UL 9540A는 시험 방법으로, 제품 인증과 구분한다. 인증/규격의 제조사 열거와 모든 프로젝트에 대한 인증 취득을 구분한다.

## 갱신과 검증

`manual/ess_products.json` → `scripts/aggregate_ess_products.py` → `data/ess/ess_products.json`.
일일 수집 시 자료를 검증해 게시하되 검토일은 변경하지 않는다. `assets/ess-products.js`가 기업·제품 필터와 원문 페이지 링크를 표시한다. 단위는 원문 kWh/kW를 보존하고 화면에서 MWh/MW로 정확히 1,000으로 나눠 표시한다.

`python -m unittest discover -s scripts -p test_ess_products.py`는 표준/최대/피상전력 구분, 미공개 출력·효율, 옵션별 시간·범위, 수치·출처 검증 및 ESS 내 순서를 확인한다. 브라우저에서는 필터, 공장표와 독립 동작, 모바일 표 스크롤·다크모드·기존 차트를 확인한다.

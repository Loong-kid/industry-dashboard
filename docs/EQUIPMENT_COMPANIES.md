# 소부장 분류와 미국 장비 3사

소부장은 장비(equipment), 부품(components), 소재(raw_materials)로 나눈다. 장비 기본 화면은 요약(미국 3사)이며 MOCVD가 하위 분야다. 부품은 블랭크마스크(기존 포토마스크 지표 전체)·정전척 ESC, 소재는 실리콘 웨이퍼다. 전공정·계측 등 추가 분류는 이번에 만들지 않았다.

주소는 `#/semicon/materials/equipment`, `#/semicon/materials/equipment/mocvd`, `#/semicon/materials/components/snstech`, `#/semicon/materials/components/esc`, `#/semicon/materials/raw_materials/wafer`다. 기존 `#/semicon/materials/snstech`, `#/semicon/snstech` 등의 주소와 IR 문서 링크도 같은 분야로 연결한다.

`fetch_equipment_companies.py`는 SEC Company Facts API에서 Lam Research(CIK 707549), Applied Materials(6951), KLA(319201)의 연결 매출·영업이익·CAPEX를 수집한다. 2014년 이후 실제 분기 종료일과 공시 접수일·원문 링크를 보존한다. 영업이익은 조정 이익이나 순이익이 아니다.

- Lam은 6월 말 52/53주 결산, AMAT는 10월 말 52/53주 결산, KLA는 6월 결산이다. FY는 종료 연도다. 누적 현금지출은 같은 회계연도 차분으로 분기화한다. 연간은 회사의 완결 10-K 기준이다.
- Lam의 `PaymentsToAcquireProductiveAssets`는 **Capital expenditures and intangible assets**다. 무형자산을 포함하므로 다른 회사의 유형자산 현금취득과 같은 범위로 간주하지 않는다. AMAT·KLA는 `PaymentsToAcquirePropertyPlantAndEquipment`다.
- KLA는 최근 손익계산서에서 영업이익 소계를 별도로 제시하지 않는다. 미공시 소계는 **GAAP 연결 매출 − 매출원가 − 연구개발비 − 판관비 − 영업상 손상차손**으로 계산한다. 매출·매출원가·R&D·판관비는 동일 accession·start·end가 모두 일치해야 하며, 과거 직접 공시된 영업이익이 있으면 그 값을 우선한다. 매출 표준 태그 변경도 처리한다. 손상차손은 AssetImpairmentCharges를 우선하고 동일 문맥의 GoodwillImpairmentLoss를 대체로 사용한다. 손상 항목이 없는 문맥은 0으로 처리한다. 이자·기타영업외손익·채무상환손익을 영업이익에 포함하지 않는다. 계산 공식과 실제 입력 태그·금액은 `equipment_state.json`의 근거에 남기고 차트에도 계산값임을 표시한다. 이는 회사의 비GAAP 조정 영업이익이 아니다.
- GAAP 손익에 포함된 손상차손·구조조정 등을 임의로 가산하지 않는다. 특히 KLA의 사업부 이익 합계로 대체하지 않는다.
- 장비사의 CAPEX는 고객의 WFE 투자액·장비 수주액이 아니다. 연결 매출에는 서비스 및 다른 연결 사업이 포함된다.
- 실패·이력 축소·일부 지표 누락 시 마지막 성공 자료를 유지하고 실패 상태를 표시한다. `.github/workflows/update-equipment.yml`가 매일 KST 08:30에 확인하며 사이트의 장비 실적 갱신 버튼으로도 실행할 수 있다. 수집 성공 후 자동 배포한다.

검증: `python -m unittest discover -s scripts -p test_equipment_companies.py -v`, `python scripts/verify_equipment_ui.py --url http://127.0.0.1:8792/`.

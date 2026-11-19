# 해양 시추 주가·밴드

경로: `#/oil/offshore/valuations` — 원유 → 해양 시추 → 주가·밴드.
기존 운영사 실적·선대·계약·시장 화면을 유지하며 `#/offshore/valuations` 북마크도 연결합니다.

- Transocean(RIG), Valaris(VAL), Noble(NE), Seadrill(SDRL), Odfjell Drilling(ODL.OL), Borr Drilling(BORR).
- 비교표 및 기업별 주가·PER·PBR 차트 18개. 기존 밴드 모듈의 확대·기간 선택·표 보기·PER 배수 설정을 사용합니다.
- Yahoo Finance의 일별 종가·보고 희석 EPS·보통주 귀속 자본·기말 주식수. API 응답 원본은 비공개 `.cache/offshore-valuation/`에 보관합니다.
- 주가: RIG·ODL은 2014년부터, VAL은 2021-05-03, NE는 2021-06-09, SDRL은 2022-10-14, BORR은 2019-07-31 이후 해당 상장 주식만 사용합니다. 구조조정으로 취소된 구주·OTC·다른 통화의 상장 주가와 연결하지 않습니다. 경계 확인 출처는 등록 파일의 `listing_source`입니다.
- 실적은 공급자가 제공하는 2022년 이후 확보 구간부터입니다. Seadrill은 2023년 완결 연간 EPS부터 확보했습니다. 초기 BPS는 연간 값이며, 분기별 원자료가 없는 구간을 추정하지 않습니다.
- PER은 실제 TTM 희석 EPS(완결 연간 포함), PBR은 보통주 귀속 자본 / 동일 기말 보통주 수 기준입니다. 적자·0 이하·미확보 값은 N/M입니다.
- ODL.OL 주가는 NOK, 실적은 USD이므로 해당 거래일의 USD/NOK로 EPS·BPS를 변환합니다. 환율이 없으면 계산하지 않습니다.
- 자동 배수는 2022년 이후 양의 유효 배수 중앙값의 0.5·0.75·1·1.25·1.5배. 밴드는 주가 단위의 참고선입니다. 보고 손익의 일회성 항목을 제거하지 않으며 회계기간 기준 참고치로 공시일 당시의 투자 정보를 재현하지 않습니다.
- 매일 08:30 KST `update-offshore-valuation.yml`에서 갱신합니다. 선대 수집과 분리하며, 실패 시 마지막 성공 자료를 유지하고 확인 필요 상태를 표시합니다.

검증: `python -m unittest discover -s scripts -p test_offshore_valuation.py -v`, `python scripts/verify_offshore_valuation_ui.py --url http://127.0.0.1:8811/`.

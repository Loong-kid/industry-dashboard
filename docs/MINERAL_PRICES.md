# 우라늄·희토류 가격

`scripts/fetch_mineral_prices.py`가 기타 원자재 탭의 세 카드를 생성한다.
API 키나 로그인이 필요하지 않으며 일일 `update-data.yml`에서 실행한다.

## 우라늄

- 원문: https://www.cameco.com/invest/markets/uranium-price
- 현물과 장기계약 지표는 U₃O₈ 기준 USD/lb의 **월말 가격**이다. 월평균이나 일별 선물 종가로 표시하지 않는다.
- Cameco는 UxC와 TradeTech의 월말 가격을 평균한다. 2004년 5월 이전 장기 가격은 TradeTech 단일 자료원이다.
- 최초 확인: 현물 1988-01~2026-09, 465개월; 장기 1996-03~2026-09, 367개월.
- 날짜·현물·장기 가격이 함께 있는 숨김 HTML 표를 헤더로 식별한다. 최근 5개년 요약 표를 읽지 않는다.
- 구간에 따라 월초로 표기된 원문 날짜도 해당 월말로 통일한다. 같은 달의 동일한 중복 행은 제거하고 서로 다른 가격이면 실패한다.
- 장기 가격의 초기 빈칸은 관측치 없음으로 유지한다. 0이나 현물 가격으로 채우지 않는다.

## 희토류 산화물

- 화면: https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals
- KOMIS의 공개 화면이 사용하는 POST 응답을 읽는다. 공식적으로 보장된 외부 OpenAPI라고 부르지 않는다.
- 가격 기준은 **순도 99.5% 이상, FOB China, USD/kg**. 금속·내수·다른 순도의 가격과 합치지 않는다.
- 네오디뮴: `MNRL1001`, 가격기준 `757`, `Neodymium Oxide`; 최초 확인 2010-07-02~2026-09-24, 3,753개.
- 디스프로슘: `MNRL1004`, 가격기준 `803`, `Dysprosium Oxide`; 최초 확인 2013-03-21~2026-09-24, 3,128개.
- `getMnrlPriceCrtr`에서 상품명·순도·가격기준 ID를 먼저 검증하고 `getMnrlPrcByMnrkndUnqCd`의 `data.defaultMnrl`을 읽는다.
- `dataAvg.INFO`의 광종명·통화·중량단위·인도조건, 최신가격 요약과 행의 일치 여부를 확인한다.
- 과거 일부 행의 최저/최고 가격 0/0은 범위 미제공을 뜻한다. 실제 가격은 `cmercPrc`이며 0/음수/비유한 값은 거부한다.
- **2026년 자료원 변경:** KOMIS는 2026년 1월부터 희토류 등 자료원을 단계적으로 변경한다고 공지한다. 같은 규격도 과거와 차이가 날 수 있다. 공지에는 품목별 정확한 전환일이 없어 임의의 단절 날짜를 만들지 않는다. 카드에 비교 주의사항을 표시한다.
- 일자별 게시값이지만 매일 새로운 거래나 가격 변화를 뜻하지 않는다. 현재 화면은 ISE를 자료원으로 표시한다.

## 갱신·실패 처리

```powershell
python scripts/fetch_mineral_prices.py
python scripts/fetch_mineral_prices.py --backfill
python -m unittest discover -s scripts -p test_mineral_prices.py
node scripts/test_mineral_cards.cjs
```

최초에는 전체 이력을 읽는다. 이후 희토류는 현재·직전 연도를 재확인하고 기존 오래된 관측치를 보존한다. `--backfill`은 전체 이력을 다시 확인한다.
원문의 같은 날짜 정정은 반영한다. 미래 날짜·규격 변경·잘못된 가격·최신일 역행·빈 응답은 기존 파일을 덮어쓰지 않는다. 각 카드가 독립적으로 수집되어 한 소스 실패가 다른 카드 수집을 막지 않는다.

`fetched`는 한국 시간 수집일, `updated`는 실제 자료 기준일이다. 수집에 성공해도 자료 기준일이 오래되면 카드에 경고한다(우라늄 70일, 희토류 21일).

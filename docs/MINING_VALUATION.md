# 광산기업 주가·PER·PBR

원자재 → 광산기업 탭의 기존 10개사(BHP, Southern Copper, Rio Tinto, Newmont, Zijin Mining, Freeport-McMoRan, Grupo México, Agnico Eagle, Glencore, Barrick Mining)에 기업별 주가·실적 PER·PBR 밴드를 붙였다. 각 회사 매출·영업이익·CAPEX 바로 아래에 세 차트를 둔다. 상단 비교 표는 기존 순위와 광물 매출 구성 표 다음에 배치하며 10개사의 종가·통화·실적 기준일·배수를 비교하고 기업 차트로 이동한다.

주가는 거래소 통화 그대로 표시한다. 기존 기업 재무 차트의 통화와 환산 방식은 바꾸지 않는다. EPS/BPS의 원공시 통화를 보존하고 해당 거래일의 환율로 주가 통화에 맞춘 뒤 배수를 계산하므로 PER/PBR은 통화와 무관하게 비교할 수 있다. 영국 GBp는 펜스로 100 GBp=1 GBP다. USD/GBP 원환율에 100을 곱해 EPS/BPS를 펜스로 환산하며 허구의 `USDGBp=X`를 요청하지 않는다.

| 회사 | 선택 종목 | 주가 통화 | 보고 EPS/BPS |
|---|---|---|---|
| BHP | ASX BHP.AX 보통주 | AUD | USD |
| Southern Copper | NYSE SCCO | USD | USD |
| Rio Tinto | LSE RIO.L plc 보통주 | GBp | USD |
| Newmont | NYSE NEM | USD | USD |
| Zijin Mining | HKEX 2899.HK H주 | HKD | CNY |
| Freeport-McMoRan | NYSE FCX | USD | USD |
| Grupo México | BMV GMEXICOB.MX B주 | MXN | USD |
| Agnico Eagle | NYSE AEM 보통주 | USD | USD |
| Glencore | LSE GLEN.L 보통주 | GBp | USD |
| Barrick Mining | TSX ABX.TO 보통주 | CAD | USD |

BHP의 NYSE ADS는 보통주 2주에 해당하므로 ASX 보통주를 선택해 보통주 EPS와 비율을 맞췄다. [회사 FAQ](https://www.bhp.com/investor-centre/shareholder-information/frequently-asked-questions). Rio는 DLC 그룹의 보통주 주당 기준이며 London plc 보통주 가격을 쓴다. [Rio FAQ](https://www.riotinto.com/invest/shareholder-information/shareholder-faqs). Glencore 회사 주가는 LSE GBp로 표시된다. [회사 IR](https://www.glencore.com/investors). Barrick의 NYSE 심볼은 2025-05-09 GOLD에서 B로 바뀌었고 TSX ABX는 유지됐다. 이전 B 법인의 가격 혼입을 피하려고 ABX를 쓴다. [회사 공지](https://www.barrick.com/English/news/news-details/2025/barrick-Is-now-B-on-the-NYSE/default.aspx). Zijin은 HKEX H주로 A주와 구분한다. [회사 IR](https://www.zijinmining.com/investor/invest_cen.htm).

무료 Yahoo completed-session Close(분할 반영, 배당 재투자 제외), reported fundamentals와 일별 환율을 사용한다. 종가는 2014년 이후 확보 이력, 밴드는 EPS/BPS가 확보된 2022~2023년 이후만 표시한다. 자료 없는 초기 구간을 생성하지 않는다. 영국·호주 등의 반기 공시 주기는 원래 공시 간격을 유지하고 임의 분기 EPS를 만들지 않는다. Grupo México의 미검토 분할 이전 TTM은 공유 검증대로 제외하며 제공된 연간 EPS는 유지한다. 적자 EPS와 0 이하 순자산은 N/M, PER 적자 구간은 단절·음영 처리한다. Newmont와 Glencore의 음수 원자료도 보존한다. 손상차손 등을 빼는 조정 EPS나 전망을 쓰지 않는다. 밴드는 재작성된 결산기준으로 공시일 당시 투자 정보의 백테스트가 아니다. 환율은 7일, 실적은 460일 이후 만료한다.

SCCO/FCX는 `data/commodities/valuation/`의 기존 구리 자료를 재사용한다. 새로운 수집이 두 파일을 덮어쓰지 않으며 같은 기업의 사용자 PER 배수 설정도 두 탭에서 공유한다. 신규 8개사 파일과 10개사 목록은 `data/commodities/mining-valuation/`에 둔다. 독립 `update-mining-valuation.yml`은 매일 **08:25 KST**, 기존 구리 갱신은 08:20 KST다. 원자료 실패 시 마지막 성공 이력·환율을 유지하고 확인 필요 상태를 표시한다. 회사 파일은 화면 근처에서만 불러와 큰 탭에서도 초기 비용을 줄이고 화면 밖 차트를 정리한다.

USD 환율은 공급자가 `CAD=X`/`USDCAD=X`, `GBP=X`/`USDGBP=X`처럼 같은 쌍을 두 이름으로 반환할 수 있다. 동일 USD 환율의 확인된 별칭만 허용하며 다른 통화쌍·표시 통화가 오면 검증 실패로 보존 처리한다.

수집 `python scripts/fetch_mining_valuation.py`, 검증 `python -m unittest discover -s scripts -p test_mining_valuation.py -v`. 공개 원본 캐시는 `.cache/mining-valuation/`, API 키나 유료 데이터는 필요 없다.

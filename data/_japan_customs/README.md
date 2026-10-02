일본 재무성 블랭크마스크 관련 수출통계
====================================

`exports.json`은 e-Stat 공개 CSV에서 추출한 HS 370199000·370130000의
연도별 국가·월별 원단위 기록과 공표 메타데이터다. 배열 순서는
`[HS, 월(YYYY-MM-01), 일본 국가코드, 수출금액(천 엔), Quantity2(㎡)]`.

```sh
python scripts/fetch_japan_customs.py
python scripts/fetch_japan_customs.py --refresh
python -m unittest discover -s scripts -p test_japan_customs.py
node scripts/test_japan_customs.cjs
```

2021년부터 매일 각 연도 최신 표의 공표일·파일 ID·기간을 확인하며,
변경된 표만 다시 다운로드한다. 해당 연도의 국가·월별 기록 전체를
교체하여 하향 정정이나 삭제된 거래도 반영한다. 모든 연도 파싱과
월 합계/YTD 대조가 성공한 뒤 저장한다. 수집 실패 시 기존 파일을 보존한다.
API 키·로그인이 필요 없다. 자동 갱신은 update-data 워크플로에 포함한다.

CSV에는 Jan~Dec 월별 열과 Year 누적 열이 함께 있다. 누적 열은 검증에만
쓰며 공표 제목의 월까지만 추출한다. 아직 공표되지 않은 달의 0은 저장하지
않는다. 한 국가가 해당 연도에 전혀 없는 경우 공표된 달은 거래 0으로 처리한다.
금액은 천 엔→백만 엔으로, 면적은 SM=㎡로 표시한다. 면적당 수출액은
합산 금액(엔)/합산 면적이며 면적 0이면 null이다. 보간하지 않는다.

주지표 370199000은 KOTRA의 일본 블랭크마스크 분석에서 사용한 코드이나
일본 세관상 반도체·EUV 전용은 아니다. 370130000은 한 변이 255mm를
넘는 감광 플레이트/평면 필름으로 디스플레이 외 인쇄용 등도 섞이는
보조지표다. 두 코드 모두 제조사·EUV/DUV 구분 및 일본 밖 생산을 추적할 수 없다.
한국의 반도체 전용 코드 및 USD/kg 단가와 직접 비교하지 않는다.

출처:
- [재무성 공개 다운로드 안내](https://www.customs.go.jp/toukei/info/tsdl_e.htm)
- [e-Stat 품목별 국가별 수출](https://www.e-stat.go.jp/en/stat-search/files?cycle=1&layout=datalist&tclass1=000001013180&tclass2=000001013181&toukei=00350300&tstat=000001013141)
- [2026년 일본 수출 품목표 제37류](https://www.customs.go.jp/yusyutu/2026_01_01/data/j_37.htm)
- [일본 국가코드](https://www.customs.go.jp/toukei/sankou/code/country_e.htm)
- [KOTRA 일본 블랭크마스크 시장 동향](https://dream.kotra.or.kr/user/extra/kotranews/bbs/linkView/jsp/Page.do?dataIdx=198224)

초기 수집 교차 검증: 370199000의 2021년 월별 세계 수출 합계
41,228,338천 엔 및 한국향 4,112,847천 엔은 KOTRA 표와 일치한다.

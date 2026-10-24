# 게임 시장 관측

경로: `#/games` — 시장 규모 / Steam 장르 / Google Play / App Store 차트 / 게임별 매출 / 게임사 실적 / 게임 플랫폼 / 출처·범위. 기존 `#/games/mobile` 주소는 Google Play 화면으로 유지한다.

## 화면 설계

기존 대시보드의 `--page`, `--surface`, `--ink`, `--accent`와 시스템 한글 글꼴을 사용한다. 데이터 색은 기존 파랑 `#2a78d6`, 초록 `#1baf7a`, 노랑 `#eda100`을 잇는다. 왼쪽 정렬, 표의 숫자는 오른쪽 정렬한다. 시장 개요는 플랫폼 규모와 탐색 링크를 두 열로, 장르 화면은 넓은 추이 차트와 비중 지도로 구성한다. 모바일에서는 한 열로 전환하고 표 안에서만 가로 스크롤한다. 통일된 카드 장식을 늘리기보다 차트·표의 비교 기준을 드러낸다.

## 무료 자료와 갱신

- **SteamCharts:** 직접 선정한 57개 게임의 월평균·월 최고 동시접속자 과거 기록. 완료된 달만 가져온다. 고정 표본이며 전체 Steam 시장의 점유율이 아니다. 대표 장르는 `scripts/fetch_games.py`의 `STEAM`에서 직접 관리한다.
- **Google Play:** 장르별 공개 목록에서 발견한 표본과 주요 게임 목록의 공개 누적 다운로드 하한·평점·평가 수. 국가 US로 조회하지만 누적 다운로드 하한은 전 세계 값이다. 일별 관측을 보존하고 월별 마지막 관측값을 표시한다. 하한의 차이를 월 다운로드로 계산하지 않는다.
- **AppBrain:** 로그인 없이 보이는 17개 게임의 최근 30일·누적 설치 추정치를 직접 확인해 `manual/games/download-estimates.json`에 출처·기준일과 함께 기록했다. 반올림 추정치이고 기준일이 다르므로 동일 기간 시장 합계가 아니다. HTTP 자동 조회가 제한되어 일일 자동 수집 대상에 포함하지 않는다. 새 확인 없이 날짜를 바꾸지 않는다. 유료 상세 이력에 접근하지 않는다.
- **Apple:** 공식 게임 전용 RSS, 한국·미국·일본·중국의 무료·유료 Top 100. 공식 lookup에서 첫 게임 세부 장르를 조회한다. 원래 순위를 보존하며 다운로드·매출을 역산하지 않는다. 일별 차트 이력을 보존한다.
- **시장 규모:** Newzoo 2026-06-18 공개 발표의 2025년 시장 추정치와 발표 YoY. 과거 추이는 [2026-03-16 공개 공시](https://kind.krx.co.kr/external/2026/03/16/002677/20260316007552/11011.htm)에 인용된 동일 판본의 2021–2024년 표를 사용한다. 두 판본을 연결하거나 판본 간 성장률을 계산하지 않는다. 무료 발표를 확인한 경우에만 `manual/games/market.json`을 갱신한다.
- **Appfigures 공개 월간 보고서:** 2025-08·2025-12·2026-01·2026-08의 스토어별 Top 10, 총 120개 매출 관측. 로그인 없이 공개한 원본 표를 대조해 `manual/games/revenue-reports.json`에 기록했다. [공개 보고서 목록](https://appfigures.com/resources/tagged/games), 각 보고서·이미지·발표일·대조일 링크를 보존한다. Apple/Google 수수료 차감 후의 월간 스토어 매출 **추정치**다. 광고·외부 결제·개발비·마케팅비를 포함한 게임 전체 손익이 아니다. 이미지의 반올림 값을 보존하며 합산 스토어 값을 개별 Top 10으로 재구성하지 않는다. 유료 Intelligence API는 사용하지 않는다. 새 원문을 확인해야 추가되는 수기 자료다.
- **SEC Company Facts:** EA·Take-Two·Roblox·Playtika·NetEase·Gravity의 2020년 이후 구조화 재무 공시. [SEC API 문서](https://www.sec.gov/edgar/sec-api-documentation)에 따른 식별 User-Agent를 사용한다. 외국 상장사는 구조화 데이터가 연간에 한정되거나 최신 IR보다 늦을 수 있다. 통화는 원통화 USD/CNY/KRW, 단위는 백만이다. 최신 제출된 동일 기간 값으로 수정 공시를 반영하고 각 지표의 계정·접수번호 링크·제출일·계산 근거를 저장한다.
- **OpenDART:** 크래프톤·넷마블·NC·펄어비스·컴투스의 연결 재무제표. 기존 CI의 무료 `DART_API_KEY`를 환경변수로 재사용한다. [단일회사 전체 재무제표 문서](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020)의 손익계산서 `thstrm_amount`는 3개월, `thstrm_add_amount`는 누적값이므로 구분한다. 연결 KRW 계정만 사용하고 별도 재무로 대체하지 않는다. 최초 2020년부터 수집하고 이후 최근 2개 회계연도를 다시 확인한다. 키가 없거나 요청이 실패하면 회사별 기존 자료와 실제 수집일을 유지한다. 키와 키가 포함된 URL·오류 메시지를 저장하지 않는다.
- **공식 IR 대조:** Tencent·Nexon·NC의 공개 실적 발표와 NC의 일부 타이틀 매출을 원문 대조해 `manual/games/company-financials.json`, `revenue-reports.json`에 기록했다. 확인일을 보존하며 자동 수집한 것처럼 날짜를 바꾸지 않는다. Tencent는 IFRS 이익으로 통일하고 광고·핀테크 등을 포함한 연결 전체라는 범위를 표시한다.

`update-games.yml`이 매일 KST 07:20에 자동 수집한다. 유료 구독·체험판은 사용하지 않는다. OpenDART만 기존 무료 키를 사용하고 나머지 수집은 키가 필요 없다. GitHub Actions 무료 제공량 내에서 기존 공개 저장소 방식으로 실행한다. 수집 실패 항목은 기존 값과 실제 수집일을 유지하며 개수는 출처 화면에 표시한다. 심각한 커버리지 저하나 파서 변경 시 해당 파일을 교체하지 않고 실패한다. 완료 후 기존 Pages 워크플로가 배포한다.

페이지가 매년 수백 개의 일별 차트를 전부 받지 않도록 최근 35일의 일별 관측과 각 월의 마지막 실제 관측값을 보관한다. 월말 관측이 없다면 마지막으로 관측한 실제 날짜를 표시한다. 월별 비교용 이력은 계속 누적한다.

게임사 수집은 회사별 독립 세션으로 최대 3개 요청을 동시에 처리한다. 국내 최초 이력은 최신 회계연도부터 확인하고, 3회 연속 오류가 나면 해당 회사의 조회를 중단해 기존 자료를 보존한다. 요청 실패로 값이 유지되었을 때 마지막 성공 수집일을 새 날짜로 바꾸지 않는다.

국내 5개사의 고유번호는 DART 공식 기업정보 팝업의 회사명·종목코드와 대조해 고정하고(`https://englishdart.fss.or.kr/dsbc001/selectPopup.ax?selectKey=<고유번호>`), 응답의 회사 고유번호도 검증한다. 대형 전체 회사목록 ZIP 다운로드에 매일 의존하지 않는다. 펄어비스는 2026년 CCP 매각 전후 연결 범위가 다르므로 브랜드 안내에도 해당 사실을 표시한다.

```powershell
python scripts/fetch_games.py
python scripts/fetch_game_financials.py
python scripts/fetch_game_platforms.py
# 신규 Google Play 공개 표본 발견은 필요할 때만 실행
python scripts/fetch_games.py --source mobile --discover
python -m unittest discover -s scripts -p test_games.py
python -m unittest discover -s scripts -p test_game_financials.py
python -m unittest discover -s scripts -p test_game_platforms.py
node scripts/test_games.cjs
```

## 계산과 범위

월별 Steam 장르 이용량 = 해당 월의 표본 게임별 평균 동시접속자 합. 연간은 관측 월의 일수 가중평균이며, 현재 연도는 포함한 월을 표시한다. 동시접속자의 합은 고유 이용자 수나 다운로드 수가 아니다. 출시 전과 누락된 기간을 임의 생성하지 않는다. 비교 시 같은 기간·표본 범위를 확인한다.

모바일 달력 기준 월 다운로드·국가별 다운로드·과거 전체 다운로드 이력·Steam 개별 게임의 연속 매출·원스토어 연속 실적은 무료로 확보하지 못했다. 해당 값은 0 또는 허구의 추정치로 채우지 않는다. 관측 누적값·최근 30일 추정치·차트 순위를 서로 다른 지표로 표시한다. 스토어에 남은 게임과 대표 게임 위주의 선정 편향이 있다. 플랫폼 간 장르 분류와 표본 범위도 다르다.

퍼블리셔별 매출 소계는 **동일 월·동일 스토어의 공개 Top 10 안에서만** 합산한다. 합산 스토어 + 개별 스토어를 중복 합산하지 않는다. 앱·지역 버전은 원문 범위를 유지하며 Honor of Kings 중국 iOS판을 글로벌 앱 전체로 확장하지 않는다. 보고서에 없는 게임/월은 미확보이며 전월·전년 동월의 동일 앱·스토어 값이 있을 때만 변화율을 계산한다. 원문이 일부 정수/일부 소수로 반올림했기 때문에 스토어 간 합계가 정확히 일치하지 않을 수 있다.

게임사 화면은 같은 통화·기간 유형·실제 결산일의 값만 비교한다. 다른 통화를 합산·환산하거나 회사별 서로 다른 최신 분기를 같은 분기처럼 순위 매기지 않는다. EA·Take-Two의 3월 결산 FY는 실제 날짜에 따라 표시한다. 3개월 공시 우선, 누적 차감은 같은 회계연도 시작과 같은 회계 체계일 때만 허용한다. 연간÷4 금지. Q4는 연간−9개월이 가능한 경우에만 생성한다. 회사 연결 매출과 게임 스토어 수수료 차감 후 추정 매출, 개발사 로열티, 게임 순이익은 각각 다르다. 비상장사의 전체 손익은 공개 자료가 없으면 미확보다.

시장 매출은 시장 규모 추정치이지 잠재적 최대 수요(TAM)의 실측값이 아니다. 스토어 다운로드 표본으로 세계 매출, 광고·외부 결제 매출 또는 고유 이용자 수를 복원하지 않는다.

## 해외 업체와 플랫폼

2026-10-25 확장 기준 27개 업체(해외 21개, 7개 국가)를 다룬다. 재무 이력이 있는 회사·사업부는 25곳이며 비상장 Epic·Valve는 공식 사업 지표를 연결한다. 지역은 업체의 본사·사업 근거지/상장 법인에 따른 탐색 분류이며 매출 발생 국가가 아니다. `manual/games/company-directory.json`의 지역·사업·소유 상태·비교 범위·검색 별칭을 모든 회사 데이터에 결합한다. 전 세계 전체 목록을 통화 필터 앞에 두고 기본 통화를 USD로 변경해 해외 업체가 KRW 필터에 가려지지 않도록 했다.

기존 색상 파랑 `#2a78d6`, 초록 `#1baf7a`, 노랑 `#eda100`, 보라 `#4a3aa7`, 적색 `#e34948`과 시스템 글꼴을 유지한다. 전체 업체 목록 → 같은 통화의 공시 비교 → 개별 회사 추이로 읽는다. 플랫폼은 사업 모델을 비교하는 표와 선택 업체의 실제 지표를 배치한다. 금액·분모·관측일을 함께 표시하며 통화가 다른 행을 금액순으로 정렬하지 않는다. Microsoft·Sea·Tencent는 게임 외 대형 사업을 포함하므로 기본 공시 비교에서 제외하고 선택 시 포함할 수 있다. 전체 목록에는 항상 남으며 해당 업체의 ‘실적 보기’는 자동으로 포함 설정을 켠다.

- **SEC 추가:** Unity, AppLovin, Microsoft, Sea. 공시 원통화 USD, 백만 단위. Microsoft의 7월 회계연도 시작을 반영한다. 최대 3개 동시 요청과 SEC 요청 시작 간격 0.35초를 적용한다. `--company <id>`를 반복 지정하면 해당 회사만 조회하고 나머지의 값·날짜·상태를 유지한다.
- **공식 해외 IR 추가:** Nintendo, Sony G&NS, Bandai Namco, SEGA SAMMY, Square Enix, Konami, Capcom, CD PROJEKT. `manual/games/global-financials.json`에 원문 URL·실제 기간·공시일·PDF 실제 페이지(표지 포함)·금액 단위·순이익 기준을 저장했다. 직접 공개한 분기·연간 값만 입력하고 빈 분기는 생성하지 않았다. 일본 업체의 지배기업 소유주 귀속 이익, Sony 사업부의 순이익 미공개, CD PROJEKT의 계속영업 재표시·중단영업 포함 순이익을 표시한다. [CD PROJEKT 원문](https://www.cdprojekt.com/en/investors/financial-summary-report/)의 PLN 천 단위를 백만 단위로 변환했다. 화면 FY는 결산연도 기준이므로 Sony의 원문 FY2025(2026년 3월 종료)는 화면 FY2026이다.
- **AppLovin 재표시:** [2026년 2분기 공식 발표](https://investors.applovin.com/news/news-details/2026/AppLovin-Announces-Second-Quarter-2026-Financial-Results/default.aspx)의 계속영업과 전체 순이익이 구분된다. 게임 사업 중단영업 재표시로 최신 연간과 오래된 누적 분기의 범위가 다를 수 있어 Q4 누적 차감을 사용하지 않는다. 비교 가능한 재표시 연간은 2023년부터, 공시된 단독 분기는 2025년부터 제공한다. 해당 기간 밖을 0으로 채우지 않는다.
- **EA 비상장 전환:** [2026-08-04 EA 공식 발표](https://www.ea.com/ea-studios/ea-sports/news/ea-announces-completion-of-acquisition)에 따라 비상장으로 표시하고 인수 전 SEC 실적은 보존한다. 이후 정기 공시가 계속 나온다고 가정하지 않는다.
- **Epic Games / Unreal Engine:** [EGS 2024](https://store.epicgames.com/en-US/news/epic-games-store-2024-year-in-review), [EGS 2025](https://store.epicgames.com/en-US/news/epic-games-store-2025-year-in-review) 공식 보고서에서 PC 스토어 지출·서드파티 지출·연평균 MAU·연중 최고 MAU·누적 이용자·계정을 기록했다. [Fab 2025](https://www.unrealengine.com/news/fab-2025-year-in-review)는 창작자 수익·판매자·등록 상품을 제공한다. EGS 이용자 지출은 거래 규모이며 Epic/Unreal 매출·이익이 아니다. 자체 결제로 발생한 서드파티 지출은 EGS 결제 지표에서 제외된다. ‘초과’ 하한을 보존한다.
- **Valve / Steam:** [공식 온라인 통계](https://store.steampowered.com/stats/?l=english)를 매일 조회해 동시 온라인과 화면의 최고값을 누적한다. 게임 미실행 계정 포함이며 MAU·월간 다운로드·매출로 환산하지 않는다. 화면의 `PEAK ONLINE` 집계창을 임의로 일간·월간·역대 최고라고 명명하지 않는다. 관측 시각은 UTC 원본과 KST 표시를 제공하고 최근 35일 이후에는 월별 마지막 실제 관측을 유지한다. 파싱·접근 실패 시 이전 관측값·수집 시각을 보존한다.
- **PlayStation·Nintendo·Xbox:** Sony의 PlayStation MAU/PS5 보급, Nintendo의 하드웨어 판매/디지털 매출, [Microsoft 연차보고서](https://www.microsoft.com/investor/reports/ar26/index.html)의 Xbox 제품·서비스 매출을 별도 지표로 기록했다. Microsoft 전사 매출·순이익을 Xbox 단독 값으로 표시하지 않는다.

`manual/games/platforms.json`은 8개 플랫폼의 사업 모델·기업 관계·공개 지표 원본이다. 스토어 거래액, 회계 매출, 창작자 수익, 누적 계정, 활성 이용, 동시 온라인, 하드웨어 대수를 서로 합산하지 않는다. 같은 지표·단위·정의의 이력만 차트로 연결하며 Steam 관측은 점으로만 표시한다. 수기 자료는 원문 확인 날짜를 보존한다. 유료 API·체험판·로그인 후 프리미엄 자료는 사용하지 않는다.

각 화면은 필요한 JSON만 내려받는다. 시장 개요는 시장 자료만, 플랫폼은 회사·플랫폼 자료만 읽으며 모든 소스의 현황을 읽는 것은 출처 화면뿐이다. 갱신 표시도 로드한 소스의 조회일·발표일·원문 대조일을 구분한다.

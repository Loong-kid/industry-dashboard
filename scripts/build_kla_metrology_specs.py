"""KLA metrology product table, from KLA's own product pages, brochures and press releases.

Every product family listed on KLA's chip-manufacturing metrology page (plus irArcher from the packaging page)
is one row. Values come from three kinds of KLA source, each cited per cell (checked 2026-11-27):
  p_*  product pages (kla.com, anchored to the product)
  b_*  product brochures / fact sheets (kla.com PDFs)
  r_*  KLA / KLA-Tencor press releases (ir.kla.com), which give launch dates and quoted figures
KLA publishes few numeric specs; anything it does not state is left blank.

    python scripts/build_kla_metrology_specs.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/semicon/kla_metrology_specs.json'
CHECKED = '2026-11-27'
METRO = 'https://www.kla.com/products/chip-manufacturing/metrology'
IR = 'https://ir.kla.com/news-events/press-releases/detail/'

COLUMNS = [
    dict(id='name', label='제품', width=170),
    dict(id='measures', label='측정 대상', width=220),
    dict(id='method', label='측정 원리', width=190),
    dict(id='launched', label='최근 공식 발표', width=120, date=True),
    dict(id='figures', label='공개 수치', width=280),
    dict(id='nodes', label='대상 소자·노드', width=230),
    dict(id='lineup', label='모델 라인업 (발표)', width=280),
    dict(id='tech', label='핵심 기술', width=300),
    dict(id='apps', label='용도', width=240),
    dict(id='features', label='특징', width=320),
    dict(id='page', label='공식 페이지', width=100, url=True),
]
VIEWS = [
    dict(id='overview', label='한눈에 보기', keys=['name', 'measures', 'method', 'launched', 'figures', 'nodes']),
    dict(id='detail', label='전체 사양', keys=['name', 'measures', 'method', 'launched', 'figures', 'nodes', 'lineup', 'tech', 'apps',
                                            'features', 'page']),
]
GROUPS = ['오버레이', 'CD·3D 형상', '박막', '웨이퍼 형상', '이온주입·면저항', '자성 (MRAM)', '복합 (검사·계측·리뷰)']

SOURCES = {
    'p_archer': ('KLA · Archer 제품 페이지', METRO + '#archer'),
    'p_atl': ('KLA · ATL 제품 페이지', METRO + '#atl'),
    'p_archer_power': ('KLA · Archer Power 제품 페이지', METRO + '#archer-power'),
    'p_irarcher': ('KLA · irArcher 제품 페이지 (첨단 패키징)',
                   'https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging#irarcher'),
    'p_spectrashape': ('KLA · SpectraShape 제품 페이지', METRO + '#spectrashape'),
    'p_axion': ('KLA · Axion 제품 페이지', METRO + '#axion'),
    'p_spectrafilm': ('KLA · SpectraFilm 제품 페이지', METRO + '#spectrafilm'),
    'p_aleris': ('KLA · Aleris 제품 페이지', METRO + '#aleris'),
    'p_pwg': ('KLA · PWG 제품 페이지', METRO + '#pwg'),
    'p_therma': ('KLA · Therma-Probe 제품 페이지', METRO + '#therma-probe'),
    'p_microrsp': ('KLA · CAPRES microRSP 제품 페이지', METRO + '#capres-microrsp'),
    'p_ciptech': ('KLA · CAPRES CIPTech 제품 페이지', METRO + '#capres-ciptech'),
    'p_pkmram': ('KLA · MicroSense PKMRAM 제품 페이지', METRO + '#pkmram'),
    'p_kerr': ('KLA · MicroSense KerrMapper 제품 페이지', METRO + '#kerrmapper'),
    'p_omnimap': ('KLA · OmniMap RS-200P 제품 페이지', METRO + '#omnimap-rs-200p'),
    'p_circl': ('KLA · CIRCL 제품 페이지', METRO + '#circl'),
    'b_archer800': ('KLA · Archer 800 제품 소개서 (Rev 1.4, 2025-05)', 'https://www.kla.com/wp-content/uploads/Archer_800_Rev1.4_May_16_2025_DIGITAL.pdf'),
    'b_pwg5': ('KLA · PWG5 브로셔 (Rev 1.1, 2021-09)', 'https://www.kla.com/documents/products/brochures/PWG5_Rev1.1_Sep_20_21_PRINT.pdf'),
    'b_axion': ('KLA · Axion T2000 팩트시트 (2022)', 'https://www.kla.com/wp-content/uploads/KLA_Axion_T2000_ProductFactSheet.pdf'),
    'r2007_aleris': ('KLA-Tencor 보도자료 2007-12-02 · Aleris 8500 (Aleris 제품군 시작)',
                     IR + '351/kla-tencors-new-aleris-8500-film-metrology-system-is'),
    'r2007_therma': ('KLA-Tencor 보도자료 2007-05-25 · Therma-Wave 인수 완료',
                     IR + '369/kla-tencor-completes-acquisition-of-therma-wave'),
    'r2008_aleris': ('KLA-Tencor 보도자료 2008-01-29 · Aleris 8310·8350',
                     IR + '345/kla-tencor-extends-the-aleristm-film-metrology-family'),
    'r2010_aleris': ('KLA-Tencor 보도자료 2010-08-04 · Aleris 8330', IR + '261/kla-tencor-introduces-the-new-aleris-8330-film-metrology'),
    'r2012_archer500': ('KLA-Tencor 보도자료 2012-09-05 · Archer 500', IR + '204/kla-tencor-announces-new-archer-500-overlay-metrology'),
    'r2012_circl': ('KLA-Tencor 보도자료 2012-04-23 · CIRCL', IR + '216/kla-tencor-announces-new-circl-suite'),
    'r2013_ss9000': ('KLA-Tencor 보도자료 2013-02-25 · SpectraShape 9000',
                     IR + '197/kla-tencor-announces-two-additions-to-lithoetch-process'),
    'r2014_pwg': ('KLA-Tencor 보도자료 2014-08-26 · WaferSight PWG', IR + '157/kla-tencor-introduces-key-systems-for-5d-patterning'),
    'r2015': ('KLA-Tencor 보도자료 2015-02-19 · Archer 500LCM · SpectraFilm LD10',
              IR + '144/kla-tencor-extends-its-5d-patterning-control-solution'),
    'r2017_feb': ('KLA-Tencor 보도자료 2017-02-22 · Archer 600 · WaferSight PWG2 · SpectraShape 10K',
                  IR + '106/kla-tencor-introduces-new-metrology-systems-for'),
    'r2017_sep': ('KLA-Tencor 보도자료 2017-09-11 · ATL · SpectraFilm F1',
                  IR + '95/kla-tencor-introduces-five-patterning-control-systems-for'),
    'r2020_feb': ('KLA 보도자료 2020-02-24 · Archer 750 · SpectraShape 11k', IR + '24/kla-introduces-new-ic-metrology-systems'),
    'r2020_dec': ('KLA 보도자료 2020-12-10 · PWG5', IR + '390/kla-introduces-two-new-systems-that-take-on-semiconductor'),
    'r2022_axion': ('KLA 보도자료 2022-12-06 · Axion T2000', IR + '447/kla-launches-revolutionary-x-ray-metrology-system'),
}
NOTES = {'p': '제품 페이지 본문.', 'b': '제품 소개서·브로셔 PDF.', 'r': '보도자료 원문 (ir.kla.com).'}
REVIEW = {'p': 'KLA 공식 제품 페이지 기재', 'b': 'KLA 제품 소개서 기재', 'r': 'KLA 보도자료 기재'}
NO_FIG = '수치 미기재'

# (id, name, group, page source, fields). A value is text (cites the product page) or (text, source id).
PRODUCTS = [
    # --- 오버레이 ---
    ('archer', 'Archer (최신 Archer 800)', '오버레이', 'p_archer', dict(
        measures='층간 패턴 정렬 오차(오버레이) · 명시야 CD', method='이미징 기반 오버레이',
        launched=('2020-02-24', 'r2020_feb'),
        figures=('Archer 600: 오버레이 오차 3 nm 미만 달성 지원 (2017 발표)', 'r2017_feb'),
        nodes='Archer 800: 첨단 메모리·로직 (EUV 포함) · 750: 7 nm 이하 로직 · 600: 10 nm 이하',
        lineup='Archer 800 · 750(2020-02) · 600(2017-02) · 500LCM(2015-02) · 500(2012-09)',
        tech=('층별 최적 조건(PCPL 색상·FPL 초점) · 딥러닝·ML 보정(mTIS·mFocus) · rAIM 타깃 · 다중 신호 측정', 'b_archer800'),
        apps='제품 웨이퍼 오버레이 관리 · 인라인 모니터링 · 스캐너 검증 · 패터닝 관리',
        features='층마다 파장을 바꿔 nm 단위로 맞춤. 고차 스캐너 보정을 위한 샘플링 확대와 인라인용 높은 처리량')),
    ('atl', 'ATL (ATL100)', '오버레이', 'p_atl', dict(
        measures='오버레이 (다이 내·미세 피치 타깃 포함)', method='스캐터로메트리 기반 오버레이 (파장 가변 레이저)',
        launched=('2017-09-11', 'r2017_sep'),
        figures='파장 가변 레이저 해상도 1 nm', nodes='7 nm 이하 개발·양산',
        lineup=('ATL100 (2017-09 발표)', 'r2017_sep'),
        tech='Accurate Tunable Laser · 실시간 Homing으로 공정 편차 속 정확도 유지',
        apps='제품 웨이퍼 오버레이 관리 · 인라인 모니터링 · 스캐너 검증 · 다이 내 측정',
        features='층·소자·노드·패터닝 기법마다 다른 스캐터로메트리 타깃 지원')),
    ('archer-power', 'Archer Power', '오버레이', 'p_archer_power', dict(
        measures='오버레이 · CD', method='오버레이·CD 계측',
        figures='웨이퍼 150·200·300 mm 및 150/200·200/300 mm 겸용 구성',
        nodes='전력 반도체 · 로직·메모리 · LED · 포토닉스 · RF · MEMS 등 특수 소자',
        lineup='Archer Power · Archer Power XT',
        tech='양산 검증된 Archer 오버레이 플랫폼 기반 · 낮은 총 측정 불확도(TMU)',
        apps='R&D·양산 오버레이·CD 모니터링 · 스캐너 검증',
        features='Si·SiC·GaN·GaAs·유리·사파이어 등 기판과 두께가 다른 웨이퍼를 한 라인에서 처리')),
    ('irarcher', 'irArcher 007', '오버레이', 'p_irarcher', dict(
        measures='웨이퍼-웨이퍼(W2W) 본딩 정렬 오버레이', method='단파장 적외선(SWIR) 투과 오버레이',
        figures=NO_FIG, nodes='3D 이종 집적 · W2W 하이브리드 본딩',
        lineup='irArcher 007',
        tech='SWIR 조명으로 기판을 투과해 타깃 측정 · 고속 초점 시스템 · 공장 자동화·APC 연동',
        apps='W2W 오버레이 관리 · 인라인 모니터링 · 패터닝 관리',
        features='연삭 전 본딩 웨이퍼와 휨이 큰 본딩 웨이퍼를 측정, 여러 본더 지원')),
    # --- CD·3D 형상 ---
    ('spectrashape', 'SpectraShape (최신 12k)', 'CD·3D 형상', 'p_spectrashape', dict(
        measures='CD · 3D 형상 (HKMG 리세스·측벽 각도·레지스트·하드마스크 높이·피치 워킹·소자 위 오버레이)',
        method='광학 CD(OCD)·형상 계측', launched=('2020-02-24', 'r2020_feb'), figures=NO_FIG,
        nodes='나노시트(GAA) · finFET · DRAM · 3D NAND',
        lineup='SpectraShape 12k · 11k(2020-02) · 10K(2017-02) · 9010 · 9000(2013-02)',
        tech='개선된 스테이지·새 측정 모듈 · AcuShape 모델링 · TurboShape ML 모델링 · ICON 레시피 자동 갱신',
        apps='인라인 공정 모니터 · 패터닝 관리 · 공정 윈도 확장·관리 · APC',
        features=('10K는 다중 입사각·편광 엘립소미터와 고휘도 반사계를 썼고 파운드리 finFET·3D NAND 주요 메모리 업체에 채택 (2017 발표)', 'r2017_feb'))),
    ('axion', 'Axion T2000', 'CD·3D 형상', 'p_axion', dict(
        measures='고종횡비 구조 3D 형상 (휨·보잉·CD 프로파일·식각 깊이·타원도·기울기)', method=('X선 CD-SAXS (투과 소각 산란)', 'r2022_axion'),
        launched=('2022-12-06', 'r2022_axion'),
        figures=('종횡비 100:1 이상 구조를 위에서 바닥까지 3D로 측정', 'r2022_axion'),
        nodes='3D NAND · DRAM (300 mm)',
        lineup=('Axion T2000 (2022-12 발표)', 'r2022_axion'),
        tech=('고선속 X선 원 · 회절 차수 분리 최대 · 고해상 검출기 · 넓은 입사각 스테이지 · AcuShape 모델링', 'b_axion'),
        apps='공정 특성화·최적화 · 인라인 모니터 · 식각 장비 모니터 · 정비 후 식각 장비 검증',
        features='FIB-SEM·TEM·단면 SEM 같은 파괴 분석을 인라인 비파괴 측정으로 대체')),
    # --- 박막 ---
    ('spectrafilm', 'SpectraFilm (최신 F10·F20)', '박막', 'p_spectrafilm', dict(
        measures='막 두께 · 굴절률 · 응력 · 밴드갭', method='광대역 분광 엘립소메트리(BBSE, 파장 확장)',
        launched=('2017-09-11', 'r2017_sep'),
        figures='F10: 옹스트롬 이하 정밀도',
        nodes='F10: 2 nm 이하 GAA·최신 DRAM · F20: 수백 쌍 적층 3D NAND · F1: 7 nm 이하 · LD10: 16 nm 이하',
        lineup='SpectraFilm F10 · F20 · F1(2017-09) · LD10(2015-02)',
        tech='고휘도 광원 · 파장 범위를 넓힌 BBSE',
        apps='밴드갭 모니터링 · 인라인 공정 모니터 · 장비 모니터 · 장비 간 매칭',
        features='F10은 초격자 HKMG 층을 제어해 문턱전압 분포를 좁힘, F20은 3D NAND 얇은 막·두꺼운 막 모두')),
    ('aleris', 'Aleris (최신 9350)', '박막', 'p_aleris', dict(
        measures='막 두께 · 굴절률 · 응력 · 조성 (범용 막)', method='광대역 분광 엘립소메트리(BBSE)',
        launched=('2010-08-04', 'r2010_aleris'), figures=NO_FIG,
        nodes='9350: 첨단 로직·DRAM·3D NAND · 8510: 28 nm 이하 HKMG · 8350: 32 nm 이하 핵심 막 · 8330: 32 nm 이하 비핵심 막',
        lineup='Aleris 9350 · 8510 · 8350(2008-01) · 8330(2010-08) · 8500(2007-12, 첫 모델)',
        tech='고휘도 광원·새 광학계 · 레시피 이식·플랫폼 간 매칭',
        apps='공정 엔지니어링 분석 · 인라인 공정 모니터 · 장비 모니터 · 장비 간 매칭',
        features=('Aleris 8500은 양산용으로 조성과 다층 막 두께를 함께 재는 업계 첫 장비였음 (2007 발표)', 'r2007_aleris'))),
    # --- 웨이퍼 형상 ---
    ('pwg', 'PWG (최신 PWG5)', '웨이퍼 형상', 'p_pwg', dict(
        measures=('패턴 웨이퍼 휨·보우 · 면내 변위 · 응력 곡률 · 두께·평탄도 · 앞뒷면 나노토포그래피 · 가장자리 롤오프', 'b_pwg5'),
        method=('수직 웨이퍼 고정 · 앞뒷면 동시 측정', 'b_pwg5'), launched=('2020-12-10', 'r2020_dec'),
        figures=('휨 측정 범위 최대 1000 µm · 공간 해상도 40 µm', 'b_pwg5'),
        nodes=('96단 이상 3D NAND · 1X nm 이하 로직·DRAM', 'b_pwg5'),
        lineup='PWG5 · PWG5 XT(본딩 웨이퍼) · PWG3 · WaferSight PWG2(2017-02) · WaferSight PWG(2014-08)',
        tech=('5D Analyzer로 형상 기인 오버레이 보정값을 스캐너에 전달 · WaferSight 플랫폼 기반', 'b_pwg5'),
        apps='공정 모니터링 · 인라인 모니터링 · 노광 오버레이 관리',
        features=('첫 WaferSight PWG는 웨이퍼당 350만 점 측정 (2014 발표)', 'r2014_pwg'))),
    # --- 이온주입·면저항 ---
    ('therma-probe', 'Therma-Probe', '이온주입·면저항', 'p_therma', dict(
        measures='이온주입 선량·프로파일 · 주입·어닐 균일도 · 주입 끝단(EOR) 손상', method='이온주입·어닐 계측',
        figures=NO_FIG, nodes='680XP: 2X/1X nm 실리콘 소자 · 화합물 반도체',
        lineup='Therma-Probe 680XP · 780',
        tech='고해상 마이크로 균일도 맵으로 주입·어닐 공정 지문 확인',
        apps='공정 엔지니어링 분석 · 인라인 공정 모니터 · 장비 모니터 · 장비 간 매칭',
        features=('2007년 KLA-Tencor가 인수한 Therma-Wave의 제품군', 'r2007_therma'))),
    ('microrsp', 'CAPRES microRSP', '이온주입·면저항', 'p_microrsp', dict(
        measures='면저항 (홀 이동도·캐리어 밀도는 microHALL 구성)', method='마이크로 4탐침 접촉 측정',
        figures='캔틸레버 폭 최소 500 nm 미세 전극 배열',
        nodes='300 mm 블랭킷·제품 웨이퍼 스크라이브 라인 (200 mm 제품도 있음)',
        lineup='CAPRES A301 microRSP · A301 microHALL · M300 · M201',
        tech='기존 거시 4탐침법을 미세 전극으로 축소',
        apps='제품 웨이퍼 면저항 관리 · 증착·CMP·식각 인라인 모니터 · 장비 간 매칭',
        features='300 mm 제품 웨이퍼 스크라이브 라인 크기에서 작동하는 첫 비파괴 저항 계측 장비')),
    ('omnimap', 'OmniMap RS-200P', '이온주입·면저항', 'p_omnimap', dict(
        measures='면저항 맵', method='저항률 매핑 (업계 표준 방식)', figures=NO_FIG,
        nodes='칩 생산 · 첨단 패키징', lineup='OmniMap RS-200P',
        tech='고급 자동화 · 가장자리 측정 성능 개선', apps='공정 모니터 · 장비 모니터',
        features='첨단 패키징 공정에도 사용')),
    # --- 자성 (MRAM) ---
    ('ciptech', 'CAPRES CIPTech', '자성 (MRAM)', 'p_ciptech', dict(
        measures='MTJ 자기저항(MR) · 터널 저항(RA)', method='면내 전류 터널링(CIPTech) 다점 탐침',
        figures='탐침 전극 12개 · 수직 자석 600 mT(A301 ROW) · 수평 자석 150 mT(A201)',
        nodes='MRAM·STT-RAM · 자기 기록 헤드 · 자기 센서',
        lineup='CAPRES A301 CIPTech · M300 · M201 · A301 ROW · A201 Horizontal',
        tech='IBM에서 라이선스한 CIPTech · CAPRES 나노 MEMS 탐침',
        apps='MRAM 전기 특성 직접 측정 · 공정 관리 · 장비 간 매칭',
        features='블랭킷 MTJ 스택을 비파괴로 300 mm 전체 웨이퍼 또는 조각 시편에서 측정')),
    ('pkmram', 'MicroSense PKMRAM', '자성 (MRAM)', 'p_pkmram', dict(
        measures='자성 다층막 특성 (자유층·고정층)', method='극성 자기광학 커 효과(polar MOKE), 비접촉',
        figures='웨이퍼 최대 300 mm 전체 맵', nodes='수직 자화 MRAM', lineup='MicroSense PKMRAM (수동·자동 투입)',
        tech='독자 직접 자기장 제어 · 높은 자기장과 저자기장 분해능을 한 장비에',
        apps='MRAM 자성막 공정 개발·특성화·최적화',
        features='R&D와 양산 모두에 맞춘 수동·완전 자동 구성')),
    ('kerrmapper', 'MicroSense KerrMapper', '자성 (MRAM)', 'p_kerr', dict(
        measures='자성 다층막 특성', method='종방향 자기광학 커 효과(longitudinal MOKE), 비접촉',
        figures=NO_FIG, nodes='데이터 저장 · MRAM · 자기 센서', lineup='MicroSense KerrMapper S300 · V300',
        tech='독자 직접 자기장 제어 · 전체 웨이퍼 자성 특성 맵',
        apps='자성막 공정 개발·특성화 · 연·경자성 다층막 특성 분석',
        features='수동·완전 자동 구성')),
    # --- 복합 ---
    ('circl', 'CIRCL (최신 CIRCL9)', '복합 (검사·계측·리뷰)', 'p_circl', dict(
        measures='앞면·가장자리·뒷면 결함 · 가장자리 프로파일 계측 · 광학 리뷰', method='4모듈 클러스터 (검사·계측·리뷰 병렬)',
        launched=('2012-04-23', 'r2012_circl'), figures='모듈 4개 병렬 데이터 수집',
        nodes='첨단 로직·메모리 (패키징용 CIRCL-AP 별도)',
        lineup='CIRCL9 · CIRCL(2012-04) · CIRCL-AP · 모듈: 8 시리즈·CV350·BDR300·Micro-SR',
        tech='DirectedSampling: 한 측정 결과로 다른 측정을 자동 촉발',
        apps='공정 모니터 · 출하 품질 검사(OQC) · 장비 모니터 · 뒷면·가장자리 수율 모니터',
        features='팹 공간 절약·웨이퍼 대기 시간 단축, 모듈 단위 업그레이드 가능')),
]

FIELD_KEYS = [c['id'] for c in COLUMNS if c['id'] != 'name']


def build():
    sources = {sid: dict(title=title, url=url, checked=CHECKED, note=NOTES[sid[0]]) for sid, (title, url) in SOURCES.items()}
    rows = []
    for pid, name, group, page, fields in PRODUCTS:
        unknown = set(fields) - set(FIELD_KEYS)
        if unknown:
            raise ValueError(f'{pid}: unknown fields {unknown}')
        reviews = {}
        for key, raw in dict(fields, page=sources[page]['url']).items():
            value, source = raw if isinstance(raw, tuple) else (raw, page)
            if source not in sources:
                raise ValueError(f'{pid}.{key}: unknown source {source}')
            reviews[key] = dict(value=value, source=source, note=REVIEW[source[0]])
        reviews['name'] = dict(value=name, source=page, note='KLA 공식 제품명')
        rows.append(dict(id=pid, sheet_row=None, name=name, company='KLA', group=group, original={}, reviews=reviews,
                         review_note='KLA 공식 제품 페이지·소개서·보도자료 기준. 수치는 KLA가 밝힌 값이며 실제 팹 조건에 따라 다릅니다.'))
    return dict(
        id='kla_metrology_specs', name='KLA 계측 장비 · 제품별 사양', table_family='metrology', official_only=True,
        short_name='KLA 계측 장비', manual=True, frequency='irregular', source='KLA 공식 제품 페이지·소개서·보도자료',
        source_url=METRO, updated=CHECKED, fetched=CHECKED,
        update_note='KLA 제품 페이지·소개서·보도자료를 확인한 날짜 기준 스냅샷입니다. 새 장비 발표 시 scripts/build_kla_metrology_specs.py를 고칩니다.',
        evidence_text='모든 값은 아래 KLA 공식 제품 페이지, 제품 소개서(PDF), 보도자료에서 확인했습니다. 셀에 마우스를 올리면 그 값이 적힌 자료가 나옵니다. 라인업 칸 괄호 안 날짜는 아래 보도자료의 발표일입니다. KLA가 밝히지 않은 항목은 —로 둡니다.',
        columns=COLUMNS, rows=rows, name_key='name', default_group='all', default_view='overview', views=VIEWS,
        sources=sources, company_order=['KLA'], group_label='측정 분야', item_label='제품',
        search_placeholder='제품명·측정 대상·기술 검색',
        caption='KLA 공식 자료 기준 · 최근 공식 발표는 그 제품군에서 날짜가 확인되는 가장 최근 보도자료',
        evidence_summary=f'KLA 계측 제품 페이지 {len({p[3] for p in PRODUCTS})}곳 · 소개서 3건 · 보도자료 {sum(s.startswith("r") for s in SOURCES)}건 · {len(rows)}개 제품군',
        scroll_hint='셀에 마우스를 올리면 근거 · 맨 오른쪽 상세',
        note=('KLA 칩 제조용 계측 제품 페이지에 올라 있는 제품군(첨단 패키징 페이지의 irArcher 포함)을 한 줄씩 담았습니다. '
              '"최근 공식 발표"는 그 제품군에서 보도자료로 날짜가 확인되는 가장 최근 모델 기준입니다. Archer 800·SpectraShape 12k·SpectraFilm F10/F20·Aleris 9350 같은 '
              '최신 모델은 KLA가 별도 보도자료를 내지 않아 날짜가 없습니다. KLA도 처리량 같은 장비 사양은 거의 공개하지 않아, 공개 수치는 제품 페이지·소개서·보도자료에 '
              '적힌 값만 옮겼고 조건이 제각각이니 제품끼리 단순 비교하지 마세요. 결함 검사 장비(광대역 플라즈마·e-beam 검사 등)는 별도 분야라 넣지 않았습니다. '
              '가격·출하 대수는 공개되지 않아 넣지 않았습니다.'))


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(OUT)

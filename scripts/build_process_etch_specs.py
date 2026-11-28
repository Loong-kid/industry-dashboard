"""Etch equipment compared across makers (전공정 세부 > 식각).

One row per tool, grouped by the etch application it competes in, so the same step can be compared across
Lam, TEL, Applied Materials, Hitachi High-Tech, KLA (SPTS), AMEC, NAURA and Korean makers (세메스, 브이엠, 테스,
피에스케이). Every value cites the maker's own source (checked 2026-11-28):
  page     product page            release  press release / news       history  company history page
  user     figures the user supplies later (throughput, price) - add them to USER_VALUES with their source.
Lam rows are reused from build_lam_etch_specs.py so the two tables never drift apart.
Throughput (WPH) and price are left blank on purpose: makers do not publish them; the user fills them in.

    python scripts/build_process_etch_specs.py
"""
import json
from pathlib import Path

import build_lam_etch_specs as lam

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/semicon/process_etch_specs.json'
CHECKED = '2026-11-28'

COLUMNS = [
    dict(id='name', label='장비', width=190),
    dict(id='country', label='국가', width=70),
    dict(id='method', label='식각 방식', width=170),
    dict(id='status', label='단계', width=90),
    dict(id='launched', label='출시', width=100, date=True),
    dict(id='config', label='웨이퍼·챔버 구성', width=200),
    dict(id='throughput', label='처리량 (WPH)', width=110),
    dict(id='price', label='가격', width=110),
    dict(id='adoption', label='채택·설치 기반', width=280),
    dict(id='figures', label='공개 수치·비용 주장', width=300),
    dict(id='apps', label='주요 공정·소자', width=280),
    dict(id='lineup', label='모델 라인업', width=220),
    dict(id='tech', label='핵심 기술', width=300),
    dict(id='page', label='공식 자료', width=90, url=True),
]
VIEWS = [
    dict(id='overview', label='한눈에 보기', keys=['name', 'country', 'method', 'launched', 'figures', 'adoption', 'apps']),
    dict(id='cost', label='비용·생산성', keys=['name', 'country', 'launched', 'config', 'throughput', 'price', 'figures', 'adoption']),
    dict(id='detail', label='전체', keys=[c['id'] for c in COLUMNS]),
]
GROUPS = ['범용 플랫폼 (도체·유전체)', '도체 식각', '유전체 식각', '금속 식각', '선택적·등방성 식각', '실리콘 딥 식각',
          '베벨·가장자리', '패턴 형상', '전력·특수 소자 (200 mm 이하 포함)']
COMPANIES = {  # display order = matrix column order; value = country
    'Lam Research': '미국', 'TEL': '일본', 'Applied Materials': '미국', 'Hitachi High-Tech': '일본', 'KLA (SPTS)': '미국',
    'AMEC': '중국', 'NAURA': '중국', '세메스': '한국', '브이엠': '한국', '테스': '한국', '피에스케이': '한국',
}
KIND_NOTE = {'page': '공식 제품 페이지 기재', 'release': '공식 보도자료 기재', 'history': '회사 연혁·제품 페이지 기재',
             'user': '사용자 제공 자료'}
SOURCE_NOTE = {'page': '제품 페이지 본문.', 'release': '보도자료·뉴스 원문.', 'history': '회사 홈페이지 연혁·제품 소개.',
               'user': '사용자가 제공한 자료.'}

TEL = 'https://www.tel.com/'
AMAT = 'https://www.appliedmaterials.com/us/en/semiconductor/products/shape/etch/'
NASDAQ = 'https://www.nasdaq.com/press-release/'
HHT = 'https://www.hitachi-hightech.com/'
AMEC = 'https://www.amec-inc.com/en/index/Lists/show/catid/'
NAURA = 'https://www.naura.com/product/details_15_'
VM = 'https://www.vmsemi.com/kor/'

# source id -> (title, url, kind)
SOURCES = {
    # TEL
    'tel_p_episode': ('TEL · Episode UL 제품 페이지', TEL + 'product/episode_ul.html', 'page'),
    'tel_p_tactras': ('TEL · Tactras 제품 페이지', TEL + 'product/tactras.html', 'page'),
    'tel_p_certas': ('TEL · Certas 제품 페이지', TEL + 'product/certas_leaga.html', 'page'),
    'tel_p_unity': ('TEL · UNITY 제품 페이지', TEL + 'product/unity.html', 'page'),
    'tel_r_episode': ('TEL 뉴스 2021-01-14 · Episode UL 발표', TEL + 'news/product/2021/20210114_001.html', 'release'),
    'tel_r_udemae': ('TEL 뉴스 2021-12-14 · Tactras-UDEMAE (300 mm 전력 소자)', TEL + 'news/product/2021/20211214_001.html', 'release'),
    'tel_r_cryo': ('TEL 뉴스 2023-06-09 · 400단 이상 3D NAND 채널홀 극저온 식각 기술', TEL + 'news/product/2023/20230609_001.html', 'release'),
    # Applied Materials
    'amat_p_sym3z': ('AMAT · Sym3 Z Magnum 제품 페이지', AMAT + 'sym3z-etch.html', 'page'),
    'amat_p_selectra': ('AMAT · Producer Selectra Etch 제품 페이지', AMAT + 'producer-selectra-etch.html', 'page'),
    'amat_p_producer': ('AMAT · Producer Etch 제품 페이지', AMAT + 'producer-etch.html', 'page'),
    'amat_r2022': ('AMAT 보도자료 2022-04-21 · EUV·GAA (Selectra 2016 출시·챔버 1000개)',
                   NASDAQ + 'applied-materials-technologies-enable-2d-scaling-with-euv-and-3d-gate-all-around', 'release'),
    'amat_r2024': ('AMAT 보도자료 2024-02-26 · Sym3 Y Magnum · Sculpta',
                   NASDAQ + 'applied-materials-expands-patterning-solutions-portfolio-for-angstrom-era-chipmaking', 'release'),
    'amat_r2026_feb': ('AMAT 보도자료 2026-02-10 · Sym3 Z Magnum',
                       'https://www.theglobeandmail.com/investing/markets/stocks/AMAT/pressreleases/36491210/'
                       'applied-materials-unveils-transistor-and-wiring-innovations-for-faster-ai-chips/', 'release'),
    'amat_r2026_jun': ('AMAT 보도자료 2026-06-15 · Selectra Mo Etch',
                       NASDAQ + 'applied-materials-unveils-deposition-and-selective-etch-systems-advance-3d-chip', 'release'),
    # Hitachi High-Tech
    'hht_p_9000': ('Hitachi High-Tech · 9000 시리즈 제품 페이지',
                   HHT + 'us/en/products/semiconductor-manufacturing/dry-etch-systems/conductor/9000.html', 'page'),
    'hht_p_conductor': ('Hitachi High-Tech · 도체 식각 제품군 페이지',
                        HHT + 'global/en/products/semiconductor-manufacturing/dry-etch-systems/conductor/', 'page'),
    'hht_p_ecr': ('Hitachi High-Tech · 마이크로파 ECR 챔버 페이지',
                  HHT + 'us/en/products/semiconductor-manufacturing/dry-etch-systems/microwave-ecr.html', 'page'),
    # KLA (SPTS)
    'kla_p_etch': ('KLA · SPTS 식각 제품 페이지', 'https://www.kla.com/products/chip-manufacturing/etch', 'page'),
    # AMEC
    'amec_p_drie': ('AMEC · Primo D-RIE 제품 페이지', AMEC + '29/id/82.html', 'page'),
    'amec_p_adrie': ('AMEC · Primo AD-RIE 제품 페이지', AMEC + '29/id/513.html', 'page'),
    'amec_p_ssc': ('AMEC · Primo SSC AD-RIE 제품 페이지', AMEC + '29/id/514.html', 'page'),
    'amec_p_idea': ('AMEC · Primo iDEA 제품 페이지', AMEC + '29/id/515.html', 'page'),
    'amec_p_twinstar': ('AMEC · Primo Twin-Star 제품 페이지', AMEC + '29/id/516.html', 'page'),
    'amec_p_hdrie': ('AMEC · Primo HD-RIE 제품 페이지', AMEC + '29/id/517.html', 'page'),
    'amec_p_udrie': ('AMEC · Primo UD-RIE 제품 페이지', AMEC + '29/id/605.html', 'page'),
    'amec_p_nanova': ('AMEC · Primo Nanova 제품 페이지', AMEC + '29/id/269.html', 'page'),
    'amec_p_tsv': ('AMEC · Primo TSV 제품 페이지', AMEC + '29/id/289.html', 'page'),
    'amec_r2011': ('AMEC 보도자료 2011-07 · Primo AD-RIE 출시', AMEC + '97/id/540.html', 'release'),
    'amec_r2018': ('AMEC 보도자료 2018-03 · Primo Nanova 출시 (첫 ICP)', AMEC + '97/id/547.html', 'release'),
    'amec_r2021_tw': ('AMEC 보도자료 2021-03-16 · Primo Twin-Star 출시', AMEC + '97/id/172.html', 'release'),
    'amec_r2021_ccp': ('AMEC 보도자료 2021-11 · CCP 식각 1,500번째 스테이션 출하', AMEC + '97/id/175.html', 'release'),
    # NAURA (product pages in Chinese)
    'naura_rx': ('NAURA · Accura RX 제품 페이지', NAURA + '2454.html', 'page'),
    'naura_nz': ('NAURA · Accura NZ 제품 페이지', NAURA + '2455.html', 'page'),
    'naura_lx': ('NAURA · Accura LX 제품 페이지', NAURA + '2456.html', 'page'),
    'naura_be': ('NAURA · Accura BE 제품 페이지', NAURA + '2457.html', 'page'),
    'naura_612g': ('NAURA · NMC 612G 제품 페이지', NAURA + '2459.html', 'page'),
    'naura_612m': ('NAURA · NMC 612M 제품 페이지', NAURA + '2460.html', 'page'),
    'naura_612e': ('NAURA · NMC 612E 제품 페이지', NAURA + '2461.html', 'page'),
    'naura_612d': ('NAURA · NMC 612D 제품 페이지', NAURA + '2462.html', 'page'),
    'naura_612c': ('NAURA · NMC 612C 제품 페이지', NAURA + '2463.html', 'page'),
    'naura_gde': ('NAURA · GDE C200 제품 페이지', NAURA + '2466.html', 'page'),
    'naura_508c': ('NAURA · NMC 508 CCP 제품 페이지', NAURA + '2467.html', 'page'),
    'naura_508i': ('NAURA · NMC 508 ICP 제품 페이지', NAURA + '2468.html', 'page'),
    'naura_ace': ('NAURA · ACE E300 제품 페이지', NAURA + '2469.html', 'page'),
    'naura_acege': ('NAURA · ACE E300Ge 제품 페이지', NAURA + '2470.html', 'page'),
    'naura_hse': ('NAURA · HSE P300 제품 페이지', NAURA + '2473.html', 'page'),
    'naura_pse': ('NAURA · PSE V300 제품 페이지', NAURA + '2475.html', 'page'),
    # Korean makers
    'semes_p': ('세메스 · 제품 페이지 (식각: Oxide·Poly)', 'https://www.semes.com/ko/product/product/view', 'page'),
    'vm_h': ('브이엠 · 회사 연혁', VM + 'History', 'history'),
    'vm_poly': ('브이엠 · Poly Etcher 제품 페이지', VM + 'PolyEtcherbrSystem', 'history'),
    'vm_metal': ('브이엠 · Metal Etcher 제품 페이지', VM + 'MetalEtcherSystem', 'history'),
    'vm_oxide': ('브이엠 · Oxide Etcher 제품 페이지', VM + 'OxideEtcherSystem', 'history'),
    'vm_dev': ('브이엠 · 개발 계획 장비 페이지', VM + 'UnderDevelopment', 'history'),
    'tes_p': ('테스 · 반도체 장비 제품 페이지', 'https://www.hites.co.kr/bbs/board.php?bo_table=b1', 'page'),
    'psk_p': ('피에스케이 · Edge clean 제품 페이지', 'https://www.pskinc.com/producttech/edge_clean.php', 'page'),
}
# Lam sources keep their own ids with a lam_ prefix.
for sid, (title, url) in lam.SOURCES.items():
    SOURCES['lam_' + sid] = (title, url, 'release' if sid.startswith('r_') else 'page')

# Figures the user supplies later: {(row id, 'throughput'|'price'): (value, source id)}; add the source to SOURCES with kind 'user'.
USER_VALUES = {}

ON_SALE, DEV, TECH = '판매 중', '개발 중', '기술 발표'
NO_FIG = '수치 미기재'
LAM_GROUP = {'도체 식각': '도체 식각', '유전체 식각': '유전체 식각', '금속 식각': '금속 식각', '실리콘 딥 식각': '실리콘 딥 식각',
             '선택적 식각': '선택적·등방성 식각', '베벨 (웨이퍼 가장자리)': '베벨·가장자리', '플랫폼': '범용 플랫폼 (도체·유전체)',
             '재생 장비 (Reliant)': '전력·특수 소자 (200 mm 이하 포함)'}

# (id, name, company, group, page source, fields). A value is text (cites the page source) or (text, source id).
PRODUCTS = [
    # ---------------- TEL ----------------
    ('tel-episode-ul', 'Episode UL', 'TEL', '범용 플랫폼 (도체·유전체)', 'tel_p_episode', dict(
        method='반응성 이온 식각(RIE) · 도체·유전체', status=ON_SALE, launched='2020',
        config='300 mm · 챔버 4~12개 (두 줄 마주 보는 직사각형 클러스터)', figures='챔버당 설치 면적 대폭 축소 (수치 미기재)',
        adoption=NO_FIG, apps='최신 로직·메모리', lineup='Episode UL',
        tech='스마트 툴: 센서·고속 제어로 빅데이터 기반 자율 공정 제어 · 정비 공간 확대')),
    ('tel-tactras', 'Tactras', 'TEL', '범용 플랫폼 (도체·유전체)', 'tel_p_tactras', dict(
        method='반응성 이온 식각(RIE) · 도체·유전체', status=ON_SALE, launched='2006',
        config='300 mm · 챔버 1~6개 (챔버마다 다른 식각 가능)', figures='웨이퍼 이송 속도·설치 면적 세계 최고 수준 (TEL 주장, 수치 미기재)',
        adoption='많은 고객이 계속 사용 (수치 미기재)', apps='고종횡비 홀·트렌치 · 마스크·유전체 · BEOL 유전체',
        lineup='Tactras · Tactras-UDEMAE(300 mm 전력 소자)',
        tech='공통 기본 설계에 용도별 챔버 · 장비·챔버 간 편차 최소화 · 파티클 저감')),
    ('tel-cryo', '극저온 채널홀 식각 기술', 'TEL', '유전체 식각', 'tel_r_cryo', dict(
        method='극저온 유전체 식각 (유전체를 극저온 영역으로 처음 확장)', status=TECH, launched='2023-06-09',
        figures='종횡비가 큰 깊이 10 µm 식각을 33분에 · 지구온난화지수 84% 절감', apps='400단 이상 3D NAND 메모리 채널홀',
        adoption='기술 개발 발표 (2023 VLSI 심포지엄 발표)', tech='극저온 유전체 식각 · 높은 식각 속도')),
    ('tel-certas', 'Certas LEAGA', 'TEL', '선택적·등방성 식각', 'tel_p_certas', dict(
        method='가스 화학 식각 (플라즈마 없음, 등방성)', status=ON_SALE,
        config='300 mm · 2매 동시 처리 챔버 최대 6개', figures=NO_FIG,
        adoption='글로벌 반도체 업체가 양산부터 차세대 개발까지 널리 채택',
        apps='Si 콘택 형성 전 표면 세정 · 산화막 제거·에치백 · 고종횡비 3D 선택 식각 · 정밀 리세스',
        tech='액체 없는 건식 공정(워터마크 없음) · 여러 SiO2 막 사이 고유 선택비 · TEL 세정 장비와 결합')),
    ('tel-unity', 'UNITY Me+', 'TEL', '전력·특수 소자 (200 mm 이하 포함)', 'tel_p_unity', dict(
        method='플라즈마 식각 (SCCM·DRM·UD 챔버)', status=ON_SALE, launched='2021',
        config='100·150·200 mm · 챔버 1~4개 · 신품·인증 중고', figures=NO_FIG,
        adoption='200 mm 이하에서 오래 팔린 장비, SiC 전력 소자 시장에서 주목', apps='SiO2·SiN 식각 · Si·SiC 트렌치 · TSV',
        lineup='UNITY Me+ Ox · Me+ Si · Me+ SiC', tech='2021년 UNITY Me를 개편해 지원 수명 연장 · LT·LN 등 화합물 웨이퍼 처리 실적')),
    ('tel-udemae', 'Tactras-UDEMAE', 'TEL', '전력·특수 소자 (200 mm 이하 포함)', 'tel_r_udemae', dict(
        method='플라즈마 식각 (전력 소자용 반응기)', status=ON_SALE, launched='2021-12-14',
        config='300 mm (Tactras 플랫폼)', figures=NO_FIG,
        adoption='200 mm 전력 소자 시장 설치 기반 1위 반응기를 300 mm로 확장',
        apps='300 mm 전력·개별 소자', tech='200 mm 공정 라이브러리를 300 mm에 그대로 적용 · 웨이퍼 가장자리 파티클 억제')),
    # ---------------- Applied Materials ----------------
    ('amat-sym3z', 'Centris Sym3 Z Magnum', 'Applied Materials', '도체 식각', 'amat_p_sym3z', dict(
        method='도체 플라즈마 식각 (펄스 전압 PVT2)', status=ON_SALE, launched=('2026-02-10', 'amat_r2026_feb'),
        adoption=('Sym3 Z 계열: 2 nm 로직 양산 기준 장비, 현장 설치 챔버 250개 이상 · 여러 선두 업체 채택', 'amat_r2026_feb'),
        figures=NO_FIG, apps='GAA 소스/드레인 캐비티 · 3D 트렌치 · DRAM·HBM 고밀도 배열',
        lineup='Sym3 Z Magnum · Sym3 Z · (Sym3 Y Magnum은 별도 행)',
        tech='2세대 펄스 전압 기술(PVT2) · 이온 각도·에너지 독립 조절 · 웨이퍼 가까이 플라즈마 생성 · Si/SiGe 선택비')),
    ('amat-sym3y', 'Sym3 Y Magnum', 'Applied Materials', '도체 식각', 'amat_r2024', dict(
        method='식각 + 증착을 한 챔버에서 (EUV 라인 거칠기 보정)', status=ON_SALE, launched='2024-02-26', figures=NO_FIG,
        adoption='파운드리·로직 핵심 식각 채택 · DRAM EUV 패터닝에서 가장 많이 채택된 식각 기술',
        apps='EUV·High-NA EUV 패터닝 (옹스트롬 노드) · DRAM', tech='거친 패턴 가장자리에 재료를 증착해 다듬은 뒤 식각')),
    ('amat-selectra', 'Producer Selectra', 'Applied Materials', '선택적·등방성 식각', 'amat_p_selectra', dict(
        method='라디칼 기반 선택적 식각 (건식)', status=ON_SALE, launched=('2016', 'amat_r2022'),
        adoption=('선택적 재료 제거 시장 1위, 고객사 사용 챔버 1,000개 이상 (2022 기준)', 'amat_r2022'), figures=NO_FIG,
        apps='FinFET 원자층 수준 식각 · 3D NAND 텅스텐 리세스 · 고종횡비 DRAM 무손상 세정 · GAA',
        tech='라디칼 화학으로 유전체·금속·반도체 막 선택비 조정 · 완전 건식이라 패턴 붕괴 방지')),
    ('amat-selectra-mo', 'Producer Selectra Mo Etch', 'Applied Materials', '금속 식각', 'amat_r2026_jun', dict(
        method='선택적 금속(몰리브덴) 제거', status=ON_SALE, launched='2026-06-15', figures=NO_FIG,
        adoption='양산 검증 완료', apps='3D NAND 몰리브덴 워드라인 분리 (습식 식각 대체)',
        tech='공정 제어·가스 공급으로 깊은 구조에서도 위아래 균일한 선택적 금속 제거')),
    ('amat-sculpta', 'Centura Sculpta', 'Applied Materials', '패턴 형상', 'amat_r2024', dict(
        method='패턴 형상 가공 (패턴 늘이기)', status=ON_SALE, launched='2023', figures=NO_FIG,
        adoption='모든 선두 로직 업체와 적용 확대 중 · Intel 옹스트롬 노드에 배치 · 삼성 4 nm 평가 (2024 발표)',
        apps='EUV 이중 패터닝 단계 축소 · 팁 간격 축소 · 브리지 결함 제거',
        tech='패턴을 한 방향으로 늘여 팁을 더 가깝게 (단일 노광 한계 이하)')),
    ('amat-producer-etch', 'Producer Etch', 'Applied Materials', '범용 플랫폼 (도체·유전체)', 'amat_p_producer', dict(
        method='플라즈마 식각 (Twin Chamber)', status=ON_SALE,
        config='Twin Chamber 최대 3개 (챔버당 1~2매) · 2 FOUP·듀얼 로봇', figures='습식 세정 간격 500 RF시간 이상 (양산 환경)',
        adoption=NO_FIG, apps='90 nm 이하 고생산성 식각', tech='전극 간격 조절로 식각 속도·균일도·선택비 조정 · 플라즈마 가둠·인시투 세정')),
    # ---------------- Hitachi High-Tech ----------------
    ('hht-9000', '9000 시리즈', 'Hitachi High-Tech', '도체 식각', 'hht_p_9000', dict(
        method=('마이크로파 ECR 플라즈마 (0.1 Pa 미만 저압 고밀도)', 'hht_p_ecr'), status=ON_SALE,
        config='300 mm · 챔버 최대 9개', figures=NO_FIG, adoption='ECR 챔버는 양산 검증 (수치 미기재)',
        apps='20 nm 이하 · 이중 패터닝 · 3D 구조 · STI·게이트·SAC·배선 식각', lineup='9000 시리즈',
        tech='저오염 고속 이송 · 모듈형 챔버 확장 · 플라즈마 분포·높이 제어')),
    ('hht-m8000', 'M-8000 시리즈', 'Hitachi High-Tech', '도체 식각', 'hht_p_conductor', dict(
        method='마이크로파 ECR 플라즈마', status=ON_SALE, figures=NO_FIG, adoption=NO_FIG,
        apps='32 nm 이하 하드마스크·실리콘 식각 · 이중 패터닝 · HKMG', lineup='M-8000 · (구형) M-600/6000',
        tech='소자·재료·장비 업체와 공동개발(JDP)로 공정 개발')),
    # ---------------- KLA (SPTS) ----------------
    ('kla-spts-rapier', 'SPTS Omega (Rapier·DSi-v)', 'KLA (SPTS)', '실리콘 딥 식각', 'kla_p_etch', dict(
        method='딥 반응성 이온 식각(DRIE, Bosch 공정)', status=ON_SALE, figures=NO_FIG,
        adoption='DRIE 공정 모듈 1,500개 이상 설치', config='Omega LPX·c2L·fxP 이송 플랫폼 또는 Versalis 클러스터',
        apps='첨단 패키징 · RF · 전력 소자 · MEMS', lineup='Rapier · DSi-v (그 밖에 플라즈마 다이싱·HF·XeF2 증기 식각)',
        tech='독립 제어되는 1·2차 플라즈마 이중 소스 · 이중 가스 주입으로 높은 식각 속도·CD·기울기 제어')),
    # ---------------- AMEC ----------------
    ('amec-drie', 'Primo D-RIE', 'AMEC', '유전체 식각', 'amec_p_drie', dict(
        method='CCP 유전체 식각 (VHF·LF 분리)', status=ON_SALE, launched='2007',
        config='300 mm · 2스테이션 공정 모듈 최대 3개 (모듈당 2매 동시)', figures=NO_FIG,
        adoption=('CCP 식각 제품군 누적 1,500번째 스테이션 출하 (2021-11) · 중국 내 반복 주문', 'amec_r2021_ccp'),
        apps='65~16 nm 산화막·질화막·low-k 유전체', lineup='Primo D-RIE (1세대)', tech='VHF·LF 분리 RF 소스 · FEIS 링 플라즈마 가둠')),
    ('amec-adrie', 'Primo AD-RIE', 'AMEC', '유전체 식각', 'amec_p_adrie', dict(
        method='CCP 유전체 식각 (2세대)', status=ON_SALE, launched=('2011-07', 'amec_r2011'),
        config='300 mm · 2스테이션 공정 모듈 최대 3개 (6스테이션)',
        figures=('업계 표준 대비 자본 생산성 35~50%↑ · 소유비용(CoO) 20~40%↓ · 가장 큰 경쟁 장비보다 면적 30% 이상 작음 (2011 발표)', 'amec_r2011'),
        adoption=('HD-RIE와 AD-RIE-e(7 nm 이하 로직)가 2021년 출하의 절반, 대부분 중국 본토·대만', 'amec_r2021_ccp'),
        apps='40~7 nm BEOL · 10 nm FEOL', lineup='AD-RIE · AD-RIE-e(동적 ESC) · AD-RIE-cr(내부식)',
        tech='전환형 이중 저주파 RF · 다구역 가스 분배 · 이중 칠러 온도 제어')),
    ('amec-ssc', 'Primo SSC AD-RIE', 'AMEC', '유전체 식각', 'amec_p_ssc', dict(
        method='CCP 유전체 식각 (단일 반응기 6개)', status=ON_SALE, launched='2013', config='300 mm · 단일 반응기 6개',
        figures=NO_FIG, adoption=NO_FIG, apps='26~10 nm · 콘택홀 식각', tech='동기 펄스 RF · 냉각 포커스 링 · 초저압 배기')),
    ('amec-hdrie', 'Primo HD-RIE', 'AMEC', '유전체 식각', 'amec_p_hdrie', dict(
        method='CCP 고종횡비 유전체 식각', status=ON_SALE, launched='2015', config='300 mm · 공정 스테이션 6개',
        figures=NO_FIG, adoption=('2021년 출하의 절반(AD-RIE-e와 합산), 3D NAND용', 'amec_r2021_ccp'),
        apps='3D NAND·DRAM 중·고종횡비 구조', tech='고출력 동기 RF 펄싱 · 고출력·고온 ESC · 가스 펄싱 · 다구역 가스')),
    ('amec-udrie', 'Primo UD-RIE', 'AMEC', '유전체 식각', 'amec_p_udrie', dict(
        method='CCP 고종횡비 유전체 식각 (초저주파 고출력)', status=ON_SALE, config='단일 웨이퍼 반응 챔버 최대 6개 + 스트립 챔버 2개',
        figures=NO_FIG, adoption=NO_FIG, apps='메모리 가장 까다로운 고종횡비(HAR) 유전체 식각',
        tech='초저주파 고출력 다단 펄싱 RF · 실시간 온도 전환 하부 전극 · 고전압 ESC')),
    ('amec-idea', 'Primo iDEA', 'AMEC', '유전체 식각', 'amec_p_idea', dict(
        method='CCP 유전체 식각 + 다운스트림 애셔 통합', status=ON_SALE, figures=NO_FIG, adoption=NO_FIG,
        config='D-RIE 또는 AD-RIE 모듈 1~2개 + 애셔(DsA) 챔버', apps='식각 후 포토레지스트 제거까지 한 장비 (표면 전하 민감 소자)',
        tech='원격 플라즈마 소스 애셔로 웨이퍼 직접 노출 최소화')),
    ('amec-nanova', 'Primo Nanova', 'AMEC', '도체 식각', 'amec_p_nanova', dict(
        method='ICP 도체 식각 (단일 스테이션)', status=ON_SALE, launched=('2018-03', 'amec_r2018'),
        config='300 mm · 챔버 최대 6개 + 스트립 챔버 2개', figures=NO_FIG,
        adoption=('여러 고객 주문·출하, 첫 장비 양산 투입 (2018 발표)', 'amec_r2018'),
        apps='로직·DRAM 1x nm 이하 · STI·폴리 게이트·스페이서·마스크·에치백', lineup='Primo Nanova (AMEC 첫 ICP)',
        tech='저용량 결합 3D 코일 · 대칭 챔버·고속 배기 · 다구역 온도 제어 ESC')),
    ('amec-twinstar', 'Primo Twin-Star', 'AMEC', '도체 식각', 'amec_p_twinstar', dict(
        method='ICP 식각 (2스테이션)', status=ON_SALE, launched=('2021-03-16', 'amec_r2021_tw'),
        config='300 mm · 2스테이션 챔버 최대 3개 + 스트립 챔버 2개', figures=NO_FIG,
        adoption=('중국 선두 고객 주문·출하, 첫 장비 양산 투입 (2021 발표)', 'amec_r2021_tw'),
        apps='FEOL·BEOL 도체·유전체 · 폴리 · 전력·CIS DTI·BSI', tech='2스테이션 챔버(배기구 영향 최소) · 저용량 결합 3D 코일 · 다구역 ESC')),
    ('amec-tsv', 'Primo TSV', 'AMEC', '실리콘 딥 식각', 'amec_p_tsv', dict(
        method='고밀도 플라즈마 TSV 식각 (Bosch·정상상태 겸용)', status=ON_SALE,
        config='200·300 mm · 2스테이션 공정 모듈 최대 3개', figures=NO_FIG, adoption=NO_FIG,
        apps='CMOS 이미지센서 · 2.5D·3D IC · 플라즈마 다이싱', tech='한 챔버에서 Bosch·정상상태 공정')),
    # ---------------- NAURA ----------------
    ('naura-612e', 'NMC 612E', 'NAURA', '도체 식각', 'naura_612e', dict(
        method='ICP 식각 (펄스 플라즈마)', status=ON_SALE, config='300 mm', figures=NO_FIG, adoption='양산 경험 풍부 (수치 미기재)',
        apps='STI · 게이트 · 스페이서 · SAMP · 텅스텐 · 금속 하드마스크 · high-k (로직·DRAM·3D NAND)',
        tech='유연한 펄스 플라즈마 · 다구역 온도 ESC · 가스 고속 전환 준원자층 식각')),
    ('naura-612d', 'NMC 612D', 'NAURA', '도체 식각', 'naura_612d', dict(
        method='실리콘 식각 (펄스 플라즈마)', status=ON_SALE, config='300 mm', figures=NO_FIG,
        adoption='로직·3D NAND·DRAM·CIS·전력·실리콘 포토닉스 안정 양산', apps='STI · 폴리/금속 게이트 · 산화막/질화막 스페이서',
        tech='저손상 펄스 플라즈마 · 다구역 온도 ESC')),
    ('naura-612c', 'NMC 612C', 'NAURA', '도체 식각', 'naura_612c', dict(
        method='실리콘 식각', status=ON_SALE, config='300 mm', figures=NO_FIG, adoption='성숙 로직·전력 양산 경험',
        apps='폴리 게이트 · STI · 스페이서', tech='다층 막 인시투 식각 · 현지 서비스·맞춤 소프트웨어')),
    ('naura-nz', 'Accura NZ', 'NAURA', '유전체 식각', 'naura_nz', dict(
        method='고종횡비 유전체 식각 (고출력 고·저주파 RF)', status=ON_SALE, config='300 mm', figures=NO_FIG, adoption=NO_FIG,
        apps='3D NAND G5 이상 채널홀 (산화막·질화막 적층)', tech='가장자리 플라즈마 조절(PEA) · 4구역 자기장 코일 · ESC 고·저온 빠른 전환')),
    ('naura-lx', 'Accura LX', 'NAURA', '유전체 식각', 'naura_lx', dict(
        method='유전체 식각 (이중 주파수 펄스 + Top DC)', status=ON_SALE, config='300 mm', figures=NO_FIG, adoption=NO_FIG,
        apps='로직 G0 노드 이상 BEOL 일체형(AIO) 비아·트렌치 · 듀얼 다마신 · 콘택', tech='TiN 선택비 향상 · ESC 4구역 정밀 온도 · 고온 챔버로 부산물 감소')),
    ('naura-612g', 'NMC 612G', 'NAURA', '금속 식각', 'naura_612g', dict(
        method='금속 플라즈마 식각', status=ON_SALE, config='300 mm · Si·SiC·유리 웨이퍼', figures=NO_FIG,
        adoption='로직·DRAM·3D NAND·전력·CIS 등 양산 경험 풍부', apps='알루미늄 배선·패드 · 몰리브덴·텅스텐·ITO',
        tech='고성능 ESC · 다양한 균일도 조절 (UPH·WPH 경쟁력 주장, 수치 미기재)')),
    ('naura-612m', 'NMC 612M', 'NAURA', '금속 식각', 'naura_612m', dict(
        method='금속 하드마스크 식각 (펄스 플라즈마)', status=ON_SALE, config='300 mm', figures=NO_FIG, adoption='양산 경험 풍부',
        apps='TiN 금속 하드마스크 · high-k · 금속 저항 · W·Ti·Ta 화합물', tech='저손상 펄스 플라즈마 · 다구역 온도 ESC')),
    ('naura-rx', 'Accura RX', 'NAURA', '선택적·등방성 식각', 'naura_rx', dict(
        method='화학 기상 식각 (고선택비 산화막)', status=ON_SALE, config='300 mm · 대형 이송 플랫폼·공정 챔버·어닐 챔버',
        figures=NO_FIG, adoption='로직·메모리 첨단 공정 폭넓게 적용', apps='산화막 선택적 식각', tech='고균일도·저손상 · 미세 로딩 조정')),
    ('naura-ace', 'ACE E300 · E300Ge', 'NAURA', '선택적·등방성 식각', 'naura_ace', dict(
        method='이온 필터 고선택비 식각', status=ON_SALE, config='300 mm', figures=NO_FIG, adoption=NO_FIG,
        apps=('E300: 로직·3D 구조 Si·폴리·STI·low-k · E300Ge: 첨단 메모리 횡방향 식각·TiN·표면 손상층 처리', 'naura_acege'),
        tech='초고효율 이온 필터로 입자 에너지 정밀 제어 · 하부층 무손상 · OES Plus 모니터링')),
    ('naura-pse', 'PSE V300', 'NAURA', '실리콘 딥 식각', 'naura_pse', dict(
        method='딥 실리콘 식각 (Bosch·비Bosch 겸용)', status=ON_SALE, config='300 mm · 독립 반응 챔버 최대 6개', figures=NO_FIG,
        adoption='현지 전문가 현장 대응 (수치 미기재)', apps='TSV · 딥 트렌치 분리·커패시터 · 전력 실리콘 트렌치 · MEMS',
        lineup=('PSE V300 · HSE P300(첨단 패키징 딥 실리콘)', 'naura_hse'), tech='구역별 가스·고속 전환 · 저스캘럽·고식각 속도')),
    ('naura-be', 'Accura BE', 'NAURA', '베벨·가장자리', 'naura_be', dict(
        method='플라즈마 베벨 식각', status=ON_SALE, config='300 mm · 공정 압력 1~5 Torr',
        figures='윗면 식각 거리 0~3 mm · 뒷면 0~5 mm 조절', adoption=NO_FIG,
        apps='로직·3D NAND·DRAM 웨이퍼 가장자리 폴리머·막 제거 (결함 감소)', tech='가시화 동축 조정 · 실시간 갭 감지 · 고정밀 이송')),
    ('naura-508', 'NMC 508 (ICP·CCP)', 'NAURA', '전력·특수 소자 (200 mm 이하 포함)', 'naura_508i', dict(
        method='ICP·CCP 식각', status=ON_SALE, config='150·200 mm · 다챔버 클러스터', figures=NO_FIG, adoption=NO_FIG,
        apps='IC·패키징·화합물 반도체 금속·실리콘·딥실리콘·유전체', lineup=('NMC 508 ICP · NMC 508 CCP · GDE C200(화합물 반도체)', 'naura_gde'),
        tech='고유 플라즈마 소스 · 직하 배기 챔버 · 낮은 CoO (수치 미기재)')),
    # ---------------- 한국 ----------------
    ('semes-etch', '세메스 식각 장비 (Oxide·Poly)', '세메스', '유전체 식각', 'semes_p', dict(
        method='산화막·폴리 건식 식각', status=ON_SALE, figures='공식 사이트에 장비명·사양 미공개', adoption=NO_FIG,
        apps='산화막 · 폴리')),
    ('vm-leo-nk', 'Leo NK I · NK I-C', '브이엠', '도체 식각', 'vm_poly', dict(
        method='폴리(도체) 식각', status=ON_SALE, launched=('2016-01', 'vm_h'), config='300 mm', figures=NO_FIG,
        adoption=('NK I: 2016-01 SK하이닉스 양산 판매 · NK I-C: 2017-12 SK하이닉스 양산, 2018-04 SK하이닉스 우시 수출', 'vm_h'),
        apps='폴리 식각 (메모리)', lineup=('Leo NK I(2015-05 개발) · NK I-C(2016-06 개발)', 'vm_h'))),
    ('vm-leo-wh', 'Leo WH', '브이엠', '도체 식각', 'vm_poly', dict(
        method='폴리(도체) 식각', status=ON_SALE, launched=('2021-01', 'vm_h'), config='300 mm', figures=NO_FIG,
        adoption=('2021-01 SK하이닉스 양산 판매 성공', 'vm_h'), apps='폴리 식각 (메모리)')),
    ('vm-leo-ws', 'Leo WS', '브이엠', '도체 식각', 'vm_poly', dict(
        method='폴리(도체) 식각', status='개발 완료 (2027 양산 판매 예정)', config='300 mm', figures=NO_FIG,
        adoption='2025년 개발 완료, 2027년 양산 판매 예정', apps='폴리 식각')),
    ('vm-nardo-m', 'Nardo-M', '브이엠', '금속 식각', 'vm_metal', dict(
        method='금속 식각', status=ON_SALE, launched=('2020-10', 'vm_h'), config='300 mm', figures=NO_FIG,
        adoption=('2020-10 SK하이닉스 우시 수출 · 2021-01 SK하이닉스 양산 판매 (2009년 국내 첫 300 mm 금속 식각 양산 판매)', 'vm_h'),
        apps='금속 배선 식각')),
    ('vm-oxide', 'Oxide Etcher (개발 중)', '브이엠', '유전체 식각', 'vm_oxide', dict(
        method='산화막(유전체) 식각', status=DEV, figures=NO_FIG, adoption='2026년 개발 완료 예정, 2028년 양산 판매 예정',
        apps='유전체 식각')),
    ('vm-apes', 'APES A (원자층 식각, 개발 중)', '브이엠', '선택적·등방성 식각', 'vm_dev', dict(
        method='원자층 식각(ALE)', status=DEV, figures=NO_FIG, adoption='2027년 개발 완료 예정, 2029년 양산 판매 예정', apps='원자층 식각')),
    ('tes-cumax', 'CUMAX', '테스', '선택적·등방성 식각', 'tes_p', dict(
        method='가스·라디칼 기반 등방성 식각 (CCP 라디칼 + 가스)', status=ON_SALE, figures='SiGe 선택비 200 이상',
        adoption=NO_FIG,
        apps='자연 산화막 제거 · 산화막 측면 리세스 · 에어갭 · 3D 구조 산화막 패터닝 · 3D DRAM·로직 SiGe 적층 식각 · 폴리 하드마스크 제거',
        tech='램프 가열 인시투 건식 세정 · 고속 반복 식각 · 질화막 대비 선택비 가변 (회사 분류는 건식 세정)')),
    ('tes-spica', 'SPICA', '테스', '선택적·등방성 식각', 'tes_p', dict(
        method='CCP 플라즈마 라디칼 식각 (플라즈마 손상 없음)', status=ON_SALE, figures=NO_FIG, adoption=NO_FIG,
        apps='등방성 질화막 리세스 · 폴리 세정 · 3D 구조 질화막 패터닝 · SiGe 적층 고선택 패터닝 · 뒷면 제거',
        tech='고속 반복 식각 · 인시투 챔버 세정 · 높은 식각 속도·선택비')),
    ('psk-precia', 'PRECIA (Edge clean)', '피에스케이', '베벨·가장자리', 'psk_p', dict(
        method='이중 플라즈마 소스 베벨 식각', status=ON_SALE, figures='높은 생산성·낮은 CoO (수치 미기재)', adoption=NO_FIG,
        apps='웨이퍼 가장자리(베벨) 막·잔여물 제거', tech='이중 플라즈마 소스 · 자동 웨이퍼 센터링 · 비전 시스템으로 베벨 식각 모니터링')),
]

FIELD_KEYS = [c['id'] for c in COLUMNS if c['id'] not in ('name', 'country')]


def lam_rows():
    out = []
    for pid, name, group, page, fields in lam.PRODUCTS:
        f = {}
        for key, raw in fields.items():
            value, source = raw if isinstance(raw, tuple) else (raw, page)
            target = {'platform': 'config', 'features': 'adoption'}.get(key, key)
            f[target] = (value, 'lam_' + source)
        f.setdefault('status', ('기술 (Flex·Vantex에 적용)' if pid == 'cryo-3' else ON_SALE, 'lam_' + page))
        out.append(('lam-' + pid, name, 'Lam Research', LAM_GROUP[group], 'lam_' + page, f))
    return out


def build():
    sources = {sid: dict(title=title, url=url, checked=CHECKED, kind=kind, note=SOURCE_NOTE[kind])
               for sid, (title, url, kind) in SOURCES.items()}
    rows = []
    for pid, name, company, group, page, fields in lam_rows() + PRODUCTS:
        if company not in COMPANIES or group not in GROUPS:
            raise ValueError(f'{pid}: unknown company/group')
        unknown = set(fields) - set(FIELD_KEYS)
        if unknown:
            raise ValueError(f'{pid}: unknown fields {unknown}')
        reviews = {}
        merged = dict(fields, page=sources[page]['url'])
        for (rid, key), raw in USER_VALUES.items():
            if rid == pid:
                merged[key] = raw
        for key, raw in merged.items():
            value, source = raw if isinstance(raw, tuple) else (raw, page)
            if source not in sources:
                raise ValueError(f'{pid}.{key}: unknown source {source}')
            reviews[key] = dict(value=value, source=source, note=KIND_NOTE[sources[source]['kind']])
        reviews['name'] = dict(value=name, source=page, note='제조사 공식 제품명')
        reviews['country'] = dict(value=COMPANIES[company], source=page, note='제조사 본사 국가')
        rows.append(dict(id=pid, sheet_row=None, name=name, company=company, group=group, original={}, reviews=reviews,
                         review_note='제조사 공식 자료 기준. 처리량·가격은 제조사가 공개하지 않아 비워 두고, 확인된 자료가 생기면 출처와 함께 채웁니다.'))
    companies = [c for c in COMPANIES if any(r['company'] == c for r in rows)]
    return dict(
        id='process_etch_specs', name='식각 장비 · 업체별 비교', table_family='process', official_only=True,
        short_name='식각 장비', manual=True, frequency='irregular', source='각 제조사 공식 제품 페이지·보도자료·연혁',
        source_url='', source_label='출처는 아래 목록',
        basis_label='제조사 공식 자료 기준', updated=CHECKED, fetched=CHECKED,
        update_note='제조사 자료를 확인한 날짜 기준 스냅샷입니다. 새 장비·처리량·가격 자료가 생기면 scripts/build_process_etch_specs.py에 출처와 함께 추가합니다.',
        evidence_text=('모든 값은 각 제조사의 공식 제품 페이지, 보도자료, 회사 연혁에서 확인했습니다. 셀에 마우스를 올리면 그 값이 적힌 자료가 나옵니다. '
                       '처리량(WPH)과 가격은 제조사가 공개하지 않아 비워 뒀고, 확인된 자료를 받으면 출처와 함께 채웁니다.'),
        columns=COLUMNS, rows=rows, groups=GROUPS, name_key='name', default_group='all', default_view='overview', views=VIEWS,
        sources=sources, company_order=companies, countries={c: COMPANIES[c] for c in companies},
        group_label='식각 분야', item_label='장비', search_placeholder='장비명·공정·기술 검색',
        caption='제조사 공식 자료 기준 · 출시는 제조사가 밝힌 출시·발표·양산 판매 시점 (연도만 있으면 연도)',
        evidence_summary=f'{len(companies)}개 업체 · {len(rows)}개 장비 · 모든 값 제조사 공식 자료 확인',
        scroll_hint='셀에 마우스를 올리면 근거 · 맨 오른쪽 상세',
        note=('같은 식각 분야(도체·유전체·선택적 식각 등)에서 업체별 장비를 비교합니다. 위 대결표는 분야별로 각 업체가 내놓은 장비와 출시 연도를, '
              '아래 표는 장비별 세부 내용을 보여 줍니다. 제조사는 처리량·가격을 공개하지 않아 빈칸이며, 비용 우위는 제조사가 밝힌 주장(면적·소유비용 등)만 옮겼습니다. '
              '"출시"는 제조사가 밝힌 시점이고 기준이 제각각(출시·발표·첫 양산 판매)이라 셀에 마우스를 올려 근거를 확인하세요. '
              '세메스는 공식 사이트에 장비명·사양이 없어 분류만 적었습니다. 테스 CUMAX·SPICA는 회사가 건식 세정으로 분류하지만 '
              '선택적·등방성 식각 경쟁 장비라 여기 넣었습니다. 드라이 스트립·애싱 장비는 세정·스트립 분야에서 따로 다룹니다.'))


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(OUT)

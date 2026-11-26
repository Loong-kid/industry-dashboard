"""Applied Materials deposition product table, from Applied's own press releases.

Applied's website (product pages, newsroom, IR) refuses automated requests, so every value here was read from
the full text of Applied's press releases as distributed through GlobeNewswire and republished verbatim by
Nasdaq, Yahoo Finance and The Globe and Mail (checked 2026-11-27). Like Lam, Applied does not publish numeric
tool specs, so the table records what each release states: deposition method, platform, announcement date,
quoted figures, target applications, core technology and adoption. Anything a release does not state is blank.

    python scripts/build_amat_dep_specs.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/semicon/amat_dep_specs.json'
CHECKED = '2026-11-27'
NASDAQ = 'https://www.nasdaq.com/press-release/'
YAHOO = 'https://finance.yahoo.com/news/'

COLUMNS = [
    dict(id='name', label='제품', width=190),
    dict(id='method', label='증착 방식', width=150),
    dict(id='platform', label='플랫폼', width=110),
    dict(id='launched', label='발표', width=110, date=True),
    dict(id='figures', label='공개 수치', width=280),
    dict(id='apps', label='주요 공정·소자', width=280),
    dict(id='tech', label='핵심 기술', width=300),
    dict(id='features', label='특징·채택', width=300),
    dict(id='page', label='보도자료', width=100, url=True),
]
VIEWS = [
    dict(id='overview', label='한눈에 보기', keys=['name', 'method', 'launched', 'figures', 'apps', 'tech']),
    dict(id='detail', label='전체 사양', keys=['name', 'method', 'platform', 'launched', 'figures', 'apps', 'tech', 'features', 'page']),
]
GROUPS = ['트랜지스터', '콘택·배선', '패터닝 막', '첨단 패키징·HBM']

# Applied press releases: (title, url of the verbatim copy that was read).
SOURCES = {
    'r2021_cubs': ('AMAT 보도자료 2021-06-16 · 3nm 배선 (Endura Copper Barrier Seed IMS)',
                   YAHOO + 'applied-materials-breakthrough-chip-wiring-113000579.html'),
    'r2022_gaa': ('AMAT 보도자료 2022-04-21 · EUV 2D 스케일링과 GAA',
                  NASDAQ + 'applied-materials-technologies-enable-2d-scaling-with-euv-and-3d-gate-all-around'),
    'r2023_hi': ('AMAT 보도자료 2023-07-10 · 하이브리드 본딩·TSV',
                 YAHOO + 'applied-materials-advances-heterogeneous-chip-113000121.html'),
    'r2024_pattern': ('AMAT 보도자료 2024-02-26 · 옹스트롬 시대 패터닝',
                      NASDAQ + 'applied-materials-expands-patterning-solutions-portfolio-for-angstrom-era-chipmaking'),
    'r2024_wiring': ('AMAT 보도자료 2024-07-08 · 배선 (Black Diamond · Volta Ru)',
                     NASDAQ + 'applied-materials-unveils-chip-wiring-innovations-more-energy-efficient-computing'),
    'r2025_next': ('AMAT 보도자료 2025-10-07 · Kinex · Xtera · PROVision 10',
                   NASDAQ + 'applied-materials-unveils-next-gen-chipmaking-products-supercharge-ai-performance'),
    'r2026_feb': ('AMAT 보도자료 2026-02-10 · GAA 트랜지스터·배선 (Spectral Mo ALD)',
                  'https://www.theglobeandmail.com/investing/markets/stocks/AMAT/pressreleases/36491210/'
                  'applied-materials-unveils-transistor-and-wiring-innovations-for-faster-ai-chips/'),
    'r2026_apr': ('AMAT 보도자료 2026-04-08 · 옹스트롬 로직 증착 (Selective Nitride · Trillium)',
                  NASDAQ + 'applied-materials-introduces-deposition-systems-angstrom-era-logic-chips-2026-04-08'),
    'r2026_jun15': ('AMAT 보도자료 2026-06-15 · 3D 구조 증착·선택 식각 (Spectral SiN ALD)',
                    NASDAQ + 'applied-materials-unveils-deposition-and-selective-etch-systems-advance-3d-chip'),
    'r2026_jun25': ('AMAT 보도자료 2026-06-25 · DRAM·첨단 패키징',
                    NASDAQ + 'applied-materials-introduces-new-systems-accelerate-dram-and-advanced-packaging-ai'),
}
ADOPT_2NM = '2nm 이하 GAA 공정에서 주요 로직 업체가 채택 중'

# (id, name, group, release, fields). A value is text (cites the row's release) or (text, source id).
PRODUCTS = [
    # --- 트랜지스터 ---
    ('xtera-epi', 'Centura Xtera Epi', '트랜지스터', 'r2025_next', dict(
        method='에피택시 (증착-식각 반복)', platform='Centura', launched='2025-10-07',
        figures='기존 에피 대비 가스 사용 50% 절감 · 셀 간 균일도 40% 이상 개선',
        apps='2nm 이하 GAA 트랜지스터 소스/드레인 (고종횡비 트렌치 채움)',
        tech='저용적 챔버 · 사전 세정·식각 통합 · 트렌치 입구를 계속 넓히며 쌓는 증착-식각 공정',
        features='보이드 없는 균일한 소스/드레인. 주요 로직·메모리 업체가 채택 중')),
    ('prime-epi', 'Centura Prime Epi (개선판)', '트랜지스터', 'r2026_jun25', dict(
        method='선택적 에피택시', platform='Centura', launched='2026-06-25',
        figures='설치 면적 20% 축소',
        apps='DRAM 주변회로 트랜지스터 소스/드레인 (HBM·차세대 DDR)',
        tech='도핑된 SiGe·SiP 선택 성장 · 변형(strain) 공학 + 정밀 도핑 제어',
        features='로직용 에피 기술을 DRAM으로 옮긴 장비. 구동 전류·효율 향상. 원조 Prime Epi는 10여 년 전 채널 SiGe 에피를 처음 도입')),
    ('trillium-ald', 'Endura Trillium ALD', '트랜지스터', 'r2026_apr', dict(
        method='금속 ALD (IMS 통합 장비)', platform='Endura', launched='2026-04-08',
        figures='수치 미기재 (옹스트롬 단위 두께 제어)',
        apps='GAA 메탈 게이트 스택 (트랜지스터별 문턱전압 조정)',
        tech='여러 금속 증착 단계를 고진공 한 플랫폼에 통합 · 더 얇은 일함수 금속 · 부피 없는(volume-less) 다이폴 소재',
        features='FinFET 여러 세대에서 메탈 게이트 증착 표준이던 장비를 GAA용으로 개량. ' + ADOPT_2NM)),
    ('selective-nitride', 'Producer Precision Selective Nitride PECVD', '트랜지스터', 'r2026_apr', dict(
        method='선택적 PECVD (바텀업)', platform='Producer', launched='2026-04-08',
        figures='수치 미기재',
        apps='GAA 얕은 트렌치 소자분리(STI) 보호',
        tech='업계 첫 선택적 바텀업 증착 · 트렌치 산화막 위에만 치밀한 질화막(SiN) · 저온 공정',
        features='후속 공정에서 STI가 깎이지 않게 해 기생 용량·누설을 줄임. ' + ADOPT_2NM)),
    ('spectral-sin', 'Centris Spectral SiN ALD', '트랜지스터', 'r2026_jun15', dict(
        method='플라즈마 ALD (질화막)', platform='Centris · Spectral', launched='2026-06-15',
        figures='수치 미기재',
        apps='GAA 콘택 라이너 · DRAM·로직의 표면 보호·절연·패터닝 스페이서용 SiN',
        tech='고밀도 마이크로파 플라즈마(이온 손상 없이 고밀도) · 저온 증착 · 쿼드 리액터 Spectral 플랫폼',
        features='깊고 좁은 3D 구조 안까지 균일한 SiN. 주요 업체가 채택 중')),
    ('gaa-oxide-ims', 'GAA 게이트 산화막 IMS (제품명 미공개)', '트랜지스터', 'r2022_gaa', dict(
        method='ALD + 열·플라즈마 처리 (IMS 통합 장비)', launched='2022-04-21',
        figures='등가 산화막 두께(EOT) 1.5 Å 감소 · 같은 성능에서 게이트 누설 10배 이상 감소',
        apps='GAA 트랜지스터 게이트 산화막 스택',
        tech='ALD·열처리·플라즈마 처리·계측을 고진공 한 장비에 통합',
        features='같은 발표에서 GAA 메탈 게이트용 IMS도 공개 (금속 ALD를 고진공에서 수행)')),
    # --- 콘택·배선 ---
    ('spectral-mo', 'Centris Spectral Molybdenum ALD', '콘택·배선', 'r2026_feb', dict(
        method='선택적 금속 ALD (몰리브덴)', platform='Centris · Spectral', launched='2026-02-10',
        figures='콘택 저항 최대 15% 감소 (현 업계 기준 Endura Volta Selective Tungsten 대비)',
        apps='트랜지스터-배선 콘택 금속을 텅스텐에서 몰리브덴으로 전환 (2nm 이하)',
        tech='단결정 몰리브덴 선택 증착 · 쿼드 리액터 · 플라즈마·열 공정 · 시간·공간 분할 ALD 겸용',
        features='새 ALD 제품군 Spectral로 발표. ' + ADOPT_2NM)),
    ('cubs-ims', 'Endura Copper Barrier Seed IMS', '콘택·배선', 'r2021_cubs', dict(
        method='ALD·PVD·CVD 통합 (IMS)', platform='Endura', launched='2021-06-16',
        figures='비아 접촉 저항 최대 50% 감소',
        apps='3nm 이하 로직 구리 배선 배리어·시드',
        tech='ALD·PVD·CVD·구리 리플로·표면 처리·계면 공학·계측 7개 공정을 고진공 한 장비에 통합 · 선택적 ALD로 비아 계면의 고저항 배리어 제거',
        features='구리 리플로로 좁은 배선도 보이드 없이 채움. 발표 당시 주요 파운드리·로직 업체가 사용 중')),
    ('volta-ru', 'Endura CuBS IMS with Volta Ruthenium CVD', '콘택·배선', 'r2024_wiring', dict(
        method='CVD·PVD 등 통합 (IMS)', platform='Endura', launched='2024-07-08',
        figures='라이너 두께 33% 줄여 2nm · 배선 저항 최대 25% 감소',
        apps='2nm 이하 구리 배선 라이너',
        tech='루테늄·코발트(RuCo) 이원 금속 라이너(업계 첫 조합) · 6개 기술을 고진공 한 장비에 통합',
        features='모든 주요 로직 업체가 채택 중, 3nm 공정부터 출하')),
    ('black-diamond', 'Producer Black Diamond PECVD (개선판)', '콘택·배선', 'r2024_wiring', dict(
        method='PECVD (저유전율 막)', platform='Producer', launched='2024-07-08',
        figures='수치 미기재 (최저 k값을 더 낮추고 기계 강도 향상)',
        apps='구리 배선 층간 저유전(low-k) 절연막 · 2nm 이하 · 3D 적층',
        tech='낮은 k값과 높은 기계 강도를 함께 확보한 Black Diamond 신소재',
        features='수십 년간 low-k 막을 이끈 제품군의 최신판. 모든 주요 로직·DRAM 업체가 채택 중')),
    # --- 패터닝 막 ---
    ('pioneer', 'Producer XP Pioneer CVD', '패터닝 막', 'r2024_pattern', dict(
        method='CVD (탄소 패터닝 막)', platform='Producer XP', launched='2024-02-26',
        figures='수치 미기재',
        apps='EUV·High-NA EUV 패턴 전사막 (포토레지스트 공정 전 증착) · DRAM 패터닝',
        tech='식각에 강한 고밀도 탄소 조성 · 더 얇은 막 스택 · Sculpta·Sym3 Y Magnum과 공동 최적화',
        features='주요 메모리 업체가 DRAM 패터닝에 채택')),
    ('stensar', 'Stensar Advanced Patterning Film', '패터닝 막', 'r2022_gaa', dict(
        method='CVD (EUV 하드마스크)', platform='Precision CVD', launched='2022-04-21',
        figures='수치 미기재',
        apps='EUV 전사층·하드마스크 (기존 스핀온 방식 대체)',
        tech='CVD로 하드마스크 두께·식각 내성을 공정별로 조정',
        features='웨이퍼 전체에서 균일한 EUV 패턴 전사')),
    # --- 첨단 패키징·HBM ---
    ('insepra', 'Insepra SiCN', '첨단 패키징·HBM', 'r2023_hi', dict(
        method='유전막 증착 (방식 미기재)', launched='2023-07-10',
        figures='수치 미기재 (업계 최고 유전체 접합 강도)',
        apps='하이브리드 본딩 접합면 유전막',
        tech='새 실리콘 탄소 질화막(SiCN) 소재 · 구리 확산 방지',
        features='접합이 단단해져 같은 면적에 더 많은 구리-구리 연결 가능')),
    ('invia2', 'Producer InVia 2 CVD', '첨단 패키징·HBM', 'r2023_hi', dict(
        method='CVD (유전체 라이너)', platform='Producer', launched='2023-07-10',
        figures='수치 미기재 (ALD보다 높은 처리량)',
        apps='TSV 절연 라이너 (로직·메모리)',
        tech='독자 인시투 증착으로 고종횡비 TSV에서도 균일한 막',
        features='웨이퍼당 TSV 비용을 낮춤. Ventura 2 PVD와 공동 최적화')),
    ('ventura2', 'Endura Ventura 2 PVD', '첨단 패키징·HBM', 'r2023_hi', dict(
        method='PVD (금속)', platform='Endura', launched='2023-07-10',
        figures='종횡비 최대 20:1 TSV',
        apps='TSV 금속 배선 증착',
        tech='금속 TSV 증착 제어 강화로 완전 채움 · InVia 2 CVD와 공동 최적화',
        features='모든 첨단 파운드리·로직 업체와 주요 DRAM 업체 전부가 도입 중')),
    ('avila', 'Producer Avila PECVD (2023년판)', '첨단 패키징·HBM', 'r2023_hi', dict(
        method='초저온 PECVD', platform='Producer', launched='2023-07-10',
        figures='임시 접착제가 상하는 약 200°C보다 낮은 온도에서 증착',
        apps='TSV 리빌(reveal) 후 절연막',
        tech='초저온·고속 고품질 유전막',
        features='임시 캐리어에 붙인 얇은 웨이퍼의 수율 손실을 막음')),
    ('avila2', 'Producer Avila 2 PECVD', '첨단 패키징·HBM', 'r2026_jun25', dict(
        method='PECVD (응력 균형 유전막)', platform='Producer', launched='2026-06-25',
        figures='12단·16단 및 그 이상 HBM 적층 지원 (HBM 다이는 표준 웨이퍼 두께의 약 1/25)',
        apps='HBM TSV 주변 유전막 · 메모리·로직 3D 집적',
        tech='응력 균형 유전막으로 초박형 DRAM 다이의 휨·변형 억제',
        features='적층이 늘수록 커지는 본딩 실패·수율 손실을 줄임')),
    ('nokota-vmax2', 'Nokota VMax 2 ECD', '첨단 패키징·HBM', 'r2026_jun25', dict(
        method='전기도금 (ECD, 구리)', platform='Nokota', launched='2026-06-25',
        figures='수치 미기재',
        apps='TSV 채움 · 마이크로범프 등 미세 피치 연결',
        tech='APT(Adaptive Pattern Tuning): 전기장을 동적으로 조정해 레이아웃에 따른 편차 보정',
        features='웨이퍼 전체에서 TSV·범프 높이를 고르게 맞춰 적층 수율 향상')),
]

FIELD_KEYS = [c['id'] for c in COLUMNS if c['id'] != 'name']
NOTE = '보도자료 원문 (GlobeNewswire 배포본을 그대로 실은 게재본으로 확인. AMAT 사이트는 자동 접근 차단).'


def build():
    sources = {sid: dict(title=title, url=url, checked=CHECKED, note=NOTE) for sid, (title, url) in SOURCES.items()}
    rows = []
    for pid, name, group, release, fields in PRODUCTS:
        unknown = set(fields) - set(FIELD_KEYS)
        if unknown:
            raise ValueError(f'{pid}: unknown fields {unknown}')
        reviews = {}
        for key, raw in dict(fields, page=sources[release]['url']).items():
            value, source = raw if isinstance(raw, tuple) else (raw, release)
            if source not in sources:
                raise ValueError(f'{pid}.{key}: unknown source {source}')
            reviews[key] = dict(value=value, source=source, note='AMAT 보도자료 기재')
        reviews['name'] = dict(value=name, source=release, note='AMAT 보도자료의 제품명')
        rows.append(dict(id=pid, sheet_row=None, name=name, company='Applied Materials', group=group, original={}, reviews=reviews,
                         review_note='AMAT 보도자료 기준. 수치는 AMAT가 발표한 값이며 실제 팹 조건에 따라 다릅니다.'))
    return dict(
        id='amat_dep_specs', name='Applied Materials 증착 장비 · 제품별 사양', table_family='deposition', official_only=True,
        short_name='AMAT 증착 장비', manual=True, frequency='irregular', source='Applied Materials 보도자료',
        source_url='https://www.appliedmaterials.com/us/en/newsroom/press-releases.html', source_label='AMAT 보도자료 목록 ↗', basis_label='AMAT 보도자료 기준',
        updated=CHECKED, fetched=CHECKED,
        update_note='AMAT 보도자료를 확인한 날짜 기준 스냅샷입니다. 새 증착 장비 발표 시 scripts/build_amat_dep_specs.py를 고칩니다.',
        evidence_text=('모든 값은 아래 AMAT 보도자료 원문에서 확인했습니다. AMAT 홈페이지가 자동 접근을 막아, '
                       'GlobeNewswire로 배포된 원문을 그대로 실은 Nasdaq·Yahoo Finance·Globe and Mail 게재본으로 읽었습니다. '
                       '셀에 마우스를 올리면 그 값이 적힌 보도자료가 나옵니다. 보도자료에 없는 항목은 —로 둡니다.'),
        columns=COLUMNS, rows=rows, name_key='name', default_group='all', default_view='overview', views=VIEWS,
        sources=sources, company_order=['Applied Materials'], group_label='용도', item_label='제품',
        search_placeholder='제품명·공정·기술 검색',
        caption='AMAT 보도자료 기준 · 발표는 해당 보도자료 날짜(제품군 첫 출시일이 아닐 수 있음)',
        evidence_summary=f'보도자료 {len(SOURCES)}건(2021~2026) · {len(rows)}개 제품 · 모든 값 원문 확인',
        scroll_hint='셀에 마우스를 올리면 근거 · 맨 오른쪽 상세',
        note=('2021~2026년 AMAT 보도자료에서 새로 발표되거나 개량된 증착 장비(CVD·PVD·ALD·에피택시·전기도금)만 담았습니다. '
              'AMAT도 Lam처럼 처리량 같은 장비 사양을 공개하지 않아, 방식·용도·핵심 기술·공개 수치를 보도자료에서 옮겼습니다. '
              '"공개 수치"는 AMAT가 발표한 대표값이라 비교 기준이 제각각이니 제품끼리 단순 비교하지 마세요. '
              '"발표"는 그 보도자료 날짜라, Prime Epi·Trillium·Black Diamond·Avila처럼 오래된 제품군은 개량판 발표일입니다. '
              '2019년 MRAM·PCRAM용 Endura Clover·Impulse PVD는 원문 보도자료를 읽을 수 없어 넣지 않았습니다. '
              '가격·출하 대수는 공개되지 않아 넣지 않았습니다.'))


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(OUT)

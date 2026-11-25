"""Lam Research etch product table, from Lam's official product pages and press releases.

Lam does not publish numeric tool specs (throughput, resolution) on its product pages the way ASML does,
so this table records what Lam itself states: etch type, platform, launch date, the figures quoted in its
launch releases, key applications, model line-up and core technologies. Every cell cites the Lam page or
release it was read from (checked 2026-11-26); anything Lam does not state is left blank.

    python scripts/build_lam_etch_specs.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/semicon/lam_etch_specs.json'
CHECKED = '2026-11-26'
PRODUCT = 'https://www.lamresearch.com/product/'
NEWS = 'https://newsroom.lamresearch.com/'

COLUMNS = [
    dict(id='name', label='제품', width=170),
    dict(id='method', label='식각 방식', width=160),
    dict(id='platform', label='플랫폼', width=150),
    dict(id='launched', label='공식 발표', width=110, date=True),
    dict(id='figures', label='공개 수치', width=280),
    dict(id='apps', label='주요 공정·소자', width=280),
    dict(id='lineup', label='모델 라인업', width=220),
    dict(id='tech', label='핵심 기술', width=280),
    dict(id='features', label='특징', width=320),
    dict(id='page', label='공식 페이지', width=100, url=True),
]
VIEWS = [
    dict(id='overview', label='한눈에 보기', keys=['name', 'method', 'launched', 'figures', 'apps', 'tech']),
    dict(id='detail', label='전체 사양', keys=['name', 'method', 'platform', 'launched', 'figures', 'apps', 'lineup', 'tech',
                                            'features', 'page']),
]
GROUPS = ['도체 식각', '유전체 식각', '금속 식각', '실리콘 딥 식각', '선택적 식각', '베벨 (웨이퍼 가장자리)', '플랫폼', '재생 장비 (Reliant)']

# Sources: product pages first, then launch releases. (title, url, note)
SOURCES = {
    'p_akara': ('Lam · Akara 제품 페이지', PRODUCT + 'akara/'),
    'p_kiyo': ('Lam · Kiyo 제품군 페이지', PRODUCT + 'kiyo-product-family/'),
    'p_sensei': ('Lam · Sense.i 제품군 페이지', PRODUCT + 'sense-i/'),
    'p_vantex': ('Lam · Vantex 제품군 페이지', PRODUCT + 'vantex/'),
    'p_flex': ('Lam · Flex 제품군 페이지', PRODUCT + 'flex-product-family/'),
    'p_cryo': ('Lam · 극저온 식각(Cryogenic Etching) 페이지', 'https://www.lamresearch.com/products/our-solutions/cryogenic-etching/'),
    'p_versys': ('Lam · Versys Metal 제품군 페이지', PRODUCT + 'versys-metal-product-family/'),
    'p_syndion': ('Lam · Syndion 제품군 페이지', PRODUCT + 'syndion-product-family/'),
    'p_selective': ('Lam · 선택적 식각 제품군 페이지', PRODUCT + 'selective-etch-product-family/'),
    'p_coronus': ('Lam · Coronus 제품군 페이지', PRODUCT + 'coronus-product-family/'),
    'p_reliant': ('Lam · Reliant 식각 제품 페이지', PRODUCT + 'reliant-etch-products/'),
    'r_sensei': ('Lam 보도자료 2020-03-03 · Sense.i 발표',
                 NEWS + '2020-03-03-Lam-Research-Breaks-New-Ground-in-Etch-Technology-and-Productivity-for-Chipmaking-Processes'),
    'r_vantex': ('Lam 보도자료 2021-01-27 · Vantex 발표',
                 NEWS + '2021-01-27-Lam-Research-Advances-Next-Generation-3D-Memory-Manufacturing-with-Revolutionary-New-Etch-Technology'),
    'r_syndion2007': ('Lam 보도자료 2007-08-20 · 첫 300 mm Syndion 출하',
                      NEWS + '2007-08-20-Lam-Research-Corporation-Ships-First-300-mm-2300-R-Syndion-TM-System-for-3-D-IC-Through-Silicon-Via-Etch'),
    'r_syndiongp': ('Lam 보도자료 2021-12-07 · Syndion GP 발표',
                    NEWS + '2021-12-07-Lam-Research-Unveils-Syndion-GP-to-Help-Chipmakers-Meet-Demand-for-Advanced-Power-Devices'),
    'r_selective': ('Lam 보도자료 2022-02-09 · 선택적 식각 3종 발표',
                    NEWS + '2022-02-09-Lam-Research-Introduces-Groundbreaking-Suite-of-Selective-Etch-Tools-to-Accelerate-Chipmakers-3D-Roadmaps'),
    'r_coronusdx': ('Lam 보도자료 2023-06-20 · Coronus DX 발표',
                    NEWS + '2023-06-20-Lam-Research-Introduces-Worlds-First-Bevel-Deposition-Solution-to-Increase-Yield-in-Chip-Production'),
    'r_cryo3': ('Lam 보도자료 2024-07-31 · Lam Cryo 3.0 발표',
                NEWS + '2024-07-31-Lam-Research-Introduces-Lam-Cryo-TM-3-0-Cryogenic-Etch-Technology-to-Accelerate-Scaling-of-3D-NAND-for-the-AI-Era'),
    'r_akara': ('Lam 보도자료 2025-02-19 · Akara 발표',
                NEWS + '2025-02-19-Lam-Research-Unveils-Industrys-Most-Advanced-Conductor-Etch-Technology-to-Date'),
}

SELECTIVE_APPS = '더미 폴리 제거 · GAA SiGe 제거 · 산화막 리세스 · Si 트리밍 · 소스/드레인 증착 전 세정 · low-k 제거 · 표면 오염 제거·개질 (제품군 공통)'
SELECTIVE_FIGURES = '삼성전자 첨단 로직 핵심 공정 10여 곳에 사용 (2022 발표 당시, 3종 공통)'

# (id, name, group, page source, fields). A value is either text (cites the page source) or (text, source id).
PRODUCTS = [
    ('akara', 'Akara', '도체 식각', 'p_akara', dict(
        method='플라즈마 도체 식각', platform='Sense.i', launched=('2025-02-19', 'r_akara'),
        figures='플라즈마 응답 기존 소스보다 100배 빠름 · 밀리초 단위 응답 · 옹스트롬 수준 CD 균일도',
        apps=('GAA 트랜지스터·6F² DRAM·3D NAND, 4F² DRAM·CFET·3D DRAM으로 확장 가능', 'r_akara'),
        lineup='Akara',
        tech=('DirectDrive(업계 첫 고체 플라즈마 소스) · TEMPO 플라즈마 펄싱 · SNAP 이온 에너지 제어 · Equipment Intelligence 자동 유지보수', 'r_akara'),
        features=('Kiyo를 잇는 차세대 도체 식각기. 앞선 플래너 DRAM·파운드리 GAA 여러 공정에서 양산 기준 장비(POR)로 채택, 재주문 확보', 'r_akara'))),
    ('kiyo', 'Kiyo 제품군', '도체 식각', 'p_kiyo', dict(
        method='RIE · 플라즈마 ALE', launched=('2004', 'r_akara'),
        figures=('양산 중인 챔버 3만 개 이상 (2025-02 기준)', 'r_akara'),
        apps='STI · 소스/드레인 · 고유전율 메탈게이트(HKMG) · FinFET·트라이게이트 · 멀티 패터닝 · 3D NAND',
        lineup='Versys Kiyo · Kiyo45 · Kiyo C·E·F·G 시리즈',
        tech='Hydra(앞 공정 패턴 편차를 보정하는 CD 균일도 제어) · Corvus(가장자리 다이 수율용 플라즈마 시스 조정) · 플라즈마 ALE · 웨이퍼 없는 자동 세정',
        features='대칭 챔버와 정전척으로 균일도·재현성 확보, 여러 세대에 걸쳐 업그레이드 가능. 일부 모델은 Reliant 재생 장비로도 공급')),
    ('sense-i', 'Sense.i', '플랫폼', 'p_sensei', dict(
        method='RIE (도체·유전체 식각)', platform='Sense.i (자체 플랫폼)', launched=('2020-03-03', 'r_sensei'),
        figures=('식각 출력 밀도(같은 면적당 생산량) 50% 이상 개선', 'r_sensei'),
        apps='로직·메모리의 핵심·준핵심 도체 식각, 유전체 식각', lineup='Sense.i',
        tech='Equipment Intelligence · 자율 캘리브레이션·유지보수 · 스마트 센싱',
        features=('Kiyo·Flex 공정 모듈 기술을 이어받은 고밀도 플랫폼. 머신러닝으로 공정 편차를 스스로 보정. 발표 당시 Lam 식각 장비가 매달 웨이퍼 400만 장 이상 처리', 'r_sensei'))),
    ('vantex', 'Vantex', '유전체 식각', 'p_vantex', dict(
        method='RIE · 극저온(Cryo)', platform=('Sense.i 전용 챔버', 'r_vantex'), launched=('2021-01-27', 'r_vantex'),
        figures='수치 미기재', apps='3D NAND 고종횡비 홀·트렌치·콘택 · DRAM 커패시터 셀', lineup='Vantex',
        tech=('기존보다 높은 RF 출력 · RF 펄싱 · 식각 수직 각도 제어 · Sense.i 센서 데이터 활용', 'r_vantex'),
        features='가장 높은 종횡비 식각과 CD·선택비 제어, 가장 빠른 식각 속도, 웨이퍼 간 재현성(Equipment Intelligence)')),
    ('flex', 'Flex 제품군', '유전체 식각', 'p_flex', dict(
        method='RIE · ALE · 극저온(Cryo)', figures='수치 미기재',
        apps='low-k·초저유전 듀얼 다마신 · 자기정렬 콘택 · 커패시터 셀 · 마스크 오픈 · 3D NAND 고종횡비 홀·트렌치·콘택',
        lineup='Exelan Flex · Flex45 · Flex D·E·F·G·H 시리즈',
        tech='다중 주파수·소용적 confined 플라즈마 · AMMP 펄싱 기반 플라즈마 ALE · 인시투 다단계 식각',
        features=('주요 메모리 업체 모두가 3D NAND 양산에 쓰는 고종횡비 유전체 식각기. Lam Cryo 3.0 적용 가능', 'r_cryo3'))),
    ('cryo-3', 'Lam Cryo 3.0', '유전체 식각', 'p_cryo', dict(
        method='극저온 유전체 식각 (장비 위 기술)', platform='Flex · Vantex(Sense.i)에 적용', launched=('2024-07-31', 'r_cryo3'),
        figures=('채널 깊이 최대 10 µm, 위아래 CD 편차 0.1% 미만 · 기존 대비 식각 속도 2.5배 · 웨이퍼당 에너지 40%↓ · 배출 최대 90%↓(Lam 추정, 외부 검증 없음)', 'r_cryo3'),
        apps='3D NAND 채널 홀 (400단 이상)', lineup=('3세대 극저온 식각 (1세대는 2019년 양산 도입)', 'r_cryo3'),
        tech=('영하 온도 · 고출력 confined 플라즈마 반응기 · 새 식각 화학 · Vantex 펄스 플라즈마와 결합', 'r_cryo3'),
        features=('극저온 식각으로 웨이퍼 500만 장 생산. NAND 양산 중인 Lam 고종횡비 유전체 챔버 7,500개 이상 중 약 1,000개가 극저온', 'r_cryo3'))),
    ('versys-metal', 'Versys Metal 제품군', '금속 식각', 'p_versys', dict(
        method='RIE', figures='수치 미기재', apps='TiN 금속 하드마스크 · 고밀도 알루미늄 배선 · 알루미늄 패드',
        lineup='Versys Metal · Metal45 · Metal L·M·N', tech='대칭 챔버·독립 공정 조정 · 독자 챔버 세정 기술',
        features='BEOL 금속 식각과 금속 하드마스크 패터닝. 여러 세대 업그레이드 가능, 일부 모델은 Reliant 재생 장비로 공급')),
    ('syndion', 'Syndion 제품군', '실리콘 딥 식각', 'p_syndion', dict(
        method='DRIE · RIE', platform=('2300 (200·300 mm 겸용)', 'r_syndion2007'), launched=('2007-08-20', 'r_syndion2007'),
        figures=('비아 폭 2~100 µm, 깊이 20~400 µm 이상 식각 (2007 첫 300 mm 출하 당시)', 'r_syndion2007'),
        apps='HBM·첨단 패키징 TSV · CMOS 이미지센서 고종횡비 구조 · 전력 반도체·아날로그·MEMS 트렌치 · 웨이퍼 후면 공정',
        lineup='Syndion C · F 시리즈 · G 시리즈',
        tech='RAP(식각·증착 빠른 교대)로 깊이 균일도 · TSV 스택(실리콘·유전체·도전막) 인시투 식각',
        features=('2021-12 Syndion GP 발표(전력 반도체·PMIC, 200·300 mm 겸용). 300 mm Syndion GS는 패키징·HBM·CIS용, 200 mm는 DSiE', 'r_syndiongp'))),
    ('argos', 'Argos', '선택적 식각', 'p_selective', dict(
        method=('라디칼 표면 처리', 'r_selective'), launched=('2022-02-09', 'r_selective'),
        figures=(SELECTIVE_FIGURES, 'r_selective'), apps=SELECTIVE_APPS, lineup='Argos',
        tech=('MARS(준안정 활성 라디칼 소스)', 'r_selective'),
        features=('웨이퍼 표면을 선택적으로 개질하고 오염을 제거해 다음 공정에 맞게 처리', 'r_selective'))),
    ('prevos', 'Prevos', '선택적 식각', 'p_selective', dict(
        method=('기상(vapor) 선택적 식각', 'r_selective'), launched=('2022-02-09', 'r_selective'),
        figures=(SELECTIVE_FIGURES, 'r_selective'), apps=SELECTIVE_APPS, lineup='Prevos',
        tech=('Lam 독자 화학 · 기상 기술 · 빠른 온도 제어 (화학 추가 가능)', 'r_selective'),
        features=('원자층 정밀도로 산화막·실리콘·금속을 초고선택비 식각. Selis와 한 장비로 통합 공급 가능', 'r_selective'))),
    ('selis', 'Selis', '선택적 식각', 'p_selective', dict(
        method=('라디칼 + 열 식각', 'r_selective'), launched=('2022-02-09', 'r_selective'),
        figures=(SELECTIVE_FIGURES, 'r_selective'), apps=SELECTIVE_APPS, lineup='Selis',
        tech=('라디칼 식각과 열 식각 병행', 'r_selective'),
        features=('구조 손상 없이 위아래 균일한 초고선택비 식각. Prevos와 통합 시 다층 선택적 식각·대기 시간(queue time) 제어', 'r_selective'))),
    ('coronus', 'Coronus · Coronus HP', '베벨 (웨이퍼 가장자리)', 'p_coronus', dict(
        method='플라즈마 베벨 식각', launched=('2007', 'r_coronusdx'),
        figures=('식각·증착 단계마다 수율 0.2~0.5%p 추가, 전체 공정 최대 5% 개선 · 설치 챔버 수천 개', 'r_coronusdx'),
        apps='STI·게이트·MOL·BEOL 식각 후 · 증착 전후 · 노광 전 · 금속막 제거 · 습식·건식 식각 중 베벨 보호',
        lineup='Coronus · Coronus HP',
        tech='독자 플라즈마 confinement로 다이 영역 보호 · α-카본·탄소 잔여물 제거(업계 유일 베벨 세정)',
        features=('웨이퍼 가장자리의 막·잔여물을 걷어내 결함원을 없앰. 모든 주요 반도체 업체가 사용', 'r_coronusdx'))),
    ('coronus-dx', 'Coronus DX', '베벨 (웨이퍼 가장자리)', 'p_coronus', dict(
        method=('베벨 증착 (식각 아님)', 'r_coronusdx'), launched=('2023-06-20', 'r_coronusdx'), figures='수치 미기재',
        apps=('3D 패키징 웨이퍼 본딩 · 3D NAND 긴 습식 식각 중 가장자리 보호 · 차세대 로직', 'r_coronusdx'), lineup='Coronus DX',
        tech=('웨이퍼 가장자리 양면에 보호 유전막을 한 번에 증착 · 정밀 웨이퍼 센터링·통합 계측', 'r_coronusdx'),
        features=('업계 첫 베벨 증착 솔루션. 주요 고객 팹에서 양산 사용 중(발표 당시)', 'r_coronusdx'))),
    ('reliant', 'Reliant 식각 제품', '재생 장비 (Reliant)', 'p_reliant', dict(
        method='RIE · DRIE', figures='수치 미기재',
        apps='도체·유전체·금속 식각 · 특수막(PZT·GaN·AlGaN·SiC) · MEMS·전력 반도체·TSV 실리콘 딥 식각',
        lineup='Kiyo(~Kiyo45) · Flex(~Flex45) · DSiE · Syndion · TCP 9400 · TCP 9600',
        tech='대칭 챔버·정전척 · 인시투 다단계 식각 · 고종횡비 제어',
        features='150~300 mm 웨이퍼. MEMS·전력·IoT 같은 특수 공정용과 기존 팹 수명 연장용 장비')),
]

FIELD_KEYS = [c['id'] for c in COLUMNS if c['id'] != 'name']


def build():
    sources = {sid: dict(title=title, url=url, checked=CHECKED,
                         note='보도자료 원문의 Lam 발표 내용.' if sid.startswith('r_') else '제품 페이지 본문(식각 방식·주요 공정·라인업·핵심 기술).')
               for sid, (title, url) in SOURCES.items()}
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
            reviews[key] = dict(value=value, source=source,
                                note='Lam 보도자료 기재' if source.startswith('r_') else 'Lam 공식 제품 페이지 기재')
        reviews['name'] = dict(value=name, source=page, note='Lam 공식 제품명')
        rows.append(dict(id=pid, sheet_row=None, name=name, company='Lam Research', group=group, original={}, reviews=reviews,
                         review_note='Lam 공식 제품 페이지와 보도자료 기준. 수치는 Lam이 발표한 값이며 실제 팹 조건에 따라 다릅니다.'))
    return dict(
        id='lam_etch_specs', name='Lam Research 식각 장비 · 제품별 사양', table_family='etch', official_only=True,
        short_name='Lam 식각 장비', manual=True, frequency='irregular', source='Lam Research 공식 제품 페이지·보도자료',
        source_url='https://www.lamresearch.com/products/our-processes/etch/', updated=CHECKED, fetched=CHECKED,
        update_note='Lam 제품 페이지와 보도자료를 확인한 날짜 기준 스냅샷입니다. 새 장비 발표 시 scripts/build_lam_etch_specs.py를 고칩니다.',
        evidence_text='모든 값은 아래 Lam 공식 제품 페이지와 보도자료에서 확인했습니다. 셀에 마우스를 올리면 그 값이 적힌 페이지가 나옵니다. Lam이 밝히지 않은 항목은 —로 둡니다.',
        columns=COLUMNS, rows=rows, name_key='name', default_group='all', default_view='overview', views=VIEWS,
        sources=sources, company_order=['Lam Research'], group_label='분류', item_label='제품',
        search_placeholder='제품명·공정·기술 검색',
        caption='Lam 공식 발표 기준 · 공식 발표는 보도자료 날짜(연도만 있으면 최초 도입 연도)',
        evidence_summary=f'현재 식각 제품 페이지 {len({p[3] for p in PRODUCTS})}곳 · {len(rows)}개 제품 · 모든 값 공식 페이지·보도자료 확인',
        scroll_hint='셀에 마우스를 올리면 근거 · 맨 오른쪽 상세',
        note=('Lam 식각 제품 페이지에 올라 있는 제품만 담았습니다. Lam은 ASML과 달리 처리량·해상도 같은 장비 사양을 공개하지 않아, '
              '식각 방식·주요 공정·라인업·핵심 기술은 제품 페이지에서, 발표일과 수치는 해당 제품의 발표 보도자료에서 옮겼습니다. '
              '"공개 수치"는 Lam이 발표한 대표값이라 측정 조건이 제각각이니 제품끼리 단순 비교하지 마세요. '
              'Lam Cryo 3.0은 독립 장비가 아니라 Flex·Vantex에 얹는 극저온 식각 기술이고, Coronus DX는 제품군 안의 베벨 증착 장비입니다. '
              '가격·출하 대수는 공개되지 않아 넣지 않았습니다.'))


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(OUT)

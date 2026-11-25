"""ASML lithography systems spec table (EUV / DUV), from ASML's official product pages.

Values are a reviewed snapshot of https://www.asml.com/en/products (checked 2026-11-25). The headline
figures on those pages are animated counters, so they were read from the rendered page (the counters'
data-value attributes), and overlay/use/lineage from the page text. A field the page does not state is
left blank; nothing is filled from other sources. Re-run after reviewing the pages again:

    python scripts/build_asml_litho_specs.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/semicon/asml_litho_specs.json'
CHECKED = '2026-11-25'
BASE = 'https://www.asml.com/en/products/'

COLUMNS = [
    dict(id='name', label='장비', width=170),
    dict(id='platform', label='플랫폼', width=130),
    dict(id='light', label='광원·파장', width=130),
    dict(id='na', label='NA', width=90, measure=True),
    dict(id='resolution', label='해상도', width=110, measure=True),
    dict(id='throughput', label='처리량 (장/시간)', width=120, measure=True),
    dict(id='dose', label='처리량 조건', width=130),
    dict(id='overlay', label='오버레이 (공식 표기)', width=230),
    dict(id='use', label='주 용도', width=230),
    dict(id='lineage', label='세대 관계', width=190),
    dict(id='wafer', label='웨이퍼', width=100),
    dict(id='features', label='특징', width=300),
    dict(id='page', label='공식 페이지', width=100, url=True),
]
VIEWS = [
    dict(id='overview', label='한눈에 보기', keys=['name', 'light', 'na', 'resolution', 'throughput', 'dose', 'overlay', 'use']),
    dict(id='detail', label='전체 사양', keys=['name', 'platform', 'light', 'na', 'resolution', 'throughput', 'dose', 'overlay',
                                            'wafer', 'lineage', 'use', 'features', 'page']),
]
GROUPS = ['EUV High-NA (0.55 NA)', 'EUV (0.33 NA)', 'ArF 액침 (ArFi)', 'ArF 건식', 'KrF', 'i-line']

EUV, ARFI, ARF, KRF, ILINE = '13.5 nm EUV', '193 nm ArF 액침', '193 nm ArF', '248 nm KrF', '365 nm i-line'

# (id, name, group, path, fields). Every field below is stated on that system's ASML page.
SYSTEMS = [
    ('exe-5200b', 'TWINSCAN EXE:5200B', GROUPS[0], 'euv-lithography-systems/twinscan-exe-5200b', dict(
        platform='TWINSCAN EXE · High-NA', light=EUV, na='0.55', resolution='8 nm', throughput='≥ 175', dose='50 mJ/cm²',
        overlay='수치 미기재 · EXE:5000 대비 오버레이 개선',
        use='sub-2 nm 로직·첨단 DRAM 양산', lineage='EXE:5000 후속 · 두 번째 High-NA',
        features='광원 출력 향상으로 처리량 증가. NXE 대비 이미징 콘트라스트 40%↑, 한 번 노광으로 1.7배 작은 패턴(트랜지스터 밀도 2.9배)')),
    ('exe-5000', 'TWINSCAN EXE:5000', GROUPS[0], 'euv-lithography-systems/twinscan-exe-5000', dict(
        platform='TWINSCAN EXE · High-NA', light=EUV, na='0.55', resolution='8 nm', throughput='≥ 110', dose='50 mJ/cm²',
        overlay='수치 미기재', use='첨단 로직·메모리 (멀티 패터닝을 단일 노광으로)', lineage='첫 0.55 NA(High-NA) 장비',
        features='비대칭(anamorphic) 반사경으로 노광 영역이 NXE의 절반 → 더 빠른 웨이퍼·레티클 스테이지. 첫 High-NA 장비 2023-12 인도(ASML 제품 목록 페이지)')),
    ('nxe-3800e', 'TWINSCAN NXE:3800E', GROUPS[1], 'euv-lithography-systems/twinscan-nxe-3800e', dict(
        platform='TWINSCAN NXE · 0.33 NA', light=EUV, na='0.33', resolution='13 nm', throughput='≥ 220', dose='30 mJ/cm²',
        overlay='수치 미기재 · 3600D 대비 개선', use='2 nm 로직·첨단 DRAM 양산', lineage='NXE:3600D 후속',
        features='EXE와 같은 하부 모듈(웨이퍼 핸들러·스테이지)과 고출력 광원으로 생산성 큰 폭 향상, 반사경 가열 완화')),
    ('nxe-3600d', 'TWINSCAN NXE:3600D', GROUPS[1], 'euv-lithography-systems/twinscan-nxe-3600d', dict(
        platform='TWINSCAN NXE · 0.33 NA', light=EUV, na='0.33', resolution='13 nm', throughput='≥ 160', dose='30 mJ/cm²',
        overlay='수치 미기재 · 3400C 대비 개선', use='5·3 nm 로직·첨단 DRAM 양산', lineage='NXE:3400C 후속',
        wafer='300 mm', features='30 mJ/cm² 기준 3400C 대비 생산성 15~20%↑. 최대 노광 영역 26×33 mm')),
    ('nxe-3400c', 'TWINSCAN NXE:3400C', GROUPS[1], 'euv-lithography-systems/twinscan-nxe3400c', dict(
        platform='TWINSCAN NXE · 0.33 NA', light=EUV, na='0.33', resolution='13 nm', throughput='≥ 170 (30 mJ/cm²: ≥ 135)',
        dose='20 mJ/cm²', overlay='단일 장비(DCO) 1.4 nm · 장비 간(MMO) 1.5 nm', use='7·5 nm 양산',
        lineage='NXE:3400B 후속', features='2019년 하반기부터 공급(페이지 표기). 최대 노광 영역 26×33 mm')),
    ('nxt-2150i', 'TWINSCAN NXT:2150i', GROUPS[2], 'duv-lithography-systems/twinscan-nxt-2150i', dict(
        platform='NXT', light=ARFI, na='1.35', resolution='≤ 38 nm', throughput='≥ 310',
        overlay='수치 미기재 · 2100i 대비 on-product 오버레이 15% 개선', use='첨단 메모리·로직 핵심(critical) 레이어',
        lineage='NXT:2100i 후속 · 처리량 5%↑', features='다이아몬드 코팅 웨이퍼 테이블로 정기 유지보수 없이 오버레이 유지')),
    ('nxt-2100i', 'TWINSCAN NXT:2100i', GROUPS[2], 'duv-lithography-systems/twinscan-nxt2100i', dict(
        platform='NXT', light=ARFI, na='1.35', resolution='≤ 38 nm', throughput='295',
        overlay='단일 장비 최대 10% 개선(0.9 nm) · 장비 간 13% 개선(1.3 nm) — 공식 표기', use='메모리·로직 (DUV-EUV 혼용 레이어)',
        lineage='NXT:2050i 후속', features='렌즈 왜곡 보정기로 DUV-EUV 교차 오버레이 개선, 정렬 측정 4→12색')),
    ('nxt-2050i', 'TWINSCAN NXT:2050i', GROUPS[2], 'duv-lithography-systems/twinscan-nxt2050i', dict(
        platform='NXT4', light=ARFI, na='1.35', resolution='≤ 38 nm (dipole) · 40 nm (C-quad)', throughput='295',
        overlay='교차 매칭 on-product 2.5 nm', use='첨단 로직·DRAM 멀티 패터닝', lineage='NXT:2000i 다음 세대',
        wafer='300 mm', features='오버헤드 감소로 하루 400~500장 추가 생산')),
    ('nxt-2000i', 'TWINSCAN NXT:2000i', GROUPS[2], 'duv-lithography-systems/twinscan-nxt2000i', dict(
        platform='NXT', light=ARFI, na='1.35', resolution='≤ 38 nm (dipole) · 40 nm (C-quad)', throughput='≥ 275',
        overlay='교차 매칭 on-product 2.5 nm', use='첨단 로직·DRAM 양산', wafer='300 mm',
        features='최고 생산성 하루 4,600장(champion). ORION 정렬 센서')),
    ('nxt-1980fi', 'TWINSCAN NXT:1980Fi', GROUPS[2], 'duv-lithography-systems/twinscan-nxt1980fi', dict(
        platform='NXT', light=ARFI, na='1.35', resolution='≤ 38 nm', throughput='≥ 330',
        overlay='장비 간 매칭 2.5 nm', use='첨단·성숙 노드의 중간 핵심(mid-critical) 레이어', wafer='300 mm',
        features='빠른 스테이지·액침 후드 개선으로 결함 감소·처리량 향상')),
    ('nxt-1470', 'TWINSCAN NXT:1470', GROUPS[3], 'duv-lithography-systems/twinscan-nxt1470', dict(
        platform='NXT', light=ARF, na='0.93 (가변 0.70–0.93)', resolution='≤ 57 nm', throughput='≥ 300',
        overlay='on-product 4.5 nm 미만', lineage='NXT 플랫폼 첫 건식 장비',
        features='이전 최고속 ArF 장비 대비 처리량 최대 50%↑')),
    ('xt-1460k', 'TWINSCAN XT:1460K', GROUPS[3], 'duv-lithography-systems/twinscan-xt1460k', dict(
        platform='XT', light=ARF, na='0.93 (가변 0.65–0.93)', resolution='≤ 65 nm (편광 조명 시 57 nm)', throughput='≥ 205',
        overlay='단일 장비(DCO) ≤ 3.5 nm · 장비 간(MMO) ≤ 5 nm (TOP 패키지)', use='65 nm 양산', wafer='300 mm',
        features='45 W ArF 레이저, 오프라인 레벨링으로 가장자리 다이까지 초점 제어')),
    ('nxt-870b', 'TWINSCAN NXT:870B', GROUPS[4], 'duv-lithography-systems/twinscan-nxt-870b', dict(
        platform='NXT', light=KRF, na='0.80', resolution='≤ 110 nm', throughput='≥ 400',
        overlay='수치 미기재 · NXT:870 수준 유지', lineage='NXT:870 후속 · 처리량 20%↑', wafer='300 mm',
        features='업계 최초 시간당 400장. 빠른 스테이지와 레티클 미끄럼 방지 장치')),
    ('nxt-870', 'TWINSCAN NXT:870', GROUPS[4], 'duv-lithography-systems/twinscan-nxt870', dict(
        platform='NXT', light=KRF, na='0.80 (가변 0.55–0.80)', resolution='≤ 110 nm', throughput='≥ 330',
        overlay='장비 간(MMO) ≤ 7.5 nm (웨이퍼 전체)', use='110 nm 이하 양산', wafer='300 mm',
        features='ArF 건식·액침과 같은 NXT 플랫폼의 KrF 장비')),
    ('xt-1060k', 'TWINSCAN XT:1060K', GROUPS[4], 'duv-lithography-systems/twinscan-xt-1060k', dict(
        platform='XT', light=KRF, na='0.93', resolution='≤ 80 nm', throughput='≥ 205',
        overlay='단일 장비(DCO) ≤ 3.5 nm · 장비 간(MMO) ≤ 5 nm (웨이퍼 전체)', use='2X nm 이하 메모리·로직의 금속·비아·이온주입 레이어',
        wafer='300 mm', features='업계 최고 NA·생산성의 KrF 장비(페이지 표기), 반사굴절 렌즈')),
    ('xt-860n', 'TWINSCAN XT:860N', GROUPS[4], 'duv-lithography-systems/twinscan-xt860n', dict(
        platform='XT', light=KRF, na='0.80 (가변 0.55–0.80)', resolution='≤ 110 nm', throughput='≥ 260 (200 mm: 275)',
        overlay='장비 간(MMO) ≤ 7.5 nm (웨이퍼 전체)', use='110 nm 이하 양산', wafer='200·300 mm',
        features='40·50·60 W KrF 레이저')),
    ('xt-860m', 'TWINSCAN XT:860M', GROUPS[4], 'duv-lithography-systems/twinscan-xt-860m', dict(
        platform='XT', light=KRF, na='0.80', resolution='≤ 110 nm', throughput='≥ 240',
        overlay='단일 장비(DCO) ≤ 12 nm · 장비 간(MMO) ≤ 14 nm', use='110 nm 미만 양산', wafer='300 mm',
        features='40 W KrF 레이저')),
    ('xt-400m', 'TWINSCAN XT:400M', GROUPS[5], 'duv-lithography-systems/twinscan-xt-400m', dict(
        platform='XT', light=ILINE, na='0.65', resolution='≤ 350 nm (옵션 시 220 nm)', throughput='≥ 245',
        overlay='웨이퍼 전체 ≤ 20 nm', use='성숙 공정', lineage='XT:400L 후속', wafer='200·300 mm',
        features='광학계 투과율 개선으로 생산성 향상, 기존 공정 변경 없이 교체')),
    ('xt-260', 'TWINSCAN XT:260', GROUPS[5], 'duv-lithography-systems/twinscan-xt-260', dict(
        platform='XT', light=ILINE, na='0.35 (가변 0.25–0.35, 2배 축소)', resolution='≤ 400 nm (옵션)', throughput='≥ 270',
        dose='340 mJ/cm²', overlay='수치 미기재', use='3D 집적·첨단 패키징',
        features='스테퍼 대신 스캐너, 기존 장비 대비 생산성 최대 4배. 두께 1.7 mm 웨이퍼·휜 웨이퍼 지원')),
]

FIELD_KEYS = [c['id'] for c in COLUMNS if c['id'] != 'name']


def build():
    sources, rows = {}, []
    for sid, full_name, group, path, fields in SYSTEMS:
        name = full_name.replace('TWINSCAN ', '')  # shorter for the sticky name column; full name in the source title
        url = BASE + path
        sources[sid] = dict(title=f'ASML · {full_name}', url=url, checked=CHECKED,
                            note='제품 페이지의 수치 카드(해상도·NA·처리량)와 본문. 페이지에 없는 항목은 비워 둠.')
        values = dict(fields, page=url)
        unknown = set(values) - set(FIELD_KEYS)
        if unknown:
            raise ValueError(f'{sid}: unknown fields {unknown}')
        reviews = {key: dict(value=value, source=sid, note='ASML 공식 제품 페이지 기재값')
                   for key, value in values.items() if value}
        reviews['name'] = dict(value=name, source=sid, note=f'ASML 공식 제품명 {full_name}')
        rows.append(dict(id=sid, sheet_row=None, name=name, company='ASML', group=group, original={}, reviews=reviews,
                         review_note='ASML 공식 제품 페이지 기준. 처리량은 ASML이 밝힌 조건(노광량)의 사양값이며 실제 팹 가동률과 다릅니다.'))
    return dict(
        id='asml_litho_specs', name='ASML 노광 장비 · EUV·DUV 장비별 사양', table_family='litho', official_only=True,
        short_name='ASML 노광기', manual=True, frequency='irregular', source='ASML 공식 제품 페이지',
        source_url='https://www.asml.com/en/products', updated=CHECKED, fetched=CHECKED,
        update_note='ASML 제품 페이지를 확인한 날짜 기준 스냅샷입니다. 새 장비 발표 시 페이지를 다시 확인해 scripts/build_asml_litho_specs.py를 고칩니다.',
        columns=COLUMNS, rows=rows, name_key='name', default_group='all', default_view='overview', views=VIEWS,
        sources=sources, company_order=['ASML'], group_label='분류', item_label='장비',
        search_placeholder='장비명·광원·용도 검색',
        caption='ASML 공식 사양 · 해상도는 최소 선폭 · 처리량은 300 mm 웨이퍼 시간당 장수',
        evidence_summary=f'현재 판매 장비 {len(rows)}종 · EUV {sum(r["group"].startswith("EUV") for r in rows)} · DUV {sum(not r["group"].startswith("EUV") for r in rows)} · 모든 값 공식 페이지 확인',
        scroll_hint='셀에 마우스를 올리면 근거 · 맨 오른쪽 상세',
        note=('ASML이 현재 제품으로 공개한 노광 장비만 담았습니다(단종 장비 제외). 해상도·NA·처리량은 제품 페이지의 대표 사양이며, '
              '처리량은 표기된 노광량 조건 기준이라 장비 간 단순 비교에 주의하세요. 오버레이는 회사마다 단일 장비(DCO), 장비 간(MMO), '
              '실제 웨이퍼(on-product) 등 기준이 달라 공식 표기를 그대로 적었고, 신형 EUV처럼 수치를 밝히지 않은 장비는 비워 두었습니다. '
              '가격·출하 대수는 페이지에 없어 넣지 않았습니다(판매 대수는 위 "ASML · 노광기 판매 대수" 카드).'))


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(OUT)

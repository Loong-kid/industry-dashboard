// 전체 지도: 메르카토르 계산, 화면 맞춤, 점 고르기와 기본값·연결 시험.
const fs = require('node:fs');
const assert = require('node:assert/strict');

const near = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;

(async () => {
  const source = fs.readFileSync('assets/globe-map.js', 'utf8');
  const m = await import('data:text/javascript;charset=utf-8,' + encodeURIComponent(source));

  // 메르카토르: 적도는 0, 위도가 높을수록 간격이 벌어지고, 되돌리면 같은 위도다.
  assert.ok(near(m.mercY(0), 0));
  assert.ok(m.mercY(60) - m.mercY(50) > m.mercY(10) - m.mercY(0), '고위도가 더 늘어난다');
  for (const lat of [-41.1, 0, 37.5, 73.15]) assert.ok(near(m.invMercY(m.mercY(lat)), lat), `왕복 ${lat}`);
  assert.ok(Number.isFinite(m.mercY(-90)), '남극에서도 무한대가 되지 않는다');

  // 화면 변환: 왕복하면 같은 지점이고 북쪽이 위다.
  const world = m.worldFrame();
  const t = m.frameTransform(world, 1000, 400);
  const [sx, sy] = m.toScreen(t, 37.5, 127);
  const back = m.fromScreen(t, sx, sy);
  assert.ok(near(back.lat, 37.5) && near(back.lng, 127), '화면 좌표 왕복');
  assert.ok(m.toScreen(t, 60, 0)[1] < m.toScreen(t, 0, 0)[1], '북쪽이 위');
  assert.ok(m.toScreen(t, 0, 10)[0] > m.toScreen(t, 0, 0)[0], '동쪽이 오른쪽');
  const corners = [m.toScreen(t, m.WORLD_NORTH, -180), m.toScreen(t, m.WORLD_SOUTH, 180)];
  assert.ok(corners[0][0] >= 0 && corners[0][1] >= 0 && corners[1][0] <= 1000 && corners[1][1] <= 400, '세계 전체가 화면 안');

  // 맞춤: 없으면 세계, 한국만이면 한국 쪽, 태평양 양쪽이면 세계.
  assert.deepEqual(m.fitFrame([]), world);
  const korea = [{lat: 34.57, lon: 126.53}, {lat: 38.0, lon: 129.42}];
  const fit = m.fitFrame(korea);
  assert.ok(fit.x1 - fit.x0 < 20, '한국만 켜면 가까이 맞춘다');
  for (const p of korea) {
    assert.ok(p.lon > fit.x0 && p.lon < fit.x1 && m.mercY(p.lat) > fit.y0 && m.mercY(p.lat) < fit.y1, '점이 범위 안');
  }
  const single = m.fitFrame([{lat: 37.5, lon: 127}]);
  assert.ok(single.x1 - single.x0 >= m.MIN_SPAN - 1e-9, '점 하나여도 너무 당기지 않는다');
  assert.deepEqual(m.fitFrame([{lat: 30, lon: -121}, {lat: 37, lon: 129}]), world);
  const edge = m.fitFrame([{lat: 10, lon: 175}]);
  assert.ok(edge.x1 <= 180 && edge.x0 >= -180, '범위가 세계 밖으로 나가지 않는다');

  // 날짜변경선: 건너뛰는 고리를 이으면 경도 차가 작아진다.
  const ring = m.unwrapRing([[170, 60], [179, 62], [-179, 63], [-170, 61], [170, 60]]);
  assert.deepEqual(ring.map(p => p[0]), [170, 179, 181, 190, 170 + 0], '넘어간 경도를 이어 붙인다');
  const plain = [[120, 30], [130, 35], [125, 40]];
  assert.deepEqual(m.unwrapRing(plain), plain, '넘지 않으면 그대로');

  // 점 고르기: 가장 가까운 점 + 근처 개수, 멀면 없음.
  const points = [{x: 100, y: 100, id: 'a'}, {x: 106, y: 100, id: 'b'}, {x: 300, y: 300, id: 'c'}];
  const hit = m.nearestPoint(points, 105, 100);
  assert.equal(hit.point.id, 'b');
  assert.equal(hit.nearby, 2);
  assert.equal(m.nearestPoint(points, 500, 500), null);

  // 연결: 레이어 기본 해제, 지도 모듈 사용, 지구본 위에 배치, 스타일.
  const globe = fs.readFileSync('assets/globe.js', 'utf8');
  assert.ok(/const prefs = \{layers: new Set\(\),/.test(globe), '기본 레이어는 전부 해제');
  assert.ok(globe.includes('from "./globe-map.js"'), '지도 계산 모듈 사용');
  assert.ok(globe.indexOf('id="gl-map"') > 0 && globe.indexOf('id="gl-map"') < globe.indexOf('id="gl-globe"'), '지도가 지구본 위');
  const css = fs.readFileSync('assets/globe.css', 'utf8');
  assert.ok(css.includes('.gl-map {'), '지도 스타일');
  console.log('globe map OK');
})().catch(e => { console.error(e); process.exit(1); });

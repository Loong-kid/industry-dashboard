// 지구본 근접 시점: 카메라 위치·끌기 방향·막대 크기 계산과 연결 시험.
const fs = require('node:fs');
const assert = require('node:assert/strict');

const near = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;
const dot = (a, b) => a.reduce((sum, v, i) => sum + v * b[i], 0);
const sub = (a, b) => a.map((v, i) => v - b[i]);
const length = v => Math.sqrt(dot(v, v));
const latOf = p => Math.asin(p[1] / length(p)) * 180 / Math.PI;

(async () => {
  const source = fs.readFileSync('assets/globe-view.js', 'utf8');
  const m = await import('data:text/javascript;charset=utf-8,' + encodeURIComponent(source));
  const seoul = {lat: 37.5, lng: 127, range: 0.2};

  // 위에서 볼 때는 카메라가 중심 바로 위이고, 화면 위쪽이 북쪽이다.
  const top = m.cameraFrame({...seoul, tilt: 0, heading: 0});
  assert.ok(near(length(sub(top.position, top.target)), 0.2 * m.GLOBE_RADIUS), '중심까지 거리 = range');
  assert.ok(near(latOf(top.position), 37.5), '수직일 때 카메라 위도 = 중심 위도');
  assert.ok(top.up[1] > 0, '북쪽이 위');

  // 기울이면 북쪽을 바라보도록 카메라가 남쪽으로 물러난다.
  const tilted = m.cameraFrame({...seoul, tilt: 50, heading: 0});
  assert.ok(near(length(sub(tilted.position, tilted.target)), 0.2 * m.GLOBE_RADIUS), '기울여도 거리 유지');
  assert.ok(latOf(tilted.position) < 37.5, '북쪽을 보면 카메라는 남쪽');
  assert.ok(length(tilted.position) > m.GLOBE_RADIUS * (1 + m.LAND_ALT), '카메라가 땅 위');
  const view = sub(tilted.target, tilted.position);
  assert.ok(near(dot(view, tilted.up), 0), '화면 위쪽은 시선과 수직');
  assert.ok(near(length(tilted.up), 1), '화면 위쪽은 단위 벡터');

  // 가장 가까이에서 가장 크게 기울여도 땅에 묻히지 않는다.
  const lowest = m.cameraFrame({lat: 37.5, lng: 127, range: m.MIN_RANGE, tilt: m.MAX_TILT, heading: 123});
  assert.ok(length(lowest.position) > m.GLOBE_RADIUS * (1 + m.LAND_ALT), '최소 거리·최대 기울기');

  // 방위를 180도 돌리면 카메라가 중심의 반대편으로 간다.
  const back = m.cameraFrame({...seoul, tilt: 50, heading: 180});
  assert.ok(latOf(back.position) > 37.5, '남쪽을 보면 카메라는 북쪽');

  // 라이브러리 컨트롤과 만나는 지점에서는 기울기가 0이어야 화면이 튀지 않는다.
  assert.equal(m.viewFade(m.NEAR_RANGE), 0);
  assert.equal(m.viewFade(m.FULL_RANGE), 1);
  assert.equal(m.autoTilt(m.NEAR_RANGE), 0);
  assert.ok(m.autoTilt(0.5) > m.autoTilt(0.8), '가까울수록 더 기운다');
  assert.ok(m.autoTilt(0.05) <= m.MAX_TILT);

  // 끌면 땅이 손을 따라온다: 오른쪽으로 끌면 중심은 서쪽, 아래로 끌면 중심은 북쪽.
  const flat = {...seoul, tilt: 0, heading: 0};
  assert.ok(m.panFocus(flat, 100, 0, 800).lng < 127, '오른쪽으로 끌면 서쪽을 본다');
  assert.ok(m.panFocus(flat, 0, 100, 800).lat > 37.5, '아래로 끌면 북쪽을 본다');
  const south = {...flat, heading: 180};
  assert.ok(m.panFocus(south, 100, 0, 800).lng > 127, '남쪽을 볼 때는 좌우가 반대');
  assert.ok(m.panFocus({...flat, range: 0.1}, 100, 0, 800).lng > m.panFocus(flat, 100, 0, 800).lng, '가까울수록 조금 움직인다');
  assert.equal(m.panFocus({...flat, lat: 84.9}, 0, 8000, 800).lat, 85, '극점을 넘지 않는다');

  // 막대는 화면에서 같은 크기를 유지하고, 멀리서는 원래 크기 그대로다.
  assert.deepEqual(m.barScale(2.4), {radius: 1, height: 1});
  const wide = d => m.barScale(d).radius * 0.3 * 2 / d;
  for (const d of [0.04, 0.1, 0.3, 0.7]) {
    const ratio = wide(d) / wide(0.3);
    assert.ok(ratio > 0.8 && ratio < 1.25, `거리 ${d}의 화면 폭 비율 ${ratio}`);
  }
  assert.ok(m.barScale(0.1).height < m.barScale(0.5).height, '다가가면 낮아진다');

  // 아무리 줄여도 막대가 육지 면 아래로 묻히지 않는다.
  assert.ok(m.barAltitude(0.012, m.barScale(m.MIN_RANGE).height) > m.LAND_ALT, '가장 낮은 막대도 육지 위');

  const globe = fs.readFileSync('assets/globe.js', 'utf8');
  assert.ok(globe.includes('from "./globe-view.js"'), 'globe.js가 시점 모듈을 쓴다');
  for (const id of ['gl-view', 'gl-tilt', 'gl-turn-left', 'gl-turn-right', 'gl-north']) {
    assert.ok(globe.includes(`id="${id}"`), `시점 도구 ${id}`);
  }
  assert.ok(fs.readFileSync('assets/globe.css', 'utf8').includes('.gl-view'), 'globe.css에 시점 도구');
  console.log('globe view: all assertions passed');
})().catch(error => { console.error(error); process.exit(1); });

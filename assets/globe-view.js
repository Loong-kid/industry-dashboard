/* 지구본 근접 시점 계산. 화면 요소를 건드리지 않는 순수 함수만 둔다(scripts/test_globe_view.cjs).
   거리·고도는 지구 반지름 배수, 각도는 도. 좌표축은 three-globe와 같다(y가 북극, 경도 0이 +z). */
export const GLOBE_RADIUS = 100;
export const LAND_ALT = 0.004; // 육지 면 높이. 막대와 시점 중심은 이 위에서 잰다.
export const NEAR_RANGE = 1.2, FULL_RANGE = 0.84; // 이 거리 사이에서 위에서 보기 ↔ 근접 시점이 이어진다
export const MIN_RANGE = 0.012, MAX_RANGE = 12, MAX_TILT = 65;
export const LABEL_ALT = LAND_ALT + 0.0008; // 더 띄우면 낮게 내려갔을 때 라벨이 공중에 떠 보인다
const AUTO_TILT = 50, AUTO_TILT_FROM = 0.9, AUTO_TILT_FULL = 0.25;

const toRad = d => d * Math.PI / 180;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const smooth = t => t * t * (3 - 2 * t);

// 다가갈수록 저절로 기운다. 사용자가 기울기를 정하면 그 값을 쓴다.
export function autoTilt(range) {
  return AUTO_TILT * smooth(clamp((AUTO_TILT_FROM - range) / (AUTO_TILT_FROM - AUTO_TILT_FULL), 0, 1));
}
// 기울기·방향이 적용되는 정도. NEAR_RANGE에서 0이라 라이브러리 컨트롤로 끊김 없이 넘어간다.
export function viewFade(range) {
  return smooth(clamp((NEAR_RANGE - range) / (NEAR_RANGE - FULL_RANGE), 0, 1));
}

function frameAxes(lat, lng) {
  const a = toRad(lat), o = toRad(lng);
  const up = [Math.cos(a) * Math.sin(o), Math.sin(a), Math.cos(a) * Math.cos(o)];
  const east = [Math.cos(o), 0, -Math.sin(o)];
  const north = [-Math.sin(a) * Math.sin(o), Math.cos(a), -Math.sin(a) * Math.cos(o)];
  return {up, east, north};
}

// heading은 카메라가 바라보는 방위(0=북, 시계 방향), tilt는 수직으로 내려다보는 방향에서 기운 각도.
export function cameraFrame({lat, lng, range, tilt, heading}) {
  const {up, east, north} = frameAxes(lat, lng);
  const t = toRad(tilt), h = toRad(heading);
  const forward = north.map((n, i) => n * Math.cos(h) + east[i] * Math.sin(h));
  const center = up.map(u => u * (1 + LAND_ALT));
  const scale = v => v.map(x => x * GLOBE_RADIUS);
  return {
    target: scale(center),
    position: scale(center.map((c, i) => c + range * (up[i] * Math.cos(t) - forward[i] * Math.sin(t)))),
    up: up.map((u, i) => u * Math.sin(t) + forward[i] * Math.cos(t)),
  };
}

// 화면에서 (dx, dy)픽셀 끌면 땅이 손을 따라오도록 중심을 옮긴다.
export function panFocus({lat, lng, range, tilt, heading}, dx, dy, heightPx, fov = 50) {
  const perPx = 2 * range * Math.tan(toRad(fov) / 2) / heightPx;
  const h = toRad(heading);
  const right = -dx * perPx;
  const forward = dy * perPx / Math.max(0.35, Math.cos(toRad(tilt)));
  const east = right * Math.cos(h) + forward * Math.sin(h);
  const north = -right * Math.sin(h) + forward * Math.cos(h);
  return {
    lat: clamp(lat + north * 180 / Math.PI, -85, 85),
    lng: lng + east * 180 / Math.PI / Math.max(0.05, Math.cos(toRad(lat))),
  };
}

// 막대는 지구 기준 크기라 다가가면 화면을 덮는다. 거리에 비례해 줄여 화면에서의 크기를 일정하게 둔다.
// 매 프레임 다시 그리지 않도록 약 19% 간격으로 끊는다.
const step = v => v >= 1 ? 1 : 2 ** (Math.round(Math.log2(v) * 4) / 4);
export function barScale(distance) {
  return {radius: step(distance * 0.5), height: step(distance * 1.1)};
}
// 막대 밑동은 지표면이고 육지 면이 그보다 떠 있다. 육지 위로 나온 부분이 규모에 비례하게 띄운다.
export const barAltitude = (height, scale) => LAND_ALT + height * scale;

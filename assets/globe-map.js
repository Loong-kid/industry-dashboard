/* 🗺 지구본 위 전체 지도: 메르카토르 투영과 화면 맞춤 계산. 그리기는 assets/globe.js가 맡는다. */
export const WORLD_NORTH = 76, WORLD_SOUTH = -58; // 야말 LNG(73°N)는 담고 극지방 늘어짐은 잘라 낸다
export const MIN_SPAN = 7; // 한 나라에 몰려도 이보다 좁게 당기지 않는다(경도 도)
export const PICK_RADIUS = 14; // 점에서 이만큼(px) 떨어져도 그 점을 가리킨 것으로 본다
const MAX_MERC_LAT = 85;
const toRad = d => d * Math.PI / 180, toDeg = r => r * 180 / Math.PI;

// 지도 좌표: x는 경도, y는 같은 눈금(도)으로 환산한 메르카토르 값. 북쪽이 크다.
export const mercY = lat => {
  const clamped = Math.max(-MAX_MERC_LAT, Math.min(MAX_MERC_LAT, lat));
  return toDeg(Math.log(Math.tan(Math.PI / 4 + toRad(clamped) / 2)));
};
export const invMercY = y => toDeg(2 * Math.atan(Math.exp(toRad(y))) - Math.PI / 2);

export const worldFrame = () => ({x0: -180, x1: 180, y0: mercY(WORLD_SOUTH), y1: mercY(WORLD_NORTH)});

// 표시 중인 점이 모두 들어오는 범위. 세계 절반을 넘게 퍼지면 그냥 세계 전체를 보여 준다.
export function fitFrame(points) {
  const world = worldFrame();
  if (!points.length) return world;
  const xs = points.map(p => p.lon), ys = points.map(p => mercY(p.lat));
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  if (maxX - minX > 180) return world;
  const pad = Math.max(MIN_SPAN, Math.max(maxX - minX, maxY - minY)) * 0.18;
  const halfX = Math.max(maxX - minX + pad * 2, MIN_SPAN) / 2, halfY = Math.max(maxY - minY + pad * 2, MIN_SPAN / 2) / 2;
  const midX = (minX + maxX) / 2, midY = (minY + maxY) / 2;
  return {x0: Math.max(world.x0, midX - halfX), x1: Math.min(world.x1, midX + halfX),
    y0: Math.max(world.y0, midY - halfY), y1: Math.min(world.y1, midY + halfY)};
}

// 범위를 화면 안에 비율을 지켜 넣는 변환. 남는 쪽은 바다가 된다.
export function frameTransform(frame, width, height, inset = 10) {
  const scale = Math.min((width - inset * 2) / (frame.x1 - frame.x0), (height - inset * 2) / (frame.y1 - frame.y0));
  const midX = (frame.x0 + frame.x1) / 2, midY = (frame.y0 + frame.y1) / 2;
  return {scale, tx: width / 2 - midX * scale, ty: height / 2 + midY * scale};
}
export const toScreen = (t, lat, lon) => [lon * t.scale + t.tx, t.ty - mercY(lat) * t.scale];
export const fromScreen = (t, x, y) => ({lat: invMercY((t.ty - y) / t.scale), lng: (x - t.tx) / t.scale});

// 국경 자료는 날짜변경선을 넘는 고리가 경도 ±180에서 건너뛴다. 이어 붙여야 지도를 가로지르는 선이 생기지 않는다.
export function unwrapRing(ring) {
  let offset = 0;
  return ring.map(([lon, lat], i) => {
    if (i) {
      const jump = lon - ring[i - 1][0];
      if (jump > 180) offset -= 360;
      else if (jump < -180) offset += 360;
    }
    return [lon + offset, lat];
  });
}

export function lerpFrame(a, b, k) {
  return {x0: a.x0 + (b.x0 - a.x0) * k, x1: a.x1 + (b.x1 - a.x1) * k, y0: a.y0 + (b.y0 - a.y0) * k, y1: a.y1 + (b.y1 - a.y1) * k};
}

// 포인터 근처의 점. 겹친 점이 많아도 가장 가까운 하나와 함께 근처 개수를 돌려준다.
export function nearestPoint(screenPoints, x, y, radius = PICK_RADIUS) {
  let best = null, bestDist = radius * radius, nearby = 0;
  for (const p of screenPoints) {
    const d = (p.x - x) ** 2 + (p.y - y) ** 2;
    if (d > radius * radius) continue;
    nearby++;
    if (d <= bestDist) { best = p; bestDist = d; }
  }
  return best && {point: best, nearby};
}

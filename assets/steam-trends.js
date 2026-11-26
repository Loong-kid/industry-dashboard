/* Steam 신작 흥행: 판매(리뷰·판매 순위)·동접·찜(팔로워) 세 갈래로 신작을 본다.
   동시접속자는 판매량이 아니고, 리뷰 수 × 20~60은 판매 추정 범위(경험칙)일 뿐이다. */
const prefs = {maxDays: "365", group: "seed", movers: "new", sellers: "new", metric: "reviews"};
const store = id => `https://store.steampowered.com/app/${id}/`;
const DAY = 86400000;
export const SALES_PER_REVIEW = [20, 60];
export const WISHLIST_PER_FOLLOWER = [7, 12];

// 앞서 해보기 후 정식 출시한 게임은 Steam 표기 출시일이 1.0 날짜라 수집기가 계산한 launch(SteamCharts 첫 기록 달과 비교)를 우선한다.
const launchOf = app => app?.launch || app?.release || null;
export const ageDays = (app, on) => launchOf(app) ? Math.round((Date.parse(on) - Date.parse(launchOf(app))) / DAY) : null;
const launchCell = (app, esc) => `${esc(launchOf(app) || "—")}${app.launch && app.release && app.launch < app.release ? `<small>정식 ${esc(app.release)}</small>` : ""}`;
const isGame = app => (app.type || "game") === "game";
export function median(values){
  const v = values.filter(x => x != null && Number.isFinite(x)).sort((a,b) => a-b);
  if(!v.length) return null;
  const m = Math.floor(v.length/2);
  return v.length % 2 ? v[m] : (v[m-1]+v[m])/2;
}
export const salesRange = count => count == null ? null : SALES_PER_REVIEW.map(k => count * k);

// 일별 누적값(리뷰 수·팔로워)의 최근 하루 평균 증가. days일 이상 떨어진 가장 가까운 과거 관측과 비교하고, 없으면 가장 오래된 관측과 비교한다.
export function perDay(rows, days = 7){
  if(!rows || rows.length < 2) return null;
  const last = rows.at(-1), end = Date.parse(last[0]);
  const older = rows.slice(0, -1).filter(r => r[1] != null);
  const base = [...older].reverse().find(r => (end - Date.parse(r[0])) / DAY >= days) || older[0];
  if(!base || last[1] == null) return null;
  const gap = (end - Date.parse(base[0])) / DAY;
  return gap > 0 ? (last[1] - base[1]) / gap : null;
}

// 지금 동시접속 상위 100 안에서 출시 maxDays 이내인 게임. 게임이 아닌 앱(도구 등)은 뺀다.
export function newReleaseRows(data, maxDays = 365){
  const on = data.date, apps = data.apps || {};
  const weekly = data.weekly?.at(-1)?.ranks || [];
  const week = new Map(weekly.map(r => [r[0], r]));
  return (data.concurrent?.ranks || []).map(([id, rank, ccu, peak]) => {
    const app = apps[id] || {};
    return {id, rank, ccu, peak, app, age: ageDays(app, on), week: week.get(id)};
  }).filter(r => isGame(r.app) && r.age != null && r.age >= 0 && r.age <= maxDays);
}

// 주간 최고 판매(미국, 매출 기준) 순위. ccuRank는 지금 동접 상위 100 안의 순위(없으면 null = 100위 밖).
export function sellerRows(data, maxDays = null){
  const apps = data.apps || {};
  const ccu = new Map((data.concurrent?.ranks || []).map(r => [r[0], r[1]]));
  return (data.topsellers?.at(-1)?.ranks || []).map(([id, rank, prev, weeks]) => {
    const app = apps[id] || {};
    return {id, rank, prev, weeks, app, age: ageDays(app, data.date), ccuRank: ccu.get(id) ?? null};
  }).filter(r => isGame(r.app) && (maxDays == null || (r.age != null && r.age >= 0 && r.age <= maxDays)));
}

// 찜 많은 출시 예정작. 팔로워는 최근 관측값, 하루 증가는 perDay.
export function wishlistRows(data){
  const apps = data.apps || {};
  return (data.wishlist?.ranks || []).map(([id, rank]) => {
    const app = apps[id] || {};
    const followers = app.followers_daily?.at(-1)?.[1] ?? null;
    return {id, rank, app, followers, growth: perDay(app.followers_daily), demo: app.demo_daily?.at(-1)?.[1] ?? null};
  });
}

// 주간 최다 플레이에서 새로 들어왔거나 minJump 계단 이상 오른 게임.
export function weeklyMovers(data, minJump = 10){
  const last = data.weekly?.at(-1);
  if(!last) return [];
  return last.ranks.map(([id, rank, prev, peak]) => ({id, rank, prev, peak, jump: prev ? prev - rank : null, app: data.apps?.[id] || {}}))
    .filter(r => isGame(r.app) && (r.prev == null || r.prev === 0 || r.jump >= minJump))
    .sort((a,b) => (b.jump ?? 1e9) - (a.jump ?? 1e9) || a.rank - b.rank);
}

// 최고 달 이후 k개월 뒤의 값을 최고 달 대비 %로. rows: [경과 개월, 월, 값, ...]. 관측이 없으면 null.
export function fadeRow(rows, offsets = [1,3,6,12]){
  if(!rows?.length) return null;
  const best = rows.reduce((a,b) => b[2] > a[2] ? b : a);
  const byIndex = new Map(rows.map(r => [r[0], r]));
  const after = Object.fromEntries(offsets.map(k => {
    const row = byIndex.get(best[0]+k);
    return [k, row && best[2] > 0 ? row[2]/best[2]*100 : null];
  }));
  return {peakIndex: best[0], peakMonth: best[1], peakValue: best[2], after, months: rows.length};
}

// 출시 후 첫 n개월(0~n-1개월)이 지금까지 전체에서 차지하는 비중. 판매가 출시 직후에 얼마나 몰렸는지.
export function frontShare(rows, n = 3){
  if(!rows?.length || rows.at(-1)[0] < n) return null;
  const total = rows.reduce((s, r) => s + r[2], 0);
  return total > 0 ? rows.filter(r => r[0] < n).reduce((s, r) => s + r[2], 0) / total * 100 : null;
}

export function shareOf(rows, test){
  return rows.length ? rows.filter(test).length / rows.length * 100 : null;
}

const kind = app => [app.online_coop ? "온라인 협동" : app.coop ? "협동" : app.multi ? "멀티" : "싱글", app.early_access ? "앞서 해보기" : ""].filter(Boolean).join(" · ");
const price = app => app.free ? "무료" : app.price_usd == null ? "—" : `$${app.price_usd.toFixed(2)}`;
const METRICS = {
  reviews: {rows: app => app.review_lifecycle, ratio: 3, label: "월별 신규 리뷰", unit: "리뷰"},
  ccu: {rows: app => app.lifecycle, ratio: 4, label: "SteamCharts 월평균 동접", unit: "동접"},
};

export function renderSteamTrends(root, data, h){
  const {header, panel, table, stats, note, link, esc, num, compact, options, chart, on, palette, rerender} = h;
  const pct = v => v == null ? "—" : `${num(v, 0)}%`;
  const reviewCell = app => app.reviews ? `${compact(app.reviews.count)}<small>긍정 ${app.reviews.positive ?? "—"}%</small>` : "—";
  const salesCell = app => { if(app.free) return "<small>무료 · 판매 아님</small>"; const r = salesRange(app.reviews?.count); return r ? `${compact(r[0])}~${compact(r[1])}장` : "—"; };
  const growthCell = (v, rows) => v != null ? `+${compact(Math.round(v))}` : rows?.length ? "<small>쌓는 중</small>" : "—";
  const releaseText = t => ({"To be announced":"미정","Coming soon":"곧 출시","":"미정"})[t ?? ""] ?? t;
  const metric = METRICS[prefs.metric];
  const rows = newReleaseRows(data, Number(prefs.maxDays));
  const top100 = newReleaseRows(data, 365);
  const paid = top100.filter(r => !r.app.free);
  const sellersNew = sellerRows(data, 365);
  const sellers = sellerRows(data, prefs.sellers === "new" ? 730 : null);
  const quietSellers = sellersNew.filter(r => r.ccuRank == null);
  const wishes = wishlistRows(data);
  const movers = weeklyMovers(data).filter(r => prefs.movers === "all" || (ageDays(r.app, data.date) ?? 1e9) <= 730);
  const apps = Object.entries(data.apps || {}).map(([id, app]) => ({id: Number(id), app}));
  const inGroup = a => prefs.group === "seed" ? a.app.seed : prefs.group === "ranked" ? a.app.first_seen && launchOf(a.app) >= "2023-01-01" : a.app.seed || launchOf(a.app) >= "2023-01-01";
  const withFade = key => apps.map(a => ({...a, rows: METRICS[key].rows(a.app) || [], fade: fadeRow(METRICS[key].rows(a.app))})).filter(a => a.fade && a.fade.months >= 2 && inGroup(a));
  const group = withFade(prefs.metric);
  const fadeMedian = (k, list = group) => median(list.map(a => a.fade.after[k]));
  const reviewFade3 = fadeMedian(3, withFade("reviews")), ccuFade3 = fadeMedian(3, withFade("ccu"));
  const lines = [...group].sort((a,b) => b.fade.peakValue - a.fade.peakValue).slice(0, 10);
  const maxIndex = Math.min(24, Math.max(0, ...lines.flatMap(a => a.rows.map(r => r[0]))));
  const daily = apps.filter(a => a.app.daily?.length).sort((a,b) => (b.app.daily.at(-1)[1] || 0) - (a.app.daily.at(-1)[1] || 0)).slice(0, 8);
  const days = [...new Set(daily.flatMap(a => a.app.daily.map(r => r[0])))].sort().slice(-90);
  const week = data.weekly?.at(-1), sellerWeek = data.topsellers?.at(-1);
  const untracked = apps.filter(a => a.app.seed && a.app.steamcharts?.status === "untracked").map(a => a.app.name);

  root.innerHTML = header("지금 어떤 신작이 팔리고, 얼마나 버틸까?", "판매(리뷰 수·주간 판매 순위), 플레이(동시접속), 출시 전 관심(찜 순위·팔로워)을 나눠 봅니다. Steam은 판매량·찜 수를 공개하지 않으므로 모두 대리 지표입니다.") +
    stats([
      ["주간 판매 상위 100 중 출시 1년 이내", `${sellersNew.length}개`, `미국 매출 기준 순위 · ${esc(sellerWeek?.week || "—")} 주`],
      ["그중 동접 100위 밖", `${quietSellers.length}개`, "많이 팔렸지만 동접은 낮은 게임 · 싱글·짧은 플레이형"],
      ["판매 최고 달 3개월 뒤", pct(reviewFade3), "월별 신규 리뷰 중앙값 · 바이럴·신작 비교 묶음"],
      ["동접 최고 달 3개월 뒤", pct(ccuFade3), "SteamCharts 월평균 동접 중앙값 · 같은 묶음"],
      ["동접 상위 100 중 출시 1년 이내", `${top100.length}개`, `Steam 동시접속 순위 · ${esc((data.concurrent?.observed_at || "").replace("T", " ").slice(0, 16))} UTC`],
      ["그중 협동 지원 · 유료 $10 이하", `${pct(shareOf(top100, r => r.app.coop))} · ${pct(shareOf(paid, r => r.app.price_usd != null && r.app.price_usd <= 10))}`, "Steam 상점 분류 · 미국 상점 정가"],
    ]) +
    panel(`주간 판매 순위 · 미국 매출 기준${sellerWeek ? ` · ${esc(sellerWeek.week)} 주` : ""}`,
      `<div class="gm-toolbar"><label>대상<select id="st-sellers">${options([["new","출시 2년 이내"],["all","전체"]], prefs.sellers)}</select></label></div>` +
      table(["게임","판매 순위","지난 주","연속","출시","정가","분류","리뷰","추정 판매","동접 순위"], sellers.slice(0, 40).map(r => [
        link(store(r.id), r.app.name || r.id), r.rank, r.prev || "신규", `${num(r.weeks)}주`, launchCell(r.app, esc), price(r.app), esc(kind(r.app)),
        reviewCell(r.app), salesCell(r.app), r.ccuRank ? `${r.ccuRank}위` : `<small>100위 밖</small>`])) +
      note(`Steam 주간 최고 판매(미국)는 매출 기준 순위만 공개하고 금액·판매량은 공개하지 않습니다. 추정 판매 = 리뷰 수 × ${SALES_PER_REVIEW.join("~")}(업계 경험칙)이며 장르·가격·무료 여부에 따라 크게 달라집니다. 무료 게임은 판매가 아니라 이용자 규모로 읽습니다. 동접 순위가 100위 밖인데 판매 상위인 게임은 싱글·짧은 플레이 게임일 가능성이 큽니다.`)) +
    panel("지금 동접 상위 100 안의 신작",
      `<div class="gm-toolbar"><label>출시 후<select id="st-max-days">${options([["90","90일 이내"],["180","180일 이내"],["365","1년 이내"],["730","2년 이내"]], prefs.maxDays)}</select></label></div>` +
      table(["게임","동접 순위","출시","정가","분류","지금 동접","오늘 최고","리뷰","추정 판매","하루 리뷰 증가"], rows.map(r => [
        link(store(r.id), r.app.name || r.id), r.rank, `${launchCell(r.app, esc)}<small>출시 ${num(r.age)}일째</small>`, price(r.app), esc(kind(r.app)),
        compact(r.ccu), compact(r.peak), reviewCell(r.app), salesCell(r.app), growthCell(perDay(r.app.reviews_daily), r.app.reviews_daily)])) +
      note("지금 동접은 Steam이 순위를 갱신한 시각의 값, 오늘 최고는 Steam 순위표가 표시한 그날 최고값입니다. 하루 리뷰 증가는 최근 7일 평균이며 2026-11-27부터 쌓습니다. 정가는 할인 전 미국 상점 가격입니다.")) +
    panel("출시 후 흐름 · 최고 달 대비",
      `<div class="gm-toolbar"><label>기준<select id="st-metric">${options([["reviews","판매 · 월별 신규 리뷰"],["ccu","플레이 · 월평균 동접"]], prefs.metric)}</select></label><label>비교 묶음<select id="st-group">${options([["seed","바이럴 흥행작 (선정 목록)"],["ranked","순위에 든 2023년 이후 출시작"],["all","전체"]], prefs.group)}</select></label></div>` +
      `<div class="gm-chart gm-chart-tall"><canvas id="st-lifecycle" role="img" aria-label="출시 후 경과 개월별 최고 달 대비 비율"></canvas></div>` +
      table(["게임","출시","정가","분류","누적 리뷰","최고 달",`최고 달 ${metric.unit}`,"+1개월","+3개월","+6개월","+12개월","첫 3개월 비중"], [...group].sort((a,b) => b.fade.peakValue - a.fade.peakValue).map(a => [
        link(store(a.id), a.app.name || a.id), launchCell(a.app, esc), price(a.app), esc(kind(a.app)), reviewCell(a.app), `${esc(a.fade.peakMonth)}<small>출시 ${a.fade.peakIndex}개월째</small>`,
        compact(a.fade.peakValue), pct(a.fade.after[1]), pct(a.fade.after[3]), pct(a.fade.after[6]), pct(a.fade.after[12]), pct(frontShare(a.rows))])) +
      note(prefs.metric === "reviews"
        ? `월별 신규 리뷰(Steam 상점 리뷰 이력, 전 언어, 이번 달 제외)를 판매의 대리 지표로 씁니다. 리뷰 이력은 출시 2년 이내는 주 단위, 그보다 오래되면 월 단위로 제공되어 주 시작일이 속한 달에 합산합니다. 첫 3개월 비중 = 지금까지 리뷰 중 출시 후 0~2개월에 달린 비율로, 높을수록 판매가 출시 직후에 몰렸다는 뜻입니다. 중앙값: +1개월 ${pct(fadeMedian(1))} · +3개월 ${pct(fadeMedian(3))} · +6개월 ${pct(fadeMedian(6))}.`
        : `SteamCharts의 완료된 달 월평균 동접. 출시 달(0개월)은 한 달을 다 채우지 않습니다. 중앙값: +1개월 ${pct(fadeMedian(1))} · +3개월 ${pct(fadeMedian(3))} · +6개월 ${pct(fadeMedian(6))}.${untracked.length ? ` SteamCharts 미수록: ${esc(untracked.join(", "))} — 일별 관측만 있습니다.` : ""}`) +
      note("앞서 해보기로 먼저 나온 게임은 첫 기록 달을 출시로 보고 정식 출시일을 따로 표시합니다. +N개월은 최고 달 대비 비율이며 아직 지나지 않은 달은 비워 둡니다.")) +
    panel("출시 전 · 찜 많은 출시 예정작",
      table(["게임","찜 순위","출시 예정","팔로워","하루 팔로워 증가","추정 찜","데모 동접"], wishes.map(r => [
        link(store(r.id), r.app.name || r.id), r.rank, esc(releaseText(r.app.release_text)), compact(r.followers), growthCell(r.growth, r.app.followers_daily),
        r.followers == null ? "—" : `${compact(r.followers * WISHLIST_PER_FOLLOWER[0])}~${compact(r.followers * WISHLIST_PER_FOLLOWER[1])}`,
        r.app.demo ? (r.demo == null ? "<small>데모 있음</small>" : compact(r.demo)) : "—"])) +
      note(`찜 순위는 Steam 상점의 '찜 많은 출시 예정작' 정렬 순서이며 찜 수는 공개되지 않습니다. 팔로워는 Steam 커뮤니티 허브 회원 수(SteamDB 팔로워와 같은 출처)이고, 추정 찜 = 팔로워 × ${WISHLIST_PER_FOLLOWER.join("~")}(업계 경험칙)입니다. 데모 동접은 매일 같은 시각의 현재 접속자입니다.`)) +
    panel(`주간 동접 급상승${week ? ` · ${esc(week.week)} 주` : ""}`,
      `<div class="gm-toolbar"><label>대상<select id="st-movers">${options([["new","출시 2년 이내"],["all","전체 (할인·업데이트로 오른 옛 게임 포함)"]], prefs.movers)}</select></label></div>` +
      table(["게임","이번 주","지난 주","변화","출시","정가","주간 최고 동접"], movers.slice(0, 15).map(r => [
        link(store(r.id), r.app.name || r.id), r.rank, r.prev || "—", r.prev ? `▲${r.jump}` : "신규 진입", launchCell(r.app, esc), price(r.app), compact(r.peak)])) +
      note("Steam 주간 최다 플레이 상위 100 기준. 지난 주 100위 밖이었거나 10계단 이상 오른 게임입니다.")) +
    panel("출시 2년 이내 게임의 일별 동접",
      `<div class="gm-chart"><canvas id="st-daily" role="img" aria-label="신작 일별 동시접속자"></canvas></div>` +
      note(`매일 KST 07:20 무렵 같은 시각에 조회한 값입니다(상위 100 안이면 순위표 값, 밖이면 게임별 현재 접속자). 2026-11-27부터 쌓기 시작했으며 그 이전 값은 없습니다. 조회 실패일은 비워 둡니다.`)) +
    note(`수집 ${esc((data.fetched || "").slice(0, 10))} · 추적 ${apps.length}개${data.errors?.length ? ` · 최근 조회 실패 ${data.errors.length}건(기존 값 유지)` : ""}. 바이럴 흥행작 선정 목록은 2023년 이후 크게 화제가 된 저가·협동·단순 루프 게임을 직접 고른 것이며 시장 전체를 대표하지 않습니다.`);

  on("#st-max-days", "change", e => { prefs.maxDays = e.target.value; rerender(); });
  on("#st-sellers", "change", e => { prefs.sellers = e.target.value; rerender(); });
  on("#st-movers", "change", e => { prefs.movers = e.target.value; rerender(); });
  on("#st-group", "change", e => { prefs.group = e.target.value; rerender(); });
  on("#st-metric", "change", e => { prefs.metric = e.target.value; rerender(); });
  const labels = Array.from({length: maxIndex+1}, (_, i) => `${i}개월`);
  chart("st-lifecycle", "line", labels, lines.map((a, i) => {
    const map = new Map(a.rows.map(r => [r[0], r[metric.ratio]]));
    return {label: a.app.name, data: labels.map((_, k) => map.get(k) ?? null), borderColor: palette[i % palette.length], backgroundColor: palette[i % palette.length], pointRadius: 2, borderWidth: 1.5, spanGaps: false};
  }), {percentAxis: true});
  chart("st-daily", "line", days, daily.map((a, i) => {
    const map = new Map(a.app.daily.map(r => [r[0], r[1]]));
    return {label: a.app.name, data: days.map(d => map.get(d) ?? null), borderColor: palette[i % palette.length], backgroundColor: palette[i % palette.length], pointRadius: days.length < 20 ? 3 : 0, borderWidth: 1.5, spanGaps: false};
  }));
}

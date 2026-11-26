/* Steam 신작 흥행: 공식 순위에서 새로 뜬 게임과 출시 후 흐름. 동시접속자는 판매량·매출이 아니다. */
const prefs = {maxDays: "365", group: "seed", movers: "new"};
const store = id => `https://store.steampowered.com/app/${id}/`;
const DAY = 86400000;

// 앞서 해보기 후 정식 출시한 게임은 Steam 표기 출시일이 1.0 날짜라 수집기가 계산한 launch(SteamCharts 첫 기록 달과 비교)를 우선한다.
const launchOf = app => app?.launch || app?.release || null;
export const ageDays = (app, on) => launchOf(app) ? Math.round((Date.parse(on) - Date.parse(launchOf(app))) / DAY) : null;
const launchCell = (app, esc) => `${esc(launchOf(app) || "—")}${app.launch && app.release && app.launch < app.release ? `<small>정식 ${esc(app.release)}</small>` : ""}`;
export function median(values){
  const v = values.filter(x => x != null && Number.isFinite(x)).sort((a,b) => a-b);
  if(!v.length) return null;
  const m = Math.floor(v.length/2);
  return v.length % 2 ? v[m] : (v[m-1]+v[m])/2;
}

// 지금 동시접속 상위 100 안에서 출시 maxDays 이내인 게임. 게임이 아닌 앱(도구 등)은 뺀다.
export function newReleaseRows(data, maxDays = 365){
  const on = data.date, apps = data.apps || {};
  const weekly = data.weekly?.at(-1)?.ranks || [];
  const week = new Map(weekly.map(r => [r[0], r]));
  return (data.concurrent?.ranks || []).map(([id, rank, ccu, peak]) => {
    const app = apps[id] || {};
    return {id, rank, ccu, peak, app, age: ageDays(app, on), week: week.get(id)};
  }).filter(r => (r.app.type || "game") === "game" && r.age != null && r.age >= 0 && r.age <= maxDays);
}

// 주간 최다 플레이에서 새로 들어왔거나 minJump 계단 이상 오른 게임.
export function weeklyMovers(data, minJump = 10){
  const last = data.weekly?.at(-1);
  if(!last) return [];
  return last.ranks.map(([id, rank, prev, peak]) => ({id, rank, prev, peak, jump: prev ? prev - rank : null, app: data.apps?.[id] || {}}))
    .filter(r => (r.app.type || "game") === "game" && (r.prev == null || r.prev === 0 || r.jump >= minJump))
    .sort((a,b) => (b.jump ?? 1e9) - (a.jump ?? 1e9) || a.rank - b.rank);
}

// 최고 달(월평균 동접 최대) 이후 k개월 뒤의 월평균을 최고 달 대비 %로. 관측이 없으면 null.
export function fadeRow(lifecycle, offsets = [1,3,6,12]){
  if(!lifecycle?.length) return null;
  const best = lifecycle.reduce((a,b) => b[2] > a[2] ? b : a);
  const byIndex = new Map(lifecycle.map(r => [r[0], r]));
  const after = Object.fromEntries(offsets.map(k => {
    const row = byIndex.get(best[0]+k);
    return [k, row && best[2] > 0 ? row[2]/best[2]*100 : null];
  }));
  return {peakIndex: best[0], peakMonth: best[1], peakAvg: best[2], peakMax: Math.max(...lifecycle.map(r => r[3] || 0)), after, months: lifecycle.length};
}

export function shareOf(rows, test){
  return rows.length ? rows.filter(test).length / rows.length * 100 : null;
}

const kind = app => [app.online_coop ? "온라인 협동" : app.coop ? "협동" : app.multi ? "멀티" : "싱글", app.early_access ? "앞서 해보기" : ""].filter(Boolean).join(" · ");
const price = app => app.free ? "무료" : app.price_usd == null ? "—" : `$${app.price_usd.toFixed(2)}`;

export function renderSteamTrends(root, data, h){
  const {header, panel, table, stats, note, link, esc, num, compact, options, chart, on, palette, rerender} = h;
  const pct = v => v == null ? "—" : `${num(v, 0)}%`;
  const rows = newReleaseRows(data, Number(prefs.maxDays));
  const top100 = newReleaseRows(data, 365);
  const paid = top100.filter(r => !r.app.free);
  const movers = weeklyMovers(data).filter(r => prefs.movers === "all" || (ageDays(r.app, data.date) ?? 1e9) <= 730);
  const apps = Object.entries(data.apps || {}).map(([id, app]) => ({id: Number(id), app, fade: fadeRow(app.lifecycle)}));
  const group = apps.filter(a => a.fade && a.fade.months >= 2 && (prefs.group === "seed" ? a.app.seed : prefs.group === "ranked" ? a.app.first_seen && launchOf(a.app) >= "2023-01-01" : a.app.seed || launchOf(a.app) >= "2023-01-01"));
  const lines = [...group].sort((a,b) => b.fade.peakAvg - a.fade.peakAvg).slice(0, 10);
  const maxIndex = Math.min(24, Math.max(0, ...lines.flatMap(a => a.app.lifecycle.map(r => r[0]))));
  const fadeMedian = k => median(group.map(a => a.fade.after[k]));
  const daily = apps.filter(a => a.app.daily?.length).sort((a,b) => (b.app.daily.at(-1)[1] || 0) - (a.app.daily.at(-1)[1] || 0)).slice(0, 8);
  const days = [...new Set(daily.flatMap(a => a.app.daily.map(r => r[0])))].sort().slice(-90);
  const week = data.weekly?.at(-1);
  const untracked = apps.filter(a => a.app.seed && a.app.steamcharts?.status === "untracked").map(a => a.app.name);

  root.innerHTML = header("지금 어떤 신작이 뜨고, 얼마나 버틸까?", "Steam 공식 동시접속·주간 최다 플레이 순위에서 출시 2년 안의 게임을 찾아 출시 이후 흐름을 쌓습니다. 동시접속자는 판매량·매출·고유 이용자 수가 아닙니다.") +
    stats([
      ["상위 100 중 출시 1년 이내", `${top100.length}개`, `Steam 동시접속 순위 · ${esc((data.concurrent?.observed_at || "").replace("T", " ").slice(0, 16))} UTC`],
      ["그중 유료 $10 이하", pct(shareOf(paid, r => r.app.price_usd != null && r.app.price_usd <= 10)), `유료 ${paid.length}개 기준 · 미국 상점 정가`],
      ["그중 협동 지원", pct(shareOf(top100, r => r.app.coop)), "Steam 상점 분류의 협동(온라인·로컬)"],
      ["최고 달 3개월 뒤 남은 동접", pct(fadeMedian(3)), `월평균 동접 중앙값 · 아래 비교 묶음 ${group.length}개`],
    ]) +
    panel("지금 상위 100 안의 신작",
      `<div class="gm-toolbar"><label>출시 후<select id="st-max-days">${options([["90","90일 이내"],["180","180일 이내"],["365","1년 이내"],["730","2년 이내"]], prefs.maxDays)}</select></label></div>` +
      table(["게임","순위","출시","정가","분류","지금 동접","오늘 최고","주간 순위"], rows.map(r => [
        link(store(r.id), r.app.name || r.id), r.rank, `${launchCell(r.app, esc)}<small>출시 ${num(r.age)}일째</small>`, price(r.app), esc(kind(r.app)),
        compact(r.ccu), compact(r.peak), r.week ? `${r.week[2] ? `${r.week[2]} → ` : "신규 → "}${r.week[1]}` : "—"])) +
      note("지금 동접은 Steam이 순위를 갱신한 시각의 값, 오늘 최고는 Steam 순위표가 표시한 그날 최고값입니다. 정가는 할인 전 미국 상점 가격이며 출시 당시 가격과 다를 수 있습니다.")) +
    panel(`주간 급상승${week ? ` · ${esc(week.week)} 주` : ""}`,
      `<div class="gm-toolbar"><label>대상<select id="st-movers">${options([["new","출시 2년 이내"],["all","전체 (할인·업데이트로 오른 옛 게임 포함)"]], prefs.movers)}</select></label></div>` +
      table(["게임","이번 주","지난 주","변화","출시","정가","주간 최고 동접"], movers.slice(0, 15).map(r => [
        link(store(r.id), r.app.name || r.id), r.rank, r.prev || "—", r.prev ? `▲${r.jump}` : "신규 진입", launchCell(r.app, esc), price(r.app), compact(r.peak)])) +
      note("Steam 주간 최다 플레이 상위 100 기준. 지난 주 100위 밖이었거나 10계단 이상 오른 게임입니다. 순위는 판매 순위가 아닙니다.")) +
    panel("출시 후 흐름 · 최고 달 대비 월평균 동접",
      `<div class="gm-toolbar"><label>비교 묶음<select id="st-group">${options([["seed","바이럴 흥행작 (선정 목록)"],["ranked","상위 100에 든 신작"],["all","전체"]], prefs.group)}</select></label></div>` +
      `<div class="gm-chart gm-chart-tall"><canvas id="st-lifecycle" role="img" aria-label="출시 후 경과 개월별 최고 달 대비 월평균 동시접속자"></canvas></div>` +
      table(["게임","출시","정가","분류","최고 달","최고 월평균","+1개월","+3개월","+6개월","+12개월"], [...group].sort((a,b) => b.fade.peakAvg - a.fade.peakAvg).map(a => [
        link(store(a.id), a.app.name || a.id), launchCell(a.app, esc), price(a.app), esc(kind(a.app)), `${esc(a.fade.peakMonth)}<small>출시 ${a.fade.peakIndex}개월째</small>`,
        compact(a.fade.peakAvg), pct(a.fade.after[1]), pct(a.fade.after[3]), pct(a.fade.after[6]), pct(a.fade.after[12])])) +
      note(`SteamCharts의 완료된 달 월평균 동접. 출시 달(0개월)은 한 달을 다 채우지 않습니다. 앞서 해보기로 먼저 나온 게임은 SteamCharts 첫 기록 달을 출시로 보고 정식 출시일을 따로 표시합니다. +N개월은 최고 달 대비 비율이며 아직 지나지 않은 달은 비워 둡니다. 중앙값: +1개월 ${pct(fadeMedian(1))} · +3개월 ${pct(fadeMedian(3))} · +6개월 ${pct(fadeMedian(6))}.${untracked.length ? ` SteamCharts 미수록: ${esc(untracked.join(", "))} — 아래 일별 관측만 있습니다.` : ""}`)) +
    panel("출시 2년 이내 게임의 일별 동접",
      `<div class="gm-chart"><canvas id="st-daily" role="img" aria-label="신작 일별 동시접속자"></canvas></div>` +
      note(`매일 KST 07:20 무렵 같은 시각에 조회한 값입니다(상위 100 안이면 순위표 값, 밖이면 게임별 현재 접속자). 2026-11-27부터 쌓기 시작했으며 그 이전 값은 없습니다. 조회 실패일은 비워 둡니다.`)) +
    note(`수집 ${esc((data.fetched || "").slice(0, 10))} · 추적 ${apps.length}개${data.errors?.length ? ` · 최근 조회 실패 ${data.errors.length}건(기존 값 유지)` : ""}. 바이럴 흥행작 선정 목록은 2023년 이후 크게 화제가 된 저가·협동·단순 루프 게임을 직접 고른 것이며 시장 전체를 대표하지 않습니다.`);

  on("#st-max-days", "change", e => { prefs.maxDays = e.target.value; rerender(); });
  on("#st-movers", "change", e => { prefs.movers = e.target.value; rerender(); });
  on("#st-group", "change", e => { prefs.group = e.target.value; rerender(); });
  const labels = Array.from({length: maxIndex+1}, (_, i) => `${i}개월`);
  chart("st-lifecycle", "line", labels, lines.map((a, i) => {
    const map = new Map(a.app.lifecycle.map(r => [r[0], r[4]]));
    return {label: a.app.name, data: labels.map((_, k) => map.get(k) ?? null), borderColor: palette[i % palette.length], backgroundColor: palette[i % palette.length], pointRadius: 2, borderWidth: 1.5, spanGaps: false};
  }), {percentAxis: true});
  chart("st-daily", "line", days, daily.map((a, i) => {
    const map = new Map(a.app.daily.map(r => [r[0], r[1]]));
    return {label: a.app.name, data: days.map(d => map.get(d) ?? null), borderColor: palette[i % palette.length], backgroundColor: palette[i % palette.length], pointRadius: days.length < 20 ? 3 : 0, borderWidth: 1.5, spanGaps: false};
  }));
}

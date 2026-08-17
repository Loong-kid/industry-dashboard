/* 수주 갱신 버튼: GitHub Actions(update-data.yml)를 workflow_dispatch로 원격 실행하고
   완료까지 상태를 폴링한 뒤 대시보드 데이터를 다시 불러온다.

   정적 사이트라 서버가 없으므로, 실행 권한은 사용자의 GitHub PAT(브라우저 localStorage에만
   저장, 리포엔 안 올라감)로 GitHub REST API를 직접 호출해 얻는다. */
"use strict";

const REPO = (window.dashboard && window.dashboard.GH_REPO) || "Loong-kid/industry-dashboard";
const WORKFLOW = "update-data.yml";

// 같은 workflow가 전부 갱신하지만, 라벨/신선도 확인 대상은 현재 탭에 맞춘다.
const REFRESH_TARGETS = {
  shipbuilding: { file: "data/shipbuilding/korea_orders.json", label: "수주 갱신" },
  institution: { file: "data/institution/major_holdings.json", label: "수급 갱신" },
  gifts: { file: "data/gifts/gifts.json", label: "증여 갱신" },
};
const DEFAULT_TARGET = { file: "data/shipbuilding/korea_orders.json", label: "데이터 갱신" };
function currentTarget() {
  const id = window.dashboard && window.dashboard.state && window.dashboard.state.industry && window.dashboard.state.industry.id;
  return REFRESH_TARGETS[id] || DEFAULT_TARGET;
}
const PAT_KEY = "gh_pat";
const API = "https://api.github.com";

const $ = (id) => document.getElementById(id);
const getPat = () => localStorage.getItem(PAT_KEY) || "";
const setPat = (v) => (v ? localStorage.setItem(PAT_KEY, v) : localStorage.removeItem(PAT_KEY));

function ghHeaders() {
  return {
    Authorization: `Bearer ${getPat()}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── 버튼 상태 ────────────────────────────────────────────────────
let busy = false;
function setBtn(state, text) {
  const btn = $("refresh-btn");
  const label = $("refresh-label");
  btn.classList.remove("is-loading", "is-ok", "is-err");
  if (state) btn.classList.add(state);
  if (text) label.textContent = text;
  btn.disabled = state === "is-loading";
}

// ── GitHub API 흐름 ──────────────────────────────────────────────
async function dispatchWorkflow() {
  const res = await fetch(`${API}/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: ghHeaders(),
    body: JSON.stringify({ ref: "main" }),
  });
  if (res.status === 204) return true;
  if (res.status === 401 || res.status === 403) throw new Error("AUTH");
  const body = await res.text();
  throw new Error(`dispatch 실패 (${res.status}): ${body.slice(0, 120)}`);
}

async function findRun(sinceMs) {
  // dispatch 이후 생성된 최신 workflow_dispatch 런을 찾음
  const res = await fetch(
    `${API}/repos/${REPO}/actions/runs?event=workflow_dispatch&per_page=5`,
    { headers: ghHeaders() }
  );
  if (!res.ok) return null;
  const data = await res.json();
  const runs = (data.workflow_runs || []).filter((r) => new Date(r.created_at).getTime() >= sinceMs - 60000);
  return runs.sort((a, b) => b.id - a.id)[0] || null;
}

async function waitForRun(run) {
  // status: queued | in_progress | completed / conclusion: success | failure | ...
  for (let i = 0; i < 120; i++) { // 최대 ~20분
    const res = await fetch(`${API}/repos/${REPO}/actions/runs/${run.id}`, { headers: ghHeaders() });
    if (res.ok) {
      const r = await res.json();
      if (r.status === "completed") return r;
    }
    await sleep(10000);
  }
  return null;
}

// 커밋 후 Pages 재배포까지 시간이 걸리므로, 대상 JSON의 updated가 바뀔 때까지 확인
async function waitForFreshData(prevUpdated, file) {
  for (let i = 0; i < 24; i++) { // 최대 ~2분
    try {
      const res = await fetch(`${file}?t=${Date.now()}`);
      if (res.ok) {
        const j = await res.json();
        if (j.updated && j.updated !== prevUpdated) return true;
      }
    } catch (e) { /* 재시도 */ }
    await sleep(5000);
  }
  return false; // 타임아웃이어도 갱신 자체는 됐을 수 있음
}

async function currentUpdated(file) {
  try {
    const res = await fetch(`${file}?t=${Date.now()}`);
    if (res.ok) return (await res.json()).updated || "";
  } catch (e) { /* noop */ }
  return "";
}

// ── 메인 클릭 핸들러 ─────────────────────────────────────────────
async function onRefresh() {
  if (busy) return;
  if (!getPat()) { openModal(); return; }
  busy = true;
  const target = currentTarget(); // 클릭 시점의 탭 기준으로 고정
  const started = Date.now();
  try {
    setBtn("is-loading", "실행 요청…");
    const prevUpdated = await currentUpdated(target.file);
    await dispatchWorkflow();

    setBtn("is-loading", "실행 대기…");
    let run = null;
    for (let i = 0; i < 12 && !run; i++) { await sleep(3000); run = await findRun(started); }
    if (!run) throw new Error("실행된 워크플로를 찾지 못함 (Actions 탭 확인)");

    setBtn("is-loading", "수집 중…");
    const done = await waitForRun(run);
    if (!done) throw new Error("시간 초과 — Actions 로그 확인");
    if (done.conclusion !== "success") {
      window._lastRunUrl = done.html_url;
      throw new Error(`실패(${done.conclusion})`);
    }

    setBtn("is-loading", "반영 대기…");
    await waitForFreshData(prevUpdated, target.file);
    await window.dashboard.reloadData();
    setBtn("is-ok", "갱신 완료 ✓");
    await sleep(3000);
    setBtn(null, target.label);
  } catch (e) {
    if (e.message === "AUTH") {
      setBtn("is-err", "토큰 오류");
      openModal("토큰이 유효하지 않거나 권한이 부족합니다 (Actions: Read and write 필요).");
    } else {
      setBtn("is-err", "실패");
      console.error(e);
      const url = window._lastRunUrl;
      $("refresh-btn").title = e.message + (url ? ` — ${url}` : "");
    }
    await sleep(4000);
    setBtn(null, target.label);
  } finally {
    busy = false;
  }
}

// ── PAT 설정 모달 ────────────────────────────────────────────────
function openModal(msg) {
  const owner = REPO.split("/")[0];
  $("pat-link").href = `https://github.com/settings/personal-access-tokens/new`;
  $("pat-input").value = getPat();
  $("pat-status").textContent = msg || "";
  $("pat-status").className = "modal-status" + (msg ? " err" : "");
  $("pat-modal").hidden = false;
  $("pat-input").focus();
}
function closeModal() { $("pat-modal").hidden = true; }

// 탭에 맞는 버튼 라벨 (app.js renderIndustry / 해시 변경 시 호출)
function setRefreshLabel() {
  if (busy) return;
  const label = $("refresh-label");
  if (label) label.textContent = currentTarget().label;
}
window.setRefreshLabel = setRefreshLabel;

function initRefresh() {
  $("refresh-btn").addEventListener("click", onRefresh);
  window.addEventListener("hashchange", setRefreshLabel);
  setRefreshLabel();
  $("settings-btn").addEventListener("click", () => openModal());
  $("pat-cancel").addEventListener("click", closeModal);
  $("pat-modal").addEventListener("click", (e) => { if (e.target.id === "pat-modal") closeModal(); });
  $("pat-save").addEventListener("click", () => {
    const v = $("pat-input").value.trim();
    setPat(v);
    $("pat-status").textContent = v ? "저장됨 — 이제 '수주 갱신'을 누르세요." : "토큰이 비었습니다.";
    $("pat-status").className = "modal-status ok";
    if (v) setTimeout(closeModal, 900);
  });
  $("pat-clear").addEventListener("click", () => {
    setPat("");
    $("pat-input").value = "";
    $("pat-status").textContent = "토큰을 삭제했습니다.";
    $("pat-status").className = "modal-status";
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initRefresh);
} else {
  initRefresh();
}

/* LNG 용량 막대: 기업별(한 칸 = 프로젝트) 또는 프로젝트별로 상태 색을 나눠 그린다. */
"use strict";

const LngCapacity = (() => {
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const mt = value => Number(value).toLocaleString("ko-KR", {minimumFractionDigits: 1, maximumFractionDigits: 1});
  const url = raw => { try { const u = new URL(raw); return u.protocol === "https:" ? u.href : ""; } catch { return ""; } };

  // 표시 중인 상태만 합쳐 큰 순서로 묶는다. 칸은 상태 순서, 같은 상태에서는 큰 순서다.
  function groupRows(rows, active, mode, order) {
    const rank = Object.fromEntries(order.map((s, i) => [s, i]));
    const groups = new Map();
    for (const row of rows) {
      if (!active.has(row.status)) continue;
      const key = mode === "company" ? row.company : `${row.project}|${row.company}`;
      if (!groups.has(key)) groups.set(key, {key, label: mode === "company" ? row.company : row.project, sub: mode === "company" ? "" : row.company, rows: [], total: 0});
      const group = groups.get(key);
      group.rows.push(row);
      group.total += row.mtpa;
    }
    for (const group of groups.values()) group.rows.sort((a, b) => rank[a.status] - rank[b.status] || b.mtpa - a.mtpa);
    return [...groups.values()].sort((a, b) => b.total - a.total || a.label.localeCompare(b.label, "ko"));
  }

  function tipHtml(row, labels) {
    const facts = [row.unit, row.start && `가동 ${row.start}`, row.fid && `FID ${row.fid}`].filter(Boolean).join(" · ");
    return `<b>${esc(row.project)}</b><span>${esc(row.company)}</span><span>${esc(labels[row.status])} · ${mt(row.mtpa)} MTPA</span>`
      + (facts ? `<span>${esc(facts)}</span>` : "") + (row.note ? `<span>${esc(row.note)}</span>` : "");
  }

  function render(doc) {
    const order = doc.status_order.filter(s => doc.totals[s] > 0), labels = doc.status_labels; // 값이 없는 상태는 칩도 뺀다
    const state = {mode: "company", active: new Set(order), open: new Set()};
    const card = document.createElement("section");
    card.className = "card lng-capacity";
    card.innerHTML = `
      <div class="card-head"><div><h3 class="card-title">${esc(doc.name)}</h3>
        <p class="card-freq">단위 MTPA · ${esc(doc.updated)} 대조 · ${doc.rows.length}건</p></div>
        <div class="lc-mode" role="group" aria-label="묶는 기준">
          <button type="button" data-mode="company" aria-pressed="true">${esc(doc.row_noun)}별</button>
          <button type="button" data-mode="project" aria-pressed="false">${esc(doc.project_noun)}별</button>
        </div></div>
      <div class="lc-legend" role="group" aria-label="상태 고르기">${order.map(s => `
        <button type="button" data-status="${s}" aria-pressed="true">
          <span class="lc-key lc-${s}"></span><span>${esc(labels[s])}</span><b>${mt(doc.totals[s])}</b></button>`).join("")}</div>
      <p class="lc-note">${esc(doc.note)}</p>
      <ol class="lc-rows"></ol>
      <div class="lc-tip" hidden></div>
      <details class="lc-table"><summary>표로 보기·출처</summary><div class="lc-table-scroll"><table>
        <thead><tr><th>${esc(doc.row_noun)}</th><th>${esc(doc.project_noun)}</th><th>상태</th><th class="lc-num">MTPA</th><th>가동(예정)</th><th>FID</th><th>메모</th><th>출처</th></tr></thead>
        <tbody>${[...doc.rows].sort((a, b) => a.company.localeCompare(b.company, "ko") || order.indexOf(a.status) - order.indexOf(b.status) || b.mtpa - a.mtpa).map(r => {
          const link = url(r.source_url);
          return `<tr><td>${esc(r.company)}</td><td>${esc(r.project)}${r.unit ? ` <small>${esc(r.unit)}</small>` : ""}</td><td>${esc(labels[r.status])}</td><td class="lc-num">${mt(r.mtpa)}</td><td>${esc(r.start)}</td><td>${esc(r.fid)}</td><td>${esc(r.note)}</td><td>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${esc(r.source)} ↗</a>` : esc(r.source)}</td></tr>`;
        }).join("")}</tbody></table></div></details>`;
    const list = card.querySelector(".lc-rows"), tip = card.querySelector(".lc-tip");

    // 칸 안에 이름이 다 들어갈 때만 보여 준다.
    function fitLabels() {
      for (const seg of list.querySelectorAll(".lc-seg > span")) {
        seg.style.visibility = "hidden";
        seg.style.visibility = seg.scrollWidth <= seg.parentElement.clientWidth - 8 ? "" : "hidden";
      }
    }
    function draw() {
      const groups = groupRows(doc.rows, state.active, state.mode, order);
      const max = groups[0]?.total || 1;
      list.innerHTML = groups.length ? groups.map((g, i) => {
        const open = state.open.has(g.key);
        return `<li class="lc-row">
          <button type="button" class="lc-name" data-group="${i}" aria-expanded="${open}" title="${esc(g.label)}"><span>${esc(g.label)}</span>${g.sub ? `<small>${esc(g.sub)}</small>` : ""}</button>
          <div class="lc-bar"><div class="lc-track" style="width:${(g.total / max * 100).toFixed(2)}%">${g.rows.map((r, j) =>
            `<div class="lc-seg lc-${r.status}" data-group="${i}" data-row="${j}" style="flex:${r.mtpa} 1 0"><span>${esc(r.project)}</span></div>`).join("")}</div>
            <b class="lc-total">${mt(g.total)}</b></div>
          ${open ? `<ul class="lc-detail">${g.rows.map(r => `<li><span class="lc-key lc-${r.status}"></span><span>${esc(r.project)}${r.unit ? ` <small>${esc(r.unit)}</small>` : ""}</span><span>${esc(labels[r.status])}${r.start ? ` · ${esc(r.start)}` : ""}</span><b>${mt(r.mtpa)}</b></li>`).join("")}</ul>` : ""}
        </li>`;
      }).join("") : `<li class="lc-empty">상태를 하나 이상 고르면 막대가 나온다.</li>`;
      list.groups = groups;
      fitLabels();
    }
    card.querySelector(".lc-mode").addEventListener("click", e => {
      const button = e.target.closest("button[data-mode]");
      if (!button) return;
      state.mode = button.dataset.mode; state.open.clear();
      card.querySelectorAll(".lc-mode button").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
      draw();
    });
    card.querySelector(".lc-legend").addEventListener("click", e => {
      const button = e.target.closest("button[data-status]");
      if (!button) return;
      const status = button.dataset.status, on = !state.active.has(status);
      if (on) state.active.add(status); else state.active.delete(status);
      button.setAttribute("aria-pressed", String(on));
      draw();
    });
    list.addEventListener("click", e => {
      const hit = e.target.closest("[data-group]");
      if (!hit) return;
      const key = list.groups[+hit.dataset.group].key;
      if (state.open.has(key)) state.open.delete(key); else state.open.add(key);
      draw();
    });
    list.addEventListener("pointermove", e => {
      const seg = e.pointerType === "touch" ? null : e.target.closest(".lc-seg");
      tip.hidden = !seg;
      if (!seg) return;
      tip.innerHTML = tipHtml(list.groups[+seg.dataset.group].rows[+seg.dataset.row], labels);
      const box = card.getBoundingClientRect();
      const x = e.clientX - box.left, y = e.clientY - box.top;
      const flip = x > box.width - 300;
      tip.style.left = flip ? "auto" : `${x + 14}px`;
      tip.style.right = flip ? `${box.width - x + 14}px` : "auto";
      tip.style.top = `${y + 14}px`;
    });
    list.addEventListener("pointerleave", () => { tip.hidden = true; });
    new ResizeObserver(fitLabels).observe(list);
    draw();
    return card;
  }
  return {render, groupRows};
})();

function renderLngCapacity(doc) { return LngCapacity.render(doc); }

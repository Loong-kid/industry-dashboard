"use strict";

// Currency columns and a percentage line must never share an axis or a unit.
function dcComboChartData(doc, filtered) {
  const labels = [...new Set(Object.values(filtered).flatMap(points => points.map(p => p[0])))].sort();
  const palette = SERIES_COLORS[isDark() ? "dark" : "light"];
  const datasets = Object.entries(filtered).map(([label, points], i) => {
    const margin = label === doc.margin_series, values = new Map(points);
    return {label, data: labels.map(date => values.get(date) ?? null),
      type: margin ? "line" : "bar", yAxisID: margin ? "margin" : "amount",
      borderColor: palette[i], backgroundColor: margin ? palette[i] : palette[i] + "99",
      borderWidth: margin ? 2 : 0, pointRadius: margin ? 2 : 0,
      spanGaps: false, order: margin ? 0 : 1, maxBarThickness: 24,
      unit: doc.series_units[label]};
  });
  return {labels, datasets};
}

function renderUsDatacenterCombo(doc) {
  const card = document.createElement("div");
  card.className = "card dc-financial-combo";
  card.dataset.dcCombo = doc.id;
  const names = Object.keys(doc.series);
  const latest = doc.updated;
  const filtered = Object.fromEntries(names.map(name => [name, doc.series[name].filter(([date]) => date >= rangeCutoff())]));
  if (Object.values(filtered).every(points => !points.length)) {
    for (const name of names) filtered[name] = doc.series[name];
  }
  const e = escapeHtml;
  card.innerHTML = `<div class="card-head"><div class="card-name">${e(doc.name)}</div><div class="card-freq">${e(doc.frequency_label)}</div></div>
    <p class="card-foot">${e(doc.collection_status.checked)} · ${e(doc.collection_status.message)}</p>
    <div class="stat-date">${e(periodLabel(doc, latest))} · ${e(latest)}</div>
    <dl class="dc-combo-stats">${names.map(name => {
      const value = new Map(doc.series[name]).get(latest), unit = doc.series_units[name];
      const ref = doc.series_sources[name]?.[latest];
      const memo = `${latest} · ${name} · ${unit}\n${ref?.start || ""} ~ ${ref?.end || latest}\n${ref?.calculation || "공시 실제 기간"}`;
      return `<div><dt>${e(name)}</dt><dd>${value == null ? "—" : `<button type="button" class="gm-money" data-money-note="${e(memo)}">${fmt(value)}</button>`} <small>${value == null ? "미공개" : e(unit)}</small></dd></div>`;
    }).join("")}</dl>
    ${doc.missing_profit_note ? `<p class="ir-scope-note">${e(doc.missing_profit_note)}</p>` : ""}
    <div class="dc-combo-chips"></div><div class="chart-wrap"><canvas aria-label="${e(doc.name)}" role="img"></canvas></div>
    <p class="ir-scope-note">${e(doc.note)}</p>
    <div class="card-foot"><a href="${e(doc.source_url)}" target="_blank" rel="noopener">${e(doc.source)} ↗</a><button type="button" class="table-btn">표 보기</button></div>
    <div class="data-table" hidden></div>`;
  const data = dcComboChartData(doc, filtered);
  const chart = new Chart(card.querySelector("canvas"), {
    type: "bar", data,
    options: {responsive: true, maintainAspectRatio: false, animation: false,
      interaction: {mode: "index", intersect: false},
      plugins: {legend: {display: false}, tooltip: {
        backgroundColor: css("--surface"), titleColor: css("--ink"), bodyColor: css("--ink-2"),
        borderColor: css("--border"), borderWidth: 1,
        callbacks: {title: items => items.length ? periodLabel(doc, items[0].label) : "",
          label: c => `${c.dataset.label}: ${fmt(c.parsed.y)} ${c.dataset.unit}`,
          afterLabel: c => doc.series_sources[c.dataset.label]?.[c.label]?.calculation || ""}}},
      scales: {
        x: {ticks: {color: css("--muted"), maxTicksLimit: 6, maxRotation: 0, font: {size: 11},
          callback: function(v) {return periodLabel(doc, this.getLabelForValue(v));}}, grid: {display: false}},
        amount: {position: "left", beginAtZero: true, title: {display: true, text: "USD 백만", color: css("--muted")},
          ticks: {color: css("--muted"), maxTicksLimit: 5, callback: fmt}, grid: {color: css("--grid")}},
        margin: {position: "right", display: data.datasets.at(-1).data.some(v => v != null),
          title: {display: true, text: "%", color: css("--muted")},
          ticks: {color: css("--muted"), maxTicksLimit: 5, callback: v => fmt(v) + "%"}, grid: {drawOnChartArea: false}},
      }}, plugins: [crosshair],
  });
  state.charts.push(chart);
  const chips = card.querySelector(".dc-combo-chips");
  buildChips(chips, chart);
  chips.querySelectorAll("input").forEach((input, i) => {
    const chip = input.closest("label");
    if (data.datasets[i].data.every(v => v == null)) {
      input.disabled = true;
      chip.append(" · 미공개");
    }
    chip.tabIndex = input.disabled ? -1 : 0;
    chip.setAttribute("role", "checkbox");
    chip.setAttribute("aria-disabled", String(input.disabled));
    chip.setAttribute("aria-checked", String(input.checked));
    input.addEventListener("change", () => chip.setAttribute("aria-checked", String(input.checked)));
    chip.addEventListener("keydown", event => {
      if (!input.disabled && [" ", "Enter"].includes(event.key)) {event.preventDefault(); input.click();}
    });
  });
  const table = card.querySelector(".data-table"), button = card.querySelector(".table-btn");
  button.addEventListener("click", () => {
    table.hidden = !table.hidden;
    button.textContent = table.hidden ? "표 보기" : "표 닫기";
    if (!table.hidden) table.innerHTML = `<table><thead><tr><th>회계기간</th>${names.map(name => `<th>${e(name)} (${e(doc.series_units[name])})</th>`).join("")}<th>원문</th></tr></thead><tbody>${data.labels.slice().reverse().map(date =>
      `<tr><td>${e(periodLabel(doc, date))}</td>${names.map(name => {
        const v = new Map(filtered[name]).get(date), ref = doc.series_sources[name]?.[date];
        return `<td>${v == null ? "—" : `<button type="button" class="gm-money" data-money-note="${e(ref?.calculation || "공시 실제 기간")} · ${e(date)} · ${e(doc.series_units[name])}">${fmt(v)}</button>`}</td>`;
      }).join("")}<td>${[...new Set(names.flatMap(name => {
        const ref = doc.series_sources[name]?.[date];
        return ref ? [ref.url, ...(ref.components || []).map(c => c.url)] : [];
      }))].map((url, i) => `<a href="${e(url)}" target="_blank" rel="noopener">SEC ${i+1}</a>`).join(" / ")}</td></tr>`).join("")}</tbody></table>`;
  });
  return card;
}

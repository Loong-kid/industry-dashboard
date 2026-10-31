"use strict";

function dcComparisonDefaults(doc, saved) {
  const available = Object.keys(doc.series).filter(name => doc.series[name].some(([,v]) => v != null));
  return (saved ?? doc.default_series ?? available).filter(name => available.includes(name));
}

// Reuse the shipbuilding line chart, company chips and headline interaction.
// Only this wrapper adds per-company fiscal period/source notes and persistence.
function renderUsDatacenterComparison(doc) {
  state.dcComparisonSelections ??= {};
  const selected = dcComparisonDefaults(doc, state.dcComparisonSelections[doc.id]);
  const card = renderCard({...doc, company_comparison: false, default_series: selected}, doc.id);
  card.classList.add("dc-company-comparison");
  card.dataset.dcComparison = doc.comparison_metric;
  const chart = Chart.getChart(card.querySelector("canvas"));
  const names = Object.keys(doc.series), e = escapeHtml;
  chart.options.plugins.tooltip.callbacks.afterLabel = c => doc.series_point_notes[c.dataset.label]?.[c.label] || [];
  chart.options.plugins.tooltip.callbacks.afterBody = () => [];
  const updateHeadline = () => {
    if (!chart.data.datasets.some((_,i) => chart.isDatasetVisible(i))) {
      card.querySelector('.card-stat').innerHTML = '<span class="stat-unit">비교할 기업을 선택하세요</span>';
      return;
    }
    const name = card.querySelector(".stat-series")?.textContent;
    const last = doc.series[name]?.at(-1);
    if (!last) return;
    const ref = doc.series_sources[name]?.[last[0]], memo = doc.series_point_notes[name]?.[last[0]];
    const date = card.querySelector(".stat-date");
    if (date && ref) date.textContent = `${ref.period} · ${ref.observed_date}`;
    const value = card.querySelector(".stat-value");
    if (value && memo) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "stat-value gm-money";
      button.textContent = value.textContent; button.dataset.moneyNote = memo.join("\n");
      button.setAttribute("aria-label", `${value.textContent} ${doc.unit}. ${memo.join(". ")}`);
      value.replaceWith(button);
    }
  };
  card.querySelectorAll(".chips input").forEach((input, i) => {
    const name = names[i], chip = input.closest("label");
    const empty = !doc.series[name].some(([,v]) => v != null);
    input.disabled = empty;
    if (empty) {
      chip.append(name === "Meta" ? " · 해당 없음" : " · 미공개");
      chip.title = doc.series_unavailable[name] || "선택 기간에 공시된 자료가 없습니다.";
    } else if (name.startsWith("xAI")) chip.title = "Grok·X·Cursor 등을 포함한 AI/SI 사업부";
    chip.tabIndex = empty ? -1 : 0;
    chip.setAttribute("role", "checkbox");
    chip.setAttribute("aria-checked", String(input.checked));
    chip.setAttribute("aria-disabled", String(empty));
    input.addEventListener("change", () => {
      state.dcComparisonSelections[doc.id] = chart.data.datasets.filter((_, index) => chart.isDatasetVisible(index)).map(d => d.label);
      chip.setAttribute("aria-checked", String(input.checked));
      updateHeadline();
    });
    chip.addEventListener("keydown", event => {
      if (!empty && [" ", "Enter"].includes(event.key)) {event.preventDefault(); input.click();}
    });
  });
  updateHeadline();
  // Notes belong to a company and a period; a shared date note can otherwise
  // mislabel Oracle's August close as a September cloud quarter.
  const table = card.querySelector(".data-table");
  card.querySelector(".table-btn").addEventListener("click", () => {
    if (table.style.display === "none") return;
    const dates = chart.data.labels.slice().reverse();
    const maps = Object.fromEntries(names.map(name => [name, new Map(doc.series[name])]));
    table.innerHTML = `<table><thead><tr><th>${doc.frequency === "yearly" ? "결산연도" : "표시 분기"}</th>${names.map(name => `<th>${e(name)} (${e(doc.unit)})</th>`).join("")}<th>공식 원문</th></tr></thead><tbody>${dates.map(date => {
      const sources = [];
      const cells = names.map(name => {
        const value = maps[name].get(date), ref = doc.series_sources[name]?.[date];
        if (value == null) return "<td>—</td>";
        for (const part of [ref, ...(ref?.components || [])]) {
          if (part && !sources.some(s => s.url === part.url)) sources.push({url: part.url, label: name});
        }
        const memo = doc.series_point_notes[name]?.[date]?.join("\n") || "";
        return `<td><button type="button" class="gm-money" data-money-note="${e(memo)}">${fmt(value)}</button><small>${e(ref?.period || "")} · ${e(ref?.observed_date || "")}</small></td>`;
      }).join("");
      return `<tr><td>${e(doc.period_labels[date])}</td>${cells}<td>${sources.map(source => `<a href="${e(source.url)}" target="_blank" rel="noopener">${e(source.label)}</a>`).join(" / ")}</td></tr>`;
    }).join("")}</tbody></table>`;
  });
  return card;
}

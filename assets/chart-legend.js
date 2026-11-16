/* Native legends: show a line sample, rather than dashing a tiny filled box. */
(() => {
  const Chart = window.Chart;
  if (!Chart) return;
  const generators = new WeakMap();
  Chart.register({
    id: 'dashboardLegend',
    beforeUpdate(chart) {
      const legend = chart.options.plugins?.legend;
      if (!legend || legend.display === false || !['line', 'bar', 'scatter', 'bubble'].includes(chart.config.type)) return;
      const labels = legend.labels;
      const current = labels.generateLabels;
      let state = generators.get(chart);
      if (!state || current !== state.generate) {
        const original = current;
        const generate = function (chart) {
          return original.call(this, chart).map(item => {
            if (item.datasetIndex == null) return item;
            const meta = chart.getDatasetMeta(item.datasetIndex);
            const dataset = chart.data.datasets[item.datasetIndex];
            const showLine = dataset.showLine ?? meta.controller.options?.showLine;
            if ((meta.type === 'line' && showLine !== false) || (meta.type === 'scatter' && showLine === true)) {
              // getStyle() resolves dataset line options; getStyle(0) resolves
              // point options and can lose the line's dash, width and color.
              const style = meta.controller.getStyle();
              return {
                ...item, pointStyle: 'line', rotation: 0,
                strokeStyle: style.borderColor, fillStyle: style.borderColor,
                lineWidth: style.borderWidth ?? 2,
                lineDash: style.borderDash || [], lineDashOffset: style.borderDashOffset || 0,
                lineCap: style.borderCapStyle || 'butt', lineJoin: style.borderJoinStyle || 'miter',
              };
            }
            if (meta.type === 'bar') {
              return {...item, pointStyle: 'rect', rotation: 0, lineWidth: 0, lineDash: []};
            }
            return item; // Keep point-only markers, visibility and custom labels.
          });
        };
        state = {generate};
        generators.set(chart, state);
      }
      labels.generateLabels = state.generate;
      labels.usePointStyle = true;
      // A wide sample helps read dashes, but stretches point-only markers.
      const pointOnly = chart.data.datasets.some(dataset => {
        const type = dataset.type || chart.config.type;
        const showLine = dataset.showLine ?? chart.options.showLine;
        return type === 'bubble' || (type === 'scatter' && showLine !== true) || (type === 'line' && showLine === false);
      });
      labels.pointStyleWidth = pointOnly ? 12 : 24;
      labels.boxWidth = labels.pointStyleWidth;
      labels.boxHeight = Math.max(8, Number(labels.boxHeight) || 8);
    },
    afterDestroy(chart) { generators.delete(chart); },
  });
})();

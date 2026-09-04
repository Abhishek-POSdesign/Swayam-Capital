/**
 * Cumulative P&L Curve Component for Swayam Capital (BUILD-11).
 *
 * Plotly line chart with zero line, area fill, and dark/light theme support.
 */

export class AnalyticsCumulativePnlComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.series = options.series || [];
    this._Plotly = null;
  }

  async update(series) {
    this.series = series || [];
    await this.render();
  }

  async render() {
    if (!this.container) return;

    this.container.innerHTML = `
      <div style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 14px 16px; height: 100%;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600;">
            📈 Cumulative Equity Curve (Net ₹)
          </span>
          <span style="font-size: 0.7rem; color: var(--dl-fg-3);">
            ${this.series.length} data points
          </span>
        </div>
        <div id="cumulative-pnl-canvas" style="width: 100%; height: 260px;"></div>
      </div>
    `;

    if (typeof window === 'undefined') return;
    if (typeof process !== 'undefined' && process.env?.VITEST) return;

    try {
      if (!this._Plotly) {
        if (window.Plotly) {
          this._Plotly = window.Plotly;
        } else {
          const m = await import('plotly.js-dist-min');
          this._Plotly = m.default || m;
        }
      }
      const Plotly = this._Plotly;
      const canvas = this.container.querySelector('#cumulative-pnl-canvas');
      if (!canvas) return;

      const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
      const bgColor = 'transparent';
      const textColor = isDark ? '#8b8e9b' : '#6b6e7b';
      const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

      const dates = this.series.map(s => s.date);
      const values = this.series.map(s => s.cumulative_pnl_inr);
      const lastVal = values.length ? values[values.length - 1] : 0;
      const lineColor = lastVal >= 0 ? '#86ab92' : '#dd8170';
      const fillColor = lastVal >= 0 ? 'rgba(134,171,146,0.12)' : 'rgba(221,129,112,0.12)';

      const trace = {
        x: dates,
        y: values,
        type: 'scatter',
        mode: 'lines+markers',
        fill: 'tozeroy',
        fillcolor: fillColor,
        line: { color: lineColor, width: 2.5, shape: 'spline' },
        marker: { size: 5, color: lineColor },
        name: 'Net P&L',
      };

      const layout = {
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        margin: { l: 45, r: 15, t: 10, b: 35 },
        xaxis: {
          showgrid: true,
          gridcolor: gridColor,
          tickfont: { color: textColor, size: 10, family: 'monospace' },
        },
        yaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: true,
          zerolinecolor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)',
          zerolinewidth: 1.5,
          tickfont: { color: textColor, size: 10, family: 'monospace' },
          tickprefix: '₹',
        },
        hovermode: 'x unified',
      };

      const config = { responsive: true, displayModeBar: false };
      Plotly.newPlot(canvas, [trace], layout, config);
    } catch (err) {
      console.error('Failed to render Cumulative P&L chart:', err);
    }
  }
}
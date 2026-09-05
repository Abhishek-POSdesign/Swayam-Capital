/**
 * P&L by Strategy Component for Swayam Capital (BUILD-11).
 *
 * Plotly horizontal bar chart showing net P&L and win rate per strategy preset.
 */

export class AnalyticsPnlByStrategyComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.stratList = options.stratList || [];
    this._Plotly = null;
  }

  async update(stratList) {
    this.stratList = stratList || [];
    await this.render();
  }

  async render() {
    if (!this.container) return;

    this.container.innerHTML = `
      <div style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: var(--radius-card); padding: 14px 16px; height: 100%;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600;">
            📊 Performance by Strategy
          </span>
          <span style="font-size: 0.7rem; color: var(--dl-fg-3);">
            ${this.stratList.length} strategies
          </span>
        </div>
        <div id="pnl-strategy-canvas" style="width: 100%; height: 260px;"></div>
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
      const canvas = this.container.querySelector('#pnl-strategy-canvas');
      if (!canvas) return;

      const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
      const bgColor = 'transparent';
      const textColor = isDark ? '#8b8e9b' : '#6b6e7b';
      const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

      const names = this.stratList.map(s => s.strategy);
      const pnls = this.stratList.map(s => s.pnl_inr);
      const colors = pnls.map(p => p >= 0 ? '#86ab92' : '#dd8170');
      const textLabels = this.stratList.map(s => `₹${Math.round(s.pnl_inr).toLocaleString('en-IN')} (${s.win_rate_pct}% WR, ${s.trades}T)`);

      const trace = {
        y: names,
        x: pnls,
        type: 'bar',
        orientation: 'h',
        marker: { color: colors, opacity: 0.85 },
        text: textLabels,
        textposition: 'auto',
        hoverinfo: 'x+y+text',
      };

      const layout = {
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        margin: { l: 110, r: 25, t: 10, b: 30 },
        xaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: true,
          zerolinecolor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)',
          tickfont: { color: textColor, size: 10, family: 'monospace' },
          tickprefix: '₹',
        },
        yaxis: {
          showgrid: false,
          tickfont: { color: textColor, size: 10 },
          autorange: 'reversed',
        },
      };

      const config = { responsive: true, displayModeBar: false };
      Plotly.newPlot(canvas, [trace], layout, config);
    } catch (err) {
      console.error('Failed to render P&L by Strategy chart:', err);
    }
  }
}
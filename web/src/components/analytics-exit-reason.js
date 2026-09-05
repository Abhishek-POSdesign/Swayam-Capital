/**
 * P&L by Exit Reason Component for Swayam Capital (BUILD-11).
 *
 * Bar chart displaying win rate and P&L by trade exit trigger.
 */

export class AnalyticsExitReasonComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.exitList = options.exitList || [];
    this._Plotly = null;
  }

  async update(exitList) {
    this.exitList = exitList || [];
    await this.render();
  }

  async render() {
    if (!this.container) return;

    this.container.innerHTML = `
      <div style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: var(--radius-card); padding: 14px 16px; height: 100%;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600;">
            🎯 P&amp;L by Exit Trigger
          </span>
          <span style="font-size: 0.7rem; color: var(--dl-fg-3);">
            ${this.exitList.length} exit types
          </span>
        </div>
        <div id="pnl-exit-reason-canvas" style="width: 100%; height: 260px;"></div>
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
      const canvas = this.container.querySelector('#pnl-exit-reason-canvas');
      if (!canvas) return;

      if (!this.exitList.length) {
        canvas.innerHTML = `
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--dl-fg-3); font-size: 0.8rem; gap: 4px;">
            <span style="font-size: 1.1rem; opacity: 0.6;">🎯</span>
            <span>— No exit reason data yet —</span>
          </div>
        `;
        return;
      }

      const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
      const bgColor = 'transparent';
      const textColor = isDark ? '#8b8e9b' : '#6b6e7b';
      const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

      const reasons = this.exitList.map(e => e.exit_reason);
      const pnls = this.exitList.map(e => e.pnl_inr);
      const colors = pnls.map(p => p >= 0 ? '#86ab92' : '#dd8170');
      const textLabels = this.exitList.map(e => `₹${Math.round(e.pnl_inr).toLocaleString('en-IN')}`);

      const trace = {
        x: reasons,
        y: pnls,
        type: 'bar',
        marker: { color: colors, opacity: 0.85 },
        text: textLabels,
        textposition: 'auto',
        hoverinfo: 'x+y+text',
      };

      const layout = {
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        margin: { l: 45, r: 15, t: 10, b: 45 },
        xaxis: {
          showgrid: false,
          tickfont: { color: textColor, size: 10 },
        },
        yaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: true,
          zerolinecolor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)',
          tickfont: { color: textColor, size: 10, family: 'monospace' },
          tickprefix: '₹',
        },
      };

      const config = { responsive: true, displayModeBar: false };
      Plotly.newPlot(canvas, [trace], layout, config);
    } catch (err) {
      console.error('Failed to render Exit Reason chart:', err);
    }
  }

  resize() {
    const canvas = this.container?.querySelector('#pnl-exit-reason-canvas');
    if (canvas && this._Plotly && canvas.data) {
      try {
        this._Plotly.Plots.resize(canvas);
      } catch (_) {}
    }
  }
}
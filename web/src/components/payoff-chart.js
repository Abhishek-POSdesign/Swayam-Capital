/**
 * Strategy Payoff Chart Component for Swayam Capital (BUILD-10).
 *
 * Plotly-based payoff chart displaying dual curves (Expiry & T+0),
 * current spot marker, breakeven markers, and risk threshold lines (2σ and Blast Radius).
 */

export class PayoffChartComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this._Plotly = null;
    this.chartData = null;
    this.currentSpot = 24850;
    this.maxLoss = 0;
    this.maxProfit = 0;
    this.breakevens = [];
    this.realisticRisk = 0;
    this._themeListenerAttached = false;
  }

  async init() {
    this.container.innerHTML = `
      <div class="payoff-chart-tile" style="display: flex; flex-direction: column; gap: 8px; background: var(--dl-card); padding: 16px 18px; border-radius: var(--radius-card); border: 1px solid var(--dl-line); height: 100%; min-height: 380px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="eyebrow" style="color: var(--dl-fg-3);">STRATEGY PAYOFF</span>
          <div style="display: flex; align-items: center; gap: 10px; font-size: 0.72rem;">
            <span style="display: flex; align-items: center; gap: 4px; color: var(--accent-sage);">
              <span style="display: inline-block; width: 12px; height: 2px; background: var(--accent-sage);"></span> Expiry
            </span>
            <span style="display: flex; align-items: center; gap: 4px; color: var(--dl-fg-2);">
              <span style="display: inline-block; width: 12px; height: 2px; border-top: 2px dashed var(--dl-fg-2);"></span> T+0
            </span>
          </div>
        </div>

        <div id="payoff-plotly-canvas" style="width: 100%; flex: 1; min-height: 290px;"></div>

        <!-- Legend / Risk Key -->
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; padding-top: 6px; border-top: 1px solid var(--dl-line); font-family: var(--font-mono);">
          <span style="color: var(--accent-amber);">● Spot: ${this.currentSpot.toFixed(1)}</span>
          <span style="color: var(--accent-sage);">Max: +₹${Math.round(this.maxProfit).toLocaleString('en-IN')}</span>
          <span style="color: var(--accent-coral);">Blast: -₹${Math.round(this.maxLoss).toLocaleString('en-IN')}</span>
        </div>
      </div>
    `;

    if (typeof window !== 'undefined' && !this._themeListenerAttached) {
      window.addEventListener('swayam-theme-change', () => this.retheme());
      this._themeListenerAttached = true;
    }
  }

  async updateData({ curveData, currentSpot, maxLoss, maxProfit, breakevens, realisticRisk }) {
    this.chartData = curveData;
    this.currentSpot = currentSpot || this.currentSpot;
    this.maxLoss = Math.abs(maxLoss || 0);
    this.maxProfit = maxProfit || 0;
    this.breakevens = breakevens || [];
    this.realisticRisk = Math.abs(realisticRisk || 0);

    await this.renderPlot();
  }

  async renderPlot() {
    if (typeof window === 'undefined') return;
    if (typeof process !== 'undefined' && process.env?.VITEST) return;

    try {
      if (!this._Plotly) {
        if (typeof window !== 'undefined' && window.Plotly) {
          this._Plotly = window.Plotly;
        } else {
          const m = await import('plotly.js-dist-min');
          this._Plotly = m.default || m;
        }
      }
      const Plotly = this._Plotly;
      const chartDiv = this.container.querySelector('#payoff-plotly-canvas');
      if (!chartDiv) return;

      const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
      const bgColor = isDark ? '#191b21' : '#f8f8f7';
      const textColor = isDark ? '#8b8e9b' : '#6b6e7b';
      const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

      let xVals = [];
      let yExpiry = [];
      let yToday = [];

      if (this.chartData && this.chartData.points) {
        xVals = this.chartData.points.map((p) => p.spot);
        yExpiry = this.chartData.points.map((p) => p.pnl_expiry);
        yToday = this.chartData.points.map((p) => p.pnl_today);
      } else {
        // Fallback placeholder curve around spot
        const s = this.currentSpot || 24850;
        for (let pt = s * 0.96; pt <= s * 1.04; pt += 25) {
          xVals.push(pt);
          const diff = pt - s;
          yExpiry.push(diff > 50 ? 5500 : (diff < -50 ? -3800 : diff * 80));
          yToday.push(diff > 50 ? 3200 : (diff < -50 ? -2400 : diff * 50));
        }
      }

      const expiryTrace = {
        x: xVals,
        y: yExpiry,
        type: 'scatter',
        mode: 'lines',
        name: 'Expiry P&L',
        line: { color: '#86ab92', width: 2.2 },
        hoverinfo: 'x+y',
      };

      const todayTrace = {
        x: xVals,
        y: yToday,
        type: 'scatter',
        mode: 'lines',
        name: 'T+0 P&L',
        line: { color: isDark ? '#ac9fd2' : '#7b6ea8', width: 1.6, dash: 'dot' },
        hoverinfo: 'x+y',
      };

      // Breakeven markers
      const bePoints = this.breakevens.map((be) => ({
        x: [be],
        y: [0],
        type: 'scatter',
        mode: 'markers',
        name: 'Breakeven',
        marker: { color: '#c9a04a', size: 8, symbol: 'circle' },
        hoverinfo: 'x',
      }));

      // Shapes: spot vertical line + horizontal threshold lines
      const shapes = [
        // Zero line
        {
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: 0, y1: 0,
          line: { color: isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)', width: 1 },
        },
        // Spot vertical line
        {
          type: 'line',
          x0: this.currentSpot, x1: this.currentSpot,
          yref: 'paper', y0: 0, y1: 1,
          line: { color: '#c9a04a', width: 1.5, dash: 'dash' },
        },
      ];

      // 2σ Realistic worst-case line (Amber dashed)
      if (this.realisticRisk > 0) {
        shapes.push({
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: -this.realisticRisk, y1: -this.realisticRisk,
          line: { color: '#c9a04a', width: 1.2, dash: 'dash' },
        });
      }

      // Blast radius max loss line (Coral dashed)
      if (this.maxLoss > 0) {
        shapes.push({
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: -this.maxLoss, y1: -this.maxLoss,
          line: { color: '#dd8170', width: 1.2, dash: 'dash' },
        });
      }

      // Max profit line (Sage dashed)
      if (this.maxProfit > 0) {
        shapes.push({
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: this.maxProfit, y1: this.maxProfit,
          line: { color: '#86ab92', width: 1.2, dash: 'dash' },
        });
      }

      const annotations = [
        {
          x: this.currentSpot,
          yref: 'paper',
          y: 0.95,
          text: `Spot ${this.currentSpot.toFixed(0)}`,
          showarrow: false,
          font: { color: '#c9a04a', size: 9, family: 'JetBrains Mono, monospace' },
          bgcolor: bgColor,
          bordercolor: '#c9a04a',
          borderwidth: 1,
        },
      ];

      const layout = {
        margin: { l: 45, r: 15, t: 10, b: 24 },
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        showlegend: false,
        dragmode: false,
        xaxis: {
          showgrid: false,
          zeroline: false,
          tickfont: { color: textColor, size: 8 },
        },
        yaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: false,
          tickfont: { color: textColor, size: 8 },
          tickformat: ',.0f',
        },
        shapes,
        annotations,
      };

      chartDiv.innerHTML = '';
      await Plotly.newPlot(chartDiv, [expiryTrace, todayTrace, ...bePoints], layout, {
        responsive: true,
        displayModeBar: false,
      });
    } catch (e) {
      // Quiet fail if Plotly fails to render
    }
  }

  retheme() {
    this.renderPlot();
  }
}

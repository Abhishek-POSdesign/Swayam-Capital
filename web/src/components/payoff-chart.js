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
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="eyebrow" style="color: var(--dl-fg-3);">STRATEGY PAYOFF PROFILE</span>
          </div>
          <div style="display: flex; align-items: center; gap: 10px; font-size: 0.72rem;">
            <span style="display: flex; align-items: center; gap: 4px; color: var(--accent-sage); font-weight: 600;">
              <span style="display: inline-block; width: 14px; height: 3px; background: var(--accent-sage); border-radius: 2px;"></span> At Expiry
            </span>
            <span style="display: flex; align-items: center; gap: 4px; color: var(--accent-lilac, #ac9fd2); font-weight: 600;">
              <span style="display: inline-block; width: 14px; height: 2px; border-top: 2px dashed var(--accent-lilac, #ac9fd2);"></span> Today (T+0)
            </span>
            <span style="display: flex; align-items: center; gap: 4px; color: var(--accent-amber); font-weight: 600;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--accent-amber);"></span> Breakeven
            </span>
          </div>
        </div>

        <!-- Metric Summary Chips immediately above chart -->
        <div id="payoff-metrics-strip" style="display: flex; gap: 8px; flex-wrap: wrap; font-size: 0.72rem; padding: 4px 0;">
          <span style="padding: 3px 8px; border-radius: 4px; background: var(--accent-sage-tint); color: var(--accent-sage); border: 1px solid rgba(134,171,146,0.3); font-weight: 600;">
            Max Profit: +₹${Math.round(this.maxProfit).toLocaleString('en-IN')}
          </span>
          <span style="padding: 3px 8px; border-radius: 4px; background: var(--accent-coral-tint); color: var(--accent-coral); border: 1px solid rgba(221,129,112,0.3); font-weight: 600;">
            Max Loss: -₹${Math.round(this.maxLoss).toLocaleString('en-IN')}
          </span>
          ${this.breakevens.length > 0 ? `
            <span style="padding: 3px 8px; border-radius: 4px; background: rgba(201,160,74,0.12); color: var(--accent-amber); border: 1px solid rgba(201,160,74,0.3); font-family: var(--font-mono); font-weight: 600;">
              Breakeven: ${this.breakevens.map(b => Math.round(b).toLocaleString('en-IN')).join(' | ')}
            </span>
          ` : ''}
        </div>

        <div id="payoff-plotly-canvas" style="width: 100%; flex: 1; min-height: 290px;"></div>

        <!-- Legend / Risk Key -->
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; padding-top: 6px; border-top: 1px solid var(--dl-line); font-family: var(--font-mono);">
          <span style="color: var(--accent-amber); font-weight: 600;">● Spot: ${this.currentSpot.toFixed(2)}</span>
          <span style="color: var(--dl-fg-3);">Green = Profit Zone · Red = Loss Zone</span>
        </div>
      </div>
    `;

    if (typeof window !== 'undefined' && !this._themeListenerAttached) {
      window.addEventListener('swayam-theme-change', () => this.retheme());
      this._themeListenerAttached = true;
    }

    // Immediately render initial plot
    await this.renderPlot();
  }

  async updateData({ curveData, currentSpot, maxLoss, maxProfit, breakevens, realisticRisk }) {
    this.chartData = curveData;
    this.currentSpot = currentSpot || this.currentSpot;
    this.maxLoss = Math.abs(maxLoss || 0);
    this.maxProfit = maxProfit || 0;
    this.breakevens = breakevens || [];
    this.realisticRisk = Math.abs(realisticRisk || 0);

    // Update metrics strip in DOM
    const strip = this.container.querySelector('#payoff-metrics-strip');
    if (strip) {
      strip.innerHTML = `
        <span style="padding: 3px 8px; border-radius: 4px; background: var(--accent-sage-tint); color: var(--accent-sage); border: 1px solid rgba(134,171,146,0.3); font-weight: 600;">
          Max Profit: +₹${Math.round(this.maxProfit).toLocaleString('en-IN')}
        </span>
        <span style="padding: 3px 8px; border-radius: 4px; background: var(--accent-coral-tint); color: var(--accent-coral); border: 1px solid rgba(221,129,112,0.3); font-weight: 600;">
          Max Loss: -₹${Math.round(this.maxLoss).toLocaleString('en-IN')}
        </span>
        ${this.breakevens.length > 0 ? `
          <span style="padding: 3px 8px; border-radius: 4px; background: rgba(201,160,74,0.12); color: var(--accent-amber); border: 1px solid rgba(201,160,74,0.3); font-family: var(--font-mono); font-weight: 600;">
            Breakeven: ${this.breakevens.map(b => Math.round(b).toLocaleString('en-IN')).join(' | ')}
          </span>
        ` : ''}
      `;
    }

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
      const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';

      let xVals = [];
      let yExpiry = [];
      let yToday = [];

      if (this.chartData && this.chartData.points && this.chartData.points.length > 0) {
        xVals = this.chartData.points.map((p) => p.spot);
        yExpiry = this.chartData.points.map((p) => p.pnl_expiry);
        yToday = this.chartData.points.map((p) => p.pnl_today);
      } else {
        // Fallback default Bear Put curve around current spot
        const s = this.currentSpot || 24850;
        for (let pt = s - 600; pt <= s + 600; pt += 25) {
          xVals.push(pt);
          // Bear put spread (Long 24900 PE @ 116, Short 24700 PE @ 59 -> Net Debit 57 pts = ₹4275)
          const longPut = Math.max(0, 24900 - pt) - 116.62;
          const shortPut = Math.max(0, 24700 - pt) - 59.13;
          const pnlExpiry = (longPut - shortPut) * 75;
          yExpiry.push(Math.round(pnlExpiry));
          // T+0 smooth transition
          const diff = (24850 - pt) / 600;
          yToday.push(Math.round(pnlExpiry * 0.45 + diff * 1500));
        }
      }

      // Shaded green area for positive profit zone
      const profitShadeTrace = {
        x: xVals,
        y: yExpiry.map((y) => (y > 0 ? y : 0)),
        type: 'scatter',
        mode: 'lines',
        line: { width: 0, color: 'transparent' },
        fill: 'tozeroy',
        fillcolor: isDark ? 'rgba(134, 171, 146, 0.16)' : 'rgba(134, 171, 146, 0.22)',
        hoverinfo: 'none',
        showlegend: false,
      };

      // Shaded red area for negative loss zone
      const lossShadeTrace = {
        x: xVals,
        y: yExpiry.map((y) => (y < 0 ? y : 0)),
        type: 'scatter',
        mode: 'lines',
        line: { width: 0, color: 'transparent' },
        fill: 'tozeroy',
        fillcolor: isDark ? 'rgba(221, 129, 112, 0.16)' : 'rgba(221, 129, 112, 0.22)',
        hoverinfo: 'none',
        showlegend: false,
      };

      const expiryTrace = {
        x: xVals,
        y: yExpiry,
        type: 'scatter',
        mode: 'lines',
        name: 'Expiry P&L',
        line: { color: '#86ab92', width: 2.6 },
        hovertemplate: 'Spot: %{x:,.0f}<br>Expiry P&L: ₹%{y:,.0f}<extra></extra>',
      };

      const todayTrace = {
        x: xVals,
        y: yToday,
        type: 'scatter',
        mode: 'lines',
        name: 'T+0 (Today)',
        line: { color: isDark ? '#ac9fd2' : '#7b6ea8', width: 1.8, dash: 'dot' },
        hovertemplate: 'Spot: %{x:,.0f}<br>T+0 P&L: ₹%{y:,.0f}<extra></extra>',
      };

      // Breakeven markers
      const bePoints = this.breakevens.map((be) => ({
        x: [be],
        y: [0],
        type: 'scatter',
        mode: 'markers+text',
        name: 'Breakeven',
        text: [`BE ${Math.round(be).toLocaleString('en-IN')}`],
        textposition: 'top center',
        textfont: { size: 9, color: '#c9a04a', family: 'JetBrains Mono, monospace' },
        marker: { color: '#c9a04a', size: 9, symbol: 'diamond' },
        hovertemplate: 'Breakeven: %{x:,.0f}<extra></extra>',
      }));

      // Shapes: Zero baseline + Spot vertical line + 2σ / Max Loss
      const shapes = [
        // Solid Zero line
        {
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: 0, y1: 0,
          line: { color: isDark ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.28)', width: 1.2 },
        },
        // Spot vertical line
        {
          type: 'line',
          x0: this.currentSpot, x1: this.currentSpot,
          yref: 'paper', y0: 0, y1: 1,
          line: { color: '#c9a04a', width: 1.6, dash: 'dash' },
        },
      ];

      // 2σ Realistic worst-case line
      if (this.realisticRisk > 0) {
        shapes.push({
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: -this.realisticRisk, y1: -this.realisticRisk,
          line: { color: '#c9a04a', width: 1.2, dash: 'dot' },
        });
      }

      // Max profit horizontal line
      if (this.maxProfit > 0) {
        shapes.push({
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: this.maxProfit, y1: this.maxProfit,
          line: { color: '#86ab92', width: 1.0, dash: 'dot' },
        });
      }

      const annotations = [
        {
          x: this.currentSpot,
          yref: 'paper',
          y: 0.98,
          text: `● Spot: ${this.currentSpot.toFixed(1)}`,
          showarrow: false,
          font: { color: '#c9a04a', size: 9, family: 'JetBrains Mono, monospace', weight: 700 },
          bgcolor: isDark ? 'rgba(25, 27, 33, 0.92)' : 'rgba(255, 255, 255, 0.92)',
          bordercolor: '#c9a04a',
          borderwidth: 1,
          borderpad: 3,
        },
      ];

      const layout = {
        margin: { l: 55, r: 20, t: 15, b: 30 },
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        showlegend: false,
        dragmode: false,
        xaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: false,
          tickfont: { color: textColor, size: 9, family: 'JetBrains Mono, monospace' },
          tickformat: ',.0f',
        },
        yaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: false,
          tickfont: { color: textColor, size: 9, family: 'JetBrains Mono, monospace' },
          tickformat: '+,.0f',
        },
        shapes,
        annotations,
      };

      chartDiv.innerHTML = '';
      await Plotly.newPlot(
        chartDiv,
        [profitShadeTrace, lossShadeTrace, expiryTrace, todayTrace, ...bePoints],
        layout,
        {
          responsive: true,
          displayModeBar: false,
        }
      );
    } catch (e) {
      // Quiet fail if Plotly fails to render
    }
  }

  retheme() {
    this.renderPlot();
  }
}

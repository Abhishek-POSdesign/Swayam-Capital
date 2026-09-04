/**
 * NIFTY Chart Card Component for Swayam Capital (BUILD-9-FIXES-A).
 * Full-width (span-12). Interactive timeframe tabs fetch real candle data.
 * Uses Plotly.react() (no flicker) for tab switches.
 * Shows loading spinner during fetch. Support/resistance re-anchors per timeframe.
 */

import { api } from '../api.js';

export class NiftyChartCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.activeTimeframe = '1D';
    this._plotlyLoaded = false;
    this._Plotly = null;
    this._isLoading = false;
  }

  async render(candleData = null) {
    this.container.innerHTML = `
      <div class="tile nifty-chart-tile span-12" style="display: flex; flex-direction: column; height: 100%; min-height: 240px; gap: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="eyebrow" style="color: var(--dl-fg-3);">NIFTY 50 · CHART</span>
            <span class="mono-nums" style="font-size: 0.8rem; font-weight: 600; color: var(--accent-sage);">24,842.65</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div id="nifty-chart-spinner" style="display: none; width: 14px; height: 14px; border: 2px solid var(--dl-track); border-top-color: var(--accent-sage); border-radius: 50%; animation: spin 0.6s linear infinite;"></div>
            <div class="chart-timeframe-tabs" style="display: flex; gap: 4px;">
              <button type="button" class="tab-tf" id="tab-tf-15m" data-tf="15m" style="padding: 3px 9px; border-radius: 6px; font-size: 0.72rem; border: 1px solid transparent; background: transparent; color: var(--dl-fg-3); cursor: pointer;">15m</button>
              <button type="button" class="tab-tf" id="tab-tf-1h" data-tf="1h" style="padding: 3px 9px; border-radius: 6px; font-size: 0.72rem; border: 1px solid transparent; background: transparent; color: var(--dl-fg-3); cursor: pointer;">1h</button>
              <button type="button" class="tab-tf active" id="tab-tf-1D" data-tf="1D" style="padding: 3px 9px; border-radius: 6px; font-size: 0.72rem; border: 1px solid rgba(134,171,146,0.3); background: var(--accent-sage-tint); color: var(--accent-sage); font-weight: 600; cursor: pointer;">1D</button>
            </div>

          </div>
        </div>

        <div id="nifty-plotly-canvas" style="width: 100%; flex: 1; min-height: 190px; border-radius: 8px; overflow: hidden;"></div>
      </div>
    `;

    // Add spinner CSS if not already present
    if (!document.getElementById('nifty-chart-spinner-style')) {
      const style = document.createElement('style');
      style.id = 'nifty-chart-spinner-style';
      style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
      document.head.appendChild(style);
    }

    this.attachTabs();
    await this.renderPlot(candleData);
  }

  attachTabs() {
    let tabs = [];
    const t15m = this.container.querySelector('#tab-tf-15m');
    const t1h = this.container.querySelector('#tab-tf-1h');
    const t1D = this.container.querySelector('#tab-tf-1D');
    if (t15m || t1h || t1D) {
      tabs = [t15m, t1h, t1D].filter(Boolean);
    } else if (this.container.querySelectorAll) {
      const q = this.container.querySelectorAll('.tab-tf');
      if (q && q.forEach) q.forEach(b => tabs.push(b));
    }
    if (!tabs.length) return;

    tabs.forEach(btn => {
      if (btn.addEventListener) {

        btn.addEventListener('click', async () => {
          if (this._isLoading) return;
          const tf = btn.getAttribute('data-tf');
          if (tf === this.activeTimeframe) return;

          // Update active tab styling
          tabs.forEach(b => {
            if (b.classList) b.classList.remove('active');
            b.style.background = 'transparent';
            b.style.color = 'var(--dl-fg-3)';
            b.style.borderColor = 'transparent';
            b.style.fontWeight = 'normal';
          });
          if (btn.classList) btn.classList.add('active');
          btn.style.background = 'var(--accent-sage-tint)';
          btn.style.color = 'var(--accent-sage)';
          btn.style.borderColor = 'rgba(134,171,146,0.3)';
          btn.style.fontWeight = '600';

          this.activeTimeframe = tf;
          await this.loadAndRefreshChart(tf);
        });
      }
    });
  }

  /** Fetch candle data from API and update chart via Plotly.react() */
  async loadAndRefreshChart(timeframe) {
    this._isLoading = true;
    const spinner = this.container.querySelector('#nifty-chart-spinner');
    if (spinner) spinner.style.display = 'block';

    try {
      const apiTf = timeframe.toLowerCase(); // 15m, 1h, 1d
      const data = await api.getNiftyCandles(apiTf);
      await this.renderPlot(data);
    } catch (err) {
      console.warn('NIFTY chart fetch failed, keeping current chart:', err);
      const chartDiv = this.container.querySelector('#nifty-plotly-canvas');
      if (chartDiv) {
        const banner = document.createElement('div');
        banner.style.cssText = 'position: absolute; top: 0; left: 0; right: 0; background: var(--accent-coral-tint); color: var(--accent-coral); font-size: 0.75rem; padding: 4px 10px; border-radius: 8px 8px 0 0;';
        banner.textContent = `Chart failed to load: ${err.message || 'Service unavailable'}`;
        chartDiv.style.position = 'relative';
        chartDiv.appendChild(banner);
        setTimeout(() => banner.remove(), 5000);
      }
    } finally {
      this._isLoading = false;
      if (spinner) spinner.style.display = 'none';
    }
  }

  async renderPlot(candleData) {
    if (!this.container.querySelector) return;
    const chartDiv = this.container.querySelector('#nifty-plotly-canvas');
    if (!chartDiv) return;

    // In headless / node test environments, render fallback directly
    if (typeof window === 'undefined' || typeof self === 'undefined') {
      this.renderSvgFallback(chartDiv);
      return;
    }

    try {
      // Lazy-load Plotly once
      if (!this._Plotly) {
        const plotlyModule = await import('plotly.js-dist-min');
        this._Plotly = plotlyModule.default || plotlyModule;
      }
      const Plotly = this._Plotly;

      // Read CSS vars for theme-aware chart colors
      const style = getComputedStyle(document.documentElement);
      const bgColor = style.getPropertyValue('--plotly-bg').trim() || '#191b21';
      const gridColor = style.getPropertyValue('--plotly-grid').trim() || '#272a33';
      const textColor = style.getPropertyValue('--dl-fg-3').trim() || '#8a91a0';

      let dates, open, high, low, close, ema20, supportLevels, resistanceLevels;

      if (candleData && candleData.dates && candleData.dates.length > 0) {
        // Real API data
        dates = candleData.dates;
        open = candleData.open;
        high = candleData.high;
        low = candleData.low;
        close = candleData.close;
        ema20 = candleData.ema20;
        supportLevels = candleData.support_levels || [];
        resistanceLevels = candleData.resistance_levels || [];
      } else {
        // Placeholder data while waiting for first API load
        dates = [];
        open = []; high = []; low = []; close = []; ema20 = [];
        supportLevels = [{ price: 24700, label: 'S: 24,700' }];
        resistanceLevels = [{ price: 24900, label: 'R: 24,900' }];

        let cur = 24600;
        for (let i = 30; i >= 1; i--) {
          const d = new Date();
          d.setDate(d.getDate() - i);
          dates.push(d.toISOString().split('T')[0]);
          const change = (Math.sin(i * 0.7) * 90) + (i < 10 ? 30 : -10);
          const o = cur;
          const c = cur + change;
          const h = Math.max(o, c) + Math.abs(Math.cos(i) * 60) + 20;
          const l = Math.min(o, c) - Math.abs(Math.sin(i) * 50) - 15;
          open.push(o); high.push(h); low.push(l); close.push(c);
          ema20.push(24650 + (30 - i) * 7);
          cur = c;
        }
      }

      const candleTrace = {
        x: dates, open, high, low, close,
        type: 'candlestick',
        name: 'NIFTY 50',
        increasing: { line: { color: '#86ab92', width: 1 }, fillcolor: '#86ab92' },
        decreasing: { line: { color: '#dd8170', width: 1 }, fillcolor: '#dd8170' },
        showlegend: false,
      };

      const emaTrace = {
        x: dates,
        y: ema20.filter(v => v !== null),
        type: 'scatter',
        mode: 'lines',
        name: '20 EMA',
        line: { color: '#86ab92', width: 1.5 },
        hoverinfo: 'none',
        showlegend: false,
      };

      // Build shapes (support = amber dashed, resistance = coral dashed)
      const shapes = supportLevels.map(s => ({
        type: 'line', xref: 'paper', x0: 0, x1: 1,
        y0: s.price, y1: s.price,
        line: { color: '#c9a04a', width: 1.5, dash: 'dash' },
      })).concat(resistanceLevels.map(r => ({
        type: 'line', xref: 'paper', x0: 0, x1: 1,
        y0: r.price, y1: r.price,
        line: { color: '#dd8170', width: 1.5, dash: 'dash' },
      })));

      const annotations = supportLevels.map(s => ({
        xref: 'paper', x: 0.99, y: s.price,
        text: s.label, showarrow: false,
        font: { color: '#c9a04a', size: 10, family: 'JetBrains Mono, monospace' },
        bgcolor: bgColor, bordercolor: '#c9a04a', borderwidth: 1, borderpad: 2,
        xanchor: 'right',
      })).concat(resistanceLevels.map(r => ({
        xref: 'paper', x: 0.99, y: r.price,
        text: r.label, showarrow: false,
        font: { color: '#dd8170', size: 10, family: 'JetBrains Mono, monospace' },
        bgcolor: bgColor, bordercolor: '#dd8170', borderwidth: 1, borderpad: 2,
        xanchor: 'right',
      })));

      const layout = {
        dragmode: false,
        margin: { l: 36, r: 60, t: 8, b: 24 },
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        showlegend: false,
        xaxis: {
          rangeslider: { visible: false },
          showgrid: false,
          zeroline: false,
          tickfont: { color: textColor, size: 9 },
        },
        yaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: false,
          tickfont: { color: textColor, size: 9 },
          side: 'right',
        },
        shapes,
        annotations,
      };

      const config = { responsive: true, displayModeBar: false };

      // Use react() for smooth tab switching (no flicker), newPlot on first render
      if (this._plotlyLoaded && chartDiv._plotlyLoaded) {
        await Plotly.react(chartDiv, [candleTrace, emaTrace], layout, config);
      } else {
        await Plotly.newPlot(chartDiv, [candleTrace, emaTrace], layout, config);
        chartDiv._plotlyLoaded = true;
        this._plotlyLoaded = true;
      }
    } catch {
      this.renderSvgFallback(chartDiv);
    }
  }

  renderSvgFallback(chartDiv) {
    chartDiv.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: center; height: 100%; background: var(--dl-card-2); border-radius: 8px;">
        <span style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--accent-sage);">
          [ NIFTY Candlestick Chart · 20-EMA · S/R Levels ]
        </span>
      </div>
    `;
  }
}

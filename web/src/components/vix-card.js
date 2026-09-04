/**
 * India VIX Card Component for Swayam Capital (BUILD-9-FIXES-A).
 * Full-width span-12 row: three-panel layout.
 *   LEFT:   Current VIX value + regime chip
 *   CENTER: 60-day Plotly line chart (sage color)
 *   RIGHT:  1-year historical percentile band with triangle marker
 */

import { api } from '../api.js';

export class VixCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this._Plotly = null;
  }

  render(vixData = null) {
    const rawCurrent = vixData?.current ?? vixData?.value;
    const defaultVals = [13.4,13.2,13.1,13.5,13.0,12.9,12.8,13.1,12.7,12.6,12.9,13.2,13.0,12.8,12.7,12.9,13.1,12.9,12.8,12.85];
    const data = {
      current: typeof rawCurrent === 'number' ? rawCurrent : 12.85,
      regime: vixData?.regime || 'Low Vol',
      percentile: vixData?.percentile ?? 8,
      percentile_label: vixData?.percentile_label || `${(typeof rawCurrent === 'number' ? rawCurrent : 12.85).toFixed(2)} is in the 8th percentile of last 365 days · Historically calm`,
      year_low: vixData?.year_low ?? 10.2,
      year_high: vixData?.year_high ?? 28.5,
      p10: vixData?.p10 ?? 11.0,
      p25: vixData?.p25 ?? 13.5,
      p50: vixData?.p50 ?? 16.8,
      p75: vixData?.p75 ?? 20.2,
      p90: vixData?.p90 ?? 24.5,
      history_60d: {
        dates: vixData?.history_60d?.dates || [],
        values: vixData?.history_60d?.values || vixData?.sparkline_20d || defaultVals,
      },
    };
    this.lastData = data;

    if (typeof window !== 'undefined' && !this._themeListenerAttached) {
      window.addEventListener('swayam-theme-change', () => {
        if (this.lastData?.history_60d) {
          this._tryRenderPlotly(this.lastData.history_60d);
        }
      });
      this._themeListenerAttached = true;
    }

    // Regime → color mapping
    const regimeKey = (data.regime || '').toLowerCase();
    let color = 'var(--accent-sage)';
    let tint = 'var(--accent-sage-tint)';
    if (regimeKey.includes('spike')) {
      color = 'var(--accent-coral)';
      tint = 'var(--accent-coral-tint)';
    } else if (regimeKey.includes('elevated')) {
      color = 'var(--accent-amber)';
      tint = 'var(--accent-amber-tint)';
    } else if (regimeKey.includes('normal')) {
      color = 'var(--accent-blue)';
      tint = 'var(--accent-blue-tint)';
    }

    // Percentile bar: compute triangle position %
    const pct = Math.min(100, Math.max(0, data.percentile || 0));
    const pctLabel = data.percentile_label || `${data.current} · ${pct}th percentile`;

    // 60-day sparkline (SVG fallback if Plotly not loaded)
    const sparkSvg = this._buildSparkline(data.history_60d?.values || []);

    this.container.innerHTML = `
      <div class="tile vix-tile span-12" style="display: flex; align-items: stretch; gap: 0; padding: 0; min-height: 130px;">

        <!-- LEFT: Value + Regime -->
        <div style="flex: 0 0 200px; padding: 16px 20px; display: flex; flex-direction: column; justify-content: center; gap: 8px; border-right: 1px solid var(--dl-line);">
          <span class="eyebrow" style="color: var(--dl-fg-3);">INDIA VIX · 20-DAY</span>
          <div class="fig-xl" style="font-size: 2.4rem; font-family: var(--font-serif); font-weight: 700; line-height: 1; color: var(--dl-fg);">
            ${(data.current || 0).toFixed(2)}
          </div>
          <div>
            <span style="font-size: 0.72rem; font-weight: 700; padding: 3px 10px; border-radius: 999px; background: ${tint}; color: ${color}; border: 1px solid ${color}33; letter-spacing: 0.04em;">
              ${data.regime || 'Low Vol'}
            </span>
          </div>
        </div>

        <!-- CENTER: 60-day chart -->
        <div style="flex: 1; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px; border-right: 1px solid var(--dl-line); min-width: 0;">
          <span class="eyebrow" style="color: var(--dl-fg-3); font-size: 0.65rem;">60-DAY HISTORY</span>
          <div id="vix-plotly-canvas" style="width: 100%; flex: 1; min-height: 80px;">
            ${sparkSvg}
          </div>
        </div>

        <!-- RIGHT: Percentile band -->
        <div style="flex: 0 0 280px; padding: 14px 18px; display: flex; flex-direction: column; justify-content: center; gap: 10px;">
          <span class="eyebrow" style="color: var(--dl-fg-3); font-size: 0.65rem;">1-YEAR PERCENTILE</span>

          <!-- Horizontal bar with scale marks -->
          <div style="position: relative; height: 28px;">
            <!-- Track bar -->
            <div style="position: absolute; top: 50%; left: 0; right: 0; height: 6px; transform: translateY(-50%); background: var(--dl-track); border-radius: 3px; overflow: visible;">
              <!-- P10-P90 colored zone -->
              <div style="position: absolute; left: 10%; right: 10%; top: 0; bottom: 0; background: var(--dl-card-2); border-radius: 2px;"></div>
            </div>
            <!-- Percentile tick marks -->
            ${[10, 25, 50, 75, 90].map(p => `
              <div style="position: absolute; top: 0; bottom: 0; left: ${p}%; transform: translateX(-50%); display: flex; flex-direction: column; align-items: center; justify-content: flex-end;">
                <div style="width: 1px; height: 6px; background: var(--dl-fg-3); margin-bottom: 2px;"></div>
                <span style="font-family: var(--font-mono); font-size: 0.58rem; color: var(--dl-fg-3); white-space: nowrap;">${p}</span>
              </div>
            `).join('')}
            <!-- Current value triangle marker -->
            <div style="position: absolute; top: 2px; left: ${pct}%; transform: translateX(-50%);">
              <svg width="10" height="8" viewBox="0 0 10 8" style="overflow: visible;">
                <polygon points="5,8 0,0 10,0" fill="${color}" />
              </svg>
            </div>
          </div>

          <!-- Label -->
          <div style="font-family: var(--font-mono); font-size: 0.71rem; color: var(--dl-fg-2); line-height: 1.4;">
            ${pctLabel}
          </div>
          <div style="display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 0.65rem; color: var(--dl-fg-3);">
            <span>Low ${data.year_low ?? '—'}</span>
            <span>High ${data.year_high ?? '—'}</span>
          </div>
        </div>
      </div>
    `;

    // Try to upgrade center chart to Plotly
    this._tryRenderPlotly(data.history_60d);
  }

  _buildSparkline(points) {
    if (!points || points.length < 2) return '<div style="height:80px; display:flex; align-items:center; justify-content:center; color:var(--dl-fg-3); font-size:0.75rem;">No data</div>';
    const min = Math.min(...points) - 0.2;
    const max = Math.max(...points) + 0.2;
    const range = (max - min) || 1;
    const W = 400, H = 80;

    const coords = points.map((p, i) => {
      const x = (i / (points.length - 1)) * W;
      const y = H - ((p - min) / range) * (H - 8) - 4;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    return `
      <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="overflow: visible;">
        <polyline fill="none" stroke="var(--accent-sage)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${coords.join(' ')}" />
        <circle cx="${coords[coords.length - 1].split(',')[0]}" cy="${coords[coords.length - 1].split(',')[1]}" r="3" fill="var(--accent-sage)" />
      </svg>
    `;
  }

  async _tryRenderPlotly(history60d) {
    if (!history60d || !history60d.values || history60d.values.length < 5) return;
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
      const chartDiv = this.container.querySelector('#vix-plotly-canvas');
      if (!chartDiv) return;

      const style = getComputedStyle(document.documentElement);
      const bgColor = style.getPropertyValue('--plotly-bg').trim() || '#191b21';
      const gridColor = style.getPropertyValue('--plotly-grid').trim() || '#272a33';
      const textColor = style.getPropertyValue('--dl-fg-3').trim() || '#8a91a0';

      const dates = history60d.dates && history60d.dates.length ? history60d.dates : history60d.values.map((_, i) => i);
      const vals = (history60d.values || []).map(Number);
      const minVal = Math.min(...vals);
      const maxVal = Math.max(...vals);
      const range = (maxVal - minVal) || 1.0;
      const pad = Math.max(range * 0.10, 0.35);

      const lineTrace = {
        x: dates,
        y: vals,
        type: 'scatter',
        mode: 'lines',
        line: { color: '#86ab92', width: 2 },
        hoverinfo: 'y+x',
        showlegend: false,
      };

      // Identify 3 highest and 3 lowest points for regime visual guidance
      const indexed = vals.map((v, i) => ({ val: v, idx: i }));
      indexed.sort((a, b) => a.val - b.val);
      const lowest3 = indexed.slice(0, Math.min(3, indexed.length));
      const highest3 = indexed.slice(-Math.min(3, indexed.length));

      const highMarkerTrace = {
        x: highest3.map((item) => dates[item.idx]),
        y: highest3.map((item) => item.val),
        type: 'scatter',
        mode: 'markers',
        marker: { color: '#dd8170', size: 5, symbol: 'circle' },
        hoverinfo: 'y',
        name: 'High',
        showlegend: false,
      };

      const lowMarkerTrace = {
        x: lowest3.map((item) => dates[item.idx]),
        y: lowest3.map((item) => item.val),
        type: 'scatter',
        mode: 'markers',
        marker: { color: '#86ab92', size: 5, symbol: 'circle' },
        hoverinfo: 'y',
        name: 'Low',
        showlegend: false,
      };

      const shapes = [];
      const annotations = [];
      const medianVal = this.lastData?.p50 || (vals.slice().sort((a, b) => a - b)[Math.floor(vals.length / 2)]);
      if (medianVal) {
        shapes.push({
          type: 'line',
          xref: 'paper',
          x0: 0,
          x1: 1,
          yref: 'y',
          y0: medianVal,
          y1: medianVal,
          line: {
            color: 'rgba(138, 145, 160, 0.4)',
            width: 1,
            dash: 'dash',
          },
        });
        annotations.push({
          xref: 'paper',
          x: 0.99,
          yref: 'y',
          y: medianVal,
          text: `1y median ${Number(medianVal).toFixed(1)}`,
          showarrow: false,
          xanchor: 'right',
          yanchor: 'bottom',
          font: { color: textColor, size: 8, family: 'var(--font-mono)' },
        });
      }

      const layout = {
        margin: { l: 28, r: 8, t: 8, b: 20 },
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        showlegend: false,
        dragmode: false,
        xaxis: {
          showgrid: false,
          zeroline: false,
          tickfont: { color: textColor, size: 8 },
          showticklabels: true,
        },
        yaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: false,
          tickfont: { color: textColor, size: 8 },
          autorange: false,
          range: [Math.max(0, minVal - pad), maxVal + pad],
        },
        shapes,
        annotations,
      };

      chartDiv.innerHTML = '';
      await Plotly.newPlot(chartDiv, [lineTrace, highMarkerTrace, lowMarkerTrace], layout, { responsive: true, displayModeBar: false });
    } catch (e) {
      // SVG fallback already rendered — silent fail
    }
  }
}

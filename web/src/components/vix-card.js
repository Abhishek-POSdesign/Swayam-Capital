/**
 * India VIX Card — compact (Swayam Capital, Strategy Builder v2 re-skin).
 *
 * One compact card, ~half the old height: current VIX + day change + regime chip on the left,
 * a 1-year percentile band in the middle, and a 60-day sparkline on the right.
 *
 * No-fake-numbers law: every figure is real-from-the-VIX-history or shows '—'. The day change is
 * COMPUTED from the real 60-day series (last two closes) — the API carries no change field, so we
 * never invent one. If there is no real data, the card renders an explicit "unavailable" state
 * instead of any placeholder value.
 */

export class VixCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  _regimeColors(regime) {
    const key = (regime || '').toLowerCase();
    if (key.includes('spike')) return { color: 'var(--accent-coral)', tint: 'var(--accent-coral-tint)' };
    if (key.includes('elevated')) return { color: 'var(--accent-amber)', tint: 'var(--accent-amber-tint)' };
    if (key.includes('normal')) return { color: 'var(--accent-blue)', tint: 'var(--accent-blue-tint)' };
    return { color: 'var(--accent-sage)', tint: 'var(--accent-sage-tint)' }; // Low Vol / default
  }

  render(vixData = null) {
    const current = typeof (vixData?.current ?? vixData?.value) === 'number'
      ? (vixData.current ?? vixData.value)
      : null;

    if (current == null) {
      // No real value → honest unavailable state, never a placeholder number.
      this.renderUnavailable();
      return;
    }

    // Real 60-day series (real backend shape or the simplified sparkline shape).
    const series = (vixData?.history_60d?.values?.length
      ? vixData.history_60d.values
      : (vixData?.sparkline_20d || []))
      .map(Number)
      .filter((v) => !isNaN(v));

    // Day change — computed from the real series (API has no change field). '—' if we can't.
    let changeHtml = `<span style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--dl-fg-3);">—</span>`;
    if (series.length >= 2) {
      const prev = series[series.length - 2];
      const chg = current - prev;
      const chgPct = prev ? (chg / prev) * 100 : 0;
      // Rising VIX = rising fear → coral; falling VIX = calming → sage.
      const c = chg > 0 ? 'var(--accent-coral)' : chg < 0 ? 'var(--accent-sage)' : 'var(--dl-fg-3)';
      const arrow = chg > 0 ? '▲' : chg < 0 ? '▼' : '■';
      changeHtml = `<span style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; color: ${c};">${arrow} ${chg >= 0 ? '+' : ''}${chg.toFixed(2)} (${chgPct >= 0 ? '+' : ''}${chgPct.toFixed(1)}%)</span>`;
    }

    const regime = vixData?.regime || null;
    const { color, tint } = this._regimeColors(regime);
    const pct = typeof vixData?.percentile === 'number' ? Math.min(100, Math.max(0, vixData.percentile)) : null;
    const p50 = typeof vixData?.p50 === 'number' ? vixData.p50 : null;
    const yearLow = typeof vixData?.year_low === 'number' ? vixData.year_low : null;
    const yearHigh = typeof vixData?.year_high === 'number' ? vixData.year_high : null;

    const regimeChip = regime
      ? `<span style="width: fit-content; font-size: 0.64rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; padding: 2px 9px; border-radius: 999px; background: ${tint}; color: ${color};">${regime}${pct != null ? ` · ${Math.round(pct)}th pctl` : ''}</span>`
      : '';

    // Middle: 1-year percentile band (only when we have a real percentile + range).
    let bandHtml = '';
    if (pct != null && yearLow != null && yearHigh != null) {
      const caption = `${Math.round(pct)}th percentile of the last year${p50 != null ? ` · median ${p50.toFixed(1)}` : ''}`;
      bandHtml = `
        <div style="display: flex; flex-direction: column; gap: 6px; min-width: 0;">
          <div style="display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 0.66rem; color: var(--dl-fg-3);">
            <span>${yearLow.toFixed(1)}</span><span>1-year range</span><span>${yearHigh.toFixed(1)}</span>
          </div>
          <div style="position: relative; height: 10px;">
            <div style="position: absolute; top: 1px; left: 0; right: 0; height: 8px; border-radius: 4px; background: var(--dl-track);"></div>
            <div style="position: absolute; top: 0; left: ${pct}%; transform: translateX(-50%); width: 3px; height: 10px; border-radius: 2px; background: ${color};"></div>
          </div>
          <div style="font-size: 0.7rem; color: var(--dl-fg-2); font-family: var(--font-mono);">${caption}</div>
        </div>`;
    } else {
      bandHtml = `<div style="font-size: 0.7rem; color: var(--dl-fg-3); font-family: var(--font-mono); align-self: center;">1-year percentile — unavailable</div>`;
    }

    // Right: 60-day sparkline (real values only).
    const sparkHtml = series.length >= 2
      ? `<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 3px;">
           <span class="eyebrow" style="color: var(--dl-fg-3); font-size: 0.6rem;">60-DAY</span>
           ${this._buildSparkline(series, color)}
         </div>`
      : `<div style="align-self: center; font-size: 0.68rem; color: var(--dl-fg-3);">60-day — n/a</div>`;

    this.container.innerHTML = `
      <div class="tile vix-tile span-12" style="display: grid; grid-template-columns: auto 1fr auto; gap: 22px; align-items: center; padding: 14px 20px; min-height: 74px;">
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <span class="eyebrow" style="color: var(--dl-fg-3);">INDIA VIX</span>
          <div style="display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap;">
            <span style="font-family: var(--font-serif); font-weight: 700; font-size: 2.0rem; line-height: 1; color: var(--dl-fg);">${current.toFixed(2)}</span>
            ${changeHtml}
          </div>
          ${regimeChip}
        </div>
        ${bandHtml}
        ${sparkHtml}
      </div>
    `;
  }

  renderUnavailable(message) {
    this.container.innerHTML = `
      <div class="tile vix-tile span-12" style="display: flex; align-items: center; gap: 16px; padding: 14px 20px; min-height: 74px;">
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <span class="eyebrow" style="color: var(--dl-fg-3);">INDIA VIX</span>
          <span style="font-family: var(--font-serif); font-weight: 700; font-size: 2.0rem; line-height: 1; color: var(--dl-fg-3);">—</span>
        </div>
        <div style="font-size: 0.76rem; color: var(--dl-fg-3); font-family: var(--font-mono);">
          ${message || 'VIX history unavailable — not yet ingested.'}
        </div>
      </div>
    `;
  }

  _buildSparkline(points, color = 'var(--accent-sage)') {
    if (!points || points.length < 2) return '';
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min || 1;
    const W = 130, H = 40;
    const coords = points.map((p, i) => {
      const x = (i / (points.length - 1)) * W;
      const y = H - ((p - min) / range) * (H - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const [lastX, lastY] = coords[coords.length - 1].split(',');
    return `
      <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-label="VIX 60-day sparkline">
        <polyline fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${coords.join(' ')}" />
        <circle cx="${lastX}" cy="${lastY}" r="2.6" fill="${color}" />
      </svg>
    `;
  }
}

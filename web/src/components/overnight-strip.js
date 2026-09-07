/**
 * Overnight Global Strip Component for Swayam Capital (BUILD-9-FIXES-A).
 * BIG numbers — 1.5rem JetBrains Mono 700 — readable at a glance.
 * Total strip height ~72px with cell padding 12px horizontal.
 */

export class OvernightStripComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(overnightData = null) {
    // No fabricated defaults. If no real overnight-global feed is wired, render an honest
    // "not connected" state — never invented index levels. (This component is currently
    // unused on the home page for exactly this reason: FYERS does not provide US indices/Brent.)
    if (!overnightData || Object.keys(overnightData).length === 0) {
      this.container.innerHTML = `
        <div class="tile overnight-strip-tile span-12" style="display:flex; align-items:center; gap:8px; padding:14px 16px; min-height:56px; color:var(--dl-fg-3); font-size:0.8rem;">
          <span>🌐</span><span>Overnight global feed not connected — no live data source.</span>
        </div>`;
      return;
    }
    const data = overnightData;

    const cellsHtml = Object.entries(data).map(([ticker, info], idx) => {
      let deltaColor = 'var(--dl-fg-2)';
      if (info.neutral) {
        deltaColor = 'var(--accent-amber)';
      } else if (info.positive) {
        deltaColor = 'var(--accent-sage)';
      } else if (info.positive === false) {
        deltaColor = 'var(--accent-coral)';
      }

      const borderLeft = idx > 0 ? 'border-left: 1px solid var(--dl-line-2);' : '';

      return `
        <div class="global-ticker-cell" style="flex: 1 0 auto; min-width: 135px; padding: 10px 16px; ${borderLeft} display: flex; flex-direction: column; gap: 4px;">
          <span style="font-family: var(--font-sans); font-size: 0.70rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--dl-fg-3);">
            ${ticker}
          </span>
          <div style="display: flex; align-items: baseline; gap: 8px; flex-wrap: nowrap;">
            <span class="mono-nums" style="font-size: 1.35rem; font-weight: 700; color: var(--dl-fg); line-height: 1; letter-spacing: -0.01em; white-space: nowrap;">
              ${info.value}
            </span>
            <span class="mono-nums" style="font-size: 0.86rem; font-weight: 600; color: ${deltaColor}; white-space: nowrap;">
              ${info.pct}
            </span>
          </div>
        </div>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="tile overnight-strip-tile span-12" style="display: flex; align-items: stretch; justify-content: space-between; padding: 0; overflow-x: auto; -webkit-overflow-scrolling: touch; min-height: 72px;">
        ${cellsHtml}
      </div>
    `;
  }
}

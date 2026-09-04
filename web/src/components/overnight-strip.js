/**
 * Overnight Global Strip Component for Swayam Capital (BUILD-9).
 * Renders 5 global macro tickers side-by-side with tabular monospace numbers and semantic deltas.
 */

export class OvernightStripComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(overnightData = null) {
    const data = overnightData || {
      DJI: { value: '45,203.47', pct: '+0.42%', positive: true, neutral: false },
      'S&P 500': { value: '6,124.11', pct: '+0.31%', positive: true, neutral: false },
      NASDAQ: { value: '20,556.82', pct: '-0.18%', positive: false, neutral: false },
      'USD/INR': { value: '83.42', pct: '+0.05', positive: null, neutral: true },
      BRENT: { value: '$71.23', pct: '-1.2%', positive: false, neutral: false },
    };

    const cellsHtml = Object.entries(data).map(([ticker, info], idx) => {
      let deltaColor = 'var(--dl-fg-2)';
      if (info.neutral) {
        deltaColor = 'var(--accent-amber)';
      } else if (info.positive) {
        deltaColor = 'var(--accent-sage)';
      } else if (info.positive === false) {
        deltaColor = 'var(--accent-coral)';
      }

      const borderLeft = idx > 0 ? 'border-left: 1px solid var(--dl-line);' : '';

      return `
        <div class="global-ticker-cell" style="flex: 1; min-width: 0; padding: 6px 14px; ${borderLeft} display: flex; flex-direction: column; gap: 4px;">
          <span style="font-family: var(--font-sans); font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3);">
            ${ticker}
          </span>
          <div style="display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;">
            <span class="mono-nums" style="font-size: 0.95rem; font-weight: 600; color: var(--dl-fg);">
              ${info.value}
            </span>
            <span class="mono-nums" style="font-size: 0.8rem; font-weight: 600; color: ${deltaColor};">
              ${info.pct}
            </span>
          </div>
        </div>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="tile overnight-strip-tile span-12" style="display: flex; align-items: stretch; justify-content: space-between; padding: 12px 6px; overflow-x: auto;">
        ${cellsHtml}
      </div>
    `;
  }
}

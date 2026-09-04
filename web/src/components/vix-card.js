/**
 * India VIX Card Component for Swayam Capital (BUILD-9).
 * Displays trailing 20-day India VIX, volatility regime badge, and sparkline.
 */

export class VixCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(vixData = null) {
    const data = vixData || {
      value: 12.85,
      regime: 'Low Vol Regime',
      sparkline_20d: [13.4, 13.2, 13.1, 13.5, 13.0, 12.9, 12.8, 13.1, 12.7, 12.6, 12.9, 13.2, 13.0, 12.8, 12.7, 12.9, 13.1, 12.9, 12.8, 12.85],
    };

    const sparklineSvg = this.generateSparkline(data.sparkline_20d);

    this.container.innerHTML = `
      <div class="tile vix-tile" style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; min-height: 220px; gap: 10px;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="eyebrow" style="color: var(--dl-fg-3);">INDIA VIX · 20-DAY</span>
            <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--dl-fg-3);">REALTIME</span>
          </div>
          <div class="fig-xl" style="font-size: 2.6rem; margin-top: 8px;">
            ${data.value.toFixed(2)}
          </div>
          <div style="margin-top: 6px;">
            <span style="font-size: 0.75rem; font-weight: 600; padding: 3px 10px; border-radius: 999px; background: var(--accent-sage-tint); color: var(--accent-sage); border: 1px solid rgba(134,171,146,0.3);">
              ${data.regime}
            </span>
          </div>
        </div>

        <div style="width: 100%; height: 55px; margin-top: 8px;">
          ${sparklineSvg}
        </div>
      </div>
    `;
  }

  generateSparkline(points) {
    if (!points || points.length < 2) return '';
    const min = Math.min(...points) - 0.2;
    const max = Math.max(...points) + 0.2;
    const range = (max - min) || 1;
    const width = 260;
    const height = 55;

    const coords = points.map((p, i) => {
      const x = (i / (points.length - 1)) * width;
      const y = height - ((p - min) / range) * (height - 8) - 4;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    return `
      <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="overflow: visible;">
        <polyline
          fill="none"
          stroke="var(--accent-sage)"
          stroke-width="2.2"
          stroke-linecap="round"
          stroke-linejoin="round"
          points="${coords.join(' ')}"
        />
        <circle cx="${coords[coords.length - 1].split(',')[0]}" cy="${coords[coords.length - 1].split(',')[1]}" r="3.5" fill="var(--accent-sage)" />
      </svg>
    `;
  }
}

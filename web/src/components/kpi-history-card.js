/**
 * KPI History Card Component for Swayam Capital (BUILD-9).
 * Reusable reflective metric cards matching Atlas's .fig-xl serif treatment:
 * - Alcohol-Free Streak with Ramp Tier chip
 * - Last 7 Days Readiness Streak with circular day dots
 * - Morning Routine Completion with SVG trend sparkline
 */

export class KPIHistoryCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  /**
   * Renders the 3 streak/history cards in a clean vertical stack.
   * @param {Object} kpiData Data from /api/readiness/kpis
   */
  render(kpiData = {}) {
    const alcoholDays = kpiData.alcohol_streak_days ?? 0;
    const rampTier = kpiData.ramp_tier_label || 'Ramp tier 4 · 1.0% cap';
    const streakDots = kpiData.readiness_last_7_days || ['green', 'green', 'green', 'green', 'green', 'green', 'yellow'];
    const ratioStr = kpiData.readiness_ratio_str || '6 / 7';
    const routinePct = kpiData.morning_routine_pct ?? 92;
    const sparkline = kpiData.morning_routine_sparkline || [85, 88, 90, 89, 94, 91, 92];

    // Build 7 dots HTML
    // Pad to 7 if fewer
    const paddedDots = [...streakDots];
    while (paddedDots.length < 7) {
      paddedDots.unshift('track');
    }
    const dotsHtml = paddedDots.slice(-7).map(verdict => {
      let dotColor;
      if (verdict === 'green') dotColor = 'var(--accent-sage)';
      else if (verdict === 'yellow') dotColor = 'var(--accent-amber)';
      else if (verdict === 'red') dotColor = 'var(--accent-coral)';
      else dotColor = 'var(--dl-track)';

      return `<div style="width: 14px; height: 14px; border-radius: 50%; background: ${dotColor};"></div>`;
    }).join('');

    // Format ratio with muted slash
    const ratioParts = ratioStr.split('/');
    const ratioHtml = ratioParts.length === 2
      ? `<span class="fig-xl" style="font-size: 2.125rem;">${ratioParts[0].trim()}</span> <span style="font-family: var(--font-serif); font-size: 1.5rem; color: var(--dl-fg-3);">/</span> <span class="fig-xl" style="font-size: 1.75rem; color: var(--dl-fg-2);">${ratioParts[1].trim()}</span>`
      : `<span class="fig-xl" style="font-size: 1.75rem;">${ratioStr}</span>`;

    // SVG Sparkline
    const sparklineSvg = this.generateSparkline(sparkline);

    this.container.innerHTML = `
      <!-- Card 3: Alcohol-Free Streak -->
      <div class="tile kpi-streak-card" style="display: flex; flex-direction: column; gap: 8px;">
        <span class="eyebrow" style="color: var(--dl-fg-3);">ALCOHOL-FREE STREAK</span>
        <div style="display: flex; align-items: baseline; gap: 4px;">
          <span class="fig-xl">${alcoholDays}</span>
          <span style="font-family: var(--font-serif); font-size: 1.15rem; color: var(--dl-fg-2);">days</span>
        </div>
        <div style="margin-top: 2px;">
          <span style="font-size: 0.72rem; font-weight: 600; padding: 3px 8px; border-radius: 999px; background: var(--accent-sage-tint); color: var(--accent-sage); border: 1px solid rgba(134,171,146,0.3);">
            ${rampTier}
          </span>
        </div>
      </div>

      <!-- Card 4: 7-Day Readiness Streak -->
      <div class="tile kpi-readiness-streak-card" style="display: flex; flex-direction: column; gap: 8px;">
        <span class="eyebrow" style="color: var(--dl-fg-3);">LAST 7 DAYS · READINESS</span>
        <div style="display: flex; gap: 8px; align-items: center; margin: 4px 0;">
          ${dotsHtml}
        </div>
        <div>
          ${ratioHtml}
        </div>
      </div>

      <!-- Card 5: Morning Routine Completion -->
      <div class="tile kpi-routine-card" style="display: flex; flex-direction: column; gap: 8px;">
        <span class="eyebrow" style="color: var(--dl-fg-3);">MORNING ROUTINE COMPLETION</span>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div class="fig-xl">${routinePct}%</div>
          <div style="width: 100px; height: 36px;">
            ${sparklineSvg}
          </div>
        </div>
      </div>
    `;
  }

  generateSparkline(points) {
    if (!points || points.length < 2) return '';
    const min = Math.min(...points) - 5;
    const max = Math.max(...points) + 5;
    const range = (max - min) || 1;
    const width = 100;
    const height = 36;

    const coords = points.map((p, i) => {
      const x = (i / (points.length - 1)) * width;
      const y = height - ((p - min) / range) * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    return `
      <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="overflow: visible;">
        <polyline
          fill="none"
          stroke="var(--accent-sage)"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          points="${coords.join(' ')}"
        />
        <circle cx="${coords[coords.length - 1].split(',')[0]}" cy="${coords[coords.length - 1].split(',')[1]}" r="3" fill="var(--accent-sage)" />
      </svg>
    `;
  }
}

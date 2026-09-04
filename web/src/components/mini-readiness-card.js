/**
 * Mini Readiness Status Card for Strategy Builder Left Rail (BUILD-10).
 *
 * Compact summary of trader readiness ritual: verdict, streak, and 7-day history dots.
 */

export class MiniReadinessCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(readinessData = null) {
    const verdict = readinessData?.verdict || 'GO';
    const streak = readinessData?.streak ?? 5;
    const isGo = verdict === 'GO';
    const isCaution = verdict === 'CAUTION';

    const color = isGo ? 'var(--accent-sage)' : (isCaution ? 'var(--accent-amber)' : 'var(--accent-coral)');
    const tint = isGo ? 'var(--accent-sage-tint)' : (isCaution ? 'var(--accent-amber-tint)' : 'var(--accent-coral-tint)');

    // 7-day dot indicators
    const dotsHtml = Array.from({ length: 7 }).map((_, i) => {
      const active = i >= (7 - streak);
      return `
        <span style="
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: ${active ? 'var(--accent-sage)' : 'var(--dl-line)'};
          display: inline-block;
        "></span>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="mini-readiness-card" style="
        background: var(--dl-card);
        border: 1px solid var(--dl-line);
        border-radius: var(--radius-card);
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="eyebrow" style="color: var(--dl-fg-3);">READINESS</span>
          <span style="
            font-size: 0.72rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 999px;
            background: ${tint};
            color: ${color};
            border: 1px solid ${color}44;
          ">
            ${verdict}
          </span>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem;">
          <span style="color: var(--dl-fg-2);">Discipline Streak:</span>
          <span style="font-family: var(--font-mono); font-weight: 600; color: var(--dl-fg);">${streak} Days</span>
        </div>

        <div style="display: flex; align-items: center; gap: 5px; margin-top: 2px;">
          ${dotsHtml}
        </div>
      </div>
    `;
  }
}

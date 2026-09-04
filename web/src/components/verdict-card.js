/**
 * Verdict Card Component for Swayam Capital (BUILD-9).
 * Displays the operational readiness verdict (GREEN / YELLOW / RED)
 * in Atlas pastel card finishes with typography rules and rule citations.
 */

export class VerdictCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.currentVerdict = null;
  }

  init() {
    this.renderPending();
  }

  setVerdict(verdictData) {
    this.currentVerdict = verdictData;
    this.render();
  }

  renderPending() {
    this.container.innerHTML = `
      <div class="tile verdict-tile-pending" style="display: flex; flex-direction: column; gap: 8px; background: var(--dl-card); border: 1px dashed var(--dl-line); border-radius: var(--radius-card); padding: 18px 20px;">
        <span class="eyebrow" style="color: var(--dl-fg-3);">VERDICT · PENDING RITUAL</span>
        <div class="fig-lg" style="color: var(--dl-fg-2); font-size: 1.65rem;">
          AWAITING CHECK-IN
        </div>
        <p style="font-size: 0.85rem; color: var(--dl-fg-3); margin: 0; line-height: 1.45;">
          Complete your 6-step readiness ritual above. Your physical state, sleep, and emotional readiness gate today's trading permissions.
        </p>
      </div>
    `;
  }

  render() {
    if (!this.currentVerdict) {
      this.renderPending();
      return;
    }

    const v = (this.currentVerdict.verdict || 'green').toLowerCase();
    const isGreen = v === 'green';
    const isYellow = v === 'yellow';
    const isRed = v === 'red';

    let bg, textColor, headline, bodyText, chipBg, chipColor;

    if (isGreen) {
      bg = 'var(--dl-done)';
      textColor = 'var(--dl-done-on)';
      headline = 'GREEN — READY';
      const capPct = (this.currentVerdict.size_cap_pct || 0.01) * 100;
      bodyText = `All 5 gates cleared. Full ${capPct.toFixed(1)}% risk per trade unlocked. Trade window opens at 09:15 IST.`;
      chipBg = 'rgba(10, 92, 60, 0.15)';
      chipColor = '#0a5c3c';
    } else if (isYellow) {
      bg = 'var(--dl-skip)';
      textColor = 'var(--dl-skip-on)';
      headline = 'YELLOW — CAUTION';
      const capPct = (this.currentVerdict.size_cap_pct || 0.0075) * 100;
      bodyText = `Readiness reduced. Position size capped at ${capPct.toFixed(2)}% of margin base. Single spreads only.`;
      chipBg = 'rgba(111, 75, 6, 0.18)';
      chipColor = '#6f4b06';
    } else {
      bg = 'var(--dl-alert)';
      textColor = 'var(--dl-alert-on)';
      headline = 'RED — NO TRADING';
      bodyText = 'Session blocked. One or more non-negotiable readiness rules were breached. Platform execution locked.';
      chipBg = 'rgba(141, 45, 19, 0.18)';
      chipColor = '#8d2d13';
    }

    const reasons = this.currentVerdict.reasons || [];
    const reasonsHtml = reasons.length > 0
      ? `<div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;">
          ${reasons.map(r => `
            <span style="font-size: 0.75rem; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: ${chipBg}; color: ${chipColor};">
              Rule: ${r}
            </span>
          `).join('')}
        </div>`
      : '';

    this.container.innerHTML = `
      <div class="tile verdict-tile" style="display: flex; flex-direction: column; gap: 8px; background: ${bg}; color: ${textColor}; border: 1px solid transparent; border-radius: var(--radius-card); padding: 18px 20px; transition: all var(--dur-base) ease;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="eyebrow" style="color: ${textColor}; opacity: 0.85;">VERDICT</span>
          <span style="font-family: var(--font-mono); font-size: 0.72rem; opacity: 0.85;">ENFORCED</span>
        </div>
        <div class="fig-lg" style="color: ${textColor};">
          ${headline}
        </div>
        <p style="font-size: 0.875rem; margin: 0; line-height: 1.45; font-weight: 500;">
          ${bodyText}
        </p>
        ${reasonsHtml}
      </div>
    `;
  }
}

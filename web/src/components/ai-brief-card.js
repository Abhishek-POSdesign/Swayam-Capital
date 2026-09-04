/**
 * AI Brief Card Component for Swayam Capital (BUILD-9).
 * Displays the "What Matters Today" morning prep briefing from the AI Trading Partner,
 * framed as elimination criteria with a 2px lilac left border and AI Drawer launcher button.
 */

export class AIBriefCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onOpenAIDrawer }
  }

  render(briefData = null, errorMessage = null) {
    if (errorMessage) {
      this.container.innerHTML = `
        <div class="tile ai-brief-tile span-12" style="border-left: 2px solid var(--accent-coral); background: var(--dl-card); display: flex; flex-direction: column; gap: 8px;">
          <span class="eyebrow" style="color: var(--accent-coral);">WHAT MATTERS TODAY · AI UNAVAILABLE</span>
          <p style="font-size: 0.9rem; color: var(--dl-fg-2); margin: 0; line-height: 1.5;">
            AI Trading Partner briefing could not be generated: <strong style="color: var(--accent-coral);">${errorMessage}</strong>
          </p>
        </div>
      `;
      return;
    }

    const defaultBrief = "India VIX at 12.85 confirms low-volatility regime. Premium-selling favorable, but reward is compressed — spreads over singles. Prefer setups where realistic risk (2σ NIFTY move ≈ ₹165) stays under 1% cap. Skip trades if event risk within 48 hours — RBI meet Monday. Bear Put Spread around 24,800 has clean structure given yesterday's higher-high VWAP bounce.";
    const text = briefData?.brief_text || defaultBrief;

    this.container.innerHTML = `
      <div class="tile ai-brief-tile span-12" style="border-left: 3px solid var(--accent-lilac); background: var(--dl-card); display: flex; flex-direction: column; gap: 10px; padding: 18px 22px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="color: var(--accent-lilac);">
              <path d="M8 0L9.8 6.2L16 8L9.8 9.8L8 16L6.2 9.8L0 8L6.2 6.2L8 0Z" fill="currentColor"/>
            </svg>
            <span class="eyebrow" style="color: var(--accent-lilac); font-weight: 700;">WHAT MATTERS TODAY · AI TRADING PARTNER</span>
          </div>
          <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--dl-fg-3);">DAILY PRE-MARKET</span>
        </div>

        <p id="ai-brief-content" style="font-family: var(--font-sans); font-size: 0.9375rem; color: var(--dl-fg); margin: 0; line-height: 1.6; font-weight: 400;">
          ${text}
        </p>

        <div style="display: flex; justify-content: flex-end; margin-top: 4px;">
          <button id="btn-open-ai-drawer" style="background: var(--accent-lilac); color: #101116; border: none; height: 32px; padding: 0 16px; border-radius: 9px; font-size: 0.82rem; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: transform var(--dur-fast) ease;">
            Open Full AI Drawer →
          </button>
        </div>
      </div>
    `;

    const btnOpen = this.container.querySelector('#btn-open-ai-drawer');
    if (btnOpen) {
      btnOpen.addEventListener('click', () => {
        if (this.options.onOpenAIDrawer) {
          this.options.onOpenAIDrawer();
        }
      });
    }
  }
}

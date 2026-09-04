/**
 * Today's Session Recap Component for Strategy Builder Left Rail (BUILD-10).
 *
 * Displays key context bullets extracted from the AI Trading Partner dialogue
 * on the Home page, guaranteeing conversation continuity into the Builder.
 */

export class SessionRecapComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(recapData = null) {
    const bullets = recapData?.bullets || [
      'Focus: "NIFTY Bear Put Spread around 24,800"',
      'AI: Low volatility regime favors spreads over single legs',
      'RBI Meet Monday: Avoid naked positions or high theta drag',
    ];

    const bulletsHtml = bullets.map((b) => `
      <li style="margin-bottom: 5px; line-height: 1.4; color: var(--dl-fg-2);">
        ${b}
      </li>
    `).join('');

    this.container.innerHTML = `
      <div class="session-recap-card" style="
        background: var(--dl-card);
        border: 1px solid var(--dl-line);
        border-radius: var(--radius-card);
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="var(--accent-lilac)">
              <path d="M8 0L9.8 6.2L16 8L9.8 9.8L8 16L6.2 9.8L0 8L6.2 6.2L8 0Z"/>
            </svg>
            <span class="eyebrow" style="color: var(--accent-lilac);">HOME SESSION RECAP</span>
          </div>
          <span style="font-size: 0.68rem; color: var(--dl-fg-3); font-family: var(--font-mono);">CONTINUOUS</span>
        </div>

        <ul style="
          margin: 0;
          padding-left: 14px;
          font-size: 0.75rem;
          list-style: disc;
        ">
          ${bulletsHtml}
        </ul>
      </div>
    `;
  }
}

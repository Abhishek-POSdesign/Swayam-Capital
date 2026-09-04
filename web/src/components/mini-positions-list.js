/**
 * Mini Open Positions List for Strategy Builder Left Rail (BUILD-10).
 *
 * Displays compact cards for current active positions with live P&L indicators.
 */

export class MiniPositionsListComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onSelectPosition }
    this.positions = [];
  }

  render(positions = []) {
    this.positions = positions;

    let itemsHtml = '';
    if (!positions || positions.length === 0) {
      itemsHtml = `
        <div style="font-size: 0.76rem; color: var(--dl-fg-3); font-style: italic; padding: 6px 0;">
          No open positions.
        </div>
      `;
    } else {
      itemsHtml = positions.map((p) => {
        const pnl = p.unrealized_pnl_inr || 0;
        const isPos = pnl >= 0;
        const pnlColor = isPos ? 'var(--accent-sage)' : 'var(--accent-coral)';
        const sign = isPos ? '+' : '';
        const legsCount = (p.legs || []).length;

        return `
          <div
            class="mini-pos-item"
            data-position-id="${p.id}"
            style="
              background: var(--dl-card-2);
              border: 1px solid var(--dl-line);
              border-radius: 6px;
              padding: 8px 10px;
              display: flex;
              justify-content: space-between;
              align-items: center;
              cursor: pointer;
              transition: border-color var(--dur-fast) ease;
            "
            onmouseover="this.style.borderColor='var(--dl-fg-3)'"
            onmouseout="this.style.borderColor='var(--dl-line)'"
          >
            <div>
              <div style="font-size: 0.78rem; font-weight: 600; color: var(--dl-fg);">
                ${p.strategy_name || 'Spread'}
              </div>
              <div style="font-size: 0.68rem; color: var(--dl-fg-3); font-family: var(--font-mono);">
                ${legsCount} legs · ${p.expiry_date || 'NIFTY'}
              </div>
            </div>
            <div style="text-align: right;">
              <div style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; color: ${pnlColor};">
                ${sign}₹${Math.round(pnl).toLocaleString('en-IN')}
              </div>
              <div style="font-size: 0.65rem; color: var(--dl-fg-3);">unrealized</div>
            </div>
          </div>
        `;
      }).join('');
    }

    this.container.innerHTML = `
      <div class="mini-positions-container" style="
        background: var(--dl-card);
        border: 1px solid var(--dl-line);
        border-radius: var(--radius-card);
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="eyebrow" style="color: var(--dl-fg-3);">ACTIVE TRADES (${positions.length})</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px;">
          ${itemsHtml}
        </div>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    this.container.querySelectorAll('.mini-pos-item').forEach((el) => {
      el.addEventListener('click', () => {
        const id = el.getAttribute('data-position-id');
        const pos = this.positions.find((p) => p.id === id);
        if (pos && this.options.onSelectPosition) {
          this.options.onSelectPosition(pos);
        }
      });
    });
  }
}

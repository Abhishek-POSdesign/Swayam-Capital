/**
 * Overnight Naked Auto-Block Modal Component for Swayam Capital (BUILD-10).
 *
 * Hard-blocks unhedged short positions approaching 15:20 IST.
 * Cannot be dismissed with Escape or backdrop click.
 * Only two paths forward: [Add Hedge Now] or [Exit Position Instead].
 */

export class OvernightBlockModalComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onAddHedge, onExitPosition }
    this.isOpen = false;
    this.violationData = null;
  }

  show(violation) {
    this.violationData = violation;
    this.isOpen = true;
    this.render();
  }

  hide() {
    this.isOpen = false;
    this.container.innerHTML = '';
  }

  render() {
    if (!this.isOpen || !this.violationData) {
      this.container.innerHTML = '';
      return;
    }

    const v = this.violationData;
    const nakedLegsStr = (v.naked_legs || [])
      .map((l) => `${l.direction?.toUpperCase()} ${l.strike} ${l.option_type} (${l.quantity_lots || 1} lot)`)
      .join(', ');

    const hedgeSuggestion = v.suggested_hedges && v.suggested_hedges[0]
      ? `Suggested Hedge: BUY ${v.suggested_hedges[0].strike} ${v.suggested_hedges[0].option_type} (${v.suggested_hedges[0].quantity_lots} lot)`
      : 'Suggested Hedge: Buy matching OTM wing to cap tail risk';

    this.container.innerHTML = `
      <div id="overnight-modal-scrim" style="
        position: fixed;
        inset: 0;
        z-index: 9999;
        background: rgba(16, 17, 22, 0.88);
        backdrop-filter: blur(8px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
      ">
        <div style="
          width: 100%;
          max-width: 540px;
          background: var(--dl-card);
          border: 2px solid var(--accent-coral);
          border-radius: var(--radius-card, 12px);
          box-shadow: 0 20px 50px rgba(221, 129, 112, 0.25);
          padding: 28px;
          display: flex;
          flex-direction: column;
          gap: 18px;
        ">
          <!-- Header with Alert Icon -->
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="
              width: 44px;
              height: 44px;
              border-radius: 50%;
              background: var(--accent-coral-tint, rgba(221,129,112,0.15));
              color: var(--accent-coral);
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 1.4rem;
            ">
              ⚠️
            </div>
            <div>
              <div class="eyebrow" style="color: var(--accent-coral); font-weight: 700;">
                AUTO-BLOCK ENFORCEMENT · 15:20 IST
              </div>
              <h2 style="font-family: var(--font-serif); font-size: 1.35rem; color: var(--dl-fg); margin: 2px 0 0 0;">
                Overnight Naked Position Detected
              </h2>
            </div>
          </div>

          <!-- Position Details Box -->
          <div style="
            background: var(--dl-card-2);
            border: 1px solid var(--dl-line);
            border-radius: 8px;
            padding: 14px 16px;
            font-size: 0.82rem;
            display: flex;
            flex-direction: column;
            gap: 6px;
          ">
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--dl-fg-3);">Position:</span>
              <span style="font-weight: 600; color: var(--dl-fg);">${v.strategy_name || 'Open Position'} (#${(v.position_id || '').slice(0, 8)})</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--dl-fg-3);">Unhedged Short Leg:</span>
              <span style="font-family: var(--font-mono); color: var(--accent-coral); font-weight: 600;">${nakedLegsStr || 'Short Leg'}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 4px; padding-top: 6px; border-top: 1px solid var(--dl-line);">
              <span style="color: var(--accent-sage);">${hedgeSuggestion}</span>
            </div>
          </div>

          <!-- Rule Citation -->
          <div style="font-size: 0.76rem; color: var(--dl-fg-2); line-height: 1.5; background: rgba(255,255,255,0.03); padding: 10px 12px; border-radius: 6px;">
            📜 <strong>${v.rule_citation || 'Risk Management Rules § 10a — no overnight naked. Overnight hedge cap: 2% of margin base.'}</strong>
            <br />
            Holding unhedged short options overnight creates uncapped gap-risk against adverse macro opens.
          </div>

          <!-- Strict Two Action Buttons Only -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 4px;">
            <button
              type="button"
              id="btn-add-hedge-now"
              style="
                height: 44px;
                background: var(--accent-sage);
                color: #101116;
                font-weight: 700;
                font-size: 0.88rem;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                transition: opacity var(--dur-fast) ease;
              "
            >
              🛡️ Add Hedge Now
            </button>

            <button
              type="button"
              id="btn-exit-position-instead"
              style="
                height: 44px;
                background: var(--accent-coral-tint);
                color: var(--accent-coral);
                border: 1px solid rgba(221,129,112,0.4);
                font-weight: 700;
                font-size: 0.88rem;
                border-radius: 8px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                transition: all var(--dur-fast) ease;
              "
            >
              Exit Position Instead
            </button>
          </div>
        </div>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const btnHedge = this.container.querySelector('#btn-add-hedge-now');
    if (btnHedge) {
      btnHedge.addEventListener('click', () => {
        const v = this.violationData;
        this.hide();
        if (this.options.onAddHedge) {
          this.options.onAddHedge(v);
        }
      });
    }

    const btnExit = this.container.querySelector('#btn-exit-position-instead');
    if (btnExit) {
      btnExit.addEventListener('click', () => {
        const v = this.violationData;
        this.hide();
        if (this.options.onExitPosition) {
          this.options.onExitPosition(v);
        }
      });
    }

    // Intercept Escape key to prevent closing
    window.addEventListener('keydown', (e) => {
      if (this.isOpen && e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
      }
    }, true);
  }
}

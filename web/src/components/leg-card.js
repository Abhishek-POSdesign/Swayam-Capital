/**
 * Single Leg Card Component for Swayam Capital (BUILD-10).
 *
 * Represents an individual option leg in the Strategy Builder.
 */

export class LegCardComponent {
  constructor(container, legData, index, options = {}) {
    this.container = container;
    this.leg = { ...legData };
    this.index = index;
    this.options = options; // { onChange, onRemove, onQuoteFetch }
  }

  updateGreeks(greeks) {
    if (!greeks) return;
    if (greeks.delta !== undefined) this.leg.delta = greeks.delta;
    if (greeks.theta !== undefined) this.leg.theta = greeks.theta;
    if (greeks.vega !== undefined) this.leg.vega = greeks.vega;
  }

  render() {
    const isBuy = this.leg.direction?.toLowerCase() === 'buy';
    const isCE = this.leg.option_type === 'CE';
    const badgeBg = isBuy ? 'var(--accent-sage-tint)' : 'var(--accent-coral-tint)';
    const badgeColor = isBuy ? 'var(--accent-sage)' : 'var(--accent-coral)';
    const badgeBorder = isBuy ? 'rgba(134,171,146,0.35)' : 'rgba(221,129,112,0.35)';

    const ltpDisplay = typeof this.leg.entry_premium === 'number' && this.leg.entry_premium > 0
      ? `₹${this.leg.entry_premium.toFixed(2)}`
      : '₹--';

    // Strike IV calculation
    const ivVal = typeof this.leg.iv === 'number' && this.leg.iv > 0
      ? this.leg.iv
      : typeof this.leg.implied_volatility === 'number' && this.leg.implied_volatility > 0
      ? (this.leg.implied_volatility > 1 ? this.leg.implied_volatility : this.leg.implied_volatility * 100)
      : null;
    const ivDisplay = ivVal != null ? `${ivVal.toFixed(1)}%` : '14.2%';

    // Live LTP move % since added
    if (this.leg.initial_premium == null && typeof this.leg.entry_premium === 'number' && this.leg.entry_premium > 0) {
      this.leg.initial_premium = this.leg.entry_premium;
    }
    let changePct = this.leg.change_pct;
    if (changePct == null && this.leg.entry_premium && this.leg.initial_premium && this.leg.initial_premium > 0) {
      changePct = ((this.leg.entry_premium - this.leg.initial_premium) / this.leg.initial_premium) * 100;
    }
    const hasChange = changePct != null && !isNaN(changePct);
    const isUp = hasChange ? changePct >= 0 : true;
    const changeIcon = hasChange ? (isUp ? '▲' : '▼') : '—';
    const changeText = hasChange ? `${isUp ? '+' : ''}${changePct.toFixed(1)}%` : '0.0%';
    const changeColor = hasChange ? (isUp ? 'var(--accent-sage)' : 'var(--accent-coral)') : 'var(--text-muted)';

    this.container.innerHTML = `
      <div class="leg-card ${isBuy ? 'leg-buy' : 'leg-sell'}" style="
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        border: 1px solid var(--dl-line);
        border-radius: var(--radius-sm);
        transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease;
      ">
        <!-- B / S Toggle Badge -->
        <button
          type="button"
          id="btn-toggle-dir-${this.index}"
          class="btn-toggle-direction"
          title="Click to toggle BUY / SELL"
          style="
            width: 34px;
            height: 34px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.95rem;
            background: ${badgeBg};
            color: ${badgeColor};
            border: 1px solid ${badgeBorder};
            cursor: pointer;
            transition: all var(--dur-fast) ease;
          "
        >
          ${isBuy ? 'B' : 'S'}
        </button>

        <!-- Instrument selector (NIFTY) -->
        <div style="width: 80px;">
          <select class="input-instrument" style="
            width: 100%;
            height: 32px;
            background: var(--dl-input-bg, var(--dl-card-2));
            color: var(--dl-fg);
            border: 1px solid var(--dl-line);
            border-radius: 6px;
            padding: 0 6px;
            font-size: 0.8rem;
            font-weight: 600;
          ">
            <option value="NIFTY" selected>NIFTY</option>
          </select>
        </div>

        <!-- CE / PE Toggle -->
        <div class="ce-pe-toggle" style="display: flex; background: var(--dl-card-2); border-radius: 6px; border: 1px solid var(--dl-line); padding: 2px;">
          <button
            type="button"
            class="btn-type-ce ${isCE ? 'active' : ''}"
            style="
              padding: 4px 10px;
              font-size: 0.75rem;
              font-weight: 700;
              border: none;
              border-radius: 4px;
              cursor: pointer;
              background: ${isCE ? 'var(--accent-sage-tint)' : 'transparent'};
              color: ${isCE ? 'var(--accent-sage)' : 'var(--dl-fg-3)'};
            "
          >
            CE
          </button>
          <button
            type="button"
            class="btn-type-pe ${!isCE ? 'active' : ''}"
            style="
              padding: 4px 10px;
              font-size: 0.75rem;
              font-weight: 700;
              border: none;
              border-radius: 4px;
              cursor: pointer;
              background: ${!isCE ? 'var(--accent-coral-tint)' : 'transparent'};
              color: ${!isCE ? 'var(--accent-coral)' : 'var(--dl-fg-3)'};
            "
          >
            PE
          </button>
        </div>

        <!-- Expiry Date picker -->
        <div style="flex: 0 0 120px;">
          <input
            type="date"
            class="input-expiry"
            value="${this.leg.expiry_date || ''}"
            style="
              width: 100%;
              height: 32px;
              background: var(--dl-input-bg, var(--dl-card-2));
              color: var(--dl-fg);
              border: 1px solid var(--dl-line);
              border-radius: 6px;
              padding: 0 6px;
              font-size: 0.78rem;
              font-family: var(--font-mono);
            "
          />
        </div>

        <!-- Strike input (snaps to 50) -->
        <div style="flex: 0 0 95px; position: relative;">
          <input
            type="number"
            step="50"
            class="input-strike"
            value="${this.leg.strike || 24850}"
            style="
              width: 100%;
              height: 32px;
              background: var(--dl-input-bg, var(--dl-card-2));
              color: var(--text-primary);
              border: 1px solid var(--dl-line);
              border-radius: 6px;
              padding: 0 8px;
              font-size: 0.85rem;
              font-family: var(--font-mono);
              font-weight: 600;
            "
          />
        </div>

        <!-- Lots stepper -->
        <div style="display: flex; align-items: center; background: var(--dl-card-2); border: 1px solid var(--dl-line); border-radius: 6px; height: 32px;">
          <button
            type="button"
            class="btn-lot-dec"
            style="width: 26px; height: 100%; border: none; background: transparent; color: var(--text-secondary); cursor: pointer; font-weight: 700;"
          >-</button>
          <span class="lot-val" style="min-width: 44px; text-align: center; font-size: 0.78rem; font-family: var(--font-mono); font-weight: 600; color: var(--text-primary);">
            ${this.leg.quantity_lots || 1} lot
          </span>
          <button
            type="button"
            class="btn-lot-inc"
            style="width: 26px; height: 100%; border: none; background: transparent; color: var(--text-secondary); cursor: pointer; font-weight: 700;"
          >+</button>
        </div>

        <!-- Live LTP -->
        <div style="flex: 0 0 85px; text-align: right;">
          <div class="leg-ltp" style="font-family: var(--font-mono); font-size: 0.92rem; font-weight: 700; color: var(--text-primary);">
            ${ltpDisplay}
          </div>
          <div style="font-size: 0.65rem; color: var(--text-muted); font-weight: 500;">LTP</div>
        </div>

        <!-- Secondary Right-Side Column: Live LTP Move % & Strike IV -->
        <div class="leg-secondary-metrics" style="
          flex: 1 1 auto;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          justify-content: center;
          padding: 0 14px;
          min-width: 90px;
          border-left: 1px dashed var(--dl-line);
          margin-left: 6px;
        ">
          <div style="font-family: var(--font-mono); font-size: 0.78rem; font-weight: 700; color: ${changeColor}; display: flex; align-items: center; gap: 3px;">
            <span>${changeIcon}</span>
            <span>${changeText}</span>
          </div>
          <div style="font-family: var(--font-mono); font-size: 0.68rem; color: var(--text-muted); margin-top: 2px;">
            IV ~${ivDisplay}
          </div>
        </div>

        <!-- Remove Button -->
        <button
          type="button"
          id="btn-remove-leg-${this.index}"
          class="btn-remove-leg"
          title="Remove leg"
          style="
            margin-left: auto;
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 1rem;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            transition: color var(--dur-fast) ease;
          "
          onmouseover="this.style.color='var(--accent-coral)'"
          onmouseout="this.style.color='var(--text-muted)'"
        >
          ✕
        </button>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const btnDir = this.container.querySelector(`#btn-toggle-dir-${this.index}`) || this.container.querySelector('.btn-toggle-direction');
    if (btnDir) {
      btnDir.addEventListener('click', () => {
        this.leg.direction = this.leg.direction?.toLowerCase() === 'buy' ? 'sell' : 'buy';
        this.notifyChange();
      });
    }

    const btnCe = this.container.querySelector('.btn-type-ce');
    const btnPe = this.container.querySelector('.btn-type-pe');
    if (btnCe && btnPe) {
      btnCe.addEventListener('click', () => {
        if (this.leg.option_type !== 'CE') {
          this.leg.option_type = 'CE';
          this.notifyChange();
        }
      });
      btnPe.addEventListener('click', () => {
        if (this.leg.option_type !== 'PE') {
          this.leg.option_type = 'PE';
          this.notifyChange();
        }
      });
    }

    const inputStrike = this.container.querySelector('.input-strike');
    if (inputStrike) {
      inputStrike.addEventListener('change', (e) => {
        let val = parseFloat(e.target.value) || 24850;
        val = Math.round(val / 50) * 50;
        inputStrike.value = val;
        this.leg.strike = val;
        this.notifyChange();
      });
    }

    const inputExpiry = this.container.querySelector('.input-expiry');
    if (inputExpiry) {
      inputExpiry.addEventListener('change', (e) => {
        this.leg.expiry_date = e.target.value;
        this.notifyChange();
      });
    }

    const btnDec = this.container.querySelector('.btn-lot-dec');
    const btnInc = this.container.querySelector('.btn-lot-inc');
    if (btnDec && btnInc) {
      btnDec.addEventListener('click', () => {
        const cur = this.leg.quantity_lots || 1;
        if (cur > 1) {
          this.leg.quantity_lots = cur - 1;
          this.notifyChange();
        }
      });
      btnInc.addEventListener('click', () => {
        const cur = this.leg.quantity_lots || 1;
        this.leg.quantity_lots = cur + 1;
        this.notifyChange();
      });
    }

    const btnRemove = this.container.querySelector(`#btn-remove-leg-${this.index}`) || this.container.querySelector('.btn-remove-leg');
    if (btnRemove) {
      btnRemove.addEventListener('click', () => {
        if (this.options.onRemove) {
          this.options.onRemove(this.index);
        }
      });
    }
  }

  notifyChange() {
    this.render();
    if (this.options.onChange) {
      this.options.onChange(this.index, this.leg);
    }
  }

  updateQuote(quote) {
    if (!quote) return;
    if (this.leg.initial_premium == null && this.leg.entry_premium != null) {
      this.leg.initial_premium = this.leg.entry_premium;
    }
    if (quote.ltp != null && this.leg.initial_premium != null && this.leg.initial_premium > 0) {
      this.leg.change_pct = ((quote.ltp - this.leg.initial_premium) / this.leg.initial_premium) * 100;
    }
    this.leg.entry_premium = quote.ltp ?? this.leg.entry_premium;
    this.leg.delta = quote.delta;
    this.leg.theta = quote.theta;
    this.leg.vega = quote.vega;
    this.leg.iv = quote.iv;

    this.render();
  }
}

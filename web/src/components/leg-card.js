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

  _renderGreeksHtml() {
    const hasDelta = this.leg.delta !== undefined && this.leg.delta !== null && !isNaN(this.leg.delta);
    const hasTheta = this.leg.theta !== undefined && this.leg.theta !== null && !isNaN(this.leg.theta);
    const hasVega = this.leg.vega !== undefined && this.leg.vega !== null && !isNaN(this.leg.vega);

    const deltaSign = hasDelta
      ? (Number(this.leg.delta) > 0 ? `+${Number(this.leg.delta).toFixed(2)}` : Number(this.leg.delta).toFixed(2))
      : null;

    let thetaDisplay = null;
    let thetaColor = 'var(--accent-lilac)';
    if (hasTheta) {
      const numTheta = Number(this.leg.theta);
      thetaDisplay = numTheta > 0 ? `+${numTheta.toFixed(1)}` : numTheta.toFixed(1);
      thetaColor = numTheta >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';
    }

    const vegaDisplay = hasVega ? (Math.abs(Number(this.leg.vega) % 1) > 0.01 ? Number(this.leg.vega).toFixed(1) : Math.round(Number(this.leg.vega))) : null;

    const deltaHtml = deltaSign !== null
      ? `<span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--accent-lilac); background: var(--accent-lilac-tint); padding: 2px 6px; border-radius: 4px;" title="Delta">Δ ${deltaSign}</span>`
      : `<span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--accent-amber); background: rgba(201,160,74,0.12); padding: 2px 6px; border-radius: 4px; cursor: help;" title="Greek computation unavailable — see server logs">⚠ Δ</span>`;

    const thetaHtml = thetaDisplay !== null
      ? `<span style="font-family: var(--font-mono); font-size: 0.72rem; color: ${thetaColor}; background: var(--accent-lilac-tint); padding: 2px 6px; border-radius: 4px;" title="Theta per day (₹/day)">θ ${thetaDisplay}</span>`
      : `<span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--accent-amber); background: rgba(201,160,74,0.12); padding: 2px 6px; border-radius: 4px; cursor: help;" title="Greek computation unavailable — see server logs">⚠ θ</span>`;

    const vegaHtml = vegaDisplay !== null
      ? `<span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--accent-lilac); background: var(--accent-lilac-tint); padding: 2px 6px; border-radius: 4px;" title="Vega (₹/vol)">ν ${vegaDisplay}</span>`
      : `<span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--accent-amber); background: rgba(201,160,74,0.12); padding: 2px 6px; border-radius: 4px; cursor: help;" title="Greek computation unavailable — see server logs">⚠ ν</span>`;

    return `${deltaHtml}${thetaHtml}${vegaHtml}`;
  }

  updateGreeks(greeks) {
    if (!greeks) return;
    if (greeks.delta !== undefined) this.leg.delta = greeks.delta;
    if (greeks.theta !== undefined) this.leg.theta = greeks.theta;
    if (greeks.vega !== undefined) this.leg.vega = greeks.vega;
    const strip = this.container.querySelector('.leg-greeks-strip');
    if (strip) {
      strip.innerHTML = this._renderGreeksHtml();
    }
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

    this.container.innerHTML = `
      <div class="leg-card" style="
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 14px;
        background: var(--dl-card);
        border: 1px solid var(--dl-line);
        border-radius: var(--radius-card);
        transition: border-color var(--dur-fast) ease;
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
              color: var(--dl-fg);
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
            style="width: 26px; height: 100%; border: none; background: transparent; color: var(--dl-fg-2); cursor: pointer; font-weight: 700;"
          >-</button>
          <span class="lot-val" style="min-width: 44px; text-align: center; font-size: 0.78rem; font-family: var(--font-mono); font-weight: 600; color: var(--dl-fg);">
            ${this.leg.quantity_lots || 1} lot
          </span>
          <button
            type="button"
            class="btn-lot-inc"
            style="width: 26px; height: 100%; border: none; background: transparent; color: var(--dl-fg-2); cursor: pointer; font-weight: 700;"
          >+</button>
        </div>

        <!-- Live LTP -->
        <div style="flex: 0 0 85px; text-align: right;">
          <div class="leg-ltp" style="font-family: var(--font-mono); font-size: 0.9rem; font-weight: 600; color: var(--dl-fg);">
            ${ltpDisplay}
          </div>
          <div style="font-size: 0.65rem; color: var(--dl-fg-3);">LTP</div>
        </div>

        <!-- Greeks Pill Strip -->
        <div class="leg-greeks-strip" style="display: flex; gap: 6px; flex: 1; justify-content: flex-end; align-items: center;">
          ${this._renderGreeksHtml()}
        </div>

        <!-- Remove Button -->
        <button
          type="button"
          id="btn-remove-leg-${this.index}"
          class="btn-remove-leg"
          title="Remove leg"
          style="
            background: transparent;
            border: none;
            color: var(--dl-fg-3);
            font-size: 1rem;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            transition: color var(--dur-fast) ease;
          "
          onmouseover="this.style.color='var(--accent-coral)'"
          onmouseout="this.style.color='var(--dl-fg-3)'"
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
    this.leg.entry_premium = quote.ltp ?? this.leg.entry_premium;
    this.leg.delta = quote.delta;
    this.leg.theta = quote.theta;
    this.leg.vega = quote.vega;
    this.leg.iv = quote.iv;

    const ltpEl = this.container.querySelector('.leg-ltp');
    if (ltpEl && quote.ltp !== undefined) {
      ltpEl.textContent = `₹${Number(quote.ltp).toFixed(2)}`;
    }
  }
}

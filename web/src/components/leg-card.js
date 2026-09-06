/**
 * Single Leg Card — Strategy Builder v2 (Swayam Capital).
 *
 * Row: [B/S] [CE/PE] [Expiry ▼] [Strike] [Lots] [Price (editable)] [IV] [Delta] [✕]
 *
 * No-fake-numbers law:
 *  - IV and Delta show '—' when they can't be derived from a real price; never a placeholder.
 *  - Price is editable: real LTP pre-fills it when the market is open; otherwise you type your
 *    (limit) price. IV and Delta are computed from whatever price is in the field.
 *  - Editing the price updates IV/Delta WITHOUT re-rendering the row, so the input keeps focus.
 */

export class LegCardComponent {
  constructor(container, legData, index, options = {}) {
    this.container = container;
    this.leg = { ...legData };
    this.index = index;
    this.options = options; // { onChange, onPriceInput, onRemove, expiries }
  }

  _fmtIv() {
    if (this.leg.iv_available === false) return '—';
    const iv = this.leg.iv;
    return (typeof iv === 'number' && iv > 0) ? `${(iv * 100).toFixed(1)}%` : '—';
  }

  _fmtDelta() {
    const d = this.leg.delta;
    return (typeof d === 'number') ? d.toFixed(2) : '—';
  }

  render() {
    const isBuy = this.leg.direction?.toLowerCase() === 'buy';
    const isCE = this.leg.option_type === 'CE';
    const badgeBg = isBuy ? 'var(--accent-sage-tint)' : 'var(--accent-coral-tint)';
    const badgeColor = isBuy ? 'var(--accent-sage)' : 'var(--accent-coral)';
    const priceVal =
      typeof this.leg.entry_premium === 'number' && this.leg.entry_premium > 0
        ? this.leg.entry_premium
        : '';

    const expiries = this.options.expiries || [];
    const expOptions = expiries.length
      ? expiries
          .map(
            (e) =>
              `<option value="${e.date}" ${e.date === this.leg.expiry_date ? 'selected' : ''}>${e.label}</option>`
          )
          .join('')
      : `<option value="${this.leg.expiry_date || ''}" selected>${this.leg.expiry_date || '—'}</option>`;

    this.container.innerHTML = `
      <div class="leg-card ${isBuy ? 'leg-buy' : 'leg-sell'}" style="display:flex; align-items:center; gap:10px; padding:10px 12px; border:1px solid var(--dl-line); border-radius:var(--radius-sm); flex-wrap:nowrap;">
        <button type="button" class="btn-toggle-direction" title="Click to toggle BUY / SELL" style="flex:0 0 auto; width:32px; height:32px; border-radius:8px; font-weight:700; font-size:0.9rem; background:${badgeBg}; color:${badgeColor}; border:1px solid ${badgeColor}33; cursor:pointer;">${isBuy ? 'B' : 'S'}</button>

        <div class="ce-pe-toggle" style="flex:0 0 auto; display:flex; background:var(--dl-card-2); border-radius:6px; border:1px solid var(--dl-line); padding:2px;">
          <button type="button" class="btn-type-ce" style="padding:4px 9px; font-size:0.74rem; font-weight:700; border:none; border-radius:4px; cursor:pointer; background:${isCE ? 'var(--accent-sage-tint)' : 'transparent'}; color:${isCE ? 'var(--accent-sage)' : 'var(--dl-fg-3)'};">CE</button>
          <button type="button" class="btn-type-pe" style="padding:4px 9px; font-size:0.74rem; font-weight:700; border:none; border-radius:4px; cursor:pointer; background:${!isCE ? 'var(--accent-coral-tint)' : 'transparent'}; color:${!isCE ? 'var(--accent-coral)' : 'var(--dl-fg-3)'};">PE</button>
        </div>

        <select class="input-expiry" title="Expiry" style="flex:0 0 auto; height:32px; max-width:120px; background:var(--dl-card-2); color:var(--dl-fg); border:1px solid var(--dl-line); border-radius:6px; padding:0 6px; font-size:0.76rem; font-family:var(--font-mono);">${expOptions}</select>

        <input type="number" step="50" class="input-strike" value="${this.leg.strike || ''}" title="Strike (snaps to 50)" style="flex:0 0 84px; height:32px; background:var(--dl-card-2); color:var(--text-primary); border:1px solid var(--dl-line); border-radius:6px; padding:0 8px; font-size:0.82rem; font-family:var(--font-mono); font-weight:600;" />

        <div style="flex:0 0 auto; display:flex; align-items:center; background:var(--dl-card-2); border:1px solid var(--dl-line); border-radius:6px; height:32px;">
          <button type="button" class="btn-lot-dec" title="Fewer lots" style="width:24px; height:100%; border:none; background:transparent; color:var(--text-secondary); cursor:pointer; font-weight:700;">−</button>
          <span class="lot-val" style="min-width:38px; text-align:center; font-size:0.76rem; font-family:var(--font-mono); font-weight:600; color:var(--text-primary);">${this.leg.quantity_lots || 1}</span>
          <button type="button" class="btn-lot-inc" title="More lots" style="width:24px; height:100%; border:none; background:transparent; color:var(--text-secondary); cursor:pointer; font-weight:700;">+</button>
        </div>

        <div style="flex:0 0 94px; display:flex; flex-direction:column;">
          <input type="number" step="0.05" min="0" class="input-price" value="${priceVal}" placeholder="—" title="Price per share — real LTP pre-fills when market is open; type your limit price to override" style="width:100%; height:30px; background:var(--dl-input-bg,var(--dl-card-2)); color:var(--text-primary); border:1px solid var(--dl-line); border-radius:6px; padding:0 8px; font-size:0.82rem; font-family:var(--font-mono); font-weight:700; text-align:right;" />
          <span style="font-size:0.6rem; color:var(--text-muted); text-align:right; margin-top:1px;">Price ₹</span>
        </div>

        <div style="flex:0 0 58px; text-align:right;">
          <div class="leg-iv" style="font-family:var(--font-mono); font-size:0.8rem; font-weight:700; color:var(--dl-fg);">${this._fmtIv()}</div>
          <div style="font-size:0.6rem; color:var(--text-muted);">IV</div>
        </div>
        <div style="flex:0 0 58px; text-align:right;">
          <div class="leg-delta" style="font-family:var(--font-mono); font-size:0.8rem; font-weight:700; color:var(--dl-fg);">${this._fmtDelta()}</div>
          <div style="font-size:0.6rem; color:var(--text-muted);">Delta</div>
        </div>

        <button type="button" class="btn-remove-leg" title="Remove leg" style="flex:0 0 auto; margin-left:auto; background:transparent; border:none; color:var(--text-muted); font-size:0.95rem; cursor:pointer; padding:4px 6px; border-radius:4px;" onmouseover="this.style.color='var(--accent-coral)'" onmouseout="this.style.color='var(--text-muted)'">✕</button>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const q = (s) => this.container.querySelector(s);

    q('.btn-toggle-direction')?.addEventListener('click', () => {
      this.leg.direction = this.leg.direction?.toLowerCase() === 'buy' ? 'sell' : 'buy';
      this._structural();
    });
    q('.btn-type-ce')?.addEventListener('click', () => {
      if (this.leg.option_type !== 'CE') {
        this.leg.option_type = 'CE';
        this._structural();
      }
    });
    q('.btn-type-pe')?.addEventListener('click', () => {
      if (this.leg.option_type !== 'PE') {
        this.leg.option_type = 'PE';
        this._structural();
      }
    });
    q('.input-strike')?.addEventListener('change', (e) => {
      const v = Math.round((parseFloat(e.target.value) || 0) / 50) * 50;
      this.leg.strike = v;
      this._structural();
    });
    q('.input-expiry')?.addEventListener('change', (e) => {
      this.leg.expiry_date = e.target.value;
      this._structural();
    });
    q('.btn-lot-dec')?.addEventListener('click', () => {
      const c = this.leg.quantity_lots || 1;
      if (c > 1) {
        this.leg.quantity_lots = c - 1;
        this._structural();
      }
    });
    q('.btn-lot-inc')?.addEventListener('click', () => {
      this.leg.quantity_lots = (this.leg.quantity_lots || 1) + 1;
      this._structural();
    });
    q('.btn-remove-leg')?.addEventListener('click', () => this.options.onRemove?.(this.index));

    // Price edit: update the model + trigger a (debounced) recompute WITHOUT re-rendering,
    // so the field keeps focus while you type. IV/Delta refresh in place via updateComputed().
    const price = q('.input-price');
    if (price) {
      price.addEventListener('input', (e) => {
        const v = parseFloat(e.target.value);
        this.leg.entry_premium = isNaN(v) || v < 0 ? 0 : v;
        this.options.onPriceInput?.(this.index, this.leg);
      });
    }
  }

  _structural() {
    this.render();
    this.options.onChange?.(this.index, this.leg);
  }

  /** Update IV & Delta in place (no re-render → keeps the price input focused). */
  updateComputed({ iv, iv_available, delta } = {}) {
    this.leg.iv = iv;
    this.leg.iv_available = iv_available;
    this.leg.delta = delta;
    const ivEl = this.container.querySelector('.leg-iv');
    const dEl = this.container.querySelector('.leg-delta');
    if (ivEl) ivEl.textContent = this._fmtIv();
    if (dEl) dEl.textContent = this._fmtDelta();
  }

  /** Live quote pre-fill (market open): set price if the user isn't editing it, refresh IV/Delta. */
  updateQuote(quote) {
    if (!quote) return;
    if (quote.available && quote.ltp != null) {
      this.leg.entry_premium = quote.ltp;
      const priceEl = this.container.querySelector('.input-price');
      if (priceEl && document.activeElement !== priceEl) priceEl.value = quote.ltp;
    }
    this.updateComputed({ iv: quote.iv, iv_available: quote.available, delta: quote.delta });
  }
}

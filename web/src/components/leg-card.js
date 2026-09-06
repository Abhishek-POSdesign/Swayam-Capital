/**
 * Single Leg Card — Strategy Builder v2, Option B (Swayam Capital).
 *
 * A leg is a CARD (not a row). Its side (BUY / SELL) is decided by which column it lives in —
 * there is NO Buy/Sell toggle on the card; the "B"/"S" chip is a static accent only.
 *
 * Card layout:
 *   top:   [B|S chip] [CE/PE toggle] [− strike +] [lots ▼] [price + ↻]
 *   stats: Bid · Ask · IV · Δ · OI   (small mono, real-or-'—')
 *
 * Expiry is chosen once globally ("Expiry · all legs"), not per card.
 *
 * No-fake-numbers law:
 *  - Bid/Ask/IV/Delta/OI show '—' when they aren't real; never a placeholder.
 *  - Price is editable: real LTP pre-fills it when the market is open, or ↻ refreshes it;
 *    otherwise you type your (limit) price. IV/Delta are computed from whatever price is set.
 *  - Editing the price updates the stats WITHOUT re-rendering the card, so the input keeps focus.
 */

export class LegCardComponent {
  constructor(container, legData, index, options = {}) {
    this.container = container;
    this.leg = { ...legData };
    this.index = index;
    this.options = options; // { onChange, onPriceInput, onRemove, onRefresh }
  }

  _fmtIv() {
    if (this.leg.iv_available === false) return '—';
    const iv = this.leg.iv;
    return typeof iv === 'number' && iv > 0 ? `${(iv * 100).toFixed(1)}%` : '—';
  }

  _fmtDelta() {
    const d = this.leg.delta;
    return typeof d === 'number' ? (d >= 0 ? `+${d.toFixed(2)}` : d.toFixed(2)) : '—';
  }

  _deltaColor() {
    const d = this.leg.delta;
    if (typeof d !== 'number') return 'var(--dl-fg-3)';
    return d < 0 ? 'var(--accent-coral)' : 'var(--accent-sage)';
  }

  _fmtNum(v, digits = 1) {
    return typeof v === 'number' && !isNaN(v) ? v.toFixed(digits) : '—';
  }

  _fmtOi(v) {
    if (typeof v !== 'number' || isNaN(v) || v <= 0) return '—';
    if (v >= 100000) return `${(v / 100000).toFixed(1)}L`;
    if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
    return String(v);
  }

  _lotOptions() {
    const cur = this.leg.quantity_lots || 1;
    const max = Math.max(15, cur); // free lots: never hard-capped; extend range to hold any value
    let html = '';
    for (let n = 1; n <= max; n++) {
      const label = n === 1 ? '1 lot' : String(n);
      html += `<option value="${n}" ${n === cur ? 'selected' : ''}>${label}</option>`;
    }
    return html;
  }

  render() {
    const isBuy = this.leg.direction?.toLowerCase() === 'buy';
    const isCE = this.leg.option_type === 'CE';
    const sideColor = isBuy ? 'var(--accent-sage)' : 'var(--accent-coral)';
    const sideTint = isBuy ? 'var(--accent-sage-tint)' : 'var(--accent-coral-tint)';
    const priceVal =
      typeof this.leg.entry_premium === 'number' && this.leg.entry_premium > 0
        ? this.leg.entry_premium
        : '';
    const strikeStr = (this.leg.strike || 0).toLocaleString('en-IN');

    this.container.innerHTML = `
      <div class="leg-card ${isBuy ? 'leg-buy' : 'leg-sell'}" style="border:1px solid var(--dl-line); border-radius:10px; padding:12px; display:flex; flex-direction:column; gap:10px;">
        <div class="legcard-top" style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
          <span class="bs-chip" title="${isBuy ? 'Buy leg' : 'Sell leg'}" style="flex:0 0 auto; width:26px; height:26px; display:flex; align-items:center; justify-content:center; border-radius:7px; font-weight:800; font-size:0.8rem; background:${sideTint}; color:${sideColor};">${isBuy ? 'B' : 'S'}</span>

          <div class="ce-pe-toggle" style="flex:0 0 auto; display:flex; background:var(--dl-card-2); border-radius:7px; border:1px solid var(--dl-line); padding:2px;">
            <button type="button" class="btn-type-ce" style="padding:5px 10px; font-size:0.74rem; font-weight:700; border:none; border-radius:5px; cursor:pointer; background:${isCE ? 'var(--accent-sage-tint)' : 'transparent'}; color:${isCE ? 'var(--accent-sage)' : 'var(--dl-fg-3)'};">CE</button>
            <button type="button" class="btn-type-pe" style="padding:5px 10px; font-size:0.74rem; font-weight:700; border:none; border-radius:5px; cursor:pointer; background:${!isCE ? 'var(--accent-coral-tint)' : 'transparent'}; color:${!isCE ? 'var(--accent-coral)' : 'var(--dl-fg-3)'};">PE</button>
          </div>

          <div class="stepper" style="flex:0 0 auto; display:flex; align-items:center; background:var(--dl-card-2); border:1px solid var(--dl-line); border-radius:7px; height:32px;">
            <button type="button" class="btn-strike-dec" title="Strike −50" style="width:26px; height:100%; border:none; background:transparent; color:var(--dl-fg-2); cursor:pointer; font-weight:700; font-size:0.95rem;">−</button>
            <span class="strike-val" style="min-width:58px; text-align:center; font-family:var(--font-mono); font-size:0.82rem; font-weight:700; color:var(--dl-fg);">${strikeStr}</span>
            <button type="button" class="btn-strike-inc" title="Strike +50" style="width:26px; height:100%; border:none; background:transparent; color:var(--dl-fg-2); cursor:pointer; font-weight:700; font-size:0.95rem;">+</button>
          </div>

          <select class="input-lots" title="Lots (free — never restricted)" style="flex:0 0 auto; height:32px; background:var(--dl-card-2); color:var(--dl-fg); border:1px solid var(--dl-line); border-radius:7px; padding:0 6px; font-size:0.78rem; font-family:var(--font-mono); font-weight:600; cursor:pointer;">${this._lotOptions()}</select>

          <div class="price" style="flex:1 1 120px; min-width:112px; display:flex; align-items:center; gap:6px;">
            <input type="number" step="0.05" min="0" class="input-price" value="${priceVal}" placeholder="—" title="Price per share — real LTP pre-fills when the market is open; ↻ refreshes it; type to override" style="flex:1 1 auto; min-width:0; height:32px; background:var(--dl-card-2); color:var(--dl-fg); border:1px solid var(--dl-line); border-radius:7px; padding:0 8px; font-size:0.82rem; font-family:var(--font-mono); font-weight:700; text-align:right;" />
            <button type="button" class="btn-refresh-price" title="Refresh live LTP" style="flex:0 0 auto; width:32px; height:32px; border-radius:7px; border:1px solid var(--dl-line); background:var(--dl-card-2); color:var(--dl-fg-2); cursor:pointer; font-size:0.95rem;" onmouseover="this.style.color='var(--accent-sage)'; this.style.borderColor='var(--accent-sage)';" onmouseout="this.style.color='var(--dl-fg-2)'; this.style.borderColor='var(--dl-line)';">↻</button>
          </div>

          <button type="button" class="btn-remove-leg" title="Remove leg" style="flex:0 0 auto; margin-left:auto; background:transparent; border:none; color:var(--dl-fg-3); font-size:0.95rem; cursor:pointer; padding:4px 6px; border-radius:4px;" onmouseover="this.style.color='var(--accent-coral)'" onmouseout="this.style.color='var(--dl-fg-3)'">✕</button>
        </div>

        <div class="legcard-stats" style="display:flex; gap:8px 16px; flex-wrap:wrap; font-family:var(--font-mono); font-size:0.74rem; color:var(--dl-fg-2); border-top:1px solid var(--dl-line); padding-top:9px;">
          <span>Bid <b class="leg-bid" style="color:var(--dl-fg);">${this._fmtNum(this.leg.bid)}</b></span>
          <span>Ask <b class="leg-ask" style="color:var(--dl-fg);">${this._fmtNum(this.leg.ask)}</b></span>
          <span>IV <b class="leg-iv" style="color:var(--dl-fg);">${this._fmtIv()}</b></span>
          <span>Δ <b class="leg-delta" style="color:${this._deltaColor()};">${this._fmtDelta()}</b></span>
          <span>OI <b class="leg-oi" style="color:var(--dl-fg);">${this._fmtOi(this.leg.oi)}</b></span>
        </div>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const q = (s) => this.container.querySelector(s);

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
    q('.btn-strike-dec')?.addEventListener('click', () => {
      this.leg.strike = Math.max(0, (this.leg.strike || 0) - 50);
      this._structural();
    });
    q('.btn-strike-inc')?.addEventListener('click', () => {
      this.leg.strike = (this.leg.strike || 0) + 50;
      this._structural();
    });
    q('.input-lots')?.addEventListener('change', (e) => {
      this.leg.quantity_lots = parseInt(e.target.value, 10) || 1;
      this._structural();
    });
    q('.btn-refresh-price')?.addEventListener('click', () => this.options.onRefresh?.(this.index));
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
    if (dEl) {
      dEl.textContent = this._fmtDelta();
      dEl.style.color = this._deltaColor();
    }
  }

  /** Live quote fill: set price if the user isn't editing it, refresh Bid/Ask/IV/Delta/OI. */
  updateQuote(quote) {
    if (!quote) return;
    if (quote.available && quote.ltp != null) {
      this.leg.entry_premium = quote.ltp;
      const priceEl = this.container.querySelector('.input-price');
      if (priceEl && document.activeElement !== priceEl) priceEl.value = quote.ltp;
    }
    this.leg.bid = quote.available ? quote.bid : null;
    this.leg.ask = quote.available ? quote.ask : null;
    this.leg.oi = quote.available ? quote.oi : null;
    const bidEl = this.container.querySelector('.leg-bid');
    const askEl = this.container.querySelector('.leg-ask');
    const oiEl = this.container.querySelector('.leg-oi');
    if (bidEl) bidEl.textContent = this._fmtNum(this.leg.bid);
    if (askEl) askEl.textContent = this._fmtNum(this.leg.ask);
    if (oiEl) oiEl.textContent = this._fmtOi(this.leg.oi);
    this.updateComputed({ iv: quote.iv, iv_available: quote.available, delta: quote.delta });
  }
}

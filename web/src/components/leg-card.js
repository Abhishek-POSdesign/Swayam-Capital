/**
 * Single Leg Card — Strategy Builder v2, Option B (Swayam Capital).
 *
 * A leg is a CARD (not a row). Its side (BUY / SELL) is decided by which column it lives in —
 * there is NO Buy/Sell toggle on the card; the "B"/"S" chip is a static accent only.
 *
 * Card layout:
 *   row 1: [B|S chip] [CE/PE] [− strike +] [expiry ▼] [lots ▼]            [✕]
 *   row 2: Price   [ −  |  <big editable price>  |  + ]  [↻]   <source tag>
 *   row 3: Bid · Ask · IV · Δ · OI   (small mono, real-or-'—')
 *
 * Expiry is PER LEG (each leg has its own expiry dropdown) so calendar / diagonal spreads with
 * different expiries per leg are possible. A "Set all legs →" control on the builder is a
 * convenience that stamps one expiry onto every leg at once.
 *
 * No-fake-numbers law:
 *  - Price/Bid/Ask/IV/Delta/OI show '—' when they aren't real; never a fabricated placeholder.
 *  - The price is the real last-traded (or live) price for THIS strike+expiry when available; if
 *    no real price exists, the field is left for you to type and the tag reads "no real price".
 *  - The source tag says exactly where the price came from: live / prev close / your price.
 */

export class LegCardComponent {
  constructor(container, legData, index, options = {}) {
    this.container = container;
    this.leg = { ...legData };
    this.index = index;
    this.options = options; // { onChange, onPriceInput, onRemove, onRefresh, onExpiryChange, expiries }
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

  _expiryOptions() {
    const list = this.options.expiries || [];
    const cur = this.leg.expiry_date || '';
    if (!list.length) return `<option value="${cur}" selected>${cur || '—'}</option>`;
    const opts = list
      .map(
        (e) =>
          `<option value="${e.date}" ${e.date === cur ? 'selected' : ''}>${e.label || e.date}</option>`
      )
      .join('');
    // If the leg's expiry isn't in the loaded list yet, keep it visible so we never lose the pick.
    const known = list.some((e) => e.date === cur);
    return known || !cur ? opts : `<option value="${cur}" selected>${cur}</option>${opts}`;
  }

  _sourceLabel() {
    const s = this.leg.price_source;
    if (s === 'live') return '● live price';
    if (s === 'prev_close') return '● prev close (real last-traded)';
    if (s === 'manual') return '● your typed price';
    if (s === 'unavailable') return '⚠ no real price — type your price';
    return '';
  }

  _sourceColor() {
    const s = this.leg.price_source;
    if (s === 'live') return 'var(--accent-sage)';
    if (s === 'unavailable') return 'var(--accent-amber)';
    return 'var(--dl-fg-3)';
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
        <div class="legcard-top" style="display:flex; align-items:center; gap:7px; flex-wrap:wrap;">
          <span class="bs-chip" title="${isBuy ? 'Buy leg' : 'Sell leg'}" style="flex:0 0 auto; width:24px; height:30px; display:flex; align-items:center; justify-content:center; border-radius:6px; font-weight:800; font-size:0.78rem; background:${sideTint}; color:${sideColor};">${isBuy ? 'B' : 'S'}</span>

          <div class="ce-pe-toggle" style="flex:0 0 auto; display:flex; background:var(--dl-card-2); border-radius:6px; border:1px solid var(--dl-line); padding:2px; height:30px; align-items:center;">
            <button type="button" class="btn-type-ce" style="padding:4px 8px; font-size:0.72rem; font-weight:700; border:none; border-radius:4px; cursor:pointer; background:${isCE ? 'var(--accent-sage-tint)' : 'transparent'}; color:${isCE ? 'var(--accent-sage)' : 'var(--dl-fg-3)'};">CE</button>
            <button type="button" class="btn-type-pe" style="padding:4px 8px; font-size:0.72rem; font-weight:700; border:none; border-radius:4px; cursor:pointer; background:${!isCE ? 'var(--accent-coral-tint)' : 'transparent'}; color:${!isCE ? 'var(--accent-coral)' : 'var(--dl-fg-3)'};">PE</button>
          </div>

          <div class="stepper" style="flex:0 0 auto; display:flex; align-items:center; background:var(--dl-card-2); border:1px solid var(--dl-line); border-radius:6px; height:30px;">
            <button type="button" class="btn-strike-dec" title="Strike −50" style="width:24px; height:100%; border:none; background:transparent; color:var(--dl-fg-2); cursor:pointer; font-weight:700; font-size:0.9rem;">−</button>
            <span class="strike-val" style="min-width:52px; text-align:center; font-family:var(--font-mono); font-size:0.8rem; font-weight:700; color:var(--dl-fg);">${strikeStr}</span>
            <button type="button" class="btn-strike-inc" title="Strike +50" style="width:24px; height:100%; border:none; background:transparent; color:var(--dl-fg-2); cursor:pointer; font-weight:700; font-size:0.9rem;">+</button>
          </div>

          <select class="input-expiry" title="Expiry for THIS leg — change per leg to build calendar / diagonal spreads" style="flex:0 0 auto; height:30px; max-width:120px; background:var(--dl-card-2); color:var(--dl-fg); border:1px solid var(--dl-line); border-radius:6px; padding:0 5px; font-size:0.72rem; font-family:var(--font-mono); font-weight:600; cursor:pointer;">${this._expiryOptions()}</select>

          <select class="input-lots" title="Lots (free — never restricted)" style="flex:0 0 auto; height:30px; background:var(--dl-card-2); color:var(--dl-fg); border:1px solid var(--dl-line); border-radius:6px; padding:0 5px; font-size:0.76rem; font-family:var(--font-mono); font-weight:600; cursor:pointer;">${this._lotOptions()}</select>

          <!-- Price: compact inline stepper (− price +), Sensibull-style — no extra row -->
          <div class="price-ctl" title="Price for this leg — real last-traded fills it; − / + or type to override" style="flex:0 0 auto; display:flex; align-items:stretch; height:30px; background:var(--dl-card-2); border:1px solid var(--dl-line); border-radius:6px; overflow:hidden;">
            <button type="button" class="btn-price-dec" title="−0.05" style="flex:0 0 26px; border:none; background:transparent; color:var(--dl-fg-2); cursor:pointer; font-size:1.05rem; font-weight:700; line-height:1;">−</button>
            <input type="number" step="0.05" min="0" class="input-price" value="${priceVal}" placeholder="₹—" style="flex:0 0 62px; width:62px; min-width:0; border:none; border-left:1px solid var(--dl-line); border-right:1px solid var(--dl-line); background:transparent; color:var(--dl-fg); text-align:center; font-family:var(--font-mono); font-weight:700; font-size:0.86rem; padding:0 2px;" />
            <button type="button" class="btn-price-inc" title="+0.05" style="flex:0 0 26px; border:none; background:transparent; color:var(--dl-fg-2); cursor:pointer; font-size:1.05rem; font-weight:700; line-height:1;">+</button>
          </div>

          <button type="button" class="btn-refresh-price" title="Refresh real price for this strike + expiry" style="flex:0 0 auto; width:30px; height:30px; border-radius:6px; border:1px solid var(--dl-line); background:var(--dl-card-2); color:var(--dl-fg-2); cursor:pointer; font-size:0.9rem;" onmouseover="this.style.color='var(--accent-sage)'; this.style.borderColor='var(--accent-sage)';" onmouseout="this.style.color='var(--dl-fg-2)'; this.style.borderColor='var(--dl-line)';">↻</button>

          <button type="button" class="btn-remove-leg" title="Remove leg" style="flex:0 0 auto; margin-left:auto; background:transparent; border:none; color:var(--dl-fg-3); font-size:0.95rem; cursor:pointer; padding:4px 6px; border-radius:4px;" onmouseover="this.style.color='var(--accent-coral)'" onmouseout="this.style.color='var(--dl-fg-3)'">✕</button>
        </div>

        <div class="legcard-stats" style="display:flex; gap:6px 14px; flex-wrap:wrap; align-items:center; font-family:var(--font-mono); font-size:0.72rem; color:var(--dl-fg-2); border-top:1px solid var(--dl-line); padding-top:7px;">
          <span>Bid <b class="leg-bid" style="color:var(--dl-fg);">${this._fmtNum(this.leg.bid)}</b></span>
          <span>Ask <b class="leg-ask" style="color:var(--dl-fg);">${this._fmtNum(this.leg.ask)}</b></span>
          <span>IV <b class="leg-iv" style="color:var(--dl-fg);">${this._fmtIv()}</b></span>
          <span>Δ <b class="leg-delta" style="color:${this._deltaColor()};">${this._fmtDelta()}</b></span>
          <span>OI <b class="leg-oi" style="color:var(--dl-fg);">${this._fmtOi(this.leg.oi)}</b></span>
          <span class="price-src" style="margin-left:auto; color:${this._sourceColor()};">${this._sourceLabel()}</span>
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
    q('.input-expiry')?.addEventListener('change', (e) => {
      this.options.onExpiryChange?.(this.index, e.target.value);
    });
    q('.input-lots')?.addEventListener('change', (e) => {
      this.leg.quantity_lots = parseInt(e.target.value, 10) || 1;
      this._structural();
    });
    q('.btn-refresh-price')?.addEventListener('click', () => this.options.onRefresh?.(this.index));
    q('.btn-remove-leg')?.addEventListener('click', () => this.options.onRemove?.(this.index));

    q('.btn-price-dec')?.addEventListener('click', () => this._nudgePrice(-0.05));
    q('.btn-price-inc')?.addEventListener('click', () => this._nudgePrice(0.05));

    // Price edit: update the model + trigger a (debounced) recompute WITHOUT re-rendering,
    // so the field keeps focus while you type. IV/Delta refresh in place via updateComputed().
    const price = q('.input-price');
    if (price) {
      price.addEventListener('input', (e) => {
        const v = parseFloat(e.target.value);
        this.leg.entry_premium = isNaN(v) || v < 0 ? 0 : v;
        this.leg.price_source = 'manual';
        this._refreshSourceTag();
        this.options.onPriceInput?.(this.index, this.leg);
      });
    }
  }

  /** Step the price by delta, rounded to the 0.05 tick, and recompute (keeps card in place). */
  _nudgePrice(delta) {
    const cur = typeof this.leg.entry_premium === 'number' ? this.leg.entry_premium : 0;
    const v = Math.max(0, Math.round((cur + delta) * 20) / 20);
    this.leg.entry_premium = v;
    this.leg.price_source = 'manual';
    const inp = this.container.querySelector('.input-price');
    if (inp) inp.value = v;
    this._refreshSourceTag();
    this.options.onPriceInput?.(this.index, this.leg);
  }

  _refreshSourceTag() {
    const el = this.container.querySelector('.price-src');
    if (el) {
      el.textContent = this._sourceLabel();
      el.style.color = this._sourceColor();
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

  /**
   * Real quote fill: set price from the real last-traded/live value if the user isn't editing it,
   * refresh Bid/Ask/IV/Delta/OI, and label where the price came from. When no real price exists,
   * we leave the field for the user and flag it "no real price" — never a fabricated number.
   */
  updateQuote(quote) {
    if (!quote) return;
    this.leg.price_source = quote.source || (quote.available ? 'live' : 'unavailable');
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
    this._refreshSourceTag();
    this.updateComputed({ iv: quote.iv, iv_available: quote.available, delta: quote.delta });
  }
}

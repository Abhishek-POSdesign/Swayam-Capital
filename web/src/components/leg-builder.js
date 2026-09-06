/**
 * Multi-leg Builder — Strategy Builder v2, Option B (Swayam Capital).
 *
 * Legs are cards in two columns: BUY on the left, SELL on the right. A leg's side is decided by
 * its column — you add legs with "+ Add Buy Leg" / "+ Add Sell Leg"; there is no Buy/Sell toggle.
 * Expiry is PER LEG (each card has its own expiry) so calendar / diagonal spreads work; the
 * "Set all legs →" selector is a convenience that stamps one expiry onto every leg at once.
 *
 * Real prices only: the real last-traded (or live) price for each leg's strike+expiry pre-fills the
 * card (or on ↻ refresh); IV/Delta are computed from it; Bid/Ask/OI come straight from the chain.
 * No fabricated prices — if none is available the card says so and you type your own.
 * Lots are free (never restricted). Net Debit/Credit stays in sync with the live compute.
 */

import { api } from '../api.js';
import { LegCardComponent } from './leg-card.js';

export class LegBuilderComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onLegsUpdated, currentSpot }
    this.legs = [];
    this.legCards = [];
    this.expiries = [];
    this.weeklyExpiry = null;
    this.globalExpiry = null;
    this._expiryUserChosen = false; // becomes true once the user picks from the global selector
    this._priceDebounce = null;
    this._loadExpiries();
  }

  async _loadExpiries() {
    try {
      const res = await api.getExpiries();
      this.expiries = res.expiries || [];
      this.weeklyExpiry = res.weekly_expiry || this.expiries[0]?.date || null;

      const before = this.globalExpiry;
      this._reconcileExpiry();
      if (this.legs.length) {
        this.render(); // repopulate the selector + reflect any snap once real expiries arrive
        // If the reconcile snapped to a different (real) expiry, refresh quotes + recompute so the
        // payoff chart's days-to-expiry follows the real leg expiry, not the preset's guess.
        if (this.globalExpiry !== before) {
          this.fetchQuotesForAllLegs().finally(() => this.options.onLegsUpdated?.(this.legs));
        }
      }
    } catch (_) {
      this.expiries = [];
    }
  }

  /** The expiry all legs share, else the weekly, else the first available. */
  _deriveGlobalExpiry() {
    const set = new Set(this.legs.map((l) => l.expiry_date).filter(Boolean));
    if (set.size === 1) return [...set][0];
    return this.weeklyExpiry || this.expiries[0]?.date || this.legs[0]?.expiry_date || null;
  }

  /**
   * Repair each leg's expiry WITHOUT collapsing distinct per-leg expiries.
   *
   * Per-leg expiry is real now (calendar / diagonal spreads). This only *fills or fixes* a leg
   * that has no expiry, or a stale placeholder expiry that isn't a real NIFTY expiry (e.g. a
   * preset's pre-load guess). Legs flagged `back_month` (the far leg of a calendar preset) get the
   * SECOND real expiry; everything else gets the nearest. A valid per-leg pick is always kept.
   * The "Set all legs →" selector is the only thing that deliberately equalises every leg.
   */
  _reconcileExpiry() {
    const validDates = this.expiries.length ? new Set(this.expiries.map((e) => e.date)) : null;
    const nearest = this.weeklyExpiry || this.expiries[0]?.date || null;
    const second = this.expiries[1]?.date || nearest;
    if (!this.globalExpiry) this.globalExpiry = nearest || this._deriveGlobalExpiry();

    this.legs.forEach((l) => {
      const missing = !l.expiry_date;
      const stale = validDates && l.expiry_date && !validDates.has(l.expiry_date);
      if (missing || stale) {
        l.expiry_date = l.back_month ? second : nearest;
      }
      if ('back_month' in l) delete l.back_month; // one-shot hint from presets
    });
  }

  setLegs(legs) {
    this.legs = legs.map((l) => ({ ...l }));
    this._reconcileExpiry();
    this.render();
    this.fetchQuotesForAllLegs().finally(() => this.options.onLegsUpdated?.(this.legs));
  }

  getLegs() {
    return this.legs;
  }

  _netInr() {
    let net = 0;
    this.legs.forEach((leg) => {
      const isBuy = leg.direction?.toLowerCase() === 'buy';
      const contracts = (leg.quantity_lots || 1) * (leg.lot_size || 75);
      const val = (leg.entry_premium || 0) * contracts;
      net += isBuy ? -val : val;
    });
    return net;
  }

  _updateNetDisplay() {
    const net = this._netInr();
    const isCredit = net >= 0;
    const el = this.container.querySelector('#leg-net-value');
    const lbl = this.container.querySelector('#leg-net-label');
    if (el) {
      el.textContent = `₹${Math.abs(net).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      el.style.color = isCredit ? 'var(--accent-sage)' : 'var(--accent-coral)';
    }
    if (lbl) lbl.textContent = isCredit ? 'Net Credit' : 'Net Debit';
  }

  _expiryOptions() {
    if (!this.expiries.length) {
      const cur = this.globalExpiry || '';
      return `<option value="${cur}" selected>${cur || '—'}</option>`;
    }
    return this.expiries
      .map(
        (e) =>
          `<option value="${e.date}" ${e.date === this.globalExpiry ? 'selected' : ''}>${e.label}</option>`
      )
      .join('');
  }

  render() {
    const buy = this.legs
      .map((leg, idx) => ({ leg, idx }))
      .filter((i) => i.leg.direction?.toLowerCase() === 'buy');
    const sell = this.legs
      .map((leg, idx) => ({ leg, idx }))
      .filter((i) => i.leg.direction?.toLowerCase() === 'sell');
    const net = this._netInr();
    const isCredit = net >= 0;
    const netStr = `₹${Math.abs(net).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const addBtn = (id, label, color) =>
      `<button type="button" id="${id}" style="width:100%; height:34px; border:1px dashed var(--dl-line); background:transparent; color:var(--dl-fg-2); border-radius:9px; font-size:0.78rem; font-weight:600; cursor:pointer; transition:all var(--dur-fast) ease;" onmouseover="this.style.borderColor='${color}'; this.style.color='${color}';" onmouseout="this.style.borderColor='var(--dl-line)'; this.style.color='var(--dl-fg-2)';">${label}</button>`;

    this.container.innerHTML = `
      <div class="leg-builder-container" style="display:flex; flex-direction:column; gap:14px; background:var(--dl-card); padding:16px 18px; border-radius:var(--radius-card); border:1px solid var(--dl-line);">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
          <span class="eyebrow" style="color:var(--dl-fg-3);">STRATEGY LEGS (${this.legs.length})</span>
          <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap;">
            <label style="display:flex; align-items:center; gap:7px; font-size:0.74rem; color:var(--dl-fg-3);">
              <span style="text-transform:uppercase; letter-spacing:0.05em; font-weight:700;">Set all legs →</span>
              <select id="global-expiry" title="Stamps this expiry onto EVERY leg at once. For a calendar/diagonal spread, leave this and set each leg's own expiry on its card instead." style="height:30px; background:var(--dl-card-2); color:var(--dl-fg); border:1px solid var(--dl-line); border-radius:7px; padding:0 8px; font-size:0.76rem; font-family:var(--font-mono); font-weight:600; cursor:pointer;">${this._expiryOptions()}</select>
            </label>
            <div style="display:flex; align-items:baseline; gap:7px;">
              <span id="leg-net-label" style="font-size:0.78rem; color:var(--dl-fg-3); font-weight:500;">${isCredit ? 'Net Credit' : 'Net Debit'}</span>
              <span id="leg-net-value" style="font-family:var(--font-serif); font-size:1.3rem; font-weight:700; color:${isCredit ? 'var(--accent-sage)' : 'var(--accent-coral)'};">${netStr}</span>
            </div>
          </div>
        </div>

        <div class="bscols" style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
          <div class="bscol" style="display:flex; flex-direction:column; gap:10px;">
            <div class="bscol-head buy" style="font-size:0.7rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; padding:7px 11px; border-radius:7px; background:var(--accent-sage-tint); color:var(--accent-sage);">▲ Buy legs</div>
            <div id="buy-legs-container" style="display:flex; flex-direction:column; gap:10px;"></div>
            ${addBtn('btn-add-buy-leg', '+ Add Buy Leg', 'var(--accent-sage)')}
          </div>
          <div class="bscol" style="display:flex; flex-direction:column; gap:10px;">
            <div class="bscol-head sell" style="font-size:0.7rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; padding:7px 11px; border-radius:7px; background:var(--accent-coral-tint); color:var(--accent-coral);">▼ Sell legs</div>
            <div id="sell-legs-container" style="display:flex; flex-direction:column; gap:10px;"></div>
            ${addBtn('btn-add-sell-leg', '+ Add Sell Leg', 'var(--accent-coral)')}
          </div>
        </div>

        <div style="font-size:0.72rem; color:var(--dl-fg-3); border-top:1px solid var(--dl-line); padding-top:10px;">
          Buys-first sequencing happens at <b style="color:var(--dl-fg-2);">execution</b>, not here.
        </div>
      </div>
    `;

    const buyC = this.container.querySelector('#buy-legs-container');
    const sellC = this.container.querySelector('#sell-legs-container');
    this.legCards = [];

    const mount = (parent, { leg, idx }) => {
      const wrap = document.createElement('div');
      parent.appendChild(wrap);
      const card = new LegCardComponent(wrap, leg, idx, {
        expiries: this.expiries,
        onChange: (i, l) => this.handleStructuralChange(i, l),
        onPriceInput: (i, l) => this.handlePriceInput(i, l),
        onRefresh: (i) => this.handleRefreshLeg(i),
        onRemove: (i) => this.handleLegRemove(i),
        onExpiryChange: (i, exp) => this.handleLegExpiryChange(i, exp),
      });
      card.render();
      this.legCards.push({ idx, card });
    };
    buy.forEach((x) => mount(buyC, x));
    sell.forEach((x) => mount(sellC, x));

    this.container
      .querySelector('#btn-add-buy-leg')
      ?.addEventListener('click', () => this.handleAddLeg('buy'));
    this.container
      .querySelector('#btn-add-sell-leg')
      ?.addEventListener('click', () => this.handleAddLeg('sell'));
    this.container
      .querySelector('#global-expiry')
      ?.addEventListener('change', (e) => this.handleGlobalExpiryChange(e.target.value));
  }

  /** "Set all legs →": stamp ONE expiry onto every leg at once (convenience), then re-price all. */
  handleGlobalExpiryChange(expiry) {
    if (!expiry) return;
    this._expiryUserChosen = true;
    this.globalExpiry = expiry;
    this.legs.forEach((l) => (l.expiry_date = expiry));
    this.render();
    this.fetchQuotesForAllLegs().finally(() => this.options.onLegsUpdated?.(this.legs));
  }

  /** Per-leg expiry change (for calendar / diagonal spreads) — re-price only that leg. */
  handleLegExpiryChange(idx, expiry) {
    if (!expiry || !this.legs[idx]) return;
    this.legs[idx].expiry_date = expiry;
    this.legs[idx].price_source = undefined; // force a fresh real quote for the new expiry
    this.render();
    this.fetchQuoteForLeg(idx).finally(() => this.options.onLegsUpdated?.(this.legs));
  }

  handleStructuralChange(idx, leg) {
    this.legs[idx] = leg;
    this.render();
    this.fetchQuoteForLeg(idx).finally(() => this.options.onLegsUpdated?.(this.legs));
  }

  handlePriceInput(idx, leg) {
    this.legs[idx] = leg;
    this._updateNetDisplay();
    if (this._priceDebounce) clearTimeout(this._priceDebounce);
    this._priceDebounce = setTimeout(() => this.options.onLegsUpdated?.(this.legs), 350);
  }

  async handleRefreshLeg(idx) {
    await this.fetchQuoteForLeg(idx);
    this._updateNetDisplay();
    this.options.onLegsUpdated?.(this.legs);
  }

  handleLegRemove(idx) {
    this.legs.splice(idx, 1);
    this.render();
    this.options.onLegsUpdated?.(this.legs);
  }

  handleAddLeg(direction) {
    const spot = this.options.currentSpot || 24850;
    const base = Math.round(spot / 50) * 50;
    this.legs.push({
      strike: base,
      option_type: direction === 'sell' ? 'CE' : 'PE',
      direction,
      quantity_lots: 1,
      lot_size: 75,
      expiry_date: this.globalExpiry || this.weeklyExpiry || this.expiries[0]?.date || '',
      entry_premium: 0,
    });
    this.render();
    this.fetchQuoteForLeg(this.legs.length - 1).finally(() => this.options.onLegsUpdated?.(this.legs));
  }

  /** Update per-leg IV & Delta in place from a compute response's per_leg array. */
  updateGreeks(perLeg) {
    if (!Array.isArray(perLeg)) return;
    perLeg.forEach((pg, i) => {
      if (!this.legs[i]) return;
      this.legs[i].iv = pg.iv;
      this.legs[i].iv_available = pg.iv_available;
      this.legs[i].delta = pg.delta;
      const match = this.legCards.find((c) => c.idx === i);
      match?.card?.updateComputed({ iv: pg.iv, iv_available: pg.iv_available, delta: pg.delta });
    });
  }

  async fetchQuotesForAllLegs() {
    for (let i = 0; i < this.legs.length; i++) await this.fetchQuoteForLeg(i);
  }

  /** Pre-fill a leg's real LTP + Bid/Ask/OI when available. No fake fill when unavailable. */
  async fetchQuoteForLeg(index) {
    const leg = this.legs[index];
    if (!leg || !leg.strike || !leg.expiry_date || !leg.option_type) return;
    try {
      const quote = await api.getOptionQuote({
        strike: leg.strike,
        expiry: leg.expiry_date,
        type: leg.option_type,
      });
      const match = this.legCards.find((c) => c.idx === index);
      if (quote && quote.available && quote.ltp != null) {
        leg.entry_premium = quote.ltp;
        leg.bid = quote.bid;
        leg.ask = quote.ask;
        leg.oi = quote.oi;
      }
      match?.card?.updateQuote(quote);
    } catch (_) {
      // Quiet: unavailable stays unavailable (user types a price); never a fake fill.
    }
  }
}

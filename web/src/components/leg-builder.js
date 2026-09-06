/**
 * Multi-leg Builder — Strategy Builder v2 (Swayam Capital).
 *
 * Renders the leg rows (Buys first, margin-safe), fetches real per-leg expiries, pre-fills real
 * LTP when the market is open, and keeps Net Debit/Credit + per-leg IV/Delta in sync with the
 * live compute. Price edits recompute without re-rendering (focus preserved). Lots are free.
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
    this._priceDebounce = null;
    this._loadExpiries();
  }

  async _loadExpiries() {
    try {
      const res = await api.getExpiries();
      this.expiries = res.expiries || [];
      this.weeklyExpiry = res.weekly_expiry || this.expiries[0]?.date || null;
      if (this.legs.length) this.render(); // repopulate dropdowns once real expiries arrive
    } catch (_) {
      this.expiries = [];
    }
  }

  setLegs(legs) {
    this.legs = legs.map((l) => ({ ...l }));
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
    if (lbl) lbl.textContent = isCredit ? 'Net Credit:' : 'Net Debit:';
  }

  render() {
    const buy = this.legs.map((leg, idx) => ({ leg, idx })).filter((i) => i.leg.direction?.toLowerCase() === 'buy');
    const sell = this.legs.map((leg, idx) => ({ leg, idx })).filter((i) => i.leg.direction?.toLowerCase() === 'sell');
    const net = this._netInr();
    const isCredit = net >= 0;
    const netStr = `₹${Math.abs(net).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    this.container.innerHTML = `
      <div class="leg-builder-container" style="display:flex; flex-direction:column; gap:12px; background:var(--dl-card); padding:16px 18px; border-radius:var(--radius-card); border:1px solid var(--dl-line); overflow-x:auto;">
        <div style="display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px;">
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span class="eyebrow" style="color:var(--text-muted);">STRATEGY LEGS (${this.legs.length})</span>
            ${buy.length && sell.length ? `<span style="display:inline-flex; align-items:center; gap:4px; height:20px; padding:0 8px; border-radius:999px; background:var(--accent-sage-tint); color:var(--accent-sage); border:1px solid rgba(134,171,146,0.3); font-size:0.66rem; font-weight:600;">↑ Buys execute first (margin-safe)</span>` : ''}
          </div>
          <div style="display:flex; align-items:baseline; gap:6px;">
            <span id="leg-net-label" style="font-size:0.8rem; color:var(--text-muted); font-weight:500;">${isCredit ? 'Net Credit:' : 'Net Debit:'}</span>
            <span id="leg-net-value" style="font-family:var(--font-serif); font-size:1.3rem; font-weight:700; color:${isCredit ? 'var(--accent-sage)' : 'var(--accent-coral)'};">${netStr}</span>
          </div>
        </div>

        <div id="buy-legs-container" style="display:flex; flex-direction:column; gap:8px;"></div>
        <div id="sell-legs-container" style="display:flex; flex-direction:column; gap:8px;"></div>

        <button type="button" id="btn-add-leg" style="width:100%; height:36px; border:1px dashed var(--dl-line); background:transparent; color:var(--dl-fg-2); border-radius:var(--radius-card); font-size:0.82rem; font-weight:600; cursor:pointer;" onmouseover="this.style.borderColor='var(--accent-sage)'; this.style.color='var(--accent-sage)';" onmouseout="this.style.borderColor='var(--dl-line)'; this.style.color='var(--dl-fg-2)';">+ Add Leg</button>
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
        onRemove: (i) => this.handleLegRemove(i),
      });
      card.render();
      this.legCards.push({ idx, card });
    };
    buy.forEach((x) => mount(buyC, x));
    sell.forEach((x) => mount(sellC, x));

    this.container.querySelector('#btn-add-leg')?.addEventListener('click', () => this.handleAddLeg());
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

  handleLegRemove(idx) {
    this.legs.splice(idx, 1);
    this.render();
    this.options.onLegsUpdated?.(this.legs);
  }

  handleAddLeg() {
    const spot = this.options.currentSpot || 24850;
    const base = Math.round(spot / 50) * 50;
    this.legs.push({
      strike: base,
      option_type: 'PE',
      direction: 'buy',
      quantity_lots: 1,
      lot_size: 75,
      expiry_date: this.weeklyExpiry || this.expiries[0]?.date || '',
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

  /** Pre-fill a leg's real LTP when the market is open. Does not itself trigger a recompute —
   * callers own that so we don't storm the compute endpoint. No fake fill when unavailable. */
  async fetchQuoteForLeg(index) {
    const leg = this.legs[index];
    if (!leg || !leg.strike || !leg.expiry_date || !leg.option_type) return;
    try {
      const quote = await api.getOptionQuote({ strike: leg.strike, expiry: leg.expiry_date, type: leg.option_type });
      if (quote && quote.available && quote.ltp != null) {
        leg.entry_premium = quote.ltp;
        const match = this.legCards.find((c) => c.idx === index);
        match?.card?.updateQuote(quote);
      }
    } catch (_) {
      // Quiet: unavailable stays unavailable (user types a price); never a fake fill.
    }
  }
}

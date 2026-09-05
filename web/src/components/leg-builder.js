/**
 * Multi-leg Builder Container for Swayam Capital (BUILD-10).
 *
 * Renders list of option legs, enforces BUY-first visual ordering with
 * margin safety divider, displays Net Debit/Credit, and manages live quote updates.
 */

import { api } from '../api.js';
import { LegCardComponent } from './leg-card.js';
import { getNextWeeklyThursday } from './preset-bar.js';

export class LegBuilderComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onLegsUpdated, currentSpot }
    this.legs = [];
    this.quotePollTimer = null;
    this.legCards = [];
  }

  setLegs(legs) {
    this.legs = legs.map((l) => ({ ...l }));
    this.render();
    this.fetchQuotesForAllLegs();
    if (this.options.onLegsUpdated) {
      this.options.onLegsUpdated(this.legs);
    }
  }

  getLegs() {
    return this.legs;
  }

  render() {
    const buyLegsWithIdx = this.legs
      .map((leg, idx) => ({ leg, idx }))
      .filter((item) => item.leg.direction?.toLowerCase() === 'buy');

    const sellLegsWithIdx = this.legs
      .map((leg, idx) => ({ leg, idx }))
      .filter((item) => item.leg.direction?.toLowerCase() === 'sell');

    // Compute Net Debit / Credit
    let netInr = 0;
    this.legs.forEach((leg) => {
      const isBuy = leg.direction?.toLowerCase() === 'buy';
      const contracts = (leg.quantity_lots || 1) * (leg.lot_size || 75);
      const val = (leg.entry_premium || 0) * contracts;
      netInr += isBuy ? -val : val;
    });

    const isCredit = netInr >= 0;
    const netLabel = isCredit ? 'Net Credit' : 'Net Debit';
    const netColor = isCredit ? 'var(--accent-sage)' : 'var(--accent-coral)';
    const absNet = Math.abs(netInr).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    this.container.innerHTML = `
      <div class="leg-builder-container" style="display: flex; flex-direction: column; gap: 14px; background: var(--dl-card); padding: 18px 20px; border-radius: var(--radius-card); border: 1px solid var(--dl-line);">
        <!-- Header: Title + Margin Pill + Net Debit/Credit -->
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span class="eyebrow" style="color: var(--text-muted);">STRATEGY LEGS (${this.legs.length})</span>
            ${buyLegsWithIdx.length > 0 && sellLegsWithIdx.length > 0 ? `
              <span class="margin-safety-pill" style="
                display: inline-flex;
                align-items: center;
                gap: 4px;
                height: 20px;
                line-height: 20px;
                padding: 0 8px;
                border-radius: 999px;
                background: var(--accent-sage-tint);
                color: var(--accent-sage);
                border: 1px solid rgba(134,171,146,0.3);
                font-size: 0.68rem;
                font-weight: 600;
              ">
                ↑ Buys execute first (margin-safe)
              </span>
            ` : ''}
          </div>
          <div style="display: flex; align-items: baseline; gap: 6px;">
            <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 500;">${netLabel}:</span>
            <span style="font-family: var(--font-serif); font-size: 1.35rem; font-weight: 700; color: ${netColor};">
              ₹${absNet}
            </span>
          </div>
        </div>

        <!-- Legs Cards Container (Unconditional single column stack) -->
        <div id="legs-cards-wrapper" class="legs-stack-1col" style="display: flex; flex-direction: column; gap: 10px;">
          <!-- Buy Legs Container -->
          <div id="buy-legs-container" style="display: flex; flex-direction: column; gap: 10px;"></div>

          <!-- Sell Legs Container -->
          <div id="sell-legs-container" style="display: flex; flex-direction: column; gap: 10px;"></div>
        </div>

        <!-- Add Leg Button -->
        <button
          type="button"
          id="btn-add-leg"
          style="
            width: 100%;
            height: 38px;
            border: 1px dashed var(--dl-line);
            background: transparent;
            color: var(--dl-fg-2);
            border-radius: var(--radius-card);
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            transition: all var(--dur-fast) ease;
          "
          onmouseover="this.style.borderColor='var(--accent-sage)'; this.style.color='var(--accent-sage)';"
          onmouseout="this.style.borderColor='var(--dl-line)'; this.style.color='var(--dl-fg-2)';"
        >
          + Add Leg
        </button>
      </div>
    `;

    // Render Buy Cards
    const buyContainer = this.container.querySelector('#buy-legs-container');
    const sellContainer = this.container.querySelector('#sell-legs-container');
    this.legCards = [];

    buyLegsWithIdx.forEach(({ leg, idx }) => {
      const wrap = document.createElement('div');
      buyContainer.appendChild(wrap);
      const card = new LegCardComponent(wrap, leg, idx, {
        onChange: (legIdx, updatedLeg) => this.handleLegChange(legIdx, updatedLeg),
        onRemove: (legIdx) => this.handleLegRemove(legIdx),
      });
      card.render();
      this.legCards.push({ idx, card });
    });

    // Render Sell Cards
    sellLegsWithIdx.forEach(({ leg, idx }) => {
      const wrap = document.createElement('div');
      sellContainer.appendChild(wrap);
      const card = new LegCardComponent(wrap, leg, idx, {
        onChange: (legIdx, updatedLeg) => this.handleLegChange(legIdx, updatedLeg),
        onRemove: (legIdx) => this.handleLegRemove(legIdx),
      });
      card.render();
      this.legCards.push({ idx, card });
    });

    // Attach Add Leg Event
    const btnAdd = this.container.querySelector('#btn-add-leg');
    if (btnAdd) {
      btnAdd.addEventListener('click', () => this.handleAddLeg());
    }
  }

  updateGreeks(perLegGreeks) {
    if (!perLegGreeks || !Array.isArray(perLegGreeks)) return;
    perLegGreeks.forEach((pg, i) => {
      if (this.legs[i]) {
        this.legs[i].delta = pg.delta;
        this.legs[i].theta = pg.theta;
        this.legs[i].vega = pg.vega;
        this.legs[i].gamma = pg.gamma;
      }
    });
    this.legCards.forEach(({ idx, card }) => {
      const g = this.legs[idx];
      if (g && card && card.updateGreeks) {
        card.updateGreeks({
          delta: g.delta,
          theta: g.theta,
          vega: g.vega,
        });
      }
    });
  }

  handleLegChange(idx, updatedLeg) {
    this.legs[idx] = updatedLeg;
    this.render();
    this.fetchQuoteForLeg(idx);
    if (this.options.onLegsUpdated) {
      this.options.onLegsUpdated(this.legs);
    }
  }

  handleLegRemove(idx) {
    this.legs.splice(idx, 1);
    this.render();
    if (this.options.onLegsUpdated) {
      this.options.onLegsUpdated(this.legs);
    }
  }

  handleAddLeg() {
    const spot = this.options.currentSpot || 24850;
    const base = Math.round(spot / 50) * 50;
    const newLeg = {
      strike: base,
      option_type: 'PE',
      direction: 'buy',
      quantity_lots: 1,
      lot_size: 75,
      expiry_date: getNextWeeklyThursday(),
      entry_premium: 80.0,
    };
    this.legs.push(newLeg);
    this.render();
    this.fetchQuoteForLeg(this.legs.length - 1);
    if (this.options.onLegsUpdated) {
      this.options.onLegsUpdated(this.legs);
    }
  }

  async fetchQuotesForAllLegs() {
    for (let i = 0; i < this.legs.length; i++) {
      await this.fetchQuoteForLeg(i);
    }
  }

  async fetchQuoteForLeg(index) {
    const leg = this.legs[index];
    if (!leg || !leg.strike || !leg.expiry_date || !leg.option_type) return;

    try {
      const quote = await api.getOptionQuote({
        strike: leg.strike,
        expiry: leg.expiry_date,
        type: leg.option_type,
      });

      if (quote && quote.ltp) {
        leg.entry_premium = quote.ltp;
        leg.delta = quote.delta;
        leg.theta = quote.theta;
        leg.vega = quote.vega;
        leg.iv = quote.iv;

        // Update card if mounted
        const match = this.legCards.find((c) => c.idx === index);
        if (match && match.card) {
          match.card.updateQuote(quote);
        }
      }
    } catch (e) {
      // Quiet fail if quote API unavailable
    }
  }
}

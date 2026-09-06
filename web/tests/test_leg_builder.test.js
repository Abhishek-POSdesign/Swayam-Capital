import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { LegBuilderComponent } from '../src/components/leg-builder.js';

describe('LegBuilderComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('groups BUY legs in the left column and SELL legs in the right column', () => {
    const builder = new LegBuilderComponent(container);
    builder.setLegs([
      { strike: 24700, option_type: 'PE', direction: 'sell', quantity_lots: 1, lot_size: 75, entry_premium: 45 },
      { strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1, lot_size: 75, entry_premium: 110 },
    ]);

    expect(container.textContent).toContain('STRATEGY LEGS (2)');
    expect(container.textContent).toContain('Buys-first sequencing happens at');
    expect(container.textContent).toContain('Buy legs');
    expect(container.textContent).toContain('Sell legs');
    // Global expiry selector present (per-card expiry removed in Option B)
    expect(container.querySelector('#global-expiry')).not.toBeNull();

    const buyMount = container.querySelector('#buy-legs-container');
    const sellMount = container.querySelector('#sell-legs-container');

    expect(buyMount.children.length).toBe(1);
    expect(sellMount.children.length).toBe(1);
  });

  it('calculates Net Debit correctly for debit spread', () => {
    const builder = new LegBuilderComponent(container);
    builder.setLegs([
      { strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1, lot_size: 75, entry_premium: 100 },
      { strike: 24700, option_type: 'PE', direction: 'sell', quantity_lots: 1, lot_size: 75, entry_premium: 40 },
    ]);

    // Net Debit = (100 - 40) * 75 = 60 * 75 = 4500
    expect(container.textContent).toContain('Net Debit');
    expect(container.textContent).toContain('4,500');
  });

  // NOTE: each add is a separate test with its own builder. The in-memory test DOM keeps a global
  // id->element map that isn't cleared on innerHTML reset, so re-rendering then clicking the same id
  // accumulates a stale listener (a mock artifact — real browsers discard the old node). One render
  // per click keeps the assertion honest.
  it("'+ Add Buy Leg' adds a leg to the buy column", () => {
    const builder = new LegBuilderComponent(container, { currentSpot: 24850 });
    builder.setLegs([]);

    expect(container.querySelector('#btn-add-buy-leg')).not.toBeNull();
    container.querySelector('#btn-add-buy-leg').click();

    expect(builder.getLegs().length).toBe(1);
    expect(builder.getLegs()[0].direction).toBe('buy');
  });

  it("'+ Add Sell Leg' adds a leg to the sell column", () => {
    const builder = new LegBuilderComponent(container, { currentSpot: 24850 });
    builder.setLegs([]);

    expect(container.querySelector('#btn-add-sell-leg')).not.toBeNull();
    container.querySelector('#btn-add-sell-leg').click();

    expect(builder.getLegs().length).toBe(1);
    expect(builder.getLegs()[0].direction).toBe('sell');
  });

  it('lays out legs in a two-column Buy / Sell grid regardless of count', () => {
    const builder = new LegBuilderComponent(container);

    [1, 2, 4].forEach((count) => {
      const legs = Array.from({ length: count }, (_, i) => ({
        strike: 24500 + i * 50,
        option_type: 'CE',
        direction: i % 2 === 0 ? 'buy' : 'sell',
        quantity_lots: 1,
        lot_size: 75,
        entry_premium: 50,
      }));
      builder.setLegs(legs);
      expect(container.querySelector('#buy-legs-container')).not.toBeNull();
      expect(container.querySelector('#sell-legs-container')).not.toBeNull();
      const wrap = container.querySelector('.leg-builder-container');
      expect(wrap.style.flexDirection).toBe('column');
    });
  });
});

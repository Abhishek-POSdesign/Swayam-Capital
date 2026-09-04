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

  it('orders BUY legs at top and SELL legs at bottom with margin safety divider', () => {
    const builder = new LegBuilderComponent(container);
    builder.setLegs([
      { strike: 24700, option_type: 'PE', direction: 'sell', quantity_lots: 1, lot_size: 75, entry_premium: 45 },
      { strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1, lot_size: 75, entry_premium: 110 },
    ]);

    expect(container.textContent).toContain('STRATEGY LEGS (2)');
    expect(container.textContent).toContain('Buys execute first (margin-safe)');

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

  it('adds a new leg when + Add Leg button is clicked', () => {
    const builder = new LegBuilderComponent(container, { currentSpot: 24850 });
    builder.setLegs([]);

    const btnAdd = container.querySelector('#btn-add-leg');
    expect(btnAdd).not.toBeNull();
    btnAdd.click();

    expect(builder.getLegs().length).toBe(1);
  });
});

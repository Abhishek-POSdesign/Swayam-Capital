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

  it('unconditionally uses vertical single-column stack regardless of leg count', () => {
    const builder = new LegBuilderComponent(container);
    
    // Test with 1, 2, 4 legs
    [1, 2, 4].forEach(count => {
      const legs = Array.from({ length: count }, (_, i) => ({
        strike: 24500 + i * 50,
        option_type: 'CE',
        direction: i % 2 === 0 ? 'buy' : 'sell',
        quantity_lots: 1,
        lot_size: 75,
        entry_premium: 50,
      }));
      builder.setLegs(legs);
      const wrapper = container.querySelector('#legs-cards-wrapper');
      expect(wrapper.classList.contains('legs-stack-1col')).toBe(true);
      expect(wrapper.classList.contains('legs-grid-2col')).toBe(false);
      expect(wrapper.style.display).toBe('flex');
      expect(wrapper.style.flexDirection).toBe('column');
    });
  });
});

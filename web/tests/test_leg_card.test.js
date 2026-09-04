import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { LegCardComponent } from '../src/components/leg-card.js';

describe('LegCardComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders leg attributes including badge, strike, lots, and LTP', () => {
    const legData = {
      strike: 24900,
      option_type: 'PE',
      direction: 'buy',
      quantity_lots: 1,
      entry_premium: 110.5,
      expiry_date: '2026-09-10',
      delta: -0.45,
      theta: -8.2,
      vega: 14.1,
    };

    const card = new LegCardComponent(container, legData, 0);
    card.render();

    expect(container.textContent).toContain('B');
    expect(container.textContent).toContain('PE');
    expect(container.textContent).toContain('1 lot');
    expect(container.textContent).toContain('₹110.50');
    expect(container.textContent).toContain('Δ -0.45');
    expect(container.textContent).toContain('θ -8.2');
  });

  it('toggles direction when badge is clicked', () => {
    const onChange = vi.fn();
    const legData = {
      strike: 24900,
      option_type: 'PE',
      direction: 'buy',
      quantity_lots: 1,
      entry_premium: 110.5,
    };

    const card = new LegCardComponent(container, legData, 0, { onChange });
    card.render();

    const btnDir = container.querySelector('#btn-toggle-dir-0');
    expect(btnDir.textContent.trim()).toBe('B');
    btnDir.click();

    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][1].direction).toBe('sell');
  });

  it('triggers onRemove when close button is clicked', () => {
    const onRemove = vi.fn();
    const legData = { strike: 24800, option_type: 'CE', direction: 'sell' };

    const card = new LegCardComponent(container, legData, 2, { onRemove });
    card.render();

    const btnRemove = container.querySelector('#btn-remove-leg-2');
    btnRemove.click();

    expect(onRemove).toHaveBeenCalledWith(2);
  });
});

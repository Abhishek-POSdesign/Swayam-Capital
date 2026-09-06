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

  it('renders badge, CE/PE, editable price, and inline IV & Delta', () => {
    const legData = {
      strike: 24900,
      option_type: 'PE',
      direction: 'buy',
      quantity_lots: 1,
      entry_premium: 110.5,
      expiry_date: '2026-09-16',
      delta: -0.45,
      iv: 0.12,
      iv_available: true,
    };

    const card = new LegCardComponent(container, legData, 0);
    card.render();

    expect(container.textContent).toContain('B');
    expect(container.textContent).toContain('PE');
    expect(container.textContent).toContain('IV');
    expect(container.textContent).toContain('Delta');
    expect(container.textContent).toContain('-0.45');

    const priceInput = container.querySelector('.input-price');
    expect(priceInput).not.toBeNull();
    expect(Number(priceInput.value)).toBe(110.5);
  });

  it("shows '—' for IV/Delta when not derivable from a price (no fake numbers)", () => {
    const card = new LegCardComponent(container, {
      strike: 24800,
      option_type: 'CE',
      direction: 'buy',
      iv_available: false,
    }, 0);
    card.render();

    expect(container.querySelector('.leg-iv').textContent).toBe('—');
    expect(container.querySelector('.leg-delta').textContent).toBe('—');
  });

  it('toggles direction when badge is clicked', () => {
    const onChange = vi.fn();
    const card = new LegCardComponent(container, {
      strike: 24900,
      option_type: 'PE',
      direction: 'buy',
      quantity_lots: 1,
      entry_premium: 110.5,
    }, 0, { onChange });
    card.render();

    const btnDir = container.querySelector('.btn-toggle-direction');
    expect(btnDir.textContent.trim()).toBe('B');
    btnDir.click();

    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][1].direction).toBe('sell');
  });

  it('triggers onRemove when close button is clicked', () => {
    const onRemove = vi.fn();
    const card = new LegCardComponent(container, { strike: 24800, option_type: 'CE', direction: 'sell' }, 2, { onRemove });
    card.render();

    container.querySelector('.btn-remove-leg').click();

    expect(onRemove).toHaveBeenCalledWith(2);
  });

  it('updates the price and fires onPriceInput without re-rendering (focus preserved)', () => {
    const onPriceInput = vi.fn();
    const card = new LegCardComponent(container, {
      strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1, entry_premium: 110,
    }, 0, { onPriceInput });
    card.render();

    const priceInput = container.querySelector('.input-price');
    const before = priceInput; // same node must persist (no re-render)
    priceInput.value = '150';
    priceInput.dispatchEvent(new Event('input', { bubbles: true }));

    expect(card.leg.entry_premium).toBe(150);
    expect(onPriceInput).toHaveBeenCalled();
    expect(container.querySelector('.input-price')).toBe(before);
  });
});

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { LegCardComponent } from '../src/components/leg-card.js';

describe('LegCardComponent (Option B card)', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders side chip, CE/PE, editable price, and inline IV / Δ / Bid / Ask / OI stats', () => {
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
      bid: 109.6,
      ask: 110.4,
      oi: 120000,
    };

    const card = new LegCardComponent(container, legData, 0);
    card.render();

    // side chip B, CE/PE toggle, and the stats labels
    expect(container.querySelector('.bs-chip').textContent.trim()).toBe('B');
    expect(container.textContent).toContain('PE');
    expect(container.textContent).toContain('IV');
    expect(container.textContent).toContain('Δ');
    expect(container.textContent).toContain('Bid');
    expect(container.textContent).toContain('Ask');
    expect(container.textContent).toContain('OI');

    // real stat values (no fakes)
    expect(container.querySelector('.leg-delta').textContent).toBe('-0.45');
    expect(container.querySelector('.leg-iv').textContent).toBe('12.0%');
    expect(container.querySelector('.leg-bid').textContent).toBe('109.6');
    expect(container.querySelector('.leg-oi').textContent).toBe('1.2L');

    const priceInput = container.querySelector('.input-price');
    expect(priceInput).not.toBeNull();
    expect(Number(priceInput.value)).toBe(110.5);
  });

  it("shows '—' for every stat when not derivable from a real price (no fake numbers)", () => {
    const card = new LegCardComponent(
      container,
      { strike: 24800, option_type: 'CE', direction: 'buy', iv_available: false },
      0
    );
    card.render();

    expect(container.querySelector('.leg-iv').textContent).toBe('—');
    expect(container.querySelector('.leg-delta').textContent).toBe('—');
    expect(container.querySelector('.leg-bid').textContent).toBe('—');
    expect(container.querySelector('.leg-ask').textContent).toBe('—');
    expect(container.querySelector('.leg-oi').textContent).toBe('—');
  });

  it('has no Buy/Sell toggle — side is fixed by the column (chip is static)', () => {
    const onChange = vi.fn();
    const card = new LegCardComponent(
      container,
      { strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1 },
      0,
      { onChange }
    );
    card.render();

    expect(container.querySelector('.btn-toggle-direction')).toBeNull();
    expect(container.querySelector('.bs-chip').tagName).toBe('SPAN');
  });

  it('switches CE/PE and fires onChange', () => {
    const onChange = vi.fn();
    const card = new LegCardComponent(
      container,
      { strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1 },
      0,
      { onChange }
    );
    card.render();

    container.querySelector('.btn-type-ce').click();

    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][1].option_type).toBe('CE');
  });

  it('steps the strike by 50 and fires onChange', () => {
    const onChange = vi.fn();
    const card = new LegCardComponent(
      container,
      { strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1 },
      0,
      { onChange }
    );
    card.render();

    container.querySelector('.btn-strike-inc').click();
    expect(onChange.mock.calls[0][1].strike).toBe(24950);
  });

  it('fires onRefresh when the ↻ button is clicked', () => {
    const onRefresh = vi.fn();
    const card = new LegCardComponent(
      container,
      { strike: 24900, option_type: 'PE', direction: 'buy' },
      3,
      { onRefresh }
    );
    card.render();

    container.querySelector('.btn-refresh-price').click();
    expect(onRefresh).toHaveBeenCalledWith(3);
  });

  it('triggers onRemove when close button is clicked', () => {
    const onRemove = vi.fn();
    const card = new LegCardComponent(
      container,
      { strike: 24800, option_type: 'CE', direction: 'sell' },
      2,
      { onRemove }
    );
    card.render();

    container.querySelector('.btn-remove-leg').click();
    expect(onRemove).toHaveBeenCalledWith(2);
  });

  it('updates the price and fires onPriceInput without re-rendering (focus preserved)', () => {
    const onPriceInput = vi.fn();
    const card = new LegCardComponent(
      container,
      { strike: 24900, option_type: 'PE', direction: 'buy', quantity_lots: 1, entry_premium: 110 },
      0,
      { onPriceInput }
    );
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

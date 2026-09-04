import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { OvernightBlockModalComponent } from '../src/components/overnight-block-modal.js';

describe('OvernightBlockModalComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders modal with coral scrim and violation details when shown', () => {
    const modal = new OvernightBlockModalComponent(container);
    modal.show({
      position_id: 'pos-12345678-abcd',
      strategy_name: 'Short Strangle',
      naked_legs: [
        { strike: 24600, option_type: 'PE', direction: 'sell', quantity_lots: 1 },
      ],
      suggested_hedges: [
        { strike: 24450, option_type: 'PE', action: 'BUY', quantity_lots: 1 },
      ],
      rule_citation: 'Risk Management Rules § 10a — no overnight naked. Overnight hedge cap: 2% of margin base.',
    });

    expect(container.textContent).toContain('AUTO-BLOCK ENFORCEMENT · 15:20 IST');
    expect(container.textContent).toContain('Overnight Naked Position Detected');
    expect(container.textContent).toContain('Risk Management Rules § 10a');
    expect(container.textContent).toContain('Short Strangle');
    expect(container.textContent).toContain('SELL 24600 PE');
    expect(container.textContent).toContain('Add Hedge Now');
    expect(container.textContent).toContain('Exit Position Instead');
  });

  it('triggers onAddHedge when Add Hedge Now button is clicked', () => {
    const onAddHedge = vi.fn();
    const modal = new OvernightBlockModalComponent(container, { onAddHedge });
    const violation = {
      position_id: 'pos-1',
      naked_legs: [],
      suggested_hedges: [{ strike: 24500, option_type: 'PE' }],
    };

    modal.show(violation);
    const btn = container.querySelector('#btn-add-hedge-now');
    expect(btn).not.toBeNull();
    btn.click();

    expect(onAddHedge).toHaveBeenCalledWith(violation);
    expect(modal.isOpen).toBe(false);
  });

  it('triggers onExitPosition when Exit Position Instead button is clicked', () => {
    const onExit = vi.fn();
    const modal = new OvernightBlockModalComponent(container, { onExitPosition: onExit });
    const violation = {
      position_id: 'pos-999',
      naked_legs: [],
    };

    modal.show(violation);
    const btn = container.querySelector('#btn-exit-position-instead');
    expect(btn).not.toBeNull();
    btn.click();

    expect(onExit).toHaveBeenCalledWith(violation);
    expect(modal.isOpen).toBe(false);
  });
});

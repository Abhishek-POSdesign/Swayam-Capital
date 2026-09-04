import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { VerdictCardComponent } from '../src/components/verdict-card.js';

describe('VerdictCardComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders pending state when no verdict provided', () => {
    const comp = new VerdictCardComponent(container);
    comp.init();

    expect(container.textContent).toContain('AWAITING CHECK-IN');
    expect(container.textContent).toContain('Complete your 6-step readiness ritual');
  });

  it('renders GREEN verdict with full 1.0% cap unlocked', () => {
    const comp = new VerdictCardComponent(container);
    comp.setVerdict({
      verdict: 'green',
      trading_allowed: true,
      size_cap_pct: 0.01,
      reasons: [],
    });

    expect(container.textContent).toContain('GREEN — READY');
    expect(container.textContent).toContain('Full 1.0% risk per trade unlocked');
  });

  it('renders YELLOW verdict with reduced size cap and reason chip', () => {
    const comp = new VerdictCardComponent(container);
    comp.setVerdict({
      verdict: 'yellow',
      trading_allowed: true,
      size_cap_pct: 0.0075,
      reasons: ['Sleep < 6h reduces sizing to 0.75%'],
    });

    expect(container.textContent).toContain('YELLOW — CAUTION');
    expect(container.textContent).toContain('Position size capped at 0.75%');
    expect(container.textContent).toContain('Rule: Sleep < 6h reduces sizing to 0.75%');
  });

  it('renders RED verdict with locked session notice', () => {
    const comp = new VerdictCardComponent(container);
    comp.setVerdict({
      verdict: 'red',
      trading_allowed: false,
      size_cap_pct: null,
      reasons: ['Alcohol lockout 24h'],
    });

    expect(container.textContent).toContain('RED — NO TRADING');
    expect(container.textContent).toContain('Session blocked');
    expect(container.textContent).toContain('Rule: Alcohol lockout 24h');
  });
});

import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { RuleValidationPanelComponent } from '../src/components/rule-validation-panel.js';

/**
 * These tests describe the panel as Abhishek settled it on 2026-09-08.
 *
 * The previous version of this file asserted the superseded model: a
 * "READY FOR EXECUTION" badge, an "EXECUTION GATED" state that blocked a
 * naked short, and the fabricated figures 4125 / 10000 / 0.41 which the
 * component invented whenever real data was missing. All of that is gone.
 *
 * Entry is never blocked. Only carrying overnight is gated.
 */

const CAPITAL = {
  risk_capital_inr: 971002.38,
  free_cash_inr: 100000,
  collateral_inr: 871002.38,
  primary_risk_cap_inr: 9710.02,
  black_swan_fuse_inr: 48550.12,
  source: 'FYERS funds() id 1 Total Balance',
  taken_at: '2026-09-08T09:30:00+05:30',
};

describe('RuleValidationPanelComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('shows the four rules by his own names', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 125, cap_inr: 9710.02, pct_of_margin: 0.01, passed: true },
      blast_radius: { loss_inr: 3900, cap_inr: 48550.12, pct_of_margin: 0.4, passed: true },
      checks: [{ rule: 'deployable_margin_ceiling', verdict: 'PASS', cap_inr: 554960.92, blocking: false }],
      capital: CAPITAL,
      intraday: true,
      max_loss_is_unlimited: false,
      warnings: [],
    }, false);

    // The panel uppercases these with CSS, which jsdom does not apply, so the
    // assertions match the source text rather than what the screen shows.
    const text = container.textContent;
    expect(text).toContain('Running loss');
    expect(text).toContain('Overnight gap');
    expect(text).toContain('Black swan');
    expect(text).toContain('Deployable margin');
    expect(text).toContain('1% of live balance');
    expect(text).toContain('2% of live balance');
    expect(text).toContain('5% of live balance');
  });

  it('does NOT multiply pct_of_margin by 100', () => {
    // The regression this test exists for: the server sends 1.74 meaning
    // 1.74%. The panel multiplied it again and printed 174%, overstating his
    // risk a hundredfold on the one screen he checks before every trade.
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 16879, cap_inr: 9710.02, pct_of_margin: 1.74, passed: false },
      blast_radius: { loss_inr: 20000, cap_inr: 48550.12, pct_of_margin: 2.06, passed: true },
      checks: [],
      capital: CAPITAL,
      intraday: true,
      max_loss_is_unlimited: false,
      warnings: [],
    }, false);

    expect(container.textContent).toContain('1.74%');
    expect(container.textContent).not.toContain('174.00%');
  });

  it('never invents a number when the response is empty', () => {
    // Every one of these figures was previously hardcoded as a fallback and
    // shown to him as real: a 1:2.63 reward ratio, Rs 15,875 of daily
    // headroom, Rs 35,875 weekly, and a Rs 4,125 risk against a Rs 10,000 cap.
    const panel = new RuleValidationPanelComponent(container);
    panel.render(null, false);

    const text = container.textContent;
    for (const invented of ['4,125', '10,000', '2.63', '15,875', '35,875', '0.41']) {
      expect(text).not.toContain(invented);
    }
  });

  it('says unavailable, with a reason, rather than substituting a figure', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: null, cap_inr: 9710.02, pct_of_margin: null, passed: false },
      blast_radius: { loss_inr: null, cap_inr: 48550.12, pct_of_margin: null, passed: false },
      checks: [],
      capital: CAPITAL,
      intraday: true,
      max_loss_is_unlimited: false,
      warnings: [],
    }, false);

    expect(container.textContent).toContain('unavailable');
    expect(container.textContent).toContain('Why:');
  });

  it('reports an uncapped loss as Unlimited, never as a number', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 16879, cap_inr: 9710.02, pct_of_margin: 1.74, passed: false },
      blast_radius: { loss_inr: null, cap_inr: 48550.12, pct_of_margin: null, passed: false },
      checks: [],
      capital: CAPITAL,
      intraday: true,
      max_loss_is_unlimited: true,
      warnings: [],
    }, false);

    expect(container.textContent).toContain('Unlimited');
  });

  it('never blocks an intraday entry, however naked the structure', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 16879, cap_inr: 9710.02, pct_of_margin: 1.74, passed: false },
      blast_radius: { loss_inr: null, cap_inr: 48550.12, pct_of_margin: null, passed: false },
      checks: [{ rule: 'hedged_structure', verdict: 'FAIL', note: 'short CE 23900 uncovered', blocking: false }],
      capital: CAPITAL,
      intraday: true,
      max_loss_is_unlimited: true,
      warnings: [],
    }, true);

    const text = container.textContent;
    expect(text).toContain('Nothing here blocks you');
    expect(text).not.toContain('EXECUTION GATED');
    expect(text).not.toContain('Execution blocked');
  });

  it('applies the 2% gap test only when the position is carried overnight', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 16879, cap_inr: 9710.02, pct_of_margin: 1.74, passed: false },
      blast_radius: { loss_inr: null, cap_inr: 48550.12, pct_of_margin: null, passed: false },
      checks: [],
      capital: CAPITAL,
      intraday: false,
      max_loss_is_unlimited: true,
      carry: {
        may_carry_overnight: false,
        hedged: false,
        gap_loss_inr: 16628,
        cap_inr: 19420.05,
        move: {
          average_daily_move_points: 80.1,
          gap_tested_points: 160.1,
          sessions_used: 20,
        },
        reasons: ['The position is not hedged, so its loss has no ceiling.'],
        arithmetic: 'NIFTY gaps 160 points either way',
      },
      warnings: [],
    }, false);

    const text = container.textContent;
    expect(text).toContain('gap test below applies');
    expect(text).toContain('160.1 points');
    expect(text).toContain('20 sessions');
  });

  it('shows the deployable margin as a ceiling, not as consumption', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 125, cap_inr: 9710.02, pct_of_margin: 0.01, passed: true },
      blast_radius: { loss_inr: 3900, cap_inr: 48550.12, pct_of_margin: 0.4, passed: true },
      checks: [{ rule: 'deployable_margin_ceiling', verdict: 'PASS', cap_inr: 554960.92, blocking: false }],
      capital: CAPITAL,
      intraday: true,
      max_loss_is_unlimited: false,
      warnings: [],
    }, false);

    expect(container.textContent).toContain('5,54,961');
    expect(container.textContent).toContain('This is your ceiling');
  });

  it('names where the balance came from and when it was read', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 125, cap_inr: 9710.02, pct_of_margin: 0.01, passed: true },
      blast_radius: { loss_inr: 3900, cap_inr: 48550.12, pct_of_margin: 0.4, passed: true },
      checks: [],
      capital: CAPITAL,
      intraday: true,
      max_loss_is_unlimited: false,
      warnings: [],
    }, false);

    const text = container.textContent;
    expect(text).toContain('9,71,002');
    expect(text).toContain('FYERS funds()');
    expect(text).toContain('2026-09-08');
  });
});

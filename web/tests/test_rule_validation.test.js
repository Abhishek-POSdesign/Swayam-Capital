import { describe, it, expect, beforeEach } from 'vitest';
import { renderRuleValidation } from '../src/components/rule-validation.js';

describe('Rule Validation Panel (Two-Tier Risk Model)', () => {
  let container;

  beforeEach(() => {
    container = {
      innerHTML: '',
    };
    global.document = {
      getElementById: (id) => {
        if (id === 'btn-execute-trade') {
          return {
            addEventListener: () => {},
          };
        }
        return null;
      },
    };
  });

  it('enables Execute button when both realistic risk and blast radius pass', () => {
    const val = {
      passed: true,
      overall_passed: true,
      realistic_risk: {
        loss_inr: 4200.0,
        cap_inr: 8670.0,
        pct_of_margin: 0.48,
        passed: true,
      },
      blast_radius: {
        loss_inr: 16500.0,
        cap_inr: 26010.0,
        pct_of_margin: 1.89,
        passed: true,
      },
      checks: [
        { rule: 'rr_minimum', verdict: 'PASS', note: 'R:R 2.5 vs 2.0' },
        { rule: 'no_single_leg', verdict: 'PASS', note: '2 legs' },
      ],
    };

    renderRuleValidation(container, val);

    // Both badges are green (verdict-pass)
    expect(container.innerHTML).toContain('realistic-risk-badge verdict-pass');
    expect(container.innerHTML).toContain('blast-radius-badge verdict-pass');
    expect(container.innerHTML).toContain('₹4,200 / ₹8,670');
    expect(container.innerHTML).toContain('₹16,500 / ₹26,010');
    expect(container.innerHTML).toContain('0.48% of margin base');
    expect(container.innerHTML).toContain('1.89% of margin base');

    // Execute button is enabled (does NOT have disabled attribute)
    expect(container.innerHTML).not.toContain('disabled');
    expect(container.innerHTML).toContain('VERDICT: ✅ PASSED METHOD AUDIT');
  });

  it('disables Execute button and renders realistic verdict red when realistic risk fails', () => {
    const val = {
      passed: false,
      overall_passed: false,
      realistic_risk: {
        loss_inr: 9500.0,
        cap_inr: 8670.0,
        pct_of_margin: 1.12,
        passed: false,
      },
      blast_radius: {
        loss_inr: 20000.0,
        cap_inr: 26010.0,
        pct_of_margin: 2.35,
        passed: true,
      },
      checks: [
        { rule: 'rr_minimum', verdict: 'PASS', note: 'R:R 2.5 vs 2.0' },
      ],
    };

    renderRuleValidation(container, val);

    // Realistic badge is red (verdict-fail), blast badge is green (verdict-pass)
    expect(container.innerHTML).toContain('realistic-risk-badge verdict-fail');
    expect(container.innerHTML).toContain('blast-radius-badge verdict-pass');
    expect(container.innerHTML).toContain('❌ ₹9,500 / ₹8,670');
    expect(container.innerHTML).toContain('✅ ₹20,000 / ₹26,010');

    // Execute button is disabled
    expect(container.innerHTML).toContain('disabled');
    expect(container.innerHTML).toContain('VERDICT: ❌ BLOCKED BY METHOD RULES');
  });

  it('disables Execute button and renders blast verdict red when blast radius fails', () => {
    const val = {
      passed: false,
      overall_passed: false,
      realistic_risk: {
        loss_inr: 4200.0,
        cap_inr: 8670.0,
        pct_of_margin: 0.48,
        passed: true,
      },
      blast_radius: {
        loss_inr: 32000.0,
        cap_inr: 26010.0,
        pct_of_margin: 3.76,
        passed: false,
      },
      checks: [
        { rule: 'rr_minimum', verdict: 'PASS', note: 'R:R 2.5 vs 2.0' },
      ],
    };

    renderRuleValidation(container, val);

    // Realistic badge is green (verdict-pass), blast badge is red (verdict-fail)
    expect(container.innerHTML).toContain('realistic-risk-badge verdict-pass');
    expect(container.innerHTML).toContain('blast-radius-badge verdict-fail');
    expect(container.innerHTML).toContain('✅ ₹4,200 / ₹8,670');
    expect(container.innerHTML).toContain('❌ ₹32,000 / ₹26,010');

    // Execute button is disabled
    expect(container.innerHTML).toContain('disabled');
    expect(container.innerHTML).toContain('VERDICT: ❌ BLOCKED BY METHOD RULES');
  });
});

import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { RuleValidationPanelComponent } from '../src/components/rule-validation-panel.js';

describe('RuleValidationPanelComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders two primary risk cards: Realistic Risk and Blast Radius', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 4125, cap_inr: 10000, pct_of_margin: 0.41, passed: true },
      blast_radius: { loss_inr: 4125, cap_inr: 20000, pct_of_margin: 0.41, passed: true },
      checks: [
        { rule: 'Risk:Reward Ratio', verdict: 'PASS', actual: 2.63 },
        { rule: 'Daily Loss Cap', verdict: 'PASS', actual_inr: 4125, cap_inr: 20000 },
        { rule: 'Weekly Loss Cap', verdict: 'PASS', actual_inr: 4125, cap_inr: 40000 },
      ],
    }, false);

    expect(container.textContent).toContain('REALISTIC RISK (2σ, 20D VOL)');
    expect(container.textContent).toContain('BLAST RADIUS (ABSOLUTE MAX)');
    expect(container.textContent).toContain('READY FOR EXECUTION');
    expect(container.textContent).toContain('PASS ✅');
  });

  it('flags execution gated when naked short risk exists', () => {
    const panel = new RuleValidationPanelComponent(container);
    panel.render({
      realistic_risk: { loss_inr: 4125, cap_inr: 10000, pct_of_margin: 0.41, passed: true },
      blast_radius: { loss_inr: 4125, cap_inr: 20000, pct_of_margin: 0.41, passed: true },
      checks: [],
    }, true); // hasNakedShorts = true

    expect(container.textContent).toContain('EXECUTION GATED');
    expect(container.textContent).toContain('Naked Short Risk');
    expect(container.textContent).toContain('⚠️ Execution blocked: One or more Method risk rules failed');
  });
});

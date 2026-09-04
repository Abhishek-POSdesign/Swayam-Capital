import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { SessionRecapComponent } from '../src/components/session-recap.js';

describe('SessionRecapComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders honest empty-state card when recapData is null', () => {
    const recap = new SessionRecapComponent(container);
    recap.render(null);

    expect(container.textContent).toContain("TODAY'S SESSION RECAP");
    expect(container.textContent).toContain('No prior session context yet');
    expect(container.textContent).not.toContain('RBI Meet Monday');
  });

  it('renders honest empty-state card when recapData has empty bullets', () => {
    const recap = new SessionRecapComponent(container);
    recap.render({ bullets: [] });

    expect(container.textContent).toContain("TODAY'S SESSION RECAP");
    expect(container.textContent).toContain('No prior session context yet');
  });

  it('renders real bullets when provided from AI context', () => {
    const recap = new SessionRecapComponent(container);
    recap.render({
      bullets: [
        'Focus: Iron Condor around 24,800',
        'IV rank: Low volatility environment',
      ],
    });

    expect(container.textContent).toContain('HOME SESSION RECAP');
    expect(container.textContent).toContain('Focus: Iron Condor around 24,800');
    expect(container.textContent).toContain('IV rank: Low volatility environment');
    expect(container.textContent).not.toContain('No prior session context yet');
  });
});

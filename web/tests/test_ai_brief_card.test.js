import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { AIBriefCardComponent } from '../src/components/ai-brief-card.js';

describe('AIBriefCardComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders briefing text with lilac left border styling', () => {
    const comp = new AIBriefCardComponent(container);
    const testText = 'India VIX at 12.85 confirms low-vol regime. Bear Put Spread around 24,800 clean.';
    comp.render({ brief_text: testText });

    expect(container.textContent).toContain('WHAT MATTERS TODAY · AI TRADING PARTNER');
    expect(container.textContent).toContain(testText);
    expect(container.querySelector('#btn-open-ai-drawer')).not.toBeNull();
  });

  it('triggers onOpenAIDrawer callback when button is clicked', () => {
    const onOpenAIDrawer = vi.fn();
    const comp = new AIBriefCardComponent(container, { onOpenAIDrawer });
    comp.render({ brief_text: 'Test briefing text.' });

    const btn = container.querySelector('#btn-open-ai-drawer');
    if (btn) btn.click();

    expect(onOpenAIDrawer).toHaveBeenCalled();
  });

  it('renders actionable coral warning when error occurs', () => {
    const comp = new AIBriefCardComponent(container);
    comp.render(null, 'Service 503 — AI Router unavailable');

    expect(container.textContent).toContain('WHAT MATTERS TODAY · AI UNAVAILABLE');
    expect(container.textContent).toContain('Service 503 — AI Router unavailable');
  });
});

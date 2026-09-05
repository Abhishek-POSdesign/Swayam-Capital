import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { initHeader } from '../src/components/header.js';
import { NiftySnapshotCardComponent } from '../src/components/nifty-snapshot-card.js';
import { AIBriefCardComponent } from '../src/components/ai-brief-card.js';

describe('BUILD-9-FIXES-A Frontend Enhancements', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('1. Theme switcher defaults to auto and cycles auto -> dark -> light -> auto', () => {
    initHeader(container);

    const themeBtn = container.querySelector('#theme-switcher-btn');
    expect(themeBtn).not.toBeNull();
    // Default theme initialized to auto (System default)
    expect(document.documentElement.getAttribute('data-theme')).toBe('auto');
    expect(localStorage.getItem('swayam-theme')).toBe('auto');

    // First click: auto -> dark
    themeBtn.click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('swayam-theme')).toBe('dark');

    // Second click: dark -> light
    themeBtn.click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('swayam-theme')).toBe('light');

    // Third click: light -> auto
    themeBtn.click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('auto');
    expect(localStorage.getItem('swayam-theme')).toBe('auto');
  });

  it('2. NIFTY snapshot renders Cash and F&O panes with freshness badges', async () => {
    const card = new NiftySnapshotCardComponent(container);
    card.data = {
      cash_pane: {
        spot: 24864.20,
        day_change_pct: 0.09,
        spot_freshness: 'LIVE',
        range_20d: { low: 24200, high: 25100 },
        sentiment: 'Neutral',
      },
      fno_pane: {
        weekly_expiry: '2026-09-08',
        weekly_dte: { formatted: '2 calendar days · 2 trading sessions' },
        expiry_freshness: 'CALCULATED',
        institutional: {
          fii_cash_net_cr: -485.50,
          fii_cash_freshness: 'PREVIOUS SESSION',
          fii_fno_net_contracts: '+14,230',
        },
      },
    };
    card.render();

    expect(container.textContent).toContain('NIFTY 50 SNAPSHOT');
    expect(container.textContent).toContain('24,864.20');
    expect(container.textContent).toContain('2026-09-08');
    expect(container.textContent).toContain('LIVE');
    expect(container.textContent).toContain('CALCULATED');
    expect(container.textContent).toContain('PREVIOUS SESSION');
  });

  it('3. AI Brief renders markdown (bold, italic, code, bullets) as HTML elements', () => {
    const comp = new AIBriefCardComponent(container);
    const markdownText =
      '**Skip trades if:**\n' +
      '- Event risk within 48h\n' +
      '- Intraday VIX exceeds `15.0`\n\n' +
      '*Consider paper-trading only today.*';

    comp.render({ brief_text: markdownText });

    const contentDiv = container.querySelector('#ai-brief-content');
    expect(contentDiv).not.toBeNull();

    // Verify <strong>, <code>, <em>, and list elements rendered
    expect(container.innerHTML).toContain('<strong>Skip trades if:</strong>');
    expect(container.innerHTML).toContain('15.0</code>');
    expect(container.innerHTML).toContain('<em>Consider paper-trading only today.</em>');
    expect(container.innerHTML).toContain('<ul');
    expect(container.innerHTML).toContain('<li');
    expect(container.innerHTML).toContain('Event risk within 48h');

  });
});


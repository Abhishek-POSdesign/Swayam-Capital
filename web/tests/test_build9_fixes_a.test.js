import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { initHeader } from '../src/components/header.js';
import { NiftyChartCardComponent } from '../src/components/nifty-chart-card.js';
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

  it('2. NIFTY chart timeframe tabs are interactive and update active state', async () => {
    const chart = new NiftyChartCardComponent(container);
    await chart.render();

    const tab15m = container.querySelector('#tab-tf-15m');
    const tab1D = container.querySelector('#tab-tf-1D');
    expect(tab15m).not.toBeNull();
    expect(tab1D).not.toBeNull();
    expect(tab1D.classList.contains('active')).toBe(true);

    // Mock loadAndRefreshChart to avoid network call in unit test
    vi.spyOn(chart, 'loadAndRefreshChart').mockResolvedValue();

    tab15m.click();
    expect(chart.activeTimeframe).toBe('15m');
    expect(tab15m.classList.contains('active')).toBe(true);
    expect(tab1D.classList.contains('active')).toBe(false);
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


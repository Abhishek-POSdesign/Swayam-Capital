import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('plotly.js-dist-min', () => ({
  default: {
    react: vi.fn(),
    newPlot: vi.fn(),
    relayout: vi.fn(),
    Plots: { resize: vi.fn() },
  },
}));

import { setupTestDOM } from './setup_test_dom.js';
import { SwayamApp } from '../src/main.js';

describe('Navigation Regression (Defect 2)', () => {
  beforeEach(() => {
    setupTestDOM();

    // Setup the multi-page containers
    const homeView = document.createElement('div');
    homeView.id = 'home-view';
    document.body.appendChild(homeView);

    const strategyView = document.createElement('div');
    strategyView.id = 'strategy-view';
    document.body.appendChild(strategyView);

    const journalView = document.createElement('div');
    journalView.id = 'journal-view';
    document.body.appendChild(journalView);

    const header = document.createElement('div');
    header.id = 'header-container';
    document.body.appendChild(header);
  });

  it('navigates from strategy to journal, unsetting data-initial-page and toggling view displays', () => {
    // Simulate landing on /strategy
    document.documentElement.setAttribute('data-initial-page', 'strategy');
    expect(document.documentElement.getAttribute('data-initial-page')).toBe('strategy');

    const app = new SwayamApp();

    // Call navigateTo journal
    app.navigateTo('journal', false);

    // 1. data-initial-page attribute must be stripped to prevent CSS !important conflicts
    expect(document.documentElement.getAttribute('data-initial-page')).toBeFalsy();

    // 2. View displays must be updated correctly
    const homeView = document.getElementById('home-view');
    const strategyView = document.getElementById('strategy-view');
    const journalView = document.getElementById('journal-view');

    expect(journalView.style.display).toBe('block');
    expect(strategyView.style.display).toBe('none');
    expect(homeView.style.display).toBe('none');
  });

  it('navigates back to home and strategy smoothly', () => {
    const app = new SwayamApp();

    app.navigateTo('home', false);
    expect(document.getElementById('home-view').style.display).toBe('block');
    expect(document.getElementById('strategy-view').style.display).toBe('none');
    expect(document.getElementById('journal-view').style.display).toBe('none');

    app.navigateTo('strategy', false);
    expect(document.getElementById('strategy-view').style.display).toBe('block');
    expect(document.getElementById('home-view').style.display).toBe('none');
    expect(document.getElementById('journal-view').style.display).toBe('none');
  });
});

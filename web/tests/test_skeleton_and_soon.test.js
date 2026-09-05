import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { initHeader } from '../src/components/header.js';
import fs from 'fs';
import path from 'path';

describe('Skeleton Loader & SOON Badge (Sections 3 & 4)', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('index.html contains skeleton-block placeholders in home, strategy, and journal views', () => {
    const htmlPath = path.resolve(__dirname, '../index.html');
    const html = fs.readFileSync(htmlPath, 'utf-8');

    expect(html).toContain('id="home-view"');
    expect(html).toContain('id="strategy-view"');
    expect(html).toContain('id="journal-view"');
    expect(html).toContain('skeleton-block');

    const homeViewChunk = html.split('id="home-view"')[1].split('id="strategy-view"')[0];
    expect(homeViewChunk).toContain('skeleton-block');

    const stratViewChunk = html.split('id="strategy-view"')[1].split('id="journal-view"')[0];
    expect(stratViewChunk).toContain('skeleton-block');

    const journalViewChunk = html.split('id="journal-view"')[1].split('id="ai-sidebar-container"')[0];
    expect(journalViewChunk).toContain('skeleton-block');
  });

  it('header renders Backtest Lab button with inline SOON badge', () => {
    initHeader(container, { activePage: 'home' });
    const backtestBtn = container.querySelector('[data-page="backtest"]');
    expect(backtestBtn).not.toBeNull();
    expect(backtestBtn.textContent).toContain('Backtest Lab');
    expect(backtestBtn.textContent).toContain('SOON');
  });
});

/**
 * "If, while live in the market, FYERS stops giving me the data, how will I
 * work, and how will I know?" — Abhishek, 2026-09-08.
 *
 * These hold the "how will I know" in place. The strip is on screen in every
 * state, including the healthy one, so the first time it turns red he already
 * knows what it is. It never looks healthy when it cannot tell.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';
import { setupTestDOM } from './setup_test_dom.js';
import { DataHealthStrip } from '../src/components/data-health-strip.js';
import { StrategyBuilderPage } from '../src/pages/strategy-builder.js';

const LIVE = {
  state: 'live',
  headline: 'Live prices from FYERS',
  detail: 'Option chain read 2 seconds ago. Spot ticking, 412 frames sent.',
  action: null,
  market_open: true,
  sources: { chain: { state: 'live', age_seconds: 2.0 }, spot: { state: 'live' } },
};

const REFUSED = {
  state: 'unavailable',
  headline: 'No prices from FYERS',
  detail: 'FYERS is refusing requests because too many were sent. Waiting 20 seconds before asking again.',
  action: 'Nothing to do. Too many requests went to FYERS and it is waiting before asking again.',
  market_open: true,
  sources: { chain: { state: 'unavailable', age_seconds: null }, spot: { state: 'delayed' } },
};

const CLOSED = {
  state: 'closing',
  headline: 'Closing prices, market is shut',
  detail: 'Market is shut. Showing the last price of the session.',
  action: null,
  market_open: false,
  sources: { chain: { state: 'closing', age_seconds: 140.0 }, spot: { state: 'closing' } },
};

describe('The data health strip', () => {
  beforeEach(() => {
    setupTestDOM();
  });

  it('says LIVE, in green, when prices are current', async () => {
    const host = document.createElement('div');
    const strip = new DataHealthStrip(host, { fetchHealth: async () => LIVE, pollMs: 0 });
    await strip.refresh();

    expect(host.innerHTML).toContain('sw-health--live');
    expect(host.innerHTML).toContain('LIVE');
    expect(host.innerHTML).toContain('Live prices from FYERS');
    strip.destroy();
  });

  it('shows how old the reading is, so a frozen number is visible as frozen', async () => {
    const host = document.createElement('div');
    const strip = new DataHealthStrip(host, { fetchHealth: async () => CLOSED, pollMs: 0 });
    await strip.refresh();

    expect(host.innerHTML).toContain('140s old');
    expect(host.innerHTML).toContain('sw-health--closing');
    strip.destroy();
  });

  it('turns red and says what to do when FYERS refuses', async () => {
    const host = document.createElement('div');
    const strip = new DataHealthStrip(host, { fetchHealth: async () => REFUSED, pollMs: 0 });
    await strip.refresh();

    expect(strip.state()).toBe('unavailable');
    expect(host.innerHTML).toContain('sw-health--unavailable');
    expect(host.innerHTML).toContain('NO DATA');
    expect(host.innerHTML).toContain('refusing requests');
    expect(host.innerHTML).toContain('sw-health__action');
    strip.destroy();
  });

  it('never looks healthy when the check itself fails', async () => {
    const host = document.createElement('div');
    const strip = new DataHealthStrip(host, {
      fetchHealth: async () => { throw new Error('service did not answer'); },
      pollMs: 0,
    });
    await strip.refresh();

    expect(strip.state()).toBe('unavailable');
    expect(host.innerHTML).toContain('Cannot tell whether prices are live');
    expect(host.innerHTML).not.toContain('sw-health--live');
    strip.destroy();
  });

  it('tells whoever is listening, so the desk can react to the market shutting', async () => {
    const host = document.createElement('div');
    const seen = [];
    const strip = new DataHealthStrip(host, {
      fetchHealth: async () => CLOSED,
      onHealth: (h) => seen.push(h.market_open),
      pollMs: 0,
    });
    await strip.refresh();

    expect(seen).toEqual([false]);
    strip.destroy();
  });

  it('escapes whatever the server sends, because it is drawn as HTML', async () => {
    const host = document.createElement('div');
    const strip = new DataHealthStrip(host, {
      fetchHealth: async () => ({ ...LIVE, headline: '<img src=x onerror=alert(1)>' }),
      pollMs: 0,
    });
    await strip.refresh();

    expect(host.innerHTML).not.toContain('<img');
    expect(host.innerHTML).toContain('&lt;img');
    strip.destroy();
  });

  it('has a style for every state it can render, and no purple anywhere', () => {
    const css = fs.readFileSync(path.resolve(__dirname, '../src/styles/swayam-desk.css'), 'utf8');
    for (const state of ['live', 'closing', 'delayed', 'unavailable']) {
      expect(css).toContain(`.sw-health--${state}`);
    }
    const healthCss = css.slice(css.indexOf('.sw-health'));
    expect(healthCss).not.toMatch(/purple|violet|lilac|#[0-9a-f]*8b5cf6/i);
  });
});

describe('The desk and the market clock', () => {
  beforeEach(() => {
    setupTestDOM();
  });

  it('puts the health strip above the ticker, first thing on the page', () => {
    const container = document.createElement('div');
    const page = new StrategyBuilderPage(container);
    page.renderLayout();

    const html = container.innerHTML;
    expect(html).toContain('desk-data-health');
    expect(html.indexOf('desk-data-health')).toBeLessThan(html.indexOf('strategy-sticky-ticker'));
  });

  it('stops re-quoting every five seconds once the market shuts', () => {
    const container = document.createElement('div');
    const page = new StrategyBuilderPage(container);
    page.renderLayout();

    expect(page.requoteMs).toBe(5000);

    page.onDataHealth({ market_open: false });
    expect(page.requoteMs).toBe(60000);

    page.onDataHealth({ market_open: true });
    expect(page.requoteMs).toBe(5000);
  });

  it('does not churn the timer when the market state has not changed', () => {
    const container = document.createElement('div');
    const page = new StrategyBuilderPage(container);
    page.renderLayout();
    const spy = vi.spyOn(page, 'startLiveUpdates');

    page.onDataHealth({ market_open: true });
    expect(spy).not.toHaveBeenCalled();
  });
});

describe('Home never calls a closing price live', () => {
  beforeEach(() => {
    setupTestDOM();
  });

  const mountedHome = async () => {
    const { HomePage } = await import('../src/pages/home.js');
    const container = document.createElement('div');
    const page = new HomePage(container);
    page.render();
    page.snapshot = { spot: 23635.1, spot_freshness: 'prev_close', fno: {} };
    // A spot value exists, which is what used to be enough to claim LIVE.
    page.liveSpot = 23635.1;
    // The test DOM does not reflect nested updates up through the parent's
    // innerHTML, so assertions read the sidebar host directly.
    const sidebar = () => container.querySelector('#home-nifty-sidebar').innerHTML;
    return { page, container, sidebar };
  };

  it('says CLOSED, not LIVE, when the market is shut', async () => {
    const { page, sidebar } = await mountedHome();

    page.marketOpen = false;
    page.renderSidebar();
    expect(sidebar()).toContain('>closed<');
    expect(sidebar()).not.toContain('>live<');

    page.marketOpen = true;
    page.renderSidebar();
    expect(sidebar()).toContain('>live<');
  });

  it('does not claim live before the clock is known', async () => {
    const { page, sidebar } = await mountedHome();

    expect(page.marketOpen).toBe(null);
    page.renderSidebar();
    expect(sidebar()).not.toContain('>live<');
  });
});

describe('The desk never calls a closing price live', () => {
  beforeEach(() => {
    setupTestDOM();
  });

  const desk = () => {
    const container = document.createElement('div');
    const page = new StrategyBuilderPage(container);
    page.renderLayout();
    page.spot = 23635.1;
    page.spotAt = '2026-09-08T10:00:00+00:00';
    const chip = () => container.querySelector('#desk-spot').innerHTML;
    return { page, chip };
  };

  it('says "at the close", not "live", once the market is shut', () => {
    const { page, chip } = desk();

    page.onDataHealth({ market_open: false });
    expect(chip()).toContain('at the close');
    expect(chip()).not.toContain('>live');

    page.onDataHealth({ market_open: true });
    expect(chip()).toContain('live');
  });

  it('says "last read", not "live" or "at the close", when the clock is unknown', () => {
    const { page, chip } = desk();

    page.renderSpot();
    expect(chip()).toContain('last read');

    // A failed health check must not be read as a shut market.
    page.onDataHealth(null);
    expect(page.marketOpen).toBe(null);
    expect(chip()).toContain('last read');
  });

  it('keeps the slow interval while the clock is unknown', () => {
    const { page } = desk();
    page.onDataHealth(null);
    expect(page.requoteMs).toBe(60000);
  });

  it('still stamps when the price was read, in every state', () => {
    const { page, chip } = desk();
    page.onDataHealth({ market_open: false });
    expect(chip()).toContain('IST');
  });
});

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { HomePage } from '../src/pages/home.js';
import { RitualStripComponent } from '../src/components/ritual-strip.js';
import { MarketTickerComponent } from '../src/components/market-ticker.js';
import { ChatSurfaceComponent } from '../src/components/chat-surface.js';
import { api } from '../src/api.js';

const SNAPSHOT = {
  cash_pane: {
    spot: 23779.15,
    day_change_pct: -0.5,
    spot_freshness: 'LIVE',
    range_20d: { low: 23737.9, high: 24576.85 },
    range_50d: { low: 23606.0, high: 24774.0 },
    dma_20: 24165.0,
    atr_20: 162.0,
    realized_vol_20: 5.5,
    sentiment: 'Bearish',
    advances: null,
    declines: null,
    sector_rotation: [
      { name: 'BANK', change_pct: -0.49 },
      { name: 'PHARMA', change_pct: null },
    ],
    sector_freshness: 'LIVE',
  },
  fno_pane: {
    india_vix: 11.16,
    weekly_pcr: 1.0,
    max_pain: 21300,
    weekly_dte: { formatted: '0 calendar days · 1 trading session' },
    monthly_dte: { formatted: '21 calendar days · 15 trading sessions' },
  },
};

const CAPITAL = {
  risk_capital_inr: 971002.38,
  free_cash_inr: 100000,
  collateral_inr: 871002.38,
  deployable_margin_ceiling_inr: 554960.92,
  primary_risk_cap_inr: 9710.02,
  black_swan_fuse_inr: 48550.12,
  source: 'FYERS funds() id 1 Total Balance',
  taken_at: '2026-09-08T09:30:00+05:30',
};

describe('Home — the rebuilt page', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('lays out a ticker, a one-strip ritual, a NIFTY sidebar and the right column', () => {
    const page = new HomePage(container);
    page.render();

    const html = container.innerHTML;
    expect(container.querySelector('#home-ticker')).not.toBeNull();
    expect(container.querySelector('#home-ritual')).not.toBeNull();
    expect(container.querySelector('#home-nifty-sidebar')).not.toBeNull();
    expect(html.indexOf('home-ticker')).toBeLessThan(html.indexOf('home-ritual'));
    expect(html.indexOf('home-ritual')).toBeLessThan(html.indexOf('home-nifty-sidebar'));
    // The AI panel is the last thing in the right column; So Far Today lives inside it.
    expect(html.indexOf('home-record')).toBeLessThan(html.indexOf('home-ai'));
  });

  it('exposes niftyChart.retheme, which main.js calls on every route change', () => {
    const page = new HomePage(container);
    page.render();
    expect(typeof page.niftyChart.retheme).toBe('function');
    expect(() => page.niftyChart.retheme()).not.toThrow();
  });

  it('renders volume and breadth as unavailable, never as a number', () => {
    const page = new HomePage(container);
    page.render();
    page.snapshot = SNAPSHOT;
    page.daily = { dayHigh: 23905.3, dayLow: 23737.9, averageDailyMove: 80.1, sessionsUsed: 20 };
    page.renderSidebar();

    const text = container.querySelector('#home-nifty-sidebar').textContent;
    expect(text).toContain('Futures volume');
    expect(text).toContain('Advances / declines');
    expect(text).toContain('unavailable');
    expect(text).toContain('Bearish');
    expect(text).toContain('80 pts');
    // A sector with no figure gets the word, not a bar at a guessed position.
    expect(text).toContain('PHARMA');
  });

  it('says the average daily move is unavailable when there is not enough history', () => {
    const page = new HomePage(container);
    page.render();
    page.snapshot = SNAPSHOT;
    page.daily = { dayHigh: null, dayLow: null, averageDailyMove: null, sessionsUsed: 0 };
    page.renderSidebar();

    const text = container.querySelector('#home-nifty-sidebar').textContent;
    expect(text).toContain('Average daily move');
    expect(text).toContain('unavailable');
    expect(text).not.toContain('80 pts');
  });

  it('shows the four limits as percentages of the live balance', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = CAPITAL;
    page.renderLimits();

    const text = container.querySelector('#home-limits').textContent;
    expect(text).toContain('9,710'); // 1%
    expect(text).toContain('19,420'); // 2%
    expect(text).toContain('48,550'); // 5%
    expect(text).toContain('5,54,961'); // the ceiling
    expect(text).toContain('Nothing blocks an intraday entry');
  });

  it('shows no limits at all, rather than a stored number, when the balance cannot be read', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = null;
    page.capitalError = 'Could not reach the broker for funds';
    page.renderLimits();
    page.renderMoney();

    expect(container.querySelector('#home-limits').textContent).toContain('Without the balance');
    expect(container.querySelector('#home-money').textContent).toContain('Could not reach the broker');
    expect(container.querySelector('#home-money').textContent).not.toContain('₹0');
  });

  it('says why margin used is unknown, rather than showing it as zero', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = CAPITAL;

    // Not read yet.
    page.positions = null;
    page.renderMoney();
    expect(container.querySelector('#home-money').textContent).toContain('positions not read yet');

    // Nothing open is a true zero.
    page.positions = [];
    page.renderMoney();
    expect(container.querySelector('#home-money').textContent).toContain('nothing open');

    // Something open, but /api/positions stores no margin figure on a position,
    // so this is honestly unknown and must never render as zero.
    page.positions = [{ id: 'a1', strategy_name: 'Bear Put Spread', opened_at: '2026-09-08' }];
    page.renderMoney();
    const text = container.querySelector('#home-money').textContent;
    expect(text).toContain('no margin figure is stored on a position');
    expect(text).toContain('unavailable');
  });

  it('keeps the paper book and the real-money book separate, and explains each', () => {
    const page = new HomePage(container);
    page.render();
    page.positions = [];
    page.renderRecord();

    const host = container.querySelector('#home-record');
    expect(host.textContent).toContain('81 build-and-test rows are quarantined');

    page.book = 'real';
    page.renderRecord();
    expect(container.querySelector('#home-record').textContent).toContain('no order-placement code');
  });

  it('prints market breadth in the ticker as unavailable with its reason', () => {
    const page = new HomePage(container);
    page.snapshot = SNAPSHOT;
    page.capital = CAPITAL;
    page.daily = { dayHigh: null, dayLow: null, averageDailyMove: null, sessionsUsed: 0 };

    const host = document.createElement('div');
    const ticker = new MarketTickerComponent(host);
    ticker.render(page.tickerItems());

    expect(host.textContent).toContain('Breadth');
    expect(host.textContent).toContain('unavailable');
    expect(host.textContent).toContain('no constituent quotes');
    expect(host.textContent).toContain('23,779.15');
  });
});

describe('Morning ritual strip', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('is one thin strip and says so when it has not been filled in', () => {
    const strip = new RitualStripComponent(container);
    strip.render();
    expect(container.textContent).toContain('not filled in yet');
    expect(container.textContent).toContain("Add today's check-in");
  });

  it('saves on the SAVE BUTTON click, not on the dialog close event', async () => {
    const log = vi.spyOn(api, 'logReadiness').mockResolvedValue({ verdict: 'green' });
    const strip = new RitualStripComponent(container);
    strip.render();

    // A programmatic close must not be what saves: some browsers never fire it.
    const dialog = container.querySelector('#ritual-dialog');
    dialog.dispatchEvent('close');
    expect(log).not.toHaveBeenCalled();

    container.querySelector('#btn-save-ritual').click();
    await new Promise((r) => setTimeout(r, 0));

    expect(log).toHaveBeenCalledTimes(1);
    const payload = log.mock.calls[0][0];
    expect(payload).toHaveProperty('sleep_hours_bucket');
    expect(payload).toHaveProperty('alcohol_yesterday');
    expect(payload).toHaveProperty('journal_mood');
    expect(payload).toHaveProperty('life_stressor');
  });

  it('keeps saying not filled in, and names the failure, when the save is rejected', async () => {
    vi.spyOn(api, 'logReadiness').mockRejectedValue(new Error('Database unreachable'));
    const strip = new RitualStripComponent(container);
    strip.render();

    container.querySelector('#btn-save-ritual').click();
    await new Promise((r) => setTimeout(r, 0));

    expect(container.textContent).toContain('not filled in yet');
    expect(container.textContent).toContain('Database unreachable');
  });
});

describe('So Far Today inside the AI panel', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('the chat surface offers a slot above the conversation, and is otherwise untouched', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();
    const html = container.innerHTML;
    expect(html).toContain('chat-top-slot');
    expect(html.indexOf('chat-top-slot')).toBeLessThan(html.indexOf('chat-messages-container'));
    // The panel itself is unchanged: still the same composer, send button and bridge.
    expect(html).toContain('btn-chat-send');
    expect(html).toContain('Go to Strategy Builder');
  });
});

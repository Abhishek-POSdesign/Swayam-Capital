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

  it('shows the four caps as percentages of the live balance, inside Your money', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = CAPITAL;
    page.renderMoney();

    // The standalone "Today's limits" card is gone. Its four figures live in a
    // band under the money tiles they are derived from.
    expect(container.querySelector('#home-limits')).toBeNull();
    const text = container.querySelector('#home-money').textContent;
    expect(text).toContain("Today's caps");
    expect(text).toContain('9,710'); // 1%
    expect(text).toContain('19,420'); // 2%
    expect(text).toContain('48,550'); // 5%
    expect(text).toContain('5,54,961'); // the ceiling
    expect(text).toContain('never a stored number');
  });

  it('prints the margin ceiling exactly once, as rule 4 and not also as a money tile', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = CAPITAL;
    page.renderMoney();

    const text = container.querySelector('#home-money').textContent;
    expect(text.split('5,54,961').length - 1).toBe(1);
    expect(text).toContain('4 · Margin ceiling');
    // The money tiles are what he holds and what he is using, nothing else.
    expect(text).toContain('Balance');
    expect(text).toContain('Free cash');
    expect(text).toContain('Collateral');
    expect(text).toContain('Margin used');
  });

  it('shows no caps at all, rather than a stored number, when the balance cannot be read', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = null;
    page.capitalError = 'Could not reach the broker for funds';
    page.renderMoney();

    const text = container.querySelector('#home-money').textContent;
    expect(text).toContain('Could not reach the broker');
    expect(text).toContain("every one of today's four caps is a percentage of that balance".replace('every', 'Every'));
    expect(text).not.toContain('₹0');
    expect(text).not.toContain('9,710');
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

  it('draws every record row with a dash rather than a zero when there are no trades', () => {
    const page = new HomePage(container);
    page.render();
    page.readAt.record = new Date().toISOString();
    // What the journal really returns for an empty book: a zero count, and
    // zeroes and a 100 on figures it had nothing to compute from.
    page.record = {
      total_trades: 0,
      win_rate_pct: 0.0,
      avg_rr_actual: 0.0,
      cumulative_net_pnl_inr: 0.0,
      discipline_rate_pct: 100.0,
    };
    page.renderRecord();

    const text = container.querySelector('#home-record').textContent;
    expect(text).toContain('Win rate');
    expect(text).toContain('Cumulative profit');
    expect(text).toContain('Expectancy per trade');
    expect(text).toContain('Rules followed');
    // A zero win rate and an unknown win rate are different facts.
    expect(text).not.toContain('0.0%');
    expect(text).not.toContain('100%');
    expect(text).not.toContain('₹0');
    expect(text).toContain('—');
    expect(text).toContain('No closed paper trades yet');
  });

  it('shows the real record figures once there are trades in that book', () => {
    const page = new HomePage(container);
    page.render();
    page.readAt.record = new Date().toISOString();
    page.record = {
      total_trades: 4,
      win_rate_pct: 75.0,
      avg_rr_actual: 1.45,
      cumulative_net_pnl_inr: 8200,
      discipline_rate_pct: 100.0,
    };
    page.renderRecord();

    const text = container.querySelector('#home-record').textContent;
    expect(text).toContain('75.0%');
    expect(text).toContain('8,200');
    expect(text).toContain('1 : 1.45');
    // Expectancy is the book's own cumulative result over its own trade count.
    expect(text).toContain('2,050');
    expect(text).not.toContain('No closed paper trades yet');
  });

  it('asks the journal for one book at a time, so Paper never silently includes real money', async () => {
    const spy = vi.spyOn(api, 'getJournalTrades').mockResolvedValue({ kpis: { total_trades: 0 } });
    const page = new HomePage(container);
    page.render();
    await page.loadRecord();
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ mode: 'paper', status: 'closed' }));

    page.book = 'real';
    await page.loadRecord();
    expect(spy).toHaveBeenLastCalledWith(expect.objectContaining({ mode: 'real' }));
  });

  it('collapses open positions to one muted line, and expands to the full table', () => {
    const page = new HomePage(container);
    page.render();
    page.positions = [];
    page.livePositions = [];
    page.positionsExpanded = false;
    page.renderPositions();

    const host = container.querySelector('#home-positions');
    expect(host.textContent).toContain('Nothing open');
    expect(host.textContent).toContain('paper record starts clean from 8 September');
    // Nothing open means no colour: neither the profit nor the loss edge.
    expect(host.innerHTML).toContain('posstrip t-flat');
    expect(host.innerHTML).toContain('aria-expanded="false"');
    // Shut means shut: the detail is not merely hidden, it is not rendered.
    expect(host.innerHTML).toContain('id="home-positions-body" hidden');

    page.togglePositions();
    const opened = container.querySelector('#home-positions');
    expect(opened.innerHTML).toContain('aria-expanded="true"');
    expect(opened.innerHTML).not.toContain('home-positions-body" hidden');
    expect(page.positionsExpanded).toBe(true);
    // And it is remembered for the next visit.
    expect(localStorage.getItem('swayam-home-positions-expanded')).toBe('1');
  });

  it('colours the strip from the live money and prints the running-loss headroom', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = CAPITAL; // 1% running-loss cap of 9,710.02
    page.positions = [{ id: 'a1' }, { id: 'a2' }];
    page.livePositions = [
      { position_id: 'a1', unrealized_pnl_inr: -800 },
      { position_id: 'a2', unrealized_pnl_inr: -440 },
    ];
    page.renderPositions();

    const host = container.querySelector('#home-positions');
    expect(host.innerHTML).toContain('posstrip t-loss');
    expect(host.textContent).toContain('2 open');
    expect(host.textContent).toContain('1,240');
    expect(host.textContent).toContain('running loss 13% used');

    page.livePositions = [
      { position_id: 'a1', unrealized_pnl_inr: 800 },
      { position_id: 'a2', unrealized_pnl_inr: 440 },
    ];
    page.renderPositions();
    const now = container.querySelector('#home-positions');
    expect(now.innerHTML).toContain('posstrip t-profit');
    // A profit consumes none of the running-loss cap, so no headroom is claimed.
    expect(now.textContent).not.toContain('running loss');
  });

  it('never sums a partial valuation into a total that looks complete', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = CAPITAL;
    page.positions = [{ id: 'a1' }, { id: 'a2' }];
    page.livePositions = [
      { position_id: 'a1', unrealized_pnl_inr: -800 },
      { position_id: 'a2', unrealized_pnl_inr: null, error: 'strike missing from the chain' },
    ];
    page.renderPositions();

    const text = container.querySelector('#home-positions').textContent;
    expect(page.combinedPnl()).toBeNull();
    expect(text).toContain('profit and loss unavailable');
    expect(text).not.toContain('800');
  });

  it('shows an events impact brief only on the events that have one', () => {
    const page = new HomePage(container);
    page.render();
    page.events = [
      { event_name: 'RBI policy', event_date: '2026-09-12', importance: 'high', impact_brief: 'A hold is priced in; a cut would lift banks.' },
      { event_name: 'US CPI', event_date: '2026-09-11', importance: 'medium' },
    ];
    page.renderEvents();

    const host = container.querySelector('#home-events');
    // Exactly one of the two rows carries a brief, so exactly one anchor and
    // one popover exist. The other row gets no marker and no placeholder.
    expect(host.querySelectorAll('.evb').length).toBe(1);
    expect(host.querySelectorAll('.evpop').length).toBe(1);
    expect(host.innerHTML).toContain('a cut would lift banks');
    expect(host.innerHTML).toContain('aria-controls="home-evb-0"');
    expect(host.innerHTML).not.toContain('home-evb-1');
    expect(host.textContent).not.toContain('no brief available');
    expect(host.textContent).toContain('US CPI');
    expect(host.textContent).toContain('Nothing here is scraped live yet');
  });

  it('escapes an impact brief rather than letting the curator inject markup', () => {
    const page = new HomePage(container);
    page.render();
    page.events = [{
      event_name: 'RBI policy',
      event_date: '2026-09-12',
      impact_brief: '<img src=x onerror="alert(1)">',
    }];
    page.renderEvents();

    const html = container.querySelector('#home-events').innerHTML;
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
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

describe('Home shows, Home does not manage', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('puts the open-positions line below the daily check-in strip and above Your money', () => {
    const page = new HomePage(container);
    page.render();
    const html = container.innerHTML;
    expect(html.indexOf('id="home-ritual"')).toBeLessThan(html.indexOf('id="home-positions"'));
    expect(html.indexOf('id="home-positions"')).toBeLessThan(html.indexOf('id="home-money"'));
    // In the main column, not up by the header.
    expect(html.indexOf('home-nifty-sidebar')).toBeLessThan(html.indexOf('id="home-positions"'));
  });

  it('carries no Exit button; squaring off belongs to the desk', () => {
    const page = new HomePage(container);
    page.render();
    page.positions = [{ id: 'p1', strategy_name: 'Iron Condor', legs: [1, 2, 3, 4], max_loss_inr: 8953.75, opened_at: '2026-09-09T08:37:12+00:00' }];
    page.livePositions = [{ position_id: 'p1', unrealized_pnl_inr: 510.25, unrealized_pnl_pct_of_risk: 5.7, days_remaining_to_expiry: 20 }];
    page.positionsExpanded = true;
    page.renderPositions();
    const strip = container.querySelector('#home-positions').innerHTML;
    expect(strip).toContain('Iron Condor');
    expect(strip).not.toContain('posexit');
    expect(strip).not.toContain('>Exit<');
    expect(strip).toContain('managed on the Strategy Desk');
  });

  it('re-reads positions on the live timer, so a trade appears without a reload', async () => {
    const page = new HomePage(container);
    page.render();
    const calls = { positions: 0 };
    page.loadSnapshot = async () => {};
    page.loadDaily = async () => {};
    page.loadPositions = async () => { calls.positions += 1; };
    await page.refreshLive();
    expect(calls.positions).toBe(1);
  });
});

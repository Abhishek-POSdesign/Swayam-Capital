/**
 * Round 2, PR 1: prices that actually move, and the four rules answering.
 *
 * Covers the socket watchdog (a silent socket degrades to a REST poll instead
 * of freezing the screen), Home's refresh loop and spot subscription, the
 * desk's re-quote loop that never overwrites a typed price, the overnight
 * default with its planned exit date, rule 2's wording and rule 4's verdict.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { SpotWebSocketClient, spotFeed } from '../src/modules/ws-client.js';
import { HomePage } from '../src/pages/home.js';
import { StrategyBuilderPage } from '../src/pages/strategy-builder.js';
import { MarketTickerComponent } from '../src/components/market-ticker.js';
import { api } from '../src/api.js';

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

class FakeSocket {
  constructor(url) {
    this.url = url;
    FakeSocket.instances.push(this);
  }
  close() { this.closed = true; }
}
FakeSocket.instances = [];

function desk(container, legs, patch = {}) {
  const page = new StrategyBuilderPage(container);
  page.renderLayout();
  page.initSubComponents();
  page.spot = 23779.15;
  page.lotSize = 65;
  page.lotSizeSource = 'FYERS contract master, resolved server-side';
  page.capital = CAPITAL;
  page.marginUsed = 0;
  page.targetSpot = 23780;
  page.expiry = '2026-09-29';
  page.today = '2026-09-08';
  page.nextTradingDay = '2026-09-09';
  page.legs = legs;
  page.baseLots = legs.map((l) => l.lots);
  Object.assign(page, patch);
  return page;
}

describe('Spot socket watchdog', () => {
  beforeEach(() => {
    setupTestDOM();
    FakeSocket.instances = [];
    global.WebSocket = FakeSocket;
    global.window.location.protocol = 'http:';
    global.window.location.host = 'localhost:5173';
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    delete global.WebSocket;
  });

  it('falls back to a REST poll when no frame arrives within 10 s, and stops when frames resume', async () => {
    const fetchSpot = vi.fn(async () => ({ spot: 24801.5, as_of: '2026-09-09T05:00:00+00:00' }));
    const ticks = [];
    const client = new SpotWebSocketClient((spot) => ticks.push(spot), { fetchSpot });
    client.connect();
    const ws = FakeSocket.instances[0];
    ws.onopen();

    // Open but silent: nothing for ten seconds.
    await vi.advanceTimersByTimeAsync(9000);
    expect(fetchSpot).not.toHaveBeenCalled();
    expect(client.mode).toBe('idle');

    await vi.advanceTimersByTimeAsync(1100);
    expect(client.mode).toBe('rest');
    expect(fetchSpot).toHaveBeenCalledTimes(1);
    expect(ticks).toEqual([24801.5]);

    await vi.advanceTimersByTimeAsync(3000);
    expect(fetchSpot).toHaveBeenCalledTimes(2);

    // A real frame arrives: the poll stops and the frame is delivered.
    ws.onmessage({ data: JSON.stringify({ spot: 24810, as_of: '2026-09-09T05:00:05+00:00' }) });
    expect(client.mode).toBe('socket');
    expect(client.framesReceived).toBe(1);
    expect(ticks[ticks.length - 1]).toBe(24810);
    await vi.advanceTimersByTimeAsync(6000);
    expect(fetchSpot).toHaveBeenCalledTimes(2); // no further polls

    client.disconnect();
    expect(ws.closed).toBe(true);
  });

  it('publishes every tick to the shared feed, which pages subscribe to', () => {
    const client = new SpotWebSocketClient(null);
    client.connect();
    const seen = [];
    const unsub = spotFeed.subscribe((spot, meta) => seen.push([spot, meta.source]));
    FakeSocket.instances[0].onmessage({ data: JSON.stringify({ spot: 24000, source: 'FYERS quotes, polled every 2 s' }) });
    expect(seen[seen.length - 1]).toEqual([24000, 'FYERS quotes, polled every 2 s']);
    unsub();
    client.disconnect();
  });

  it('ignores pong and non-numeric frames rather than inventing a tick', () => {
    const client = new SpotWebSocketClient(null);
    client.connect();
    const before = client.framesReceived;
    FakeSocket.instances[0].onmessage({ data: 'pong' });
    FakeSocket.instances[0].onmessage({ data: JSON.stringify({ spot: 'n/a' }) });
    expect(client.framesReceived).toBe(before);
    client.disconnect();
  });
});

describe('Home refreshes what claims to be live', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it('re-reads the snapshot and the daily candles every 15 s, and stops in destroy()', async () => {
    const snap = vi.spyOn(api, 'getNiftySnapshot').mockResolvedValue({ cash_pane: { spot: 1 }, fno_pane: {} });
    const candles = vi.spyOn(api, 'getNiftyCandles').mockResolvedValue({ close: [], high: [], low: [] });
    const page = new HomePage(container);
    page.render();
    page.startLiveUpdates();
    expect(snap).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(15000);
    expect(snap).toHaveBeenCalledTimes(1);
    expect(candles).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(15000);
    expect(snap).toHaveBeenCalledTimes(2);

    page.destroy();
    expect(page._refreshTimer).toBeNull();
    expect(page._unsubSpot).toBeNull();
    await vi.advanceTimersByTimeAsync(30000);
    expect(snap).toHaveBeenCalledTimes(2);
  });

  it('follows a spot tick: the sidebar price and today\'s change move, recomputed from the real previous close', () => {
    const page = new HomePage(container);
    page.render();
    page.snapshot = {
      cash_pane: { spot: 24000, prev_close: 24100, day_change_pct: -0.41, spot_freshness: 'LIVE', sector_rotation: [] },
      fno_pane: {},
    };
    page.renderSidebar();
    expect(container.querySelector('#home-nifty-sidebar').textContent).toContain('24,000');

    page.onSpotTick(24341, { asOf: '2026-09-09T05:00:00+00:00' });
    const text = container.querySelector('#home-nifty-sidebar').textContent;
    expect(text).toContain('24,341');
    expect(text).toContain('+1.00%'); // (24341 - 24100) / 24100
    expect(text).toContain('tick');
    expect(text).toContain('IST');
  });

  it('prints breadth and futures volume from the snapshot, with the list date', () => {
    const page = new HomePage(container);
    page.render();
    page.snapshot = {
      cash_pane: {
        spot: 24000, spot_freshness: 'LIVE', sector_rotation: [],
        advances: 31, declines: 18, unchanged: 1, breadth_quoted: 50, breadth_total: 50,
        breadth_as_of: '2026-09-08', breadth_freshness: 'LIVE',
        futures_symbol: 'NSE:NIFTY26SEPFUT', futures_volume: 1234567,
      },
      fno_pane: {},
    };
    page.renderSidebar();
    const text = container.querySelector('#home-nifty-sidebar').textContent;
    expect(text).toContain('Futures volume');
    expect(text).toContain('12,34,567');
    expect(text).toContain('NSE:NIFTY26SEPFUT');
    expect(text).toContain('31 ▲ / 18 ▼');
    expect(text).toContain('50 of 50 quoted');
    expect(text).toContain('list as of 2026-09-08');
    expect(text).not.toContain('no wired source');

    const host = document.createElement('div');
    new MarketTickerComponent(host).render(page.tickerItems());
    expect(host.textContent).toContain('31 ▲ / 18 ▼');
    expect(host.textContent).toContain('Futures volume');
  });

  it('every panel carries the time it was last read, in IST', async () => {
    vi.spyOn(api, 'getRiskCapital').mockResolvedValue(CAPITAL);
    vi.spyOn(api, 'getPositions').mockResolvedValue([]);
    const page = new HomePage(container);
    page.render();
    await page.loadCapital();
    await page.loadPositions();
    expect(container.querySelector('#home-money').textContent).toMatch(/read \d\d:\d\d:\d\d IST/);
    expect(container.querySelector('#home-positions').textContent).toMatch(/read \d\d:\d\d:\d\d IST/);
  });
});

describe('Strategy Desk: live legs and the four rules', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('defaults to carrying overnight and sends the next trading day as the planned exit', async () => {
    let seen = null;
    vi.spyOn(api, 'previewOrder').mockResolvedValue({ ordered_legs: [{ lot_size: 65 }], margin_required_inr: 120000 });
    vi.spyOn(api, 'validateStrategy').mockImplementation(async (payload) => { seen = payload; return { realistic_risk: {}, checks: [], capital: CAPITAL }; });
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130, priceSource: 'live' },
    ]);
    await page.refreshFromServer();
    expect(seen.planned_exit_date).toBe('2026-09-09');
    expect(container.querySelector('#carry-note').textContent).toContain('2026-09-09');
    expect(container.querySelector('#carry-overnight').getAttribute('aria-pressed')).toBe('true');
  });

  it('sends no planned exit when closing today, and says rule 2 was not tested', async () => {
    let seen = null;
    vi.spyOn(api, 'previewOrder').mockResolvedValue({ ordered_legs: [{ lot_size: 65 }], margin_required_inr: 120000 });
    vi.spyOn(api, 'validateStrategy').mockImplementation(async (payload) => {
      seen = payload;
      return { realistic_risk: { loss_inr: 100, cap_inr: 9710, passed: true }, blast_radius: { loss_inr: 200, cap_inr: 48550, passed: true }, checks: [], capital: CAPITAL, intraday: true };
    });
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130, priceSource: 'live' },
    ]);
    page.setCarry('today');
    await page.refreshFromServer();
    expect(seen.planned_exit_date).toBeNull();
    const rules = container.querySelector('#rule-validation-mount').textContent;
    expect(rules).toContain('closing before the bell');
    expect(container.querySelector('#execute-row-mount').textContent).toContain('closing today');
  });

  it('words rule 2 as "if you carry this overnight"', () => {
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130, priceSource: 'live' },
    ], {
      validation: {
        realistic_risk: { loss_inr: 100, cap_inr: 9710, passed: true },
        blast_radius: { loss_inr: 200, cap_inr: 48550, passed: true },
        checks: [], capital: CAPITAL, intraday: false,
        carry: { may_carry_overnight: true, hedged: true, gap_loss_inr: 4200, cap_inr: 19420.05, reasons: [] },
      },
    });
    page.renderRules();
    const rules = container.querySelector('#rule-validation-mount').textContent;
    expect(rules).toContain('if you carry this overnight');
    expect(rules).toContain('4,200');
    expect(rules).toContain('19,420');
  });

  it('rule 4 passes when margin needed plus used fits the ceiling, and fails red with the shortfall when it does not', () => {
    const fits = desk(container, [
      { on: true, bs: 'S', strike: 23900, type: 'CE', lots: 1, price: 95, priceSource: 'live' },
      { on: true, bs: 'B', strike: 24200, type: 'CE', lots: 1, price: 30, priceSource: 'live' },
    ], { preview: { margin_required_inr: 100000, ordered_legs: [{ lot_size: 65 }] }, marginUsed: 50000 });
    fits.renderRules();
    let html = container.querySelector('#rule-validation-mount').innerHTML;
    expect(html).toContain('rl pass');
    expect(html).toContain('1,50,000');
    expect(html).toContain('4,04,961 free after this');

    const short = desk(container, [
      { on: true, bs: 'S', strike: 23900, type: 'CE', lots: 10, price: 95, priceSource: 'live' },
      { on: true, bs: 'B', strike: 24200, type: 'CE', lots: 10, price: 30, priceSource: 'live' },
    ], { preview: { margin_required_inr: 600000, ordered_legs: [{ lot_size: 65 }] }, marginUsed: 50000 });
    short.renderRules();
    html = container.querySelector('#rule-validation-mount').innerHTML;
    expect(html).toContain('rl fail');
    expect(html).toContain('SHORT BY ₹95,039');
  });

  it('names the unpriced leg and still draws rule 4 when a price is missing', async () => {
    const preview = vi.spyOn(api, 'previewOrder');
    const page = desk(container, [
      { on: true, bs: 'B', strike: 24800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 24900, type: 'CE', lots: 1, price: null, priceSource: 'no traded price' },
    ]);
    await page.refreshFromServer();
    expect(preview).not.toHaveBeenCalled();
    const rules = container.querySelector('#rule-validation-mount').textContent;
    expect(rules).toContain('24,900 CE has no traded price');
    expect(rules).toContain('4 · Margin ceiling');
    expect(rules).toContain('5,54,961');
    expect(container.querySelector('#rule-why').textContent).toContain('24,900 CE');
    expect(container.querySelector('#rule-why').textContent).toContain('rules 1, 2 and 3 are not checked');
  });

  it('re-quotes chain-priced legs every 5 s and never overwrites a price he typed', async () => {
    vi.useFakeTimers();
    try {
      let ltp = 200;
      const quote = vi.spyOn(api, 'getOptionQuote').mockImplementation(async () => ({ available: true, ltp, iv: 0.12, source: 'live' }));
      vi.spyOn(api, 'previewOrder').mockResolvedValue({ ordered_legs: [{ lot_size: 65 }] });
      vi.spyOn(api, 'validateStrategy').mockResolvedValue({ realistic_risk: {}, checks: [], capital: CAPITAL });
      const page = desk(container, [
        { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 200, priceSource: 'live' },
        { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 77.5, priceSource: 'your own limit price' },
      ]);
      page.startLiveUpdates();

      ltp = 215;
      await vi.advanceTimersByTimeAsync(5000);
      expect(quote).toHaveBeenCalledTimes(1); // only the chain-priced leg
      expect(page.legs[0].price).toBe(215);
      expect(page.legs[1].price).toBe(77.5);
      expect(page.legs[1].priceSource).toBe('your own limit price');
      // The sentence promising a typed price is never overwritten was cut from
      // the screen on 2026-09-11. The BEHAVIOUR is what matters and it is
      // asserted directly two lines above: leg 1 was re-quoted, leg 2 kept his
      // 77.5 and its own price source.
      expect(container.querySelector('#leg-why').textContent).toContain('prices read');

      page.destroy();
      expect(page._requoteTimer).toBeNull();
      await vi.advanceTimersByTimeAsync(10000);
      expect(quote).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('follows the spot tick stream and never sends 75 as a contract size', () => {
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
    ]);
    page.startLiveUpdates();
    spotFeed.publish(23990.5, { asOf: '2026-09-09T05:00:00+00:00', source: 'test' });
    expect(page.spot).toBe(23990.5);
    expect(container.querySelector('#desk-spot').textContent).toContain('23,990.50');
    expect(container.querySelector('#desk-spot').textContent).toContain('IST');
    expect(JSON.stringify(page.legsPayload())).not.toContain('75');
    page.destroy();
    spotFeed.publish(1.0, { source: 'test' });
    expect(page.spot).toBe(23990.5); // unsubscribed
  });
});

describe('Strategy Desk: a re-quote that cannot read the chain keeps the last real price', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('keeps the last traded price, labelled with its age, instead of blanking every rule on a transient', async () => {
    vi.spyOn(api, 'getOptionQuote').mockResolvedValue({ available: false, ltp: null, error: 'Option chain request error: rate limit', note: 'The chain could not be read' });
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live', priceAt: '2026-09-09T05:00:00+00:00' },
    ]);
    await page.requoteLegs();
    expect(page.legs[0].price).toBe(210);
    expect(page.legs[0].priceSource).toContain('last traded price');
    expect(page.legs[0].priceSource).toContain('rate limit');

    // A first quote that finds no price still leaves the row blank: nothing is seeded.
    page.legs[0].price = null;
    page.legs[0].priceSource = null;
    await page.requoteLegs();
    expect(page.legs[0].price).toBeNull();
  });

  it('a genuine "no traded price" answer, not an error, does blank the price', async () => {
    vi.spyOn(api, 'getOptionQuote').mockResolvedValue({ available: false, ltp: null, error: null, note: 'No real price found' });
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
    ]);
    await page.requoteLegs();
    expect(page.legs[0].price).toBeNull();
  });
});

describe('Strategy Desk: the deleted reward-to-risk rule is not printed', () => {
  it('drops the R:R advisory from the server warnings and keeps the rest', () => {
    setupTestDOM();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
    ], {
      validation: {
        realistic_risk: { loss_inr: 100, cap_inr: 9710, passed: true },
        blast_radius: { loss_inr: 200, cap_inr: 48550, passed: true },
        checks: [], capital: CAPITAL, intraday: true,
        warnings: [
          'Worth knowing before you enter, though nothing here stops you: the reward-to-risk minimum, the single-leg check',
          'This position has no ceiling on its loss.',
        ],
      },
    });
    page.renderRules();
    const why = container.querySelector('#rule-why').textContent;
    expect(why).not.toContain('reward-to-risk');
    expect(why).toContain('the single-leg check');
    expect(why).toContain('no ceiling on its loss');
  });
});

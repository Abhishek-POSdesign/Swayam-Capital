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

    // Something open that was opened before migration 021 recorded the broker
    // margin. The figure is honestly unknown and must never render as zero.
    page.positions = [{ id: 'a1', strategy_name: 'Bear Put Spread', opened_at: '2026-09-08' }];
    page.renderMoney();
    const text = container.querySelector('#home-money').textContent;
    expect(text).toContain('no stored margin');

    // And with the broker figure stored, Home reads the SAME field the desk
    // reads. It said unavailable while the desk showed 84,929 from the same
    // position, which is the fault this replaces.
    page.positions = [
      { id: 'a1', strategy_name: 'Iron Condor', margin_required_inr: 84929.2 },
    ];
    page.renderMoney();
    const agreed = container.querySelector('#home-money').textContent;
    expect(agreed).toContain('84,929');
    expect(agreed).toContain('across 1 open position');
    expect(page.marginUsed()).toBeCloseTo(84929.2, 1);
    expect(text).toContain('unavailable');
  });

  it('keeps the paper book and the real-money book separate, and explains each', () => {
    const page = new HomePage(container);
    page.render();
    page.positions = [];
    page.renderRecord();

    const host = container.querySelector('#home-record');
    // The line used to carry two fixed facts in its own source: "starts clean
    // from 8 September 2026" and "81 build-and-test rows". Both were written
    // into the page, neither was read from anything, and the first contradicted
    // his correction of 2026-09-10. The card reads the phase now.
    expect(host.textContent).toContain('Test trading');
    expect(host.textContent).not.toContain('8 September');
    expect(host.textContent).not.toContain('81 build');

    page.phase = { paper_trading_started: true, paper_trading_started_at: '2026-10-01T04:00:00Z' };
    page.renderRecord();
    expect(container.querySelector('#home-record').textContent).toContain('starts from 2026-10-01');

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

  it('goes quiet with nothing open, and dates the clean start by the phase, not by a fixed day', () => {
    const page = new HomePage(container);
    page.render();
    page.positions = [];
    page.livePositions = [];
    page.renderPositions();

    const host = container.querySelector('#home-positions');
    // Muted: no colour, no blink, and no Manage to press.
    expect(host.innerHTML).toContain('hb quiet');
    // No colour and no breath: the class is never a running band.
    expect(host.innerHTML).not.toMatch(/class="hb [^"]*running/);
    expect(host.innerHTML).not.toContain('tint-');
    expect(host.textContent).toContain('nothing running');
    // The line used to name 8 September in the page's own source. It reads the
    // phase now, so it cannot go on being wrong after paper trading starts.
    expect(host.textContent).toContain('Test trading');
    expect(host.textContent).toContain('starts clean on the day you say');
    expect(host.textContent).not.toContain('8 September');

    page.phase = { paper_trading_started: true, paper_trading_started_at: '2026-10-01T04:00:00Z' };
    page.renderPositions();
    expect(container.querySelector('#home-positions').textContent).toContain('paper record is live');
  });

  it('blinks while a trade runs, goes solid when a target is reached, and never both', () => {
    const page = new HomePage(container);
    page.render();
    page.positions = [{ id: 'p1' }];

    // RUNNING, and the market is open: colour from the money, and it breathes.
    page.livePositions = [{
      position_id: 'p1', strategy_name: 'Iron Condor', state: 'running', alerts: [],
      legs_open: 4, legs_closed: 0, unrealized_pnl_inr: -1240, net_if_exit_now_inr: -1480,
      market_state: 'live', targets: { legs_with_targets: 2, legs_total: 4 },
    }];
    page.renderPositions();
    let host = container.querySelector('#home-positions');
    expect(host.innerHTML).toContain('tint-down');
    expect(host.innerHTML).toContain('running');
    expect(host.innerHTML).not.toContain('solid-');
    expect(host.textContent).toContain('1,240');
    expect(host.textContent).toContain('2 of 4 legs');
    // The name owns the corner and the chip sits beside it, the way the CLOSED
    // chip sits beside NIFTY 50. It used to have the first column to itself.
    expect(host.innerHTML.indexOf('Iron Condor')).toBeLessThan(host.innerHTML.indexOf('hchip'));

    // A LOSS TARGET REACHED: solid red, and the blink stops.
    page.livePositions = [{
      ...page.livePositions[0],
      state: 'alert',
      alerts: [{ scope: 'leg', sequence: 4, leg_label: '23,200 PE', kind: 'loss', level: 170, mark: 171 }],
    }];
    page.renderPositions();
    host = container.querySelector('#home-positions');
    expect(host.innerHTML).toContain('solid-down');
    expect(host.innerHTML).not.toContain('hb tint-down running');
    expect(host.textContent).toContain('loss target hit');
    expect(host.textContent).toContain('23,200 PE');

    // A PROFIT TARGET REACHED: solid green.
    page.livePositions = [{
      ...page.livePositions[0],
      unrealized_pnl_inr: 4200,
      net_if_exit_now_inr: 3960,
      alerts: [{ scope: 'leg', sequence: 3, leg_label: '23,800 CE', kind: 'profit', level: 50, mark: 49 }],
    }];
    page.renderPositions();
    host = container.querySelector('#home-positions');
    expect(host.innerHTML).toContain('solid-up');
    expect(host.textContent).toContain('profit target hit');
  });

  it('does not blink over a frozen number once the market is shut', () => {
    const page = new HomePage(container);
    page.render();
    page.positions = [{ id: 'p1' }];
    page.livePositions = [{
      position_id: 'p1', strategy_name: 'Iron Condor', state: 'running', alerts: [],
      legs_open: 4, unrealized_pnl_inr: 510, net_if_exit_now_inr: 380,
      market_state: 'closing', targets: {},
    }];
    page.renderPositions();
    const host = container.querySelector('#home-positions');
    // A SHUT MARKET GETS ITS OWN COLOUR. His correction, 2026-09-11: green
    // means a profit is running and red means a loss is running, so a frozen
    // figure must wear neither. The band goes calm and says so; the figures
    // themselves keep their green and red, because the money did what it did.
    expect(host.innerHTML).toContain('hb shut');
    expect(host.innerHTML).not.toContain('tint-up');
    expect(host.innerHTML).not.toContain('running');
    expect(host.textContent).toContain('at the close');
  });

  it('colours the strip from the live money and prints the running-loss headroom', () => {
    const page = new HomePage(container);
    page.render();
    page.capital = CAPITAL; // 1% running-loss cap of 9,710.02
    page.positions = [{ id: 'a1' }, { id: 'a2' }];
    page.livePositions = [
      { position_id: 'a1', unrealized_pnl_inr: -800, market_state: 'live' },
      { position_id: 'a2', unrealized_pnl_inr: -440, market_state: 'live' },
    ];
    page.renderPositions();

    const host = container.querySelector('#home-positions');
    // One band per trade, each coloured by its own money. There is no combined
    // figure any more, so there is nothing that can be a partial sum. Counted
    // on the markup: the test DOM hands out a new synthetic element on every
    // querySelector, so attribute selectors find nothing there.
    expect(host.innerHTML.split('data-band=').length - 1).toBe(2);
    expect(host.innerHTML).toContain('tint-down');
    expect(host.textContent).toContain('800');
    expect(host.textContent).toContain('440');

    page.livePositions = [
      { position_id: 'a1', unrealized_pnl_inr: 800, market_state: 'live' },
      { position_id: 'a2', unrealized_pnl_inr: 440, market_state: 'live' },
    ];
    page.renderPositions();
    const now = container.querySelector('#home-positions');
    expect(now.innerHTML).toContain('tint-up');
    expect(now.innerHTML).not.toContain('tint-down');
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

    const host = container.querySelector('#home-positions');
    // The combined figure is still null, and nothing on Home prints one.
    expect(page.combinedPnl()).toBeNull();
    // Each trade answers for itself: the one that priced shows its money, the
    // one that did not says unavailable with its reason. A partial sum is now
    // impossible by construction rather than by a check that could be forgotten.
    expect(host.innerHTML.split('data-band=').length - 1).toBe(2);
    expect(host.textContent).toContain('800');
    expect(host.textContent).toContain('unavailable');
    expect(host.textContent).toContain('strike missing from the chain');
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

  it('manages from Home through the exit ticket, without leaving Home', () => {
    // His decision of 2026-09-10, which replaced "Home shows, Home does not
    // manage": "Give a Manage button, which will open the exit modal. Over
    // there, I can exit all directly, or I can exit one leg where the target
    // is achieved." It opens the ticket here; it does not navigate to the desk.
    const page = new HomePage(container);
    page.render();
    page.positions = [{ id: 'p1' }];
    page.livePositions = [{
      position_id: 'p1', strategy_name: 'Iron Condor', state: 'running', alerts: [],
      legs_open: 4, unrealized_pnl_inr: 510.25, net_if_exit_now_inr: 380,
      market_state: 'live', targets: {},
      legs: [{ sequence: 1, strike: 24200, option_type: 'CE', direction: 'buy', status: 'open', bid: 30.6, ask: 30.75, entry_premium: 34.5, quantity_units: 65 }],
    }];
    page.renderPositions();
    const host = container.querySelector('#home-positions');
    expect(host.innerHTML).toContain('Iron Condor');
    expect(host.innerHTML).toContain('data-manage="p1"');

    page.openManage('p1');
    expect(page.exitTicket).toBeTruthy();
    expect(page.exitTicket.isOpen).toBe(true);
    expect(String(page.exitTicket.position.position_id)).toBe('p1');

    // A squared-off trade cannot be managed, and the button says so.
    page.livePositions = [{ ...page.livePositions[0], state: 'quiet', legs_open: 0 }];
    page.renderPositions();
    expect(container.querySelector('#home-positions').innerHTML).toContain('nothing running');
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

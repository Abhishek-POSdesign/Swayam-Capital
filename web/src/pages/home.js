/**
 * Home — rebuilt to the prototype Abhishek approved on 2026-09-08
 * (docs/reference/home-prototype.html), per docs/UI_BUILD_BRIEF.md.
 *
 * Top to bottom, after round 3: the data-health strip, then open positions as
 * one full-width collapsible line, then a running ticker and the morning ritual
 * as one thin strip, then two columns — a fixed NIFTY sidebar on the left, his
 * money with the four caps folded into it, his record beside the events ahead,
 * and the AI panel on the right.
 *
 * Open positions sits first because at one o'clock with something live it is
 * the most important thing on the page, and when he is flat it costs one muted
 * line. The four caps stopped being a full-width row of tiles: they are one
 * band inside "Your money", under the balance every one of them is a
 * percentage of. No figure appears twice — the margin ceiling is rule 4 and
 * lives with the rules, not with the money tiles.
 *
 * The rule this page is built around: every number on screen came out of an API
 * response, or the screen says "unavailable" and gives the reason. There is no
 * fallback constant anywhere in this file. Panels load independently, so one
 * dead feed leaves the rest of the page standing.
 */

import { api } from '../api.js';
import { MarketTickerComponent } from '../components/market-ticker.js';
import { RitualStripComponent } from '../components/ritual-strip.js';
import { ChatSurfaceComponent } from '../components/chat-surface.js';
import { SoFarTodayCardComponent } from '../components/so-far-today-card.js';
import { PwaInstallPromptComponent } from '../components/pwa-install-prompt.js';
import { DataHealthStrip } from '../components/data-health-strip.js';
import { ExitTicket } from '../components/exit-ticket.js';
import { signed } from '../components/position-area.js';
import { updateHeaderSpot } from '../components/header.js';
import { spotFeed } from '../modules/ws-client.js';
import { inr, num, signedPct, escapeHtml, istTime, flashFor } from '../utils/display.js';

const NA = '<b class="na">unavailable</b>';

/** How often the panels that claim to be live re-read their feeds. */
const REFRESH_MS = 15000;

/** Whether the open-positions strip is expanded, remembered per browser. */
const POSITIONS_KEY = 'swayam-home-positions-expanded';

function readPositionsExpanded() {
  try {
    return localStorage.getItem(POSITIONS_KEY) === '1';
  } catch (_) {
    return false;
  }
}

function writePositionsExpanded(open) {
  try {
    localStorage.setItem(POSITIONS_KEY, open ? '1' : '0');
  } catch (_) {
    /* a browser with storage blocked still gets a working toggle, just not a remembered one */
  }
}

/**
 * An empty value is a dash. Never a zero, because a zero win rate and an
 * unknown win rate are different facts and must not look the same.
 */
const DASH = '<span class="dash">—</span>';

export class HomePage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onOpenAIDrawer, onOpenSettings, onNavigateStrategy }

    this.snapshot = null;
    this.snapshotError = null;
    // null until the data-health check answers: unknown, not open, not shut.
    this.marketOpen = null;
    this.capital = null;
    this.capitalError = null;
    this.positions = null;
    this.positionsError = null;
    /**
     * /api/positions carries a STORED unrealised figure that defaults to zero.
     * The money on screen has to be the money now, so profit and loss comes
     * from /api/positions/live, which values every leg against the FYERS
     * chain. When that endpoint cannot answer, the strip says so rather than
     * showing the stale stored number as though it were current.
     */
    this.livePositions = null;
    this.livePositionsError = null;
    // The exit ticket Manage opens, mounted here on Home. The desk mounts its
    // own; neither borrows the other's.
    this.exitTicket = null;
    // Has paper trading begun. Null until read; treated as "not yet", which is
    // true today and is what the quiet line says.
    this.phase = null;
    this.positionsExpanded = readPositionsExpanded();
    /** Closed-trade KPIs behind "Your record", per book. */
    /** What the last exit attempt did, in money. Cleared on the next load. */
    this.positionsNotice = null;
    this.record = null;
    this.recordError = null;
    this.recordLoading = false;
    this.events = null;
    this.eventsError = null;
    this.daily = null; // derived from real daily candles: day range, average daily move
    this.dailyError = null;
    this.book = 'paper';

    /** The last tick from the spot stream, and when the server read it. */
    this.liveSpot = null;
    this.liveSpotAt = null;
    /** When each feed was last read, ISO. Every panel prints its own. */
    this.readAt = {};
    this._flash = {};
    this._refreshTimer = null;
    this._unsubSpot = null;
    this.refreshMs = REFRESH_MS;

    /**
     * main.js reaches for homePage.niftyChart.retheme() on every route change.
     * The rebuilt sidebar is plain SVG-free markup, so retheme simply redraws
     * it; the property has to exist or navigation throws.
     */
    this.niftyChart = { retheme: () => this.renderSidebar() };
  }

  async init() {
    this.render();
    this.mountComponents();
    this.startDataHealth();
    // Independently try-caught, so one dead feed cannot blank the page.
    this.loadData();
    this.startLiveUpdates();
  }

  /**
   * The same strip as the desk, for the same reason: he must never have to
   * work out for himself whether a number on screen is still real.
   */
  startDataHealth() {
    const host = this.container.querySelector('#home-data-health');
    if (!host || this.dataHealth) return;
    this.dataHealth = new DataHealthStrip(host, {
      onHealth: (health) => {
        // One clock for the whole page. The NIFTY card used to call a price
        // LIVE whenever any value had arrived, so at 19:12 with the market
        // shut it said LIVE over a closing price, which is exactly the kind
        // of claim this terminal must never make.
        const open = health ? Boolean(health.market_open) : null;
        if (open === this.marketOpen) return;
        this.marketOpen = open;
        this.renderSidebar();
      },
    });
    this.dataHealth.init().catch(() => {});
  }

  /**
   * Until round 2 this page had no timer of any kind: the ticker and the NIFTY
   * sidebar were frozen at page load. Now the spot follows the tick stream and
   * the snapshot and daily candles are re-read every 15 seconds. Both are torn
   * down in destroy(), or navigating away would leak them.
   */
  startLiveUpdates() {
    if (!this._unsubSpot) {
      this._unsubSpot = spotFeed.subscribe((spot, meta) => this.onSpotTick(spot, meta));
    }
    if (typeof setInterval === 'function' && !this._refreshTimer) {
      this._refreshTimer = setInterval(() => this.refreshLive(), this.refreshMs);
      if (this._refreshTimer && typeof this._refreshTimer.unref === 'function') this._refreshTimer.unref();
    }
  }

  async refreshLive() {
    // Positions used to be read once, at page load, so a trade taken on the
    // desk did not appear here until a full reload. He reported exactly that
    // on 2026-09-09. They now ride the same timer as the snapshot.
    await Promise.all([this.loadSnapshot(), this.loadDaily(), this.loadPositions()]);
    this.renderTicker();
  }

  onSpotTick(spot, meta) {
    if (typeof spot !== 'number' || !Number.isFinite(spot)) return;
    this.liveSpot = spot;
    this.liveSpotAt = (meta && meta.asOf) || new Date().toISOString();
    this.renderSidebar();
    this.renderTicker();
    const chg = this.dayChangePct();
    updateHeaderSpot(spot, null, chg);
  }

  /** The spot on screen: the latest tick if one has arrived, else the snapshot's. */
  spotNow() {
    if (typeof this.liveSpot === 'number') return this.liveSpot;
    const c = this.cash();
    return c && typeof c.spot === 'number' ? c.spot : null;
  }

  /**
   * Today's change, recomputed from the live spot against the real previous
   * close the snapshot carries. Without a previous close it is the snapshot's
   * own figure, which is as old as the snapshot.
   */
  dayChangePct() {
    const c = this.cash();
    if (!c) return null;
    const spot = this.spotNow();
    if (typeof this.liveSpot === 'number' && typeof c.prev_close === 'number' && c.prev_close > 0 && spot !== null) {
      return ((spot - c.prev_close) / c.prev_close) * 100;
    }
    return typeof c.day_change_pct === 'number' ? c.day_change_pct : null;
  }

  /**
   * A freshness word that cannot outrank the clock.
   *
   * The snapshot's `spot_live` means "FYERS returned a number", not "the market
   * is open", so both `spot_freshness` and `sector_freshness` still read LIVE
   * after the close. That is being corrected on the server; until it is, and
   * for good afterwards, no label on this page says LIVE unless
   * /api/market/data-health — the one clock — says the market is open.
   *
   * Verified against the running backend at 20:51 IST on 2026-09-08: the
   * Sectors card said "LIVE · read 20:51 IST" with the health strip beside it
   * saying CLOSED.
   */
  _freshLabel(raw) {
    if (this.marketOpen === false) return 'CLOSED';
    const word = raw ? String(raw) : null;
    // An unknown clock is not permission to claim a live price.
    if (this.marketOpen !== true && word && word.toUpperCase() === 'LIVE') return 'UNVERIFIED';
    return word || 'UNAVAILABLE';
  }

  _readStamp(key) {
    const t = istTime(this.readAt[key]);
    return t ? `read ${t} IST` : 'not read yet';
  }

  render() {
    this.container.innerHTML = `
      <div class="sw-desk">
        <div class="app">
          <div class="top">
            <h2 class="pagename">Home <em>· so far today</em></h2>
          </div>

          <div id="home-data-health"></div>
          <div id="home-ticker"></div>
          <div id="home-ritual"></div>
          <div id="home-pwa-prompt-container"></div>

          <div class="cols">
            <div class="side home-left-col" id="home-nifty-sidebar"></div>

            <main class="home-right-col">
              <h1 class="sr-only">Market Prep</h1>
              <div class="bento-grid">
                <!-- His decision, 2026-09-09, asked for twice: the open-positions
                     line sits below the black daily check-in strip and above
                     "Your money", in the main column, not up by the header.
                     Home shows the position; the desk manages it. -->
                <div class="span-12" id="home-positions"></div>
                <div id="home-exit-ticket"></div>
                <div class="span-12" id="home-money"></div>
                <div class="span-6" id="home-record"></div>
                <div class="span-6" id="home-events"></div>
                <div class="span-12" id="home-ai"></div>
              </div>
            </main>
          </div>
        </div>
      </div>
    `;
    this.renderSidebar();
    this.renderMoney();
    this.renderPositions();
    this.renderEvents();
    this.renderRecord();
  }

  mountComponents() {
    const pwa = this.container.querySelector('#home-pwa-prompt-container');
    if (pwa) {
      this.pwaPromptComponent = new PwaInstallPromptComponent(pwa);
      this.pwaPromptComponent.render();
    }

    const tickerHost = this.container.querySelector('#home-ticker');
    if (tickerHost) {
      this.ticker = new MarketTickerComponent(tickerHost);
      this.ticker.render(this.tickerItems());
    }

    const ritualHost = this.container.querySelector('#home-ritual');
    if (ritualHost) {
      this.ritual = new RitualStripComponent(ritualHost);
      this.ritual.init();
    }

    // The AI chat is kept exactly as it is. It is mounted, not redesigned.
    const aiHost = this.container.querySelector('#home-ai');
    if (aiHost) {
      this.aiBriefComponent = new ChatSurfaceComponent(aiHost, {
        onOpenSettings: () => this.options.onOpenSettings && this.options.onOpenSettings(),
        onNavigateStrategy: (dest) => {
          if (this.options.onNavigateStrategy) this.options.onNavigateStrategy(dest);
          else if (typeof window !== 'undefined') window.location.href = dest;
        },
      });
      this.aiBriefComponent.init();

      // So Far Today now lives at the top of the AI panel, above the
      // conversation. Manual button, 60-minute cache, daily cap — it must never
      // fire on page load, and init() only reads the cache status.
      const slot = aiHost.querySelector('#chat-top-slot');
      if (slot) {
        this.soFarTodayComponent = new SoFarTodayCardComponent(slot);
        this.soFarTodayComponent.init();
      }
    }
  }

  // ---------------------------------------------------------------- loading

  async loadData() {
    await Promise.all([
      this.loadSnapshot(),
      this.loadCapital(),
      this.loadPhase(),
      this.loadPositions(),
      this.loadEvents(),
      this.loadDaily(),
      this.loadRecord(),
    ]);
    this.renderTicker();
  }

  async loadSnapshot() {
    try {
      this.snapshot = await api.getNiftySnapshot();
      this.snapshotError = null;
      this.readAt.snapshot = new Date().toISOString();
    } catch (err) {
      this.snapshot = null;
      this.snapshotError = (err && err.message) || String(err);
    }
    this.renderSidebar();
    this.syncHeaderSpot();
  }

  async loadCapital() {
    try {
      this.capital = await api.getRiskCapital();
      this.capitalError = null;
      this.readAt.capital = new Date().toISOString();
    } catch (err) {
      this.capital = null;
      this.capitalError = (err && err.message) || String(err);
    }
    this.renderMoney();
    // The strip prints how much of the running-loss cap a live loss has eaten,
    // and that cap is a percentage of the balance this call just read.
    this.renderPositions();
  }

  /**
   * Has paper trading begun. Read once per visit, because it changes exactly
   * once, on a day he chooses, by a script only he runs.
   *
   * A failure is NOT an error on his screen. It leaves `phase` null, which the
   * quiet line reads as "not yet", which is true today and is the safe
   * direction: telling him his paper record has begun when it has not would
   * put his own judgement of the terminal on a false footing.
   */
  async loadPhase() {
    try {
      this.phase = await api.getPhase();
    } catch (_) {
      this.phase = null;
    }
    this.renderPositions();
  }

  async loadPositions() {
    try {
      const res = await api.getPositions('open');
      this.positions = Array.isArray(res) ? res : (res && res.positions) || [];
      this.positionsError = null;
      this.readAt.positions = new Date().toISOString();
    } catch (err) {
      this.positions = null;
      this.positionsError = (err && err.message) || String(err);
    }
    this.renderPositions();
    this.renderMoney(); // margin used is only known once positions are in
    // Valuing a position costs a FYERS chain read per expiry. With nothing
    // open there is nothing to value, so the call is not made at all.
    await this.loadLivePositions();
  }

  /**
   * Live profit and loss for whatever is open. /api/positions/live prices every
   * leg against the chain and 503s rather than guess when FYERS is unreachable,
   * which is why the failure is kept and shown instead of swallowed.
   */
  async loadLivePositions() {
    if (Array.isArray(this.positions) && !this.positions.length) {
      this.livePositions = [];
      this.livePositionsError = null;
      this.readAt.livePositions = this.readAt.positions;
      this.renderPositions();
      return;
    }
    try {
      const res = await api.getPositionsLive();
      this.livePositions = Array.isArray(res) ? res : (res && res.positions) || [];
      this.livePositionsError = null;
      this.readAt.livePositions = new Date().toISOString();
    } catch (err) {
      this.livePositions = null;
      this.livePositionsError = (err && err.message) || String(err);
    }
    this.renderPositions();
  }

  /**
   * The closed-trade figures behind "Your record", for one book at a time.
   * Paper and real money are asked for separately, because adding them
   * together and calling the total "Paper" would be a claim, not a fact.
   */
  async loadRecord() {
    const book = this.book;
    this.recordLoading = true;
    this.renderRecord();
    try {
      const res = await api.getJournalTrades({ status: 'closed', mode: book, limit: 1 });
      // He may have flipped the toggle while this was in flight.
      if (book !== this.book) return;
      this.record = (res && res.kpis) || null;
      this.recordError = this.record ? null : 'The journal answered without any figures.';
      this.readAt.record = new Date().toISOString();
    } catch (err) {
      if (book !== this.book) return;
      this.record = null;
      this.recordError = (err && err.message) || String(err);
    } finally {
      if (book === this.book) {
        this.recordLoading = false;
        this.renderRecord();
      }
    }
  }

  async loadEvents() {
    try {
      const res = await api.getMacroEvents(false);
      this.events = (res && res.events) || [];
      this.eventsError = null;
      this.readAt.events = new Date().toISOString();
    } catch (err) {
      this.events = null;
      this.eventsError = (err && err.message) || String(err);
    }
    this.renderEvents();
  }

  /**
   * The day's range and the 20-session average daily move are not on the
   * snapshot endpoint. They are measured here from the real daily candles, the
   * same way the backend measures the move for the gap test: the mean absolute
   * close-to-close change over the last 20 changes. Fewer than 21 bars and this
   * stays null, so the page says unavailable instead of estimating.
   */
  async loadDaily() {
    try {
      const c = await api.getNiftyCandles('1d');
      const closes = (c && c.close) || [];
      const highs = (c && c.high) || [];
      const lows = (c && c.low) || [];
      const out = { dayHigh: null, dayLow: null, averageDailyMove: null, sessionsUsed: 0 };
      if (highs.length && lows.length) {
        out.dayHigh = highs[highs.length - 1];
        out.dayLow = lows[lows.length - 1];
      }
      if (closes.length >= 21) {
        const recent = closes.slice(-21);
        let total = 0;
        for (let i = 1; i < recent.length; i++) total += Math.abs(recent[i] - recent[i - 1]);
        out.sessionsUsed = recent.length - 1;
        out.averageDailyMove = total / out.sessionsUsed;
      }
      this.daily = out;
      this.dailyError = null;
      this.readAt.daily = new Date().toISOString();
    } catch (err) {
      this.daily = null;
      this.dailyError = (err && err.message) || String(err);
    }
    this.renderSidebar();
  }

  // ---------------------------------------------------------------- pieces

  cash() { return (this.snapshot && this.snapshot.cash_pane) || null; }
  fno() { return (this.snapshot && this.snapshot.fno_pane) || null; }

  /**
   * The header pill is the one place the spot is shown as chrome, so home does
   * not repeat it. It gets the real change figure or nothing at all.
   */
  syncHeaderSpot() {
    const c = this.cash();
    const spot = c && typeof c.spot === 'number' ? c.spot : null;
    const chg = c && typeof c.day_change_pct === 'number' ? c.day_change_pct : null;
    if (spot !== null) updateHeaderSpot(spot, null, chg);
  }

  tickerItems() {
    const c = this.cash() || {};
    const f = this.fno() || {};
    const d = this.daily || {};
    const cap = this.capital || {};
    const spot = this.spotNow();
    const chg = this.dayChangePct();
    const spotNote = typeof this.liveSpot === 'number'
      ? `tick ${istTime(this.liveSpotAt) || ''}`.trim()
      : c.spot_freshness ? String(c.spot_freshness).toLowerCase() : '';
    const items = [
      { label: 'NIFTY 50', value: num(spot, 2), raw: spot, note: spotNote, dir: (chg || 0) < 0 ? 'down' : 'up' },
      { label: 'Today', value: signedPct(chg), raw: chg, dir: (chg || 0) < 0 ? 'down' : 'up' },
      { label: 'Day low', value: num(d.dayLow, 2) },
      { label: 'Day high', value: num(d.dayHigh, 2) },
      { label: '20d low', value: c.range_20d ? num(c.range_20d.low, 2) : null },
      { label: '20d high', value: c.range_20d ? num(c.range_20d.high, 2) : null },
      { label: 'India VIX', value: num(f.india_vix, 2) },
      { label: 'ATR 20', value: num(c.atr_20, 0) },
      { label: '20 DMA', value: num(c.dma_20, 0) },
      { label: 'Realised vol 20d', value: c.realized_vol_20 === null || c.realized_vol_20 === undefined ? null : `${c.realized_vol_20}%` },
      { label: '20d avg move', value: d.averageDailyMove ? `${Math.round(d.averageDailyMove)} pts` : null, note: d.sessionsUsed ? `${d.sessionsUsed} sessions` : '' },
      { label: 'Put-call ratio', value: num(f.weekly_pcr, 2), note: 'weekly' },
      { label: 'Max pain', value: num(f.max_pain, 0) },
    ];
    (c.sector_rotation || []).forEach((s) => {
      items.push({
        label: s.name,
        value: signedPct(s.change_pct),
        dir: (s.change_pct || 0) < 0 ? 'down' : 'up',
      });
    });
    items.push({ label: 'Balance', value: inr(cap.risk_capital_inr), note: cap.source ? 'FYERS funds()' : '' });
    items.push({ label: 'Margin ceiling', value: inr(cap.deployable_margin_ceiling_inr), note: cap.ceiling_unavailable_reason || '' });
    // Breadth is counted from a real FYERS quote of all 50 constituents now.
    const breadth = this.breadthText();
    items.push({ label: 'Breadth', value: breadth.value, note: breadth.note });
    items.push({
      label: 'Futures volume',
      value: typeof c.futures_volume === 'number' ? num(c.futures_volume, 0) : null,
      raw: typeof c.futures_volume === 'number' ? c.futures_volume : null,
      note: c.futures_symbol || c.futures_volume_unavailable_reason || '',
    });
    return items;
  }

  /** "31 ▲ / 18 ▼" with how many of the 50 were quoted and the list's date. */
  breadthText() {
    const c = this.cash() || {};
    if (typeof c.advances !== 'number' || typeof c.declines !== 'number') {
      return { value: null, note: c.breadth_unavailable_reason || 'no constituent quotes' };
    }
    const quoted = typeof c.breadth_quoted === 'number' && typeof c.breadth_total === 'number'
      ? `${c.breadth_quoted} of ${c.breadth_total} quoted`
      : '';
    const asOf = c.breadth_as_of ? `list as of ${c.breadth_as_of}` : '';
    return {
      value: `${c.advances} ▲ / ${c.declines} ▼`,
      note: [quoted, asOf].filter(Boolean).join(', '),
    };
  }

  renderTicker() {
    if (this.ticker) this.ticker.render(this.tickerItems());
  }

  _rangeBar(label, low, high, spot) {
    if (typeof low !== 'number' || typeof high !== 'number' || typeof spot !== 'number' || high <= low) {
      return `<div class="rangebar">
        <div class="lbl"><span>${escapeHtml(label)}</span><span class="na">unavailable</span></div>
        <div class="track"></div></div>`;
    }
    const pos = Math.max(0, Math.min(100, ((spot - low) / (high - low)) * 100));
    return `<div class="rangebar">
      <div class="lbl"><span>${escapeHtml(num(low, 0))}</span><span>${escapeHtml(label)}</span><span>${escapeHtml(num(high, 0))}</span></div>
      <div class="track"><i class="fill" style="left:0;right:0;opacity:.5"></i>
        <span class="dot" style="left:${pos.toFixed(1)}%"></span></div></div>`;
  }

  /** "0d · 1 session" rather than the server's long sentence, which wraps the rail. */
  _dte(dte) {
    if (!dte) return null;
    if (typeof dte.calendar_days === 'number') {
      const sessions = typeof dte.trading_sessions === 'number'
        ? ` · ${dte.trading_sessions} session${dte.trading_sessions === 1 ? '' : 's'}`
        : '';
      return `${dte.calendar_days}d${sessions}`;
    }
    return dte.formatted || null;
  }

  _kv(label, formatted, colour, note) {
    const body = formatted === null || formatted === undefined
      ? NA
      : `<b${colour ? ` style="color:${colour}"` : ''}>${escapeHtml(formatted)}</b>`;
    const sub = note ? `<i class="kvn">${escapeHtml(note)}</i>` : '';
    return `<div class="kv"><span>${escapeHtml(label)}${sub}</span>${body}</div>`;
  }

  renderSidebar() {
    const host = this.container.querySelector('#home-nifty-sidebar');
    if (!host) return;

    if (!this.snapshot) {
      host.innerHTML = `<div class="card"><h3>NIFTY 50 <span class="tag t-na">unavailable</span></h3>
        <div class="empty">The market snapshot could not be read.<br>
        <span style="color:var(--fg-3);font-size:12px">${escapeHtml(this.snapshotError || 'No response yet.')}</span></div></div>`;
      return;
    }

    const c = this.cash() || {};
    const f = this.fno() || {};
    const d = this.daily || {};
    const spot = this.spotNow();
    const chg = this.dayChangePct();
    const hasSpot = typeof this.liveSpot === 'number';
    // `marketOpen` is null until the health check answers, and an unknown
    // clock must not be reported as a live price.
    const live = hasSpot && this.marketOpen === true;
    const fresh = live ? 'LIVE' : this._freshLabel(c.spot_freshness);
    const spotInt = spot === null ? null : Math.floor(spot);
    const spotFrac = spot === null ? null : (spot - Math.floor(spot)).toFixed(2).slice(1);
    const spotFlash = flashFor(this._flash, 'spot', spot);
    // Two different questions, and one flag was wrongly answering both. The
    // STAMP says where this number came from, so a tick that really arrived is
    // named as a tick whatever the clock says. The BADGE above says whether it
    // is still live, which is the market's business, not the tick's. After the
    // close this reads "closed · tick 15:29 IST", which is the whole truth.
    const spotStamp = hasSpot ? `tick ${istTime(this.liveSpotAt) || ''} IST` : this._readStamp('snapshot');
    const breadth = this.breadthText();

    const dmaGap = spot !== null && typeof c.dma_20 === 'number' ? spot - c.dma_20 : null;

    const sectors = (c.sector_rotation || []).map((s) => {
      if (typeof s.change_pct !== 'number') {
        return `<div class="sect"><span>${escapeHtml(s.name)}</span><span class="bar"></span>
          <b class="na" style="font-family:var(--m);font-size:11.5px">unavailable</b></div>`;
      }
      const w = Math.min(50, (Math.abs(s.change_pct) / 2.5) * 50);
      const down = s.change_pct < 0;
      return `<div class="sect"><span>${escapeHtml(s.name)}</span>
        <span class="bar"><i style="background:${down ? 'var(--down)' : 'var(--up)'};${down ? `right:50%;left:${(50 - w).toFixed(1)}%` : `left:50%;width:${w.toFixed(1)}%`}"></i></span>
        <b style="font-family:var(--m);color:${down ? 'var(--down)' : 'var(--up)'};font-size:12px">${escapeHtml(signedPct(s.change_pct))}</b></div>`;
    }).join('');

    host.innerHTML = `
      <div class="card">
        <h3>NIFTY 50 <span class="tag ${fresh === 'LIVE' ? 't-live' : 't-na'}">${escapeHtml(String(fresh).toLowerCase())}</span><span class="r">FYERS · ${escapeHtml(spotStamp)}</span></h3>
        <div class="hero">
          <div class="px${spotFlash}" id="home-spot-px">${spot === null ? '<span class="na" style="font-size:.5em">unavailable</span>' : `${escapeHtml(num(spotInt, 0))}<span style="font-size:.55em;color:var(--fg-2)">${spotFrac}</span>`}</div>
          <div class="sub">
            ${chg === null
              ? '<span class="na">no change figure</span>'
              : `<span style="color:${chg < 0 ? 'var(--down)' : 'var(--up)'};font-weight:600">${chg < 0 ? '▼' : '▲'} ${escapeHtml(signedPct(chg))}</span>`}
            <span style="color:var(--fg-3)">today</span>
          </div>
        </div>
        ${this._rangeBar('DAY RANGE', d.dayLow, d.dayHigh, spot)}
        ${this._rangeBar('20-DAY RANGE', c.range_20d && c.range_20d.low, c.range_20d && c.range_20d.high, spot)}
        ${this._rangeBar('50-DAY RANGE', c.range_50d && c.range_50d.low, c.range_50d && c.range_50d.high, spot)}
        ${this._kv('Average daily move, 20 sessions', d.averageDailyMove ? `${Math.round(d.averageDailyMove)} pts` : null)}
        ${this._kv('ATR 20', num(c.atr_20, 0))}
        ${this._kv('Realised vol, 20d', typeof c.realized_vol_20 === 'number' ? `${c.realized_vol_20}%` : null)}
        ${this._kv('20-day moving average', num(c.dma_20, 0), dmaGap === null ? null : dmaGap < 0 ? 'var(--down)' : 'var(--up)')}
        ${this._kv('Spot against 20 DMA', dmaGap === null ? null : `${dmaGap < 0 ? '−' : '+'}${Math.round(Math.abs(dmaGap))}`, dmaGap === null ? null : dmaGap < 0 ? 'var(--down)' : 'var(--up)')}
        ${this._kv('Futures volume', typeof c.futures_volume === 'number' ? num(c.futures_volume, 0) : null, null, c.futures_symbol || c.futures_volume_unavailable_reason || null)}
        ${this._kv('Advances / declines', breadth.value, null, breadth.note)}
        ${this._kv('Sentiment', c.sentiment || null)}
        <div class="why">Sentiment is computed from spot against the 20-day average and where price sits inside the 20-day range. Breadth counts the 50 NIFTY constituents quoted live from FYERS. Volume is the front-month NIFTY futures contract, because the index itself has no volume. Anything not measured says unavailable.</div>
      </div>

      <div class="card">
        <h3>Sectors today <span class="r">${escapeHtml(this._freshLabel(c.sector_freshness).toLowerCase())} · ${escapeHtml(this._readStamp('snapshot'))}</span></h3>
        ${sectors || '<div class="empty">No sector figures in this response.</div>'}
      </div>

      <div class="card">
        <h3>Options, weekly <span class="r">chain · ${escapeHtml(this._readStamp('snapshot'))}</span></h3>
        ${this._kv('India VIX', num(f.india_vix, 2))}
        ${this._kv('Put-call ratio', num(f.weekly_pcr, 2))}
        ${this._maxPainRow(f)}
        ${this._kv('Days to weekly expiry', this._dte(f.weekly_dte))}
        ${this._kv('Days to monthly expiry', this._dte(f.monthly_dte))}
      </div>`;
  }

  /**
   * Max pain, saying WHICH EXPIRY it belongs to.
   *
   * docs/PLAN.md 2.12.5 item 9. On 2026-09-10 this card read 23,500 while
   * the desk's option chain read 24,000, and neither said which expiry it
   * meant. Both were right: this one is computed from the WEEKLY chain in
   * nifty_snapshot.py, and the desk computes it for whatever expiry is
   * selected there, which is usually the monthly.
   *
   * With no expiry to name it with, the figure is not shown at all. An
   * unlabelled max pain is exactly what confused the two screens.
   */
  _maxPainRow(f) {
    const label = this._expiryLabel(f && f.weekly_expiry);
    if (!label) {
      return this._kv(
        'Max pain',
        null,
        null,
        'the expiry it belongs to is unavailable, and an unlabelled max pain is what confused this card and the option chain',
      );
    }
    return this._kv(
      `Max pain, ${label} weekly`,
      num(f.max_pain, 0),
      null,
      'the option chain on the desk shows it for the expiry selected there',
    );
  }

  /** "15 Sep" from an ISO date, the way every expiry reads on the desk. */
  _expiryLabel(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
    if (!m) return null;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = months[Number(m[2]) - 1];
    return month ? `${Number(m[3])} ${month}` : null;
  }

  _money(k, formatted, sub, colour, accent = false) {
    return `<div class="mn"><div class="k">${escapeHtml(k)}</div>
      <div class="v${accent ? ' acc' : ''}"${colour ? ` style="color:${colour}"` : ''}>${formatted === null || formatted === undefined ? '<span class="na" style="font-size:14px">unavailable</span>' : escapeHtml(formatted)}</div>
      <div class="s">${escapeHtml(sub || '')}</div></div>`;
  }

  renderMoney() {
    const host = this.container.querySelector('#home-money');
    if (!host) return;
    const cap = this.capital;
    if (!cap) {
      host.innerHTML = `<div class="card"><h3>Your money <span class="r">unavailable</span></h3>
        <div class="empty">Your balance could not be read, so nothing derived from it is shown.
        Every one of today's four caps is a percentage of that balance, so without it there is
        nothing honest to put here.<br>
        <span style="color:var(--fg-3);font-size:12px">${escapeHtml(this.capitalError || 'No response yet.')}</span></div></div>`;
      return;
    }
    const used = this.marginUsed();
    host.innerHTML = `
      <div class="card">
        <h3>Your money <span class="r">${escapeHtml(cap.source || 'source not stated')}${cap.taken_at ? `, broker read ${escapeHtml(istTime(cap.taken_at) || String(cap.taken_at))} IST` : ''} · ${escapeHtml(this._readStamp('capital'))}</span></h3>
        <div class="money">
          ${this._money('Balance', inr(cap.risk_capital_inr), 'total', null, true)}
          ${this._money('Free cash', inr(cap.free_cash_inr), 'unpledged')}
          ${this._money('Collateral', inr(cap.collateral_inr), 'pledged holdings')}
          ${this._marginTile(cap, used)}
        </div>
        ${this._capsBand(cap)}
        ${cap.reconciliation_note ? `<div class="why">${escapeHtml(cap.reconciliation_note)}</div>` : ''}
      </div>`;
  }

  /**
   * The four caps, as one band under the money tiles rather than the
   * full-width row of four large tiles they used to be. They sit here because
   * every one of them is a percentage of the balance immediately above, which
   * is the only honest place for them.
   *
   * The band is visibly a different thing from the tiles above it — its own
   * ground, its own heading — because what he holds and what he may risk are
   * two different questions and he asked for them not to blur.
   *
   * The margin ceiling is rule 4 and appears HERE ONLY. It used to be printed
   * both as a money tile and as a limit, and he counted it twice on screen.
   */
  _capsBand(cap) {
    const bal = typeof cap.risk_capital_inr === 'number' ? cap.risk_capital_inr : null;
    // Rule 2's cap is 2% of the same live balance. Rules 1 and 3 come back named.
    const gapCap = bal === null ? null : bal * 0.02;
    const one = (k, value, sub) =>
      `<div class="cap"><div class="ck">${escapeHtml(k)}</div>
        <div class="cv">${value === null || value === undefined ? '<span class="na">unavailable</span>' : escapeHtml(value)}</div>
        <div class="cs">${escapeHtml(sub)}</div></div>`;

    return `<div class="caps">
      <div class="capsh">Today's caps<i>a percentage of the balance above, never a stored number</i></div>
      <div class="capsr">
        ${one('1 · Running loss', inr(cap.primary_risk_cap_inr), '1% · exit, no debate')}
        ${one('2 · Overnight gap', inr(gapCap), '2% · at twice the average daily move')}
        ${one('3 · Black swan', inr(cap.black_swan_fuse_inr), '5% · worst case at expiry')}
        ${one('4 · Margin ceiling', inr(cap.deployable_margin_ceiling_inr), cap.ceiling_unavailable_reason || '2x cash equivalent')}
      </div>
    </div>`;
  }

  /**
   * Margin used, only once positions have been read, and only if a position
   * actually carries the figure.
   *
   * Checked against /api/positions on 2026-09-08: a stored position has no
   * margin field of any kind. So with nothing open this is a true zero, and
   * with something open it is honestly unknown until the broker is asked. It is
   * never assumed, and the sub-line below says which of the two it is.
   */
  /**
   * Margin used, with how much of rule 4 it has taken and a bar to read it by.
   *
   * Rule 4 is the deployable margin ceiling, twice the cash equivalent, and it
   * is a percentage of the balance read fresh this session. No ceiling, no
   * share, and the tile says so instead of drawing an empty bar that looks
   * like zero used.
   */
  _marginTile(cap, used) {
    const ceiling = cap && typeof cap.deployable_margin_ceiling_inr === 'number'
      ? cap.deployable_margin_ceiling_inr
      : null;
    const share = used !== null && ceiling !== null && ceiling > 0 ? (used / ceiling) * 100 : null;
    const note = share === null
      ? this.marginUsedNote()
      : `${this.marginUsedNote()} · ${share.toFixed(0)}% of rule 4`;
    const bar = share === null
      ? ''
      : `<div class="mbar"><i style="width:${Math.max(0, Math.min(100, share)).toFixed(1)}%"></i></div>`;
    return `<div class="mn"><div class="k">Margin used</div>
      <div class="v" style="color:var(--fg-2)">${used === null ? '<span class="na" style="font-size:14px">unavailable</span>' : escapeHtml(inr(used))}</div>
      <div class="s">${escapeHtml(note)}</div>${bar}</div>`;
  }

  marginUsed() {
    if (!Array.isArray(this.positions)) return null;
    if (!this.positions.length) return 0;
    let total = 0;
    let missing = 0;
    for (const p of this.positions) {
      if (typeof p.margin_required_inr === 'number') total += p.margin_required_inr;
      else missing += 1;
    }
    // One position without it makes the whole figure unavailable. A partial
    // sum is a smaller number that looks whole, which is exactly what he must
    // never be shown. Identical to StrategyBuilderPage.refreshPositions.
    return missing === 0 ? total : null;
  }

  marginUsedNote() {
    if (!Array.isArray(this.positions)) return 'positions not read yet';
    if (!this.positions.length) return 'nothing open';
    const missing = this.positions.filter((p) => typeof p.margin_required_inr !== 'number').length;
    if (missing) {
      return `${missing} open position${missing === 1 ? ' has' : 's have'} no stored margin (opened before it was recorded)`;
    }
    const n = this.positions.length;
    return `across ${n} open position${n === 1 ? '' : 's'}`;
  }

  // ------------------------------------------------- open positions, the strip

  /**
   * Combined unrealised profit and loss across everything open, from the live
   * valuation only.
   *
   * A partial sum is not a total. If any open position could not be valued,
   * this returns null and the strip says the money is unavailable, rather than
   * quietly adding up the legs that happened to price and presenting the
   * result as his position.
   */
  combinedPnl() {
    if (!Array.isArray(this.livePositions) || !this.livePositions.length) return null;
    let total = 0;
    for (const p of this.livePositions) {
      if (typeof p.unrealized_pnl_inr !== 'number' || !Number.isFinite(p.unrealized_pnl_inr)) return null;
      total += p.unrealized_pnl_inr;
    }
    return total;
  }

  /**
   * How much of rule 1 a running loss has eaten, as a percentage. Only a loss
   * consumes the running-loss cap, so a position in profit returns null and the
   * strip simply does not print a headroom figure.
   */
  runningLossUsedPct() {
    const pnl = this.combinedPnl();
    const cap = this.capital && this.capital.primary_risk_cap_inr;
    if (typeof pnl !== 'number' || pnl >= 0) return null;
    if (typeof cap !== 'number' || !(cap > 0)) return null;
    return (Math.abs(pnl) / cap) * 100;
  }

  /**
   * THE RUNNING-TRADE BAND. Replaced the collapsible strip on 2026-09-10.
   *
   * His words, 2026-09-10: "A running trade is unmistakable on Home and goes
   * quiet only when squared off." He chose Option B, the whole band coloured
   * from the money, and the coloured edge is gone.
   *
   * THE THREE STATES, IN HIS OWN WORDS, because a first reading had them
   * backwards and he corrected it:
   *
   *   BLINKING  the trade is running. A gentle breath, never a strobe, "so
   *             that it always attracts attention that my profit and losses
   *             are running."
   *   SOLID     green or red. A target HE set was reached, profit or loss, on
   *             a leg or on the trade. It stops blinking and it needs him.
   *   MUTED     nothing open, or squared off. "As soon as the trade is squared
   *             off, everything goes mute: no blink, no color."
   *
   * THE STATE IS NOT DECIDED HERE. It arrives on `/api/positions/live` as
   * `state`, computed by services/targets.py, so Home and the desk cannot
   * disagree about the same trade. This file paints what it is told.
   *
   * AND IT DOES NOT BLINK OVER A FROZEN NUMBER. When the market is shut the
   * band keeps its colour and stops breathing, and says "at the close",
   * because his profit and loss is not running at nine in the evening and a
   * blink that says it is would be a small lie.
   */
  bandTone(p) {
    const pnl = p && p.unrealized_pnl_inr;
    if (typeof pnl !== 'number' || !Number.isFinite(pnl)) return 'flat';
    return pnl < 0 ? 'down' : 'up';
  }

  /** The trades that get a band, the ones needing him first. */
  bandPositions() {
    if (!Array.isArray(this.livePositions)) return [];
    const open = this.livePositions.filter((p) => String(p.state || 'running') !== 'quiet');
    const rank = (p) => (p.state === 'alert' ? 0 : p.state === 'running' ? 1 : 2);
    return open.slice().sort((a, b) => rank(a) - rank(b));
  }

  /** The third figure on the band: what he asked this trade to tell him. */
  _bandThird(p) {
    const alerts = Array.isArray(p.alerts) ? p.alerts : [];
    // BUILD B. Something waiting for a price outranks a target that has not
    // been reached, because it is a live instruction of his that the market
    // has not met yet. A reached target still comes first: that one needs him.
    const resting = Number(p.resting_orders || 0);
    if (alerts.length) {
      const a = alerts[0];
      const what = a.kind === 'profit' ? 'profit' : 'loss';
      const who = a.scope === 'leg' ? a.leg_label : 'the whole trade';
      return {
        k: 'Reached',
        v: `${who} · ${what}`,
        tone: a.kind === 'profit' ? 'up' : 'down',
      };
    }
    if (resting > 0) {
      return {
        k: 'Open orders',
        v: `${resting} resting`,
        tone: 'amber',
      };
    }
    const t = p.targets || {};
    const withTargets = Number(t.legs_with_targets || 0);
    const total = Number(t.legs_total || 0);
    const profit = typeof t.target_profit_inr === 'number' ? t.target_profit_inr : null;
    const loss = typeof t.target_loss_inr === 'number' ? t.target_loss_inr : null;

    // WHAT HE SET, IN THE FIGURE HE TYPED. His question of 2026-09-11: "I just
    // added a maximum loss for the whole trade, so where is this visible?" It
    // said only "on the trade", which is not an answer. It shows the number.
    if (profit !== null || loss !== null) {
      const parts = [];
      if (profit !== null) parts.push(`+${inr(profit)}`);
      if (loss !== null) parts.push(`−${inr(loss)}`);
      return { k: withTargets > 0 ? 'Trade target' : 'Targets set', v: parts.join(' / '), tone: '' };
    }
    if (withTargets > 0) {
      return { k: 'Targets set', v: `${withTargets} of ${total} legs`, tone: '' };
    }
    // Nothing set is not a failure and does not get a warning colour. It is
    // simply the truth, and the button beside it is how he changes it.
    return { k: 'Targets set', v: 'none yet', tone: 'muted' };
  }

  /** One band. Everything on it was read off the server; none of it is computed here. */
  _band(p) {
    const state = String(p.state || 'running');
    const tone = this.bandTone(p);
    const shut = p.market_state !== 'live';
    const alerts = Array.isArray(p.alerts) ? p.alerts : [];

    // WHAT THE GROUND SAYS, corrected by him on 2026-09-11.
    //
    //   blinking green  a profit is running
    //   blinking red    a loss is running
    //   solid green     his profit target was reached
    //   solid red       his loss target was reached
    //   calm blue       the market is shut, so nothing is running at all
    //   muted           nothing open, or squared off
    //
    // A shut market gets its OWN colour rather than a frozen green or red,
    // because a green ground on a number that stopped moving hours ago reads
    // as "running" when nothing is. His words: "when the market is closed,
    // just give the blue colour or some other colour." The figures themselves
    // keep their own green and red, because the money did what it did.
    const cls = state === 'alert'
      ? `hb ${tone === 'down' ? 'solid-down' : 'solid-up'}`
      : state === 'quiet'
        ? 'hb quiet'
        : shut
          ? 'hb shut'
          : `hb tint-${tone} running`;

    const chip = state === 'alert'
      ? `<span class="hchip alert"><span class="hdot"></span> ${alerts[0] && alerts[0].kind === 'profit' ? 'profit target hit' : 'loss target hit'}</span>`
      : state === 'quiet'
        ? '<span class="hchip">squared off</span>'
        : shut
          ? '<span class="hchip">at the close</span>'
          : `<span class="hchip ${tone === 'down' ? 'c-down' : 'c-up'}"><span class="hdot pulse"></span> running</span>`;

    const third = this._bandThird(p);
    const legs = Number(p.legs_open || 0);
    const closed = Number(p.legs_closed || 0);
    const expiry = this._expiryLabel(p.expiry_date);
    const kind = typeof p.days_held === 'number' && p.days_held >= 1 ? 'swing' : 'intraday so far';
    const since = istTime(p.opened_at, false);
    const meta = [
      `${legs} leg${legs === 1 ? '' : 's'}${closed ? ` · ${closed} already out` : ''}`,
      expiry ? `expiry ${expiry}` : null,
      since ? `since ${since} IST` : null,
      kind,
      this._readStamp('livePositions'),
      p.error ? p.error : null,
    ].filter(Boolean).join(' · ');

    const money = (k, value, klass) => `<div><div class="k">${escapeHtml(k)}</div>
      <div class="v ${klass}">${value === null || value === undefined
        ? '<span class="na">unavailable</span>'
        : escapeHtml(value)}</div></div>`;

    const pnl = typeof p.unrealized_pnl_inr === 'number' ? p.unrealized_pnl_inr : null;
    const net = typeof p.net_if_exit_now_inr === 'number' ? p.net_if_exit_now_inr : null;

    // BUILD B, his instruction of 2026-09-10. A resting exit that the bell
    // killed leaves him holding a leg he meant to be out of. He must not find
    // that out by accident, so it sits ABOVE the band, in plain words, and
    // points at the 15:20 naked-shorts reading. A warning only: it never
    // trades and it never changes an order.
    const stranded = typeof p.orders_warning === 'string' && p.orders_warning
      ? `<div class="hb-warn" role="status">${escapeHtml(p.orders_warning)}</div>`
      : '';

    // THE NAME OWNS THE CORNER, and the state chip sits beside it the way the
    // CLOSED chip sits beside NIFTY 50. It used to have the whole first column
    // to itself, which took the title's place and left the trade's name pushed
    // along. His words: "the Iron Condor and the details should be there."
    //
    // That layout is pull request #67's and it stands. This build only adds
    // the line above the band, which is outside it and changes none of it.
    return `${stranded}<div class="${cls}" data-band="${escapeHtml(String(p.position_id))}">
      <div class="t"><span class="nm">${escapeHtml(p.strategy_name || 'Trade')}</span> ${chip}
        <small>${escapeHtml(meta)}</small></div>
      ${money('Open profit / loss', pnl === null ? null : signed(pnl, { whole: true }), pnl === null ? '' : pnl < 0 ? 'dn' : 'up')}
      ${money('Net if exited', net === null ? null : signed(net, { whole: true }), net === null ? '' : net < 0 ? 'dn' : 'up')}
      ${money(third.k, third.v, third.tone === 'up' ? 'up' : third.tone === 'down' ? 'dn' : third.tone)}
      <div><button class="hbtn${state === 'alert' ? ' pri' : ''}" type="button"
        data-manage="${escapeHtml(String(p.position_id))}"
        ${state === 'quiet' ? 'disabled' : ''}>Manage</button></div>
    </div>`;
  }

  /**
   * The line when nothing is running. It stays on the page, one row high, so
   * the space does not jump about between a day with a trade and a day without.
   */
  _quietLine() {
    const testing = !this.phase || this.phase.paper_trading_started !== true;
    const words = testing
      ? 'Test trading. Your record starts clean on the day you say.'
      : 'Nothing running. Your paper record is live.';
    return `<div class="hb quiet one">
      <span class="hchip flat">nothing running</span>
      <span class="qtext">${escapeHtml(words)}
        <i class="qstamp">${escapeHtml(this._readStamp('positions'))}</i></span>
    </div>`;
  }

  renderPositions() {
    const host = this.container.querySelector('#home-positions');
    if (!host) return;

    if (this.positionsError) {
      host.innerHTML = `<div class="hb quiet one">
        <span class="hchip flat">unavailable</span>
        <span class="qtext"><span class="na">Your open positions could not be read, so nothing is shown rather than something wrong.</span>
          ${escapeHtml(this.positionsError)}</span></div>`;
      return;
    }
    if (!Array.isArray(this.positions)) {
      host.innerHTML = `<div class="hb quiet one">
        <span class="hchip flat">reading</span>
        <span class="qtext">Reading your open positions…</span></div>`;
      return;
    }
    if (!this.positions.length) {
      host.innerHTML = this._quietLine();
      return;
    }
    if (this.livePositionsError || !Array.isArray(this.livePositions)) {
      const why = this.livePositionsError || 'not valued yet';
      const n = this.positions.length;
      host.innerHTML = `<div class="hb quiet one">
        <span class="hchip flat">${n} open</span>
        <span class="qtext"><span class="na">Profit and loss unavailable</span>, so the band shows no money rather than a wrong one.
          ${escapeHtml(why)} <i class="qstamp">${escapeHtml(this._readStamp('positions'))}</i></span></div>`;
      return;
    }

    const bands = this.bandPositions();
    host.innerHTML = bands.length
      ? bands.map((p) => this._band(p)).join('')
      : this._quietLine();

    host.querySelectorAll('[data-manage]').forEach((btn) => {
      btn.addEventListener('click', () => this.openManage(btn.getAttribute('data-manage')));
    });
  }

  /**
   * MANAGE. His words: "Give a Manage button, which will open the exit modal.
   * Over there, I can exit all directly, or I can exit one leg where the target
   * is achieved."
   *
   * It opens BUILD_01's exit ticket right here on Home, for that trade. It does
   * NOT navigate to the desk, and nothing else on Home manages a position.
   */
  openManage(positionId) {
    const p = (this.livePositions || []).find((x) => String(x.position_id) === String(positionId));
    if (!p) return;
    const host = this.container.querySelector('#home-exit-ticket');
    if (!host) return;
    if (!this.exitTicket) {
      this.exitTicket = new ExitTicket(host, {
        onExitAll: (payload) => api.closePosition(this.exitTicket.position.position_id, payload),
        onExitLeg: (seq, payload) => api.exitLeg(
          this.exitTicket.position.position_id,
          seq,
          payload,
          `home-exit-${this.exitTicket.position.position_id}-${seq}`,
        ),
        // Whatever filled, Home reads itself again rather than assuming.
        onDone: () => { this.loadPositions(); },
      });
    }
    this.exitTicket.open(p, null);
  }

  renderEvents() {
    const host = this.container.querySelector('#home-events');
    if (!host) return;
    let body;
    if (this.eventsError) {
      body = `<div class="empty">The events table could not be read.<br>
        <span style="color:var(--fg-3);font-size:12px">${escapeHtml(this.eventsError)}</span></div>`;
    } else if (!Array.isArray(this.events)) {
      body = '<div class="empty">Reading your macro events…</div>';
    } else if (!this.events.length) {
      body = '<div class="empty">No dated events ahead in your macro table.</div>';
    } else {
      const tagFor = (imp) => {
        const v = String(imp || '').toLowerCase();
        if (v === 'high') return '<span class="tag t-hi">High</span>';
        if (v === 'medium' || v === 'med') return '<span class="tag t-na">Med</span>';
        if (!v) return '<span class="tag t-na">unrated</span>';
        return `<span class="tag t-na">${escapeHtml(v)}</span>`;
      };
      // The impact brief is written by the macro curator and has been sitting
      // in the response unused. It appears on hover, on focus and on tap
      // rather than in the row, because the card is the right size already and
      // five paragraphs of brief would make it the biggest thing on the page.
      // Rows without a brief show nothing extra — no placeholder, no
      // "no brief available" on every line.
      body = `<table class="g evt"><tbody>
        ${this.events.slice(0, 8).map((e, i) => {
          const name = escapeHtml(e.event_name || e.event_key || 'event');
          const brief = typeof e.impact_brief === 'string' ? e.impact_brief.trim() : '';
          const date = escapeHtml(String(e.event_date || '').slice(0, 10)) || DASH;
          const cell = brief
            ? `<span class="evb" tabindex="0" role="button" aria-expanded="false"
                 aria-controls="home-evb-${i}" data-evb="${i}">${name}</span>
               <span class="evpop" id="home-evb-${i}" role="tooltip">${escapeHtml(brief)}</span>`
            : name;
          return `<tr><td class="evc">${cell}</td>
            <td class="n">${date}</td>
            <td class="n">${tagFor(e.importance)}</td></tr>`;
        }).join('')}
      </tbody></table>
      <div class="why">From your own macro events table. Nothing here is scraped live yet.
        An underlined event carries a written impact brief — hover it, or tap it, to read it.</div>`;
    }
    host.innerHTML = `<div class="card"><h3>Events ahead <span class="r">factor these into every trade · ${escapeHtml(this._readStamp('events'))}</span></h3>${body}</div>`;
    this.bindEventBriefs(host);
  }

  /**
   * Hover and focus are handled in CSS so the brief cannot be left on screen by
   * a lost mouseout. Touch has neither, so a tap toggles a class, a second tap
   * or a tap elsewhere clears it, and Escape closes it for the keyboard.
   */
  bindEventBriefs(host) {
    const anchors = host.querySelectorAll('.evb');
    if (!anchors.length) return;
    const closeAll = (except) => {
      anchors.forEach((a) => {
        if (a === except) return;
        a.classList.remove('on');
        a.setAttribute('aria-expanded', 'false');
      });
    };
    anchors.forEach((a) => {
      a.addEventListener('click', (ev) => {
        ev.preventDefault();
        const nowOn = !a.classList.contains('on');
        closeAll(a);
        a.classList.toggle('on', nowOn);
        a.setAttribute('aria-expanded', String(nowOn));
      });
      a.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') {
          a.classList.remove('on');
          a.setAttribute('aria-expanded', 'false');
          if (typeof a.blur === 'function') a.blur();
        } else if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          a.click();
        }
      });
    });
  }

  /**
   * "Your record", as labelled rows rather than a sentence.
   *
   * Two reasons the rows are drawn even with nothing in the book. The card
   * fills its height honestly, so there is no empty half-cell for the events
   * card beside it to stretch around — which is the dead space he reported.
   * And the layout does not jump the day his first trade closes, because the
   * rows are already where they will be.
   *
   * An unknown value is a dash. Never a zero: the journal endpoint returns
   * 0.0 for expectancy and 100.0 for discipline when it has nothing to
   * compute from, and printing those as figures would be an invented record.
   */
  recordRows() {
    const k = this.record;
    const n = k && typeof k.total_trades === 'number' ? k.total_trades : null;
    const has = typeof n === 'number' && n > 0;
    const val = (ok, formatted) => (ok ? `<b>${escapeHtml(formatted)}</b>` : DASH);
    const pnl = has && typeof k.cumulative_net_pnl_inr === 'number' ? k.cumulative_net_pnl_inr : null;
    // Expectancy per trade is the cumulative result divided by the trades that
    // produced it, computed here from this book's own figures.
    const expectancy = pnl !== null && n > 0 ? pnl / n : null;

    const rows = [
      ['Trades closed', n === null ? DASH : `<b>${escapeHtml(String(n))}</b>`],
      ['Win rate', val(has && typeof k.win_rate_pct === 'number', has && typeof k.win_rate_pct === 'number' ? `${k.win_rate_pct.toFixed(1)}%` : '')],
      ['Cumulative profit', pnl === null ? DASH : `<b class="${pnl < 0 ? 'dn' : 'up'}">${escapeHtml(inr(pnl))}</b>`],
      ['Expectancy per trade', expectancy === null ? DASH : `<b class="${expectancy < 0 ? 'dn' : 'up'}">${escapeHtml(inr(expectancy))}</b>`],
      ['Average reward to risk', val(has && typeof k.avg_rr_actual === 'number' && k.avg_rr_actual !== 0, has && typeof k.avg_rr_actual === 'number' ? `1 : ${k.avg_rr_actual.toFixed(2)}` : '')],
      ['Rules followed', val(has && typeof k.discipline_rate_pct === 'number', has && typeof k.discipline_rate_pct === 'number' ? `${k.discipline_rate_pct.toFixed(0)}%` : '')],
    ];
    return `<table class="g rec"><tbody>${rows.map(
      ([label, cell]) => `<tr><td>${escapeHtml(label)}</td><td class="n">${cell}</td></tr>`,
    ).join('')}</tbody></table>`;
  }

  renderRecord() {
    const host = this.container.querySelector('#home-record');
    if (!host) return;
    const paper = this.book === 'paper';
    // The date used to be written into this line: "starts clean from 8
    // September 2026". It was a fixed string, it contradicted his correction of
    // 2026-09-10, and it would have gone on being wrong after paper trading
    // actually began. It reads the phase now, like the band above it.
    const started = this.phase && this.phase.paper_trading_started
      ? this.phase.paper_trading_started_at
      : null;
    const note = paper
      ? (started
        ? `Your paper record starts from ${String(started).slice(0, 10)}. Test rows are excluded from every figure here.`
        : 'Test trading. Every trade below was a click to see how the terminal behaves, and your record starts clean on the day you say.')
      : 'No real-money trades. Real execution is code-blocked: there is no order-placement code in the app at all. This book stays empty until you decide otherwise.';

    const why = this.recordError
      ? `Your record could not be read, so every figure above is a dash rather than a guess. ${this.recordError}`
      : this.recordLoading || !this.readAt.record
        ? 'Reading your closed trades…'
        : this.record && this.record.total_trades > 0
          ? null
          : `No closed ${paper ? 'paper' : 'real-money'} trades yet, so there is nothing to compute these from.`;

    host.innerHTML = `
      <div class="card">
        <h3>Your record
          <div class="seg" role="group" aria-label="Which record">
            <button id="tab-paper" type="button" aria-pressed="${paper}">Paper</button>
            <button id="tab-real" type="button" aria-pressed="${!paper}">Real money</button>
          </div>
          <span class="r">${escapeHtml(this._readStamp('record'))}</span>
        </h3>
        ${this.recordRows()}
        ${why ? `<div class="why">${escapeHtml(why)}</div>` : ''}
        <div class="why">${escapeHtml(note)}</div>
      </div>`;

    const tabP = host.querySelector('#tab-paper');
    const tabR = host.querySelector('#tab-real');
    const pick = (book) => {
      if (this.book === book) return;
      this.book = book;
      this.record = null;
      this.recordError = null;
      // The other book has not been read yet, so the stamp and the empty-state
      // sentence must not carry over from the one he just left.
      this.readAt.record = null;
      this.renderRecord();
      this.loadRecord();
    };
    if (tabP) tabP.addEventListener('click', () => pick('paper'));
    if (tabR) tabR.addEventListener('click', () => pick('real'));
  }

  destroy() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
    if (this._unsubSpot) {
      this._unsubSpot();
      this._unsubSpot = null;
    }
    if (this.dataHealth) {
      this.dataHealth.destroy();
      this.dataHealth = null;
    }
    this.ticker = null;
    this.ritual = null;
  }
}

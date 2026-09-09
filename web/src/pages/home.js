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
    await Promise.all([this.loadSnapshot(), this.loadDaily()]);
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
          <div id="home-positions"></div>
          <div id="home-ticker"></div>
          <div id="home-ritual"></div>
          <div id="home-pwa-prompt-container"></div>

          <div class="cols">
            <div class="side home-left-col" id="home-nifty-sidebar"></div>

            <main class="home-right-col">
              <h1 class="sr-only">Market Prep</h1>
              <div class="bento-grid">
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
        ${this._kv('Max pain', num(f.max_pain, 0))}
        ${this._kv('Days to weekly expiry', this._dte(f.weekly_dte))}
        ${this._kv('Days to monthly expiry', this._dte(f.monthly_dte))}
      </div>`;
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
          ${this._money('Margin used', inr(used), this.marginUsedNote(), 'var(--fg-2)')}
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
  marginUsed() {
    if (!Array.isArray(this.positions)) return null;
    if (!this.positions.length) return 0;
    let total = 0;
    let sawOne = false;
    for (const p of this.positions) {
      if (typeof p.margin_used_inr === 'number') { total += p.margin_used_inr; sawOne = true; }
      else if (typeof p.margin_blocked_inr === 'number') { total += p.margin_blocked_inr; sawOne = true; }
    }
    return sawOne ? total : null;
  }

  marginUsedNote() {
    if (!Array.isArray(this.positions)) return 'positions not read yet';
    if (!this.positions.length) return 'nothing open';
    if (this.marginUsed() === null) return 'no margin figure is stored on a position';
    return 'across open positions';
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

  /** grey with nothing open, sage in profit, coral in loss. Colour follows the money. */
  positionsTone() {
    if (!Array.isArray(this.positions) || !this.positions.length) return 'flat';
    const pnl = this.combinedPnl();
    if (typeof pnl !== 'number') return 'flat';
    return pnl < 0 ? 'loss' : 'profit';
  }

  /**
   * The one line he sees when the strip is shut. With something open it has to
   * be worth reading on its own: how many, what they are worth now, and how
   * much of his running-loss limit that has used.
   */
  positionsSummary() {
    if (this.positionsError) {
      return `<span class="na">Open positions could not be read</span>
        <span class="pdim">${escapeHtml(this.positionsError)}</span>`;
    }
    if (!Array.isArray(this.positions)) {
      return '<span class="pdim">Reading your open positions…</span>';
    }
    if (!this.positions.length) {
      return `<span>Nothing open.</span>
        <span class="pdim">Your paper record starts clean from 8 September.</span>`;
    }

    const n = this.positions.length;
    const parts = [`<span class="pn">${n} open</span>`];
    const pnl = this.combinedPnl();
    if (typeof pnl === 'number') {
      parts.push(`<span class="pv ${pnl < 0 ? 'dn' : 'up'}">${escapeHtml(inr(pnl))}</span>`);
    } else {
      const why = this.livePositionsError
        ? this.livePositionsError
        : this.livePositions === null
          ? 'not valued yet'
          : 'a position could not be valued against the chain';
      parts.push(`<span class="na">profit and loss unavailable</span>`);
      parts.push(`<span class="pdim">${escapeHtml(why)}</span>`);
    }
    const usedPct = this.runningLossUsedPct();
    if (usedPct !== null) {
      parts.push(`<span class="pdim">running loss ${usedPct.toFixed(0)}% used</span>`);
    }
    return parts.join('<span class="psep">·</span>');
  }

  /** Every open position in full, drawn only when he opens the strip. */
  positionsDetail() {
    if (!Array.isArray(this.positions) || !this.positions.length) {
      return `<div class="empty">Nothing open. When you take a position it appears here,
        on the desk against your margin, and in the journal once it is closed.</div>`;
    }
    const liveById = new Map();
    if (Array.isArray(this.livePositions)) {
      for (const l of this.livePositions) liveById.set(String(l.position_id), l);
    }
    const rows = this.positions.map((p) => {
      const l = liveById.get(String(p.id)) || null;
      const pnl = l && typeof l.unrealized_pnl_inr === 'number' ? l.unrealized_pnl_inr : null;
      const pct = l && typeof l.unrealized_pnl_pct_of_risk === 'number' ? l.unrealized_pnl_pct_of_risk : null;
      const legs = Array.isArray(p.legs) ? p.legs.length : null;
      const opened = String(p.opened_at || p.entry_date || '').slice(0, 10);
      return `<tr>
        <td>${escapeHtml(p.strategy_name || p.underlying || 'position')}
          ${legs === null ? '' : `<i class="pdim">${legs} leg${legs === 1 ? '' : 's'}</i>`}</td>
        <td class="n">${opened ? escapeHtml(opened) : DASH}</td>
        <td class="n">${l && typeof l.days_remaining_to_expiry === 'number' ? escapeHtml(`${l.days_remaining_to_expiry}d`) : DASH}</td>
        <td class="n">${typeof p.max_loss_inr === 'number' ? escapeHtml(inr(p.max_loss_inr)) : DASH}</td>
        <td class="n">${pnl === null
          ? '<span class="na">unavailable</span>'
          : `<b class="${pnl < 0 ? 'dn' : 'up'}">${escapeHtml(inr(pnl))}</b>`}</td>
        <td class="n">${pct === null ? DASH : escapeHtml(`${pct.toFixed(1)}%`)}</td>
        <td class="n"><button type="button" class="posexit" data-exit="${escapeHtml(String(p.id))}"
          title="Square off every leg at the traded price">Exit</button></td>
      </tr>`;
    }).join('');

    const notice = this.positionsNotice
      ? `<div class="why"><b>${escapeHtml(this.positionsNotice)}</b></div>`
      : '';

    const note = this.livePositionsError
      ? `<div class="why">Profit and loss could not be valued against the live chain. ${escapeHtml(this.livePositionsError)}</div>`
      : `<div class="why">Profit and loss is valued leg by leg against the FYERS chain, read ${escapeHtml(this._readStamp('livePositions'))}. The last column is that figure against the position's own maximum loss.</div>`;

    return `<div class="tw"><table class="g"><thead><tr>
        <th>Strategy</th><th style="text-align:right">Opened</th><th style="text-align:right">To expiry</th>
        <th style="text-align:right">Max loss</th><th style="text-align:right">Unrealised</th>
        <th style="text-align:right">Of risk</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table></div>${notice}${note}`;
  }

  renderPositions() {
    const host = this.container.querySelector('#home-positions');
    if (!host) return;
    const tone = this.positionsTone();
    const open = this.positionsExpanded;

    host.innerHTML = `
      <div class="card posstrip t-${tone}">
        <button class="posline" id="home-positions-toggle" type="button"
          aria-expanded="${open}" aria-controls="home-positions-body">
          <span class="pcar" aria-hidden="true">${open ? '▾' : '▸'}</span>
          <span class="plbl">Open positions</span>
          <span class="psum">${this.positionsSummary()}</span>
          <span class="r">paper · ${escapeHtml(this._readStamp('positions'))}</span>
        </button>
        <div class="posdet" id="home-positions-body"${open ? '' : ' hidden'}>${open ? this.positionsDetail() : ''}</div>
      </div>`;

    const btn = host.querySelector('#home-positions-toggle');
    if (btn) btn.addEventListener('click', () => this.togglePositions());
    this.bindExitButtons(host);
  }

  /**
   * Squaring off from the page he actually looks at.
   *
   * There was NO way to close a position anywhere in the app until 2026-09-09.
   * `ActiveTradesComponent` carries an exit flow and is imported by main.js,
   * but it is never instantiated and no page has a mount point for it. He
   * opened his first ever position and had to close it from a terminal.
   *
   * It asks first, because closing is not undoable, and it says what happened
   * in money rather than just succeeding quietly.
   */
  bindExitButtons(host) {
    host.querySelectorAll('.posexit').forEach((btn) => {
      btn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const id = btn.getAttribute('data-exit');
        if (!id) return;

        const row = this.positions.find((p) => String(p.id) === id) || {};
        const name = row.strategy_name || 'this position';
        if (!window.confirm(`Square off ${name}? Every leg is closed at the traded price. This cannot be undone.`)) return;

        btn.disabled = true;
        const original = btn.textContent;
        btn.textContent = 'Closing…';
        try {
          const res = await api.closePosition(id, {
            close_reason: 'manual',
            notes: 'Squared off from Home.',
          });
          const net = typeof res.realized_pnl_inr === 'number' ? inr(res.realized_pnl_inr) : DASH;
          const charges = typeof res.total_charges_inr === 'number' ? inr(res.total_charges_inr) : DASH;
          this.positionsNotice = `Closed. Net ${net} after ${charges} of charges.`;
          await this.loadPositions();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = original;
          this.positionsNotice = `Not closed: ${(err && err.message) || err}`;
          this.renderPositions();
        }
      });
    });
  }

  togglePositions() {
    this.positionsExpanded = !this.positionsExpanded;
    writePositionsExpanded(this.positionsExpanded);
    this.renderPositions();
    const btn = this.container.querySelector('#home-positions-toggle');
    if (btn && typeof btn.focus === 'function') btn.focus();
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
    const note = paper
      ? 'Your paper record starts clean from 8 September 2026. 81 build-and-test rows are quarantined and excluded from every figure here.'
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

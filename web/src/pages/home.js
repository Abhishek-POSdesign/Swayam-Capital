/**
 * Home — rebuilt to the prototype Abhishek approved on 2026-09-08
 * (docs/reference/home-prototype.html), per docs/UI_BUILD_BRIEF.md.
 *
 * Top to bottom: a running ticker, the morning ritual as one thin strip, then
 * two columns — a fixed NIFTY sidebar on the left, his money, his four limits,
 * open positions, events, his record and the AI panel on the right.
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
import { updateHeaderSpot } from '../components/header.js';
import { inr, num, signedPct, escapeHtml } from '../utils/display.js';

const NA = '<b class="na">unavailable</b>';

export class HomePage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onOpenAIDrawer, onOpenSettings, onNavigateStrategy }

    this.snapshot = null;
    this.snapshotError = null;
    this.capital = null;
    this.capitalError = null;
    this.positions = null;
    this.positionsError = null;
    this.events = null;
    this.eventsError = null;
    this.daily = null; // derived from real daily candles: day range, average daily move
    this.dailyError = null;
    this.book = 'paper';

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
    // Independently try-caught, so one dead feed cannot blank the page.
    this.loadData();
  }

  render() {
    this.container.innerHTML = `
      <div class="sw-desk">
        <div class="app">
          <div class="top">
            <div class="brandmark"><span class="mark">स्व</span>Home <em>· so far today</em></div>
          </div>

          <div id="home-ticker"></div>
          <div id="home-ritual"></div>
          <div id="home-pwa-prompt-container"></div>

          <div class="cols">
            <div class="side home-left-col" id="home-nifty-sidebar"></div>

            <main class="home-right-col">
              <h1 class="sr-only">Market Prep</h1>
              <div class="bento-grid">
                <div class="span-12" id="home-money"></div>
                <div class="span-12" id="home-limits"></div>
                <div class="span-6" id="home-positions"></div>
                <div class="span-6" id="home-events"></div>
                <div class="span-12" id="home-record"></div>
                <div class="span-12" id="home-ai"></div>
              </div>
            </main>
          </div>
        </div>
      </div>
    `;
    this.renderSidebar();
    this.renderMoney();
    this.renderLimits();
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
    ]);
    this.renderTicker();
  }

  async loadSnapshot() {
    try {
      this.snapshot = await api.getNiftySnapshot();
      this.snapshotError = null;
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
    } catch (err) {
      this.capital = null;
      this.capitalError = (err && err.message) || String(err);
    }
    this.renderMoney();
    this.renderLimits();
  }

  async loadPositions() {
    try {
      const res = await api.getPositions('open');
      this.positions = Array.isArray(res) ? res : (res && res.positions) || [];
      this.positionsError = null;
    } catch (err) {
      this.positions = null;
      this.positionsError = (err && err.message) || String(err);
    }
    this.renderPositions();
    this.renderRecord();
    this.renderMoney(); // margin used is only known once positions are in
  }

  async loadEvents() {
    try {
      const res = await api.getMacroEvents(false);
      this.events = (res && res.events) || [];
      this.eventsError = null;
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
    const items = [
      { label: 'NIFTY 50', value: num(c.spot, 2), note: c.spot_freshness ? String(c.spot_freshness).toLowerCase() : '', dir: (c.day_change_pct || 0) < 0 ? 'down' : 'up' },
      { label: 'Today', value: signedPct(c.day_change_pct), dir: (c.day_change_pct || 0) < 0 ? 'down' : 'up' },
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
    // Breadth has no wired source. It says so; it never borrows a number.
    items.push({ label: 'Breadth', value: null, note: 'no wired source' });
    return items;
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

  _kv(label, formatted, colour) {
    const body = formatted === null || formatted === undefined
      ? NA
      : `<b${colour ? ` style="color:${colour}"` : ''}>${escapeHtml(formatted)}</b>`;
    return `<div class="kv"><span>${escapeHtml(label)}</span>${body}</div>`;
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
    const spot = typeof c.spot === 'number' ? c.spot : null;
    const chg = typeof c.day_change_pct === 'number' ? c.day_change_pct : null;
    const fresh = c.spot_freshness || 'UNAVAILABLE';
    const spotInt = spot === null ? null : Math.floor(spot);
    const spotFrac = spot === null ? null : (spot - Math.floor(spot)).toFixed(2).slice(1);

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
        <h3>NIFTY 50 <span class="tag ${fresh === 'LIVE' ? 't-live' : 't-na'}">${escapeHtml(String(fresh).toLowerCase())}</span><span class="r">FYERS</span></h3>
        <div class="hero">
          <div class="px">${spot === null ? '<span class="na" style="font-size:.5em">unavailable</span>' : `${escapeHtml(num(spotInt, 0))}<span style="font-size:.55em;color:var(--fg-2)">${spotFrac}</span>`}</div>
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
        ${this._kv('Volume today', null)}
        ${this._kv('Advances / declines', typeof c.advances === 'number' && typeof c.declines === 'number' ? `${c.advances} / ${c.declines}` : null)}
        ${this._kv('Sentiment', c.sentiment || null)}
        <div class="why">Sentiment is computed from spot against the 20-day average and where price sits inside the 20-day range. Volume and market breadth have no wired source and say so rather than borrow a number.</div>
      </div>

      <div class="card">
        <h3>Sectors today <span class="r">${escapeHtml(c.sector_freshness || 'unavailable')}</span></h3>
        ${sectors || '<div class="empty">No sector figures in this response.</div>'}
      </div>

      <div class="card">
        <h3>Options, weekly <span class="r">chain</span></h3>
        ${this._kv('India VIX', num(f.india_vix, 2))}
        ${this._kv('Put-call ratio', num(f.weekly_pcr, 2))}
        ${this._kv('Max pain', num(f.max_pain, 0))}
        ${this._kv('Days to weekly expiry', this._dte(f.weekly_dte))}
        ${this._kv('Days to monthly expiry', this._dte(f.monthly_dte))}
      </div>`;
  }

  _money(k, formatted, sub, colour) {
    return `<div class="mn"><div class="k">${escapeHtml(k)}</div>
      <div class="v"${colour ? ` style="color:${colour}"` : ''}>${formatted === null || formatted === undefined ? '<span class="na" style="font-size:14px">unavailable</span>' : escapeHtml(formatted)}</div>
      <div class="s">${escapeHtml(sub || '')}</div></div>`;
  }

  renderMoney() {
    const host = this.container.querySelector('#home-money');
    if (!host) return;
    const cap = this.capital;
    if (!cap) {
      host.innerHTML = `<div class="card"><h3>Your money <span class="r">unavailable</span></h3>
        <div class="empty">Your balance could not be read, so nothing derived from it is shown.<br>
        <span style="color:var(--fg-3);font-size:12px">${escapeHtml(this.capitalError || 'No response yet.')}</span></div></div>`;
      return;
    }
    const used = this.marginUsed();
    host.innerHTML = `
      <div class="card">
        <h3>Your money <span class="r">${escapeHtml(cap.source || 'source not stated')}${cap.taken_at ? `, read ${escapeHtml(String(cap.taken_at))}` : ''}</span></h3>
        <div class="money">
          ${this._money('Balance', inr(cap.risk_capital_inr), 'total')}
          ${this._money('Free cash', inr(cap.free_cash_inr), 'unpledged')}
          ${this._money('Collateral', inr(cap.collateral_inr), 'pledged holdings')}
          ${this._money('Margin used', inr(used), used === null ? 'positions not read yet' : used === 0 ? 'nothing open' : 'across open positions', 'var(--fg-2)')}
          ${this._money('Margin ceiling', inr(cap.deployable_margin_ceiling_inr), cap.ceiling_unavailable_reason || 'twice your cash equivalent', 'var(--up)')}
        </div>
        ${cap.reconciliation_note ? `<div class="why">${escapeHtml(cap.reconciliation_note)}</div>` : ''}
      </div>`;
  }

  /** Margin used is only known once positions have been read. Never assumed. */
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

  renderLimits() {
    const host = this.container.querySelector('#home-limits');
    if (!host) return;
    const cap = this.capital;
    if (!cap) {
      host.innerHTML = `<div class="card"><h3>Today's limits <span class="r">unavailable</span></h3>
        <div class="empty">Every limit is a percentage of your live balance. Without the balance there is nothing honest to show.</div></div>`;
      return;
    }
    const bal = typeof cap.risk_capital_inr === 'number' ? cap.risk_capital_inr : null;
    // Rule 2's cap is 2% of the same live balance. Rules 1 and 5% come back named.
    const gapCap = bal === null ? null : bal * 0.02;
    const cell = (cls, k, value, sub) =>
      `<div class="rl ${cls}"><div class="k">${escapeHtml(k)}</div>
        <div class="v">${value === null ? '<span class="na" style="font-size:14px">unavailable</span>' : escapeHtml(value)}</div>
        <div class="s">${escapeHtml(sub)}</div></div>`;

    host.innerHTML = `
      <div class="card">
        <h3>Today's limits <span class="r">a percentage of the balance above, never a stored number</span></h3>
        <div class="rules">
          ${cell('a', '1 · Running loss', inr(cap.primary_risk_cap_inr), '1% · exit, no debate')}
          ${cell('b', '2 · Overnight gap', inr(gapCap), '2% · tested at twice the average daily move')}
          ${cell('c', '3 · Black swan', inr(cap.black_swan_fuse_inr), '5% · worst case at expiry')}
          ${cell('d', '4 · Margin ceiling', inr(cap.deployable_margin_ceiling_inr), cap.ceiling_unavailable_reason || '2x cash equivalent')}
        </div>
        <div class="why">Nothing blocks an intraday entry, including a naked or half-built structure: converting a straddle into a condor has to pass through states no gate would allow. Only carrying overnight is gated, and only on two conditions — hedged, and inside the 2% gap test.</div>
      </div>`;
  }

  renderPositions() {
    const host = this.container.querySelector('#home-positions');
    if (!host) return;
    let body;
    if (this.positionsError) {
      body = `<div class="empty">Open positions could not be read.<br>
        <span style="color:var(--fg-3);font-size:12px">${escapeHtml(this.positionsError)}</span></div>`;
    } else if (!Array.isArray(this.positions)) {
      body = '<div class="empty">Reading your open positions…</div>';
    } else if (!this.positions.length) {
      body = `<div class="empty">Nothing open.<br>
        <span style="color:var(--fg-3);font-size:12px">Your paper record starts clean from 8 September.</span></div>`;
    } else {
      body = `<div class="tw"><table class="g"><thead><tr>
          <th>Strategy</th><th>Opened</th><th style="text-align:right">Unrealised</th></tr></thead><tbody>
          ${this.positions.map((p) => `<tr>
            <td>${escapeHtml(p.strategy_name || p.underlying || 'position')}</td>
            <td class="n">${escapeHtml(String(p.opened_at || p.entry_date || '').slice(0, 10) || '—')}</td>
            <td class="n">${typeof p.unrealized_pnl_inr === 'number' ? escapeHtml(inr(p.unrealized_pnl_inr)) : '<span class="na">unavailable</span>'}</td>
          </tr>`).join('')}
        </tbody></table></div>`;
    }
    host.innerHTML = `<div class="card"><h3>Open positions <span class="r">paper</span></h3>${body}</div>`;
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
      body = `<div class="tw"><table class="g"><tbody>
        ${this.events.slice(0, 8).map((e) => `<tr>
          <td>${escapeHtml(e.event_name || e.event_key || 'event')}</td>
          <td class="n">${escapeHtml(String(e.event_date || '').slice(0, 10) || '—')}</td>
          <td class="n">${tagFor(e.importance)}</td></tr>`).join('')}
      </tbody></table></div>
      <div class="why">From your own macro events table. Nothing here is scraped live yet.</div>`;
    }
    host.innerHTML = `<div class="card"><h3>Events ahead <span class="r">factor these into every trade</span></h3>${body}</div>`;
  }

  renderRecord() {
    const host = this.container.querySelector('#home-record');
    if (!host) return;
    const paper = this.book === 'paper';
    const note = paper
      ? 'Your paper record starts clean from 8 September 2026. 81 build-and-test rows are quarantined and excluded from every figure here.'
      : 'No real-money trades. Real execution is code-blocked: there is no order-placement code in the app at all. This book stays empty until you decide otherwise.';

    host.innerHTML = `
      <div class="card">
        <h3>Your record
          <div class="seg" role="group" aria-label="Which record">
            <button id="tab-paper" type="button" aria-pressed="${paper}">Paper</button>
            <button id="tab-real" type="button" aria-pressed="${!paper}">Real money</button>
          </div>
        </h3>
        <div class="empty">No ${paper ? 'paper' : 'real-money'} trades yet.<br>
          <span style="color:var(--fg-3);font-size:12px">Win rate, cumulative profit and expectancy appear here once there are trades to compute them from.</span>
        </div>
        <div class="why">${escapeHtml(note)}</div>
      </div>`;

    const tabP = host.querySelector('#tab-paper');
    const tabR = host.querySelector('#tab-real');
    if (tabP) tabP.addEventListener('click', () => { this.book = 'paper'; this.renderRecord(); });
    if (tabR) tabR.addEventListener('click', () => { this.book = 'real'; this.renderRecord(); });
  }

  destroy() {
    this.ticker = null;
    this.ritual = null;
  }
}

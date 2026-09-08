/**
 * Strategy Desk — rebuilt to the prototype Abhishek approved on 2026-09-08
 * (docs/reference/strategy-desk-prototype.html), per docs/UI_BUILD_BRIEF.md.
 *
 * Left column, in his order: legs first with one expiry and one lot multiplier
 * above them, then the ready-made grid, then the strikewise volatility.
 * Right column: the metric row, the payoff graph, the greeks, and his four
 * rules with the execute button last, in one block.
 *
 * Three things this file will not do:
 *   1. Invent a number. No fallback contract size, no seeded premium, no
 *      modelled margin. The contract size comes from the server, prices come
 *      from the option chain or from him, margin comes from the broker. What is
 *      missing says "unavailable" and names the reason.
 *   2. Block an entry. Nothing here gates a trade, including a naked or
 *      half-built structure. Only carrying overnight is gated.
 *   3. Multiply pct_of_margin by 100. The server sends 1.74 meaning 1.74%.
 */

import { api } from '../api.js';
import { MarketTickerComponent } from '../components/market-ticker.js';
import { PayoffSvgComponent } from '../components/payoff-svg.js';
import { OvernightBlockModalComponent } from '../components/overnight-block-modal.js';
import { OptionChainModalComponent } from '../components/option-chain-modal.js';
import {
  maxLossProfit,
  breakevens,
  entryCost,
  pnlAt,
  netGreeks,
  unlimitedFlags,
} from '../modules/options-math.js';
import { spotFeed } from '../modules/ws-client.js';
import { inr, num, signedPct, escapeHtml, istTime, flashFor } from '../utils/display.js';

const STRIKE_STEP = 50;

/** How often every leg is re-quoted from the chain while the desk is open. */
const REQUOTE_MS = 5000;

/** A price he typed himself carries this source and is never overwritten. */
const OWN_PRICE = 'your own limit price';

/** 1 to 20 lots as a dropdown: he asked for this rather than plus and minus buttons so no width goes on stepper chrome. */
function lotOptions(current) {
  const values = Array.from({ length: 20 }, (_, i) => i + 1);
  if (current > 20 && !values.includes(current)) values.push(current);
  return values.map((n) => `<option value="${n}"${n === current ? ' selected' : ''}>${n}</option>`).join('');
}

/** Removes the reward-to-risk minimum from an advisory line; that rule was deleted. */
function stripDeletedRules(warning) {
  const text = String(warning || '');
  const marker = 'Worth knowing before you enter, though nothing here stops you: ';
  if (!text.startsWith(marker)) return text;
  const kept = text.slice(marker.length).split(', ').filter((r) => !/reward-to-risk/i.test(r));
  return kept.length ? marker + kept.join(', ') : '';
}

/**
 * Every structure that works on a single expiry, as offsets from the
 * at-the-money strike: [side, offset in points, type, lots]. Nothing here is a
 * price. Calendars and diagonals are deliberately absent: the desk has one
 * expiry for all legs and a two-expiry payoff needs real multi-expiry
 * valuation, which is the next job.
 */
const PRESETS = {
  'Bull Call Spread': [['B', 0, 'CE'], ['S', 200, 'CE']],
  'Bear Call Spread': [['S', 0, 'CE'], ['B', 200, 'CE']],
  'Bull Put Spread': [['S', 0, 'PE'], ['B', -200, 'PE']],
  'Bear Put Spread': [['B', 0, 'PE'], ['S', -200, 'PE']],
  'Long Straddle': [['B', 0, 'CE'], ['B', 0, 'PE']],
  'Short Straddle': [['S', 0, 'CE'], ['S', 0, 'PE']],
  'Long Strangle': [['B', 200, 'CE'], ['B', -200, 'PE']],
  'Short Strangle': [['S', 200, 'CE'], ['S', -200, 'PE']],
  'Iron Condor': [['S', 200, 'CE'], ['S', -200, 'PE'], ['B', 500, 'CE'], ['B', -500, 'PE']],
  'Iron Butterfly': [['S', 0, 'CE'], ['S', 0, 'PE'], ['B', 300, 'CE'], ['B', -300, 'PE']],
  'Call Butterfly': [['B', -200, 'CE'], ['S', 0, 'CE', 2], ['B', 200, 'CE']],
  'Put Butterfly': [['B', 200, 'PE'], ['S', 0, 'PE', 2], ['B', -200, 'PE']],
  'Call Ratio Back Spread': [['S', 0, 'CE'], ['B', 200, 'CE', 2]],
  'Put Ratio Back Spread': [['S', 0, 'PE'], ['B', -200, 'PE', 2]],
  'Jade Lizard': [['S', -200, 'PE'], ['S', 200, 'CE'], ['B', 400, 'CE']],
  'Broken-Wing Condor Bullish': [['S', -200, 'PE'], ['B', -600, 'PE'], ['S', 200, 'CE'], ['B', 400, 'CE']],
  'Broken-Wing Condor Bearish': [['S', 200, 'CE'], ['B', 600, 'CE'], ['S', -200, 'PE'], ['B', -400, 'PE']],
  'Naked Short Call': [['S', 100, 'CE']],
};

/** Payoff sparklines, 64 by 32, the zero line at y=17. */
const SPARKS = {
  'Bull Call Spread': 'M4,26 L20,26 L44,8 L60,8',
  'Bear Call Spread': 'M4,8 L20,8 L44,26 L60,26',
  'Bull Put Spread': 'M4,26 L20,26 L44,8 L60,8',
  'Bear Put Spread': 'M4,8 L20,8 L44,26 L60,26',
  'Long Straddle': 'M4,4 L32,28 L60,4',
  'Short Straddle': 'M4,28 L32,4 L60,28',
  'Long Strangle': 'M4,4 L22,26 L42,26 L60,4',
  'Short Strangle': 'M4,28 L22,6 L42,6 L60,28',
  'Iron Condor': 'M4,24 L16,24 L26,8 L38,8 L48,24 L60,24',
  'Iron Butterfly': 'M4,24 L18,24 L32,6 L46,24 L60,24',
  'Call Butterfly': 'M4,22 L22,22 L32,5 L42,22 L60,22',
  'Put Butterfly': 'M4,22 L22,22 L32,5 L42,22 L60,22',
  'Call Ratio Back Spread': 'M4,14 L28,14 L38,26 L60,4',
  'Put Ratio Back Spread': 'M4,4 L26,26 L36,14 L60,14',
  'Jade Lizard': 'M4,28 L24,8 L40,8 L50,20 L60,20',
  'Broken-Wing Condor Bullish': 'M4,30 L18,8 L40,8 L48,18 L60,18',
  'Broken-Wing Condor Bearish': 'M4,18 L16,18 L24,8 L46,8 L60,30',
  'Naked Short Call': 'M4,8 L30,8 L60,28',
};

/** The server names its presets differently; only these four exist server-side. */
const SERVER_PRESET_ID = {
  'Bull Call Spread': 'bull_call_spread',
  'Bear Put Spread': 'bear_put_spread',
  'Iron Condor': 'iron_condor',
};

export class StrategyBuilderPage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onNavigateHome, onOpenSettings }

    this.legs = [];
    this.baseLots = [];
    this.strategyName = null;

    this.spot = null;
    this.spotFreshness = null;
    this.spotError = null;

    /** Contract size. Server-resolved only; 65 is never assumed and 75 never sent. */
    this.lotSize = null;
    this.lotSizeSource = null;

    this.expiries = [];
    this.expiry = null;
    this.expiryError = null;
    /** From the server, computed against the NSE holiday file. Never guessed here. */
    this.today = null;
    this.nextTradingDay = null;

    /**
     * He arrives at 2:30 pm for swing and positional trades, so the desk
     * assumes the position is carried overnight and rule 2 is tested against
     * the next trading day. "Closing today" sends no planned exit date.
     */
    this.carry = 'overnight'; // 'overnight' | 'today'

    this.ivPctByStrike = {}; // strike -> implied volatility in percent
    this.ivSource = {}; // strike -> where that volatility came from

    this.dteDays = 0;
    this.dteMax = 0;
    this.targetSpot = null;

    this.capital = null;
    this.capitalError = null;
    this.positions = null;
    this.marginUsed = null;

    this.preview = null;
    this.previewError = null;
    this.validation = null;
    this.validationError = null;
    this.executeNote = null;

    this.sessionId = this._resolveSessionId();
    this._serverTimer = null;
    this._requoteTimer = null;
    this._requoting = false;
    this._unsubSpot = null;
    this.requoteMs = REQUOTE_MS;
    this._flash = {};
    this.spotAt = null;
    this.pricesReadAt = null;
    this.rulesCheckedAt = null;

    this.payoffChart = null;
    this.ticker = null;
    this.overnightModal = null;
    this.chainModal = null;
    this.cronTimer = null;
    this.safetyWarning = null;
  }

  _resolveSessionId() {
    try {
      const params = new URLSearchParams(window.location.search);
      const fromUrl = params.get('session');
      if (fromUrl) {
        localStorage.setItem('swayam_active_session_id', fromUrl);
        return fromUrl;
      }
      return localStorage.getItem('swayam_active_session_id');
    } catch (_) {
      return null;
    }
  }

  async init() {
    this.renderLayout();
    this.initSubComponents();
    this.startOvernightWatch();
    await this.loadInitialData();
    this.startLiveUpdates();
  }

  /**
   * Until round 2 the spot and every leg price were fetched once. Now the spot
   * follows the tick stream and every active leg is re-quoted from the chain
   * every 5 seconds, except a price he typed himself, which is his. Both are
   * torn down in destroy().
   */
  startLiveUpdates() {
    if (!this._unsubSpot) {
      this._unsubSpot = spotFeed.subscribe((spot, meta) => this.onSpotTick(spot, meta));
    }
    if (typeof setInterval === 'function' && !this._requoteTimer) {
      this._requoteTimer = setInterval(() => this.requoteLegs(), this.requoteMs);
      if (this._requoteTimer && typeof this._requoteTimer.unref === 'function') this._requoteTimer.unref();
    }
  }

  onSpotTick(spot, meta) {
    if (typeof spot !== 'number' || !Number.isFinite(spot)) return;
    this.spot = spot;
    this.spotFreshness = 'live';
    this.spotError = null;
    this.spotAt = (meta && meta.asOf) || new Date().toISOString();
    if (this.targetSpot === null) this.targetSpot = Math.round(spot / 5) * 5;
    this.renderSpot();
    this.renderMetrics();
    this.renderChart();
    this.renderGreeks();
    if (this.ticker) this.ticker.render(this.tickerItems());
  }

  /** True while he is typing into a leg row, so a re-quote must not redraw it under him. */
  _legInputFocused() {
    try {
      const el = typeof document !== 'undefined' ? document.activeElement : null;
      return Boolean(el && el.dataset && el.dataset.i !== undefined && el.dataset.f);
    } catch (_) {
      return false;
    }
  }

  /** Re-quotes every active leg that is not carrying a price he typed. */
  async requoteLegs() {
    if (this._requoting || !this.expiry) return;
    const indexes = this.legs
      .map((l, i) => (l.on && l.priceSource !== OWN_PRICE ? i : -1))
      .filter((i) => i >= 0);
    if (!indexes.length) return;

    this._requoting = true;
    let changed = false;
    try {
      await Promise.all(indexes.map(async (i) => {
        const before = this.legs[i] ? this.legs[i].price : null;
        await this.repriceLeg(i, { render: false, keepStale: true });
        if (this.legs[i] && this.legs[i].price !== before) changed = true;
      }));
    } finally {
      this._requoting = false;
    }
    this.pricesReadAt = new Date().toISOString();

    if (changed) {
      if (!this._legInputFocused()) this.renderLegs();
      this.renderIvs();
      this.renderRight();
      this.scheduleServerRefresh();
    } else if (!this._legInputFocused()) {
      this.renderLegs(); // only the "prices read" stamp moves
    }
    return changed;
  }

  // ------------------------------------------------------------------ layout

  renderLayout() {
    this.container.innerHTML = `
      <div class="sw-desk">
        <div class="app" id="strategy-builder-layout">
          <div class="top">
            <h2 class="pagename">Strategy Desk</h2>
            <div class="spot" id="desk-spot"></div>
            <button class="btn" id="btn-back-to-home" type="button" style="margin-left:10px">← Home</button>
          </div>

          <div id="strategy-sticky-ticker"></div>

          <div class="cols cols-desk">
            <div id="strategy-left-rail">
              <div class="card">
                <h3>Legs <span class="r" id="leg-count"></span></h3>
                <div class="toolbar">
                  <label class="tf"><span>Expiry, all legs</span>
                    <select id="global-expiry"></select></label>
                  <label class="tf"><span>Lot multiplier</span>
                    <select id="global-mult">
                      <option value="1">1x</option><option value="2">2x</option>
                      <option value="3">3x</option><option value="5">5x</option>
                      <option value="10">10x</option>
                    </select></label>
                </div>
                <div class="cb">
                  <div class="lh">
                    <span></span><span>B/S</span><span>Expiry</span><span>Strike</span>
                    <span>Type</span><span>Lots</span><span>Price</span><span></span>
                  </div>
                  <div id="leg-builder-mount"></div>
                  <div class="row" style="margin-top:11px">
                    <button class="btn" id="btn-add-leg" type="button">+ Add leg</button>
                    <button class="btn" id="btn-open-chain" type="button" title="Open interest, change in open interest, put-call ratio and the chain itself; click a strike to add the leg">Option chain</button>
                    <button class="btn" id="btn-clear-legs" type="button">Clear</button>
                    <span style="margin-left:auto;font-family:var(--m);font-size:12px" id="net-cost"></span>
                  </div>
                </div>
                <div class="why" id="leg-why"></div>
              </div>

              <div class="card">
                <h3>Ready-made <span class="r">loads at the expiry below</span></h3>
                <div class="toolbar one">
                  <label class="tf"><span>Expiry for ready-made strategies</span>
                    <select id="preset-expiry"></select></label>
                </div>
                <div class="cb"><div class="presets" id="strategy-presets-container"></div></div>
              </div>

              <div class="card">
                <h3>Strikewise IV <span class="r">edit to test a volatility change</span></h3>
                <div class="cb"><div id="iv-mount"></div></div>
              </div>

              <!-- The Greeks fill the vacant space at the bottom of the rail,
                   four label-and-value pairs across two rows, no header. The
                   rules stay at the bottom of the right column with the execute
                   button, in one block: a verdict is never separated from the
                   button it governs. Decided 2026-09-08; do not reopen. -->
              <div class="card" id="greeks-card">
                <div class="greeks" id="greeks-table"></div>
              </div>
            </div>

            <div>
              <div class="card"><div class="mets" id="metric-row"></div></div>

              <div class="card">
                <h3>Payoff <span class="r">drag the graph, or use the sliders</span></h3>
                <div id="payoff-chart-mount"></div>
                <div class="sliders">
                  <div class="sl">
                    <label>NIFTY target <button class="btn sm" id="target-reset" type="button" title="Back to the live spot">Reset</button> <b id="target-text">—</b></label>
                    <input type="range" id="target-range" min="0" max="1" step="5" value="0" disabled>
                    <div class="ends"><span id="target-min">—</span><span id="target-pct">—</span><span id="target-max">—</span></div>
                  </div>
                  <div class="sl">
                    <label>Date <button class="btn sm" id="dte-reset" type="button" title="Back to today">Reset</button> <b id="dte-text">—</b></label>
                    <input type="range" id="dte-range" min="0" max="1" step="1" value="0" disabled>
                    <div class="ends"><span>today</span><span id="dte-date">—</span><span>expiry day</span></div>
                  </div>
                </div>
                <div class="why" id="payoff-why"></div>
              </div>

              <div class="card">
                <h3>Rules and execution <span class="r" id="rules-source"></span></h3>
                <div class="carry" id="carry-row">
                  <span class="k">Plan</span>
                  <div class="seg" role="group" aria-label="Carrying overnight or closing today">
                    <button id="carry-overnight" type="button" aria-pressed="true">Carrying overnight</button>
                    <button id="carry-today" type="button" aria-pressed="false">Closing today</button>
                  </div>
                  <span class="s" id="carry-note"></span>
                </div>
                <div class="rules" id="rule-validation-mount"></div>
                <div class="why" id="rule-why"></div>
                <div class="exec">
                  <div class="banner" id="entry-banner"></div>
                  <div class="execbar" id="execute-row-mount"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div id="overnight-modal-container"></div>
      </div>
    `;

    const back = this.container.querySelector('#btn-back-to-home');
    if (back) back.addEventListener('click', () => this.options.onNavigateHome && this.options.onNavigateHome());
  }

  initSubComponents() {
    const tickerHost = this.container.querySelector('#strategy-sticky-ticker');
    if (tickerHost) {
      this.ticker = new MarketTickerComponent(tickerHost);
      this.ticker.render(this.tickerItems());
    }

    const chartHost = this.container.querySelector('#payoff-chart-mount');
    if (chartHost) {
      this.payoffChart = new PayoffSvgComponent(chartHost, {
        onTargetChange: (S) => this.setTarget(S),
      });
      this.payoffChart.init();
    }

    const modalMount = this.container.querySelector('#overnight-modal-container');
    if (modalMount) {
      this.overnightModal = new OvernightBlockModalComponent(modalMount, {
        onAddHedge: (violation) => this.loadSuggestedHedge(violation),
        onExitPosition: (violation) => this.exitPosition(violation),
      });
    }

    this.renderPresets();
    this.bindControls();
    this.renderAll();
  }

  /**
   * The 15:20 overnight-naked watch, carried over from the page this one
   * replaces. It has nothing to do with the layout and everything to do with
   * not waking up short and unhedged, so it stays.
   *
   * It watches positions that are already OPEN, which is a different job from
   * the four rules below, which judge the position he is building.
   */
  startOvernightWatch() {
    if (typeof setInterval !== 'function') return;
    const check = async () => {
      try {
        const res = await api.detectNakedShorts('15:20');
        this.safetyWarning = null;
        if (res && res.has_naked_shorts && res.violations && res.violations.length) {
          if (this.overnightModal && !this.overnightModal.isOpen) {
            this.overnightModal.show(res.violations[0]);
          }
        }
      } catch (err) {
        this.safetyWarning =
          'The overnight-naked check could not run: ' +
          ((err && err.message) || err) +
          '. Look at your open positions yourself before the bell.';
      }
      this.renderExecute();
    };
    check();
    this.cronTimer = setInterval(check, 30000);
    if (this.cronTimer && typeof this.cronTimer.unref === 'function') this.cronTimer.unref();
  }

  /**
   * Loads the hedge the server suggested into the legs table, at no price.
   *
   * The page this replaces pushed the same leg in at a premium of 35.00 and a
   * contract size of 75, both invented. The strike, type and expiry are the
   * server's; the price is fetched from the chain like any other leg, and stays
   * empty if there is none.
   */
  loadSuggestedHedge(violation) {
    const h = violation && violation.suggested_hedges && violation.suggested_hedges[0];
    if (!h) return;
    this.legs.push({
      on: true,
      bs: 'B',
      strike: h.strike,
      type: h.option_type,
      lots: h.quantity_lots || 1,
      price: null,
      priceSource: 'suggested hedge, not yet priced',
    });
    this.baseLots = this.legs.map((l) => l.lots);
    this.renderAll();
    this.repriceLeg(this.legs.length - 1);
  }

  async exitPosition(violation) {
    if (!violation || !violation.position_id) return;
    try {
      await api.closePosition(violation.position_id, {
        close_reason: 'time_exit',
        notes: 'Exited before the 15:20 IST cutoff, overnight-naked rule.',
      });
      this.executeNote = `Position ${String(violation.position_id).slice(0, 8)} closed.`;
      await this.refreshPositions();
    } catch (err) {
      this.executeNote = `Could not close it: ${(err && err.message) || err}`;
    }
    this.renderExecute();
  }

  bindControls() {
    const on = (id, evt, fn) => {
      const el = this.container.querySelector(`#${id}`);
      if (el && typeof el.addEventListener === 'function') el.addEventListener(evt, fn);
    };

    on('btn-add-leg', 'click', () => this.addLeg());
    on('btn-clear-legs', 'click', () => {
      this.legs = [];
      this.baseLots = [];
      this.strategyName = null;
      this.preview = null;
      this.validation = null;
      this.renderAll();
    });

    on('global-expiry', 'change', (e) => this.setExpiry(e.target.value, true));
    on('preset-expiry', 'change', (e) => this.setExpiry(e.target.value, true));
    on('global-mult', 'change', (e) => this.applyMultiplier(Number(e.target.value) || 1));

    on('carry-overnight', 'click', () => this.setCarry('overnight'));
    on('carry-today', 'click', () => this.setCarry('today'));

    on('target-range', 'input', (e) => this.setTarget(Number(e.target.value)));
    // The slider runs left = today, right = expiry day, so its value is the
    // number of days elapsed and dteDays is what is left.
    on('dte-range', 'input', (e) => {
      this.dteDays = Math.max(0, (this.dteMax || 0) - Number(e.target.value));
      this.renderRight();
    });
    on('target-reset', 'click', () => {
      if (this.spot) this.setTarget(Math.round(this.spot / 5) * 5);
    });
    on('dte-reset', 'click', () => {
      this.dteDays = this.dteMax || 0;
      this.renderRight();
    });
    on('btn-open-chain', 'click', () => this.openChain());

    const legs = this.container.querySelector('#leg-builder-mount');
    if (legs && typeof legs.addEventListener === 'function') {
      legs.addEventListener('input', (e) => this.onLegInput(e));
      legs.addEventListener('change', (e) => this.onLegInput(e));
      legs.addEventListener('click', (e) => this.onLegClick(e));
    }

    const ivs = this.container.querySelector('#iv-mount');
    if (ivs && typeof ivs.addEventListener === 'function') {
      ivs.addEventListener('click', (e) => this.onIvClick(e));
      ivs.addEventListener('input', (e) => this.onIvInput(e));
    }

    const presets = this.container.querySelector('#strategy-presets-container');
    if (presets && typeof presets.addEventListener === 'function') {
      presets.addEventListener('click', (e) => {
        const el = e.target && typeof e.target.closest === 'function' ? e.target.closest('.preset') : null;
        const name = el ? el.getAttribute('data-name') : e.target && e.target.getAttribute && e.target.getAttribute('data-name');
        if (name) this.loadPreset(name);
      });
    }
  }

  // -------------------------------------------------------------- data loads

  async loadInitialData() {
    await Promise.all([
      this.loadSpot(),
      this.loadExpiries(),
      this.loadCapital(),
      this.refreshPositions(),
    ]);
    this.renderAll();
  }

  async loadSpot() {
    try {
      const res = await api.getNiftySpot();
      this.spot = res && typeof res.spot === 'number' ? res.spot : null;
      this.spotFreshness = this.spot === null ? null : 'live';
      this.spotError = null;
      this.spotAt = res && res.as_of ? res.as_of : new Date().toISOString();
      if (this.spot !== null && this.targetSpot === null) this.targetSpot = Math.round(this.spot / 5) * 5;
    } catch (err) {
      this.spot = null;
      this.spotError = (err && err.message) || String(err);
    }
    this.renderSpot();
  }

  async loadExpiries() {
    try {
      const res = await api.getExpiries();
      this.expiries = (res && res.expiries) || [];
      this.expiryError = null;
      this.today = (res && res.today) || null;
      this.nextTradingDay = (res && res.next_trading_day) || null;
      if (this.expiries.length && !this.expiry) {
        const monthly = this.expiries.find((e) => e.is_monthly) || this.expiries[0];
        this.expiry = monthly.date;
        this.dteMax = monthly.calendar_days;
        this.dteDays = monthly.calendar_days;
      }
    } catch (err) {
      this.expiries = [];
      this.expiryError = (err && err.message) || String(err);
    }
    this.renderExpiryPickers();
  }

  async loadCapital() {
    try {
      this.capital = await api.getRiskCapital();
      this.capitalError = null;
    } catch (err) {
      this.capital = null;
      this.capitalError = (err && err.message) || String(err);
    }
  }

  async refreshPositions() {
    try {
      const res = await api.getPositions('open');
      this.positions = Array.isArray(res) ? res : (res && res.positions) || [];
      let total = 0;
      let sawOne = false;
      for (const p of this.positions) {
        if (typeof p.margin_used_inr === 'number') { total += p.margin_used_inr; sawOne = true; }
        else if (typeof p.margin_blocked_inr === 'number') { total += p.margin_blocked_inr; sawOne = true; }
      }
      this.marginUsed = this.positions.length === 0 ? 0 : sawOne ? total : null;
    } catch (_) {
      this.positions = null;
      this.marginUsed = null;
    }
    this.renderMetrics();
  }

  // ---------------------------------------------------------------- the legs

  atmStrike() {
    if (!this.spot) return null;
    return Math.round(this.spot / STRIKE_STEP) * STRIKE_STEP;
  }

  async loadPreset(name) {
    const shape = PRESETS[name];
    if (!shape) return;
    if (!this.spot) {
      this.executeNote = 'No live NIFTY price, so strikes cannot be placed at the money. Nothing was loaded.';
      this.renderExecute();
      return;
    }
    const atm = this.atmStrike();
    this.strategyName = name;
    this.legs = shape.map(([bs, offset, type, lots]) => ({
      on: true,
      bs,
      strike: atm + offset,
      type,
      lots: lots || 1,
      price: null,
      priceSource: null,
    }));
    this.baseLots = this.legs.map((l) => l.lots);
    const mult = this.container.querySelector('#global-mult');
    if (mult) mult.value = '1';
    this.renderAll();
    await this.repriceLegs();
  }

  addLeg() {
    const atm = this.atmStrike();
    if (atm === null) {
      this.executeNote = 'No live NIFTY price, so a new leg has no strike to sit on.';
      this.renderExecute();
      return;
    }
    this.legs.push({ on: true, bs: 'B', strike: atm, type: 'CE', lots: 1, price: null, priceSource: null });
    this.baseLots = this.legs.map((l) => l.lots);
    this.renderAll();
    this.repriceLeg(this.legs.length - 1);
  }

  /** Real quotes only. A strike with no traded price keeps a blank price box. */
  async repriceLegs() {
    await Promise.all(this.legs.map((_, i) => this.repriceLeg(i)));
    this.renderAll();
    this.scheduleServerRefresh();
  }

  async repriceLeg(index, opts = {}) {
    const leg = this.legs[index];
    if (!leg || !this.expiry) return;
    // His own limit price is his. A quote never overwrites it.
    if (leg.priceSource === OWN_PRICE && opts.render === false) return;
    try {
      const q = await api.getOptionQuote({ strike: leg.strike, expiry: this.expiry, type: leg.type });
      if (q && q.available && typeof q.ltp === 'number') {
        leg.price = q.ltp;
        leg.priceSource = q.source || 'chain';
        leg.priceAt = q.as_of || new Date().toISOString();
      } else if (opts.keepStale && leg.price !== null && q && q.error) {
        // The chain could not be READ this time round. The price already on
        // the row was a real traded price a few seconds ago; blanking it would
        // drop every rule for a transient. It stays, labelled with its age.
        leg.priceSource = `last traded price, read ${istTime(leg.priceAt) || 'earlier'} IST; the latest re-quote failed: ${q.error}`;
      } else {
        leg.price = null;
        leg.priceSource = (q && q.note) || 'no traded price for this strike and expiry';
      }
      if (q && typeof q.iv === 'number' && q.iv > 0) {
        this.ivPctByStrike[leg.strike] = q.iv * 100;
        this.ivSource[leg.strike] = 'implied from the traded price';
      } else if (this.ivSource[leg.strike] === 'implied from the traded price') {
        // The old expiry's volatility must not linger on the new one. His own
        // typed volatility is his and survives; an implied one belongs to the
        // price it came from, and that price is gone.
        delete this.ivPctByStrike[leg.strike];
        delete this.ivSource[leg.strike];
      }
    } catch (err) {
      leg.price = null;
      leg.priceSource = (err && err.message) || 'quote unavailable';
    }
    this.pricesReadAt = new Date().toISOString();
    if (opts.render === false) return;
    this.renderLegs();
    this.renderIvs();
    this.renderRight();
  }

  setExpiry(value, reprice) {
    if (!value) return;
    this.expiry = value;
    const meta = this.expiries.find((e) => e.date === value);
    if (meta) {
      this.dteMax = meta.calendar_days;
      this.dteDays = meta.calendar_days;
    }
    const ge = this.container.querySelector('#global-expiry');
    const pe = this.container.querySelector('#preset-expiry');
    if (ge) ge.value = value;
    if (pe) pe.value = value;
    this.renderAll();
    if (reprice && this.legs.length) this.repriceLegs();
  }

  /** The option chain as a floating panel. Legs added from it are ordinary legs. */
  openChain() {
    if (!this.chainModal) {
      const host = typeof document !== 'undefined' ? document.body : null;
      this.chainModal = new OptionChainModalComponent(host, {
        onAddLeg: (leg) => this.addLegFromChain(leg),
        getExpiry: () => this.expiry,
        getSpot: () => this.spot,
        refreshMs: this.requoteMs,
      });
    }
    this.chainModal.open();
  }

  /**
   * A leg from the chain arrives with the real traded price on screen and the
   * volatility implied from it. From here on it is a normal leg: re-quoted
   * every 5 s, priced by the server's contract size, judged by the four rules.
   */
  addLegFromChain(leg) {
    if (!leg || !this.expiry) return;
    const now = leg.asOf || new Date().toISOString();
    this.legs.push({
      on: true,
      bs: leg.bs === 'S' ? 'S' : 'B',
      strike: leg.strike,
      type: leg.type === 'PE' ? 'PE' : 'CE',
      lots: 1,
      price: typeof leg.price === 'number' ? leg.price : null,
      priceSource: `option chain, read ${istTime(now) || ''} IST`.trim(),
      priceAt: now,
    });
    if (typeof leg.iv === 'number' && leg.iv > 0) {
      this.ivPctByStrike[leg.strike] = leg.iv * 100;
      this.ivSource[leg.strike] = 'implied from the traded price';
    }
    this.baseLots = this.legs.map((l) => l.lots);
    if (!this.strategyName) this.strategyName = 'Custom';
    this.renderAll();
    this.scheduleServerRefresh();
  }

  /** Scales every leg from its ORIGINAL lot count, so 3x back to 1x returns home. */
  applyMultiplier(mult) {
    if (!this.baseLots.length || this.baseLots.length !== this.legs.length) {
      this.baseLots = this.legs.map((l) => l.lots);
    }
    this.legs.forEach((l, i) => {
      l.lots = Math.max(1, Math.round((this.baseLots[i] || 1) * mult));
    });
    this.renderAll();
    this.scheduleServerRefresh();
  }

  onLegInput(e) {
    const t = e.target;
    if (!t || !t.dataset) return;
    const i = Number(t.dataset.i);
    const f = t.dataset.f;
    if (Number.isNaN(i) || !f || !this.legs[i]) return;
    if (f === 'on') this.legs[i].on = t.checked !== undefined ? t.checked : !this.legs[i].on;
    else if (f === 'strike') this.legs[i].strike = Math.max(1, Number(t.value) || this.legs[i].strike);
    else if (f === 'lots') {
      this.legs[i].lots = Math.max(1, Number(t.value) || 1);
      this.baseLots = this.legs.map((l) => l.lots);
    } else if (f === 'price') {
      const v = parseFloat(t.value);
      this.legs[i].price = Number.isFinite(v) && v >= 0 ? v : null;
      this.legs[i].priceSource = OWN_PRICE;
    } else if (f === 'type') this.legs[i].type = t.value;
    this.renderRight();
    this.renderIvs();
    this.scheduleServerRefresh();
  }

  onLegClick(e) {
    const t = e.target;
    if (!t || !t.dataset) return;
    const i = Number(t.dataset.i);
    const f = t.dataset.f;
    if (Number.isNaN(i) || !f || !this.legs[i]) return;
    if (f === 'bs') {
      this.legs[i].bs = this.legs[i].bs === 'B' ? 'S' : 'B';
      this.renderAll();
      this.scheduleServerRefresh();
    } else if (f === 'del') {
      this.legs.splice(i, 1);
      this.baseLots = this.legs.map((l) => l.lots);
      this.renderAll();
      this.scheduleServerRefresh();
    } else if (f === 'strike-' || f === 'strike+') {
      this.legs[i].strike += f === 'strike+' ? STRIKE_STEP : -STRIKE_STEP;
      this.renderAll();
      this.repriceLeg(i);
      this.scheduleServerRefresh();
    }
  }

  onIvClick(e) {
    const t = e.target;
    if (!t || !t.dataset || !t.dataset.iv) return;
    const strike = Number(t.dataset.iv);
    const delta = Number(t.dataset.d);
    const current = this.ivPctByStrike[strike];
    if (!(current > 0)) return; // never step away from a volatility we never measured
    this.ivPctByStrike[strike] = Math.max(0.5, current + delta);
    this.ivSource[strike] = 'your own volatility';
    this.renderIvs();
    this.renderRight();
  }

  onIvInput(e) {
    const t = e.target;
    if (!t || !t.dataset || !t.dataset.ivin) return;
    const strike = Number(t.dataset.ivin);
    const v = parseFloat(t.value);
    if (Number.isFinite(v) && v > 0) {
      this.ivPctByStrike[strike] = v;
      this.ivSource[strike] = 'your own volatility';
      this.renderRight();
    }
  }

  ivFor(leg) {
    const p = this.ivPctByStrike[leg.strike];
    return p > 0 ? p / 100 : null;
  }

  mathOpts() {
    return {
      lotSize: this.lotSize,
      spot: this.spot,
      ivFor: (leg) => this.ivFor(leg),
    };
  }

  setTarget(S) {
    this.targetSpot = S;
    const range = this.container.querySelector('#target-range');
    if (range) range.value = String(S);
    this.renderRight();
  }

  // ------------------------------------------------------------ server calls

  activeLegs() {
    return this.legs.filter((l) => l.on);
  }

  /** True once every active leg carries a price the server can price rules from. */
  fullyPriced() {
    const on = this.activeLegs();
    return on.length > 0 && on.every((l) => l.price !== null);
  }

  /** The active legs with no price, named the way he reads them: "24,900 CE". */
  unpricedLegs() {
    return this.activeLegs().filter((l) => l.price === null).map((l) => `${num(l.strike)} ${l.type}`);
  }

  setCarry(mode) {
    this.carry = mode === 'today' ? 'today' : 'overnight';
    this.renderCarry();
    this.renderRules();
    this.renderExecute();
    this.scheduleServerRefresh();
  }

  /** The planned exit the server is told about. Null means closing today. */
  plannedExitDate() {
    if (this.carry !== 'overnight') return null;
    return this.nextTradingDay || null;
  }

  renderCarry() {
    const over = this.container.querySelector('#carry-overnight');
    const today = this.container.querySelector('#carry-today');
    const note = this.container.querySelector('#carry-note');
    const overnight = this.carry === 'overnight';
    if (over) over.setAttribute('aria-pressed', String(overnight));
    if (today) today.setAttribute('aria-pressed', String(!overnight));
    if (note) {
      note.textContent = overnight
        ? this.nextTradingDay
          ? `rule 2 is tested against the next session, ${this.nextTradingDay}`
          : 'the next trading day is unknown, so rule 2 cannot be tested'
        : 'closing before the bell, so rule 2 is not tested';
    }
  }

  legsPayload() {
    return this.activeLegs().map((l) => ({
      strike: l.strike,
      option_type: l.type,
      direction: l.bs === 'B' ? 'buy' : 'sell',
      quantity_lots: l.lots,
      entry_premium: l.price,
      expiry_date: this.expiry,
    }));
  }

  scheduleServerRefresh() {
    if (typeof setTimeout !== 'function') return;
    if (this._serverTimer) clearTimeout(this._serverTimer);
    this._serverTimer = setTimeout(() => this.refreshFromServer(), 350);
  }

  /**
   * The server resolves the real contract size, the real broker margin and all
   * four rules. Where it answers, it wins over anything computed in the browser.
   */
  async refreshFromServer() {
    const legs = this.legsPayload();
    if (!legs.length || !this.expiry || !this.spot) return;

    // An unpriced leg used to be sent as a zero premium. The server would then
    // price all four rules off a premium nobody paid and the page would show
    // those figures as his own. Nothing is sent until every leg has a price,
    // and any answer from an earlier, priced state is dropped so it cannot sit
    // on screen describing a position that no longer exists. The panel then
    // names the leg holding things up rather than going blank.
    if (!this.fullyPriced()) {
      this.preview = null;
      this.validation = null;
      this.previewError = null;
      const missing = this.unpricedLegs();
      this.validationError = `${missing.join(', ')} ${missing.length === 1 ? 'has' : 'have'} no traded price, so rules 1, 2 and 3 are not checked.`;
      this.renderAll();
      return;
    }

    const payload = {
      strategy_name: this.strategyName || 'Custom',
      underlying: 'NIFTY',
      current_spot: this.spot,
      iv_per_leg: {},
      legs,
      // Carrying overnight by default: the server computes the gap test only
      // when this is later than today. Closing today sends nothing.
      planned_exit_date: this.plannedExitDate(),
    };

    await Promise.all([
      (async () => {
        try {
          this.preview = await api.previewOrder({ underlying: 'NIFTY', current_spot: this.spot, legs });
          this.previewError = null;
          const first = this.preview && this.preview.ordered_legs && this.preview.ordered_legs[0];
          if (first && typeof first.lot_size === 'number' && first.lot_size > 0) {
            this.lotSize = first.lot_size;
            this.lotSizeSource = 'FYERS contract master, resolved server-side';
          }
        } catch (err) {
          this.preview = null;
          this.previewError = (err && err.message) || String(err);
        }
      })(),
      (async () => {
        try {
          this.validation = await api.validateStrategy(payload);
          this.validationError = null;
          this.rulesCheckedAt = new Date().toISOString();
        } catch (err) {
          this.validation = null;
          this.validationError = (err && err.message) || String(err);
        }
      })(),
    ]);

    this.renderAll();
  }

  // ------------------------------------------------------------- render bits

  renderAll() {
    this.renderSpot();
    this.renderExpiryPickers();
    this.renderCarry();
    this.renderLegs();
    this.renderIvs();
    this.renderRight();
    if (this.ticker) this.ticker.render(this.tickerItems());
  }

  renderRight() {
    this.renderMetrics();
    this.renderSliders();
    this.renderChart();
    this.renderGreeks();
    this.renderRules();
    this.renderExecute();
  }

  tickerItems() {
    const cap = this.capital || {};
    return [
      { label: 'NIFTY 50', value: num(this.spot, 2), raw: this.spot, note: this.spotAt ? `tick ${istTime(this.spotAt) || ''}`.trim() : this.spotFreshness || '' },
      { label: 'Lot', value: this.lotSize === null ? null : String(this.lotSize), note: this.lotSize === null ? 'server has not confirmed it' : 'contract master' },
      { label: 'Expiry', value: this.expiry || null },
      { label: 'Balance', value: inr(cap.risk_capital_inr), note: cap.source ? 'FYERS funds()' : '' },
      { label: 'Running loss cap', value: inr(cap.primary_risk_cap_inr), note: '1%' },
      { label: 'Overnight gap cap', value: typeof cap.risk_capital_inr === 'number' ? inr(cap.risk_capital_inr * 0.02) : null, note: '2%' },
      { label: 'Black swan cap', value: inr(cap.black_swan_fuse_inr), note: '5%' },
      { label: 'Margin ceiling', value: inr(cap.deployable_margin_ceiling_inr), note: cap.ceiling_unavailable_reason || '2x cash equivalent' },
      { label: 'Margin used', value: inr(this.marginUsed), note: this.marginUsed === null ? 'positions unread' : '' },
    ];
  }

  renderSpot() {
    const host = this.container.querySelector('#desk-spot');
    if (!host) return;
    host.innerHTML =
      `<span style="font-family:var(--m);font-size:11px;color:var(--fg-3)">NIFTY</span>` +
      `<b>${this.spot === null ? '—' : escapeHtml(num(this.spot, 2))}</b>` +
      (this.spot === null
        ? `<span class="chip c-na">${escapeHtml(this.spotError || 'no live price')}</span>`
        : `<span class="chip c-live">live${this.spotAt ? ` · ${escapeHtml(istTime(this.spotAt) || '')} IST` : ''}</span>`) +
      (this.lotSize === null
        ? `<span class="chip c-na">lot unconfirmed</span>`
        : `<span class="chip c-info">lot ${this.lotSize}</span>`);
  }

  renderExpiryPickers() {
    const opts = this.expiries.length
      ? this.expiries
          .map((e) => `<option value="${escapeHtml(e.date)}"${e.date === this.expiry ? ' selected' : ''}>${escapeHtml(e.label)}${e.is_monthly ? ' · monthly' : ''}</option>`)
          .join('')
      : `<option value="">${escapeHtml(this.expiryError ? 'expiries unavailable' : 'loading…')}</option>`;
    ['global-expiry', 'preset-expiry'].forEach((id) => {
      const el = this.container.querySelector(`#${id}`);
      if (el) {
        el.innerHTML = opts;
        if (this.expiry) el.value = this.expiry;
      }
    });
  }

  renderPresets() {
    const host = this.container.querySelector('#strategy-presets-container');
    if (!host) return;
    host.innerHTML = Object.keys(PRESETS)
      .map((name) => `<div class="preset${this.strategyName === name ? ' on' : ''}" data-name="${escapeHtml(name)}">
        <svg width="64" height="32" viewBox="0 0 64 32">
          <line x1="0" y1="17" x2="64" y2="17" stroke="var(--line-2)" stroke-width="1"/>
          <path d="${SPARKS[name]}" fill="none" stroke="var(--fg)" stroke-width="1.8" stroke-linejoin="round"/>
        </svg><span>${escapeHtml(name)}</span></div>`)
      .join('');
  }

  renderLegs() {
    const host = this.container.querySelector('#leg-builder-mount');
    const expiryLabel = (this.expiries.find((e) => e.date === this.expiry) || {}).label || (this.expiry || '—');
    if (host) {
      host.innerHTML = this.legs
        .map((l, i) => `
        <div class="lr${l.on ? '' : ' off'}">
          <input type="checkbox" ${l.on ? 'checked' : ''} data-i="${i}" data-f="on" aria-label="Include this leg"
                 style="width:15px;height:15px;padding:0;accent-color:var(--info)">
          <button class="bs ${l.bs}" data-i="${i}" data-f="bs" type="button" title="Buy or sell">${l.bs}</button>
          <input value="${escapeHtml(expiryLabel)}" readonly title="Change the expiry for all legs in the toolbar above"
                 style="text-align:center;color:var(--fg-2);cursor:default">
          <div class="stepper">
            <button data-i="${i}" data-f="strike-" type="button" aria-label="Strike down 50">−</button>
            <input value="${l.strike}" data-i="${i}" data-f="strike" inputmode="numeric" aria-label="Strike">
            <button data-i="${i}" data-f="strike+" type="button" aria-label="Strike up 50">+</button>
          </div>
          <select data-i="${i}" data-f="type" aria-label="Call or put">
            <option${l.type === 'CE' ? ' selected' : ''}>CE</option>
            <option${l.type === 'PE' ? ' selected' : ''}>PE</option>
          </select>
          <select class="lots" data-i="${i}" data-f="lots" aria-label="Lots">${lotOptions(l.lots)}</select>
          <input value="${l.price === null ? '' : l.price.toFixed(2)}" data-i="${i}" data-f="price"
                 class="${l.priceSource === OWN_PRICE ? 'own' : ''}${flashFor(this._flash, `price-${i}-${l.strike}-${l.type}`, l.price)}"
                 inputmode="decimal" placeholder="—" title="${escapeHtml(l.priceSource || '')}" aria-label="Price">
          <button class="trash" data-i="${i}" data-f="del" type="button" aria-label="Delete leg" title="Delete leg">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round" style="pointer-events:none">
              <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6"/>
              <path d="M10 11v6M14 11v6"/></svg></button>
        </div>`)
        .join('');
    }

    const count = this.container.querySelector('#leg-count');
    if (count) count.textContent = this.legs.length ? `${this.legs.filter((l) => l.on).length} active` : '';

    const cost = entryCost(this.legs, this.lotSize);
    const net = this.container.querySelector('#net-cost');
    if (net) {
      if (!this.legs.length) net.innerHTML = '';
      else if (cost === null) net.innerHTML = `<span class="na">net cost unavailable</span>`;
      else net.innerHTML = cost >= 0
        ? `Net debit <b>${escapeHtml(inr(cost))}</b>`
        : `Net credit <b style="color:var(--up)">${escapeHtml(inr(-cost))}</b>`;
    }

    const why = this.container.querySelector('#leg-why');
    if (why) {
      if (!this.legs.length) {
        why.textContent = 'No legs. Load a ready-made strategy or add one.';
      } else {
        const on = this.legs.filter((l) => l.on);
        const missing = on.filter((l) => l.price === null).length;
        const contracts = this.lotSize === null ? null : on.reduce((a, l) => a + l.lots, 0) * this.lotSize;
        why.textContent =
          (this.lotSize === null
            ? 'Contract size not confirmed by the server yet, so nothing is scaled into rupees. '
            : `Contract size ${this.lotSize} per lot, ${this.lotSizeSource}. ${on.length} active leg(s), ${contracts} contracts. `) +
          (missing
            ? `${missing} leg(s) have no traded price — type your own; nothing is seeded for you.`
            : 'Prices are the traded prices from the chain, or the ones you typed.') +
          (this.pricesReadAt ? ` Prices read ${istTime(this.pricesReadAt)} IST, re-read every ${Math.round(this.requoteMs / 1000)} s; a price you typed is never overwritten.` : '');
      }
    }
  }

  renderIvs() {
    const host = this.container.querySelector('#iv-mount');
    if (!host) return;
    const strikes = [...new Set(this.legs.filter((l) => l.on).map((l) => l.strike))].sort((a, b) => a - b);
    if (!strikes.length) {
      host.innerHTML = '<div class="na" style="font-size:12.5px">Add a leg to edit its volatility.</div>';
      return;
    }
    host.innerHTML =
      `<table class="g"><thead><tr><th>Strike</th><th style="text-align:right">IV %</th><th>Source</th></tr></thead><tbody>` +
      strikes
        .map((k) => {
          const v = this.ivPctByStrike[k];
          const cell = v > 0
            ? `<div class="stepper">
                 <button data-iv="${k}" data-d="-0.5" type="button" aria-label="Lower IV">−</button>
                 <input value="${v.toFixed(1)}" data-ivin="${k}" inputmode="decimal" aria-label="Implied volatility">
                 <button data-iv="${k}" data-d="0.5" type="button" aria-label="Raise IV">+</button></div>`
            : `<div class="stepper"><input value="" placeholder="—" data-ivin="${k}" inputmode="decimal" aria-label="Implied volatility"></div>`;
          const src = v > 0 ? this.ivSource[k] || 'entered' : 'unavailable — no traded price to imply from';
          return `<tr><td class="n" style="text-align:left">${k}</td>
            <td class="n" style="width:120px">${cell}</td>
            <td style="color:var(--fg-3);font-size:11px">${escapeHtml(src)}</td></tr>`;
        })
        .join('') +
      `</tbody></table>`;
  }

  _met(k, value, sub, colour, raw, accent = false) {
    const flash = raw === undefined ? '' : flashFor(this._flash, `met-${k}`, raw);
    const small = value !== null && String(value).length > 7 && !accent;
    return `<div class="met"><div class="k">${escapeHtml(k)}</div>
      <div class="v${small ? ' sm' : ''}${accent ? ' acc' : ''}${flash}"${colour ? ` style="color:${colour}"` : ''}>${value === null ? '<span class="na" style="font-size:14px">unavailable</span>' : escapeHtml(value)}</div>
      <div class="s">${escapeHtml(sub || '')}</div></div>`;
  }

  marginFree() {
    const ceiling = this.capital && typeof this.capital.deployable_margin_ceiling_inr === 'number'
      ? this.capital.deployable_margin_ceiling_inr
      : null;
    if (ceiling === null || this.marginUsed === null) return null;
    return ceiling - this.marginUsed;
  }

  renderMetrics() {
    const host = this.container.querySelector('#metric-row');
    if (!host) return;

    const opts = this.mathOpts();
    const { maxLoss, maxProfit, unlimited, unlimitedUp } = maxLossProfit(this.legs, opts);
    const bes = breakevens(this.legs, opts);
    const bal = this.capital && typeof this.capital.risk_capital_inr === 'number' ? this.capital.risk_capital_inr : null;

    // Margin needed is the broker's number or nothing. It is never modelled here.
    const need = this.preview && typeof this.preview.margin_required_inr === 'number'
      ? this.preview.margin_required_inr
      : null;
    const free = this.marginFree();
    const fits = need !== null && free !== null ? need <= free : null;

    const T = (this.dteDays || 0) / 365;
    const proj = this.targetSpot ? pnlAt(this.legs, this.targetSpot, T, opts) : null;

    // A ratio is only meaningful with a capped loss AND a profit worth having.
    const mathRan = maxLoss !== null && maxProfit !== null;
    const rr = !unlimited && mathRan && maxLoss > 0 && maxProfit > 0 ? maxProfit / maxLoss : null;
    const rrNote = unlimited
      ? 'the loss has no ceiling'
      : mathRan && maxProfit !== null && maxProfit <= 0
        ? 'the best case here is still a loss'
        : '';

    const marginSub = need === null
      ? (this.previewError || (this.preview && this.preview.margin_unavailable_reason) || 'the broker has not priced this basket')
      : free === null
        ? 'free margin unknown until positions and the ceiling are read'
        : fits
          ? `fits · ${inr(free)} free`
          : `SHORT BY ${inr(need - free)} · ${inr(free)} free`;

    host.innerHTML =
      this._met('Margin needed', need === null ? null : inr(need), marginSub,
        need === null ? 'var(--fg-3)' : fits === null ? null : fits ? 'var(--up)' : 'var(--down)', need, true) +
      this._met('Margin used', this.marginUsed === null ? null : inr(this.marginUsed),
        this.capital && typeof this.capital.deployable_margin_ceiling_inr === 'number'
          ? `of ${inr(this.capital.deployable_margin_ceiling_inr)} ceiling`
          : 'ceiling unavailable', 'var(--fg-2)') +
      this._met('Max profit', maxProfit === null ? null : inr(maxProfit),
        maxProfit !== null && bal ? `${((maxProfit / bal) * 100).toFixed(2)}% of balance` : '',
        maxProfit === null ? null : maxProfit >= 0 ? 'var(--up)' : 'var(--down)', maxProfit) +
      this._met('Max loss', unlimited ? 'Unlimited' : maxLoss === null ? null : inr(maxLoss),
        unlimited ? `no ceiling ${unlimitedUp ? 'above' : 'below'}` : maxLoss !== null && bal ? `${((maxLoss / bal) * 100).toFixed(2)}% of balance` : '', 'var(--down)', unlimited ? undefined : maxLoss, true) +
      this._met('Breakeven', bes.length ? bes.map((b) => num(b)).join(' / ') : mathRan ? 'none' : null,
        bes.length === 1 && this.spot
          ? `${bes[0] - this.spot > 0 ? '+' : ''}${Math.round(bes[0] - this.spot)} pts from spot`
          : bes.length > 1
            ? 'two sides'
            : mathRan
              ? 'the payoff never crosses zero'
              : '') +
      this._met('Reward : risk', unlimited || (mathRan && rr === null) ? 'n/a' : rr === null ? null : `1 : ${rr.toFixed(2)}`, rrNote) +
      this._met('At your target', proj === null ? null : inr(proj),
        this.targetSpot ? `${num(this.targetSpot)} in ${Math.max(0, (this.dteMax || 0) - (this.dteDays || 0))}d` : '',
        proj === null ? null : proj >= 0 ? 'var(--up)' : 'var(--down)', proj);
  }

  renderSliders() {
    const text = (id, value) => {
      const el = this.container.querySelector(`#${id}`);
      if (el) el.textContent = value;
    };

    const range = this.container.querySelector('#target-range');
    if (range && this.spot) {
      const lo = Math.round((this.spot * 0.94) / 5) * 5;
      const hi = Math.round((this.spot * 1.06) / 5) * 5;
      range.min = String(lo);
      range.max = String(hi);
      range.disabled = false;
      if (this.targetSpot === null) this.targetSpot = Math.round(this.spot / 5) * 5;
      range.value = String(this.targetSpot);
      text('target-min', num(lo));
      text('target-max', num(hi));
      text('target-text', num(this.targetSpot));
      text('target-pct', signedPct(((this.targetSpot - this.spot) / this.spot) * 100));
    } else {
      text('target-text', 'no live spot');
      text('target-pct', '—');
      if (range) range.disabled = true;
    }

    const dte = this.container.querySelector('#dte-range');
    if (dte && this.dteMax > 0) {
      dte.min = '0';
      dte.max = String(this.dteMax);
      dte.disabled = false;
      dte.value = String(Math.max(0, this.dteMax - (this.dteDays || 0)));
      const elapsed = Math.max(0, this.dteMax - (this.dteDays || 0));
      text('dte-text', this.dteDays === 0
        ? 'expiry day'
        : elapsed === 0
          ? `today · ${this.dteDays} day${this.dteDays > 1 ? 's' : ''} to expiry`
          : `in ${elapsed} day${elapsed > 1 ? 's' : ''} · ${this.dteDays} left`);
      text('dte-date', (this.expiries.find((e) => e.date === this.expiry) || {}).label || this.expiry || '—');
    } else {
      text('dte-text', 'no expiry');
      if (dte) dte.disabled = true;
    }
  }

  renderChart() {
    if (!this.payoffChart) return;
    this.payoffChart.update({
      legs: this.legs,
      spot: this.spot,
      lotSize: this.lotSize,
      ivFor: (leg) => this.ivFor(leg),
      dteDays: this.dteDays,
      dteMax: this.dteMax,
      targetSpot: this.targetSpot,
      reason: this.spot === null ? this.spotError : null,
    });
    const why = this.container.querySelector('#payoff-why');
    if (why) {
      why.textContent = this.legs.length
        ? 'Black line is the value at expiry. Blue line is the value on your chosen date, which still holds time value. Drag anywhere on the graph to move the target.'
        : '';
    }
  }

  renderGreeks() {
    const host = this.container.querySelector('#greeks-table');
    if (!host) return;
    if (!this.activeLegs().length) {
      host.innerHTML = '<div class="na-row na">Greeks appear here once there is a position.</div>';
      return;
    }
    const g = netGreeks(this.legs, this.targetSpot || this.spot, (this.dteDays || 0) / 365, {
      lotSize: this.lotSize,
      ivFor: (leg) => this.ivFor(leg),
    });
    if (!g) {
      host.innerHTML =
        '<div class="na-row na">Greeks unavailable: they need a measured volatility on every leg and a confirmed contract size.</div>';
      return;
    }
    const pair = (k, v, colour) =>
      `<div class="gk"><div class="k">${escapeHtml(k)}</div><div class="v"${colour ? ` style="color:${colour}"` : ''}>${escapeHtml(v)}</div></div>`;
    host.innerHTML =
      pair('Delta', g.delta.toFixed(1)) +
      pair('Gamma', g.gamma.toFixed(4)) +
      pair('Theta / day', inr(g.theta), g.theta >= 0 ? 'var(--up)' : 'var(--down)') +
      pair('Vega / 1% IV', inr(g.vega));
  }

  _rule(state, k, value, sub) {
    return `<div class="rl ${state}"><div class="k">${escapeHtml(k)}</div>
      <div class="v"${state === 'pass' ? ' style="color:var(--up)"' : state === 'fail' ? ' style="color:var(--down)"' : ''}>${value === null ? '<span class="na" style="font-size:13px">unavailable</span>' : escapeHtml(value)}</div>
      <div class="s">${escapeHtml(sub)}</div></div>`;
  }

  renderRules() {
    const host = this.container.querySelector('#rule-validation-mount');
    const why = this.container.querySelector('#rule-why');
    const src = this.container.querySelector('#rules-source');
    if (!host) return;

    if (!this.activeLegs().length) {
      host.innerHTML = '<div class="rl idle" style="grid-column:1/-1"><div class="k">Waiting for a position</div></div>';
      if (why) why.textContent = '';
      if (src) src.textContent = '';
      return;
    }

    const v = this.validation;
    if (src) {
      const stamp = this.rulesCheckedAt ? ` · checked ${istTime(this.rulesCheckedAt)} IST` : '';
      src.textContent = v && v.capital && typeof v.capital.risk_capital_inr === 'number'
        ? `caps from a live balance of ${inr(v.capital.risk_capital_inr)}${stamp}`
        : 'caps unavailable';
    }

    if (!v) {
      // Unpriced leg or a failed check: the rules that can be answered from
      // what is known are still drawn, and the reason names the leg.
      const missing = this.unpricedLegs();
      const held = missing.length
        ? `${missing.join(', ')} ${missing.length === 1 ? 'has' : 'have'} no traded price`
        : null;
      const idleWhy = held ? `${held}, so this is not checked` : 'the server has not checked this position';
      host.innerHTML =
        this._rule('idle', '1 · Running loss', null, idleWhy) +
        this._rule('idle', '2 · Overnight gap', null,
          this.carry !== 'overnight' ? 'not tested — you are closing before the bell' : idleWhy) +
        this._rule('idle', '3 · Black swan', null, idleWhy) +
        this._rule4();
      if (why) {
        why.textContent = this.validationError
          ? `The rule check could not run: ${this.validationError}`
          : 'The rule check has not run yet.';
      }
      return;
    }

    const rr = v.realistic_risk || {};
    const blast = v.blast_radius || {};
    const carry = v.carry || null;
    // The server omits `carry` for an intraday position, which is the normal
    // case and NOT missing data. Without reading `intraday` the panel cannot
    // tell the two apart, and it told him his daily-move history was missing
    // when the backend had 20 sessions and an 80-point average.
    const intraday = v.intraday !== false;
    const unlimited = Boolean(v.max_loss_is_unlimited);

    // pct_of_margin arrives ALREADY as a percentage: 1.74 means 1.74%.
    const pctNote = (x) => (typeof x.pct_of_margin === 'number' ? ` · ${x.pct_of_margin.toFixed(2)}% of margin` : '');

    const rule1 = this._rule(
      typeof rr.loss_inr === 'number' ? (rr.passed ? 'pass' : 'fail') : 'idle',
      '1 · Running loss',
      typeof rr.loss_inr === 'number' ? inr(rr.loss_inr) : null,
      typeof rr.cap_inr === 'number' ? `of ${inr(rr.cap_inr)}${pctNote(rr)}` : 'cap unavailable',
    );

    // Rule 2 is worded as a hypothetical, "if you carry this overnight", so it
    // is never read as something that already happened.
    const rule2 = carry
      ? this._rule(
          carry.hedged === false || typeof carry.gap_loss_inr !== 'number' ? 'fail' : carry.may_carry_overnight ? 'pass' : 'fail',
          '2 · Overnight gap',
          carry.hedged === false ? 'Unlimited' : typeof carry.gap_loss_inr === 'number' ? inr(carry.gap_loss_inr) : null,
          carry.hedged === false
            ? 'if you carry this overnight: not hedged, cannot carry'
            : typeof carry.cap_inr === 'number'
              ? `if you carry this overnight · of ${inr(carry.cap_inr)}`
              : 'if you carry this overnight · cap unavailable',
        )
      : this._rule(
          'idle',
          '2 · Overnight gap',
          null,
          this.carry !== 'overnight'
            ? 'not tested — you are closing before the bell'
            : !this.nextTradingDay
              ? 'not tested — the next trading day is unknown'
              : intraday
                ? 'not tested — the server treated this as intraday'
                : 'the gap test needs measured daily moves',
        );

    const rule3 = this._rule(
      unlimited ? 'fail' : typeof blast.loss_inr === 'number' ? (blast.passed ? 'pass' : 'fail') : 'idle',
      '3 · Black swan',
      unlimited ? 'Unlimited' : typeof blast.loss_inr === 'number' ? inr(blast.loss_inr) : null,
      unlimited
        ? 'no ceiling at expiry'
        : typeof blast.cap_inr === 'number'
          ? `of ${inr(blast.cap_inr)}${pctNote(blast)}`
          : 'cap unavailable',
    );

    host.innerHTML = rule1 + rule2 + rule3 + this._rule4();

    if (why) {
      const parts = [];
      if (typeof rr.loss_inr === 'number' && typeof rr.cap_inr === 'number') {
        parts.push(`Rule 1: the worse of a two-sigma day either way is ${inr(rr.loss_inr)}, against 1% of your balance, ${inr(rr.cap_inr)}.`);
      }
      if (carry && carry.arithmetic) parts.push(`Rule 2: ${carry.arithmetic}`);
      else if (carry && carry.move) {
        parts.push(`Rule 2: NIFTY gaps ${carry.move.gap_tested_points} points either way, twice your ${carry.move.average_daily_move_points}-point average over ${carry.move.sessions_used} sessions, held to the next session.`);
      }
      if (carry && carry.reasons && carry.reasons.length) parts.push(carry.reasons.join(' '));
      // The server still carries an advisory reward-to-risk check from the
      // rule set he deleted on 2026-09-07. Its arithmetic is off-limits in this
      // round, so the page drops that one line rather than print a rule that
      // no longer exists. Everything else the server says is shown verbatim.
      (v.warnings || []).forEach((w) => parts.push(stripDeletedRules(w)));
      why.textContent = parts.filter(Boolean).join(' ');
    }
  }

  /**
   * Rule 4, the deployable margin ceiling. Margin needed for this structure
   * (the broker's number from the preview) plus margin already used, against
   * the ceiling of twice the cash equivalent. Green when it fits, red with the
   * shortfall in rupees when it does not. It used to be hardcoded idle.
   */
  _rule4() {
    const need = this.preview && typeof this.preview.margin_required_inr === 'number'
      ? this.preview.margin_required_inr
      : null;
    const used = this.marginUsed;
    const cap = this.capital || (this.validation && this.validation.capital) || {};
    const ceiling = typeof cap.deployable_margin_ceiling_inr === 'number' ? cap.deployable_margin_ceiling_inr : null;

    if (ceiling === null) {
      return this._rule('idle', '4 · Margin ceiling', null,
        cap.ceiling_unavailable_reason || 'the ceiling needs the cash-equivalent figure');
    }
    if (need === null) {
      const reason = this.previewError
        || (this.preview && this.preview.margin_unavailable_reason)
        || (this.unpricedLegs().length ? 'margin needed is unknown until every leg is priced' : 'the broker has not priced this basket');
      return this._rule('idle', '4 · Margin ceiling', inr(ceiling), `ceiling · ${reason}`);
    }
    if (used === null) {
      return this._rule('idle', '4 · Margin ceiling', inr(need), `needed · margin already used is unknown, so the ceiling of ${inr(ceiling)} cannot be tested`);
    }
    const total = need + used;
    const fits = total <= ceiling;
    return this._rule(
      fits ? 'pass' : 'fail',
      '4 · Margin ceiling',
      inr(total),
      fits
        ? `of ${inr(ceiling)} · ${inr(ceiling - total)} free after this`
        : `SHORT BY ${inr(total - ceiling)} · ceiling ${inr(ceiling)}`,
    );
  }

  renderExecute() {
    const banner = this.container.querySelector('#entry-banner');
    if (banner) {
      banner.innerHTML = this.activeLegs().length
        ? '<b>Intraday entry is never blocked</b>, including a naked or half-built structure. Only carrying overnight is gated, and only on two conditions: hedged, and inside the 2% gap test.'
        : 'Load a strategy on the left to see every number recalculate.';
    }

    const host = this.container.querySelector('#execute-row-mount');
    if (!host) return;

    const v = this.validation;
    const carry = v && v.carry;
    let cls = 'v-warn';
    let text = 'Intraday ok · overnight not assessed yet';
    if (carry && carry.may_carry_overnight) {
      cls = 'v-ok';
      text = 'Intraday ok · may carry overnight';
    } else if (carry) {
      cls = 'v-warn';
      text = 'Intraday ok · must close before the bell';
    } else if (this.carry !== 'overnight') {
      cls = 'v-ok';
      text = 'Intraday ok · closing today, overnight not tested';
    }

    const blocked = v && v.execution_blocked_reason ? v.execution_blocked_reason : null;
    const hasLegs = this.activeLegs().length > 0;
    const priced = this.fullyPriced();

    host.innerHTML =
      (this.safetyWarning
        ? `<div style="flex-basis:100%;color:var(--down);font-size:12px">${escapeHtml(this.safetyWarning)}</div>`
        : '') +
      `<span class="verdict ${cls}">${escapeHtml(text)}</span>` +
      `<button class="btn pri" id="btn-execute" type="button"${hasLegs && priced ? '' : ' disabled'}>Execute paper trade</button>` +
      `<span style="margin-left:auto;font-family:var(--m);font-size:11px;color:var(--fg-3)" id="execute-note">${escapeHtml(
        this.executeNote ||
          (!hasLegs
            ? ''
            : !priced
              ? 'every leg needs a price before this can be sent'
              : blocked || 'paper only — there is no real-money order code in this app'),
      )}</span>`;

    const btn = this.container.querySelector('#btn-execute');
    if (btn && typeof btn.addEventListener === 'function') {
      btn.addEventListener('click', () => this.executePaperTrade());
    }
  }

  async executePaperTrade() {
    const legs = this.legsPayload();
    if (!legs.length) return;
    this.executeNote = 'Sending…';
    this.renderExecute();
    try {
      const res = await api.executeMultiLeg({
        strategy_name: this.strategyName || 'Custom',
        underlying: 'NIFTY',
        current_spot: this.spot,
        order_type: 'LIMIT',
        session_id: this.sessionId,
        mode: 'paper',
        legs: legs.map((l) => ({ ...l, order_type: 'LIMIT' })),
      });
      this.executeNote = res && res.position_id
        ? `Paper position ${String(res.position_id).slice(0, 8)} opened and journalled.`
        : 'Sent. The server did not return a position id.';
      await this.refreshPositions();
    } catch (err) {
      this.executeNote = `Not executed: ${(err && err.message) || err}`;
    }
    this.renderExecute();
  }

  destroy() {
    if (this._serverTimer) {
      clearTimeout(this._serverTimer);
      this._serverTimer = null;
    }
    if (this.cronTimer) {
      clearInterval(this.cronTimer);
      this.cronTimer = null;
    }
    if (this._requoteTimer) {
      clearInterval(this._requoteTimer);
      this._requoteTimer = null;
    }
    if (this._unsubSpot) {
      this._unsubSpot();
      this._unsubSpot = null;
    }
    if (this.chainModal) {
      this.chainModal.destroy();
      this.chainModal = null;
    }
  }
}

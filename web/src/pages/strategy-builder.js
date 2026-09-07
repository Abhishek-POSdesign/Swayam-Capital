/**
 * Strategy Builder & Trading Terminal Page Controller for Swayam Capital (BUILD-10).
 *
 * Full-featured workspace uniting:
 * - Left rail: Mini Readiness, Active Trades, Today's Session Recap, Session ID
 * - Row 1: Strategy Presets Bar (with Import from AI conversation)
 * - Row 2: Multi-leg Builder (Buys first) & Live Plotly Payoff Chart
 * - Row 3: Two-tier Rule Validation Panel (Realistic 2σ & Blast Radius)
 * - Row 4: Order Type & Margin-Safe Execution Row
 * - Row 5: Full-width AI Trading Partner Conversation Surface (session continuity)
 * - Sticky Ticker: Live Spot, Total P&L, Market Timer
 * - 15:20 IST Overnight-Naked Hard-Block Modal
 */

import { api } from '../api.js';
import { PresetBarComponent, generatePresetLegs } from '../components/preset-bar.js';
import { LegBuilderComponent } from '../components/leg-builder.js';
import { PayoffChartComponent } from '../components/payoff-chart.js';
import { RuleValidationPanelComponent } from '../components/rule-validation-panel.js';
import { ExecuteRowComponent } from '../components/execute-row.js';
import { ChatSurfaceComponent } from '../components/chat-surface.js';
import { MiniReadinessCardComponent } from '../components/mini-readiness-card.js';
import { MiniPositionsListComponent } from '../components/mini-positions-list.js';
import { SessionRecapComponent } from '../components/session-recap.js';
import { OvernightBlockModalComponent } from '../components/overnight-block-modal.js';
import { ExecutionTicketComponent } from '../components/execution-ticket.js';

export class StrategyBuilderPage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onNavigateHome, onOpenSettings }
    this.currentSpot = 24842.65; // math fallback only — NEVER displayed as the live spot
    this.spotIsLive = false;
    this.sessionId = this._resolveSessionId();
    this.strategyName = 'Bear Put Spread';
    this.targetDate = null;
    this.ivShiftPct = 0;
    this.targetSpot = null;
    this.isRailCollapsed = false;

    // Sub-components
    this.presetBar = null;
    this.legBuilder = null;
    this.payoffChart = null;
    this.validationPanel = null;
    this.executeRow = null;
    this.chatSurface = null;
    this.miniReadiness = null;
    this.miniPositions = null;
    this.sessionRecap = null;
    this.overnightModal = null;
    this.executionTicket = null;

    this.cronTimer = null;
    this.lastValidationData = null;
    this.lastPreviewData = null;
  }

  _resolveSessionId() {
    try {
      const params = new URLSearchParams(window.location.search);
      const urlSession = params.get('session');
      if (urlSession) {
        localStorage.setItem('swayam_active_session_id', urlSession);
        return urlSession;
      }
      const stored = localStorage.getItem('swayam_active_session_id');
      if (stored) return stored;
    } catch (_) {}
    return null;
  }

  async init() {
    this.renderLayout();
    this.initSubComponents();
    await this.loadInitialData();
    this.startOvernightCronCheck();

    // Restore rail collapsed state if previously set
    const storedRail = localStorage.getItem('swayam_strategy_rail_collapsed') === 'true';
    if (storedRail) {
      this.toggleRail(true);
    }
  }

  toggleRail(forceState) {
    const rail = this.container.querySelector('#strategy-left-rail');
    const toggleBtn = this.container.querySelector('#btn-toggle-rail');
    if (!rail) return;

    this.isRailCollapsed = forceState !== undefined ? forceState : !this.isRailCollapsed;
    rail.classList.toggle('rail-collapsed', this.isRailCollapsed);

    if (this.isRailCollapsed) {
      if (toggleBtn) toggleBtn.textContent = '›';
      localStorage.setItem('swayam_strategy_rail_collapsed', 'true');
    } else {
      if (toggleBtn) toggleBtn.textContent = '‹';
      localStorage.setItem('swayam_strategy_rail_collapsed', 'false');
    }
  }

  renderLayout() {
    const shortSid = this.sessionId ? this.sessionId.slice(0, 8) : 'new';

    this.container.innerHTML = `
      <div id="strategy-builder-layout" class="swayam-layout" style="display: flex; min-height: calc(100vh - var(--header-h, 56px)); transition: margin-right 0.25s cubic-bezier(0.16, 1, 0.3, 1);">
        <!-- LEFT SIDEBAR RAIL (Atlas design system, collapsible) -->
        <aside id="strategy-left-rail" style="
          flex: 0 0 320px;
          width: 320px;
          background: var(--dl-rail);
          border-right: 1px solid var(--dl-line);
          display: flex;
          flex-direction: column;
          padding: 20px 16px;
          gap: 16px;
          min-height: 100%;
          transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        ">
          <!-- Rail Top Header: Back to Home + Collapse Chevron -->
          <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
            <button
              type="button"
              id="btn-back-to-home"
              style="
                display: flex;
                align-items: center;
                gap: 6px;
                background: transparent;
                border: none;
                color: var(--dl-fg-2);
                font-size: 0.82rem;
                font-weight: 600;
                cursor: pointer;
                padding: 4px 6px;
                border-radius: 6px;
                width: fit-content;
                transition: color var(--dur-fast) ease;
              "
              onmouseover="this.style.color='var(--dl-fg)'"
              onmouseout="this.style.color='var(--dl-fg-2)'"
            >
              <span id="btn-back-to-home-icon">←</span>
              <span class="rail-text-label">Back to Home</span>
            </button>

            <button
              type="button"
              id="btn-toggle-rail"
              title="Collapse/Expand left rail"
              style="
                background: transparent;
                border: 1px solid var(--dl-line);
                color: var(--dl-fg-2);
                border-radius: 4px;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.82rem;
                cursor: pointer;
                transition: all var(--dur-fast) ease;
              "
              onmouseover="this.style.color='var(--dl-fg)'; this.style.borderColor='var(--dl-fg-3)';"
              onmouseout="this.style.color='var(--dl-fg-2)'; this.style.borderColor='var(--dl-line)';"
            >
              ‹
            </button>
          </div>

          <!-- Rail Full Content (Hidden when collapsed) -->
          <div class="rail-full-content" style="display: flex; flex-direction: column; gap: 16px; flex: 1;">
            <!-- Mini Readiness Status -->
            <div id="rail-mini-readiness"></div>

            <!-- Mini Active Positions -->
            <div id="rail-mini-positions"></div>

            <!-- Today's Session Recap -->
            <div id="rail-session-recap"></div>

            <!-- Sticky Rail Footer -->
            <div style="margin-top: auto; padding-top: 18px; border-top: 1px solid var(--dl-line); display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; color: var(--dl-fg-3);">
              <span style="font-family: var(--font-mono);">Sess: #${shortSid}</span>
              <span style="color: var(--accent-sage);">Paper Mode</span>
            </div>
          </div>
        </aside>

        <!-- MAIN CONTENT AREA (Flex 1) -->
        <main class="strategy-main" style="
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding: 18px 24px 70px 20px;
        ">
          <!-- Page Header -->
          <div style="display: flex; justify-content: space-between; align-items: baseline;">
            <div>
              <h1 style="font-family: var(--font-serif); font-size: 1.5rem; font-weight: 500; color: var(--dl-fg); margin: 0;">
                Strategy Builder &amp; Terminal
              </h1>
              <div style="font-size: 0.8rem; color: var(--dl-fg-3); margin-top: 2px;">
                Construct, model Greeks &amp; execute margin-safe multi-leg options structures
              </div>
            </div>
            <div id="strategy-spot-display" class="mono-nums" style="font-size: 0.95rem; font-weight: 700; color: var(--accent-sage);">
              NIFTY 50: <span style="color: var(--dl-fg-3);">—</span>
            </div>
          </div>

          <!-- Safety Critical Warning Banner (Shown if database is unreachable) -->
          <div id="safety-warning-banner-mount" style="display: none; width: 100%;"></div>

          <!-- Row 1: Strategy Presets Bar -->
          <div id="strategy-presets-container" class="span-12"></div>

          <!-- Row 2: Multi-leg Builder + Payoff Chart (Stacked full-width bands) -->
          <div class="builder-chart-grid" style="display: flex; flex-direction: column; gap: 16px; width: 100%;">
            <div id="leg-builder-mount" style="width: 100%;"></div>
            <div id="payoff-chart-mount" style="width: 100%;"></div>
          </div>

          <!-- Row 3: Rule Validation Panel (span-12) -->
          <div id="rule-validation-mount" class="span-12"></div>

          <!-- Row 4: Execute Row (span-12) -->
          <div id="execute-row-mount" class="span-12"></div>
        </main>
      </div>

      <!-- Sticky Bottom Status Ticker (40px) -->
      <footer id="strategy-sticky-ticker" style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 40px;
        background: var(--dl-card);
        border-top: 1px solid var(--dl-line);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 24px;
        font-size: 0.78rem;
        z-index: 900;
        font-family: var(--font-mono);
      ">
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="color: var(--dl-fg-3);">NIFTY SPOT:</span>
          <span id="ticker-spot-val" style="color: var(--dl-fg-3); font-weight: 700;">—</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="color: var(--dl-fg-3);">TODAY'S P&amp;L:</span>
          <span id="ticker-pnl-val" style="color: var(--accent-sage); font-weight: 700;">+₹0.00</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="color: var(--accent-amber);">MARKET STATUS:</span>
          <span id="ticker-market-status" style="color: var(--dl-fg-3);">—</span>
        </div>
      </footer>

      <!-- Overnight Naked Auto-Block Modal Mount -->
      <div id="overnight-modal-container"></div>

      <!-- Execution Ticket Modal Mount -->
      <div id="execution-ticket-container"></div>
    `;

    // Hook Back to Home button
    const btnHome = this.container.querySelector('#btn-back-to-home');
    if (btnHome) {
      btnHome.addEventListener('click', () => {
        if (this.options.onNavigateHome) {
          this.options.onNavigateHome();
        }
      });
    }

    // Hook Collapsible Rail Toggle Button
    const btnToggle = this.container.querySelector('#btn-toggle-rail');
    if (btnToggle) {
      btnToggle.addEventListener('click', () => this.toggleRail());
    }
  }

  async handleSliderChange({ targetDays, targetDate, ivShiftPct, targetSpot }) {
    // Sliders now recompute for real (this used to call a method that didn't exist, so
    // dragging did nothing). Route through the same live compute+validate path as leg edits.
    this.targetDate = targetDate;
    this.ivShiftPct = ivShiftPct;
    if (targetSpot !== undefined) this.targetSpot = targetSpot;
    const legs = this.legBuilder?.getLegs() || [];
    if (legs.length) await this.handleLegsChanged(legs);
  }

  initSubComponents() {
    // 1. Preset Bar
    const presetMount = this.container.querySelector('#strategy-presets-container');
    if (presetMount) {
      this.presetBar = new PresetBarComponent(presetMount, {
        currentSpot: this.currentSpot,
        onSelectPreset: (name, presetId) => this.handlePresetSelected(name, presetId),
        onImportAI: () => this.handleImportFromAI(),
      });
      this.presetBar.render();
    }

    // 2. Leg Builder
    const builderMount = this.container.querySelector('#leg-builder-mount');
    if (builderMount) {
      this.legBuilder = new LegBuilderComponent(builderMount, {
        currentSpot: this.currentSpot,
        onLegsUpdated: (legs) => this.handleLegsChanged(legs),
      });
    }

    // 3. Payoff Chart
    const chartMount = this.container.querySelector('#payoff-chart-mount');
    if (chartMount) {
      this.payoffChart = new PayoffChartComponent(chartMount, {
        onSliderChange: (params) => this.handleSliderChange(params),
      });
      this.payoffChart.init();
    }

    // 4. Rule Validation Panel
    const valMount = this.container.querySelector('#rule-validation-mount');
    if (valMount) {
      this.validationPanel = new RuleValidationPanelComponent(valMount);
      this.validationPanel.render();
    }

    // 5. Execute Row → opens the Execution Ticket (per-leg Market/Limit + price + margin)
    const execMount = this.container.querySelector('#execute-row-mount');
    if (execMount) {
      this.executeRow = new ExecuteRowComponent(execMount, {
        onExecute: () => this.openExecutionTicket(),
        onPreviewSequence: () => this.openExecutionTicket(),
      });
      this.executeRow.render(false);
    }

    // 5b. Execution Ticket modal
    const ticketMount = this.container.querySelector('#execution-ticket-container');
    if (ticketMount) {
      this.executionTicket = new ExecutionTicketComponent(ticketMount, {
        onConfirm: (legs) => this.confirmExecute(legs),
      });
    }

    // 6. Left Rail Mini Components
    const miniReadinessMount = this.container.querySelector('#rail-mini-readiness');
    if (miniReadinessMount) {
      this.miniReadiness = new MiniReadinessCardComponent(miniReadinessMount);
      this.miniReadiness.render();
    }

    const miniPosMount = this.container.querySelector('#rail-mini-positions');
    if (miniPosMount) {
      this.miniPositions = new MiniPositionsListComponent(miniPosMount, {
        onSelectPosition: (pos) => console.log('Selected position:', pos),
      });
      this.miniPositions.render([]);
    }

    const recapMount = this.container.querySelector('#rail-session-recap');
    if (recapMount) {
      this.sessionRecap = new SessionRecapComponent(recapMount);
      this.sessionRecap.render();
    }

    // 8. Overnight Modal
    const modalMount = this.container.querySelector('#overnight-modal-container');
    if (modalMount) {
      this.overnightModal = new OvernightBlockModalComponent(modalMount, {
        onAddHedge: (violation) => this.resolveAddHedge(violation),
        onExitPosition: (violation) => this.resolveExitPosition(violation),
      });
    }
  }

  async loadInitialData() {
    // 1. Spot fetch — show the REAL spot or an honest '—' (never the hardcoded default).
    try {
      const spotRes = await api.getNiftySpot();
      if (spotRes && spotRes.spot) {
        this.currentSpot = spotRes.spot;
        this.spotIsLive = true;
        if (this.legBuilder) this.legBuilder.options.currentSpot = this.currentSpot;
      }
    } catch (_) {
      this.spotIsLive = false;
    }
    this._updateSpotDisplay();
    this._updateMarketStatus();

    // 2. Load default Bear Put Spread legs — ONLY with a real spot, so strikes are at-the-money.
    if (this.spotIsLive) {
      const initialLegs = generatePresetLegs('bear-put', this.currentSpot);
      if (this.legBuilder) {
        this.legBuilder.setLegs(initialLegs);
      }
    } else if (this.legBuilder) {
      this.legBuilder.setLegs([]); // never seed far-OTM strikes off the fallback spot
      this._toast('Live NIFTY price unavailable — pick a strategy once the spot is live so strikes land at-the-money. Refresh your FYERS session if this persists.');
    }

    // 3. Load active positions
    await this.refreshPositions();

    // 4. Load session recap from AI endpoint
    if (this.sessionId) {
      try {
        const summary = await api.getSessionContextSummary(this.sessionId);
        if (summary && this.sessionRecap) {
          this.sessionRecap.render(summary);
        }
      } catch (_) {}
    }

    // 5. Load readiness mini status
    try {
      const readRes = await api.getTodayReadiness();
      if (readRes && this.miniReadiness) {
        this.miniReadiness.render(readRes);
      }
    } catch (_) {}
  }

  _marketOpen() {
    // NIFTY F&O trades 09:15–15:30 IST, Mon–Fri. (Public-holiday calendar not applied here.)
    const now = new Date();
    const istMs = now.getTime() + now.getTimezoneOffset() * 60000 + 5.5 * 3600000;
    const ist = new Date(istMs);
    const day = ist.getDay();
    if (day === 0 || day === 6) return false;
    const mins = ist.getHours() * 60 + ist.getMinutes();
    return mins >= 9 * 60 + 15 && mins <= 15 * 60 + 30;
  }

  _updateMarketStatus() {
    const el = this.container.querySelector('#ticker-market-status');
    if (!el) return;
    const open = this._marketOpen();
    el.textContent = open ? 'OPEN · 09:15–15:30 IST' : 'CLOSED';
    el.style.color = open ? 'var(--accent-sage)' : 'var(--dl-fg-3)';
  }

  _updateSpotDisplay() {
    const spotEl = this.container.querySelector('#strategy-spot-display');
    const tickerSpot = this.container.querySelector('#ticker-spot-val');
    if (this.spotIsLive) {
      const val = this.currentSpot.toLocaleString('en-IN', { minimumFractionDigits: 2 });
      if (spotEl) spotEl.innerHTML = `NIFTY 50: ${val} <span style="font-size:0.6rem; color:var(--accent-sage); font-weight:700; letter-spacing:0.05em;">LIVE</span>`;
      if (tickerSpot) {
        tickerSpot.textContent = this.currentSpot.toFixed(2);
        tickerSpot.style.color = 'var(--accent-sage)';
      }
    } else {
      if (spotEl) spotEl.innerHTML = `NIFTY 50: <span style="color:var(--dl-fg-3);">— no live price</span>`;
      if (tickerSpot) {
        tickerSpot.textContent = '—';
        tickerSpot.style.color = 'var(--dl-fg-3)';
      }
    }
  }

  async refreshPositions() {
    try {
      const positions = await api.getPositions('open');
      if (Array.isArray(positions)) {
        if (this.miniPositions) this.miniPositions.render(positions);

        // Update ticker P&L
        let totalPnl = 0;
        positions.forEach((p) => { totalPnl += (p.unrealized_pnl_inr || 0); });
        const tickerPnl = this.container.querySelector('#ticker-pnl-val');
        if (tickerPnl) {
          const isPos = totalPnl >= 0;
          tickerPnl.textContent = `${isPos ? '+' : ''}₹${Math.round(totalPnl).toLocaleString('en-IN')}`;
          tickerPnl.style.color = isPos ? 'var(--accent-sage)' : 'var(--accent-coral)';
        }
      }
    } catch (err) {
      if (this.miniPositions) {
        this.miniPositions.renderError('Positions unavailable — Supabase unreachable. Check broker terminal.');
      }
    }
  }

  async handlePresetSelected(name, presetId) {
    this.strategyName = name;
    await this._ensureLiveSpot();
    if (!this.spotIsLive) {
      this._toast("Live NIFTY price unavailable — refresh your FYERS session. Strikes need the real spot; I won't place far-OTM guesses.");
      return; // never build strikes off the fallback spot
    }
    const legs = generatePresetLegs(presetId, this.currentSpot);
    if (this.legBuilder) {
      this.legBuilder.setLegs(legs);
    }
  }

  /** Re-fetch the real spot on demand (e.g. right before building strikes). Never invents one. */
  async _ensureLiveSpot() {
    if (this.spotIsLive) return;
    try {
      const spotRes = await api.getNiftySpot();
      if (spotRes && spotRes.spot) {
        this.currentSpot = spotRes.spot;
        this.spotIsLive = true;
        if (this.legBuilder) this.legBuilder.options.currentSpot = this.currentSpot;
        this._updateSpotDisplay();
        this._updateMarketStatus();
      }
    } catch (_) {
      /* stays not-live; caller shows an honest message */
    }
  }

  /** Transient bottom-center notice (used when strikes can't be placed without a real spot). */
  _toast(msg) {
    let t = this.container.querySelector('#sb-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'sb-toast';
      t.style.cssText = 'position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:var(--dl-card); color:var(--accent-coral); border:1px solid var(--accent-coral); padding:10px 18px; border-radius:8px; font-size:0.85rem; font-weight:600; box-shadow:0 8px 24px rgba(0,0,0,0.4); z-index:2000; max-width:90vw; text-align:center;';
      this.container.appendChild(t);
    }
    t.textContent = msg;
    t.style.display = 'block';
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { if (t) t.style.display = 'none'; }, 6000);
  }

  async handleImportFromAI() {
    if (!this.sessionId) return;
    try {
      const summary = await api.getSessionContextSummary(this.sessionId);
      if (summary && summary.bullets) {
        // Build from the LIVE spot via the gated path (no far-OTM guesses off a fallback spot).
        await this.handlePresetSelected('Bear Put Spread (AI Suggested)', 'bear-put');
        if (this.chatSurface) {
          this.chatSurface.appendSystemNotice('Imported strategy structure recommended in Home AI dialogue.');
        }
      }
    } catch (e) {
      console.warn('Could not import from AI:', e);
    }
  }

  async handleLegsChanged(legs) {
    if (!legs || legs.length === 0) return;

    // Check if any short leg is unhedged
    const soldCalls = legs.filter((l) => l.direction?.toLowerCase() === 'sell' && l.option_type === 'CE');
    const boughtCalls = legs.filter((l) => l.direction?.toLowerCase() === 'buy' && l.option_type === 'CE');
    const soldPuts = legs.filter((l) => l.direction?.toLowerCase() === 'sell' && l.option_type === 'PE');
    const boughtPuts = legs.filter((l) => l.direction?.toLowerCase() === 'buy' && l.option_type === 'PE');

    const totalSoldCalls = soldCalls.reduce((s, l) => s + (l.quantity_lots || 1), 0);
    const totalBoughtCalls = boughtCalls.reduce((s, l) => s + (l.quantity_lots || 1), 0);
    const totalSoldPuts = soldPuts.reduce((s, l) => s + (l.quantity_lots || 1), 0);
    const totalBoughtPuts = boughtPuts.reduce((s, l) => s + (l.quantity_lots || 1), 0);

    const hasNaked = totalSoldCalls > totalBoughtCalls || totalSoldPuts > totalBoughtPuts;

    // 1. Preview order sequence and margin
    try {
      const previewRes = await api.previewOrder({
        underlying: 'NIFTY',
        current_spot: this.currentSpot,
        legs: legs.map((l) => ({
          strike: l.strike,
          option_type: l.option_type,
          direction: l.direction,
          quantity_lots: l.quantity_lots || 1,
          lot_size: l.lot_size || 75,
          entry_premium: l.entry_premium || 0,
          expiry_date: l.expiry_date,
        })),
      });
      this.lastPreviewData = previewRes;
    } catch (_) {}

    // 2. Compute payoff curve
    try {
      const computePayload = {
        strategy_name: this.strategyName,
        underlying: 'NIFTY',
        current_spot: this.currentSpot,
        iv_per_leg: {},
        legs: legs.map((l) => ({
          strike: l.strike,
          option_type: l.option_type,
          direction: l.direction,
          quantity_lots: l.quantity_lots || 1,
          lot_size: l.lot_size || 75,
          entry_premium: l.entry_premium || 0,
          expiry_date: l.expiry_date,
        })),
      };

      if (this.targetDate) {
        computePayload.target_date = this.targetDate;
      }
      if (this.ivShiftPct !== 0) {
        computePayload.iv_shift_pct = this.ivShiftPct;
      }
      if (this.targetSpot) {
        computePayload.target_spot = this.targetSpot;
      }

      const computeRes = await api.computeStrategy(computePayload);

      if (computeRes && (computeRes.payoff_curve_expiry || computeRes.payoff_curve)) {
        const curveExpiry = computeRes.payoff_curve_expiry || computeRes.payoff_curve;
        const curveTarget = computeRes.payoff_curve_target || computeRes.payoff_curve;
        const expiryDate = legs[0]?.expiry_date;
        if (this.payoffChart) {
          this.payoffChart.updateData({
            curveData: curveTarget,
            curveExpiry,
            curveTarget,
            currentSpot: this.currentSpot,
            maxLoss: curveExpiry.max_loss_inr,
            maxProfit: curveExpiry.max_profit_inr,
            breakevens: curveExpiry.breakevens,
            // Single source of truth: the 2-sigma "realistic risk" line uses the REAL number
            // from validation (set via setRealisticRisk below), not a max_loss*0.8 fudge.
            realisticRisk: this.lastValidationData?.realistic_risk?.loss_inr ?? null,
            projectedPnl: computeRes.projected_pnl_target_inr ?? null,
            projectedPnlPct: computeRes.projected_pnl_target_pct ?? null,
            greeks: computeRes.greeks,
            pop: computeRes.pop ?? computeRes.greeks?.pop,
            expiryDate,
          });
        }
        if (this.legBuilder && (computeRes.per_leg || computeRes.greeks?.per_leg)) {
          this.legBuilder.updateGreeks(computeRes.per_leg || computeRes.greeks?.per_leg);
        }
      }
    } catch (_) {}

    // 3. Validate rules
    try {
      const valRes = await api.validateStrategy({
        strategy_name: this.strategyName,
        underlying: 'NIFTY',
        current_spot: this.currentSpot,
        iv_per_leg: {},
        legs: legs.map((l) => ({
          strike: l.strike,
          option_type: l.option_type,
          direction: l.direction,
          quantity_lots: l.quantity_lots || 1,
          lot_size: l.lot_size || 75,
          entry_premium: l.entry_premium || 0,
          expiry_date: l.expiry_date,
        })),
      });

      this.lastValidationData = valRes;
      if (this.validationPanel) {
        this.validationPanel.render(valRes, hasNaked);
      }
      // Feed the REAL 2-sigma realistic-risk number to the chart's risk line (single source).
      if (this.payoffChart && valRes.realistic_risk) {
        this.payoffChart.setRealisticRisk(valRes.realistic_risk.loss_inr);
      }

      const canExecute = (valRes.passed || valRes.overall_passed) && !hasNaked;
      if (this.executeRow) {
        this.executeRow.render(canExecute, this.lastPreviewData);
      }
    } catch (_) {}
  }

  openExecutionTicket() {
    const legs = this.legBuilder?.getLegs() || [];
    if (!legs.length) return;
    this.executionTicket?.open({
      legs,
      preview: this.lastPreviewData,
      verdict: this.lastValidationData,
    });
  }

  async confirmExecute(legs) {
    const payload = {
      strategy_name: this.strategyName,
      underlying: 'NIFTY',
      current_spot: this.currentSpot,
      order_type: 'LIMIT',
      session_id: this.sessionId,
      mode: 'paper',
      legs: legs.map((l) => ({
        strike: l.strike,
        option_type: l.option_type,
        direction: l.direction,
        quantity_lots: l.quantity_lots || 1,
        lot_size: l.lot_size || 75,
        entry_premium: l.entry_premium || 0,
        expiry_date: l.expiry_date,
        order_type: l.order_type || 'LIMIT',
      })),
    };
    // api.executeMultiLeg throws on failure -> the ticket surfaces the error inline (no alert()).
    const res = await api.executeMultiLeg(payload);
    if (res && res.status === 'opened') {
      await this.refreshPositions();
      this.executionTicket?.showSuccess(`Position #${res.position_id.slice(0, 8)} opened · journal recorded.`);
    } else {
      throw new Error(res?.detail || 'Unexpected response from execution.');
    }
  }

  _showSafetyWarningBanner(message) {
    const banner = this.container.querySelector('#safety-warning-banner-mount');
    if (banner) {
      banner.innerHTML = `
        <div style="background: rgba(221, 129, 112, 0.15); border: 1px solid var(--accent-coral); border-radius: var(--radius-card); padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 0.82rem; color: var(--accent-coral);">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1rem;">⚠️</span>
            <span style="font-weight: 500;">${message}</span>
          </div>
        </div>
      `;
      banner.style.display = 'block';
    }
  }

  _clearSafetyWarningBanner() {
    const banner = this.container.querySelector('#safety-warning-banner-mount');
    if (banner) {
      banner.innerHTML = '';
      banner.style.display = 'none';
    }
  }

  startOvernightCronCheck() {
    // Check every 30 seconds if open positions have naked shorts
    this.cronTimer = setInterval(async () => {
      try {
        const res = await api.detectNakedShorts('15:20');
        this._clearSafetyWarningBanner();
        if (res && res.has_naked_shorts && res.violations && res.violations.length > 0) {
          if (this.overnightModal && !this.overnightModal.isOpen) {
            this.overnightModal.show(res.violations[0]);
          }
        }
      } catch (err) {
        this._showSafetyWarningBanner(
          'Overnight-naked safety check unavailable — Supabase unreachable. Inspect open positions manually before market close.'
        );
      }
    }, 30000);
    if (this.cronTimer && typeof this.cronTimer.unref === 'function') {
      this.cronTimer.unref();
    }
  }

  resolveAddHedge(violation) {
    if (!violation || !violation.suggested_hedges || violation.suggested_hedges.length === 0) return;
    const h = violation.suggested_hedges[0];
    const currentLegs = this.legBuilder.getLegs();
    currentLegs.push({
      strike: h.strike,
      option_type: h.option_type,
      direction: 'buy',
      quantity_lots: h.quantity_lots || 1,
      lot_size: 75,
      expiry_date: h.expiry_date,
      entry_premium: 35.0,
    });
    this.legBuilder.setLegs(currentLegs);
  }

  async resolveExitPosition(violation) {
    if (!violation || !violation.position_id) return;
    try {
      await api.closePosition(violation.position_id, {
        close_reason: 'time_exit',
        notes: 'Exited before 15:20 IST cutoff to comply with § 10a overnight naked rule.',
      });
      alert(`Position #${violation.position_id.slice(0, 8)} exited successfully.`);
      await this.refreshPositions();
    } catch (err) {
      alert(`Could not close position: ${err.message || err}`);
    }
  }

  destroy() {
    if (this.cronTimer) {
      clearInterval(this.cronTimer);
      this.cronTimer = null;
    }
  }
}

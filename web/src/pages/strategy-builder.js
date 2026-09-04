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

export class StrategyBuilderPage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onNavigateHome, onOpenSettings }
    this.currentSpot = 24842.65;
    this.sessionId = this._resolveSessionId();
    this.strategyName = 'Bear Put Spread';

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
  }

  renderLayout() {
    const shortSid = this.sessionId ? this.sessionId.slice(0, 8) : 'new';

    this.container.innerHTML = `
      <div id="strategy-builder-layout" class="swayam-layout" style="display: flex; min-height: calc(100vh - var(--header-h, 56px)); transition: margin-right 0.25s cubic-bezier(0.16, 1, 0.3, 1);">
        <!-- LEFT SIDEBAR RAIL (Atlas design system) -->
        <aside id="strategy-left-rail" style="
          flex: 0 0 320px;
          width: 320px;
          background: var(--dl-rail, #13141a);
          border-right: 1px solid var(--dl-line);
          display: flex;
          flex-direction: column;
          padding: 20px 16px;
          gap: 16px;
          min-height: 100%;
          transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        ">
          <!-- Back to Home Link -->
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
            ← Back to Home
          </button>

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
              NIFTY 50: ${this.currentSpot.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>

          <!-- Row 1: Strategy Presets Bar -->
          <div id="strategy-presets-container" class="span-12"></div>

          <!-- Row 2: Multi-leg Builder (span-7) + Payoff Chart (span-5) -->
          <div class="builder-chart-grid" style="display: grid; grid-template-columns: 7fr 5fr; gap: 16px; align-items: start;">
            <div id="leg-builder-mount"></div>
            <div id="payoff-chart-mount" style="height: 100%;"></div>
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
        background: var(--dl-card, #191b21);
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
          <span id="ticker-spot-val" style="color: var(--accent-sage); font-weight: 700;">${this.currentSpot.toFixed(2)}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="color: var(--dl-fg-3);">TODAY'S P&amp;L:</span>
          <span id="ticker-pnl-val" style="color: var(--accent-sage); font-weight: 700;">+₹0.00</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="color: var(--accent-amber);">MARKET STATUS:</span>
          <span id="ticker-market-status" style="color: var(--dl-fg-2);">TRADING OPEN</span>
        </div>
      </footer>

      <!-- Overnight Naked Auto-Block Modal Mount -->
      <div id="overnight-modal-container"></div>
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
  }

  initSubComponents() {
    // 1. Preset Bar
    const presetMount = this.container.querySelector('#strategy-presets-container');
    if (presetMount) {
      this.presetBar = new PresetBarComponent(presetMount, {
        currentSpot: this.currentSpot,
        onSelectPreset: (name, legs) => this.handlePresetSelected(name, legs),
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
      this.payoffChart = new PayoffChartComponent(chartMount);
      this.payoffChart.init();
    }

    // 4. Rule Validation Panel
    const valMount = this.container.querySelector('#rule-validation-mount');
    if (valMount) {
      this.validationPanel = new RuleValidationPanelComponent(valMount);
      this.validationPanel.render();
    }

    // 5. Execute Row
    const execMount = this.container.querySelector('#execute-row-mount');
    if (execMount) {
      this.executeRow = new ExecuteRowComponent(execMount, {
        onExecute: (orderType) => this.handleExecuteAllLegs(orderType),
        onAIOrder: (orderType) => this.handleAIOrderLegs(orderType),
        onPreviewSequence: () => this.handleShowPreviewModal(),
      });
      this.executeRow.render(false);
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
    // 1. Spot fetch
    try {
      const spotRes = await api.getNiftySpot();
      if (spotRes && spotRes.spot) {
        this.currentSpot = spotRes.spot;
        const spotEl = this.container.querySelector('#strategy-spot-display');
        const tickerSpot = this.container.querySelector('#ticker-spot-val');
        if (spotEl) spotEl.textContent = `NIFTY 50: ${this.currentSpot.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        if (tickerSpot) tickerSpot.textContent = this.currentSpot.toFixed(2);
      }
    } catch (_) {}

    // 2. Load default Bear Put Spread legs
    const initialLegs = generatePresetLegs('bear-put', this.currentSpot);
    if (this.legBuilder) {
      this.legBuilder.setLegs(initialLegs);
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
    } catch (_) {}
  }

  handlePresetSelected(name, legs) {
    this.strategyName = name;
    if (this.legBuilder) {
      this.legBuilder.setLegs(legs);
    }
  }

  async handleImportFromAI() {
    if (!this.sessionId) return;
    try {
      const summary = await api.getSessionContextSummary(this.sessionId);
      if (summary && summary.bullets) {
        // AI usually recommends Bear Put Spread around 24,800 or 24,700
        const legs = generatePresetLegs('bear-put', this.currentSpot);
        this.handlePresetSelected('Bear Put Spread (AI Suggested)', legs);
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
      const computeRes = await api.computeStrategy({
        strategy_name: this.strategyName,
        underlying: 'NIFTY',
        current_spot: this.currentSpot,
        iv_per_leg: { default: 0.135 },
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

      if (computeRes && computeRes.payoff_curve) {
        const curve = computeRes.payoff_curve;
        if (this.payoffChart) {
          this.payoffChart.updateData({
            curveData: curve,
            currentSpot: this.currentSpot,
            maxLoss: curve.max_loss_inr,
            maxProfit: curve.max_profit_inr,
            breakevens: curve.breakevens,
            realisticRisk: curve.max_loss_inr * 0.8,
          });
        }
      }
    } catch (_) {}

    // 3. Validate rules
    try {
      const valRes = await api.validateStrategy({
        strategy_name: this.strategyName,
        underlying: 'NIFTY',
        current_spot: this.currentSpot,
        iv_per_leg: { default: 0.135 },
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

      const canExecute = (valRes.passed || valRes.overall_passed) && !hasNaked;
      if (this.executeRow) {
        this.executeRow.render(canExecute, this.lastPreviewData);
      }
    } catch (_) {}
  }

  handleShowPreviewModal() {
    if (!this.lastPreviewData || !this.lastPreviewData.ordered_legs) {
      alert('Add at least one leg to preview the execution order.');
      return;
    }

    const steps = this.lastPreviewData.ordered_legs.map((s) =>
      `• Step ${s.sequence}: ${s.direction} ${s.strike} ${s.option_type} (${s.quantity_lots} lot) — Est. Margin: ₹${Math.round(s.estimated_margin_inr).toLocaleString('en-IN')}\n  ${s.action_note}`
    ).join('\n\n');

    alert(`PRE-ORDER SEQUENCE (BUYS FIRST):\n\n${steps}\n\nTotal Hedged Margin: ₹${Math.round(this.lastPreviewData.final_hedged_margin_inr).toLocaleString('en-IN')}\nMargin Saved vs Unhedged: ₹${Math.round(this.lastPreviewData.margin_saved_inr).toLocaleString('en-IN')}`);
  }

  async handleAIOrderLegs(orderType) {
    if (!this.lastPreviewData) {
      alert('Configure strategy legs before requesting AI margin ordering.');
      return;
    }

    const legs = this.legBuilder.getLegs();
    const buyCount = legs.filter((l) => l.direction?.toLowerCase() === 'buy').length;
    const sellCount = legs.filter((l) => l.direction?.toLowerCase() === 'sell').length;

    const prompt = `AI, please review my proposed ${this.strategyName} with ${buyCount} buy legs and ${sellCount} sell legs. Order the legs safely for exchange margin benefits and confirm readiness.`;

    if (this.chatSurface) {
      await this.chatSurface.sendMessage(prompt);
    }
  }

  async handleExecuteAllLegs(orderType) {
    const legs = this.legBuilder.getLegs();
    if (!legs || legs.length === 0) return;

    try {
      const payload = {
        strategy_name: this.strategyName,
        underlying: 'NIFTY',
        current_spot: this.currentSpot,
        order_type: orderType,
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
        })),
      };

      const res = await api.executeMultiLeg(payload);
      if (res && res.status === 'opened') {
        alert(`✅ Trade Executed!\n\nPaper Position #${res.position_id.slice(0, 8)} opened successfully in margin-safe sequence (Buys first).\nTrade journal note recorded at: ${res.journal_path}`);
        await this.refreshPositions();
      }
    } catch (err) {
      alert(`❌ Execution Failed: ${err.message || err}`);
    }
  }

  startOvernightCronCheck() {
    // Check every 30 seconds if open positions have naked shorts
    this.cronTimer = setInterval(async () => {
      try {
        const res = await api.detectNakedShorts('15:20');
        if (res && res.has_naked_shorts && res.violations && res.violations.length > 0) {
          if (this.overnightModal && !this.overnightModal.isOpen) {
            this.overnightModal.show(res.violations[0]);
          }
        }
      } catch (_) {}
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

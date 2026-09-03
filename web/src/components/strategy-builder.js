/**
 * Strategy Builder component for Swayam Capital.
 *
 * Provides preset selection, leg editing, live payoff curve rendering,
 * real-time Method rule validation, and paper trade execution modal.
 */

import { api } from '../api.js';
import { renderPayoffChart } from '../modules/payoff-chart.js';
import { formatINR, formatNumber } from '../utils/format.js';

export class StrategyBuilder {
  constructor(container, options = {}) {
    this.container = container;
    this.onTradeExecuted = options.onTradeExecuted || (() => {});
    this.currentSpot = 24867.5;
    this.marginBase = 850000.0;
    this.strategyName = 'Bear Put Spread';
    this.expiryDate = this.getDefaultExpiry();
    this.legs = [];
    this.ivPerLeg = {};
    this.lastCalculation = null;
    this.lastValidation = null;
    this.debounceTimer = null;
  }

  getDefaultExpiry() {
    const d = new Date();
    // Default to Thursday (Indian weekly expiry)
    const day = d.getDay();
    const diff = (4 - day + 7) % 7 || 7;
    d.setDate(d.getDate() + diff);
    return d.toISOString().split('T')[0];
  }

  setSpot(spot) {
    this.currentSpot = spot;
    const spotDisplay = document.getElementById('current-spot-field');
    if (spotDisplay) spotDisplay.value = spot;
  }

  setMarginBase(base) {
    this.marginBase = base;
  }

  async init() {
    this.renderShell();
    this.attachEventListeners();
    await this.loadPreset('bear_put_spread');
  }

  renderShell() {
    this.container.innerHTML = `
      <div class="panel">
        <div class="panel-title">
          <span>STRATEGY BUILDER</span>
          <span style="font-size: 0.8rem; color: var(--text-secondary);" id="strategy-subtitle">NIFTY 50 Options</span>
        </div>

        <div class="builder-controls">
          <div class="form-group">
            <label>Strategy Preset</label>
            <select id="preset-selector">
              <option value="bear_put_spread">Bear Put Spread</option>
              <option value="bull_call_spread">Bull Call Spread</option>
              <option value="iron_condor">Iron Condor</option>
              <option value="calendar_spread">Calendar Spread</option>
              <option value="custom">Custom Spread</option>
            </select>
          </div>
          <div class="form-group">
            <label>Expiry Date</label>
            <input type="date" id="expiry-selector" value="${this.expiryDate}">
          </div>
          <div class="form-group">
            <label>Underlying Spot (₹)</label>
            <input type="number" id="current-spot-field" value="${this.currentSpot}" step="0.5">
          </div>
        </div>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Strike</th>
                <th>Type</th>
                <th>Side</th>
                <th>Lots</th>
                <th>Premium (₹)</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody id="legs-table-body">
              <!-- Rendered dynamically -->
            </tbody>
          </table>
        </div>

        <div style="margin-bottom: 1rem;">
          <button id="btn-add-leg" style="font-size: 0.8rem;">+ Add Leg</button>
        </div>

        <div id="payoff-chart-container"></div>

        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">Max Profit</div>
            <div class="metric-value text-green mono" id="metric-max-profit">₹0</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Max Loss</div>
            <div class="metric-value text-red mono" id="metric-max-loss">₹0</div>
            <div style="font-size: 0.75rem; color: var(--text-secondary);" id="metric-loss-pct">0.0% of margin</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">R:R Implied</div>
            <div class="metric-value text-amber mono" id="metric-rr">0.00</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Breakeven(s)</div>
            <div class="metric-value mono" id="metric-breakevens" style="font-size: 0.95rem;">-</div>
          </div>
        </div>

        <div class="metrics-grid" style="margin-top: 0.5rem;">
          <div class="metric-card">
            <div class="metric-label">Net Delta</div>
            <div class="metric-value mono" id="metric-delta">0.00</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Net Theta</div>
            <div class="metric-value mono" id="metric-theta">₹0/day</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Net Vega</div>
            <div class="metric-value mono" id="metric-vega">₹0 per 1% IV</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Net Premium</div>
            <div class="metric-value mono" id="metric-debit-credit">₹0</div>
          </div>
        </div>
      </div>
    `;
  }

  attachEventListeners() {
    document.getElementById('preset-selector').addEventListener('change', async (e) => {
      const preset = e.target.value;
      if (preset !== 'custom') {
        await this.loadPreset(preset);
      }
    });

    document.getElementById('expiry-selector').addEventListener('change', (e) => {
      this.expiryDate = e.target.value;
      this.legs.forEach((l) => (l.expiry_date = this.expiryDate));
      this.renderLegsTable();
      this.scheduleRecompute();
    });

    document.getElementById('current-spot-field').addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      if (val > 0) {
        this.currentSpot = val;
        this.scheduleRecompute();
      }
    });

    document.getElementById('btn-add-leg').addEventListener('click', () => {
      const baseStrike = Math.round(this.currentSpot / 50) * 50;
      this.legs.push({
        strike: baseStrike,
        option_type: 'CE',
        direction: 'buy',
        quantity_lots: 1,
        entry_premium: 100.0,
        expiry_date: this.expiryDate,
        lot_size: 75,
      });
      document.getElementById('preset-selector').value = 'custom';
      this.renderLegsTable();
      this.scheduleRecompute();
    });
  }

  async loadPreset(presetName) {
    try {
      let farExpiry = null;
      if (presetName === 'calendar_spread') {
        const d = new Date(this.expiryDate);
        d.setDate(d.getDate() + 7);
        farExpiry = d.toISOString().split('T')[0];
      }

      const res = await api.getStrategyPreset(presetName, this.expiryDate, this.currentSpot, farExpiry);
      this.strategyName = res.strategy_name;
      this.legs = res.legs.map((l) => ({
        ...l,
        entry_premium: l.entry_premium || (l.direction === 'buy' ? 180.0 : 60.0),
      }));

      this.renderLegsTable();
      await this.recomputeAndValidate();
    } catch (err) {
      console.error('Failed to load preset:', err);
    }
  }

  renderLegsTable() {
    const tbody = document.getElementById('legs-table-body');
    if (!tbody) return;

    tbody.innerHTML = this.legs
      .map((leg, idx) => {
        return `
        <tr>
          <td class="mono">${idx + 1}</td>
          <td>
            <input type="number" class="leg-input mono leg-field" data-idx="${idx}" data-field="strike" value="${leg.strike}" step="50">
          </td>
          <td>
            <select class="leg-input leg-field" data-idx="${idx}" data-field="option_type">
              <option value="CE" ${leg.option_type === 'CE' ? 'selected' : ''}>CE</option>
              <option value="PE" ${leg.option_type === 'PE' ? 'selected' : ''}>PE</option>
            </select>
          </td>
          <td>
            <select class="leg-input leg-field" data-idx="${idx}" data-field="direction">
              <option value="buy" ${leg.direction === 'buy' ? 'selected' : ''}>BUY</option>
              <option value="sell" ${leg.direction === 'sell' ? 'selected' : ''}>SELL</option>
            </select>
          </td>
          <td>
            <input type="number" class="leg-input mono leg-field" data-idx="${idx}" data-field="quantity_lots" value="${leg.quantity_lots}" min="1">
          </td>
          <td>
            <input type="number" class="leg-input mono leg-field" data-idx="${idx}" data-field="entry_premium" value="${leg.entry_premium}" step="0.5" min="0">
          </td>
          <td>
            <button class="btn-remove-leg" data-idx="${idx}" style="padding: 0.2rem 0.5rem; font-size: 0.75rem; color: var(--red);">✕</button>
          </td>
        </tr>
      `;
      })
      .join('');

    // Attach row change listeners
    tbody.querySelectorAll('.leg-field').forEach((el) => {
      el.addEventListener('change', (e) => {
        const idx = parseInt(e.target.dataset.idx);
        const field = e.target.dataset.field;
        let val = e.target.value;
        if (field === 'strike' || field === 'quantity_lots' || field === 'entry_premium') {
          val = parseFloat(val);
        }
        this.legs[idx][field] = val;
        this.scheduleRecompute();
      });
    });

    tbody.querySelectorAll('.btn-remove-leg').forEach((el) => {
      el.addEventListener('click', (e) => {
        const idx = parseInt(e.target.dataset.idx);
        this.legs.splice(idx, 1);
        this.renderLegsTable();
        this.scheduleRecompute();
      });
    });
  }

  scheduleRecompute() {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.recomputeAndValidate(), 300);
  }

  buildComputePayload() {
    const ivPerLeg = {};
    this.legs.forEach((leg, idx) => {
      const key = `${Math.round(leg.strike)}_${leg.option_type}`;
      ivPerLeg[key] = 0.15; // default 15% IV baseline
      ivPerLeg[String(idx)] = 0.15;
    });
    ivPerLeg['default'] = 0.15;

    return {
      strategy_name: this.strategyName,
      underlying: 'NIFTY',
      legs: this.legs,
      current_spot: this.currentSpot,
      iv_per_leg: ivPerLeg,
    };
  }

  async recomputeAndValidate() {
    if (this.legs.length === 0) return;

    const payload = this.buildComputePayload();

    try {
      // 1. Calculate Payoff & Greeks
      const calc = await api.computeStrategy(payload);
      this.lastCalculation = calc;
      this.renderMetrics(calc);
      renderPayoffChart('payoff-chart-container', calc.payoff_curve, this.currentSpot);

      // 2. Validate against Method Rules
      const validation = await api.validateStrategy(payload);
      this.lastValidation = validation;
      this.renderValidationPanel(validation, calc);
    } catch (err) {
      console.error('Computation/Validation failed:', err);
    }
  }

  renderMetrics(calc) {
    const pc = calc.payoff_curve;
    const g = calc.greeks;

    document.getElementById('metric-max-profit').textContent = formatINR(pc.max_profit_inr);
    document.getElementById('metric-max-loss').textContent = `-${formatINR(pc.max_loss_inr)}`;

    const lossPct = this.marginBase > 0 ? (pc.max_loss_inr / this.marginBase) * 100 : 0;
    document.getElementById('metric-loss-pct').textContent = `${lossPct.toFixed(2)}% of margin base`;

    document.getElementById('metric-rr').textContent = pc.rr_implied.toFixed(2);
    document.getElementById('metric-breakevens').textContent =
      pc.breakevens.length > 0 ? pc.breakevens.map((b) => Math.round(b).toLocaleString('en-IN')).join(', ') : 'None';

    document.getElementById('metric-delta').textContent = g.net_delta.toFixed(2);
    document.getElementById('metric-theta').textContent = `${formatINR(g.net_theta_per_day)}/day`;
    document.getElementById('metric-vega').textContent = `${formatINR(g.net_vega)} per 1% IV`;

    const netFlow = pc.net_debit_credit_inr;
    const flowText = netFlow < 0 ? `Debit ${formatINR(Math.abs(netFlow))}` : `Credit ${formatINR(netFlow)}`;
    document.getElementById('metric-debit-credit').textContent = flowText;
  }

  renderValidationPanel(val, calc) {
    const container = document.getElementById('validation-panel-container');
    if (!container) return;

    const pc = calc.payoff_curve;
    const isPassed = val.passed;

    const checksHtml = val.checks
      .map((c) => {
        const isPass = c.verdict === 'PASS';
        const icon = isPass ? '✅' : '❌';
        const cssClass = isPass ? 'validation-pass' : 'validation-fail';
        return `
        <div class="validation-item ${cssClass}">
          <div>
            <div><strong>${c.rule.replace(/_/g, ' ').toUpperCase()}</strong></div>
            <div style="font-size: 0.75rem; color: var(--text-secondary);">${c.note || ''}</div>
          </div>
          <div class="mono" style="font-size: 0.8rem; font-weight: 600; color: ${isPass ? 'var(--green)' : 'var(--red)'};">
            ${icon} ${c.verdict}
          </div>
        </div>
      `;
      })
      .join('');

    container.innerHTML = `
      <div class="panel">
        <div class="panel-title">
          <span>RULE VALIDATION</span>
          <span style="font-size: 0.8rem; color: var(--text-secondary);">Method Gating</span>
        </div>

        <div class="validation-list">
          ${checksHtml}
        </div>

        <div class="verdict-banner ${isPassed ? 'verdict-pass' : 'verdict-fail'}">
          ${isPassed ? 'VERDICT: ✅ PASSED METHOD AUDIT' : 'VERDICT: ❌ BLOCKED BY METHOD RULES'}
        </div>

        <div>
          <button id="btn-execute-trade" class="primary" style="width: 100%; padding: 0.75rem;" ${isPassed ? '' : 'disabled'}>
            ⚡ EXECUTE PAPER TRADE
          </button>
        </div>

        <div id="tv-button-container" style="margin-top: 0.75rem;"></div>
      </div>
    `;

    // Render TradingView link button
    import('./tv-buttons.js').then(({ renderTvButton }) => {
      const tvContainer = document.getElementById('tv-button-container');
      if (tvContainer) renderTvButton(tvContainer, 'NSE:NIFTY50');
    });

    // Attach execute button click
    const execBtn = document.getElementById('btn-execute-trade');
    if (execBtn) {
      execBtn.addEventListener('click', () => {
        this.openExecutionModal(pc);
      });
    }
  }

  openExecutionModal(payoff) {
    const modal = document.getElementById('confirmation-modal');
    if (!modal) return;

    document.getElementById('modal-strategy-name').textContent = this.strategyName;
    document.getElementById('modal-max-loss').textContent = formatINR(payoff.max_loss_inr);
    document.getElementById('modal-max-profit').textContent = formatINR(payoff.max_profit_inr);
    document.getElementById('modal-rr').textContent = payoff.rr_implied.toFixed(2);

    modal.style.display = 'flex';
  }

  async executePaperTrade() {
    const payload = {
      ...this.buildComputePayload(),
      mode: 'paper',
    };

    try {
      const res = await api.executeTrade(payload);
      this.closeModal();
      this.showToast(`Paper Trade Executed! Created journal: ${res.journal_path}`);
      this.onTradeExecuted();
    } catch (err) {
      alert(`Execution Failed: ${err.message}`);
    }
  }

  closeModal() {
    const modal = document.getElementById('confirmation-modal');
    if (modal) modal.style.display = 'none';
  }

  showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 5000);
  }
}

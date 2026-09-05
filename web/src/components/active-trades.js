/**
 * Active Trades Component with 5-second Live P&L Polling & Trade Exit Flow (BUILD-7).
 *
 * Features:
 * - Polls GET /api/positions/live every 5 seconds
 * - Computes and renders live P&L, updated Greeks, Days Held, and Days to Expiry
 * - Flash animations on P&L value change
 * - Non-destructive error state: displays warning banner if FYERS is unreachable while retaining last-good quotes
 * - Interactive Close Modal with reason selection, optional notes, and editable exit leg premiums
 * - Server confirmation calls POST /api/positions/{id}/close and displays toast notification
 */

import { api } from '../api.js';
import { formatINR } from '../utils/format.js';

export class ActiveTradesComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.positions = [];
    this.pollTimer = null;
    this.lastError = null;
    this.previousPnls = new Map(); // position_id -> number
    this.isClosing = false;
    this.closingPosition = null;
  }

  async init() {
    this.renderContainer();
    await this.fetchLivePositions();
    this.startPolling();
  }

  destroy() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  startPolling() {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = setInterval(() => {
      this.fetchLivePositions();
    }, 5000);
  }

  async fetchLivePositions() {
    try {
      const liveData = await api.getPositionsLive();
      this.positions = liveData || [];
      this.lastError = null;
      this.renderTable();
    } catch (err) {
      console.warn('Live P&L poll warning:', err.message);
      this.lastError = err.message || 'Live P&L temporarily unavailable: FYERS chain unreachable. Retrying in 5s.';
      // Do NOT wipe existing data — re-render with warning banner
      this.renderTable();
    }
  }

  renderContainer() {
    this.container.innerHTML = `
      <div class="panel active-trades-container" id="active-trades-panel">
        <div class="panel-title" style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span>ACTIVE PAPER TRADES</span>
            <span class="badge badge-info" id="active-trades-count">0 Open</span>
          </div>
          <span style="font-size: 0.75rem; color: var(--text-secondary);" id="active-trades-poll-indicator">
            ● Live Polling (5s)
          </span>
        </div>
        <div id="active-trades-banner" style="display: none;"></div>
        <div class="table-wrapper" id="active-trades-table-wrapper">
          <p style="color: var(--text-secondary); font-size: 0.85rem; padding: 1rem 0;">
            No open paper positions. Build a strategy above to get started.
          </p>
        </div>
      </div>

      <!-- Close Position Modal -->
      <div id="close-modal" class="modal-overlay" style="display: none;">
        <div class="modal-content" style="max-width: 520px;">
          <h3 style="margin-bottom: 0.75rem; color: var(--accent-lilac);">Close Position</h3>
          <div id="close-modal-body"></div>
          <div id="close-modal-error" style="display: none; margin: 0.75rem 0; padding: 0.5rem; background: rgba(239, 68, 68, 0.15); border: 1px solid var(--red); border-radius: 4px; color: var(--red); font-size: 0.8rem;"></div>
          <div class="modal-actions" style="margin-top: 1rem;">
            <button id="close-modal-btn-cancel" class="btn">Cancel</button>
            <button id="close-modal-btn-confirm" class="btn primary" style="background: var(--red); border-color: var(--red);">Confirm & Close</button>
          </div>
        </div>
      </div>
    `;

    // Wire modal cancel
    const btnCancel = this.container.querySelector('#close-modal-btn-cancel');
    if (btnCancel) {
      btnCancel.addEventListener('click', () => this.hideCloseModal());
    }

    // Wire modal confirm
    const btnConfirm = this.container.querySelector('#close-modal-btn-confirm');
    if (btnConfirm) {
      btnConfirm.addEventListener('click', () => this.submitClosePosition());
    }
  }

  renderTable() {
    const bannerEl = this.container.querySelector('#active-trades-banner');
    const tableWrapper = this.container.querySelector('#active-trades-table-wrapper');
    const countBadge = this.container.querySelector('#active-trades-count');

    if (countBadge) {
      countBadge.textContent = `${this.positions.length} Open`;
    }

    // Error banner (stale data warning)
    if (bannerEl) {
      if (this.lastError) {
        bannerEl.style.display = 'block';
        bannerEl.className = 'status-banner warning';
        bannerEl.style.margin = '0.5rem 0 1rem 0';
        bannerEl.style.padding = '0.5rem 0.75rem';
        bannerEl.style.fontSize = '0.8rem';
        bannerEl.style.borderRadius = '4px';
        bannerEl.style.background = 'rgba(234, 179, 8, 0.15)';
        bannerEl.style.border = '1px solid var(--amber)';
        bannerEl.style.color = 'var(--amber)';
        bannerEl.innerHTML = `⚠️ ${this.lastError} (Displaying last known values)`;
      } else {
        bannerEl.style.display = 'none';
      }
    }

    if (!this.positions || this.positions.length === 0) {
      if (tableWrapper) {
        tableWrapper.innerHTML = `
          <p style="color: var(--text-secondary); font-size: 0.85rem; padding: 1.5rem 0; text-align: center;">
            No open paper positions. Build a strategy above to get started.
          </p>
        `;
      }
      return;
    }

    const rows = this.positions.map((p, idx) => {
      const openedDate = new Date(p.opened_at).toLocaleDateString([], { month: '2-digit', day: '2-digit' });
      const openedTime = new Date(p.opened_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      
      const pnlVal = p.unrealized_pnl_inr;
      let pnlDisplay = '-';
      let pnlClass = 'text-gray';

      if (pnlVal !== null && pnlVal !== undefined) {
        pnlDisplay = formatINR(pnlVal);
        pnlClass = pnlVal > 0 ? 'text-green' : pnlVal < 0 ? 'text-red' : 'text-gray';
      }

      // Risk % display
      const riskPct = p.unrealized_pnl_pct_of_risk !== null && p.unrealized_pnl_pct_of_risk !== undefined
        ? `(${(p.unrealized_pnl_pct_of_risk * 100).toFixed(1)}% risk)`
        : '';

      // Delta & Theta display
      const greeksText = p.current_greeks
        ? `Δ: ${p.current_greeks.net_delta.toFixed(1)} | θ: ₹${p.current_greeks.net_theta_per_day.toFixed(0)}/d`
        : 'Greeks: N/A';

      const journalFilename = p.journal_path ? p.journal_path.split('/').pop() : 'journal.md';
      const obsidianLink = p.journal_path
        ? `obsidian://open?vault=Second%20Brain&file=${encodeURIComponent(p.journal_path)}`
        : '#';

      return `
        <tr data-pos-id="${p.position_id}">
          <td class="mono">${idx + 1}</td>
          <td>
            <strong>${p.strategy_name}</strong>
            <div style="font-size: 0.75rem; color: var(--text-secondary);">${p.underlying} | ${greeksText}</div>
          </td>
          <td class="mono">
            ${openedDate} ${openedTime}
            <div style="font-size: 0.75rem; color: var(--text-secondary);">${p.days_held}d held</div>
          </td>
          <td class="mono">
            ${p.expiry_date || '-'}
            <div style="font-size: 0.75rem; color: var(--text-secondary);">${p.days_remaining_to_expiry}d left</div>
          </td>
          <td class="mono text-red">-${formatINR(p.max_loss_inr)}</td>
          <td class="mono ${pnlClass}">
            <strong class="pnl-val">${pnlDisplay}</strong>
            <div style="font-size: 0.75rem;">${riskPct}</div>
          </td>
          <td>
            <a href="${obsidianLink}" style="color: var(--accent-lilac); text-decoration: none; font-size: 0.8rem;" title="Open note in Obsidian">
              ${journalFilename} ↗
            </a>
          </td>
          <td style="text-align: right;">
            <button class="btn btn-sm btn-close-trade" data-pos-id="${p.position_id}" style="padding: 3px 8px; font-size: 0.75rem; border-color: var(--red); color: var(--red);">
              Close
            </button>
          </td>
        </tr>
      `;
    }).join('');

    if (tableWrapper) {
      tableWrapper.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Strategy & Greeks</th>
              <th>Opened</th>
              <th>Expiry</th>
              <th>Max Loss</th>
              <th>Live P&L</th>
              <th>Journal</th>
              <th style="text-align: right;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      `;

      // Wire close buttons
      tableWrapper.querySelectorAll('.btn-close-trade').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const posId = e.currentTarget.getAttribute('data-pos-id');
          this.openCloseModal(posId);
        });
      });
    }
  }

  openCloseModal(positionId) {
    const pos = this.positions.find((p) => p.position_id === positionId);
    if (!pos) return;

    this.closingPosition = pos;
    const modal = this.container.querySelector('#close-modal');
    const modalBody = this.container.querySelector('#close-modal-body');
    const modalError = this.container.querySelector('#close-modal-error');

    if (modalError) modalError.style.display = 'none';

    // Build editable exit legs list
    const legsHtml = (pos.legs || []).map((l, idx) => {
      const defaultLtp = l.current_ltp !== undefined ? l.current_ltp : l.entry_premium;
      return `
        <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 2fr; gap: 8px; align-items: center; margin-bottom: 6px; font-size: 0.8rem;" class="mono">
          <span>${l.strike} ${l.option_type} (${l.direction.toUpperCase()})</span>
          <span>Entry: ₹${l.entry_premium}</span>
          <span>Lots: ${l.quantity_lots || 1}</span>
          <div>
            <label style="font-size: 0.7rem; color: var(--text-secondary);">Exit LTP (₹):</label>
            <input type="number" step="0.05" class="exit-ltp-input" data-leg-idx="${idx}" value="${defaultLtp}" style="width: 100%; padding: 2px 4px; font-size: 0.8rem; background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary); border-radius: 3px;" />
          </div>
        </div>
      `;
    }).join('');

    const pnlDisplay = pos.unrealized_pnl_inr !== null ? formatINR(pos.unrealized_pnl_inr) : '0.00';
    const pnlColor = pos.unrealized_pnl_inr >= 0 ? 'var(--green)' : 'var(--red)';

    modalBody.innerHTML = `
      <div style="background: var(--bg-elevated); padding: 0.75rem; border-radius: 6px; border: 1px solid var(--border); margin-bottom: 0.75rem; font-size: 0.85rem;">
        <div><strong>${pos.strategy_name}</strong> (${pos.underlying})</div>
        <div style="margin-top: 4px; color: var(--text-secondary);">
          Estimated Live P&L: <strong style="color: ${pnlColor};">${pnlDisplay}</strong> | Max Risk: ₹${formatINR(pos.max_loss_inr)}
        </div>
      </div>

      <div style="margin-bottom: 0.75rem;">
        <label style="display: block; font-size: 0.8rem; margin-bottom: 4px; color: var(--text-secondary);">Close Reason:</label>
        <select id="close-reason-select" style="width: 100%; padding: 6px; border-radius: 4px; background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);">
          <option value="target_hit">🎯 Target Hit (Method R:R achieved)</option>
          <option value="stop_hit">🛑 Stop Loss Hit (Contractual risk preserved)</option>
          <option value="time_exit">⏳ Time / Expiry Exit (DTE zero or theta achieved)</option>
          <option value="manual" selected>👤 Discretionary / Manual Close</option>
        </select>
      </div>

      <div style="margin-bottom: 0.75rem;">
        <label style="display: block; font-size: 0.8rem; margin-bottom: 4px; color: var(--text-secondary);">Exit Legs (LTP confirmation):</label>
        <div style="background: var(--bg-panel); padding: 0.5rem; border-radius: 4px; border: 1px solid var(--border);">
          ${legsHtml}
        </div>
      </div>

      <div>
        <label style="display: block; font-size: 0.8rem; margin-bottom: 4px; color: var(--text-secondary);">Notes (optional rationale):</label>
        <textarea id="close-notes-input" rows="2" placeholder="Why closing now, market behaviour, or immediate thoughts..." style="width: 100%; padding: 6px; border-radius: 4px; background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary); font-family: inherit; font-size: 0.8rem; resize: none;"></textarea>
      </div>
    `;

    modal.style.display = 'flex';
  }

  hideCloseModal() {
    const modal = this.container.querySelector('#close-modal');
    if (modal) modal.style.display = 'none';
    this.closingPosition = null;
  }

  async submitClosePosition() {
    if (!this.closingPosition || this.isClosing) return;

    const modal = this.container.querySelector('#close-modal');
    const modalError = this.container.querySelector('#close-modal-error');
    const btnConfirm = this.container.querySelector('#close-modal-btn-confirm');
    const reasonSelect = this.container.querySelector('#close-reason-select');
    const notesInput = this.container.querySelector('#close-notes-input');

    const exitLegInputs = this.container.querySelectorAll('.exit-ltp-input');
    const exitLegs = [];

    exitLegInputs.forEach((inp) => {
      const idx = parseInt(inp.getAttribute('data-leg-idx'), 10);
      const originalLeg = this.closingPosition.legs[idx];
      const val = parseFloat(inp.value) || 0.0;
      if (originalLeg) {
        exitLegs.push({
          strike: originalLeg.strike,
          option_type: originalLeg.option_type,
          exit_premium: val,
        });
      }
    });

    const payload = {
      close_reason: reasonSelect ? reasonSelect.value : 'manual',
      notes: notesInput ? notesInput.value.trim() : null,
      exit_legs: exitLegs.length > 0 ? exitLegs : null,
    };

    this.isClosing = true;
    if (btnConfirm) {
      btnConfirm.disabled = true;
      btnConfirm.textContent = 'Closing...';
    }
    if (modalError) modalError.style.display = 'none';

    try {
      const res = await api.closePosition(this.closingPosition.position_id, payload);
      this.hideCloseModal();
      this.showToast(`Trade closed! Realized P&L: ₹${formatINR(res.realized_pnl_inr)}. Journal updated at ${res.journal_path || 'vault'}`);
      
      // Refresh positions list immediately
      await this.fetchLivePositions();

      if (this.options.onTradeClosed) {
        this.options.onTradeClosed(res);
      }
    } catch (err) {
      console.error('Failed to close position:', err);
      if (modalError) {
        modalError.textContent = `Close failed: ${err.message}`;
        modalError.style.display = 'block';
      }
    } finally {
      this.isClosing = false;
      if (btnConfirm) {
        btnConfirm.disabled = false;
        btnConfirm.textContent = 'Confirm & Close';
      }
    }
  }

  showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) {
      alert(message);
      return;
    }
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('fade-out');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
}

/**
 * Backward-compatible helper for callers that use renderActiveTrades.
 */
let _singletonComponent = null;

export function renderActiveTrades(container, positions) {
  if (!_singletonComponent || _singletonComponent.container !== container) {
    _singletonComponent = new ActiveTradesComponent(container);
    _singletonComponent.init();
  } else if (positions) {
    _singletonComponent.positions = positions;
    _singletonComponent.renderTable();
  }
}

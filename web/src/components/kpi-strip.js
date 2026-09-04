/**
 * 7-Tile Top KPI Strip for Swayam Capital Trade Journal (BUILD-11).
 *
 * Displays:
 * 1. Total Trades (with Wins / Losses / BE badge)
 * 2. Win Rate % (color-coded badge)
 * 3. Realised R:R (e.g. 1 : 1.45)
 * 4. Cumulative Net P&L (with Gross P&L and % of Margin base)
 * 5. Discipline Rate % (% followed)
 * 6. Charges Drag ₹ (% of gross P&L)
 * 7. Outliers (Max Profit vs Max Loss)
 */

import { formatINR } from '../utils/format.js';

export class KPIStripComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.kpis = options.kpis || null;
  }

  update(kpis) {
    this.kpis = kpis;
    this.render();
  }

  render() {
    if (!this.container) return;
    const k = this.kpis || {};

    const totalTrades = k.total_trades || 0;
    const wins = k.wins_count || 0;
    const losses = k.losses_count || 0;
    const be = k.breakeven_count || 0;
    const winRate = k.win_rate_pct != null ? k.win_rate_pct.toFixed(1) : '0.0';
    const avgRR = k.avg_rr_actual != null ? k.avg_rr_actual.toFixed(2) : '0.00';
    const netPnl = k.cumulative_net_pnl_inr || 0;
    const grossPnl = k.cumulative_gross_pnl_inr || 0;
    const pctMargin = k.cumulative_pnl_pct_of_margin != null ? k.cumulative_pnl_pct_of_margin.toFixed(2) : '0.00';
    const disciplineRate = k.discipline_rate_pct != null ? k.discipline_rate_pct.toFixed(1) : '100.0';
    const chargesDrag = k.charges_drag_inr || 0;
    const chargesPct = k.charges_drag_pct != null ? k.charges_drag_pct.toFixed(1) : '0.0';

    const maxWin = k.max_profit_trade;
    const maxLoss = k.max_loss_trade;

    const netColor = netPnl > 0 ? 'var(--accent-sage, #86ab92)' : netPnl < 0 ? 'var(--accent-coral, #dd8170)' : 'var(--dl-fg-2, #8b8e9b)';
    const winColor = parseFloat(winRate) >= 50 ? 'var(--accent-sage, #86ab92)' : 'var(--accent-amber, #c9a04a)';
    const discColor = parseFloat(disciplineRate) >= 80 ? 'var(--accent-sage, #86ab92)' : 'var(--accent-coral, #dd8170)';

    this.container.innerHTML = `
      <div class="kpi-strip-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 16px;">
        
        <!-- 1. Total Trades -->
        <div class="kpi-card" style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 12px 14px;">
          <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3, #5a5d6c); margin-bottom: 4px; font-weight: 600;">Total Trades</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: var(--dl-fg, #ffffff); font-family: var(--font-mono, monospace); line-height: 1.2;">
            ${totalTrades}
          </div>
          <div style="display: flex; gap: 4px; margin-top: 4px; font-size: 0.7rem; font-family: var(--font-mono, monospace);">
            <span style="color: var(--accent-sage, #86ab92);">${wins}W</span>
            <span style="color: var(--dl-line, #444);">·</span>
            <span style="color: var(--accent-coral, #dd8170);">${losses}L</span>
            <span style="color: var(--dl-line, #444);">·</span>
            <span style="color: var(--dl-fg-3, #777);">${be}BE</span>
          </div>
        </div>

        <!-- 2. Win Rate -->
        <div class="kpi-card" style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 12px 14px;">
          <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3, #5a5d6c); margin-bottom: 4px; font-weight: 600;">Win Rate</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: ${winColor}; font-family: var(--font-mono, monospace); line-height: 1.2;">
            ${winRate}%
          </div>
          <div style="font-size: 0.7rem; color: var(--dl-fg-3, #5a5d6c); margin-top: 4px;">
            Target: &gt; 50%
          </div>
        </div>

        <!-- 3. Realised R:R -->
        <div class="kpi-card" style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 12px 14px;">
          <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3, #5a5d6c); margin-bottom: 4px; font-weight: 600;">Realised R:R</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: var(--accent-lilac, #ac9fd2); font-family: var(--font-mono, monospace); line-height: 1.2;">
            1 : ${avgRR}
          </div>
          <div style="font-size: 0.7rem; color: var(--dl-fg-3, #5a5d6c); margin-top: 4px;">
            Avg closed ratio
          </div>
        </div>

        <!-- 4. Cumulative Net P&L -->
        <div class="kpi-card" style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 12px 14px;">
          <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3, #5a5d6c); margin-bottom: 4px; font-weight: 600;">Net P&amp;L</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: ${netColor}; font-family: var(--font-mono, monospace); line-height: 1.2;">
            ${netPnl >= 0 ? '+' : ''}₹${Math.round(netPnl).toLocaleString('en-IN')}
          </div>
          <div style="font-size: 0.7rem; color: var(--dl-fg-3, #5a5d6c); margin-top: 4px; display: flex; gap: 4px; flex-wrap: wrap;">
            <span>Gross: ₹${Math.round(grossPnl).toLocaleString('en-IN')}</span>
            <span style="color: var(--dl-line);">·</span>
            <span>${pctMargin}% cap</span>
          </div>
        </div>

        <!-- 5. Discipline Rate -->
        <div class="kpi-card" style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 12px 14px;">
          <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3, #5a5d6c); margin-bottom: 4px; font-weight: 600;">Discipline Rate</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: ${discColor}; font-family: var(--font-mono, monospace); line-height: 1.2;">
            ${disciplineRate}%
          </div>
          <div style="font-size: 0.7rem; color: var(--dl-fg-3, #5a5d6c); margin-top: 4px;">
            Rules strictly kept
          </div>
        </div>

        <!-- 6. Charges Drag -->
        <div class="kpi-card" style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 12px 14px;">
          <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3, #5a5d6c); margin-bottom: 4px; font-weight: 600;">Charges Drag</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: var(--dl-fg-2, #8b8e9b); font-family: var(--font-mono, monospace); line-height: 1.2;">
            ₹${Math.round(chargesDrag).toLocaleString('en-IN')}
          </div>
          <div style="font-size: 0.7rem; color: var(--dl-fg-3, #5a5d6c); margin-top: 4px;">
            ${chargesPct}% of gross
          </div>
        </div>

        <!-- 7. Outliers -->
        <div class="kpi-card" style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 12px 14px;">
          <div style="font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3, #5a5d6c); margin-bottom: 4px; font-weight: 600;">Outliers</div>
          <div style="display: flex; flex-direction: column; gap: 2px; margin-top: 2px;">
            <div style="font-size: 0.8rem; font-family: var(--font-mono, monospace); color: var(--accent-sage, #86ab92); font-weight: 600;">
              ▲ +₹${maxWin ? Math.round(maxWin.pnl).toLocaleString('en-IN') : '0'}
            </div>
            <div style="font-size: 0.8rem; font-family: var(--font-mono, monospace); color: var(--accent-coral, #dd8170); font-weight: 600;">
              ▼ -₹${maxLoss ? Math.abs(Math.round(maxLoss.pnl)).toLocaleString('en-IN') : '0'}
            </div>
          </div>
        </div>

      </div>
    `;
  }
}
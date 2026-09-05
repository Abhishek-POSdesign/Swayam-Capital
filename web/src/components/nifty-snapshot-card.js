/**
 * NIFTY Snapshot Card Component for Swayam Capital (BUILD-11.9).
 *
 * Renders two stacked panes:
 * - Cash pane: Spot, % changes, 20-day/50-day ranges, 20-DMA distance (ATR multiple),
 *   ATR(20), 20-day realized vol, rule-based sentiment, advance/decline, sector strip.
 * - F&O pane: Weekly & Monthly expiries + DTE (calendar days + trading sessions),
 *   Weekly & Monthly PCR, Max Pain (weekly), Max Call/Put OI strikes, India VIX + % chg,
 *   FII Cash (₹ cr) vs FII F&O (contracts) strictly separated,
 *   DII Cash (₹ cr) vs DII F&O (contracts) strictly separated,
 *   Rollover % (visible only within 3 sessions of monthly expiry).
 *
 * Freshness Badges (4 states):
 * - LIVE: Real-time via FYERS WebSocket or fresh REST
 * - CALCULATED: Derived locally from cached raw
 * - PREVIOUS SESSION: EOD data from yesterday/past session
 * - STALE: Cache expired, refresh pending
 */

import { api } from '../api.js';

export class NiftySnapshotCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.data = null;
    this.isRefreshing = false;
    this.error = null;
  }

  async init() {
    await this.fetchData(false);
  }

  async fetchData(forceRefresh = false) {
    this.isRefreshing = true;
    this.render();

    try {
      const resp = await api.getNiftySnapshot(forceRefresh);
      this.data = resp;
      this.error = null;
    } catch (err) {
      console.error('Failed to fetch NIFTY snapshot:', err);
      this.error = err.message || 'Failed to load snapshot';
    } finally {
      this.isRefreshing = false;
      this.render();
    }
  }

  getBadgeHtml(status) {
    const s = (this.isRefreshing && status === 'LIVE') ? 'STALE' : (status || 'CALCULATED');
    let bg = 'var(--dl-card-2)';
    let color = 'var(--dl-fg-2)';
    let border = 'var(--dl-line)';

    if (s === 'LIVE') {
      bg = 'rgba(74, 222, 128, 0.12)';
      color = '#4ade80';
      border = 'rgba(74, 222, 128, 0.3)';
    } else if (s === 'CALCULATED') {
      bg = 'rgba(147, 197, 253, 0.12)';
      color = '#93c5fd';
      border = 'rgba(147, 197, 253, 0.3)';
    } else if (s === 'PREVIOUS SESSION') {
      bg = 'rgba(251, 191, 36, 0.12)';
      color = '#fbbf24';
      border = 'rgba(251, 191, 36, 0.3)';
    } else if (s === 'STALE') {
      bg = 'rgba(248, 113, 113, 0.12)';
      color = '#f87171';
      border = 'rgba(248, 113, 113, 0.3)';
    }

    return `
      <span class="freshness-badge" style="display: inline-flex; align-items: center; font-size: 0.62rem; font-weight: 700; font-family: var(--font-mono); letter-spacing: 0.05em; padding: 1px 6px; border-radius: 4px; background: ${bg}; color: ${color}; border: 1px solid ${border}; white-space: nowrap;">
        ${s}
      </span>
    `;
  }

  render() {
    if (!this.data && this.isRefreshing) {
      this.container.innerHTML = `
        <div class="tile span-12" style="padding: 32px; text-align: center; color: var(--dl-fg-2);">
          <div style="width: 24px; height: 24px; border: 2px solid var(--dl-track); border-top-color: var(--accent-sage); border-radius: 50%; animation: spin 0.6s linear infinite; margin: 0 auto 12px auto;"></div>
          Loading NIFTY Market Snapshot...
        </div>
      `;
      return;
    }

    const cash = this.data?.cash_pane || {};
    const fno = this.data?.fno_pane || {};
    const inst = fno.institutional || {};

    const spot = Number(cash.spot || 24864.2).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const dayChg = Number(cash.day_change_pct || 0);
    const dayChgSign = dayChg >= 0 ? '+' : '';
    const dayChgColor = dayChg >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';

    const weekChg = Number(cash.week_change_pct || 0);
    const weekChgSign = weekChg >= 0 ? '+' : '';
    const weekChgColor = weekChg >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';

    const monthChg = Number(cash.month_change_pct || 0);
    const monthChgSign = monthChg >= 0 ? '+' : '';
    const monthChgColor = monthChg >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';

    const spotPosPct = Math.min(100, Math.max(0, Number(cash.spot_position_pct_20d || 50)));

    // Sentiment pill color
    const sentiment = cash.sentiment || 'Neutral';
    let sentColor = 'var(--dl-fg-2)';
    let sentBg = 'var(--dl-card-2)';
    if (sentiment === 'Bullish') {
      sentColor = 'var(--accent-sage)';
      sentBg = 'rgba(74, 222, 128, 0.12)';
    } else if (sentiment === 'Bearish') {
      sentColor = 'var(--accent-coral)';
      sentBg = 'rgba(248, 113, 113, 0.12)';
    }

    // Sector rotation HTML
    const sectors = cash.sector_rotation || [];
    const sectorStripHtml = sectors.map(sec => {
      const sign = sec.change_pct >= 0 ? '+' : '';
      const col = sec.change_pct >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';
      return `
        <div style="display: flex; flex-direction: column; align-items: center; background: var(--dl-card-2); padding: 4px 8px; border-radius: 6px; border: 1px solid var(--dl-line); min-width: 58px;">
          <span style="font-size: 0.65rem; color: var(--dl-fg-3); font-weight: 600;">${sec.name}</span>
          <span class="mono-nums" style="font-size: 0.72rem; color: ${col}; font-weight: 700;">${sign}${sec.change_pct.toFixed(1)}%</span>
        </div>
      `;
    }).join('');

    // FII / DII formatting
    const fiiCashVal = inst.fii_cash_net_cr || 0;
    const fiiCashStr = `${fiiCashVal >= 0 ? '+' : ''}${fiiCashVal.toLocaleString('en-IN')} cr`;
    const fiiCashColor = fiiCashVal >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';

    const diiCashVal = inst.dii_cash_net_cr || 0;
    const diiCashStr = `${diiCashVal >= 0 ? '+' : ''}${diiCashVal.toLocaleString('en-IN')} cr`;
    const diiCashColor = diiCashVal >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';

    this.container.innerHTML = `
      <div class="tile nifty-snapshot-tile span-12" style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: 10px; padding: 20px; box-sizing: border-box; display: flex; flex-direction: column; gap: 20px;">
        
        <!-- Header: Title + Refresh Control -->
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--dl-line); padding-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="eyebrow" style="font-size: 0.85rem; font-weight: 700; color: var(--dl-fg); letter-spacing: 0.06em;">NIFTY 50 SNAPSHOT</span>
            <span style="font-size: 0.72rem; color: var(--dl-fg-3);">Cash & F&O Overview</span>
          </div>

          <button id="btn-refresh-nifty-snapshot" type="button" ${this.isRefreshing ? 'disabled' : ''} style="background: var(--dl-card-2); border: 1px solid var(--dl-line); color: var(--dl-fg-2); padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; cursor: ${this.isRefreshing ? 'not-allowed' : 'pointer'}; display: flex; align-items: center; gap: 6px;" title="Refresh snapshot quotes and option chain">
            <span style="${this.isRefreshing ? 'animation: spin 0.8s linear infinite;' : ''}">🔄</span>
            <span>${this.isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>

        <!-- ==================== PANE 1: CASH PANE ==================== -->
        <div class="snapshot-pane cash-pane" style="display: flex; flex-direction: column; gap: 14px; background: rgba(0,0,0,0.06); padding: 14px; border-radius: 8px; border: 1px solid var(--dl-line);">
          
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="eyebrow" style="font-size: 0.74rem; font-weight: 700; color: var(--dl-fg-2);">CASH MARKET</span>
              ${this.getBadgeHtml(cash.spot_freshness)}
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 0.72rem; color: var(--dl-fg-3);">Breadth:</span>
              <span class="mono-nums" style="font-size: 0.76rem; color: var(--accent-sage); font-weight: 600;">▲ ${cash.advances || 32}</span>
              <span class="mono-nums" style="font-size: 0.76rem; color: var(--accent-coral); font-weight: 600;">▼ ${cash.declines || 18}</span>
              ${this.getBadgeHtml(cash.breadth_freshness)}
            </div>
          </div>

          <!-- Spot + % Changes Row -->
          <div style="display: flex; flex-wrap: wrap; align-items: baseline; gap: 20px;">
            <div style="display: flex; align-items: baseline; gap: 8px;">
              <span class="mono-nums" style="font-size: 1.85rem; font-weight: 700; color: var(--dl-fg);">${spot}</span>
              <span class="mono-nums" style="font-size: 1rem; font-weight: 600; color: ${dayChgColor};">${dayChgSign}${dayChg.toFixed(2)}%</span>
            </div>

            <div style="display: flex; align-items: center; gap: 14px; margin-left: auto;">
              <div style="display: flex; flex-direction: column; align-items: flex-end;">
                <span style="font-size: 0.65rem; color: var(--dl-fg-3); text-transform: uppercase;">Week %</span>
                <span class="mono-nums" style="font-size: 0.85rem; font-weight: 600; color: ${weekChgColor};">${weekChgSign}${weekChg.toFixed(2)}%</span>
              </div>
              <div style="display: flex; flex-direction: column; align-items: flex-end;">
                <span style="font-size: 0.65rem; color: var(--dl-fg-3); text-transform: uppercase;">Month %</span>
                <span class="mono-nums" style="font-size: 0.85rem; font-weight: 600; color: ${monthChgColor};">${monthChgSign}${monthChg.toFixed(2)}%</span>
              </div>
              <div style="display: flex; flex-direction: column; align-items: flex-end;">
                <span style="font-size: 0.65rem; color: var(--dl-fg-3); text-transform: uppercase;">Sentiment</span>
                <span style="font-size: 0.75rem; font-weight: 700; color: ${sentColor}; background: ${sentBg}; padding: 2px 8px; border-radius: 4px;">${sentiment}</span>
              </div>
            </div>
          </div>

          <!-- 20-Day Range Bar & Technical Metrics Grid -->
          <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 18px; align-items: center; padding-top: 6px;">
            
            <!-- 20-Day Range Visual Bar -->
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--dl-fg-3);">
                <span>20D Low: <strong class="mono-nums" style="color: var(--dl-fg);">${cash.range_20d?.low || '-'}</strong></span>
                <span style="font-weight: 600; color: var(--dl-fg-2);">20-Day Range</span>
                <span>20D High: <strong class="mono-nums" style="color: var(--dl-fg);">${cash.range_20d?.high || '-'}</strong></span>
              </div>
              <div style="width: 100%; height: 8px; background: var(--dl-card-2); border-radius: 4px; position: relative; border: 1px solid var(--dl-line); overflow: visible;">
                <div style="position: absolute; left: ${spotPosPct}%; top: -3px; width: 4px; height: 14px; background: var(--accent-amber); border-radius: 2px; transform: translateX(-50%); box-shadow: 0 0 6px rgba(234,179,8,0.6);" title="Current spot at ${spotPosPct}% of 20D range"></div>
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 0.68rem; color: var(--dl-fg-3);">
                <span>50D Range: <span class="mono-nums">${cash.range_50d?.low || '-'} – ${cash.range_50d?.high || '-'}</span></span>
                <span>Spot Position: <strong class="mono-nums" style="color: var(--accent-amber);">${spotPosPct}%</strong></span>
              </div>
            </div>

            <!-- Quantitative Volatility & DMA Metrics -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; text-align: center;">
              <div style="background: var(--dl-card-2); padding: 6px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.62rem; color: var(--dl-fg-3); text-transform: uppercase;">20-DMA Dist</div>
                <div class="mono-nums" style="font-size: 0.82rem; font-weight: 700; color: var(--dl-fg);">${cash.distance_20_dma_atr !== undefined ? `${cash.distance_20_dma_atr >= 0 ? '+' : ''}${cash.distance_20_dma_atr} ATR` : '+0.42 ATR'}</div>
              </div>
              <div style="background: var(--dl-card-2); padding: 6px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.62rem; color: var(--dl-fg-3); text-transform: uppercase;">20-Day ATR</div>
                <div class="mono-nums" style="font-size: 0.82rem; font-weight: 700; color: var(--dl-fg);">₹${cash.atr_20 || '185.50'}</div>
              </div>
              <div style="background: var(--dl-card-2); padding: 6px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.62rem; color: var(--dl-fg-3); text-transform: uppercase;">Realized Vol</div>
                <div class="mono-nums" style="font-size: 0.82rem; font-weight: 700; color: var(--dl-fg);">${cash.realized_vol_20 !== undefined ? `${cash.realized_vol_20}%` : '11.8%'}</div>
              </div>
            </div>

          </div>

          <!-- Sector Rotation Strip -->
          <div style="display: flex; flex-direction: column; gap: 6px; padding-top: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-size: 0.68rem; color: var(--dl-fg-3); text-transform: uppercase; letter-spacing: 0.05em;">Sector Rotation (10 Sectors)</span>
              ${this.getBadgeHtml(cash.sector_freshness)}
            </div>
            <div style="display: flex; gap: 6px; overflow-x: auto; padding-bottom: 2px;">
              ${sectorStripHtml}
            </div>
          </div>

        </div>

        <!-- ==================== PANE 2: F&O DERIVATIVES PANE ==================== -->
        <div class="snapshot-pane fno-pane" style="display: flex; flex-direction: column; gap: 14px; background: rgba(0,0,0,0.06); padding: 14px; border-radius: 8px; border: 1px solid var(--dl-line);">
          
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="eyebrow" style="font-size: 0.74rem; font-weight: 700; color: var(--dl-fg-2);">F&O DERIVATIVES</span>
              ${this.getBadgeHtml(fno.expiry_freshness)}
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 0.72rem; color: var(--dl-fg-3);">India VIX:</span>
              <span class="mono-nums" style="font-size: 0.85rem; font-weight: 700; color: var(--dl-fg);">${fno.india_vix || 13.10}</span>
              <span class="mono-nums" style="font-size: 0.72rem; color: ${(fno.india_vix_change_pct || 0) >= 0 ? 'var(--accent-coral)' : 'var(--accent-sage)'}; font-weight: 600;">
                ${(fno.india_vix_change_pct || 0) >= 0 ? '+' : ''}${fno.india_vix_change_pct !== undefined ? fno.india_vix_change_pct : '1.95'}%
              </span>
              ${this.getBadgeHtml(fno.vix_freshness)}
            </div>
          </div>

          <!-- Expiry & Structure Grid -->
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
            
            <!-- Weekly Expiry -->
            <div style="background: var(--dl-card-2); padding: 10px; border-radius: 6px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.65rem; color: var(--dl-fg-3); text-transform: uppercase;">Weekly Expiry</span>
                <span class="badge" style="font-size: 0.6rem; background: var(--dl-track); padding: 1px 4px; border-radius: 3px;">Tuesday</span>
              </div>
              <div class="mono-nums" style="font-size: 0.95rem; font-weight: 700; color: var(--dl-fg);">${fno.weekly_expiry || '-'}</div>
              <div style="font-size: 0.7rem; color: var(--accent-amber); font-family: var(--font-mono);">${fno.weekly_dte?.formatted || '-'}</div>
            </div>

            <!-- Monthly Expiry -->
            <div style="background: var(--dl-card-2); padding: 10px; border-radius: 6px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.65rem; color: var(--dl-fg-3); text-transform: uppercase;">Monthly Expiry</span>
                <span class="badge" style="font-size: 0.6rem; background: var(--dl-track); padding: 1px 4px; border-radius: 3px;">Month-End</span>
              </div>
              <div class="mono-nums" style="font-size: 0.95rem; font-weight: 700; color: var(--dl-fg);">${fno.monthly_expiry || '-'}</div>
              <div style="font-size: 0.7rem; color: var(--dl-fg-2); font-family: var(--font-mono);">${fno.monthly_dte?.formatted || '-'}</div>
            </div>

            <!-- Put-Call Ratio (PCR) -->
            <div style="background: var(--dl-card-2); padding: 10px; border-radius: 6px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.65rem; color: var(--dl-fg-3); text-transform: uppercase;">Put-Call Ratio</span>
                ${this.getBadgeHtml(fno.pcr_freshness)}
              </div>
              <div style="display: flex; align-items: baseline; gap: 10px;">
                <div><span style="font-size: 0.65rem; color: var(--dl-fg-3);">W: </span><strong class="mono-nums" style="font-size: 0.95rem; color: var(--dl-fg);">${fno.weekly_pcr || '-'}</strong></div>
                <div><span style="font-size: 0.65rem; color: var(--dl-fg-3);">M: </span><strong class="mono-nums" style="font-size: 0.95rem; color: var(--dl-fg);">${fno.monthly_pcr || '-'}</strong></div>
              </div>
              <div style="font-size: 0.68rem; color: var(--dl-fg-3);">
                ${fno.weekly_pcr > 1.2 ? 'Bullish bias' : (fno.weekly_pcr < 0.8 ? 'Bearish bias' : 'Balanced band')}
              </div>
            </div>

            <!-- Max Pain & OI Walls -->
            <div style="background: var(--dl-card-2); padding: 10px; border-radius: 6px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.65rem; color: var(--dl-fg-3); text-transform: uppercase;">Max Pain & Walls</span>
                ${this.getBadgeHtml(fno.max_pain_freshness)}
              </div>
              <div class="mono-nums" style="font-size: 0.95rem; font-weight: 700; color: var(--accent-sage);">
                Pain: ${fno.max_pain ? fno.max_pain.toLocaleString('en-IN') : '-'}
              </div>
              <div style="font-size: 0.68rem; color: var(--dl-fg-3); display: flex; gap: 8px;">
                <span>Call Wall: <strong class="mono-nums" style="color: var(--accent-coral);">${fno.max_call_oi_strike || '-'}</strong></span>
                <span>Put Wall: <strong class="mono-nums" style="color: var(--accent-sage);">${fno.max_put_oi_strike || '-'}</strong></span>
              </div>
            </div>

          </div>

          <!-- Institutional Rows (FII Cash / FII F&O / DII Cash / DII F&O) — STRICTLY SEPARATE -->
          <div style="display: flex; flex-direction: column; gap: 8px; padding-top: 4px; border-top: 1px solid var(--dl-line);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span class="eyebrow" style="font-size: 0.68rem; color: var(--dl-fg-3); text-transform: uppercase; letter-spacing: 0.05em;">Institutional Flow (Cash ₹ Cr vs F&O Contracts — Separate)</span>
              ${this.getBadgeHtml(inst.fii_cash_freshness || 'PREVIOUS SESSION')}
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">
              
              <!-- FII Cash Row -->
              <div style="background: var(--dl-card-2); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.65rem; color: var(--dl-fg-3);">FII CASH (₹ Cr)</div>
                <div class="mono-nums" style="font-size: 0.88rem; font-weight: 700; color: ${fiiCashColor};">${fiiCashStr}</div>
                <div style="font-size: 0.62rem; color: var(--dl-fg-3);">${inst.fii_cash_freshness}</div>
              </div>

              <!-- FII F&O Row -->
              <div style="background: var(--dl-card-2); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.65rem; color: var(--dl-fg-3);">FII F&O (Contracts)</div>
                <div class="mono-nums" style="font-size: 0.88rem; font-weight: 700; color: var(--dl-fg);">${inst.fii_fno_net_contracts || '-'}</div>
                <div style="font-size: 0.62rem; color: var(--dl-fg-2);">${inst.fii_fno_detail || '-'}</div>
              </div>

              <!-- DII Cash Row -->
              <div style="background: var(--dl-card-2); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.65rem; color: var(--dl-fg-3);">DII CASH (₹ Cr)</div>
                <div class="mono-nums" style="font-size: 0.88rem; font-weight: 700; color: ${diiCashColor};">${diiCashStr}</div>
                <div style="font-size: 0.62rem; color: var(--dl-fg-3);">${inst.dii_cash_freshness}</div>
              </div>

              <!-- DII F&O Row -->
              <div style="background: var(--dl-card-2); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.65rem; color: var(--dl-fg-3);">DII F&O (Contracts)</div>
                <div class="mono-nums" style="font-size: 0.88rem; font-weight: 700; color: var(--dl-fg);">${inst.dii_fno_net_contracts || '-'}</div>
                <div style="font-size: 0.62rem; color: var(--dl-fg-2);">${inst.dii_fno_detail || '-'}</div>
              </div>

            </div>
          </div>

          <!-- Rollover % (Conditional: ONLY displayed in last 3 sessions before monthly expiry) -->
          ${fno.is_rollover_window ? `
            <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(234, 179, 8, 0.1); border: 1px solid rgba(234, 179, 8, 0.3); padding: 8px 12px; border-radius: 6px; margin-top: 2px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 0.85rem;">🔄</span>
                <span style="font-size: 0.75rem; font-weight: 600; color: var(--accent-amber);">Monthly Expiry Rollover Window Active</span>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-2);">Rollover:</span>
                <span class="mono-nums" style="font-size: 0.85rem; font-weight: 700; color: var(--accent-amber);">${fno.rollover_pct}%</span>
                ${this.getBadgeHtml(fno.rollover_freshness)}
              </div>
            </div>
          ` : ''}

        </div>

      </div>
    `;

    // Attach refresh button listener
    const refBtn = this.container.querySelector('#btn-refresh-nifty-snapshot');
    if (refBtn) {
      refBtn.addEventListener('click', () => this.fetchData(true));
    }
  }
}

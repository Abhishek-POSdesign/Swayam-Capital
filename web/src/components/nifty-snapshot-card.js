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
      bg = 'var(--dl-card-2)';
      color = 'var(--dl-fg-2)';
      border = 'var(--dl-line)';
    } else if (s === 'STALE') {
      bg = 'rgba(248, 113, 113, 0.12)';
      color = '#f87171';
      border = 'rgba(248, 113, 113, 0.3)';
    }

    return `
      <span class="freshness-badge" style="display: inline-flex; align-items: center; font-size: 0.65rem; font-weight: 700; font-family: var(--font-mono); letter-spacing: 0.05em; padding: 2px 8px; border-radius: 4px; background: ${bg}; color: ${color}; border: 1px solid ${border}; white-space: nowrap;">
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

    // Honest formatting: real value or '—'. NEVER a fabricated fallback number.
    const has = (v) => !(v === null || v === undefined || v === '' || (typeof v === 'number' && isNaN(v)));
    const dash = (v, fn) => (has(v) ? (fn ? fn(v) : v) : '—');
    const pctStr = (v) => (has(v) ? `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%` : '—');
    const pctColor = (v) => (!has(v) ? 'var(--dl-fg-3)' : (v >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)'));

    const spotStr = dash(cash.spot, (v) => Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    const dayChgStr = pctStr(cash.day_change_pct);
    const dayChgColor = pctColor(cash.day_change_pct);
    const weekChgStr = pctStr(cash.week_change_pct);
    const weekChgColor = pctColor(cash.week_change_pct);
    const monthChgStr = pctStr(cash.month_change_pct);
    const monthChgColor = pctColor(cash.month_change_pct);

    const hasSpotPos = has(cash.spot_position_pct_20d);
    const spotPosPct = hasSpotPos ? Math.min(100, Math.max(0, Number(cash.spot_position_pct_20d))) : null;

    // Sentiment pill color
    const sentiment = has(cash.sentiment) ? cash.sentiment : null;
    let sentColor = 'var(--dl-fg-2)';
    let sentBg = 'var(--dl-card-2)';
    if (sentiment === 'Bullish') {
      sentColor = 'var(--accent-sage)';
      sentBg = 'rgba(74, 222, 128, 0.12)';
    } else if (sentiment === 'Bearish') {
      sentColor = 'var(--accent-coral)';
      sentBg = 'rgba(248, 113, 113, 0.12)';
    }

    // Sector rotation HTML — '—' when there's no real quote, never a fabricated move.
    const sectors = cash.sector_rotation || [];
    const sectorStripHtml = sectors.map(sec => {
      const c = sec.change_pct;
      const col = !has(c) ? 'var(--dl-fg-3)' : (c >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)');
      const val = has(c) ? `${c >= 0 ? '+' : ''}${Number(c).toFixed(1)}%` : '—';
      return `
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: var(--dl-card-2); padding: 8px 12px; border-radius: 8px; border: 1px solid var(--dl-line); min-width: 80px; flex: 0 0 auto;">
          <span style="font-size: 0.80rem; color: var(--dl-fg-2); font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;">${sec.name}</span>
          <span class="mono-nums" style="font-size: 0.98rem; color: ${col}; font-weight: 800; margin-top: 2px;">${val}</span>
        </div>
      `;
    }).join('');

    // FII / DII — '—' when unavailable (no real source), never +0 cr.
    const fiiCashStr = dash(inst.fii_cash_net_cr, (v) => `${v >= 0 ? '+' : ''}${Number(v).toLocaleString('en-IN')} cr`);
    const fiiCashColor = pctColor(inst.fii_cash_net_cr);
    const diiCashStr = dash(inst.dii_cash_net_cr, (v) => `${v >= 0 ? '+' : ''}${Number(v).toLocaleString('en-IN')} cr`);
    const diiCashColor = pctColor(inst.dii_cash_net_cr);

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
        <div class="snapshot-pane cash-pane" style="display: flex; flex-direction: column; gap: 16px; background: rgba(0,0,0,0.12); padding: 18px 20px; border-radius: 10px; border: 1px solid var(--dl-line);">
          
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="eyebrow" style="font-size: 0.88rem; font-weight: 800; color: var(--dl-fg); letter-spacing: 0.05em;">CASH MARKET</span>
              ${this.getBadgeHtml(cash.spot_freshness)}
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <span style="font-size: 0.8rem; color: var(--dl-fg-3); font-weight: 600;">Market Breadth:</span>
              <span class="mono-nums" style="font-size: 0.95rem; color: var(--accent-sage); font-weight: 700;">▲ ${dash(cash.advances)} Adv</span>
              <span class="mono-nums" style="font-size: 0.95rem; color: var(--accent-coral); font-weight: 700;">▼ ${dash(cash.declines)} Dec</span>
            </div>
          </div>

          <!-- Spot + % Changes Row -->
          <div style="display: flex; flex-wrap: wrap; align-items: baseline; gap: 24px;">
            <div style="display: flex; align-items: baseline; gap: 12px;">
              <span class="mono-nums" style="font-size: 2.35rem; font-weight: 800; color: var(--dl-fg); letter-spacing: -0.02em;">${spotStr}</span>
              <span class="mono-nums" style="font-size: 1.35rem; font-weight: 700; color: ${dayChgColor};">${dayChgStr}</span>
            </div>

            <div style="display: flex; align-items: center; gap: 20px; margin-left: auto; flex-wrap: wrap;">
              <div style="display: flex; flex-direction: column; align-items: flex-end;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Week %</span>
                <span class="mono-nums" style="font-size: 1.15rem; font-weight: 700; color: ${weekChgColor};">${weekChgStr}</span>
              </div>
              <div style="display: flex; flex-direction: column; align-items: flex-end;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Month %</span>
                <span class="mono-nums" style="font-size: 1.15rem; font-weight: 700; color: ${monthChgColor};">${monthChgStr}</span>
              </div>
              <div style="display: flex; flex-direction: column; align-items: flex-end;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Sentiment</span>
                <span style="font-size: 0.95rem; font-weight: 800; color: ${sentColor}; background: ${sentBg}; padding: 3px 10px; border-radius: 6px; letter-spacing: 0.02em;">${sentiment || '—'}</span>
              </div>
            </div>
          </div>

          <!-- 20-Day Range Bar & Technical Metrics Grid -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; align-items: center; padding-top: 4px;">
            
            <!-- 20-Day Range Visual Bar -->
            <div style="display: flex; flex-direction: column; gap: 8px; background: var(--dl-card-2); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--dl-line);">
              <div style="display: flex; justify-content: space-between; font-size: 0.82rem; color: var(--dl-fg-3);">
                <span>20D Low: <strong class="mono-nums" style="color: var(--dl-fg); font-size: 0.9rem;">${cash.range_20d?.low || '-'}</strong></span>
                <span style="font-weight: 700; color: var(--dl-fg-2);">20-Day Range</span>
                <span>20D High: <strong class="mono-nums" style="color: var(--dl-fg); font-size: 0.9rem;">${cash.range_20d?.high || '-'}</strong></span>
              </div>
              <div style="width: 100%; height: 10px; background: var(--dl-track); border-radius: 5px; position: relative; border: 1px solid var(--dl-line); overflow: visible;">
                ${hasSpotPos ? `<div style="position: absolute; left: ${spotPosPct}%; top: -3px; width: 6px; height: 16px; background: var(--accent-amber); border-radius: 3px; transform: translateX(-50%); box-shadow: 0 0 8px rgba(234,179,8,0.8);" title="Current spot at ${spotPosPct}% of 20D range"></div>` : ''}
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--dl-fg-3);">
                <span>50D Range: <span class="mono-nums" style="color: var(--dl-fg-2); font-weight: 600;">${cash.range_50d?.low || '—'} – ${cash.range_50d?.high || '—'}</span></span>
                <span>Spot Position: <strong class="mono-nums" style="color: var(--accent-amber); font-size: 0.88rem; font-weight: 700;">${hasSpotPos ? spotPosPct + '%' : '—'}</strong></span>
              </div>
            </div>

            <!-- Quantitative Volatility & DMA Metrics -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; text-align: center;">
              <div style="background: var(--dl-card-2); padding: 12px 8px; border-radius: 8px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">20-DMA Dist</div>
                <div class="mono-nums" style="font-size: 1.18rem; font-weight: 800; color: var(--dl-fg); margin-top: 4px;">${has(cash.distance_20_dma_atr) ? `${cash.distance_20_dma_atr >= 0 ? '+' : ''}${cash.distance_20_dma_atr} ATR` : '—'}</div>
              </div>
              <div style="background: var(--dl-card-2); padding: 12px 8px; border-radius: 8px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">20-Day ATR</div>
                <div class="mono-nums" style="font-size: 1.18rem; font-weight: 800; color: var(--dl-fg); margin-top: 4px;">${has(cash.atr_20) ? '₹' + cash.atr_20 : '—'}</div>
              </div>
              <div style="background: var(--dl-card-2); padding: 12px 8px; border-radius: 8px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Realized Vol</div>
                <div class="mono-nums" style="font-size: 1.18rem; font-weight: 800; color: var(--dl-fg); margin-top: 4px;">${has(cash.realized_vol_20) ? `${cash.realized_vol_20}%` : '—'}</div>
              </div>
            </div>

          </div>

          <!-- Sector Rotation Strip -->
          <div style="display: flex; flex-direction: column; gap: 8px; padding-top: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-size: 0.74rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Sector Rotation (10 Sectors)</span>
            </div>
            <div style="display: flex; gap: 10px; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 6px;">
              ${sectorStripHtml}
            </div>
          </div>

        </div>

        <!-- ==================== PANE 2: F&O DERIVATIVES PANE ==================== -->
        <div class="snapshot-pane fno-pane" style="display: flex; flex-direction: column; gap: 16px; background: rgba(0,0,0,0.12); padding: 18px 20px; border-radius: 10px; border: 1px solid var(--dl-line);">
          
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="eyebrow" style="font-size: 0.88rem; font-weight: 800; color: var(--dl-fg); letter-spacing: 0.05em;">F&O DERIVATIVES</span>
              ${this.getBadgeHtml(fno.expiry_freshness || 'PREVIOUS SESSION')}
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <span style="font-size: 0.82rem; color: var(--dl-fg-3); font-weight: 600;">India VIX:</span>
              <span class="mono-nums" style="font-size: 1.25rem; font-weight: 800; color: var(--dl-fg);">${dash(fno.india_vix)}</span>
              <span class="mono-nums" style="font-size: 0.95rem; color: ${!has(fno.india_vix_change_pct) ? 'var(--dl-fg-3)' : (fno.india_vix_change_pct >= 0 ? 'var(--accent-coral)' : 'var(--accent-sage)')}; font-weight: 700;">
                ${has(fno.india_vix_change_pct) ? `${fno.india_vix_change_pct >= 0 ? '+' : ''}${fno.india_vix_change_pct}%` : '—'}
              </span>
            </div>
          </div>

          <!-- Expiry & Structure Grid (Responsive auto-fit) -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px;">
            
            <!-- Weekly Expiry -->
            <div style="background: var(--dl-card-2); padding: 14px; border-radius: 8px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 6px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Weekly Expiry</span>
                <span class="badge" style="font-size: 0.68rem; background: var(--dl-track); padding: 2px 6px; border-radius: 4px; font-weight: 600;">Tuesday</span>
              </div>
              <div class="mono-nums" style="font-size: 1.25rem; font-weight: 800; color: var(--dl-fg);">${fno.weekly_expiry || '-'}</div>
              <div style="font-size: 0.85rem; color: var(--accent-amber); font-family: var(--font-mono); font-weight: 700;">${fno.weekly_dte?.formatted || '-'}</div>
            </div>

            <!-- Monthly Expiry -->
            <div style="background: var(--dl-card-2); padding: 14px; border-radius: 8px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 6px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Monthly Expiry</span>
                <span class="badge" style="font-size: 0.68rem; background: var(--dl-track); padding: 2px 6px; border-radius: 4px; font-weight: 600;">Month-End</span>
              </div>
              <div class="mono-nums" style="font-size: 1.25rem; font-weight: 800; color: var(--dl-fg);">${fno.monthly_expiry || '-'}</div>
              <div style="font-size: 0.85rem; color: var(--dl-fg-2); font-family: var(--font-mono); font-weight: 700;">${fno.monthly_dte?.formatted || '-'}</div>
            </div>

            <!-- Put-Call Ratio (PCR) -->
            <div style="background: var(--dl-card-2); padding: 14px; border-radius: 8px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 6px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Put-Call Ratio (PCR)</span>
              </div>
              <div style="display: flex; align-items: baseline; gap: 14px;">
                <div><span style="font-size: 0.75rem; color: var(--dl-fg-3);">W: </span><strong class="mono-nums" style="font-size: 1.25rem; color: var(--dl-fg); font-weight: 800;">${dash(fno.weekly_pcr)}</strong></div>
                <div><span style="font-size: 0.75rem; color: var(--dl-fg-3);">M: </span><strong class="mono-nums" style="font-size: 1.25rem; color: var(--dl-fg); font-weight: 800;">${dash(fno.monthly_pcr)}</strong></div>
              </div>
              <div style="font-size: 0.78rem; color: ${!has(fno.weekly_pcr) ? 'var(--dl-fg-3)' : (fno.weekly_pcr > 1.2 ? 'var(--accent-sage)' : (fno.weekly_pcr < 0.8 ? 'var(--accent-coral)' : 'var(--dl-fg-2)'))}; font-weight: 700;">
                ${!has(fno.weekly_pcr) ? 'PCR unavailable' : (fno.weekly_pcr > 1.2 ? '▲ Bullish bias (>1.2)' : (fno.weekly_pcr < 0.8 ? '▼ Bearish bias (<0.8)' : '● Balanced band (0.8–1.2)'))}
              </div>
            </div>

            <!-- Max Pain & OI Walls -->
            <div style="background: var(--dl-card-2); padding: 14px; border-radius: 8px; border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 6px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700; text-transform: uppercase;">Max Pain & OI Walls</span>
              </div>
              <div class="mono-nums" style="font-size: 1.25rem; font-weight: 800; color: var(--accent-sage);">
                Pain: ${fno.max_pain ? fno.max_pain.toLocaleString('en-IN') : '-'}
              </div>
              <div style="font-size: 0.78rem; color: var(--dl-fg-3); display: flex; gap: 12px; font-weight: 600;">
                <span>Call Wall: <strong class="mono-nums" style="color: var(--accent-coral); font-size: 0.92rem; font-weight: 800;">${fno.max_call_oi_strike || '-'}</strong></span>
                <span>Put Wall: <strong class="mono-nums" style="color: var(--accent-sage); font-size: 0.92rem; font-weight: 800;">${fno.max_put_oi_strike || '-'}</strong></span>
              </div>
            </div>

          </div>

          <!-- Institutional Rows (FII Cash / FII F&O / DII Cash / DII F&O) — STRICTLY SEPARATE -->
          <div style="display: flex; flex-direction: column; gap: 10px; padding-top: 8px; border-top: 1px solid var(--dl-line);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span class="eyebrow" style="font-size: 0.74rem; color: var(--dl-fg-3); font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em;">Institutional Flow (Cash ₹ Cr vs F&O Contracts — Separate)</span>
              ${this.getBadgeHtml(inst.fii_cash_freshness || 'PREVIOUS SESSION')}
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
              
              <!-- FII Cash Row -->
              <div style="background: var(--dl-card-2); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700;">FII CASH (₹ Cr)</div>
                <div class="mono-nums" style="font-size: 1.2rem; font-weight: 800; color: ${fiiCashColor}; margin-top: 4px;">${fiiCashStr}</div>
              </div>

              <!-- FII F&O Row -->
              <div style="background: var(--dl-card-2); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700;">FII F&O (Contracts)</div>
                <div class="mono-nums" style="font-size: 1.2rem; font-weight: 800; color: var(--dl-fg); margin-top: 4px;">${inst.fii_fno_net_contracts || '-'}</div>
                <div style="font-size: 0.72rem; color: var(--dl-fg-2); margin-top: 2px;">${inst.fii_fno_detail || '-'}</div>
              </div>

              <!-- DII Cash Row -->
              <div style="background: var(--dl-card-2); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700;">DII CASH (₹ Cr)</div>
                <div class="mono-nums" style="font-size: 1.2rem; font-weight: 800; color: ${diiCashColor}; margin-top: 4px;">${diiCashStr}</div>
              </div>

              <!-- DII F&O Row -->
              <div style="background: var(--dl-card-2); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--dl-line);">
                <div style="font-size: 0.72rem; color: var(--dl-fg-3); font-weight: 700;">DII F&O (Contracts)</div>
                <div class="mono-nums" style="font-size: 1.2rem; font-weight: 800; color: var(--dl-fg); margin-top: 4px;">${inst.dii_fno_net_contracts || '-'}</div>
                <div style="font-size: 0.72rem; color: var(--dl-fg-2); margin-top: 2px;">${inst.dii_fno_detail || '-'}</div>
              </div>

            </div>
          </div>

          <!-- Rollover % (Conditional: ONLY displayed in last 3 sessions before monthly expiry) -->
          ${fno.is_rollover_window ? `
            <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(234, 179, 8, 0.1); border: 1px solid rgba(234, 179, 8, 0.3); padding: 10px 14px; border-radius: 8px; margin-top: 2px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1rem;">🔄</span>
                <span style="font-size: 0.85rem; font-weight: 700; color: var(--accent-amber);">Monthly Expiry Rollover Window Active</span>
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 0.78rem; color: var(--dl-fg-2); font-weight: 600;">Rollover:</span>
                <span class="mono-nums" style="font-size: 1.15rem; font-weight: 800; color: var(--accent-amber);">${fno.rollover_pct}%</span>
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

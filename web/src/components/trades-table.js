/**
 * Trades Table Component for Swayam Capital (BUILD-11).
 *
 * Implements historical Excel fields + live paper positions with row expansion,
 * editable AI lessons, and discipline tracking.
 */

import { formatINR } from '../utils/format.js';

export class TradesTableComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.trades = options.trades || [];
    this.expandedTradeId = null;
    this.onEditLesson = options.onEditLesson || (() => {});
    this.onGenerateLesson = options.onGenerateLesson || (() => {});
    this.onSort = options.onSort || (() => {});
    this.sortBy = options.sortBy || 'date_desc';
  }

  update(trades, sortBy = null) {
    this.trades = trades || [];
    if (sortBy) this.sortBy = sortBy;
    this.render();
  }

  toggleExpand(tradeId) {
    if (this.expandedTradeId === tradeId) {
      this.expandedTradeId = null;
    } else {
      this.expandedTradeId = tradeId;
    }
    this.render();
  }

  render() {
    if (!this.container) return;

    if (!this.trades.length) {
      this.container.innerHTML = `
        <div style="padding: 48px; text-align: center; color: var(--dl-fg-3); background: var(--dl-card); border-radius: var(--radius-card); border: 1px solid var(--dl-line);">
          <div style="font-size: 1.5rem; margin-bottom: 8px;">📖</div>
          <div style="font-weight: 600; color: var(--dl-fg-2); margin-bottom: 4px;">No Trades Found</div>
          <div style="font-size: 0.8rem;">No executed trades match the active filters. Execute a paper trade or relax filters.</div>
        </div>
      `;
      return;
    }

    const rowsHtml = this.trades.map((t) => {
      const isExpanded = this.expandedTradeId === t.position_id;
      const netPnl = t.net_pnl_inr || 0;
      const grossPnl = t.gross_pnl_inr || 0;
      const charges = t.charges_inr || 0;
      const formattedNetPnl = netPnl > 0 
        ? `+₹${Math.round(netPnl).toLocaleString('en-IN')}` 
        : netPnl < 0 
        ? `-₹${Math.abs(Math.round(netPnl)).toLocaleString('en-IN')}` 
        : `₹0`;
      const formattedGrossPnl = grossPnl > 0 
        ? `+₹${Math.round(grossPnl).toLocaleString('en-IN')}` 
        : grossPnl < 0 
        ? `-₹${Math.abs(Math.round(grossPnl)).toLocaleString('en-IN')}` 
        : `₹0`;
      const pnlColor = netPnl > 0 ? 'var(--accent-sage)' : netPnl < 0 ? 'var(--accent-coral)' : 'var(--dl-fg-2)';
      
      const openedDate = t.opened_at ? t.opened_at.substring(0, 10) : '—';
      const openedTime = t.opened_at && t.opened_at.length > 16 ? t.opened_at.substring(11, 16) : '';
      const isClosed = t.status === 'closed';

      // Discipline icon
      const rulesFollowed = t.rules_followed !== false;
      const disciplineHtml = rulesFollowed
        ? `<span style="display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; background: var(--accent-sage-tint, rgba(134,171,146,0.15)); color: var(--accent-sage); font-weight: 700; font-size: 0.75rem;" title="Discipline kept: all method rules followed">✓</span>`
        : `<span style="display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; background: var(--accent-coral-tint, rgba(221,129,112,0.15)); color: var(--accent-coral); font-weight: 700; font-size: 0.75rem;" title="${t.rules_broken_reason || 'Rule violation recorded'}">✗</span>`;

      // Direction Badge
      const dir = (t.directional_view || 'Neutral').toLowerCase();
      const dirBg = dir.includes('bull') ? 'var(--accent-sage-tint, rgba(134,171,146,0.15))' : dir.includes('bear') ? 'var(--accent-coral-tint, rgba(221,129,112,0.15))' : 'rgba(255,255,255,0.06)';
      const dirColor = dir.includes('bull') ? 'var(--accent-sage)' : dir.includes('bear') ? 'var(--accent-coral)' : 'var(--dl-fg-3)';

      return `
        <tr class="trade-row ${isExpanded ? 'expanded' : ''}" data-id="${t.position_id}" style="cursor: pointer; border-bottom: 1px solid var(--dl-line); transition: background 0.15s ease;">
          <td style="padding: 10px 12px; font-family: var(--font-mono, monospace); font-size: 0.76rem; white-space: nowrap;">
            <div style="color: var(--dl-fg); font-weight: 600;">${openedDate}</div>
            <div style="color: var(--dl-fg-3); font-size: 0.68rem;">${openedTime} IST</div>
          </td>
          <td style="padding: 10px 12px;">
            <div style="font-weight: 600; font-size: 0.82rem; color: var(--dl-fg);">${t.strategy_name}</div>
            <div style="font-size: 0.7rem; color: var(--dl-fg-3); margin-top: 1px; max-width: 200px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
              ${t.legs_summary || 'NIFTY options'}
            </div>
          </td>
          <td style="padding: 10px 12px; font-size: 0.75rem;">
            <div style="color: var(--dl-fg-2); font-weight: 500;">${t.setup_technical || 'Method Setup'}</div>
            <div style="color: var(--dl-fg-3); font-size: 0.68rem;">${t.setup_location || 'Key Level'}</div>
          </td>
          <td style="padding: 10px 12px;">
            <span style="display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; background: ${dirBg}; color: ${dirColor};">
              ${t.directional_view || 'Neutral'}
            </span>
          </td>
          <td style="padding: 10px 12px; font-family: var(--font-mono, monospace); font-size: 0.76rem;">
            <div style="color: var(--dl-fg-2);">${t.time_in_trade_str || '—'}</div>
            <div style="font-size: 0.68rem; color: var(--dl-fg-3);">${t.points_in_trade != null ? `${t.points_in_trade > 0 ? '+' : ''}${t.points_in_trade} pts` : '—'}</div>
          </td>
          <td style="padding: 10px 12px; font-family: var(--font-mono, monospace); font-size: 0.76rem; color: var(--dl-fg-3);">
            ₹${Math.round(charges).toLocaleString('en-IN')}
          </td>
          <td style="padding: 10px 12px; text-align: right; font-family: var(--font-mono, monospace); font-size: 0.82rem;">
            <div style="font-weight: 700; color: ${pnlColor};">
              ${formattedNetPnl}
            </div>
            <div style="font-size: 0.68rem; color: var(--dl-fg-3);">
              Gross: ${formattedGrossPnl}
            </div>
          </td>
          <td style="padding: 10px 12px; text-align: center; font-family: var(--font-mono, monospace); font-size: 0.76rem;">
            <div style="color: var(--accent-lilac); font-weight: 600;">
              ${t.rr_actual != null ? `1 : ${t.rr_actual.toFixed(2)}` : '—'}
            </div>
            <div style="font-size: 0.68rem; color: var(--dl-fg-3);">
              Plan: ${t.rr_planned != null ? `1:${t.rr_planned.toFixed(2)}` : '—'}
            </div>
          </td>
          <td style="padding: 10px 12px; text-align: center;">
            ${disciplineHtml}
          </td>
          <td style="padding: 10px 12px; text-align: center;">
            <span style="display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; background: ${isClosed ? 'rgba(255,255,255,0.06)' : 'var(--accent-sage-tint)'}; color: ${isClosed ? 'var(--dl-fg-3)' : 'var(--accent-sage)'};">
              ${t.status}
            </span>
          </td>
          <td style="padding: 10px 12px; text-align: right; color: var(--dl-fg-3); font-size: 0.8rem;">
            ${isExpanded ? '▲' : '▼'}
          </td>
        </tr>
        ${isExpanded ? this.renderExpandedDetails(t) : ''}
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="trades-table-card" style="background: var(--dl-card); border: none; border-radius: var(--radius-card); overflow: visible;">
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead style="position: sticky; top: 0; z-index: 4; background: var(--dl-card);">
              <tr style="background: var(--dl-card); border-bottom: 1px solid var(--dl-line); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3);">
                <th style="padding: 10px 12px; font-weight: 600; background: var(--dl-card);">Date / Time</th>
                <th style="padding: 10px 12px; font-weight: 600; background: var(--dl-card);">Strategy</th>
                <th style="padding: 10px 12px; font-weight: 600; background: var(--dl-card);">Setup / Loc</th>
                <th style="padding: 10px 12px; font-weight: 600; background: var(--dl-card);">Direction</th>
                <th style="padding: 10px 12px; font-weight: 600; background: var(--dl-card);">TIT / PIT</th>
                <th style="padding: 10px 12px; font-weight: 600; background: var(--dl-card);">Charges</th>
                <th style="padding: 10px 12px; text-align: right; font-weight: 600; background: var(--dl-card);">Net P&amp;L (Gross)</th>
                <th style="padding: 10px 12px; text-align: center; font-weight: 600; background: var(--dl-card);">R:R (Act/Plan)</th>
                <th style="padding: 10px 12px; text-align: center; font-weight: 600; background: var(--dl-card);">Disc.</th>
                <th style="padding: 10px 12px; text-align: center; font-weight: 600; background: var(--dl-card);">Status</th>
                <th style="padding: 10px 12px; text-align: right; font-weight: 600; background: var(--dl-card);"></th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Attach row click listeners for expansion
    this.container.querySelectorAll('.trade-row').forEach((tr) => {
      tr.addEventListener('click', (e) => {
        // Prevent expand toggle if clicking inside button or link
        if (e.target.closest('button') || e.target.closest('a') || e.target.closest('input')) return;
        const tid = tr.getAttribute('data-id');
        if (tid) this.toggleExpand(tid);
      });
    });

    // Attach button listeners inside expanded details
    this.container.querySelectorAll('.btn-edit-lesson').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const lid = btn.getAttribute('data-lesson-id');
        const ltext = btn.getAttribute('data-lesson-text');
        this.onEditLesson({ id: lid, lesson_text: ltext });
      });
    });

    this.container.querySelectorAll('.btn-generate-lesson').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const pid = btn.getAttribute('data-pos-id');
        this.onGenerateLesson(pid);
      });
    });
  }

  renderExpandedDetails(t) {
    const rulesFollowed = t.rules_followed !== false;
    const lessonText = t.lesson_text || 'No lesson recorded for this trade yet.';
    const lessonSource = t.lesson_source || 'ai_generated';
    const isUserEdited = lessonSource === 'user_edited';

    return `
      <tr class="expanded-detail-row" style="background: rgba(0,0,0,0.25); border-bottom: 2px solid var(--dl-line);">
        <td colspan="11" style="padding: 16px 20px;">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
            
            <!-- Context & Setup -->
            <div style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: 6px; padding: 12px 14px;">
              <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600; margin-bottom: 8px;">
                📐 Trade Context &amp; Rationale
              </div>
              <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem;">
                <div><strong style="color: var(--dl-fg-2);">Technical Trigger:</strong> <span style="color: var(--dl-fg);">${t.setup_technical || 'Standard breakout'}</span></div>
                <div><strong style="color: var(--dl-fg-2);">Setup Location:</strong> <span style="color: var(--dl-fg);">${t.setup_location || 'Key support/resistance level'}</span></div>
                <div><strong style="color: var(--dl-fg-2);">Moneyness &amp; Structure:</strong> <span style="color: var(--dl-fg);">${t.moneyness_summary || t.legs_summary || 'Standard option spread'}</span></div>
                <div><strong style="color: var(--dl-fg-2);">Trend Alignment:</strong> <span style="color: var(--dl-fg);">${t.with_or_against_trend || 'With Trend'}</span></div>
                <div><strong style="color: var(--dl-fg-2);">Exit Reason:</strong> <span style="color: var(--dl-fg);">${t.exit_reason || 'Manual / Target'}</span></div>
                ${t.entry_rationale ? `<div><strong style="color: var(--dl-fg-2);">Entry Notes:</strong> <span style="color: var(--dl-fg-3); font-style: italic;">"${t.entry_rationale}"</span></div>` : ''}
                ${t.exit_rationale ? `<div><strong style="color: var(--dl-fg-2);">Exit Notes:</strong> <span style="color: var(--dl-fg-3); font-style: italic;">"${t.exit_rationale}"</span></div>` : ''}
              </div>
            </div>

            <!-- Discipline Audit -->
            <div style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: 6px; padding: 12px 14px;">
              <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600; margin-bottom: 8px;">
                🛡️ Method &amp; Discipline Audit
              </div>
              <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.78rem;">
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="font-weight: 600; color: ${rulesFollowed ? 'var(--accent-sage)' : 'var(--accent-coral)'};">
                    ${rulesFollowed ? '✓ 100% Rules Followed' : '✗ Discipline Violation Recorded'}
                  </span>
                </div>
                ${!rulesFollowed && t.rules_broken_reason ? `
                  <div style="padding: 8px 10px; border-radius: 4px; background: var(--accent-coral-tint); border: 1px solid rgba(221,129,112,0.3); color: var(--accent-coral); font-size: 0.75rem;">
                    <strong>Violation:</strong> ${t.rules_broken_reason}
                  </div>
                ` : `
                  <div style="color: var(--dl-fg-3); font-size: 0.74rem;">
                    Trade was managed strictly according to written position sizing, stop-loss ceiling, and entry criteria.
                  </div>
                `}
                ${t.journal_path ? `
                  <div style="margin-top: 6px; font-size: 0.72rem; color: var(--dl-fg-3); font-family: var(--font-mono, monospace);">
                    Obsidian Vault: <span style="color: var(--accent-lilac);">${t.journal_path}</span>
                  </div>
                ` : ''}
              </div>
            </div>

            <!-- AI Lesson Ledger -->
            <div style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: 6px; padding: 12px 14px; display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                  <span style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600;">
                    💡 Lesson Ledger
                  </span>
                  <span style="font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.06); color: var(--accent-lilac); font-weight: 600;">
                    ${isUserEdited ? 'Refined by Abhishek' : 'AI Trading Partner'}
                  </span>
                </div>
                <p style="margin: 0; font-size: 0.8rem; line-height: 1.4; color: var(--dl-fg); font-style: italic; border-left: 2px solid var(--accent-lilac); padding-left: 10px;">
                  "${lessonText}"
                </p>
              </div>
              <div style="margin-top: 12px; display: flex; gap: 8px; justify-content: flex-end;">
                ${t.lesson_id ? `
                  <button type="button" class="btn-edit-lesson" data-lesson-id="${t.lesson_id}" data-lesson-text="${encodeURIComponent(lessonText)}" style="background: transparent; border: 1px solid var(--dl-line); color: var(--dl-fg-2); border-radius: 4px; padding: 4px 10px; font-size: 0.72rem; cursor: pointer;">
                    ✏️ Refine Lesson
                  </button>
                ` : `
                  <button type="button" class="btn-generate-lesson" data-pos-id="${t.position_id}" style="background: var(--accent-lilac); border: none; color: #101116; font-weight: 600; border-radius: 4px; padding: 4px 10px; font-size: 0.72rem; cursor: pointer;">
                    ✨ Generate AI Lesson
                  </button>
                `}
              </div>
            </div>

          </div>
        </td>
      </tr>
    `;
  }
}
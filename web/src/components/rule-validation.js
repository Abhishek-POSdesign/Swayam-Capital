/**
 * Rule Validation Panel Component for Swayam Capital.
 *
 * Displays the two-tier risk model verdicts side-by-side:
 * 1. Realistic Risk Cap (2σ, 20d realized vol) - primary everyday sizing gate.
 * 2. Blast Radius Fuse (absolute mathematical max loss) - emergency black-swan ceiling.
 *
 * Both caps must pass for the Execute Paper Trade button to be enabled.
 */

import { formatINR } from '../utils/format.js';

export function renderRuleValidation(container, val, options = {}) {
  if (!container || !val) return;

  const isRealisticPass = Boolean(val.realistic_risk?.passed);
  const isBlastPass = Boolean(val.blast_radius?.passed);
  const isPassed = Boolean(val.overall_passed ?? (val.passed && isRealisticPass && isBlastPass));

  const realisticTooltip =
    'The primary decision variable: compares to how much the spread would lose if NIFTY moves 2× its usual daily move (2σ of 20-day realized volatility). A bad day, not the apocalypse.';
  const blastTooltip =
    'The last-resort ceiling: compares to the absolute mathematical worst case (spot going to zero or infinity). Ensures account survival even in black swans.';

  const otherChecks = (val.checks || []).filter(
    (c) => c.rule !== 'realistic_risk' && c.rule !== 'blast_radius' && c.rule !== 'per_trade_risk_cap'
  );

  const checksHtml = otherChecks
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
          <div class="mono" style="font-size: 0.8rem; font-weight: 600; color: ${isPass ? 'var(--green, #26a69a)' : 'var(--red, #ef5350)'};">
            ${icon} ${c.verdict}
          </div>
        </div>
      `;
    })
    .join('');

  container.innerHTML = `
    <div class="panel">
      <div class="panel-title" style="display: flex; justify-content: space-between; align-items: center;">
        <span>RULE VALIDATION</span>
        <span style="font-size: 0.8rem; color: var(--text-secondary);">Two-Tier Risk Gating</span>
      </div>

      <!-- Two-tier risk verdicts side-by-side -->
      <div class="two-tier-risk-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin: 0.75rem 0 1rem 0;">
        <!-- Tier 1: Realistic Risk -->
        <div class="risk-badge realistic-risk-badge ${isRealisticPass ? 'verdict-pass' : 'verdict-fail'}"
             data-testid="realistic-risk-badge"
             title="${realisticTooltip}"
             style="padding: 0.65rem; border-radius: 6px; border: 1px solid ${isRealisticPass ? 'rgba(38,166,154,0.4)' : 'rgba(239,83,80,0.4)'}; background: ${isRealisticPass ? 'rgba(38,166,154,0.08)' : 'rgba(239,83,80,0.08)'}; cursor: help;">
          <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: ${isRealisticPass ? 'var(--green, #26a69a)' : 'var(--red, #ef5350)'};">
            Realistic Risk (2σ, 20d vol)
          </div>
          <div class="mono" style="font-size: 0.95rem; font-weight: 700; margin: 0.3rem 0; color: ${isRealisticPass ? 'var(--green, #26a69a)' : 'var(--red, #ef5350)'};">
            ${isRealisticPass ? '✅' : '❌'} ${formatINR(val.realistic_risk?.loss_inr ?? 0)} / ${formatINR(val.realistic_risk?.cap_inr ?? 0)}
          </div>
          <div style="font-size: 0.72rem; color: var(--text-secondary);">
            (${Number(val.realistic_risk?.pct_of_margin ?? 0).toFixed(2)}% of margin base)
          </div>
        </div>

        <!-- Tier 2: Blast Radius Fuse -->
        <div class="risk-badge blast-radius-badge ${isBlastPass ? 'verdict-pass' : 'verdict-fail'}"
             data-testid="blast-radius-badge"
             title="${blastTooltip}"
             style="padding: 0.65rem; border-radius: 6px; border: 1px solid ${isBlastPass ? 'rgba(38,166,154,0.4)' : 'rgba(239,83,80,0.4)'}; background: ${isBlastPass ? 'rgba(38,166,154,0.08)' : 'rgba(239,83,80,0.08)'}; cursor: help;">
          <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: ${isBlastPass ? 'var(--green, #26a69a)' : 'var(--red, #ef5350)'};">
            Blast Radius (max loss)
          </div>
          <div class="mono" style="font-size: 0.95rem; font-weight: 700; margin: 0.3rem 0; color: ${isBlastPass ? 'var(--green, #26a69a)' : 'var(--red, #ef5350)'};">
            ${isBlastPass ? '✅' : '❌'} ${formatINR(val.blast_radius?.loss_inr ?? 0)} / ${formatINR(val.blast_radius?.cap_inr ?? 0)}
          </div>
          <div style="font-size: 0.72rem; color: var(--text-secondary);">
            (${Number(val.blast_radius?.pct_of_margin ?? 0).toFixed(2)}% of margin base)
          </div>
        </div>
      </div>

      <div class="validation-list" style="margin-bottom: 0.75rem;">
        ${checksHtml}
      </div>

      <div class="verdict-banner ${isPassed ? 'verdict-pass' : 'verdict-fail'}" data-testid="overall-verdict-banner">
        ${isPassed ? 'VERDICT: ✅ PASSED METHOD AUDIT' : 'VERDICT: ❌ BLOCKED BY METHOD RULES'}
      </div>

      <div>
        <button id="btn-execute-trade" class="primary" style="width: 100%; padding: 0.75rem;" ${isPassed ? '' : 'disabled'} data-testid="execute-trade-button">
          ⚡ EXECUTE PAPER TRADE
        </button>
      </div>

      <div id="tv-button-container" style="margin-top: 0.75rem;"></div>
    </div>
  `;

  // Attach TradingView button
  import('./tv-buttons.js').then(({ renderTvButton }) => {
    const tvContainer = document.getElementById('tv-button-container');
    if (tvContainer) renderTvButton(tvContainer, 'NSE:NIFTY50');
  }).catch(() => {});

  // Attach execution click handler
  const execBtn = document.getElementById('btn-execute-trade');
  if (execBtn && typeof options.onExecute === 'function') {
    execBtn.addEventListener('click', options.onExecute);
  }
}

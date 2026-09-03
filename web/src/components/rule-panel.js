/**
 * Rule Panel component: Renders active Obsidian Method rules and limits.
 */

import { formatINR, formatPercent } from '../utils/format.js';

export function renderRulePanel(container, rules) {
  if (!rules) {
    container.innerHTML = `
      <div class="panel">
        <div class="panel-title">METHOD RULES</div>
        <p style="color: var(--text-secondary); font-size: 0.85rem;">Loading rules from vault...</p>
      </div>
    `;
    return;
  }

  const obsidianDeepLink =
    'obsidian://open?vault=Second%20Brain&file=02%20-%20Projects%2FTrading%2F01%20-%20Method%2FRisk%20Management%20Rules.md';

  container.innerHTML = `
    <div class="panel">
      <div class="panel-title">
        <span>RULE PANEL</span>
        <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: normal;">From Obsidian</span>
      </div>

      <div class="rule-list">
        <div class="rule-item">
          <span>Per-Trade Risk Cap</span>
          <span class="mono">${formatPercent(rules.per_trade_risk_pct)} (${formatINR(rules.per_trade_risk_cap_inr)})</span>
        </div>
        <div class="rule-item">
          <span>R:R Minimum Floor</span>
          <span class="mono">1:${rules.rr_minimum.toFixed(1)}</span>
        </div>
        <div class="rule-item">
          <span>Daily Loss Cap</span>
          <span class="mono">${formatPercent(rules.daily_loss_cap_pct)} (${formatINR(rules.daily_loss_cap_inr)})</span>
        </div>
        <div class="rule-item">
          <span>Weekly Loss Cap</span>
          <span class="mono">${formatPercent(rules.weekly_loss_cap_pct)} (${formatINR(rules.weekly_loss_cap_inr)})</span>
        </div>
        <div class="rule-item">
          <span>Blast Radius Fuse</span>
          <span class="mono">${formatPercent(rules.blast_radius_pct)} (${formatINR(rules.blast_radius_cap_inr)})</span>
        </div>
        <div class="rule-item">
          <span>Overnight Hedge Cap</span>
          <span class="mono">${formatPercent(rules.overnight_hedge_cap_pct)} (${formatINR(rules.overnight_hedge_cap_inr)})</span>
        </div>
        <div class="rule-item">
          <span>Alcohol Lockout</span>
          <span class="mono">${rules.alcohol_lockout_days} days</span>
        </div>
        <div class="rule-item">
          <span>Sleep Gate</span>
          <span class="mono">&lt; ${rules.sleep_no_trade_threshold_hours} hrs = No Trade</span>
        </div>
      </div>

      <div style="margin-top: 1.25rem;">
        <a href="${obsidianDeepLink}" style="text-decoration: none;">
          <button style="width: 100%; font-size: 0.8rem;">
            📝 Edit rules in Obsidian
          </button>
        </a>
      </div>
    </div>
  `;
}

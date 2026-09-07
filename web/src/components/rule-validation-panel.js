/**
 * Rule panel for Swayam Capital.
 *
 * Shows the four rules Abhishek settled on 2026-09-08, and nothing else:
 *
 *   1. Running loss    1% of the live FYERS balance
 *   2. Overnight gap   2%, tested at twice the average daily move
 *   3. Black swan      5%, the absolute worst case at expiry
 *   4. Deployable margin ceiling, twice the cash-equivalent holding
 *
 * Two rules govern every line rendered here.
 *
 * NO FABRICATED VALUES. This component previously invented a reward ratio of
 * 1:2.63, a daily headroom of Rs 15,875, a weekly headroom of Rs 35,875 and a
 * whole risk verdict of Rs 4,125 against a Rs 10,000 cap, and showed all of
 * them as though they were his. Every one of those has been deleted. A number
 * that is not in the response now renders as "unavailable" with the reason.
 *
 * NO DOUBLE CONVERSION. `pct_of_margin` arrives from the server ALREADY a
 * percentage: 0.62 means 0.62%. This file used to multiply it by 100 again and
 * print 62%, overstating his risk a hundredfold. Do not reintroduce that. The
 * field the backend nominates for display is `arithmetic`, which states the
 * whole sum in words, and it is preferred here wherever it is present.
 *
 * Entry is never blocked. Only carrying overnight is gated. The panel says so
 * plainly, because a red badge that does not stop anything trains him to
 * ignore red badges.
 */

const UNAVAILABLE = 'unavailable';

/** Formats rupees the way he reads them, or returns null so the caller can say why not. */
function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return `₹${Math.round(Number(value)).toLocaleString('en-IN')}`;
}

/** `pct_of_margin` is already a percentage. Never multiply it again. */
function percent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return `${Number(value).toFixed(2)}%`;
}

function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

export class RuleValidationPanelComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.validationData = null;
    this.hasNakedShorts = false;
  }

  /**
   * @param {object|null} validationData The /api/validate response, or null.
   * @param {boolean} hasNakedShorts Retained for callers; the server's hedge
   *   geometry check is authoritative and is what is actually rendered.
   */
  render(validationData = null, hasNakedShorts = false) {
    this.validationData = validationData;
    this.hasNakedShorts = hasNakedShorts;

    if (!validationData) {
      this.container.innerHTML = this.emptyState();
      return;
    }

    const checks = Array.isArray(validationData.checks) ? validationData.checks : [];
    const checkFor = (name) => checks.find((c) => c.rule === name) || null;

    const rows = [
      this.runningLossRow(validationData),
      this.overnightGapRow(validationData),
      this.blackSwanRow(validationData),
      this.marginCeilingRow(checkFor('deployable_margin_ceiling')),
    ].join('');

    this.container.innerHTML = `
      <div class="rule-validation-panel" style="display:flex;flex-direction:column;gap:10px;">
        ${this.entryBanner(validationData)}
        <div style="display:flex;flex-direction:column;gap:8px;">${rows}</div>
        ${this.structureRow(checkFor('hedged_structure'))}
        ${this.capitalFooter(validationData.capital)}
        ${this.warnings(validationData)}
      </div>
    `;
  }

  // ---------------------------------------------------------------- states

  emptyState() {
    return `
      <div class="rule-validation-panel" style="
        background:var(--dl-card-2);border:1px dashed var(--dl-line);
        border-radius:var(--radius-card);padding:18px;text-align:center;">
        <div style="font-size:0.85rem;color:var(--dl-fg-2);">
          No rule check yet. Build a position and the four rules will be measured
          against your live balance.
        </div>
      </div>
    `;
  }

  /**
   * The most important sentence on the screen: an entry is never refused.
   * Only carrying overnight is gated, and only when hedged and inside the gap test.
   */
  entryBanner(data) {
    const intraday = data.intraday !== false;
    const blocked = data.execution_blocked_reason;

    if (blocked) {
      return `
        <div style="
          background:var(--accent-amber-tint);border:1px solid var(--accent-amber);
          border-radius:var(--radius-card);padding:11px 14px;">
          <div style="font-family:var(--font-mono);font-size:0.68rem;letter-spacing:0.1em;
                      text-transform:uppercase;color:var(--accent-amber);font-weight:700;">
            Can be studied, not executed
          </div>
          <div style="font-size:0.83rem;color:var(--dl-fg);margin-top:4px;">
            ${escapeHtml(blocked)}
          </div>
        </div>
      `;
    }

    const text = intraday
      ? 'Intraday entry. Nothing here blocks you, including a half-built or naked structure.'
      : 'Marked to be carried overnight, so the gap test below applies.';

    return `
      <div style="
        background:var(--dl-card-2);border:1px solid var(--dl-line);
        border-radius:var(--radius-card);padding:10px 14px;">
        <div style="font-size:0.82rem;color:var(--dl-fg-2);">${escapeHtml(text)}</div>
      </div>
    `;
  }

  // ----------------------------------------------------------------- rules

  /** Rule 1. Running loss, 1% of the live balance. */
  runningLossRow(data) {
    const v = data.realistic_risk;
    if (!v) {
      return this.ruleRow({
        n: '1', title: 'Running loss', cap: '1% of live balance',
        unavailable: 'no verdict returned',
      });
    }

    return this.ruleRow({
      n: '1',
      title: 'Running loss',
      cap: '1% of live balance',
      figure: money(v.loss_inr),
      capFigure: money(v.cap_inr),
      pct: percent(v.pct_of_margin),
      passed: v.passed,
      arithmetic: v.arithmetic,
      unavailable: (v.loss_inr === null || v.loss_inr === undefined)
        ? 'the loss could not be computed' : null,
    });
  }

  /** Rule 2. Overnight gap, 2%, at twice the average daily move. */
  overnightGapRow(data) {
    const intraday = data.intraday !== false;
    const carry = data.carry;

    if (intraday || !carry) {
      return this.ruleRow({
        n: '2',
        title: 'Overnight gap',
        cap: '2% of live balance',
        note: 'Not tested. This is an intraday position. Give it a planned exit date beyond today to test carrying it.',
      });
    }

    const move = carry.move;
    const detail = move
      ? `Gapped ${move.gap_tested_points} points either way, twice the ${move.average_daily_move_points}-point average of your last ${move.sessions_used} sessions.`
      : null;

    return this.ruleRow({
      n: '2',
      title: 'Overnight gap',
      cap: '2% of live balance',
      figure: (carry.gap_loss_inr === null || carry.gap_loss_inr === undefined)
        ? 'Unlimited' : money(carry.gap_loss_inr),
      capFigure: money(carry.cap_inr),
      passed: carry.may_carry_overnight,
      arithmetic: carry.arithmetic,
      note: detail,
      reasons: carry.reasons,
    });
  }

  /** Rule 3. Black swan, 5%, the absolute worst case at expiry. */
  blackSwanRow(data) {
    const v = data.blast_radius;
    const unlimited = data.max_loss_is_unlimited === true;

    if (unlimited) {
      return this.ruleRow({
        n: '3',
        title: 'Black swan',
        cap: '5% of live balance',
        figure: 'Unlimited',
        capFigure: v ? money(v.cap_inr) : null,
        passed: false,
        note: 'The loss at expiry has no ceiling, so it cannot be compared to a cap. Fine intraday. Hedge it into a butterfly or a condor and it becomes measurable.',
      });
    }

    if (!v) {
      return this.ruleRow({
        n: '3', title: 'Black swan', cap: '5% of live balance',
        unavailable: 'no verdict returned',
      });
    }

    return this.ruleRow({
      n: '3',
      title: 'Black swan',
      cap: '5% of live balance',
      figure: money(v.loss_inr),
      capFigure: money(v.cap_inr),
      pct: percent(v.pct_of_margin),
      passed: v.passed,
      arithmetic: v.arithmetic,
    });
  }

  /** Rule 4. Deployable margin ceiling, twice the cash-equivalent holding. */
  marginCeilingRow(check) {
    if (!check) {
      return this.ruleRow({
        n: '4', title: 'Deployable margin', cap: '2x cash equivalent',
        unavailable: 'not returned by the server',
      });
    }
    // This rule is a ceiling, not a consumption figure. The server sends the
    // limit in cap_inr and never fills actual_inr, so showing "unavailable"
    // here would be wrong: the number IS available, it is just a headroom.
    const ceiling = money(check.cap_inr);
    if (!ceiling) {
      return this.ruleRow({
        n: '4', title: 'Deployable margin', cap: '2x cash equivalent',
        unavailable: check.note || 'the ceiling could not be derived from your holdings',
      });
    }
    return this.ruleRow({
      n: '4',
      title: 'Deployable margin',
      cap: '2x cash equivalent',
      figure: ceiling,
      passed: check.verdict === 'PASS',
      note: 'This is your ceiling, not what this position uses. The broker refuses more than this.',
    });
  }

  /** Hedge geometry. Not one of the four numbers, but it decides rule 2. */
  structureRow(check) {
    if (!check) return '';
    const ok = check.verdict === 'PASS';
    const colour = ok ? 'var(--accent-sage)' : 'var(--accent-amber)';
    const tint = ok ? 'var(--accent-sage-tint)' : 'var(--accent-amber-tint)';
    return `
      <div style="
        background:${tint};border:1px solid ${colour};border-radius:var(--radius-card);
        padding:10px 14px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;">
        <span style="font-family:var(--font-mono);font-size:0.68rem;letter-spacing:0.09em;
                     text-transform:uppercase;color:${colour};font-weight:700;">
          ${ok ? 'Hedged' : 'Not hedged'}
        </span>
        <span style="font-size:0.81rem;color:var(--dl-fg-2);flex:1 1 200px;">
          ${escapeHtml(check.note || (ok
            ? 'Every short leg is covered.'
            : 'A short leg is uncovered, so this cannot be carried overnight.'))}
        </span>
      </div>
    `;
  }

  // ------------------------------------------------------------- rendering

  /**
   * One rule. Renders a real verdict, or says plainly that it is unavailable.
   * It never substitutes a number.
   */
  ruleRow({ n, title, cap, figure, capFigure, pct, passed, arithmetic, note, reasons, unavailable }) {
    const hasVerdict = passed === true || passed === false;
    const colour = !hasVerdict
      ? 'var(--dl-fg-3)'
      : (passed ? 'var(--accent-sage)' : 'var(--accent-coral)');
    const badge = !hasVerdict ? '—' : (passed ? 'PASS' : 'FAIL');

    const value = (unavailable || !figure)
      ? `<span style="color:var(--dl-fg-3);font-style:italic;">${UNAVAILABLE}</span>`
      : `<span style="font-family:var(--font-mono);font-size:1.18rem;font-weight:700;
                      color:var(--dl-fg);font-variant-numeric:tabular-nums;">${escapeHtml(figure)}</span>`;

    const against = (capFigure && !unavailable)
      ? `<span style="font-size:0.76rem;color:var(--dl-fg-2);">against ${escapeHtml(capFigure)}${pct ? ` · ${escapeHtml(pct)} of balance` : ''}</span>`
      : '';

    const why = arithmetic
      ? `<div style="font-family:var(--font-mono);font-size:0.71rem;color:var(--dl-fg-3);
                     margin-top:6px;line-height:1.5;">${escapeHtml(arithmetic)}</div>`
      : '';

    const extra = note
      ? `<div style="font-size:0.78rem;color:var(--dl-fg-2);margin-top:5px;">${escapeHtml(note)}</div>`
      : '';

    const carryReasons = (Array.isArray(reasons) && reasons.length)
      ? `<div style="font-size:0.78rem;color:var(--dl-fg-2);margin-top:5px;">${escapeHtml(reasons.join(' '))}</div>`
      : '';

    const reason = unavailable
      ? `<div style="font-size:0.76rem;color:var(--dl-fg-3);margin-top:5px;">Why: ${escapeHtml(unavailable)}</div>`
      : '';

    return `
      <div style="
        background:var(--dl-card-2);border:1px solid var(--dl-line);
        border-left:3px solid ${colour};border-radius:var(--radius-card);padding:12px 14px;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;">
          <div style="flex:1 1 220px;">
            <div style="font-family:var(--font-mono);font-size:0.68rem;letter-spacing:0.09em;
                        text-transform:uppercase;color:var(--dl-fg-3);font-weight:700;">
              Rule ${n} · ${escapeHtml(title)} · ${escapeHtml(cap)}
            </div>
            <div style="display:flex;align-items:baseline;gap:9px;margin-top:5px;flex-wrap:wrap;">
              ${value}
              ${against}
            </div>
          </div>
          <span style="font-family:var(--font-mono);font-size:0.72rem;font-weight:700;
                       letter-spacing:0.05em;color:${colour};">${badge}</span>
        </div>
        ${why}${extra}${carryReasons}${reason}
      </div>
    `;
  }

  /** Every figure names where it came from and when it was read. */
  capitalFooter(capital) {
    if (!capital) {
      return `
        <div style="font-size:0.75rem;color:var(--dl-fg-3);font-style:italic;">
          Balance unavailable, so the caps above could not be derived from it.
        </div>
      `;
    }
    const bal = money(capital.risk_capital_inr);
    const when = capital.taken_at
      ? String(capital.taken_at).replace('T', ' ').slice(0, 16)
      : null;
    return `
      <div style="font-family:var(--font-mono);font-size:0.7rem;color:var(--dl-fg-3);
                  border-top:1px solid var(--dl-line);padding-top:8px;line-height:1.6;">
        Caps derived from a live balance of ${escapeHtml(bal || UNAVAILABLE)}
        ${capital.source ? `· ${escapeHtml(capital.source)}` : ''}
        ${when ? `· read ${escapeHtml(when)}` : ''}
      </div>
    `;
  }

  warnings(data) {
    const list = Array.isArray(data.warnings) ? data.warnings.filter(Boolean) : [];
    if (!list.length) return '';
    return `
      <div style="
        background:var(--accent-amber-tint);border:1px solid var(--accent-amber);
        border-radius:var(--radius-card);padding:10px 14px;">
        <div style="font-family:var(--font-mono);font-size:0.66rem;letter-spacing:0.1em;
                    text-transform:uppercase;color:var(--accent-amber);font-weight:700;margin-bottom:5px;">
          Worth knowing
        </div>
        <ul style="margin:0;padding-left:17px;font-size:0.79rem;color:var(--dl-fg);line-height:1.55;">
          ${list.map((w) => `<li>${escapeHtml(w)}</li>`).join('')}
        </ul>
      </div>
    `;
  }
}

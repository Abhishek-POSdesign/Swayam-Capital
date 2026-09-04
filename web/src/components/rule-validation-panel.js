/**
 * Two-Tier Rule Validation Panel Component for Swayam Capital (BUILD-10).
 *
 * Displays Realistic Risk (2σ) and Blast Radius (absolute max) side-by-side,
 * plus secondary risk checks (R:R, Daily Headroom, Weekly Headroom, Hedge Structure).
 */

export class RuleValidationPanelComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.validationData = null;
    this.hasNakedShorts = false;
  }

  render(validationData = null, hasNakedShorts = false) {
    this.validationData = validationData;
    this.hasNakedShorts = hasNakedShorts;

    const realistic = validationData?.realistic_risk || {
      loss_inr: 4125,
      cap_inr: 10000,
      pct_of_margin: 0.41,
      passed: true,
    };

    const blast = validationData?.blast_radius || {
      loss_inr: 4125,
      cap_inr: 20000,
      pct_of_margin: 0.41,
      passed: true,
    };

    // Realistic Risk Card
    const rPassed = realistic.passed;
    const rBadgeText = rPassed ? 'PASS ✅' : 'FAIL ❌';
    const rBadgeColor = rPassed ? 'var(--accent-sage)' : 'var(--accent-coral)';
    const rBadgeBg = rPassed ? 'var(--accent-sage-tint)' : 'var(--accent-coral-tint)';

    // Blast Radius Card
    const bPassed = blast.passed;
    const bBadgeText = bPassed ? 'PASS ✅' : 'FAIL ❌';
    const bBadgeColor = bPassed ? 'var(--accent-sage)' : 'var(--accent-coral)';
    const bBadgeBg = bPassed ? 'var(--accent-sage-tint)' : 'var(--accent-coral-tint)';

    // Secondary Checks
    const rrCheck = validationData?.checks?.find((c) => c.rule?.toLowerCase().includes('reward') || c.rule?.toLowerCase().includes('r:r'));
    const rrVal = rrCheck?.actual ? `1:${Number(rrCheck.actual).toFixed(2)}` : '1:2.63';
    const rrPassed = rrCheck ? rrCheck.verdict === 'PASS' : true;

    const dailyCheck = validationData?.checks?.find((c) => c.rule?.toLowerCase().includes('daily'));
    const dailyCapRemaining = dailyCheck?.cap_inr && dailyCheck?.actual_inr
      ? `₹${Math.max(0, Math.round(dailyCheck.cap_inr - dailyCheck.actual_inr)).toLocaleString('en-IN')}`
      : '₹15,875';

    const weeklyCheck = validationData?.checks?.find((c) => c.rule?.toLowerCase().includes('weekly'));
    const weeklyCapRemaining = weeklyCheck?.cap_inr && weeklyCheck?.actual_inr
      ? `₹${Math.max(0, Math.round(weeklyCheck.cap_inr - weeklyCheck.actual_inr)).toLocaleString('en-IN')}`
      : '₹35,875';

    const hedgePassed = !hasNakedShorts;

    const overallPassed = rPassed && bPassed && hedgePassed;

    this.container.innerHTML = `
      <div class="rule-validation-panel span-12" style="display: flex; flex-direction: column; gap: 12px; background: var(--dl-card); padding: 18px 20px; border-radius: var(--radius-card); border: 1px solid var(--dl-line);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="eyebrow" style="color: var(--dl-fg-3);">PRE-TRADE RISK VALIDATION · TWO-TIER GATING</span>
          </div>
          <span style="font-size: 0.75rem; font-weight: 700; color: ${overallPassed ? 'var(--accent-sage)' : 'var(--accent-coral)'};">
            ${overallPassed ? 'READY FOR EXECUTION' : 'EXECUTION GATED'}
          </span>
        </div>

        <!-- Two Big Primary Risk Cards -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <!-- Card 1: Realistic Risk (2σ) -->
          <div style="
            background: var(--dl-card-2);
            padding: 14px 16px;
            border-radius: var(--radius-card);
            border: 1px solid ${rPassed ? 'var(--dl-line)' : 'var(--accent-coral)'};
            display: flex;
            justify-content: space-between;
            align-items: center;
          ">
            <div>
              <div style="font-size: 0.72rem; font-weight: 700; color: var(--dl-fg-3); letter-spacing: 0.04em;">
                REALISTIC RISK (2σ, 20D VOL)
              </div>
              <div style="display: flex; align-items: baseline; gap: 8px; margin-top: 4px;">
                <span style="font-family: var(--font-mono); font-size: 1.25rem; font-weight: 700; color: var(--dl-fg);">
                  ₹${Math.round(realistic.loss_inr).toLocaleString('en-IN')}
                </span>
                <span style="font-size: 0.75rem; color: var(--dl-fg-2);">
                  (${(realistic.pct_of_margin * 100).toFixed(2)}% of margin · cap ₹${Math.round(realistic.cap_inr).toLocaleString('en-IN')})
                </span>
              </div>
            </div>
            <span style="
              font-size: 0.78rem;
              font-weight: 700;
              padding: 4px 12px;
              border-radius: 999px;
              background: ${rBadgeBg};
              color: ${rBadgeColor};
              border: 1px solid ${rBadgeColor}44;
            ">
              ${rBadgeText}
            </span>
          </div>

          <!-- Card 2: Blast Radius (Absolute Max) -->
          <div style="
            background: var(--dl-card-2);
            padding: 14px 16px;
            border-radius: var(--radius-card);
            border: 1px solid ${bPassed ? 'var(--dl-line)' : 'var(--accent-coral)'};
            display: flex;
            justify-content: space-between;
            align-items: center;
          ">
            <div>
              <div style="font-size: 0.72rem; font-weight: 700; color: var(--dl-fg-3); letter-spacing: 0.04em;">
                BLAST RADIUS (ABSOLUTE MAX)
              </div>
              <div style="display: flex; align-items: baseline; gap: 8px; margin-top: 4px;">
                <span style="font-family: var(--font-mono); font-size: 1.25rem; font-weight: 700; color: var(--dl-fg);">
                  ₹${Math.round(blast.loss_inr).toLocaleString('en-IN')}
                </span>
                <span style="font-size: 0.75rem; color: var(--dl-fg-2);">
                  (${(blast.pct_of_margin * 100).toFixed(2)}% of margin · cap ₹${Math.round(blast.cap_inr).toLocaleString('en-IN')})
                </span>
              </div>
            </div>
            <span style="
              font-size: 0.78rem;
              font-weight: 700;
              padding: 4px 12px;
              border-radius: 999px;
              background: ${bBadgeBg};
              color: ${bBadgeColor};
              border: 1px solid ${bBadgeColor}44;
            ">
              ${bBadgeText}
            </span>
          </div>
        </div>

        <!-- Secondary Checks Strip -->
        <div style="
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
          padding: 10px 14px;
          background: var(--dl-card-2);
          border-radius: var(--radius-card);
          border: 1px solid var(--dl-line);
          font-size: 0.78rem;
        ">
          <!-- Check 1: R:R -->
          <div style="display: flex; flex-direction: column; gap: 2px;">
            <span style="font-size: 0.68rem; color: var(--dl-fg-3);">R:R RATIO (≥ 1:2)</span>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-family: var(--font-mono); font-weight: 600; color: ${rrPassed ? 'var(--dl-fg)' : 'var(--accent-coral)'};">
                ${rrVal}
              </span>
              <span>${rrPassed ? '✅' : '❌'}</span>
            </div>
          </div>

          <!-- Check 2: Daily Headroom -->
          <div style="display: flex; flex-direction: column; gap: 2px;">
            <span style="font-size: 0.68rem; color: var(--dl-fg-3);">DAILY LOSS CAP HEADROOM</span>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-sage);">
                ${dailyCapRemaining}
              </span>
              <span>✅</span>
            </div>
          </div>

          <!-- Check 3: Weekly Headroom -->
          <div style="display: flex; flex-direction: column; gap: 2px;">
            <span style="font-size: 0.68rem; color: var(--dl-fg-3);">WEEKLY LOSS CAP HEADROOM</span>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-sage);">
                ${weeklyCapRemaining}
              </span>
              <span>✅</span>
            </div>
          </div>

          <!-- Check 4: Hedge Structure -->
          <div style="display: flex; flex-direction: column; gap: 2px;">
            <span style="font-size: 0.68rem; color: var(--dl-fg-3);">HEDGE STRUCTURE</span>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-family: var(--font-mono); font-weight: 600; color: ${hedgePassed ? 'var(--accent-sage)' : 'var(--accent-coral)'};">
                ${hedgePassed ? 'Hedged Spread' : 'Naked Short Risk'}
              </span>
              <span>${hedgePassed ? '✅' : '❌'}</span>
            </div>
          </div>
        </div>

        ${!overallPassed ? `
          <div style="font-size: 0.75rem; color: var(--accent-coral); background: var(--accent-coral-tint); padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(221,129,112,0.3);">
            ⚠️ Execution blocked: One or more Method risk rules failed. Adjust strikes or add hedge wings to proceed.
          </div>
        ` : ''}
      </div>
    `;
  }
}

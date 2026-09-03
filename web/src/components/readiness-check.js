/**
 * 60-Second Manual-First Operational Readiness Check Component.
 */

import { api } from '../api.js';
import { formatINR, formatPercent } from '../utils/format.js';

export class ReadinessCheckComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // e.g. onVerdictChanged(verdict)
    this.readinessData = null;
    this.selectedMood = null;
    this.isSubmitting = false;
  }

  async init() {
    await this.loadStatus();
  }

  async loadStatus() {
    this.container.innerHTML = `<div class="card" style="padding: 1rem; text-align: center; color: var(--text-muted);">Loading readiness status...</div>`;
    try {
      this.readinessData = await api.getTodayReadiness();
      this.render();
      if (this.readinessData.logged && this.options.onVerdictChanged) {
        this.options.onVerdictChanged(this.readinessData);
      }
    } catch (err) {
      this.container.innerHTML = `
        <div class="card" style="padding: 1rem; border-color: var(--red);">
          <strong style="color: var(--red);">Readiness Service Unavailable:</strong>
          <span style="color: var(--text-muted); font-size: 0.875rem;">${err.message}</span>
        </div>
      `;
    }
  }

  render() {
    if (!this.readinessData) return;

    if (this.readinessData.logged) {
      this.renderVerdictCard();
    } else {
      this.renderCheckForm();
    }
  }

  renderCheckForm(prefill = null) {
    const defaults = this.readinessData.atlas_defaults || {};
    const sleepVal = prefill?.sleep_hours_bucket || defaults.sleep_hours_bucket || '';
    const alcoholVal = prefill?.alcohol_yesterday ?? defaults.alcohol_yesterday ?? false;
    const workoutVal = prefill?.workout_in_last_48h ?? defaults.workout_in_last_48h ?? false;
    const stressorVal = prefill?.life_stressor || defaults.life_stressor || 'none';
    const noteVal = prefill?.stressor_note || '';
    this.selectedMood = prefill?.journal_mood || null;

    const atlasHint = defaults.sleep_hours ? ` (Atlas synced: ${defaults.sleep_hours}h)` : '';

    this.container.innerHTML = `
      <div class="card" style="border: 1px solid var(--border-focus); background: linear-gradient(180deg, #161b22 0%, #0e1117 100%);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <div>
            <h3 style="margin: 0; font-size: 1.1rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
              <span>🌅</span> 60-Second Readiness Check
            </h3>
            <span style="font-size: 0.75rem; color: var(--text-muted);">
              Manual entries are primary. Confirm your state before trading window closes.
            </span>
          </div>
          <span class="badge" style="background: var(--bg-surface); color: var(--text-muted); border: 1px solid var(--border);">Pre-Trade Gate</span>
        </div>

        <form id="readiness-form" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; align-items: start;">
          <!-- Sleep -->
          <div>
            <label style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.35rem;">
              Sleep Duration${atlasHint}
            </label>
            <select id="readiness-sleep" required style="width: 100%; padding: 0.5rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
              <option value="" disabled ${!sleepVal ? 'selected' : ''}>Select hours...</option>
              <option value="<3" ${sleepVal === '<3' ? 'selected' : ''}>&lt; 3 hours (Critical)</option>
              <option value="3-4" ${sleepVal === '3-4' ? 'selected' : ''}>3–4 hours (Low)</option>
              <option value="4-5" ${sleepVal === '4-5' ? 'selected' : ''}>4–5 hours (Threshold)</option>
              <option value="5-6" ${sleepVal === '5-6' ? 'selected' : ''}>5–6 hours (75% Sizing)</option>
              <option value="6-7" ${sleepVal === '6-7' ? 'selected' : ''}>6–7 hours (Standard)</option>
              <option value="7+" ${sleepVal === '7+' ? 'selected' : ''}>7+ hours (Well Rested)</option>
            </select>
          </div>

          <!-- Alcohol Yesterday -->
          <div>
            <label style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.35rem;">
              Alcohol Yesterday?
            </label>
            <select id="readiness-alcohol" style="width: 100%; padding: 0.5rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
              <option value="no" ${!alcoholVal ? 'selected' : ''}>No (Clean)</option>
              <option value="yes" ${alcoholVal ? 'selected' : ''}>Yes (Triggers Lockout)</option>
            </select>
          </div>

          <!-- Workout in last 48h -->
          <div>
            <label style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.35rem;">
              Workout in last 48h?
            </label>
            <select id="readiness-workout" style="width: 100%; padding: 0.5rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
              <option value="yes" ${workoutVal ? 'selected' : ''}>Yes (Active)</option>
              <option value="no" ${!workoutVal ? 'selected' : ''}>No (Sedentary Warning)</option>
            </select>
          </div>

          <!-- Life Stressor -->
          <div>
            <label style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.35rem;">
              Life Stressor?
            </label>
            <select id="readiness-stressor" style="width: 100%; padding: 0.5rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary);">
              <option value="none" ${stressorVal === 'none' ? 'selected' : ''}>None</option>
              <option value="family" ${stressorVal === 'family' ? 'selected' : ''}>Family</option>
              <option value="work" ${stressorVal === 'work' ? 'selected' : ''}>Work</option>
              <option value="financial" ${stressorVal === 'financial' ? 'selected' : ''}>Financial</option>
              <option value="other" ${stressorVal === 'other' ? 'selected' : ''}>Other</option>
            </select>
          </div>

          <!-- Mood Selector (Horizontal Pills - Required, No Default) -->
          <div style="grid-column: 1 / -1;">
            <label style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem;">
              How do I feel right now? <span style="color: var(--accent);">* Required (feelings > data)</span>
            </label>
            <div id="mood-pill-container" style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
              ${[
                { id: 'focused', label: '🎯 Focused' },
                { id: 'neutral', label: '⚖️ Neutral' },
                { id: 'tired', label: '🥱 Tired' },
                { id: 'off', label: '⚡ Off / Restless' },
                { id: 'angry_grief', label: '🛑 Angry / Grief' },
              ].map(m => `
                <button type="button" class="mood-pill ${this.selectedMood === m.id ? 'active' : ''}" data-mood="${m.id}"
                  style="padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.825rem; cursor: pointer; border: 1px solid ${this.selectedMood === m.id ? 'var(--accent)' : 'var(--border)'}; background: ${this.selectedMood === m.id ? 'rgba(88, 166, 255, 0.15)' : 'var(--bg-surface)'}; color: var(--text-primary);">
                  ${m.label}
                </button>
              `).join('')}
            </div>
            <div id="mood-error" style="color: var(--red); font-size: 0.75rem; margin-top: 0.25rem; display: none;">
              Please select how you feel before submitting.
            </div>
          </div>

          <!-- Optional Stressor Note & Submit Button -->
          <div style="grid-column: 1 / -1; display: flex; gap: 1rem; align-items: flex-end; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 250px;">
              <input type="text" id="readiness-note" value="${noteVal}" placeholder="Optional short note (e.g. market gap-down anxiety, slight headache)..."
                style="width: 100%; padding: 0.5rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; color: var(--text-primary); font-size: 0.875rem;" />
            </div>
            <button type="submit" id="readiness-submit-btn" class="primary" style="padding: 0.6rem 1.5rem; white-space: nowrap; font-weight: 600;">
              ✓ Submit Readiness
            </button>
          </div>
        </form>
      </div>
    `;

    // Wire Mood Pills
    const pills = this.container.querySelectorAll('.mood-pill');
    pills.forEach(p => {
      p.addEventListener('click', () => {
        this.selectedMood = p.dataset.mood;
        pills.forEach(other => {
          const isActive = other.dataset.mood === this.selectedMood;
          other.style.borderColor = isActive ? 'var(--accent)' : 'var(--border)';
          other.style.background = isActive ? 'rgba(88, 166, 255, 0.15)' : 'var(--bg-surface)';
        });
        document.getElementById('mood-error').style.display = 'none';
      });
    });

    // Wire Submit Form
    const form = document.getElementById('readiness-form');
    form.addEventListener('submit', (e) => this.handleSubmit(e));
  }

  async handleSubmit(e) {
    e.preventDefault();
    if (!this.selectedMood) {
      document.getElementById('mood-error').style.display = 'block';
      return;
    }

    const sleepBucket = document.getElementById('readiness-sleep').value;
    const alcoholYesterday = document.getElementById('readiness-alcohol').value === 'yes';
    const workoutLast48h = document.getElementById('readiness-workout').value === 'yes';
    const stressor = document.getElementById('readiness-stressor').value;
    const note = document.getElementById('readiness-note').value.trim() || null;

    const payload = {
      sleep_hours_bucket: sleepBucket,
      alcohol_yesterday: alcoholYesterday,
      workout_in_last_48h: workoutLast48h,
      journal_mood: this.selectedMood,
      life_stressor: stressor,
      stressor_note: note,
    };

    const submitBtn = document.getElementById('readiness-submit-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Recording...';

    try {
      const verdict = await api.logReadiness(payload);
      this.readinessData = {
        logged: true,
        log_date: new Date().toISOString().split('T')[0],
        verdict: verdict.verdict,
        trading_allowed: verdict.trading_allowed,
        size_cap_pct: verdict.size_cap_pct,
        factors: {
          input: payload,
          per_factor_verdicts: verdict.per_factor_verdicts,
          reasons: verdict.reasons,
          rules_snapshot: verdict.method_rules_snapshot,
        },
      };

      this.renderVerdictCard();
      if (this.options.onVerdictChanged) {
        this.options.onVerdictChanged(this.readinessData);
      }
    } catch (err) {
      alert(`Failed to save readiness check: ${err.message}`);
      submitBtn.disabled = false;
      submitBtn.textContent = '✓ Submit Readiness';
    }
  }

  renderVerdictCard() {
    const { verdict, trading_allowed, size_cap_pct, factors } = this.readinessData;
    const perFactor = factors?.per_factor_verdicts || {};
    const reasons = factors?.reasons || [];
    const input = factors?.input || {};

    const colorMap = {
      green: { border: 'var(--green)', bg: 'rgba(46, 160, 67, 0.1)', text: 'var(--green)', icon: '🟢', label: 'GREEN — TRADING ALLOWED' },
      yellow: { border: 'var(--amber)', bg: 'rgba(210, 153, 34, 0.1)', text: 'var(--amber)', icon: '🟡', label: 'YELLOW — HEIGHTENED CAUTION' },
      red: { border: 'var(--red)', bg: 'rgba(248, 81, 73, 0.1)', text: 'var(--red)', icon: '🔴', label: 'RED — TRADING BLOCKED' },
    };

    const style = colorMap[verdict] || colorMap.green;
    const sizingText = trading_allowed
      ? `${formatPercent(size_cap_pct || 0.01)} max risk per trade ceiling`
      : 'Trading Blocked for Today';

    this.container.innerHTML = `
      <div class="card" style="border: 2px solid ${style.border}; background: ${style.bg};">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem;">
              <span style="font-size: 1.3rem;">${style.icon}</span>
              <strong style="font-size: 1.15rem; color: ${style.text}; text-transform: uppercase; letter-spacing: 0.05em;">
                ${style.label}
              </strong>
            </div>
            <div style="font-size: 0.95rem; font-weight: 500; color: var(--text-primary);" class="mono">
              ${sizingText}
            </div>
          </div>

          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <button id="relog-readiness-btn" style="padding: 0.35rem 0.75rem; font-size: 0.75rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; color: var(--text-secondary); cursor: pointer;">
              ✎ Re-log State
            </button>
            <button id="reconcile-readiness-btn" style="padding: 0.35rem 0.75rem; font-size: 0.75rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; color: var(--text-secondary); cursor: pointer;">
              ⟳ Reconcile with Atlas
            </button>
          </div>
        </div>

        <!-- Factors Breakdown Pills -->
        <div style="display: flex; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap;">
          <span class="badge" style="background: var(--bg-surface); border: 1px solid var(--border); font-size: 0.75rem;">
            Sleep: ${perFactor.sleep === 'green' ? '🟢' : perFactor.sleep === 'yellow' ? '🟡' : '🔴'} ${input.sleep_hours_bucket || '-'}h
          </span>
          <span class="badge" style="background: var(--bg-surface); border: 1px solid var(--border); font-size: 0.75rem;">
            Alcohol: ${perFactor.alcohol === 'green' ? '🟢 Clean' : '🔴 Consumed'}
          </span>
          <span class="badge" style="background: var(--bg-surface); border: 1px solid var(--border); font-size: 0.75rem;">
            Workout: ${perFactor.workout === 'green' ? '🟢 Active' : '🟡 Rest'}
          </span>
          <span class="badge" style="background: var(--bg-surface); border: 1px solid var(--border); font-size: 0.75rem;">
            Mood: ${perFactor.mood === 'green' ? '🟢' : perFactor.mood === 'yellow' ? '🟡' : '🔴'} ${input.journal_mood || '-'}
          </span>
          <span class="badge" style="background: var(--bg-surface); border: 1px solid var(--border); font-size: 0.75rem;">
            Stressor: ${perFactor.stressor === 'green' ? '🟢 None' : `🟡 ${input.life_stressor}`}
          </span>
        </div>

        ${reasons.length > 0 ? `
          <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.08); font-size: 0.825rem; color: ${style.text};">
            <ul style="margin: 0; padding-left: 1.25rem;">
              ${reasons.map(r => `<li>${r}</li>`).join('')}
            </ul>
          </div>
        ` : ''}

        <div id="reconcile-result-container" style="margin-top: 0.5rem;"></div>
      </div>
    `;

    document.getElementById('relog-readiness-btn').addEventListener('click', () => {
      this.renderCheckForm(input);
    });

    document.getElementById('reconcile-readiness-btn').addEventListener('click', async () => {
      const btn = document.getElementById('reconcile-readiness-btn');
      btn.disabled = true;
      btn.textContent = 'Reconciling...';
      const resultContainer = document.getElementById('reconcile-result-container');
      try {
        const res = await api.reconcileReadiness();
        if (res.has_discrepancies) {
          resultContainer.innerHTML = `
            <div style="padding: 0.5rem; background: var(--bg-surface); border-radius: 4px; border: 1px solid var(--amber); font-size: 0.75rem; color: var(--amber);">
              <strong>Atlas Reconciled Discrepancies noted:</strong>
              ${res.discrepancies.map(d => `<div>• ${d.field}: manual=${d.manual}, atlas=${d.atlas} (${d.note || ''})</div>`).join('')}
            </div>
          `;
        } else {
          resultContainer.innerHTML = `
            <div style="padding: 0.5rem; background: var(--bg-surface); border-radius: 4px; border: 1px solid var(--green); font-size: 0.75rem; color: var(--green);">
              ✓ Atlas synced cleanly with zero discrepancies.
            </div>
          `;
        }
      } catch (err) {
        resultContainer.innerHTML = `<span style="color: var(--red); font-size: 0.75rem;">Reconciliation error: ${err.message}</span>`;
      } finally {
        btn.disabled = false;
        btn.textContent = '⟳ Reconcile with Atlas';
      }
    });
  }
}

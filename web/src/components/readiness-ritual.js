/**
 * Readiness Ritual Component for Swayam Capital (BUILD-9).
 * Presents the 6-step sequential pre-trade operational readiness form
 * in a clean single-column card with an interactive 5-minute meditation timer.
 */

import { api } from '../api.js';

export class ReadinessRitualComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onVerdictChanged, onSubmitted }
    this.timerSeconds = 300; // 5:00
    this.timerInterval = null;
    this.isTimerRunning = false;
    this.meditationCompletedAt = null;

    // Default form state
    this.formData = {
      sleep_hours_bucket: '7+',
      alcohol_yesterday: false,
      workout_in_last_48h: true,
      journal_mood: 'focused',
      life_stressor: 'none',
      stressor_note: '',
    };
  }

  async init() {
    this.render();
    this.attachEvents();
    await this.loadInitialData();
  }

  async loadInitialData() {
    try {
      const res = await api.getTodayReadiness();
      if (res && res.logged && res.factors?.input) {
        const inp = res.factors.input;
        this.formData = {
          sleep_hours_bucket: inp.sleep_hours_bucket || '7+',
          alcohol_yesterday: !!inp.alcohol_yesterday,
          workout_in_last_48h: inp.workout_in_last_48h !== false,
          journal_mood: inp.journal_mood || 'focused',
          life_stressor: inp.life_stressor || 'none',
          stressor_note: inp.stressor_note || '',
        };
        if (inp.meditation_completed_at) {
          this.meditationCompletedAt = inp.meditation_completed_at;
        }
        this.syncFormUI();
        if (this.options.onVerdictChanged && res.verdict) {
          this.options.onVerdictChanged({
            verdict: res.verdict,
            trading_allowed: res.trading_allowed,
            size_cap_pct: res.size_cap_pct,
            reasons: res.factors?.reasons || [],
            per_factor_verdicts: res.factors?.per_factor_verdicts || {},
          });
        }
      } else if (res && res.atlas_defaults) {
        // Pre-fill defaults from Obsidian daily log if available
        const d = res.atlas_defaults;
        if (d.sleep_hours) {
          this.formData.sleep_hours_bucket = d.sleep_hours >= 7 ? '7+' : (d.sleep_hours >= 6 ? '6-7' : '<6');
        }
        if (d.alcohol !== undefined) this.formData.alcohol_yesterday = !!d.alcohol;
        if (d.workout !== undefined) this.formData.workout_in_last_48h = !!d.workout;
        this.syncFormUI();
      }
    } catch (err) {
      console.warn('Could not load today readiness prefill:', err);
    }
  }

  render() {
    const todayFormatted = new Intl.DateTimeFormat('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    }).format(new Date()).toUpperCase();

    this.container.innerHTML = `
      <div class="tile readiness-ritual-tile" style="display: flex; flex-direction: column; gap: 10px; padding: 14px 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="eyebrow" style="color: var(--dl-fg-3);">MORNING RITUAL · ${todayFormatted}</span>
          <span id="ritual-status-chip" style="font-size: 0.68rem; color: var(--dl-fg-3);">60-sec check</span>
        </div>

        <!-- 1. Meditation Timer (compact) -->
        <div class="ritual-step" id="step-meditation" style="padding: 8px 10px; background: var(--dl-card-2); border-radius: 10px; border: 1px solid var(--dl-line); display: flex; align-items: center; justify-content: space-between; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div style="position: relative; width: 40px; height: 40px; flex-shrink: 0;">
              <svg width="40" height="40" viewBox="0 0 40 40" style="transform: rotate(-90deg);">
                <circle cx="20" cy="20" r="17" stroke="var(--dl-track)" stroke-width="2.5" fill="none" />
                <circle id="meditation-ring-progress" cx="20" cy="20" r="17" stroke="var(--accent-sage)" stroke-width="2.5" fill="none" stroke-dasharray="106.8" stroke-dashoffset="0" style="transition: stroke-dashoffset 1s linear;" />
              </svg>
              <div id="meditation-timer-display" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 0.72rem; font-weight: 700; color: var(--dl-fg);">
                5:00
              </div>
            </div>
            <div>
              <div style="font-size: 0.8rem; font-weight: 600; color: var(--dl-fg); line-height: 1.2;">Meditation</div>
              <button id="btn-meditation-skip" style="background: none; border: none; padding: 0; font-size: 0.7rem; color: var(--dl-fg-3); cursor: pointer; text-decoration: underline; text-decoration-style: dotted;">Skip for now</button>
            </div>
          </div>
          <div style="display: flex; gap: 5px;">
            <button id="btn-meditation-toggle" class="ritual-btn-action" style="background: var(--accent-sage); color: #101116; border: none; padding: 5px 12px; border-radius: 8px; font-weight: 600; font-size: 0.75rem; cursor: pointer;">
              Start
            </button>
            <button id="btn-meditation-reset" style="background: transparent; color: var(--dl-fg-3); border: 1px solid var(--dl-line); padding: 5px 8px; border-radius: 8px; font-size: 0.72rem; cursor: pointer; display: none;">↺</button>
          </div>
        </div>

        <!-- 2. Sleep Duration -->
        <div class="ritual-step" id="step-sleep" style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <span style="font-size: 0.8rem; color: var(--dl-fg-2); white-space: nowrap;">Sleep last night</span>
          <select id="ritual-sleep-select" style="background: var(--dl-card-2); color: var(--dl-fg); border: 1px solid var(--dl-line); border-radius: 8px; padding: 5px 10px; font-size: 0.8rem; outline: none; min-width: 130px;">
            <option value="<3">&lt; 3 hours</option>
            <option value="3-4">3 – 4 hours</option>
            <option value="4-5">4 – 5 hours</option>
            <option value="5-6">5 – 6 hours</option>
            <option value="6-7">6 – 7 hours</option>
            <option value="7+" selected>7 – 8 hours</option>
          </select>
        </div>

        <!-- 3. Alcohol in Last 24h -->
        <div class="ritual-step" id="step-alcohol" style="display: flex; align-items: center; justify-content: space-between;">
          <span style="font-size: 0.8rem; color: var(--dl-fg-2);">Alcohol in last 24h?</span>
          <div class="pill-group" style="display: flex; gap: 5px;">
            <button type="button" class="pill-toggle active" data-field="alcohol" data-val="false" style="padding: 3px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; border: 1px solid rgba(134,171,146,0.3); background: var(--accent-sage-tint); color: var(--accent-sage); cursor: pointer;">No</button>
            <button type="button" class="pill-toggle" data-field="alcohol" data-val="true" style="padding: 3px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Yes</button>
          </div>
        </div>

        <!-- 4. Workout in Last 48h -->
        <div class="ritual-step" id="step-workout" style="display: flex; align-items: center; justify-content: space-between;">
          <span style="font-size: 0.8rem; color: var(--dl-fg-2);">Workout in last 48h?</span>
          <div class="pill-group" style="display: flex; gap: 5px;">
            <button type="button" class="pill-toggle active" data-field="workout" data-val="true" style="padding: 3px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; border: 1px solid rgba(134,171,146,0.3); background: var(--accent-sage-tint); color: var(--accent-sage); cursor: pointer;">Yes</button>
            <button type="button" class="pill-toggle" data-field="workout" data-val="false" style="padding: 3px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">No</button>
          </div>
        </div>

        <!-- 5. Current Mood -->
        <div class="ritual-step" id="step-mood" style="display: flex; flex-direction: column; gap: 5px;">
          <span class="eyebrow" style="color: var(--dl-fg-3); font-size: 0.65rem;">Mood</span>
          <div style="display: flex; flex-wrap: wrap; gap: 5px;">
            <button type="button" class="pill-mood active" data-mood="focused" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 600; border: 1px solid rgba(134,171,146,0.3); background: var(--accent-sage-tint); color: var(--accent-sage); cursor: pointer;">Focused</button>
            <button type="button" class="pill-mood" data-mood="neutral" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Neutral</button>
            <button type="button" class="pill-mood" data-mood="tired" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Restless</button>
            <button type="button" class="pill-mood" data-mood="off" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Anxious</button>
            <button type="button" class="pill-mood" data-mood="angry_grief" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Angry</button>
          </div>
        </div>

        <!-- 6. Life Stressor -->
        <div class="ritual-step" id="step-stressor" style="display: flex; flex-direction: column; gap: 5px;">
          <span class="eyebrow" style="color: var(--dl-fg-3); font-size: 0.65rem;">Life Stressor</span>
          <div style="display: flex; flex-wrap: wrap; gap: 5px;">
            <button type="button" class="pill-stressor active" data-stressor="none" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 600; border: 1px solid rgba(134,171,146,0.3); background: var(--accent-sage-tint); color: var(--accent-sage); cursor: pointer;">None</button>
            <button type="button" class="pill-stressor" data-stressor="work" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Work</button>
            <button type="button" class="pill-stressor" data-stressor="family" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Family</button>
            <button type="button" class="pill-stressor" data-stressor="health" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Health</button>
            <button type="button" class="pill-stressor" data-stressor="financial" style="padding: 3px 9px; border-radius: 999px; font-size: 0.73rem; font-weight: 500; border: 1px solid var(--dl-line); background: transparent; color: var(--dl-fg-2); cursor: pointer;">Financial</button>
          </div>
        </div>

        <!-- Submit Button -->
        <button id="btn-confirm-readiness" style="margin-top: 2px; height: 34px; background: var(--accent-sage); color: #101116; border: none; border-radius: 9px; font-weight: 700; font-size: 0.82rem; letter-spacing: 0.02em; cursor: pointer; transition: opacity var(--dur-fast) ease;">
          Confirm Readiness
        </button>

        <!-- Double confirmation modal for alcohol streak protection -->
        <div id="alcohol-streak-modal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 2000; align-items: center; justify-content: center; backdrop-filter: blur(2px);">
          <div style="background: var(--dl-card, #191b21); border: 2px solid var(--accent-coral, #b56b5d); border-radius: 14px; max-width: 440px; width: 90%; padding: 22px 24px; box-shadow: var(--dl-shadow); display: flex; flex-direction: column; gap: 14px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 1.3rem;">⚠️</span>
              <span style="font-weight: 700; font-size: 1.05rem; color: var(--accent-coral);">Streak Protection Warning</span>
            </div>
            <p style="font-size: 0.88rem; color: var(--dl-fg); line-height: 1.5; margin: 0;">
              You're about to log alcohol consumption. This locks Swayam for <strong>90 days</strong> and resets your streak from <strong>103 days back to 0</strong>.
            </p>
            <p style="font-size: 0.85rem; color: var(--dl-fg-2); margin: 0; font-weight: 500;">
              Are you sure this is accurate?
            </p>
            <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 8px;">
              <button id="btn-alcohol-cancel" type="button" style="background: transparent; border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 8px 16px; border-radius: 8px; font-size: 0.82rem; font-weight: 600; cursor: pointer;">
                Cancel
              </button>
              <button id="btn-alcohol-confirm" type="button" style="background: var(--accent-coral); color: #ffffff; border: none; padding: 8px 16px; border-radius: 8px; font-size: 0.82rem; font-weight: 700; cursor: pointer;">
                Yes, I drank yesterday — reset my streak
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }


  attachEvents() {
    // 1. Meditation Timer
    const btnToggle = this.container.querySelector('#btn-meditation-toggle');
    const btnReset = this.container.querySelector('#btn-meditation-reset');
    const btnSkip = this.container.querySelector('#btn-meditation-skip');
    if (btnToggle) {
      btnToggle.addEventListener('click', () => this.toggleMeditationTimer());
    }
    if (btnReset) {
      btnReset.addEventListener('click', () => this.resetMeditationTimer());
    }
    if (btnSkip) {
      btnSkip.addEventListener('click', () => {
        // Skipping meditation — mark as explicitly skipped (no timestamp set)
        this.meditationCompletedAt = null;
        btnSkip.textContent = 'Skipped';
        btnSkip.style.color = 'var(--dl-fg-3)';
        btnSkip.style.textDecoration = 'none';
        if (btnToggle) {
          btnToggle.style.opacity = '0.4';
          btnToggle.disabled = true;
        }
      });
    }

    // 2. Sleep Select
    const sleepSelect = this.container.querySelector('#ritual-sleep-select');
    if (sleepSelect) {
      sleepSelect.addEventListener('change', (e) => {
        this.formData.sleep_hours_bucket = e.target.value;
      });
    }

    // 3 & 4. Toggle buttons (Alcohol & Workout)
    const modal = this.container.querySelector('#alcohol-streak-modal');
    const btnAlcoholCancel = this.container.querySelector('#btn-alcohol-cancel');
    const btnAlcoholConfirm = this.container.querySelector('#btn-alcohol-confirm');
    let pendingAlcoholBtn = null;

    if (btnAlcoholCancel && modal) {
      btnAlcoholCancel.addEventListener('click', () => {
        modal.style.display = 'none';
        pendingAlcoholBtn = null;
        // Keep or revert to No
        this.formData.alcohol_yesterday = false;
        const noBtn = this.container.querySelector('.pill-toggle[data-field="alcohol"][data-val="false"]');
        if (noBtn) {
          noBtn.parentElement.querySelectorAll('.pill-toggle').forEach((s) => {
            s.classList.remove('active');
            s.style.background = 'transparent';
            s.style.color = 'var(--dl-fg-2)';
            s.style.borderColor = 'var(--dl-line)';
            s.style.fontWeight = '500';
          });
          noBtn.classList.add('active');
          noBtn.style.background = 'var(--accent-sage-tint)';
          noBtn.style.color = 'var(--accent-sage)';
          noBtn.style.borderColor = 'rgba(134,171,146,0.3)';
          noBtn.style.fontWeight = '600';
        }
      });
    }

    if (btnAlcoholConfirm && modal) {
      btnAlcoholConfirm.addEventListener('click', () => {
        modal.style.display = 'none';
        this.formData.alcohol_yesterday = true;
        if (pendingAlcoholBtn) {
          pendingAlcoholBtn.parentElement.querySelectorAll('.pill-toggle').forEach((s) => {
            s.classList.remove('active');
            s.style.background = 'transparent';
            s.style.color = 'var(--dl-fg-2)';
            s.style.borderColor = 'var(--dl-line)';
            s.style.fontWeight = '500';
          });
          pendingAlcoholBtn.classList.add('active');
          pendingAlcoholBtn.style.background = 'var(--accent-coral-tint, rgba(181, 107, 93, 0.14))';
          pendingAlcoholBtn.style.color = 'var(--accent-coral)';
          pendingAlcoholBtn.style.borderColor = 'var(--accent-coral)';
          pendingAlcoholBtn.style.fontWeight = '700';
        }
        pendingAlcoholBtn = null;
      });
    }

    this.container.querySelectorAll('.pill-toggle').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const field = btn.getAttribute('data-field');
        const val = btn.getAttribute('data-val') === 'true';
        if (field === 'alcohol') {
          if (val === true) {
            // Require explicit double-confirmation before logging alcohol
            pendingAlcoholBtn = btn;
            if (modal) modal.style.display = 'flex';
            return;
          }
          this.formData.alcohol_yesterday = false;
        } else if (field === 'workout') {
          this.formData.workout_in_last_48h = val;
        }
        // Update styling in parent group
        btn.parentElement.querySelectorAll('.pill-toggle').forEach((sibling) => {
          sibling.classList.remove('active');
          sibling.style.background = 'transparent';
          sibling.style.color = 'var(--dl-fg-2)';
          sibling.style.borderColor = 'var(--dl-line)';
          sibling.style.fontWeight = '500';
        });
        btn.classList.add('active');
        btn.style.background = 'var(--accent-sage-tint)';
        btn.style.color = 'var(--accent-sage)';
        btn.style.borderColor = 'rgba(134,171,146,0.3)';
        btn.style.fontWeight = '600';
      });
    });

    // 5. Mood Pills
    this.container.querySelectorAll('.pill-mood').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.formData.journal_mood = btn.getAttribute('data-mood');
        this.container.querySelectorAll('.pill-mood').forEach((b) => {
          b.classList.remove('active');
          b.style.background = 'transparent';
          b.style.color = 'var(--dl-fg-2)';
          b.style.borderColor = 'var(--dl-line)';
          b.style.fontWeight = '500';
        });
        btn.classList.add('active');
        btn.style.background = 'var(--accent-sage-tint)';
        btn.style.color = 'var(--accent-sage)';
        btn.style.borderColor = 'rgba(134,171,146,0.3)';
        btn.style.fontWeight = '600';
      });
    });

    // 6. Stressor Pills
    this.container.querySelectorAll('.pill-stressor').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.formData.life_stressor = btn.getAttribute('data-stressor');
        this.container.querySelectorAll('.pill-stressor').forEach((b) => {
          b.classList.remove('active');
          b.style.background = 'transparent';
          b.style.color = 'var(--dl-fg-2)';
          b.style.borderColor = 'var(--dl-line)';
          b.style.fontWeight = '500';
        });
        btn.classList.add('active');
        btn.style.background = 'var(--accent-sage-tint)';
        btn.style.color = 'var(--accent-sage)';
        btn.style.borderColor = 'rgba(134,171,146,0.3)';
        btn.style.fontWeight = '600';
      });
    });

    // Submit
    const btnSubmit = this.container.querySelector('#btn-confirm-readiness');
    if (btnSubmit) {
      btnSubmit.addEventListener('click', () => this.submitReadiness());
    }
  }

  toggleMeditationTimer() {
    const btnToggle = this.container.querySelector('#btn-meditation-toggle');
    const btnReset = this.container.querySelector('#btn-meditation-reset');

    if (this.isTimerRunning) {
      // Pause
      clearInterval(this.timerInterval);
      this.isTimerRunning = false;
      if (btnToggle) btnToggle.textContent = 'Resume';
    } else {
      // Start
      this.isTimerRunning = true;
      if (btnToggle) btnToggle.textContent = 'Pause';
      if (btnReset) btnReset.style.display = 'inline-block';

      this.timerInterval = setInterval(() => {
        if (this.timerSeconds > 0) {
          this.timerSeconds -= 1;
          this.updateTimerUI();
        } else {
          // Timer finished
          clearInterval(this.timerInterval);
          this.isTimerRunning = false;
          this.meditationCompletedAt = new Date().toISOString();
          if (btnToggle) {
            btnToggle.textContent = 'Done ✓';
            btnToggle.style.background = 'var(--accent-sage-tint)';
            btnToggle.style.color = 'var(--accent-sage)';
          }
          this.playBellChime();
        }
      }, 1000);
    }
  }

  resetMeditationTimer() {
    clearInterval(this.timerInterval);
    this.isTimerRunning = false;
    this.timerSeconds = 300;
    this.updateTimerUI();
    const btnToggle = this.container.querySelector('#btn-meditation-toggle');
    const btnReset = this.container.querySelector('#btn-meditation-reset');
    if (btnToggle) {
      btnToggle.textContent = 'Start';
      btnToggle.style.background = 'var(--accent-sage)';
      btnToggle.style.color = '#101116';
    }
    if (btnReset) btnReset.style.display = 'none';
  }

  updateTimerUI() {
    const mins = Math.floor(this.timerSeconds / 60);
    const secs = this.timerSeconds % 60;
    const timeStr = `${mins}:${secs < 10 ? '0' : ''}${secs}`;

    const display = this.container.querySelector('#meditation-timer-display');
    if (display) display.textContent = timeStr;

    // SVG dashoffset: compact ring circumference is 2 * PI * 17 ≈ 106.8
    const progress = this.container.querySelector('#meditation-ring-progress');
    if (progress) {
      const fraction = (300 - this.timerSeconds) / 300;
      const offset = 106.8 * (1 - fraction);
      progress.style.strokeDashoffset = offset;
    }
  }

  playBellChime() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5 gentle bell
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 2.5);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 2.5);
    } catch (e) {
      console.warn('AudioContext chime could not play:', e);
    }
  }

  syncFormUI() {
    const sleepSelect = this.container.querySelector('#ritual-sleep-select');
    if (sleepSelect) sleepSelect.value = this.formData.sleep_hours_bucket;

    // Alcohol
    this.container.querySelectorAll('.pill-toggle[data-field="alcohol"]').forEach((b) => {
      const match = (b.getAttribute('data-val') === 'true') === this.formData.alcohol_yesterday;
      this.setButtonActive(b, match);
    });

    // Workout
    this.container.querySelectorAll('.pill-toggle[data-field="workout"]').forEach((b) => {
      const match = (b.getAttribute('data-val') === 'true') === this.formData.workout_in_last_48h;
      this.setButtonActive(b, match);
    });

    // Mood
    this.container.querySelectorAll('.pill-mood').forEach((b) => {
      const match = b.getAttribute('data-mood') === this.formData.journal_mood;
      this.setButtonActive(b, match);
    });

    // Stressor
    this.container.querySelectorAll('.pill-stressor').forEach((b) => {
      const match = b.getAttribute('data-stressor') === this.formData.life_stressor;
      this.setButtonActive(b, match);
    });

    // Meditation done state if loaded from db
    if (this.meditationCompletedAt) {
      const btnToggle = this.container.querySelector('#btn-meditation-toggle');
      if (btnToggle) {
        btnToggle.textContent = 'Done ✓';
        btnToggle.style.background = 'var(--accent-sage-tint)';
        btnToggle.style.color = 'var(--accent-sage)';
      }
    }
  }

  setButtonActive(btn, isActive) {
    if (isActive) {
      btn.classList.add('active');
      btn.style.background = 'var(--accent-sage-tint)';
      btn.style.color = 'var(--accent-sage)';
      btn.style.borderColor = 'rgba(134,171,146,0.3)';
      btn.style.fontWeight = '600';
    } else {
      btn.classList.remove('active');
      btn.style.background = 'transparent';
      btn.style.color = 'var(--dl-fg-2)';
      btn.style.borderColor = 'var(--dl-line)';
      btn.style.fontWeight = '500';
    }
  }

  async submitReadiness() {
    const btn = this.container.querySelector('#btn-confirm-readiness');
    const chip = this.container.querySelector('#ritual-status-chip');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Evaluating rules...';
      btn.style.opacity = '0.7';
    }

    const payload = {
      ...this.formData,
      meditation_completed_at: this.meditationCompletedAt,
      logged_at: new Date().toISOString(),
    };

    try {
      const verdict = await api.logReadiness(payload);
      if (btn) {
        btn.textContent = 'Readiness Recorded ✓';
        btn.style.background = 'var(--accent-sage-tint)';
        btn.style.color = 'var(--accent-sage)';
      }
      if (chip) {
        chip.textContent = 'Submitted for Today';
        chip.style.color = 'var(--accent-sage)';
      }

      if (this.options.onVerdictChanged) {
        this.options.onVerdictChanged(verdict);
      }
      if (this.options.onSubmitted) {
        this.options.onSubmitted(verdict);
      }
    } catch (err) {
      console.error('Failed to record readiness:', err);
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Failed — Retry';
        btn.style.background = 'var(--accent-coral-tint)';
        btn.style.color = 'var(--accent-coral)';
      }
      if (chip) {
        chip.textContent = 'Submission error';
        chip.style.color = 'var(--accent-coral)';
      }
    }
  }
}

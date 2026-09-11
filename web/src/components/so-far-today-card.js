/**
 * "SO FAR TODAY", the grounded market summary he pays for. BUILD_07.
 *
 * HIS WORDS, 11 September 2026: "I want to save the AI-generated summary. I'm
 * paying for that, so I don't want to lose those details and create a record of
 * what's happening, a trend in the market or in the geopolitics as well."
 *
 * It is one row a trading day in `swayam_daily_summary`, keyed on the day, so
 * regenerating replaces that day's row and past days are kept for ever. The AI
 * panel reads the same row, so he can open the panel on Home and ask about the
 * day and it knows what this card says.
 *
 * ⚠️ THE COST GATE DOES NOT CHANGE, EVER:
 * - init() only READS the saved row. It is a database call, never a model call,
 *   and nothing here may ever be made to generate on page load.
 * - Generate and Generate again are the only things that spend money.
 * - A 60-minute cache and a daily cap, both enforced on the server.
 *
 * WHAT BUILD_07 CHANGED IN THIS FILE:
 * 1. It is mounted on Home in its own place. It used to live inside the on-page
 *    chat's slot, so removing that chat would have taken the summary with it.
 * 2. THE AUTO-FOLDING IS GONE. It used to hide itself for the rest of the IST
 *    day once he had expanded it, remembered in localStorage. The mockup he
 *    approved says the summary stays until he presses Generate again, and on
 *    12 September he ruled for the mockup: the clarity pass's folding rule is
 *    for EXPLANATIONS, and the summary is content he has paid for. A manual
 *    Show and Hide remains, and it resets on reload to showing.
 * 3. It says which model wrote it, or says that was never recorded. Rows
 *    backfilled by migration 026 have no model on them and must not borrow one.
 */

import { api } from '../api.js';
import { createTTSButton } from './tts-player.js';
import { hint } from './position-area.js';
import { escapeHtml } from '../utils/display.js';

/** The clock time in IST of an instant, for the stamp he reads. */
function istClock(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const ist = new Date(d.getTime() + (330 + d.getTimezoneOffset()) * 60000);
  return `${String(ist.getHours()).padStart(2, '0')}:${String(ist.getMinutes()).padStart(2, '0')}`;
}

function ageWords(minutes) {
  if (minutes === null || minutes === undefined) return '';
  if (minutes < 1) return 'just now';
  if (minutes === 1) return '1 minute ago';
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours === 1) return 'an hour ago';
  if (hours < 24) return `${hours} hours ago`;
  return 'more than a day ago';
}

export class SoFarTodayCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.state = {
      isLoading: false,
      hasData: false,
      text: '',
      sources: [],
      model: '',
      generatedAt: null,
      ageMinutes: null,
      callCountToday: 0,
      dailyCap: 8,
      capReached: false,
      errorMessage: null,
      notStoredWarning: null,
      // In memory only. A reload shows the summary again, which is the point:
      // it stays until he generates it again.
      hidden: false,
    };
  }

  async init() {
    this.render();
    await this.loadSaved();
  }

  /** Reads the day's saved row. No model call, so this is safe on load. */
  async loadSaved() {
    try {
      const res = await api.getSoFarToday();
      if (!res) return;
      if (res.has_data) {
        this.state = {
          ...this.state,
          hasData: true,
          text: res.text || '',
          sources: res.sources || [],
          model: res.model || '',
          generatedAt: res.generated_at,
          ageMinutes: typeof res.age_minutes === 'number' ? res.age_minutes : null,
          callCountToday: res.call_count_today || 0,
          dailyCap: res.daily_cap || 8,
          capReached: res.cap_reached || false,
          errorMessage: null,
          notStoredWarning: null,
          hidden: false,
        };
      } else {
        this.state.callCountToday = res.call_count_today || 0;
        this.state.dailyCap = res.daily_cap || 8;
        this.state.capReached = res.cap_reached || false;
        // An unreadable store is NOT an empty day. The server says so in words
        // and names what it looked for; the card repeats it rather than
        // showing a blank that reads like a quiet market.
        this.state.errorMessage = String(res.message || '').startsWith('unavailable')
          ? res.message
          : null;
      }
      this.render();
    } catch (err) {
      // The card says what it could not read and where it looked, rather than
      // showing an empty state that looks like "nothing has happened today".
      this.state.errorMessage =
        `Today's saved summary could not be read from the database (${err.message}). ` +
        'Generate writes a new one; it does not depend on this read.';
      this.render();
    }
  }

  async generate(force = false) {
    if (this.state.isLoading || this.state.capReached) return;

    this.state.isLoading = true;
    this.state.errorMessage = null;
    this.state.notStoredWarning = null;
    this.render();

    try {
      const res = await api.generateSoFarToday(force);
      this.state = {
        ...this.state,
        isLoading: false,
        hasData: Boolean((res.text || '').trim()),
        text: res.text || '',
        sources: res.sources || [],
        model: res.model || '',
        generatedAt: res.generated_at,
        ageMinutes: typeof res.age_minutes === 'number' ? res.age_minutes : 0,
        callCountToday: res.call_count_today || 1,
        dailyCap: res.daily_cap || 8,
        capReached: res.cap_reached || false,
        errorMessage: null,
        // He paid for it and it did not save. That is not a detail.
        notStoredWarning: res.stored === false ? res.message : null,
        hidden: false,
      };
    } catch (err) {
      this.state.isLoading = false;
      const msg = err.message || 'Failed to generate the session summary';
      if (msg.includes('Daily cap reached') || msg.includes('429')) {
        this.state.capReached = true;
        this.state.errorMessage = `${this.state.dailyCap} summaries is the cap for one day. It resets at midnight IST.`;
      } else {
        this.state.errorMessage = msg;
      }
    }

    this.render();
  }

  toggleHidden() {
    this.state.hidden = !this.state.hidden;
    this.render();
  }

  _stampLine() {
    const clock = istClock(this.state.generatedAt);
    const age = ageWords(this.state.ageMinutes);
    if (!clock) return 'Saved for today. It stays until you generate it again.';
    const agePart = age ? `, ${age}` : '';
    return `Written at ${clock} IST${agePart}, and it stays until you generate it again.`;
  }

  _modelLine() {
    if (this.state.model) return `Written by ${escapeHtml(this.state.model)}.`;
    // Migration 026's backfilled rows never recorded one. Saying so is the
    // whole difference between a record and a guess.
    return 'The model was not recorded on this row.';
  }

  render() {
    const {
      isLoading, hasData, text, sources, callCountToday, dailyCap,
      capReached, errorMessage, notStoredWarning, hidden,
    } = this.state;

    const capChip = hint(
      `${callCountToday} of ${dailyCap} today`,
      'This summary is a paid, search-grounded call. It never runs on its own: ' +
      'only this button spends anything, a second press inside an hour returns ' +
      'the one already stored, and the day stops at this cap.'
    );

    let body = '';

    if (isLoading) {
      body = `
        <div class="sft-loading">
          <div class="sft-spinner"></div>
          <div>Reading the tape since 09:15 IST, with search.</div>
        </div>`;
    } else if (hasData && text) {
      const paragraphs = text.split('\n\n').filter((p) => p.trim());
      const formatted = paragraphs.map((p) => {
        const safe = escapeHtml(p).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        if (p.includes('Bear Put Spread') || p.includes('Bull Call Spread') || p.toLowerCase().includes('setup:')) {
          return `<div class="sft-setup">${safe}</div>`;
        }
        return `<p>${safe}</p>`;
      }).join('');

      const sourcesHtml = (sources && sources.length)
        ? `<div class="sft-sources">
             <span class="k">Sources</span>
             ${sources.map((s) => {
               const title = String(s.title || s.url || s.uri || '');
               const shown = title.length > 32 ? `${title.slice(0, 30)}...` : title;
               return `<a href="${escapeHtml(s.url || s.uri || '#')}" target="_blank" rel="noopener noreferrer">&#8599; ${escapeHtml(shown)}</a>`;
             }).join('')}
           </div>`
        : '';

      body = hidden
        ? `<p class="sft-folded">Today's summary is hidden. It is still saved.</p>`
        : `<div class="sft-summary">
             <span class="sft-stamp">${escapeHtml(this._stampLine())}</span>
             <div class="sft-content">${formatted}</div>
             ${sourcesHtml}
             <p class="sft-model">${this._modelLine()}</p>
           </div>`;
    } else if (String(errorMessage || '').startsWith('unavailable')) {
      // The store could not be read. Saying "nothing saved yet" underneath
      // that would be two contradictory claims on one card.
      body = '';
    } else {
      body = `
        <div class="sft-empty">
          <p>Nothing is saved for today yet. Generate reads the tape since the
             09:15 IST open, with search, and saves what it finds as today's
             record. It is the only thing on this page that spends money.</p>
        </div>`;
    }

    const warning = notStoredWarning
      ? `<div class="sft-error">${escapeHtml(notStoredWarning)}</div>`
      : '';
    const error = errorMessage
      ? `<div class="sft-error">${escapeHtml(errorMessage)}</div>`
      : '';

    const generateLabel = capReached
      ? 'Cap reached for today'
      : (hasData ? 'Generate again' : 'Generate');

    this.container.innerHTML = `
      <div class="card sft-card">
        <h3>
          <span>So far today</span>
          <span class="r">
            <span class="sft-cap">${capChip}</span>
            <span id="sft-tools"></span>
            ${hasData ? `<button id="btn-hide-so-far" class="btn" type="button" aria-expanded="${!hidden}">${hidden ? 'Show' : 'Hide'}</button>` : ''}
            <button id="btn-generate-so-far" class="btn pri" type="button" ${isLoading || capReached ? 'disabled' : ''}>
              ${escapeHtml(generateLabel)}
            </button>
          </span>
        </h3>
        <div class="cb">${error}${warning}${body}</div>
      </div>
    `;

    const genBtn = this.container.querySelector('#btn-generate-so-far');
    if (genBtn) genBtn.addEventListener('click', () => this.generate(this.state.hasData));

    const hideBtn = this.container.querySelector('#btn-hide-so-far');
    if (hideBtn) hideBtn.addEventListener('click', () => this.toggleHidden());

    // The same read-aloud button the chat uses. It only speaks what is shown.
    if (hasData && text && !hidden) {
      const tools = this.container.querySelector('#sft-tools');
      if (tools && typeof tools.appendChild === 'function') {
        try {
          tools.appendChild(createTTSButton(() => this.state.text));
        } catch (_) {
          // No audio in this environment. The summary is still readable.
        }
      }
    }
  }
}

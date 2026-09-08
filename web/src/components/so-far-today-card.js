/**
 * "So Far Today", the grounded market summary he pays for.
 *
 * The cost gate does not change, ever:
 * - Never auto-fires on mount or page load. init() only reads the cache status.
 * - Manual Generate / Refresh button.
 * - 60-minute cache on the server, daily cap of 8 calls, enforced server-side
 *   and reflected in the disabled state here.
 *
 * Round 2 added three things and changed nothing about the gate:
 * - A play button that reads the summary aloud, the same one the chat uses.
 * - A collapse control. Once he has generated it and expanded it once, it
 *   starts collapsed for the rest of that day. The flag is stored against
 *   today's IST date in localStorage, so a new day starts expanded again.
 * - The card now sits on the desk's own tokens, so it no longer looks like a
 *   foreign object among panels that have depth.
 */

import { api } from '../api.js';
import { createTTSButton } from './tts-player.js';
import { escapeHtml } from '../utils/display.js';

function istDateKey(now = new Date()) {
  // YYYY-MM-DD in IST, so "today" is his trading day, not the browser's UTC day.
  const ist = new Date(now.getTime() + (330 + now.getTimezoneOffset()) * 60000);
  return `swayam_sft_expanded_${ist.getFullYear()}-${String(ist.getMonth() + 1).padStart(2, '0')}-${String(ist.getDate()).padStart(2, '0')}`;
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
      generatedAt: null,
      ageMinutes: 0,
      callCountToday: 0,
      dailyCap: 8,
      capReached: false,
      errorMessage: null,
      collapsed: false,
    };
  }

  async init() {
    this.render();
    await this.checkCacheStatus();
  }

  /** True once he has expanded today's summary at least once. */
  _expandedOnceToday() {
    try {
      return localStorage.getItem(istDateKey()) === '1';
    } catch (_) {
      return false;
    }
  }

  _rememberExpandedToday() {
    try {
      localStorage.setItem(istDateKey(), '1');
    } catch (_) {}
  }

  async checkCacheStatus() {
    try {
      const res = await api.getSoFarToday();
      if (res && res.has_data) {
        this.state = {
          ...this.state,
          hasData: true,
          text: res.text || '',
          sources: res.sources || [],
          generatedAt: res.generated_at,
          ageMinutes: res.age_minutes || 0,
          callCountToday: res.call_count_today || 0,
          dailyCap: res.daily_cap || 8,
          capReached: res.cap_reached || false,
          errorMessage: null,
          // Generated and expanded earlier today: start folded for the rest of the day.
          collapsed: this._expandedOnceToday(),
        };
        this.render();
      } else if (res) {
        this.state.callCountToday = res.call_count_today || 0;
        this.state.dailyCap = res.daily_cap || 8;
        this.state.capReached = res.cap_reached || false;
        this.render();
      }
    } catch (err) {
      console.warn('SoFarToday cache check error:', err);
    }
  }

  async generate(force = false) {
    if (this.state.isLoading || this.state.capReached) return;

    this.state.isLoading = true;
    this.state.errorMessage = null;
    this.render();

    try {
      const res = await api.generateSoFarToday(force);
      this.state = {
        ...this.state,
        isLoading: false,
        hasData: true,
        text: res.text || '',
        sources: res.sources || [],
        generatedAt: res.generated_at,
        ageMinutes: res.age_minutes || 0,
        callCountToday: res.call_count_today || 1,
        dailyCap: res.daily_cap || 8,
        capReached: res.cap_reached || false,
        errorMessage: null,
        collapsed: false,
      };
      // He is reading it now. From the next load onward it starts collapsed.
      this._rememberExpandedToday();
    } catch (err) {
      this.state.isLoading = false;
      const msg = err.message || 'Failed to generate session summary';
      if (msg.includes('Daily cap reached') || msg.includes('429')) {
        this.state.capReached = true;
        this.state.errorMessage = 'Daily cap reached (8 calls). Resets at 09:15 IST tomorrow.';
      } else {
        this.state.errorMessage = msg;
      }
    }

    this.render();
  }

  toggleCollapsed() {
    this.state.collapsed = !this.state.collapsed;
    if (!this.state.collapsed) this._rememberExpandedToday();
    this.render();
  }

  render() {
    const { isLoading, hasData, text, sources, ageMinutes, callCountToday, dailyCap, capReached, errorMessage, collapsed } = this.state;

    let ageStr = 'Just now';
    if (ageMinutes === 1) ageStr = '1 min ago';
    else if (ageMinutes > 1) ageStr = `${ageMinutes} min ago`;

    const capInfo = `Calls today: ${callCountToday}/${dailyCap}`;

    let bodyHtml = '';

    if (isLoading) {
      bodyHtml = `
        <div class="sft-loading">
          <div class="sft-spinner"></div>
          <div>Grounding Gemini with real-time Indian market search...</div>
        </div>`;
    } else if (hasData && text) {
      const paragraphs = text.split('\n\n').filter((p) => p.trim());
      const formattedParas = paragraphs.map((p) => {
        const safe = escapeHtml(p).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        if (p.includes('Bear Put Spread') || p.includes('Bull Call Spread') || p.toLowerCase().includes('setup:')) {
          return `<div class="sft-setup">${safe}</div>`;
        }
        return `<p>${safe}</p>`;
      }).join('');

      let sourcesHtml = '';
      if (sources && sources.length > 0) {
        sourcesHtml = `
          <div class="sft-sources">
            <span class="k">Sources</span>
            ${sources.map((s) => {
              const title = String(s.title || s.url || '');
              return `<a href="${escapeHtml(s.url || '#')}" target="_blank" rel="noopener noreferrer">↗ ${escapeHtml(title.length > 32 ? `${title.slice(0, 30)}...` : title)}</a>`;
            }).join('')}
          </div>`;
      }

      bodyHtml = collapsed
        ? ''
        : `<div class="sft-content">${formattedParas}</div>${sourcesHtml}`;
    } else {
      bodyHtml = `
        <div class="sft-empty">
          <div>Click <strong>Generate</strong> to summarize today's market session so far (09:15 IST to now), including price ranges, VIX, leaders/laggards, and breaking macro news.</div>
          <button id="btn-generate-so-far" class="btn pri" type="button" ${capReached ? 'disabled' : ''}>
            ${capReached ? 'Daily cap reached' : '⚡ Generate Summary'}
          </button>
        </div>`;
    }

    const errorBanner = errorMessage
      ? `<div class="sft-error">${escapeHtml(errorMessage)}</div>`
      : '';

    this.container.innerHTML = `
      <div class="card sft-card">
        <h3>
          <span>☀ SO FAR TODAY</span>
          ${hasData ? `<span class="chip c-info">Generated ${escapeHtml(ageStr)}</span>` : ''}
          <span class="r" style="display:inline-flex;align-items:center;gap:8px">
            <span title="Cost-gate: Maximum 8 grounded calls per trading day">${escapeHtml(capInfo)}</span>
            <span id="sft-tools" style="display:inline-flex;align-items:center;gap:4px"></span>
            ${hasData ? `
              <button id="btn-refresh-so-far" class="btn" type="button" ${isLoading || capReached ? 'disabled' : ''}
                title="${capReached ? 'Daily cap reached — resets 09:15 IST tomorrow' : 'Refresh session summary (counts towards daily cap)'}">
                ${capReached ? 'Cap reached' : '🔄 Refresh'}
              </button>
              <button id="btn-collapse-so-far" class="btn" type="button" aria-expanded="${!collapsed}"
                title="${collapsed ? 'Show the summary' : 'Hide the summary'}">${collapsed ? 'Show' : 'Hide'}</button>
            ` : ''}
          </span>
        </h3>
        ${errorBanner || bodyHtml ? `<div class="cb">${errorBanner}${bodyHtml}</div>` : ''}
      </div>
    `;

    const genBtn = this.container.querySelector('#btn-generate-so-far');
    if (genBtn) genBtn.addEventListener('click', () => this.generate(false));

    const refBtn = this.container.querySelector('#btn-refresh-so-far');
    if (refBtn) refBtn.addEventListener('click', () => this.generate(true));

    const collapseBtn = this.container.querySelector('#btn-collapse-so-far');
    if (collapseBtn) collapseBtn.addEventListener('click', () => this.toggleCollapsed());

    // The same read-aloud button the chat uses. It only speaks what is on screen.
    if (hasData && text) {
      const tools = this.container.querySelector('#sft-tools');
      if (tools && typeof tools.appendChild === 'function') {
        try {
          tools.appendChild(createTTSButton(() => this.state.text));
        } catch (_) {
          // No audio in this environment; the summary is still readable.
        }
      }
    }
  }
}

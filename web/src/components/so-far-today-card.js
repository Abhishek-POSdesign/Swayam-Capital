/**
 * "So Far Today" Grounded Market Summary Card Component.
 *
 * Implements strict cost gate:
 * - Never auto-fires on mount / page load
 * - Manual [Generate] / [Refresh] button
 * - 60-minute cache display
 * - Daily cap (8 calls) enforced with disabled state
 * - Cites real-time sources from Google Search Grounding
 */

import { api } from '../api.js';

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
    };
  }

  async init() {
    this.render();
    await this.checkCacheStatus();
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
      };
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

  render() {
    const { isLoading, hasData, text, sources, ageMinutes, callCountToday, dailyCap, capReached, errorMessage } = this.state;

    // Relative age string
    let ageStr = 'Just now';
    if (ageMinutes === 1) ageStr = '1 min ago';
    else if (ageMinutes > 1) ageStr = `${ageMinutes} min ago`;

    // Cap string
    const capInfo = `Calls today: ${callCountToday}/${dailyCap}`;

    let bodyHtml = '';

    if (isLoading) {
      bodyHtml = `
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 28px 16px; gap: 12px;">
          <div style="width: 28px; height: 28px; border: 3px solid var(--dl-track); border-top-color: var(--accent-amber); border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
          <div style="font-size: 0.85rem; color: var(--dl-fg-2); font-family: var(--font-sans);">
            Grounding Gemini with real-time Indian market search...
          </div>
        </div>
      `;
    } else if (hasData && text) {
      // Split into paragraphs
      const paragraphs = text.split('\n\n').filter(p => p.trim());
      const formattedParas = paragraphs.map(p => {
        // Highlight setup recommendation sentence if at the end
        if (p.includes('Bear Put Spread') || p.includes('Bull Call Spread') || p.toLowerCase().includes('setup:')) {
          return `
            <div style="background: var(--dl-card-2); border-left: 3px solid var(--accent-amber); padding: 10px 14px; border-radius: 0 6px 6px 0; margin-top: 10px; font-weight: 500; color: var(--dl-fg);">
              ${p.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}
            </div>
          `;
        }
        return `<p style="margin: 0 0 10px 0; line-height: 1.55; color: var(--dl-fg); font-size: 0.88rem;">${p.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</p>`;
      }).join('');

      let sourcesHtml = '';
      if (sources && sources.length > 0) {
        sourcesHtml = `
          <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--dl-line); display: flex; flex-wrap: wrap; align-items: center; gap: 8px;">
            <span class="eyebrow" style="font-size: 0.68rem; color: var(--dl-fg-3);">SOURCES:</span>
            ${sources.map(s => `
              <a href="${s.url}" target="_blank" rel="noopener noreferrer" style="font-size: 0.75rem; color: var(--accent-sage); text-decoration: none; background: var(--dl-card-2); padding: 3px 8px; border-radius: 4px; border: 1px solid var(--dl-line); display: inline-flex; align-items: center; gap: 4px; transition: border-color 0.15s;" onmouseover="this.style.borderColor='var(--accent-sage)'" onmouseout="this.style.borderColor='var(--dl-line)'">
                <span>↗</span> ${s.title.length > 32 ? s.title.slice(0, 30) + '...' : s.title}
              </a>
            `).join('')}
          </div>
        `;
      }

      bodyHtml = `
        <div style="display: flex; flex-direction: column;">
          <div class="so-far-content" style="font-family: var(--font-sans);">
            ${formattedParas}
          </div>
          ${sourcesHtml}
        </div>
      `;
    } else {
      // Empty state
      bodyHtml = `
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px 16px; gap: 12px; text-align: center;">
          <div style="font-size: 0.9rem; color: var(--dl-fg-2); max-width: 480px; line-height: 1.5;">
            Click <strong>Generate</strong> to summarize today's market session so far (09:15 IST to now), including price ranges, VIX, leaders/laggards, and breaking macro news.
          </div>
          <button id="btn-generate-so-far" type="button" ${capReached ? 'disabled' : ''} style="background: var(--accent-amber); color: #111; font-weight: 600; padding: 8px 20px; border-radius: 6px; border: none; font-size: 0.85rem; cursor: ${capReached ? 'not-allowed' : 'pointer'}; opacity: ${capReached ? 0.6 : 1}; display: inline-flex; align-items: center; gap: 6px; transition: transform 0.1s ease;">
            <span>⚡</span> ${capReached ? 'Daily cap reached' : 'Generate Summary'}
          </button>
        </div>
      `;
    }

    let errorBanner = '';
    if (errorMessage) {
      errorBanner = `
        <div style="background: rgba(224, 102, 102, 0.12); border: 1px solid var(--accent-coral); color: var(--accent-coral); padding: 8px 12px; border-radius: 6px; font-size: 0.8rem; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <span>${errorMessage}</span>
        </div>
      `;
    }

    this.container.innerHTML = `
      <div class="tile so-far-today-tile span-12" style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: 10px; padding: 18px 20px; box-sizing: border-box; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.12);">
        <!-- Top Header Bar -->
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--dl-line); padding-bottom: 10px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.05rem;">☀</span>
            <span class="eyebrow" style="color: var(--dl-fg); font-weight: 700; font-size: 0.82rem; letter-spacing: 0.06em;">SO FAR TODAY</span>
            ${hasData ? `<span class="badge" style="background: var(--dl-card-2); color: var(--dl-fg-2); border: 1px solid var(--dl-line); font-size: 0.72rem; padding: 2px 8px; border-radius: 12px;">Generated ${ageStr}</span>` : ''}
          </div>

          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="mono-nums" style="font-size: 0.72rem; color: var(--dl-fg-3);" title="Cost-gate: Maximum 8 grounded calls per trading day">${capInfo}</span>
            ${hasData ? `
              <button id="btn-refresh-so-far" type="button" ${isLoading || capReached ? 'disabled' : ''} style="background: var(--dl-card-2); border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 5px 12px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; cursor: ${isLoading || capReached ? 'not-allowed' : 'pointer'}; opacity: ${isLoading || capReached ? 0.6 : 1}; display: inline-flex; align-items: center; gap: 5px;" title="${capReached ? 'Daily cap reached — resets 09:15 IST tomorrow' : 'Refresh session summary (counts towards daily cap)'}">
                <span>🔄</span> ${capReached ? 'Cap reached' : 'Refresh'}
              </button>
            ` : ''}
          </div>
        </div>

        ${errorBanner}
        ${bodyHtml}
      </div>
    `;

    // Attach listeners
    const genBtn = this.container.querySelector('#btn-generate-so-far');
    if (genBtn) {
      genBtn.addEventListener('click', () => this.generate(false));
    }

    const refBtn = this.container.querySelector('#btn-refresh-so-far');
    if (refBtn) {
      refBtn.addEventListener('click', () => this.generate(true));
    }
  }
}

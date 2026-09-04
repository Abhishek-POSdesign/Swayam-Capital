/**
 * AI Voice & Memory Settings Drawer for Swayam Capital (BUILD-9-FIXES-B).
 *
 * Provides user controls for:
 * - Indian English TTS voice profiles (Male: swayam_calm, Female: swayam_warm)
 * - Speech rate slider (0.5x - 2.0x, default 0.90x)
 * - Auto-play toggle
 * - Layer 3 Notebook memory entries (view, delete)
 * - Layer 3 Pinned trading rules (view, unpin)
 * - Session ID copy & reset
 */

import { getTTSPreferences, setTTSPreferences } from './tts-player.js';

export class AISettingsDrawer {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onClose, onNewSession }
    this.isOpen = false;
    this.notebookEntries = [];
    this.pinnedRules = [];
  }

  init() {
    this.render();
  }

  open(sessionId = '') {
    this.sessionId = sessionId;
    this.isOpen = true;
    const drawer = this.container.querySelector('#ai-settings-drawer-panel');
    if (drawer) drawer.style.transform = 'translateX(0)';
    this.loadData();
  }

  close() {
    this.isOpen = false;
    const drawer = this.container.querySelector('#ai-settings-drawer-panel');
    if (drawer) drawer.style.transform = 'translateX(100%)';
    if (this.options.onClose) this.options.onClose();
  }

  render() {
    const { voice, rate, autoPlay } = getTTSPreferences();

    this.container.innerHTML = `
      <div id="ai-settings-drawer-panel" style="position: fixed; top: 0; right: 0; width: 380px; max-width: 90vw; height: 100vh; background: var(--dl-card, #191b21); border-left: 2px solid var(--accent-lilac, #ac9fd2); box-shadow: -6px 0 24px rgba(0,0,0,0.5); transform: translateX(100%); transition: transform var(--dur-base, 200ms) ease; z-index: 1000; display: flex; flex-direction: column;">
        
        <!-- Header -->
        <div style="background: var(--dl-rail, #16171c); padding: 16px 20px; border-bottom: 1px solid var(--dl-line); display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.1rem;">⚙️</span>
            <span style="font-weight: 700; font-size: 0.95rem; color: var(--dl-fg);">AI Partner Settings</span>
          </div>
          <button id="btn-close-settings" type="button" style="background: transparent; border: none; color: var(--dl-fg-2); font-size: 1.2rem; cursor: pointer; padding: 4px;">✕</button>
        </div>

        <!-- Body Content -->
        <div style="flex: 1; overflow-y: auto; padding: 18px 20px; display: flex; flex-direction: column; gap: 20px;">
          
          <!-- Section 1: Voice & Speech Engine -->
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <span class="eyebrow" style="color: var(--accent-lilac); font-size: 0.72rem; font-weight: 700;">VOICE & SPEECH (INDIAN ENGLISH)</span>
            
            <div style="display: flex; flex-direction: column; gap: 6px; font-size: 0.85rem; color: var(--dl-fg);">
              <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                <input type="radio" name="tts_voice" value="swayam_calm" ${voice === 'swayam_calm' ? 'checked' : ''}>
                <span><strong>Male Voice</strong> (Calm & Focused · en-IN-Neural2-B)</span>
              </label>
              <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                <input type="radio" name="tts_voice" value="swayam_warm" ${voice === 'swayam_warm' ? 'checked' : ''}>
                <span><strong>Female Voice</strong> (Warm & Clear · en-IN-Neural2-A)</span>
              </label>
            </div>

            <!-- Speech Rate Slider -->
            <div style="display: flex; flex-direction: column; gap: 4px; margin-top: 6px;">
              <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--dl-fg-2);">
                <span>Speech Rate</span>
                <span id="label-speech-rate" style="font-family: var(--font-mono); font-weight: 600; color: var(--dl-fg);">${rate.toFixed(2)}x</span>
              </div>
              <input id="slider-speech-rate" type="range" min="0.5" max="2.0" step="0.05" value="${rate}" style="accent-color: var(--accent-lilac); cursor: pointer;">
            </div>

            <!-- Auto-play Toggle -->
            <label style="display: flex; align-items: center; gap: 8px; font-size: 0.82rem; color: var(--dl-fg-2); margin-top: 4px; cursor: pointer;">
              <input id="check-auto-play" type="checkbox" ${autoPlay ? 'checked' : ''}>
              <span>Auto-play spoken audio on new replies</span>
            </label>
          </div>

          <!-- Section 2: Pinned Rules & Constraints (Layer 3) -->
          <div style="display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--dl-line); padding-top: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span class="eyebrow" style="color: var(--accent-lilac); font-size: 0.72rem; font-weight: 700;">PINNED RULES (PERMANENT CONTEXT)</span>
              <span id="pinned-count-badge" style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--dl-fg-3);">0 rules</span>
            </div>
            
            <div style="display: flex; gap: 6px;">
              <input id="input-new-rule" type="text" placeholder="Add permanent trading rule..." style="flex: 1; background: var(--dl-card-2); color: var(--dl-fg); border: 1px solid var(--dl-line); border-radius: 6px; padding: 4px 8px; font-size: 0.78rem;">
              <button id="btn-add-rule" type="button" style="background: var(--accent-lilac); color: #101116; border: none; border-radius: 6px; padding: 4px 10px; font-size: 0.75rem; font-weight: 600; cursor: pointer;">Add</button>
            </div>

            <div id="settings-pinned-list" style="max-height: 140px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px;">
              <span style="font-size: 0.8rem; color: var(--dl-fg-3);">Loading pinned directives...</span>
            </div>
          </div>

          <!-- Section 3: Memory Notebook Entries (Layer 3) -->
          <div style="display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--dl-line); padding-top: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span class="eyebrow" style="color: var(--accent-lilac); font-size: 0.72rem; font-weight: 700;">MEMORY NOTEBOOK (INSIGHTS)</span>
              <span id="notebook-count-badge" style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--dl-fg-3);">0 notes</span>
            </div>
            
            <div style="display: flex; gap: 6px;">
              <input id="input-new-note" type="text" placeholder="Add manual memory note..." style="flex: 1; background: var(--dl-card-2); color: var(--dl-fg); border: 1px solid var(--dl-line); border-radius: 6px; padding: 4px 8px; font-size: 0.78rem;">
              <button id="btn-add-note" type="button" style="background: var(--accent-lilac); color: #101116; border: none; border-radius: 6px; padding: 4px 10px; font-size: 0.75rem; font-weight: 600; cursor: pointer;">Add</button>
            </div>

            <div id="settings-notebook-list" style="max-height: 160px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px;">
              <span style="font-size: 0.8rem; color: var(--dl-fg-3);">Loading notebook memories...</span>
            </div>
          </div>

          <!-- Section 4: Session Information -->
          <div style="display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--dl-line); padding-top: 16px;">
            <span class="eyebrow" style="color: var(--dl-fg-3); font-size: 0.72rem;">ACTIVE SESSION</span>
            <div style="display: flex; gap: 8px; align-items: center;">
              <input id="input-active-session" type="text" readonly style="flex: 1; background: var(--dl-card-2); color: var(--dl-fg-2); border: 1px solid var(--dl-line); border-radius: 6px; padding: 6px 10px; font-family: var(--font-mono); font-size: 0.75rem;">
              <button id="btn-copy-session" type="button" style="background: transparent; border: 1px solid var(--dl-line); color: var(--dl-fg); border-radius: 6px; padding: 6px 10px; font-size: 0.75rem; cursor: pointer;">Copy</button>
            </div>
          </div>

        </div>

      </div>
    `;

    this._attachEventHandlers();
  }

  _attachEventHandlers() {
    const root = this.container;

    // Close button
    const closeBtn = root.querySelector('#btn-close-settings');
    if (closeBtn) closeBtn.addEventListener('click', () => this.close());

    // Voice radios
    root.querySelectorAll('input[name="tts_voice"]').forEach((radio) => {
      radio.addEventListener('change', (e) => {
        setTTSPreferences({ voice: e.target?.value || radio.value });
      });
    });

    // Speech rate slider
    const slider = root.querySelector('#slider-speech-rate');
    const labelRate = root.querySelector('#label-speech-rate');
    if (slider) {
      slider.addEventListener('input', (e) => {
        const val = parseFloat(e.target?.value || slider.value);
        if (labelRate && !isNaN(val)) labelRate.textContent = `${val.toFixed(2)}x`;
        if (!isNaN(val)) setTTSPreferences({ rate: val });
      });
    }

    // Auto-play checkbox
    const checkAuto = root.querySelector('#check-auto-play');
    if (checkAuto) {
      checkAuto.addEventListener('change', (e) => {
        setTTSPreferences({ autoPlay: e.target?.checked ?? checkAuto.checked });
      });
    }

    // Copy session ID
    const copyBtn = root.querySelector('#btn-copy-session');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        if (this.sessionId) {
          navigator.clipboard.writeText(this.sessionId);
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
        }
      });
    }

    // Add manual rule
    const btnAddRule = root.querySelector('#btn-add-rule');
    const inputRule = root.querySelector('#input-new-rule');
    if (btnAddRule && inputRule) {
      const submitRule = async () => {
        const text = inputRule.value.trim();
        if (!text) return;
        inputRule.value = '';
        try {
          await fetch('/api/ai/pinned', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rule_text: text }),
          });
          await this.loadPinned();
        } catch (_) {}
      };
      btnAddRule.addEventListener('click', submitRule);
      inputRule.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitRule(); });
    }

    // Add manual note
    const btnAddNote = root.querySelector('#btn-add-note');
    const inputNote = root.querySelector('#input-new-note');
    if (btnAddNote && inputNote) {
      const submitNote = async () => {
        const text = inputNote.value.trim();
        if (!text) return;
        inputNote.value = '';
        try {
          await fetch('/api/ai/notebook', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ entry_text: text, source_conversation_id: this.sessionId }),
          });
          await this.loadNotebook();
        } catch (_) {}
      };
      btnAddNote.addEventListener('click', submitNote);
      inputNote.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitNote(); });
    }
  }

  async loadData() {
    const inputSession = this.container.querySelector('#input-active-session');
    if (inputSession) inputSession.value = this.sessionId || 'N/A';

    await Promise.all([this.loadPinned(), this.loadNotebook()]);
  }

  async loadPinned() {
    const listEl = this.container.querySelector('#settings-pinned-list');
    const countBadge = this.container.querySelector('#pinned-count-badge');
    try {
      const resp = await fetch('/api/ai/pinned');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const items = await resp.json();
      this.pinnedRules = items;

      if (countBadge) countBadge.textContent = `${items.length} rules`;
      if (!listEl) return;

      if (items.length === 0) {
        listEl.innerHTML = '<span style="font-size: 0.78rem; color: var(--dl-fg-3);">No active pinned rules.</span>';
        return;
      }

      listEl.innerHTML = items.map((r) => `
        <div style="background: var(--dl-card-2); border: 1px solid var(--dl-line); border-radius: 8px; padding: 6px 10px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
          <span style="font-size: 0.8rem; color: var(--dl-fg); line-height: 1.4; flex: 1;">${r.rule_text}</span>
          <button type="button" class="btn-unpin-rule" data-id="${r.id}" style="background: transparent; border: none; color: var(--accent-coral); font-size: 0.75rem; cursor: pointer; padding: 2px 4px;" title="Unpin rule">✕</button>
        </div>
      `).join('');

      listEl.querySelectorAll('.btn-unpin-rule').forEach((b) => {
        b.addEventListener('click', async () => {
          const id = b.getAttribute('data-id');
          await fetch(`/api/ai/pinned/${id}`, { method: 'DELETE' });
          await this.loadPinned();
        });
      });
    } catch (err) {
      if (listEl) listEl.innerHTML = `<span style="font-size: 0.78rem; color: var(--accent-coral);">Could not load: ${err.message}</span>`;
    }
  }

  async loadNotebook() {
    const listEl = this.container.querySelector('#settings-notebook-list');
    const countBadge = this.container.querySelector('#notebook-count-badge');
    try {
      const resp = await fetch('/api/ai/notebook');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const items = await resp.json();
      this.notebookEntries = items;

      if (countBadge) countBadge.textContent = `${items.length} notes`;
      if (!listEl) return;

      if (items.length === 0) {
        listEl.innerHTML = '<span style="font-size: 0.78rem; color: var(--dl-fg-3);">No memory entries saved yet.</span>';
        return;
      }

      listEl.innerHTML = items.map((n) => `
        <div style="background: var(--dl-card-2); border: 1px solid var(--dl-line); border-radius: 8px; padding: 8px 10px; display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
          <div style="display: flex; flex-direction: column; gap: 3px; flex: 1;">
            <span style="font-size: 0.8rem; color: var(--dl-fg); line-height: 1.4;">${n.entry_text}</span>
            <span style="font-family: var(--font-mono); font-size: 0.68rem; color: var(--dl-fg-3);">${n.created_at.slice(0, 10)}</span>
          </div>
          <button type="button" class="btn-delete-note" data-id="${n.id}" style="background: transparent; border: none; color: var(--accent-coral); font-size: 0.75rem; cursor: pointer; padding: 2px 4px;" title="Delete entry">✕</button>
        </div>
      `).join('');

      listEl.querySelectorAll('.btn-delete-note').forEach((b) => {
        b.addEventListener('click', async () => {
          const id = b.getAttribute('data-id');
          await fetch(`/api/ai/notebook/${id}`, { method: 'DELETE' });
          await this.loadNotebook();
        });
      });
    } catch (err) {
      if (listEl) listEl.innerHTML = `<span style="font-size: 0.78rem; color: var(--accent-coral);">Could not load: ${err.message}</span>`;
    }
  }
}

/**
 * AI Trading Partner Chat Panel for Swayam Capital.
 *
 * Collapsible right-sidebar panel with SSE streaming, conversation history,
 * starter prompts, and daily cost footer.
 *
 * Uses browser-native EventSource for SSE — no additional dependencies.
 *
 * Layout: right-side sidebar, default expanded. Collapses via chevron button.
 * Messages: user = right-aligned accent, assistant = left-aligned text-primary.
 * Markdown: bold, italic, code, lists rendered via simple inline parser.
 */

import { openImageModal, attachmentName } from './chat-surface.js';
import {
  createTTSButton,
  playText,
  stopCurrentPlayback,
  getTTSPreferences,
  setTTSPreferences,
} from './tts-player.js';

const API_BASE = '';

// The voices the TTS backend actually supports (src/swayam/ai/tts.py). No fake options.
const VOICE_OPTIONS = [
  { id: 'swayam_calm', label: 'Swayam Calm', lang: 'Indian English · male' },
  { id: 'swayam_warm', label: 'Swayam Warm', lang: 'Indian English · female' },
];

const STARTER_PROMPTS = [
  "Walk me through today's market open — what's setting up?",
  "Given India VIX is at the 8th percentile, what setups favor this regime?",
  "Anything on the calendar this week I should NOT trade around?",
  "Based on my last 5 trades, what mistake am I repeating?",
];

/** Minimal markdown-to-HTML renderer for AI responses. */
function renderMarkdown(text) {
  if (!text) return '';
  return text
    // Code blocks (```...```)
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // Bullet lists (lines starting with - or *)
    .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    // Line breaks to <br>
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

export class AIChatPanel {
  constructor(container) {
    this.container = container;
    this.conversationId = null;
    this.isCollapsed = false;
    this.currentEventSource = null;
    this.pendingImage = null;
    this.showingSettings = false;
  }

  async init() {
    this._render();
    await this._loadOrCreateConversation();
    await this._loadCostFooter();
  }

  _render() {
    this.container.innerHTML = `
      <div class="ai-panel" id="ai-panel">
        <div class="ai-panel__header">
          <div class="ai-panel__header-left">
            <div class="ai-orb" style="width: 24px; height: 24px; border-radius: 50%; background: var(--accent-blue-tint); color: var(--accent-blue); flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 700;">✦</div>
            <span class="ai-panel__title" style="font-family: var(--font-sans); font-size: 0.92rem; font-weight: 600; color: var(--dl-fg);">Trading Partner</span>
            <span class="ai-panel__conv-title" id="ai-conv-title"></span>
          </div>
          <div class="ai-panel__header-right">
            <div class="ai-model-wrap" style="position: relative;">
              <button class="ai-model-pill" id="ai-model-pill" title="Model: Cloud (Gemini)">☁ Gemini ▾</button>
              <div class="ai-model-menu" id="ai-model-menu" style="display:none;">
                <div class="ai-model-menu__label">Model</div>
                <button class="ai-model-opt ai-model-opt--sel" type="button">☁ Cloud (Gemini)<span class="ai-model-opt__check">✓</span></button>
                <div class="ai-model-menu__note">Swayam runs one cloud model (Vertex AI · Gemini). No local model configured.</div>
              </div>
            </div>
            <button class="ai-btn ai-btn--sm" id="ai-btn-new" title="New conversation">+ New</button>
            <button class="ai-btn ai-btn--sm" id="ai-btn-history" title="Conversation history">History</button>
            <button class="ai-icon-btn" id="ai-btn-settings" title="Voice &amp; AI settings" aria-label="Settings">⚙</button>
            <button class="ai-btn ai-btn--ghost" id="ai-btn-collapse" title="Collapse">❯</button>
          </div>
        </div>

        <div class="ai-panel__body" id="ai-panel-body">
          <div class="ai-messages" id="ai-messages">
            <!-- Messages inserted here -->
          </div>

          <div class="ai-starters" id="ai-starters">
            <p class="ai-starters__label">Ask me something to start:</p>
            ${STARTER_PROMPTS.map(
              (p) => `<button class="ai-starter-btn" data-prompt="${p}">${p}</button>`
            ).join('')}
          </div>

          <div class="ai-error" id="ai-error" style="display:none;"></div>
        </div>

        <!-- Attachment preview -->
        <div id="ai-drawer-attachment-preview" style="display: none; align-items: center; gap: 8px; padding: 6px 12px; background: var(--dl-card-2); border-top: 1px solid var(--dl-line);">
          <div style="position: relative; display: inline-block;">
            <img id="ai-drawer-thumb" src="" style="max-height: 70px; max-width: 110px; border-radius: 6px; border: 1px solid var(--dl-line); object-fit: cover;" />
            <button id="ai-drawer-thumb-remove" type="button" title="Remove attachment" style="position: absolute; top: -5px; right: -5px; width: 18px; height: 18px; border-radius: 50%; background: var(--accent-coral); color: #fff; border: none; cursor: pointer; font-size: 11px; display: flex; align-items: center; justify-content: center; line-height: 1;">×</button>
          </div>
          <span id="ai-drawer-attachment-info" style="font-size: 0.72rem; color: var(--dl-fg-3);"></span>
        </div>

        <div class="ai-panel__input-area" id="ai-input-area" style="display: flex; gap: 8px; align-items: flex-end;">
          <textarea
            class="ai-textarea"
            id="ai-textarea"
            rows="2"
            placeholder="Ask anything, or paste a chart screenshot..."
            style="flex: 1;"
          ></textarea>
          <input type="file" id="ai-file-input" accept="image/png,image/jpeg,image/webp,image/gif" style="display: none;" />
          <button class="ai-btn ai-btn--ghost" id="ai-btn-upload" title="Attach screenshot or image (max 5 MB)" style="height: 38px; width: 38px; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; flex-shrink: 0; border: 1px solid var(--dl-line); border-radius: 8px; cursor: pointer;">📎</button>
          <button class="ai-btn ai-btn--primary" id="ai-btn-send">Send</button>
        </div>

        <div class="ai-panel__footer" id="ai-footer">
          <span id="ai-cost-display">Loading usage...</span>
        </div>

        <!-- Settings sub-view (voice + AI), overlays the panel when open -->
        <div class="ai-settings-view" id="ai-settings-view" style="display:none;">
          <div class="ai-settings-view__bar">
            <button class="ai-icon-btn" id="ai-settings-back" title="Back to chat" aria-label="Back">←</button>
            <span class="ai-settings-view__title">Voice &amp; AI settings</span>
          </div>
          <div class="ai-settings-view__body" id="ai-settings-body"></div>
        </div>
      </div>

      <!-- History drawer -->
      <div class="ai-history-drawer" id="ai-history-drawer" style="display:none;">
        <div class="ai-history-drawer__header">
          <span>Conversations</span>
          <button class="ai-btn ai-btn--ghost" id="ai-history-close">✕</button>
        </div>
        <ul class="ai-history-list" id="ai-history-list"></ul>
      </div>
    `;

    this._attachEventListeners();
    this._injectStyles();
  }

  _attachEventListeners() {
    // Collapse toggle
    document.getElementById('ai-btn-collapse').addEventListener('click', () => this._toggleCollapse());

    // New conversation
    document.getElementById('ai-btn-new').addEventListener('click', () => this._startNewConversation());

    // History drawer
    document.getElementById('ai-btn-history').addEventListener('click', () => this._openHistory());
    document.getElementById('ai-history-close').addEventListener('click', () => this._closeHistory());

    // Settings sub-view (voice + AI)
    document.getElementById('ai-btn-settings').addEventListener('click', () => this._openSettings());
    document.getElementById('ai-settings-back').addEventListener('click', () => this._closeSettings());

    // Model pill menu (honest: one cloud model)
    const modelPill = document.getElementById('ai-model-pill');
    const modelMenu = document.getElementById('ai-model-menu');
    if (modelPill && modelMenu) {
      modelPill.addEventListener('click', (e) => {
        e.stopPropagation();
        modelMenu.style.display = modelMenu.style.display === 'none' ? 'block' : 'none';
      });
      document.addEventListener('click', (e) => {
        if (!modelMenu.contains(e.target) && e.target !== modelPill) modelMenu.style.display = 'none';
      });
    }

    // Attachment upload button and file input
    const uploadBtn = document.getElementById('ai-btn-upload');
    const fileInput = document.getElementById('ai-file-input');
    const thumbRemove = document.getElementById('ai-drawer-thumb-remove');
    if (uploadBtn && fileInput) {
      uploadBtn.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          this._setPendingImage(e.target.files[0]);
        }
      });
    }
    if (thumbRemove) {
      thumbRemove.addEventListener('click', () => this._clearPendingImage());
    }

    // Send button
    document.getElementById('ai-btn-send').addEventListener('click', () => this._sendMessage());

    // Enter to send, Shift+Enter for newline
    const textarea = document.getElementById('ai-textarea');
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this._sendMessage();
      }
    });

    // Paste image directly into textarea
    textarea.addEventListener('paste', (e) => {
      const items = (e.clipboardData || window.clipboardData)?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) this._setPendingImage(file);
          break;
        }
      }
    });

    // Starter prompts
    this.container.querySelectorAll('.ai-starter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const prompt = btn.getAttribute('data-prompt');
        document.getElementById('ai-textarea').value = prompt;
        this._sendMessage();
      });
    });
  }

  _setPendingImage(file) {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      alert('Image exceeds maximum allowed size of 5 MB.');
      return;
    }
    const validMimes = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
    if (!validMimes.includes(file.type)) {
      alert('Invalid image format. Allowed formats: PNG, JPEG, WEBP, GIF.');
      return;
    }
    this.pendingImage = file;
    const preview = document.getElementById('ai-drawer-attachment-preview');
    const thumb = document.getElementById('ai-drawer-thumb');
    const info = document.getElementById('ai-drawer-attachment-info');
    if (preview && thumb) {
      thumb.src = URL.createObjectURL(file);
      if (info) info.textContent = `${file.name || 'Screenshot'} (${(file.size / 1024).toFixed(0)} KB)`;
      preview.style.display = 'flex';
    }
  }

  _clearPendingImage() {
    this.pendingImage = null;
    const preview = document.getElementById('ai-drawer-attachment-preview');
    const thumb = document.getElementById('ai-drawer-thumb');
    const info = document.getElementById('ai-drawer-attachment-info');
    const fileInput = document.getElementById('ai-file-input');
    if (thumb) thumb.src = '';
    if (info) info.textContent = '';
    if (preview) preview.style.display = 'none';
    if (fileInput) fileInput.value = '';
  }

  _toggleCollapse() {
    this.isCollapsed = !this.isCollapsed;
    const body = document.getElementById('ai-panel-body');
    const inputArea = document.getElementById('ai-input-area');
    const footer = document.getElementById('ai-panel__footer');
    const btn = document.getElementById('ai-btn-collapse');
    if (this.isCollapsed) {
      body.style.display = 'none';
      if (inputArea) inputArea.style.display = 'none';
      btn.textContent = '❮';
    } else {
      body.style.display = '';
      if (inputArea) inputArea.style.display = '';
      btn.textContent = '❯';
    }
  }

  async _loadOrCreateConversation() {
    try {
      const resp = await fetch(`${API_BASE}/api/ai/conversations`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const conversations = await resp.json();
      if (conversations.length > 0) {
        this.conversationId = conversations[0].conversation_id;
        document.getElementById('ai-conv-title').textContent = conversations[0].title || '';
        await this._loadMessages();
      } else {
        await this._startNewConversation();
      }
    } catch (err) {
      this._showError(`Could not load conversations: ${err.message}`);
    }
  }

  async _startNewConversation() {
    try {
      const resp = await fetch(`${API_BASE}/api/ai/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: null }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      this.conversationId = data.conversation_id;
      document.getElementById('ai-messages').innerHTML = '';
      document.getElementById('ai-conv-title').textContent = '';
      document.getElementById('ai-starters').style.display = '';
      this._clearError();
    } catch (err) {
      this._showError(`Could not create conversation: ${err.message}`);
    }
  }

  async _loadMessages() {
    if (!this.conversationId) return;
    try {
      const resp = await fetch(
        `${API_BASE}/api/ai/conversations/${this.conversationId}/messages`
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const messages = await resp.json();
      const container = document.getElementById('ai-messages');
      container.innerHTML = '';
      messages.forEach((msg) => this._appendMessage(msg.role, msg.content, false, msg.attachment_url));
      if (messages.length > 0) {
        document.getElementById('ai-starters').style.display = 'none';
      }
      this._scrollToBottom();
    } catch (err) {
      this._showError(`Could not load messages: ${err.message}`);
    }
  }

  _appendMessage(role, content, isStreaming = false, attachmentUrl = null) {
    const container = document.getElementById('ai-messages');
    const div = document.createElement('div');
    div.classList.add('ai-message', role === 'user' ? 'ai-message--user' : 'ai-message--assistant');
    if (isStreaming) div.setAttribute('id', 'ai-streaming-msg');

    const inner = document.createElement('div');
    inner.classList.add('ai-message__content');

    if (attachmentUrl) {
      // A thumbnail beside the file name, not a full-size picture in the drawer.
      const att = document.createElement('div');
      att.className = 'chat-att';
      const img = document.createElement('img');
      img.src = attachmentUrl;
      img.alt = 'attached image';
      img.title = 'Click to view full size';
      img.addEventListener('click', () => openImageModal(attachmentUrl));
      const label = document.createElement('span');
      label.textContent = attachmentName(attachmentUrl);
      att.appendChild(img);
      att.appendChild(label);
      inner.appendChild(att);
    }

    if (content) {
      const textDiv = document.createElement('div');
      textDiv.innerHTML = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);
      inner.appendChild(textDiv);
    }

    div.appendChild(inner);
    if (role === 'assistant' && !isStreaming && content) {
      this._addAssistantMeta(div, content);
    }
    container.appendChild(div);
    this._scrollToBottom();
    return inner; // Return inner for streaming delta appends
  }

  async _sendMessage() {
    // User Gesture: trigger notification permission request if not yet prompted (BUILD-11.11 Reinforcement 1)
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
      try {
        Notification.requestPermission().then(async (perm) => {
          if (perm === 'granted' && 'serviceWorker' in navigator) {
            try {
              const reg = await navigator.serviceWorker.ready;
              if (reg && reg.pushManager) {
                const sub = await reg.pushManager.getSubscription();
                if (sub) {
                  api.registerDevice(JSON.stringify(sub), navigator.userAgent, 'web').catch(() => {});
                }
              }
            } catch (_) {}
          }
        }).catch(() => {});
      } catch (_) {}
    }

    const textarea = document.getElementById('ai-textarea');
    const content = textarea.value.trim();
    const imageToUpload = this.pendingImage;
    if ((!content && !imageToUpload) || !this.conversationId) return;

    // Abort any in-progress stream + stop any voice playback
    if (this.currentEventSource) {
      this.currentEventSource.close();
      this.currentEventSource = null;
    }
    stopCurrentPlayback();

    let localAttachmentUrl = null;
    if (imageToUpload) {
      localAttachmentUrl = URL.createObjectURL(imageToUpload);
    }
    this._clearPendingImage();

    textarea.value = '';
    textarea.disabled = true;
    document.getElementById('ai-btn-send').disabled = true;
    this._clearError();

    // Hide starters
    document.getElementById('ai-starters').style.display = 'none';

    // Show user message
    this._appendMessage('user', content, false, localAttachmentUrl);

    // Create assistant placeholder
    const assistantDiv = document.createElement('div');
    assistantDiv.classList.add('ai-message', 'ai-message--assistant');
    assistantDiv.id = 'ai-streaming-msg';
    const inner = document.createElement('div');
    inner.classList.add('ai-message__content');
    inner.innerHTML = '<span class="ai-typing">▋</span>';
    assistantDiv.appendChild(inner);
    document.getElementById('ai-messages').appendChild(assistantDiv);
    this._scrollToBottom();

    // Use fetch + ReadableStream for SSE (EventSource doesn't support POST)
    let fullText = '';
    try {
      let resp;
      if (imageToUpload) {
        const formData = new FormData();
        formData.append('content', content);
        formData.append('image', imageToUpload, imageToUpload.name || 'screenshot.png');
        resp = await fetch(
          `${API_BASE}/api/ai/conversations/${this.conversationId}/messages`,
          {
            method: 'POST',
            body: formData,
          }
        );
      } else {
        resp = await fetch(
          `${API_BASE}/api/ai/conversations/${this.conversationId}/messages`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
          }
        );
      }

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Last incomplete line stays in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') break;

          try {
            const obj = JSON.parse(payload);
            if (obj.error) {
              this._showError(obj.error);
              inner.innerHTML = `<em class="ai-error-inline">${escapeHtml(obj.error)}</em>`;
              break;
            }
            if (obj.delta) {
              fullText += obj.delta;
              inner.innerHTML = renderMarkdown(fullText);
              this._scrollToBottom();
            }
          } catch (_) {
            // Malformed SSE line — skip
          }
        }
      }
    } catch (err) {
      inner.innerHTML = `<em class="ai-error-inline">Trading Partner offline: ${escapeHtml(err.message)}</em>`;
      this._showError(err.message);
    } finally {
      // Remove cursor
      const cursor = inner.querySelector('.ai-typing');
      if (cursor) cursor.remove();
      document.getElementById('ai-streaming-msg')?.removeAttribute('id');
      // Add model tag + Play/Save to the finished reply; auto-play it if Voice replies is on.
      if (fullText && fullText.trim()) {
        this._addAssistantMeta(assistantDiv, fullText);
        if (getTTSPreferences().autoPlay) {
          const playBtn = assistantDiv.querySelector('.ai-msg-action-icon');
          playText(fullText, playBtn || null);
        }
      }
      textarea.disabled = false;
      document.getElementById('ai-btn-send').disabled = false;
      textarea.focus();
      // Refresh cost footer
      await this._loadCostFooter();
      // Update conv title if set
      await this._refreshConvTitle();
    }
  }

  async _loadCostFooter() {
    try {
      const resp = await fetch(`${API_BASE}/api/ai/usage/today`);
      const el = document.getElementById('ai-cost-display');
      if (!resp.ok) {
        if (el) el.innerHTML = `<span style="color: var(--accent-coral);">Usage unavailable (${resp.status})</span>`;
        return;
      }
      const data = await resp.json();
      if (el) {
        el.textContent =
          data.request_count > 0
            ? `Today's AI spend: ₹${data.estimated_cost_inr.toFixed(2)} (${data.request_count} requests)`
            : `Today's AI spend: ₹0.00 (0 requests)`;
      }
    } catch (err) {
      const el = document.getElementById('ai-cost-display');
      if (el) el.innerHTML = `<span style="color: var(--accent-coral);">Usage error: ${err.message}</span>`;
    }
  }

  async _refreshConvTitle() {
    if (!this.conversationId) return;
    try {
      const resp = await fetch(`${API_BASE}/api/ai/conversations`);
      if (!resp.ok) return;
      const list = await resp.json();
      const current = list.find((c) => c.conversation_id === this.conversationId);
      if (current?.title) {
        document.getElementById('ai-conv-title').textContent = current.title;
      }
    } catch (_) {}
  }

  async _openHistory() {
    const drawer = document.getElementById('ai-history-drawer');
    drawer.style.display = '';
    const list = document.getElementById('ai-history-list');
    list.innerHTML = '<li class="ai-history-item">Loading...</li>';
    try {
      const resp = await fetch(`${API_BASE}/api/ai/conversations`);
      const convs = await resp.json();
      list.innerHTML = '';
      if (convs.length === 0) {
        list.innerHTML = '<li class="ai-history-item ai-history-item--empty">No conversations yet.</li>';
        return;
      }
      convs.forEach((conv) => {
        const li = document.createElement('li');
        li.classList.add('ai-history-item');
        if (conv.conversation_id === this.conversationId) li.classList.add('ai-history-item--active');
        li.textContent = conv.title || `Started ${conv.started_at.slice(0, 10)}`;
        li.addEventListener('click', async () => {
          this.conversationId = conv.conversation_id;
          document.getElementById('ai-conv-title').textContent = conv.title || '';
          this._closeHistory();
          await this._loadMessages();
        });
        list.appendChild(li);
      });
    } catch (err) {
      list.innerHTML = `<li class="ai-history-item ai-history-item--error">${escapeHtml(err.message)}</li>`;
    }
  }

  _closeHistory() {
    document.getElementById('ai-history-drawer').style.display = 'none';
  }

  // ---- Settings sub-view (voice replies + Indian voice + speaking speed) ----

  _openSettings() {
    this.showingSettings = true;
    this._renderSettingsBody();
    const v = document.getElementById('ai-settings-view');
    if (v) v.style.display = 'flex';
  }

  _closeSettings() {
    this.showingSettings = false;
    const v = document.getElementById('ai-settings-view');
    if (v) v.style.display = 'none';
  }

  _renderSettingsBody() {
    const body = document.getElementById('ai-settings-body');
    if (!body) return;
    const { voice, rate, autoPlay } = getTTSPreferences();

    body.innerHTML = `
      <div class="ai-set-block">
        <div class="ai-set-label">Voice</div>

        <div class="ai-set-row" id="ai-set-voicereply-row">
          <div>
            <div class="ai-set-row__title">Voice replies</div>
            <div class="ai-set-row__sub">Read Trading Partner's answers aloud automatically</div>
          </div>
          <button type="button" role="switch" aria-checked="${autoPlay ? 'true' : 'false'}"
            class="ai-switch ${autoPlay ? '' : 'ai-switch--off'}" id="ai-set-voicereply"></button>
        </div>

        <div class="ai-set-field">
          <label for="ai-set-voice">Voice</label>
          <select id="ai-set-voice" class="ai-set-select">
            ${VOICE_OPTIONS.map(
              (o) =>
                `<option value="${o.id}" ${o.id === voice ? 'selected' : ''}>${o.label} — ${o.lang}</option>`
            ).join('')}
          </select>
        </div>

        <div class="ai-set-field">
          <div class="ai-set-slider-head">
            <label for="ai-set-rate">Speaking speed</label>
            <span class="ai-set-rate-val" id="ai-set-rate-val">${Number(rate).toFixed(2)}×</span>
          </div>
          <input type="range" id="ai-set-rate" class="ai-set-range" min="0.75" max="1.5" step="0.05" value="${rate}" />
          <div class="ai-set-scale"><span>0.75×</span><span>1.0×</span><span>1.5×</span></div>
          <button type="button" class="ai-set-preview" id="ai-set-preview">▸ Preview voice</button>
        </div>
      </div>

      <div class="ai-set-block">
        <div class="ai-set-label">Model</div>
        <div class="ai-set-row">
          <div>
            <div class="ai-set-row__title">Cloud (Gemini)</div>
            <div class="ai-set-row__sub">Vertex AI · Gemini — the one model Swayam runs</div>
          </div>
          <span class="ai-set-badge">Active</span>
        </div>
      </div>
    `;

    // Voice replies toggle
    const toggle = document.getElementById('ai-set-voicereply');
    if (toggle) {
      toggle.addEventListener('click', () => {
        const next = toggle.classList.contains('ai-switch--off');
        toggle.classList.toggle('ai-switch--off', !next);
        toggle.setAttribute('aria-checked', next ? 'true' : 'false');
        setTTSPreferences({ autoPlay: next });
      });
    }

    // Voice selection
    const sel = document.getElementById('ai-set-voice');
    if (sel) sel.addEventListener('change', (e) => setTTSPreferences({ voice: e.target.value }));

    // Speaking rate
    const rateInput = document.getElementById('ai-set-rate');
    const rateVal = document.getElementById('ai-set-rate-val');
    if (rateInput) {
      rateInput.addEventListener('input', (e) => {
        const r = parseFloat(e.target.value);
        if (rateVal) rateVal.textContent = `${r.toFixed(2)}×`;
        setTTSPreferences({ rate: r });
      });
    }

    // Preview
    const preview = document.getElementById('ai-set-preview');
    if (preview) {
      preview.addEventListener('click', () =>
        playText('This is your Trading Partner. I will read your answers aloud at this speed.', preview)
      );
    }
  }

  /** Append the model tag + Play + Save controls under an assistant message. */
  _addAssistantMeta(msgDiv, text) {
    if (!msgDiv || !text || !text.trim()) return;
    if (msgDiv.querySelector('.ai-msg-meta')) return;

    const meta = document.createElement('div');
    meta.className = 'ai-msg-meta';

    const tag = document.createElement('span');
    tag.className = 'ai-msg-model';
    tag.textContent = 'Cloud · Gemini';

    const actions = document.createElement('div');
    actions.className = 'ai-msg-actions';

    const playBtn = createTTSButton(() => text);
    playBtn.classList.add('ai-msg-action-icon');

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'ai-msg-action';
    saveBtn.innerHTML = '<span aria-hidden="true">⤓</span> Save';
    saveBtn.title = 'Save to memory';
    saveBtn.addEventListener('click', () => this._saveToNotebook(text, saveBtn));

    actions.appendChild(playBtn);
    actions.appendChild(saveBtn);
    meta.appendChild(tag);
    meta.appendChild(actions);
    msgDiv.appendChild(meta);
  }

  async _saveToNotebook(text, btn) {
    try {
      const resp = await fetch(`${API_BASE}/api/ai/notebook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry_text: text, source_conversation_id: this.conversationId }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (btn) {
        btn.innerHTML = '<span aria-hidden="true">✓</span> Saved';
        btn.classList.add('saved');
        btn.disabled = true;
      }
    } catch (err) {
      if (btn) btn.title = `Save failed: ${err.message}`;
      this._showError(`Could not save to memory: ${err.message}`);
    }
  }

  _showError(msg) {
    const el = document.getElementById('ai-error');
    if (el) {
      el.textContent = msg;
      el.style.display = '';
    }
  }

  _clearError() {
    const el = document.getElementById('ai-error');
    if (el) el.style.display = 'none';
  }

  _scrollToBottom() {
    const el = document.getElementById('ai-messages');
    if (el) el.scrollTop = el.scrollHeight;
  }

  _injectStyles() {
    if (document.getElementById('ai-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'ai-panel-styles';
    style.textContent = `
      .ai-panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--dl-card);
        border-left: 2px solid var(--accent-blue);
        font-family: var(--font-sans, system-ui, sans-serif);
        font-size: 13px;
        color: var(--dl-fg);
      }
      .ai-panel__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-bottom: 1px solid var(--dl-line);
        background: var(--dl-rail);
        flex-shrink: 0;
      }
      .ai-panel__header { flex-wrap: nowrap; overflow: hidden; }
      /* Left side shrinks (title/convo-title truncate) so the right-side controls —
         including the ⚙ settings gear — are NEVER pushed off the 370px panel edge.
         (Bug: a past chat's conversation title used to shove the gear off-screen.) */
      .ai-panel__header-left { display: flex; align-items: center; gap: 6px; flex: 1 1 auto; min-width: 0; overflow: hidden; }
      .ai-panel__header-right { display: flex; align-items: center; gap: 4px; flex: 0 0 auto; }
      .ai-panel__icon { font-size: 16px; color: var(--accent-blue); }
      .ai-panel__title { font-weight: 600; font-size: 14px; color: var(--dl-fg); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }
      .ai-panel__conv-title {
        font-size: 11px;
        color: var(--dl-fg-3);
        max-width: 84px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex-shrink: 1;
      }
      .ai-panel__body {
        flex: 1;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        min-height: 0;
        background: var(--dl-card);
      }
      .ai-messages {
        flex: 1;
        overflow-y: auto;
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        min-height: 0;
      }
      .ai-message { display: flex; }
      .ai-message--user { justify-content: flex-end; }
      .ai-message--assistant { justify-content: flex-start; }
      .ai-message__content {
        max-width: 85%;
        padding: 8px 12px;
        border-radius: 10px;
        line-height: 1.5;
        word-break: break-word;
      }
      /* Same treatment as the Home chat, for the same reason: a pale tint on
         his own messages, nothing at all behind the AI's. */
      .ai-message--user .ai-message__content {
        background: var(--accent-sage-tint);
        color: var(--dl-fg);
        border-bottom-right-radius: 3px;
      }
      .ai-message--assistant .ai-message__content {
        max-width: 100%;
        background: none;
        color: var(--dl-fg);
        border: none;
        padding: 6px 2px;
      }
      .ai-message__content code {
        font-family: 'JetBrains Mono', monospace;
        background: var(--dl-card-2);
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 12px;
      }
      .ai-message__content pre {
        background: var(--dl-card-2);
        padding: 8px;
        border-radius: 6px;
        overflow-x: auto;
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
      }
      .ai-message__content ul { padding-left: 18px; margin: 4px 0; }
      .ai-message__content li { margin: 2px 0; }
      .ai-message__content strong { font-weight: 600; }
      .ai-typing {
        display: inline-block;
        animation: blink 1s step-end infinite;
        color: var(--accent-blue);
      }
      @keyframes blink { 50% { opacity: 0; } }
      .ai-starters {
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        border-top: 1px solid var(--dl-line);
      }
      .ai-starters__label {
        font-size: 11px;
        color: var(--dl-fg-3);
        margin: 0 0 4px 0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
      }
      .ai-starter-btn {
        text-align: left;
        background: var(--dl-card-2);
        border: 1px solid var(--dl-line);
        color: var(--dl-fg);
        padding: 8px 12px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 12px;
        line-height: 1.4;
        transition: all 0.15s;
      }
      .ai-starter-btn:hover {
        background: var(--dl-card);
        border-color: var(--accent-blue);
      }
      .ai-panel__input-area {
        display: flex;
        align-items: flex-end;
        gap: 8px;
        padding: 10px 14px;
        border-top: 1px solid var(--dl-line);
        background: var(--dl-card);
        flex-shrink: 0;
      }
      .ai-textarea {
        flex: 1;
        resize: none;
        background: var(--dl-card-2);
        border: 1px solid var(--dl-line);
        color: var(--dl-fg);
        border-radius: 8px;
        padding: 8px 10px;
        font-family: inherit;
        font-size: 13px;
        outline: none;
        line-height: 1.4;
      }
      .ai-textarea:focus { border-color: var(--accent-blue); }
      .ai-panel__footer {
        padding: 6px 14px;
        font-size: 11px;
        color: var(--dl-fg-3);
        border-top: 1px solid var(--dl-line);
        background: var(--dl-rail);
        flex-shrink: 0;
      }
      .ai-error {
        margin: 6px 12px;
        padding: 6px 10px;
        background: var(--accent-coral-tint, rgba(221, 129, 112, 0.17));
        border: 1px solid var(--accent-coral);
        border-radius: 6px;
        color: var(--accent-coral);
        font-size: 12px;
      }
      .ai-error-inline { color: var(--accent-coral); }
      .ai-btn {
        background: var(--dl-card-2);
        border: 1px solid var(--dl-line);
        color: var(--dl-fg);
        padding: 5px 10px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        transition: all 0.15s;
        white-space: nowrap;
      }
      .ai-btn:hover { background: var(--dl-line); }
      .ai-btn--sm { padding: 4px 8px; font-size: 11px; }
      .ai-btn--ghost { background: transparent; border-color: transparent; }
      .ai-btn--primary {
        background: var(--accent-blue);
        border-color: var(--accent-blue);
        color: #101116;
        font-weight: 700;
        min-width: 64px;
        flex-shrink: 0;
        height: 36px;
      }
      .ai-btn--primary:hover { opacity: 0.9; }
      .ai-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      .ai-history-drawer {
        position: absolute;
        right: 0;
        top: 0;
        bottom: 0;
        width: 280px;
        background: var(--dl-card);
        border-left: 1px solid var(--dl-line);
        z-index: 100;
        display: flex;
        flex-direction: column;
      }
      .ai-history-drawer__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px;
        border-bottom: 1px solid var(--dl-line);
        font-weight: 600;
        color: var(--dl-fg);
      }
      .ai-history-list { list-style: none; padding: 8px 0; margin: 0; overflow-y: auto; flex: 1; }
      .ai-history-item {
        padding: 8px 14px;
        cursor: pointer;
        font-size: 13px;
        border-bottom: 1px solid var(--dl-line);
        color: var(--dl-fg-2);
        transition: background 0.1s;
      }
      .ai-history-item:hover { background: var(--dl-card-2); color: var(--dl-fg); }
      .ai-history-item--active { border-left: 3px solid var(--accent-blue); padding-left: 11px; color: var(--dl-fg); font-weight: 600; }
      .ai-history-item--empty, .ai-history-item--error { color: var(--dl-fg-3); cursor: default; }
      .ai-history-item--error { color: var(--accent-coral); }

      /* Header: settings gear + model pill */
      .ai-panel { position: relative; }
      .ai-icon-btn {
        width: 28px; height: 28px; border-radius: 6px; border: none; background: transparent;
        color: var(--dl-fg-3); cursor: pointer; font-size: 15px; display: flex;
        align-items: center; justify-content: center; flex-shrink: 0; transition: all 0.15s;
      }
      .ai-icon-btn:hover { color: var(--dl-fg); background: var(--dl-card-2); }
      .ai-model-pill {
        background: var(--dl-card-2); border: 1px solid var(--dl-line); color: var(--dl-fg-2);
        font-family: inherit; font-size: 10.5px; font-weight: 600; padding: 4px 8px;
        border-radius: 999px; cursor: pointer; white-space: nowrap;
      }
      .ai-model-pill:hover { color: var(--dl-fg); border-color: var(--dl-fg-3); }
      .ai-model-menu {
        position: absolute; top: calc(100% + 6px); right: 0; z-index: 120;
        background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: 10px;
        box-shadow: var(--dl-shadow); padding: 6px; min-width: 210px;
      }
      .ai-model-menu__label {
        font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--dl-fg-3); padding: 4px 8px 6px;
      }
      .ai-model-opt {
        display: flex; align-items: center; justify-content: space-between; width: 100%;
        background: none; border: 0; font-family: inherit; font-size: 12.5px; color: var(--dl-fg);
        padding: 8px 9px; border-radius: 7px; cursor: pointer;
      }
      .ai-model-opt--sel { color: var(--accent-blue); font-weight: 600; }
      .ai-model-opt__check { color: var(--accent-blue); }
      .ai-model-menu__note { font-size: 10.5px; color: var(--dl-fg-3); padding: 6px 9px 3px; line-height: 1.4; }

      /* Assistant message meta row: model tag + Play/Save */
      .ai-message--assistant { flex-direction: column; align-items: flex-start; }
      .ai-msg-meta {
        display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
        margin-top: 3px; padding: 0 2px; width: 100%;
      }
      .ai-msg-model {
        font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--dl-fg-3); opacity: 0.75;
      }
      .ai-msg-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; }
      .ai-msg-action {
        background: none; border: 0; color: var(--dl-fg-3); font-family: inherit;
        font-size: 12px; font-weight: 500; cursor: pointer; display: inline-flex;
        align-items: center; gap: 4px; padding: 2px 4px; border-radius: 5px;
      }
      .ai-msg-action:hover { color: var(--accent-blue); }
      .ai-msg-action.saved { color: var(--accent-sage); cursor: default; }
      .ai-msg-action:disabled { cursor: default; }

      /* Settings sub-view */
      .ai-settings-view {
        position: absolute; inset: 0; z-index: 130; background: var(--dl-card);
        display: flex; flex-direction: column;
      }
      .ai-settings-view__bar {
        display: flex; align-items: center; gap: 10px; padding: 10px 12px;
        border-bottom: 1px solid var(--dl-line); background: var(--dl-rail); flex-shrink: 0;
      }
      .ai-settings-view__title { font-size: 13px; font-weight: 600; color: var(--dl-fg); }
      .ai-settings-view__body {
        flex: 1; overflow-y: auto; padding: 16px 14px; display: flex; flex-direction: column; gap: 18px;
      }
      .ai-set-block { display: flex; flex-direction: column; gap: 10px; }
      .ai-set-label {
        font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--dl-fg-3);
      }
      .ai-set-row {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        background: var(--dl-card-2); border: 1px solid var(--dl-line); border-radius: 9px; padding: 11px 13px;
      }
      .ai-set-row__title { font-size: 13px; color: var(--dl-fg); }
      .ai-set-row__sub { font-size: 11px; color: var(--dl-fg-3); margin-top: 2px; line-height: 1.4; }
      .ai-set-badge {
        font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
        color: var(--accent-sage); background: var(--accent-sage-tint); padding: 3px 9px; border-radius: 999px;
      }
      .ai-switch {
        width: 38px; height: 22px; border-radius: 999px; background: var(--accent-blue);
        position: relative; flex-shrink: 0; cursor: pointer; border: none; padding: 0; transition: background 0.15s;
      }
      .ai-switch::after {
        content: ""; position: absolute; top: 2px; left: 18px; width: 18px; height: 18px;
        border-radius: 50%; background: #fff; transition: left 0.15s;
      }
      .ai-switch--off { background: var(--dl-track); }
      .ai-switch--off::after { left: 2px; }
      .ai-set-field { display: flex; flex-direction: column; gap: 6px; }
      .ai-set-field label {
        font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--dl-fg-3);
      }
      .ai-set-select {
        width: 100%; background: var(--dl-card-2); border: 1px solid var(--dl-line); border-radius: 8px;
        padding: 10px 11px; color: var(--dl-fg); font-family: inherit; font-size: 13px; cursor: pointer;
      }
      .ai-set-slider-head { display: flex; align-items: center; justify-content: space-between; }
      .ai-set-rate-val { font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 700; color: var(--dl-fg); }
      .ai-set-range { width: 100%; accent-color: var(--accent-blue); }
      .ai-set-scale {
        display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace;
        font-size: 10px; color: var(--dl-fg-3); margin-top: 2px;
      }
      .ai-set-preview {
        align-self: flex-start; margin-top: 8px; background: var(--dl-card-2); border: 1px solid var(--dl-line);
        color: var(--dl-fg-2); font-family: inherit; font-size: 12px; padding: 6px 12px; border-radius: 7px; cursor: pointer;
      }
      .ai-set-preview:hover { color: var(--accent-blue); border-color: var(--accent-blue); }
    `;
    document.head.appendChild(style);
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

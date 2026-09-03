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

const API_BASE = 'http://localhost:8000';

const STARTER_PROMPTS = [
  'Read the current setup and tell me what you see',
  'What historical trade does this most resemble?',
  'What could go wrong with this spread this week?',
  "What's my readiness verdict today and does this trade fit it?",
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
            <span class="ai-panel__icon">🤝</span>
            <span class="ai-panel__title">Trading Partner</span>
            <span class="ai-panel__conv-title" id="ai-conv-title"></span>
          </div>
          <div class="ai-panel__header-right">
            <button class="ai-btn ai-btn--sm" id="ai-btn-new" title="New conversation">+ New</button>
            <button class="ai-btn ai-btn--sm" id="ai-btn-history" title="Conversation history">History</button>
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

        <div class="ai-panel__input-area" id="ai-input-area">
          <textarea
            class="ai-textarea"
            id="ai-textarea"
            rows="2"
            placeholder="Ask anything about this trade, regime, or your method..."
          ></textarea>
          <button class="ai-btn ai-btn--primary" id="ai-btn-send">Send</button>
        </div>

        <div class="ai-panel__footer" id="ai-footer">
          <span id="ai-cost-display">Loading usage...</span>
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

    // Send button
    document.getElementById('ai-btn-send').addEventListener('click', () => this._sendMessage());

    // Enter to send, Shift+Enter for newline
    document.getElementById('ai-textarea').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this._sendMessage();
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
      messages.forEach((msg) => this._appendMessage(msg.role, msg.content, false));
      if (messages.length > 0) {
        document.getElementById('ai-starters').style.display = 'none';
      }
      this._scrollToBottom();
    } catch (err) {
      this._showError(`Could not load messages: ${err.message}`);
    }
  }

  _appendMessage(role, content, isStreaming = false) {
    const container = document.getElementById('ai-messages');
    const div = document.createElement('div');
    div.classList.add('ai-message', role === 'user' ? 'ai-message--user' : 'ai-message--assistant');
    if (isStreaming) div.setAttribute('id', 'ai-streaming-msg');

    const inner = document.createElement('div');
    inner.classList.add('ai-message__content');
    inner.innerHTML = role === 'assistant' ? renderMarkdown(content) : escapeHtml(content);
    div.appendChild(inner);
    container.appendChild(div);
    this._scrollToBottom();
    return inner; // Return inner for streaming delta appends
  }

  async _sendMessage() {
    const textarea = document.getElementById('ai-textarea');
    const content = textarea.value.trim();
    if (!content || !this.conversationId) return;

    // Abort any in-progress stream
    if (this.currentEventSource) {
      this.currentEventSource.close();
      this.currentEventSource = null;
    }

    textarea.value = '';
    textarea.disabled = true;
    document.getElementById('ai-btn-send').disabled = true;
    this._clearError();

    // Hide starters
    document.getElementById('ai-starters').style.display = 'none';

    // Show user message
    this._appendMessage('user', content, false);

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
      const resp = await fetch(
        `${API_BASE}/api/ai/conversations/${this.conversationId}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
        }
      );

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
      if (!resp.ok) return;
      const data = await resp.json();
      const el = document.getElementById('ai-cost-display');
      if (el) {
        el.textContent =
          data.request_count > 0
            ? `Today's AI spend: ₹${data.estimated_cost_inr.toFixed(2)} (${data.request_count} requests)`
            : 'Today's AI spend: ₹0.00 (0 requests)';
      }
    } catch (_) {
      // Non-fatal
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
        background: var(--bg-secondary, #1a1a2e);
        border-left: 1px solid var(--border-color, #2a2a4a);
        font-family: var(--font-body, system-ui, sans-serif);
        font-size: 13px;
        color: var(--text-primary, #e8e8f0);
      }
      .ai-panel__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-bottom: 1px solid var(--border-color, #2a2a4a);
        background: var(--bg-tertiary, #16213e);
        flex-shrink: 0;
      }
      .ai-panel__header-left { display: flex; align-items: center; gap: 6px; }
      .ai-panel__header-right { display: flex; align-items: center; gap: 4px; }
      .ai-panel__icon { font-size: 16px; }
      .ai-panel__title { font-weight: 600; font-size: 14px; }
      .ai-panel__conv-title {
        font-size: 11px;
        color: var(--text-secondary, #8888aa);
        max-width: 120px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .ai-panel__body {
        flex: 1;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        min-height: 0;
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
      .ai-message--user .ai-message__content {
        background: var(--accent, #4f46e5);
        color: #fff;
        border-bottom-right-radius: 3px;
      }
      .ai-message--assistant .ai-message__content {
        background: var(--bg-tertiary, #16213e);
        color: var(--text-primary, #e8e8f0);
        border-bottom-left-radius: 3px;
      }
      .ai-message__content code {
        font-family: 'JetBrains Mono', monospace;
        background: rgba(0,0,0,0.3);
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 12px;
      }
      .ai-message__content pre {
        background: rgba(0,0,0,0.3);
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
        color: var(--accent, #4f46e5);
      }
      @keyframes blink { 50% { opacity: 0; } }
      .ai-starters {
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        border-top: 1px solid var(--border-color, #2a2a4a);
      }
      .ai-starters__label {
        font-size: 11px;
        color: var(--text-secondary, #8888aa);
        margin: 0 0 4px 0;
      }
      .ai-starter-btn {
        text-align: left;
        background: var(--bg-tertiary, #16213e);
        border: 1px solid var(--border-color, #2a2a4a);
        color: var(--text-primary, #e8e8f0);
        padding: 6px 10px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        transition: background 0.15s;
      }
      .ai-starter-btn:hover { background: var(--bg-hover, #1e2a50); }
      .ai-panel__input-area {
        display: flex;
        gap: 6px;
        padding: 8px 12px;
        border-top: 1px solid var(--border-color, #2a2a4a);
        flex-shrink: 0;
      }
      .ai-textarea {
        flex: 1;
        resize: none;
        background: var(--bg-input, #0f1224);
        border: 1px solid var(--border-color, #2a2a4a);
        color: var(--text-primary, #e8e8f0);
        border-radius: 6px;
        padding: 6px 8px;
        font-family: inherit;
        font-size: 13px;
        outline: none;
      }
      .ai-textarea:focus { border-color: var(--accent, #4f46e5); }
      .ai-panel__footer {
        padding: 4px 12px;
        font-size: 11px;
        color: var(--text-secondary, #8888aa);
        border-top: 1px solid var(--border-color, #2a2a4a);
        flex-shrink: 0;
      }
      .ai-error {
        margin: 6px 12px;
        padding: 6px 10px;
        background: rgba(220, 50, 47, 0.15);
        border: 1px solid rgba(220, 50, 47, 0.4);
        border-radius: 6px;
        color: #ff6b6b;
        font-size: 12px;
      }
      .ai-error-inline { color: #ff6b6b; }
      .ai-btn {
        background: var(--bg-tertiary, #16213e);
        border: 1px solid var(--border-color, #2a2a4a);
        color: var(--text-primary, #e8e8f0);
        padding: 5px 10px;
        border-radius: 5px;
        cursor: pointer;
        font-size: 12px;
        transition: background 0.15s;
        white-space: nowrap;
      }
      .ai-btn:hover { background: var(--bg-hover, #1e2a50); }
      .ai-btn--sm { padding: 3px 7px; font-size: 11px; }
      .ai-btn--ghost { background: transparent; border-color: transparent; }
      .ai-btn--primary {
        background: var(--accent, #4f46e5);
        border-color: var(--accent, #4f46e5);
        color: #fff;
        font-weight: 600;
      }
      .ai-btn--primary:hover { background: #3730a3; }
      .ai-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      .ai-history-drawer {
        position: absolute;
        right: 0;
        top: 0;
        bottom: 0;
        width: 260px;
        background: var(--bg-secondary, #1a1a2e);
        border-left: 1px solid var(--border-color, #2a2a4a);
        z-index: 100;
        display: flex;
        flex-direction: column;
      }
      .ai-history-drawer__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-bottom: 1px solid var(--border-color, #2a2a4a);
        font-weight: 600;
      }
      .ai-history-list { list-style: none; padding: 8px 0; margin: 0; overflow-y: auto; flex: 1; }
      .ai-history-item {
        padding: 8px 14px;
        cursor: pointer;
        font-size: 13px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        transition: background 0.1s;
      }
      .ai-history-item:hover { background: var(--bg-tertiary, #16213e); }
      .ai-history-item--active { border-left: 3px solid var(--accent, #4f46e5); padding-left: 11px; }
      .ai-history-item--empty, .ai-history-item--error { color: var(--text-secondary, #8888aa); cursor: default; }
      .ai-history-item--error { color: #ff6b6b; }
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

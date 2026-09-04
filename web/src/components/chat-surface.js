/**
 * Interactive Conversational AI Trading Partner Surface for Swayam Capital (BUILD-9-FIXES-B).
 *
 * Refactors "What Matters Today" into an inline conversation surface with:
 * - AI Pre-market Brief at top with speaker/note/pin toolbar
 * - Scrollable dialogue history (lilac user bubbles right, dark AI bubbles left)
 * - Per-response actions: TTS speech playback (Indian English), notebook memory, rule pinning
 * - Real-time SSE streaming for AI replies
 * - Session continuity via ?session= query parameter
 * - "Go to Strategy Builder →" continuous workflow bridge
 */

import { createTTSButton } from './tts-player.js';

function parseMarkdown(text) {
  if (!text) return '';
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  const lines = escaped.split('\n');
  const outputParts = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const isBullet = /^[-*+]\s+/.test(line);

    if (isBullet) {
      if (!inList) {
        outputParts.push('<ul style="margin: 6px 0 6px 1.2em; padding: 0; list-style: disc;">');
        inList = true;
      }
      const content = line.replace(/^[-*+]\s+/, '');
      outputParts.push(`<li style="margin-bottom: 3px;">${inlineMarkdown(content)}</li>`);
    } else {
      if (inList) {
        outputParts.push('</ul>');
        inList = false;
      }
      const trimmed = line.trim();
      if (trimmed === '') {
        if (outputParts.length > 0 && !outputParts[outputParts.length - 1].endsWith('<br>')) {
          outputParts.push('<br>');
        }
      } else {
        outputParts.push(inlineMarkdown(trimmed));
        if (i < lines.length - 1 && lines[i + 1].trim() !== '' && !/^[-*+]/.test(lines[i + 1])) {
          outputParts.push(' ');
        }
      }
    }
  }

  if (inList) outputParts.push('</ul>');
  return outputParts.join('');
}

function inlineMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="font-family: var(--font-mono); font-size: 0.85em; background: var(--dl-card-2); padding: 1px 5px; border-radius: 4px; color: var(--accent-lilac);">$1</code>');
}

export class ChatSurfaceComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onOpenSettings, onNavigateStrategy }
    this.sessionId = this._getInitialSessionId();
    this.messages = [];
    this.isStreaming = false;
    this.briefText = '';
  }

  _getInitialSessionId() {
    try {
      const params = new URLSearchParams(window.location.search);
      const s = params.get('session');
      if (s) return s;
    } catch (_) {}
    return null;
  }

  _setSessionParam(sessionId) {
    this.sessionId = sessionId;
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('session', sessionId);
      window.history.replaceState({}, '', url.toString());
    } catch (_) {}
  }

  async init(briefData = null, errorMessage = null) {
    this.briefText = briefData?.brief_text || "India VIX at 12.85 confirms low-volatility regime. Premium-selling favorable, but reward is compressed — spreads over singles.\n\n**Skip trades if:**\n- Event risk within 48 hours — RBI meet Monday\n- Intraday VIX rises above 15\n\n**Prefer setups where:**\n- Realistic risk (2σ NIFTY move ≈ ₹165) stays under 1% cap\n- Bear Put Spread around 24,800 has clean structure given yesterday's higher-high VWAP bounce";

    this.render(errorMessage);
    await this._ensureSession();
  }

  render(briefData = null, errorMessage = null) {
    if (typeof briefData === 'string' && errorMessage === null && briefData.toLowerCase().includes('fail')) {
      errorMessage = briefData;
      briefData = null;
    }

    if (briefData) {
      if (typeof briefData === 'object' && briefData.brief_text) {
        this.briefText = briefData.brief_text;
      } else if (typeof briefData === 'string') {
        this.briefText = briefData;
      }
    }

    if (errorMessage) {
      this.container.innerHTML = `
        <div class="ai-trading-partner-workspace" style="width: 100%; box-sizing: border-box; border-left: 2px solid var(--accent-coral); background: var(--dl-card); border-radius: 12px; display: flex; flex-direction: column; gap: 10px; padding: 20px 24px;">
          <span class="eyebrow" style="color: var(--accent-coral); font-weight: 700;">WHAT MATTERS TODAY · AI UNAVAILABLE</span>
          <p style="font-size: 0.92rem; color: var(--dl-fg-2); margin: 0; line-height: 1.5;">
            AI Trading Partner briefing could not be generated: <strong style="color: var(--accent-coral);">${errorMessage}</strong>
          </p>
        </div>
      `;
      return;
    }

    const shortSession = this.sessionId ? `swayam-${this.sessionId.slice(0, 6)}` : 'initializing...';

    this.container.innerHTML = `
      <div class="ai-trading-partner-workspace" style="width: 100%; box-sizing: border-box; border-left: 2px solid var(--accent-lilac); background: var(--dl-card); border-radius: 12px; display: flex; flex-direction: column; gap: 16px; padding: 22px 28px; position: relative;">
        
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 2px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color: var(--accent-lilac);">
              <path d="M8 0L9.8 6.2L16 8L9.8 9.8L8 16L6.2 9.8L0 8L6.2 6.2L8 0Z" fill="currentColor"/>
            </svg>
            <span class="eyebrow" style="color: var(--accent-lilac); font-weight: 700; font-size: 0.84rem; letter-spacing: 0.05em;">AI TRADING PARTNER · WHAT MATTERS TODAY</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--dl-fg-3);">DAILY PRE-MARKET</span>
            <button id="btn-chat-settings" type="button" title="AI Voice & Memory Settings" style="background: var(--dl-card-2); border: 1px solid var(--dl-line); color: var(--dl-fg); border-radius: 7px; padding: 5px 10px; cursor: pointer; display: flex; align-items: center; gap: 5px; font-size: 0.78rem; font-weight: 500;">
              ⚙️ Settings
            </button>
          </div>
        </div>

        <!-- Pre-market Brief Block with Action Toolbar -->
        <div class="ai-brief-block" style="background: var(--dl-card-2); border: 1px solid var(--dl-line); border-radius: 10px; padding: 16px 20px; position: relative;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
            <div id="ai-brief-text-content" style="font-family: var(--font-sans); font-size: 0.94rem; color: var(--dl-fg); line-height: 1.65; flex: 1;">
              ${parseMarkdown(this.briefText)}
            </div>
            <div class="brief-actions" style="display: flex; gap: 6px; flex-shrink: 0; align-items: center; background: var(--dl-card); padding: 4px 8px; border-radius: 8px; border: 1px solid var(--dl-line);">
              <span id="brief-tts-slot"></span>
              <button id="btn-brief-notebook" type="button" title="Save brief to notebook memory" style="background: transparent; border: none; cursor: pointer; color: var(--dl-fg-3); padding: 4px 6px; font-size: 0.85rem;">
                📓
              </button>
              <button id="btn-brief-pin" type="button" title="Pin brief directives" style="background: transparent; border: none; cursor: pointer; color: var(--dl-fg-3); padding: 4px 6px; font-size: 0.85rem;">
                ⭐
              </button>
            </div>
          </div>
        </div>

        <!-- Full-Width Divider -->
        <div style="height: 1px; background: var(--dl-line); width: 100%; margin: 2px 0;"></div>

        <!-- Conversation Message History Container (Spacious Full-Width) -->
        <div id="chat-messages-container" style="min-height: 300px; max-height: 520px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; padding: 4px 2px;">
          <!-- Empty State when no dialogue yet -->
          <div id="chat-empty-state" style="padding: 24px; text-align: center; color: var(--dl-fg-3); font-size: 0.88rem; border: 1px dashed var(--dl-line); border-radius: 10px; background: rgba(0,0,0,0.02);">
            Start the conversation below with a question, observation, or challenge to the brief above.
          </div>
        </div>

        <!-- Full-Width Composer Section -->
        <div class="chat-composer" style="display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--dl-line); padding-top: 14px;">
          <div style="display: flex; justify-content: flex-end; align-items: center; gap: 12px;">
            <span id="chat-char-counter" style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--dl-fg-3); display: none;">0 chars</span>
            <button id="btn-new-convo" type="button" style="background: transparent; border: none; font-size: 0.78rem; color: var(--dl-fg-3); cursor: pointer; text-decoration: underline;">
              + New Conversation
            </button>
          </div>
          <div style="display: flex; gap: 12px; align-items: flex-end;">
            <textarea
              id="chat-textarea"
              rows="3"
              placeholder="Type your thoughts, question, or challenge the brief above..."
              style="flex: 1; min-height: 76px; max-height: 200px; background: var(--dl-card-2); color: var(--dl-fg); border: 1px solid var(--dl-line); border-radius: 10px; padding: 12px 16px; font-family: var(--font-sans); font-size: 0.92rem; resize: vertical; outline: none; line-height: 1.55;"
            ></textarea>
            <button
              id="btn-chat-send"
              type="button"
              style="height: 48px; padding: 0 26px; background: var(--accent-lilac); color: #101116; border: none; border-radius: 10px; font-weight: 700; font-size: 0.88rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: opacity var(--dur-fast, 120ms) ease;"
            >
              Send
            </button>
          </div>
        </div>

        <!-- Footer Bar -->
        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--dl-line-2, rgba(255,255,255,0.05)); padding-top: 12px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span id="chat-session-badge" style="font-family: var(--font-mono); font-size: 0.74rem; color: var(--dl-fg-3);">
              Session: ${shortSession}
            </span>
          </div>
          <button
            id="btn-goto-strategy"
            type="button"
            style="background: var(--accent-lilac-tint, rgba(172, 159, 210, 0.14)); color: var(--accent-lilac); border: 1px solid var(--accent-lilac); height: 34px; padding: 0 18px; border-radius: 8px; font-size: 0.82rem; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all var(--dur-fast, 120ms) ease;"
          >
            Go to Strategy Builder →
          </button>
        </div>

        <!-- Temporary Floating Toast Notification -->
        <div id="chat-toast" style="display: none; position: absolute; bottom: 70px; left: 50%; transform: translateX(-50%); background: var(--dl-card); color: var(--accent-lilac); border: 1px solid var(--accent-lilac); padding: 7px 16px; border-radius: 8px; font-size: 0.82rem; font-weight: 600; box-shadow: var(--dl-shadow); z-index: 10;">
          Saved to memory
        </div>

      </div>
    `;

    this._attachEventHandlers();
    this._mountBriefTTS();
  }

  _mountBriefTTS() {
    const slot = this.container.querySelector('#brief-tts-slot');
    if (slot) {
      slot.innerHTML = '';
      const ttsBtn = createTTSButton(() => this.briefText);
      slot.appendChild(ttsBtn);
    }
  }

  _attachEventHandlers() {
    // Brief notebook action
    const btnBriefNote = this.container.querySelector('#btn-brief-notebook');
    if (btnBriefNote) {
      btnBriefNote.addEventListener('click', () => {
        this.saveToNotebook(this.briefText);
      });
    }

    // Brief pin action
    const btnBriefPin = this.container.querySelector('#btn-brief-pin');
    if (btnBriefPin) {
      btnBriefPin.addEventListener('click', () => {
        this.pinRule('Daily Pre-market Directives: ' + this.briefText.slice(0, 150));
        btnBriefPin.style.color = 'var(--accent-lilac)';
      });
    }

    // Settings drawer open
    const btnSettings = this.container.querySelector('#btn-chat-settings');
    if (btnSettings) {
      btnSettings.addEventListener('click', () => {
        if (this.options.onOpenSettings) this.options.onOpenSettings();
      });
    }

    // Send button & textarea
    const sendBtn = this.container.querySelector('#btn-chat-send');
    const textarea = this.container.querySelector('#chat-textarea');
    const charCounter = this.container.querySelector('#chat-char-counter');

    if (textarea) {
      textarea.addEventListener('input', () => {
        const count = textarea.value.length;
        if (charCounter) {
          charCounter.textContent = `${count} chars`;
          charCounter.style.display = count > 300 ? 'inline' : 'none';
        }
      });

      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }

    if (sendBtn) {
      sendBtn.addEventListener('click', () => this.sendMessage());
    }

    // New conversation
    const btnNew = this.container.querySelector('#btn-new-convo');
    if (btnNew) {
      btnNew.addEventListener('click', async () => {
        if (confirm('Start a fresh conversation session? Your previous discussion will be preserved in history.')) {
          await this.createNewSession();
        }
      });
    }

    // Go to strategy builder
    const btnStrategy = this.container.querySelector('#btn-goto-strategy');
    if (btnStrategy) {
      btnStrategy.addEventListener('click', () => {
        const dest = `/strategy?session=${encodeURIComponent(this.sessionId || '')}`;
        if (this.options.onNavigateStrategy) {
          this.options.onNavigateStrategy(dest);
        } else {
          window.location.href = dest;
        }
      });
    }
  }

  async _ensureSession() {
    if (!this.sessionId) {
      await this.createNewSession();
    } else {
      await this.loadSessionMessages();
    }
  }

  async createNewSession() {
    try {
      const resp = await fetch('/api/ai/session/new', { method: 'POST' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      this._setSessionParam(data.session_id);

      const badge = this.container.querySelector('#chat-session-badge');
      if (badge) badge.textContent = `Session: swayam-${data.session_id.slice(0, 6)}`;

      this.messages = [];
      const messagesContainer = this.container.querySelector('#chat-messages-container');
      if (messagesContainer) {
        messagesContainer.innerHTML = `
          <div id="chat-empty-state" style="padding: 18px; text-align: center; color: var(--dl-fg-3); font-size: 0.85rem; border: 1px dashed var(--dl-line); border-radius: 10px; background: rgba(0,0,0,0.02);">
            Start the conversation below with a question, observation, or challenge to the brief above.
          </div>
        `;
      }
    } catch (err) {
      console.error('Failed to create new session:', err);
    }
  }

  async loadSessionMessages() {
    if (!this.sessionId) return;
    try {
      const resp = await fetch(`/api/ai/session/${this.sessionId}/messages`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const msgs = await resp.json();
      this.messages = msgs;

      const container = this.container.querySelector('#chat-messages-container');
      if (!container) return;

      container.innerHTML = '';
      if (msgs.length === 0) {
        container.innerHTML = `
          <div id="chat-empty-state" style="padding: 18px; text-align: center; color: var(--dl-fg-3); font-size: 0.85rem; border: 1px dashed var(--dl-line); border-radius: 10px; background: rgba(0,0,0,0.02);">
            Start the conversation below with a question, observation, or challenge to the brief above.
          </div>
        `;
      } else {
        msgs.forEach((m) => this.appendMessageDOM(m.role, m.content, m.id));
      }
    } catch (err) {
      console.error('Could not load session messages:', err);
    }
  }

  appendMessageDOM(role, content, messageId = null, isStreaming = false) {
    const container = this.container.querySelector('#chat-messages-container');
    if (!container) return null;

    const empty = container.querySelector('#chat-empty-state');
    if (empty) empty.remove();

    const msgRow = document.createElement('div');
    msgRow.style.cssText = `
      display: flex;
      flex-direction: column;
      align-items: ${role === 'user' ? 'flex-end' : 'flex-start'};
      margin-bottom: 6px;
    `;

    if (role === 'user') {
      const bubble = document.createElement('div');
      bubble.style.cssText = `
        max-width: 70%;
        background: var(--accent-lilac);
        color: #101116;
        padding: 12px 18px;
        border-radius: 14px 14px 3px 14px;
        font-size: 0.92rem;
        line-height: 1.55;
        font-weight: 500;
        word-break: break-word;
      `;
      bubble.textContent = content;
      msgRow.appendChild(bubble);
    } else {
      // AI Assistant response card
      const bubble = document.createElement('div');
      bubble.style.cssText = `
        max-width: 75%;
        background: var(--dl-card-2);
        color: var(--dl-fg);
        padding: 16px 20px;
        border-radius: 14px 14px 14px 3px;
        border: 1px solid var(--dl-line);
        font-size: 0.93rem;
        line-height: 1.65;
        word-break: break-word;
      `;
      bubble.innerHTML = parseMarkdown(content);
      if (isStreaming) bubble.setAttribute('id', 'chat-active-streaming-bubble');
      msgRow.appendChild(bubble);

      // Under AI bubble: small action toolbar (speaker | notebook | star)
      const toolbar = document.createElement('div');
      toolbar.style.cssText = `
        display: flex;
        gap: 6px;
        align-items: center;
        margin-top: 4px;
        margin-left: 4px;
      `;

      const ttsBtn = createTTSButton(() => bubble.textContent);
      toolbar.appendChild(ttsBtn);

      const noteBtn = document.createElement('button');
      noteBtn.type = 'button';
      noteBtn.title = 'Save to memory notebook';
      noteBtn.innerHTML = '📓';
      noteBtn.style.cssText = 'background: transparent; border: none; cursor: pointer; padding: 2px 4px; font-size: 0.8rem;';
      noteBtn.addEventListener('click', () => {
        this.saveToNotebook(bubble.textContent, messageId);
      });
      toolbar.appendChild(noteBtn);

      const pinBtn = document.createElement('button');
      pinBtn.type = 'button';
      pinBtn.title = 'Pin rule to context';
      pinBtn.innerHTML = '⭐';
      pinBtn.style.cssText = 'background: transparent; border: none; cursor: pointer; padding: 2px 4px; font-size: 0.8rem; color: var(--dl-fg-3);';
      pinBtn.addEventListener('click', () => {
        this.pinRule(bubble.textContent.slice(0, 180), messageId);
        pinBtn.style.color = 'var(--accent-lilac)';
      });
      toolbar.appendChild(pinBtn);

      msgRow.appendChild(toolbar);
    }

    container.appendChild(msgRow);
    container.scrollTop = container.scrollHeight;
    return msgRow;
  }

  async sendMessage() {
    if (this.isStreaming) return;
    const textarea = this.container.querySelector('#chat-textarea');
    if (!textarea) return;
    const text = textarea.value.trim();
    if (!text) return;

    textarea.value = '';
    const charCounter = this.container.querySelector('#chat-char-counter');
    if (charCounter) charCounter.style.display = 'none';

    // 1. Append user message locally
    this.appendMessageDOM('user', text);
    this.messages.push({ role: 'user', content: text });

    // 2. Prepare streaming bubble for assistant
    this.isStreaming = true;
    const sendBtn = this.container.querySelector('#btn-chat-send');
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.style.opacity = '0.6';
    }

    const row = this.appendMessageDOM('assistant', 'Thinking...', null, true);
    const bubble = row ? row.querySelector('#chat-active-streaming-bubble') : null;

    let fullAssistantText = '';

    try {
      const response = await fetch(`/api/ai/conversations/${this.sessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep last incomplete line

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.replace(/^data:\s*/, '');
            if (dataStr === '[DONE]') {
              break;
            }
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.delta) {
                fullAssistantText += parsed.delta;
                if (bubble) {
                  bubble.innerHTML = parseMarkdown(fullAssistantText);
                }
              }
            } catch (_) {}
          }
        }
      }

      if (bubble) {
        bubble.removeAttribute('id');
        bubble.innerHTML = parseMarkdown(fullAssistantText || 'No response generated.');
      }
      this.messages.push({ role: 'assistant', content: fullAssistantText });
    } catch (err) {
      console.error('Chat streaming error:', err);
      if (bubble) {
        bubble.removeAttribute('id');
        bubble.innerHTML = `<span style="color: var(--accent-coral);">Error: ${err.message}</span>`;
      }
    } finally {
      this.isStreaming = false;
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.style.opacity = '1';
      }
    }
  }

  showToast(text) {
    const toast = this.container.querySelector('#chat-toast');
    if (!toast) return;
    toast.textContent = text;
    toast.style.display = 'block';
    setTimeout(() => {
      toast.style.display = 'none';
    }, 2200);
  }

  async saveToNotebook(entryText, sourceMessageId = null) {
    try {
      const resp = await fetch('/api/ai/notebook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entry_text: entryText,
          source_message_id: sourceMessageId,
          source_conversation_id: this.sessionId,
        }),
      });
      if (resp.ok) {
        this.showToast('✓ Saved to memory');
      } else {
        throw new Error(`HTTP ${resp.status}`);
      }
    } catch (err) {
      console.error('Failed to save notebook entry:', err);
      alert(`Could not save to notebook: ${err.message}`);
    }
  }

  async pinRule(ruleText, sourceMessageId = null) {
    try {
      const resp = await fetch('/api/ai/pinned', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rule_text: ruleText,
          source_message_id: sourceMessageId,
        }),
      });
      if (resp.ok) {
        this.showToast('⭐ Rule pinned to context');
      } else {
        throw new Error(`HTTP ${resp.status}`);
      }
    } catch (err) {
      console.error('Failed to pin rule:', err);
      alert(`Could not pin rule: ${err.message}`);
    }
  }
}

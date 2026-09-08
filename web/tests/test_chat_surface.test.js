import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { ChatSurfaceComponent } from '../src/components/chat-surface.js';

describe('ChatSurfaceComponent (Full-Width AI Workspace)', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders full-width conversational workspace container and header', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    const workspace = container.querySelector('.ai-trading-partner-workspace');
    expect(workspace).not.toBeNull();
    expect(workspace.style.width).toBe('100%');
    expect(container.textContent).toContain('AI TRADING PARTNER');
    // No fake pre-market brief framing anymore.
    expect(container.textContent).not.toContain('WHAT MATTERS TODAY');
    expect(container.textContent).not.toContain('DAILY PRE-MARKET');
  });

  it('has NO hardcoded brief block and NO suggested questions (no fake data)', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    // The old fake pre-market brief block and its action buttons are gone.
    expect(container.querySelector('.ai-brief-block')).toBeNull();
    expect(container.querySelector('#btn-brief-notebook')).toBeNull();
    expect(container.querySelector('#btn-brief-pin')).toBeNull();
    expect(container.querySelector('#brief-tts-slot')).toBeNull();
    // Suggested-question prompt cards are removed.
    expect(container.querySelector('.chat-quick-prompt-card')).toBeNull();
    expect(container.textContent).not.toContain('Suggested Questions');
  });

  it('gives his own message a pale sage tint and body text, never white on green', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    const row = chat.appendMessageDOM('user', 'Can we take a bear put spread?');
    expect(row).not.toBeNull();

    const bubble = row.children[0];
    expect(bubble.textContent).toBe('Can we take a bear put spread?');
    expect(bubble.style.maxWidth).toBe('70%');
    // The tint is read from the theme, not hardcoded, and it is a tint rather
    // than the saturated fill it used to be.
    expect(bubble.style.background).toContain('--accent-sage-tint');
    expect(bubble.style.background).not.toContain('var(--accent-sage)');
    expect(bubble.style.color).toContain('--dl-fg');
  });

  it('gives the AI no background at all, full width, with its action toolbar', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    const row = chat.appendMessageDOM('assistant', 'Two things to consider:\n- 12.85 VIX compresses reward');
    expect(row).not.toBeNull();

    const bubble = row.children[0];
    expect(bubble.innerHTML).toContain('12.85 VIX compresses reward');
    expect(bubble.style.maxWidth).toBe('100%');
    expect(bubble.style.background).toBe('none');
    // No card behind the AI: no border, no tint, no rounded corners.
    expect(bubble.style.cssText).not.toContain('border');
    expect(bubble.style.cssText).not.toContain('--dl-card-2');

    const toolbar = row.children[1];
    expect(toolbar).not.toBeNull();
    expect(toolbar.children.length).toBeGreaterThanOrEqual(2);
  });

  it('navigates to strategy builder when footer action clicked', () => {
    const onNavigateStrategy = vi.fn();
    const chat = new ChatSurfaceComponent(container, { onNavigateStrategy });
    chat.sessionId = 'test-session-1234';
    chat.render();

    const btn = container.querySelector('#btn-goto-strategy');
    expect(btn).not.toBeNull();
    btn.click();

    expect(onNavigateStrategy).toHaveBeenCalledWith('/strategy?session=test-session-1234');
  });

  it('renders graceful error message on briefing generation failure', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render(null, 'Gemini quota exceeded');

    expect(container.textContent).toContain('AI UNAVAILABLE');
    expect(container.textContent).toContain('Gemini quota exceeded');
  });

  it('stages an image and shows thumbnail preview with remove button (BUILD-11.7)', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    // Mock file
    const fakeFile = new File(['fake-png-data'], 'chart.png', { type: 'image/png' });
    chat.setPendingImage(fakeFile);

    const previewContainer = container.querySelector('#chat-attachment-preview-container');
    const thumb = container.querySelector('#chat-attachment-thumb');
    const info = container.querySelector('#chat-attachment-info');
    const removeBtn = container.querySelector('#chat-attachment-remove');

    expect(previewContainer.style.display).toBe('flex');
    expect(info.textContent).toContain('chart.png');
    expect(chat.pendingImage).toBe(fakeFile);

    // Click remove button
    removeBtn.click();
    expect(previewContainer.style.display).toBe('none');
    expect(chat.pendingImage).toBeNull();
  });

  it('renders image attachment in user message bubble with expand click (BUILD-11.7)', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    const row = chat.appendMessageDOM('user', 'Check this chart', 'msg-1', false, 'https://example.com/chart.png');
    expect(row).not.toBeNull();

    const bubble = row.children[0];
    const img = bubble.querySelector('img');
    expect(img).not.toBeNull();
    expect(img.getAttribute('src') || img.src).toBe('https://example.com/chart.png');
    expect(bubble.textContent).toContain('Check this chart');
  });
});

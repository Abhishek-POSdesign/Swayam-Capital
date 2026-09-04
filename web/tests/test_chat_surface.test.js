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
    expect(container.textContent).toContain('AI TRADING PARTNER · WHAT MATTERS TODAY');
    expect(container.textContent).toContain('DAILY PRE-MARKET');
  });

  it('renders brief block with markdown formatting and action buttons', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.briefText = '**Key Level:** NIFTY 24,800.\n- Watch put writing';
    chat.render();

    const briefBlock = container.querySelector('.ai-brief-block');
    expect(briefBlock).not.toBeNull();
    expect(briefBlock.innerHTML).toContain('<strong>Key Level:</strong>');
    expect(briefBlock.innerHTML).toContain('Watch put writing');

    expect(container.querySelector('#btn-brief-notebook')).not.toBeNull();
    expect(container.querySelector('#btn-brief-pin')).not.toBeNull();
    expect(container.querySelector('#brief-tts-slot')).not.toBeNull();
  });

  it('appends user message with 70% max-width and lilac theme', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    const row = chat.appendMessageDOM('user', 'Can we take a bear put spread?');
    expect(row).not.toBeNull();

    const bubble = row.children[0];
    expect(bubble.textContent).toBe('Can we take a bear put spread?');
    expect(bubble.style.maxWidth).toBe('70%');
  });

  it('appends assistant message with 75% max-width and action toolbar', () => {
    const chat = new ChatSurfaceComponent(container);
    chat.render();

    const row = chat.appendMessageDOM('assistant', 'Two things to consider:\n- 12.85 VIX compresses reward');
    expect(row).not.toBeNull();

    const bubble = row.children[0];
    expect(bubble.innerHTML).toContain('12.85 VIX compresses reward');
    expect(bubble.style.maxWidth).toBe('75%');

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
});

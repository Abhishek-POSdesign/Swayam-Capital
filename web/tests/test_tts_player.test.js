import { describe, it, expect, vi, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import {
  getTTSPreferences,
  setTTSPreferences,
  createTTSButton,
  stopCurrentPlayback,
} from '../src/components/tts-player.js';

describe('TTS Player Component', () => {
  beforeEach(() => {
    setupTestDOM();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('provides default preferences and persists updates', () => {
    const initial = getTTSPreferences();
    expect(initial.voice).toBe('swayam_calm');
    expect(initial.rate).toBe(0.90);
    expect(initial.autoPlay).toBe(false);

    setTTSPreferences({ voice: 'swayam_warm', rate: 1.1, autoPlay: true });

    const updated = getTTSPreferences();
    expect(updated.voice).toBe('swayam_warm');
    expect(updated.rate).toBe(1.1);
    expect(updated.autoPlay).toBe(true);
  });

  it('creates an action button with idle state', () => {
    const btn = createTTSButton(() => 'Test synthesis phrase');
    expect(btn).toBeDefined();
    expect(btn.tagName).toBe('BUTTON');
    expect(btn.getAttribute('data-state')).toBe('idle');
    expect(btn.title).toContain('Read aloud');
  });

  it('can stop playback cleanly', () => {
    expect(() => stopCurrentPlayback()).not.toThrow();
  });
});

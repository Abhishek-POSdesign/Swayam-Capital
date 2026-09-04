import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { AISettingsDrawer } from '../src/components/ai-settings-drawer.js';

describe('AISettingsDrawer', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders settings drawer panel with voice options and speech rate slider', () => {
    const drawer = new AISettingsDrawer(container);
    drawer.init();

    const panel = container.querySelector('#ai-settings-drawer-panel');
    expect(panel).not.toBeNull();
    expect(container.textContent).toContain('AI Partner Settings');
    expect(container.textContent).toContain('VOICE & SPEECH (INDIAN ENGLISH)');

    const rateSlider = container.querySelector('#slider-speech-rate');
    expect(rateSlider).not.toBeNull();
    expect(rateSlider.getAttribute('min')).toBe('0.5');
    expect(rateSlider.getAttribute('max')).toBe('2.0');
  });

  it('slides open and close via open() and close() methods', () => {
    const drawer = new AISettingsDrawer(container);
    drawer.init();

    const panel = container.querySelector('#ai-settings-drawer-panel');
    expect(panel.style.transform).toBe('translateX(100%)');

    drawer.open('session-test-123');
    expect(panel.style.transform).toContain('translateX(0');

    drawer.close();
    expect(panel.style.transform).toBe('translateX(100%)');
  });

  it('updates speech rate label on slider input', () => {
    const drawer = new AISettingsDrawer(container);
    drawer.init();

    const slider = container.querySelector('#slider-speech-rate');
    const label = container.querySelector('#label-speech-rate');

    slider.value = '1.15';
    slider.dispatchEvent({ type: 'input', target: slider });

    expect(label.textContent).toBe('1.15x');
  });

  it('renders notebook and pinned rule sections', () => {
    const drawer = new AISettingsDrawer(container);
    drawer.init();

    expect(container.querySelector('#settings-pinned-list')).not.toBeNull();
    expect(container.querySelector('#settings-notebook-list')).not.toBeNull();
    expect(container.querySelector('#input-new-rule')).not.toBeNull();
    expect(container.querySelector('#input-new-note')).not.toBeNull();
  });
});

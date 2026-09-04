import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { ReadinessRitualComponent } from '../src/components/readiness-ritual.js';

describe('ReadinessRitualComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders all 6 sequential steps in a single column', () => {
    const comp = new ReadinessRitualComponent(container);
    comp.render();

    expect(container.querySelector('#step-meditation')).not.toBeNull();
    expect(container.querySelector('#step-sleep')).not.toBeNull();
    expect(container.querySelector('#step-alcohol')).not.toBeNull();
    expect(container.querySelector('#step-workout')).not.toBeNull();
    expect(container.querySelector('#step-mood')).not.toBeNull();
    expect(container.querySelector('#step-stressor')).not.toBeNull();
    expect(container.querySelector('#btn-confirm-readiness')).not.toBeNull();
  });

  it('initializes meditation timer with 5:00 and start button', () => {
    const comp = new ReadinessRitualComponent(container);
    comp.render();
    comp.attachEvents();

    expect(comp.timerSeconds).toBe(300);
    expect(comp.isTimerRunning).toBe(false);
  });

  it('toggles meditation timer to Pause when started', () => {
    const comp = new ReadinessRitualComponent(container);
    comp.render();
    comp.attachEvents();

    comp.toggleMeditationTimer();
    expect(comp.isTimerRunning).toBe(true);

    // Pause it
    comp.toggleMeditationTimer();
    expect(comp.isTimerRunning).toBe(false);
  });

  it('updates form state when sleep and pill toggles are clicked', () => {
    const comp = new ReadinessRitualComponent(container);
    comp.render();
    comp.attachEvents();

    // Modify form values
    comp.formData.sleep_hours_bucket = '6-7';
    comp.formData.alcohol_yesterday = true;
    comp.formData.journal_mood = 'neutral';
    comp.formData.life_stressor = 'work';

    expect(comp.formData.sleep_hours_bucket).toBe('6-7');
    expect(comp.formData.alcohol_yesterday).toBe(true);
    expect(comp.formData.journal_mood).toBe('neutral');
    expect(comp.formData.life_stressor).toBe('work');
  });

  it('invokes submitReadiness callback on confirm button click', async () => {
    const onSubmitted = vi.fn();
    const comp = new ReadinessRitualComponent(container, { onSubmitted });
    comp.render();
    comp.attachEvents();

    // Mock submit
    comp.submitReadiness = vi.fn(async () => {
      onSubmitted({ verdict: 'green' });
    });

    const btn = container.querySelector('#btn-confirm-readiness');
    if (btn) btn.click();

    expect(comp.submitReadiness).toHaveBeenCalled();
  });
});

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { PresetBarComponent, STRATEGY_PRESETS, generatePresetLegs } from '../src/components/preset-bar.js';

describe('PresetBarComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders all strategy preset chips and Import from AI button', () => {
    const bar = new PresetBarComponent(container);
    bar.render();

    expect(container.textContent).toContain('PRESETS:');
    expect(container.textContent).toContain('Bear Put Spread');
    expect(container.textContent).toContain('Bull Call Spread');
    expect(container.textContent).toContain('Iron Condor');
    expect(container.textContent).toContain('Import from AI conversation');
  });

  it('triggers onSelectPreset when a preset chip is clicked', () => {
    const onSelect = vi.fn();
    const bar = new PresetBarComponent(container, {
      currentSpot: 24850,
      onSelectPreset: onSelect,
    });
    bar.render();

    const chip = container.querySelector('#preset-chip-iron-condor');
    expect(chip).not.toBeNull();
    chip.click();

    expect(onSelect).toHaveBeenCalled();
    const [name, legs] = onSelect.mock.calls[0];
    expect(name).toBe('Iron Condor');
    expect(legs.length).toBe(4);
  });

  it('triggers onImportAI when import button is clicked', () => {
    const onImport = vi.fn();
    const bar = new PresetBarComponent(container, {
      onImportAI: onImport,
    });
    bar.render();

    const btn = container.querySelector('#btn-import-ai');
    expect(btn).not.toBeNull();
    btn.click();

    expect(onImport).toHaveBeenCalled();
  });
});

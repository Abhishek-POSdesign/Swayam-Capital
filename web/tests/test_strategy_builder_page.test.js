import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { StrategyBuilderPage } from '../src/pages/strategy-builder.js';

describe('StrategyBuilderPage (Page Controller)', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders all sections: sidebar rail, presets, builder, payoff chart, validation, execute row, AI chat', () => {
    const page = new StrategyBuilderPage(container);
    page.renderLayout();
    page.initSubComponents();

    expect(container.querySelector('#strategy-left-rail')).not.toBeNull();
    expect(container.querySelector('#strategy-presets-container')).not.toBeNull();
    expect(container.querySelector('#leg-builder-mount')).not.toBeNull();
    expect(container.querySelector('#payoff-chart-mount')).not.toBeNull();
    expect(container.querySelector('#rule-validation-mount')).not.toBeNull();
    expect(container.querySelector('#execute-row-mount')).not.toBeNull();
    expect(container.querySelector('#strategy-ai-chat-mount')).not.toBeNull();
    expect(container.querySelector('#strategy-sticky-ticker')).not.toBeNull();
    expect(container.querySelector('#btn-back-to-home')).not.toBeNull();
  });

  it('triggers onNavigateHome when Back to Home is clicked', () => {
    const onHome = vi.fn();
    const page = new StrategyBuilderPage(container, { onNavigateHome: onHome });
    page.renderLayout();

    const btnHome = container.querySelector('#btn-back-to-home');
    expect(btnHome).not.toBeNull();
    btnHome.click();

    expect(onHome).toHaveBeenCalled();
  });
});

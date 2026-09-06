import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { ExecuteRowComponent } from '../src/components/execute-row.js';

describe('ExecuteRowComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders order type controls and the Execute button (no dead AI-order button)', () => {
    const row = new ExecuteRowComponent(container);
    row.render(false);

    expect(container.textContent).toContain('ORDER TYPE:');
    expect(container.textContent).toContain('Limit (Default)');
    expect(container.textContent).toContain('Market');
    expect(container.textContent).toContain('Execute All Legs');
    // The dead 'AI-order the legs' button was removed (pointed at a chat panel not on this page).
    expect(container.querySelector('#btn-ai-order')).toBeNull();
  });

  it('disables Execute All Legs button when canExecute is false', () => {
    const onExecute = vi.fn();
    const row = new ExecuteRowComponent(container, { onExecute });
    row.render(false);

    expect(row.canExecute).toBe(false);
    const btnExec = container.querySelector('#btn-execute-all');
    btnExec.click();
    expect(onExecute).not.toHaveBeenCalled();
  });

  it('enables Execute All Legs and triggers onExecute when canExecute is true', () => {
    const onExecute = vi.fn();
    const row = new ExecuteRowComponent(container, { onExecute });
    row.render(true);

    expect(row.canExecute).toBe(true);
    const btnExec = container.querySelector('#btn-execute-all');
    btnExec.click();
    expect(onExecute).toHaveBeenCalledWith('LIMIT');
  });
});

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

  it('renders order type controls and execution action buttons', () => {
    const row = new ExecuteRowComponent(container);
    row.render(false);

    expect(container.textContent).toContain('ORDER TYPE:');
    expect(container.textContent).toContain('Limit (Default)');
    expect(container.textContent).toContain('Market');
    expect(container.textContent).toContain('Execute All Legs');
    expect(container.textContent).toContain('AI-order the legs');
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

  it('triggers onAIOrder when AI order button is clicked', () => {
    const onAIOrder = vi.fn();
    const row = new ExecuteRowComponent(container, { onAIOrder });
    row.render(true);

    const btnAI = container.querySelector('#btn-ai-order');
    btnAI.click();
    expect(onAIOrder).toHaveBeenCalledWith('LIMIT');
  });
});

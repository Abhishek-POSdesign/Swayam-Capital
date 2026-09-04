/**
 * Execute Row Component for Swayam Capital (BUILD-10).
 *
 * Controls order type (Limit/Market), displays execution sequence preview,
 * and hosts [Execute All Legs] and [⚡ AI-order the legs for margin safety] buttons.
 */

export class ExecuteRowComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onExecute, onAIOrder, onPreviewSequence }
    this.orderType = 'LIMIT';
    this.canExecute = false;
    this.previewData = null;
  }

  render(canExecute = false, previewData = null) {
    this.canExecute = canExecute;
    this.previewData = previewData;

    const marginSummary = previewData
      ? `Estimated Margin: ₹${Math.round(previewData.final_hedged_margin_inr || 0).toLocaleString('en-IN')} (Saved ₹${Math.round(previewData.margin_saved_inr || 0).toLocaleString('en-IN')})`
      : 'Buys first · Margin-safe execution order';

    this.container.innerHTML = `
      <div class="execute-row span-12" style="
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 14px 20px;
        background: var(--dl-card);
        border: 1px solid var(--dl-line);
        border-radius: var(--radius-card);
      ">
        <!-- LEFT: Order Type Radio -->
        <div style="display: flex; align-items: center; gap: 10px;">
          <span class="eyebrow" style="color: var(--dl-fg-3);">ORDER TYPE:</span>
          <label style="display: flex; align-items: center; gap: 6px; font-size: 0.82rem; cursor: pointer; color: var(--dl-fg);">
            <input type="radio" name="order-type" value="LIMIT" ${this.orderType === 'LIMIT' ? 'checked' : ''} style="accent-color: var(--accent-sage);" />
            <span style="font-weight: 600;">Limit (Default)</span>
          </label>
          <label style="display: flex; align-items: center; gap: 6px; font-size: 0.82rem; cursor: pointer; color: var(--accent-amber);" title="Unusual — use only for cheap hedges">
            <input type="radio" name="order-type" value="MARKET" ${this.orderType === 'MARKET' ? 'checked' : ''} style="accent-color: var(--accent-amber);" />
            <span style="font-weight: 600;">Market</span>
            <span style="font-size: 0.68rem; color: var(--dl-fg-3);">(cheap hedges only)</span>
          </label>
        </div>

        <!-- MIDDLE: Preview sequence pill -->
        <div style="display: flex; align-items: center; gap: 8px;">
          <button
            type="button"
            id="btn-preview-seq"
            style="
              background: var(--dl-card-2);
              border: 1px solid var(--dl-line);
              color: var(--dl-fg-2);
              padding: 6px 14px;
              border-radius: var(--radius-pill);
              font-size: 0.76rem;
              font-weight: 600;
              cursor: pointer;
              transition: all var(--dur-fast) ease;
            "
          >
            📋 Preview Order Sequence
          </button>
          <span style="font-size: 0.76rem; font-family: var(--font-mono); color: var(--accent-sage);">
            ${marginSummary}
          </span>
        </div>

        <!-- RIGHT: Action Buttons -->
        <div style="display: flex; align-items: center; gap: 10px;">
          <!-- AI Order Legs Button -->
          <button
            type="button"
            id="btn-ai-order"
            style="
              height: 40px;
              padding: 0 16px;
              border-radius: 9px;
              font-size: 0.82rem;
              font-weight: 700;
              background: var(--accent-lilac-tint);
              color: var(--accent-lilac);
              border: 1px solid rgba(172, 159, 210, 0.4);
              cursor: pointer;
              display: flex;
              align-items: center;
              gap: 6px;
              transition: all var(--dur-fast) ease;
            "
          >
            <span>⚡ AI-order the legs</span>
          </button>

          <!-- Execute All Legs Button -->
          <button
            type="button"
            id="btn-execute-all"
            ${!this.canExecute ? 'disabled="disabled"' : ''}
            style="
              height: 40px;
              padding: 0 22px;
              border-radius: 9px;
              font-size: 0.85rem;
              font-weight: 700;
              background: ${this.canExecute ? 'var(--accent-sage)' : 'var(--dl-track)'};
              color: ${this.canExecute ? '#101116' : 'var(--dl-fg-3)'};
              border: none;
              cursor: ${this.canExecute ? 'pointer' : 'not-allowed'};
              transition: all var(--dur-fast) ease;
            "
          >
            Execute All Legs
          </button>
        </div>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    this.container.querySelectorAll('input[name="order-type"]').forEach((radio) => {
      radio.addEventListener('change', (e) => {
        this.orderType = e.target.value;
      });
    });

    const btnPreview = this.container.querySelector('#btn-preview-seq');
    if (btnPreview) {
      btnPreview.addEventListener('click', () => {
        if (this.options.onPreviewSequence) {
          this.options.onPreviewSequence();
        }
      });
    }

    const btnAI = this.container.querySelector('#btn-ai-order');
    if (btnAI) {
      btnAI.addEventListener('click', () => {
        if (this.options.onAIOrder) {
          this.options.onAIOrder(this.orderType);
        }
      });
    }

    const btnExec = this.container.querySelector('#btn-execute-all');
    if (btnExec) {
      btnExec.addEventListener('click', () => {
        if (this.canExecute && this.options.onExecute) {
          this.options.onExecute(this.orderType);
        }
      });
    }
  }
}

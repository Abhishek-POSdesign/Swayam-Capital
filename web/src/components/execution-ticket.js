/**
 * Execution Ticket — Strategy Builder v2 (Swayam Capital).
 *
 * A modal to review every leg before firing. Each leg gets its OWN Market/Limit choice and its
 * OWN editable limit price, with live Net and Margin. Paper execution now; the per-leg type +
 * price map 1:1 onto FYERS place_multileg_order for Phase 2. Replaces the old alert()-based flow.
 */

export class ExecutionTicketComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onConfirm, onClose }
    this.legs = [];
    this.preview = null;
    this.verdict = null;
    this.busy = false;
  }

  open({ legs, preview, verdict } = {}) {
    this.legs = (legs || []).map((l) => ({ ...l, order_type: (l.order_type || 'LIMIT').toUpperCase() }));
    this.preview = preview || null;
    this.verdict = verdict || null;
    this.busy = false;
    this.render();
  }

  close() {
    this.container.innerHTML = '';
    this.options.onClose?.();
  }

  _net() {
    let net = 0;
    this.legs.forEach((l) => {
      const c = (l.quantity_lots || 1) * (l.lot_size || 75);
      const v = (l.entry_premium || 0) * c;
      net += l.direction?.toLowerCase() === 'buy' ? -v : v;
    });
    return net;
  }

  _netStr() {
    const net = this._net();
    return { isCredit: net >= 0, str: `₹${Math.abs(net).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` };
  }

  render() {
    const { isCredit, str: netStr } = this._netStr();
    const marginNeeded = this.preview?.final_hedged_margin_inr;
    const marginSaved = this.preview?.margin_saved_inr;
    const v = this.verdict;
    const pass = v ? v.passed || v.overall_passed : null;

    const legRows = this.legs
      .map((l, i) => {
        const isBuy = l.direction?.toLowerCase() === 'buy';
        const isMkt = l.order_type === 'MARKET';
        const dirColor = isBuy ? 'var(--accent-sage)' : 'var(--accent-coral)';
        return `
        <div style="display:flex; align-items:center; gap:10px; padding:8px 10px; border:1px solid var(--dl-line); border-radius:6px;">
          <span style="flex:0 0 40px; font-weight:700; font-size:0.78rem; color:${dirColor};">${isBuy ? 'BUY' : 'SELL'}</span>
          <span style="flex:1 1 auto; font-family:var(--font-mono); font-size:0.8rem; color:var(--dl-fg);">NIFTY ${l.strike} ${l.option_type} · ${l.expiry_date} · ${l.quantity_lots || 1} lot</span>
          <div style="flex:0 0 auto; display:flex; background:var(--dl-card-2); border:1px solid var(--dl-line); border-radius:6px; padding:2px;">
            <button type="button" class="tk-ot" data-leg="${i}" data-ot="LIMIT" style="padding:3px 8px; font-size:0.7rem; font-weight:700; border:none; border-radius:4px; cursor:pointer; background:${!isMkt ? 'var(--accent-sage-tint)' : 'transparent'}; color:${!isMkt ? 'var(--accent-sage)' : 'var(--dl-fg-3)'};">Limit</button>
            <button type="button" class="tk-ot" data-leg="${i}" data-ot="MARKET" style="padding:3px 8px; font-size:0.7rem; font-weight:700; border:none; border-radius:4px; cursor:pointer; background:${isMkt ? 'rgba(201,160,74,0.16)' : 'transparent'}; color:${isMkt ? 'var(--accent-amber)' : 'var(--dl-fg-3)'};">Market</button>
          </div>
          <input type="number" step="0.05" min="0" data-legprice="${i}" value="${l.entry_premium || ''}" ${isMkt ? 'disabled' : ''} placeholder="${isMkt ? 'at mkt' : 'limit ₹'}" title="${isMkt ? 'Fills at market' : 'Your limit price'}" style="flex:0 0 84px; height:30px; text-align:right; background:var(--dl-input-bg,var(--dl-card-2)); color:var(--text-primary); border:1px solid var(--dl-line); border-radius:6px; padding:0 8px; font-family:var(--font-mono); font-weight:700; ${isMkt ? 'opacity:0.45;' : ''}" />
        </div>`;
      })
      .join('');

    this.container.innerHTML = `
      <div class="ticket-scrim" style="position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:1000; display:flex; align-items:center; justify-content:center; padding:20px;">
        <div class="ticket-modal" style="width:100%; max-width:640px; max-height:90vh; overflow:auto; background:var(--dl-card); border:1px solid var(--dl-line); border-radius:12px; box-shadow:0 20px 60px rgba(0,0,0,0.4);">
          <div style="display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid var(--dl-line);">
            <div style="display:flex; align-items:center; gap:10px;">
              <span style="font-family:var(--font-serif); font-size:1.15rem; font-weight:600; color:var(--dl-fg);">Review &amp; Execute</span>
              <span style="font-size:0.64rem; font-weight:700; padding:2px 8px; border-radius:999px; background:var(--accent-sage-tint); color:var(--accent-sage);">PAPER</span>
            </div>
            <button type="button" id="tk-close" style="background:transparent; border:none; color:var(--text-muted); font-size:1.1rem; cursor:pointer;">✕</button>
          </div>

          <div style="padding:16px 20px; display:flex; flex-direction:column; gap:12px;">
            ${v ? `<div style="padding:8px 12px; border-radius:6px; font-size:0.8rem; font-weight:600; background:${pass ? 'var(--accent-sage-tint)' : 'var(--accent-coral-tint)'}; color:${pass ? 'var(--accent-sage)' : 'var(--accent-coral)'};">${pass ? '✓ Passes your rules — clear to trade' : '✕ Blocked — ' + ((v.warnings && v.warnings[0]) || 'fails a Method rule')}</div>` : ''}

            <div style="display:flex; align-items:center; gap:8px; font-size:0.68rem; color:var(--dl-fg-3);">
              <span>Set each leg to Limit (your price) or Market. Buys are sent before sells (margin-safe).</span>
            </div>

            <div style="display:flex; flex-direction:column; gap:8px;">${legRows}</div>

            <div style="display:flex; justify-content:space-between; align-items:center; padding-top:6px; border-top:1px solid var(--dl-line); font-size:0.85rem;">
              <span style="color:var(--text-muted);" id="tk-net-label">${isCredit ? 'Net Credit' : 'Net Debit'}</span>
              <span id="tk-net-value" style="font-family:var(--font-serif); font-weight:700; color:${isCredit ? 'var(--accent-sage)' : 'var(--accent-coral)'};">${netStr}</span>
            </div>
            ${marginNeeded != null ? `<div style="display:flex; justify-content:space-between; font-size:0.76rem; color:var(--text-secondary); font-family:var(--font-mono);"><span>Margin needed</span><span>₹${Math.round(marginNeeded).toLocaleString('en-IN')}${marginSaved ? ` · saved ₹${Math.round(marginSaved).toLocaleString('en-IN')} vs naked` : ''}</span></div>` : ''}

            <div style="padding:8px 12px; border:1px dashed var(--dl-line); border-radius:6px; font-size:0.72rem; color:var(--dl-fg-3);">⏰ Per-trade Wake Alerts — activates in a later build (BUILD-11.13).</div>

            <div id="tk-error" style="display:none; color:var(--accent-coral); font-size:0.78rem;"></div>
          </div>

          <div style="display:flex; justify-content:flex-end; gap:10px; padding:14px 20px; border-top:1px solid var(--dl-line);">
            <button type="button" id="tk-cancel" style="height:38px; padding:0 16px; border-radius:8px; background:transparent; border:1px solid var(--dl-line); color:var(--dl-fg-2); font-weight:600; cursor:pointer;">Cancel</button>
            <button type="button" id="tk-confirm" style="height:38px; padding:0 20px; border-radius:8px; background:var(--accent-sage); color:#101116; border:none; font-weight:700; cursor:pointer;">Confirm &amp; Execute (Paper)</button>
          </div>
        </div>
      </div>
    `;
    this._attach();
  }

  _attach() {
    this.container.querySelector('#tk-close')?.addEventListener('click', () => this.close());
    this.container.querySelector('#tk-cancel')?.addEventListener('click', () => this.close());
    this.container.querySelector('.ticket-scrim')?.addEventListener('click', (e) => {
      if (e.target.classList?.contains('ticket-scrim')) this.close();
    });

    this.container.querySelectorAll('.tk-ot').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.currentTarget.getAttribute('data-leg'), 10);
        this.legs[i].order_type = e.currentTarget.getAttribute('data-ot');
        this.render(); // re-render to enable/disable the price field
      });
    });

    this.container.querySelectorAll('[data-legprice]').forEach((inp) => {
      inp.addEventListener('input', (e) => {
        const i = parseInt(e.target.getAttribute('data-legprice'), 10);
        const val = parseFloat(e.target.value);
        this.legs[i].entry_premium = isNaN(val) || val < 0 ? 0 : val;
        const { isCredit, str } = this._netStr();
        const vEl = this.container.querySelector('#tk-net-value');
        const lEl = this.container.querySelector('#tk-net-label');
        if (vEl) {
          vEl.textContent = str;
          vEl.style.color = isCredit ? 'var(--accent-sage)' : 'var(--accent-coral)';
        }
        if (lEl) lEl.textContent = isCredit ? 'Net Credit' : 'Net Debit';
      });
    });

    this.container.querySelector('#tk-confirm')?.addEventListener('click', () => this._confirm());
  }

  async _confirm() {
    if (this.busy) return;
    this.busy = true;
    const btn = this.container.querySelector('#tk-confirm');
    const errEl = this.container.querySelector('#tk-error');
    if (errEl) errEl.style.display = 'none';
    if (btn) {
      btn.textContent = 'Executing…';
      btn.disabled = true;
    }
    try {
      await this.options.onConfirm?.(this.legs);
      // Caller handles success (refresh + close).
    } catch (err) {
      if (errEl) {
        errEl.style.display = 'block';
        errEl.textContent = `Execution failed: ${err.message || err}`;
      }
      if (btn) {
        btn.textContent = 'Confirm & Execute (Paper)';
        btn.disabled = false;
      }
      this.busy = false;
    }
  }

  /** Replace the modal body with a success confirmation, then auto-close. */
  showSuccess(message) {
    const modal = this.container.querySelector('.ticket-modal');
    if (!modal) return;
    modal.innerHTML = `
      <div style="padding:28px 24px; text-align:center; display:flex; flex-direction:column; gap:10px; align-items:center;">
        <div style="font-size:1.6rem;">✅</div>
        <div style="font-family:var(--font-serif); font-size:1.1rem; font-weight:600; color:var(--dl-fg);">Paper trade executed</div>
        <div style="font-size:0.82rem; color:var(--text-secondary);">${message || ''}</div>
      </div>`;
    setTimeout(() => this.close(), 2200);
  }
}

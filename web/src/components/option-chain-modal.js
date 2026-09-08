/**
 * The option chain, as a floating panel on the desk.
 *
 * Calls on the left, strikes down the middle, puts on the right. The
 * at-the-money row is marked and scrolled to on open. Per strike: price and
 * its change, open interest with a bar scaled to the largest on screen so
 * the walls are visible at a glance, change in open interest, volume, and the
 * implied volatility solved from the traded price. Above the table: total
 * call and put open interest, the put-call ratio and max pain, all from the
 * same rows the server returned.
 *
 * Hovering a row reveals a small B and a small S on that side. Clicking one
 * adds the leg at the price on screen. Explicit buttons, never a hidden
 * modifier key: a wrong side on an options leg is not a small mistake. The
 * panel stays open, so a four-leg structure is four clicks. A strike with no
 * traded price is not clickable and says why.
 *
 * It follows the expiry chosen on the desk, refreshes on the same 5 s timer
 * as the leg prices while open, and stops when closed. Dismissed with Escape
 * and by clicking outside. Draggable by its header.
 *
 * Every number here came out of /api/option-chain or the cell says so.
 */

import { api } from '../api.js';
import { num, escapeHtml, istTime } from '../utils/display.js';

const REFRESH_MS = 5000;

function fmtChange(v) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '';
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}`;
}

function fmtInt(v) {
  return typeof v === 'number' && Number.isFinite(v) ? num(v, 0) : null;
}

function fmtIv(v) {
  return typeof v === 'number' && Number.isFinite(v) && v > 0 ? `${(v * 100).toFixed(1)}%` : null;
}

export class OptionChainModalComponent {
  constructor(host, options = {}) {
    this.host = host; // usually document.body
    this.options = options; // { onAddLeg, getExpiry, getSpot, refreshMs }
    this.refreshMs = options.refreshMs || REFRESH_MS;
    this.el = null;
    this.isOpen = false;
    this.data = null;
    this.error = null;
    this.loading = false;
    this._timer = null;
    this._onKey = null;
    this._drag = null;
    this._pos = null; // { left, top } once dragged
  }

  // ------------------------------------------------------------ lifecycle

  open() {
    if (this.isOpen) {
      this.refresh();
      return;
    }
    this.isOpen = true;
    this._mount();
    this.render();
    this.refresh(true);
    if (typeof setInterval === 'function' && !this._timer) {
      this._timer = setInterval(() => this.refresh(), this.refreshMs);
      if (this._timer && typeof this._timer.unref === 'function') this._timer.unref();
    }
    if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
      this._onKey = (e) => {
        if (e && e.key === 'Escape') this.close();
      };
      document.addEventListener('keydown', this._onKey);
    }
  }

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    if (this._onKey && typeof document !== 'undefined' && typeof document.removeEventListener === 'function') {
      document.removeEventListener('keydown', this._onKey);
    }
    this._onKey = null;
    if (this.el && typeof this.el.remove === 'function') this.el.remove();
    this.el = null;
    if (this.options.onClose) this.options.onClose();
  }

  destroy() {
    this.close();
  }

  _mount() {
    if (!this.host || typeof document === 'undefined') return;
    this.el = document.createElement('div');
    this.el.className = 'ocm-backdrop';
    this.el.id = 'option-chain-modal';
    if (typeof this.el.addEventListener === 'function') {
      // Outside click closes; clicks inside the panel do not bubble to here.
      this.el.addEventListener('click', (e) => {
        if (e && e.target === this.el) this.close();
      });
      this.el.addEventListener('click', (e) => this._onClick(e));
      this.el.addEventListener('pointerdown', (e) => this._dragStart(e));
      this.el.addEventListener('pointermove', (e) => this._dragMove(e));
      this.el.addEventListener('pointerup', () => this._dragEnd());
      this.el.addEventListener('pointercancel', () => this._dragEnd());
    }
    this.host.appendChild(this.el);
  }

  // ------------------------------------------------------------ data

  async refresh(scrollToAtm = false) {
    if (!this.isOpen || this.loading) return;
    const expiry = this.options.getExpiry ? this.options.getExpiry() : null;
    if (!expiry) {
      this.error = 'No expiry is selected on the desk.';
      this.render();
      return;
    }
    this.loading = true;
    try {
      const res = await api.getOptionChain(expiry, 30);
      this.data = res;
      this.error = null;
    } catch (err) {
      this.error = (err && err.message) || String(err);
    } finally {
      this.loading = false;
    }
    this.render();
    if (scrollToAtm) this._scrollToAtm();
  }

  // ------------------------------------------------------------ render

  render() {
    if (!this.el) return;
    const d = this.data;
    const spot = d && typeof d.spot === 'number' ? d.spot : (this.options.getSpot ? this.options.getSpot() : null);
    const rows = (d && d.strikes) || [];
    const atm = d && typeof d.atm_strike === 'number'
      ? d.atm_strike
      : spot && rows.length
        ? rows.reduce((best, r) => (Math.abs(r.strike - spot) < Math.abs(best - spot) ? r.strike : best), rows[0].strike)
        : null;

    const maxOi = rows.reduce((m, r) => Math.max(m, (r.ce && r.ce.oi) || 0, (r.pe && r.pe.oi) || 0), 0);

    const stat = (k, v, sub) =>
      `<div class="ocm-stat"><div class="k">${escapeHtml(k)}</div><div class="v sm">${v === null || v === undefined ? '<span class="na">unavailable</span>' : escapeHtml(v)}</div>${sub ? `<div class="s">${escapeHtml(sub)}</div>` : ''}</div>`;

    const head = d
      ? stat('Expiry', d.expiry || null, d.days_to_expiry !== null && d.days_to_expiry !== undefined ? `${d.days_to_expiry} days` : '') +
        stat('Spot', num(spot, 2), 'from the chain') +
        stat('Call OI', fmtInt(d.total_call_oi), 'total on screen') +
        stat('Put OI', fmtInt(d.total_put_oi), 'total on screen') +
        stat('Put-call ratio', typeof d.pcr === 'number' ? d.pcr.toFixed(2) : null, 'by open interest') +
        stat('Max pain', num(d.max_pain, 0), 'least payout at expiry')
      : '';

    const side = (q, type, strike, priced) => {
      const ltp = q && typeof q.ltp === 'number' ? q.ltp : null;
      const chg = q ? q.ltp_change_pct : null;
      const oi = q && typeof q.oi === 'number' ? q.oi : null;
      const bar = oi !== null && maxOi > 0 ? Math.max(1, (oi / maxOi) * 100) : 0;
      const dOi = q && typeof q.oi_change === 'number' ? q.oi_change : null;
      const vol = q && typeof q.volume === 'number' ? q.volume : null;
      const iv = fmtIv(q && q.iv);
      const why = priced ? '' : 'no traded price for this strike, so it cannot be added';
      const btns = `<span class="bs-mini">
          <button type="button" class="bs B" data-act="add" data-bs="B" data-strike="${strike}" data-type="${type}"${priced ? '' : ` disabled title="${escapeHtml(why)}"`}>B</button>
          <button type="button" class="bs S" data-act="add" data-bs="S" data-strike="${strike}" data-type="${type}"${priced ? '' : ` disabled title="${escapeHtml(why)}"`}>S</button>
        </span>`;
      const cells = [
        `<td class="n oi"><i class="bar ${type === 'CE' ? 'ce' : 'pe'}" style="width:${bar.toFixed(1)}%"></i><span>${oi === null ? '<span class="na">—</span>' : escapeHtml(num(oi, 0))}</span></td>`,
        `<td class="n ${dOi === null ? '' : dOi > 0 ? 'up' : dOi < 0 ? 'down' : ''}">${dOi === null ? '<span class="na">—</span>' : escapeHtml(`${dOi > 0 ? '+' : ''}${num(dOi, 0)}`)}</td>`,
        `<td class="n">${vol === null ? '<span class="na">—</span>' : escapeHtml(num(vol, 0))}</td>`,
        `<td class="n">${iv === null ? '<span class="na">—</span>' : escapeHtml(iv)}</td>`,
        `<td class="n px ${typeof chg === 'number' ? (chg < 0 ? 'down' : chg > 0 ? 'up' : '') : ''}">${ltp === null ? `<span class="na" title="${escapeHtml(why)}">no trade</span>` : `<b>${escapeHtml(num(ltp, 2))}</b><small>${escapeHtml(fmtChange(chg))}${typeof chg === 'number' ? '%' : ''}</small>`}</td>`,
      ];
      // Calls read left-to-right towards the strike; puts mirror it.
      const ordered = type === 'CE' ? cells : cells.slice().reverse();
      return type === 'CE'
        ? `<td class="act">${btns}</td>${ordered.join('')}`
        : `${ordered.join('')}<td class="act">${btns}</td>`;
    };

    const body = rows.map((r) => {
      const isAtm = atm !== null && r.strike === atm;
      const cePriced = Boolean(r.ce && typeof r.ce.ltp === 'number');
      const pePriced = Boolean(r.pe && typeof r.pe.ltp === 'number');
      return `<tr class="${isAtm ? 'atm' : ''}${spot && r.strike < spot ? ' itm-ce' : ''}" data-strike="${r.strike}">
        ${side(r.ce, 'CE', r.strike, cePriced)}
        <td class="k-strike"><b>${escapeHtml(num(r.strike, 0))}</b>${isAtm ? '<i>ATM</i>' : ''}</td>
        ${side(r.pe, 'PE', r.strike, pePriced)}
      </tr>`;
    }).join('');

    const status = this.error
      ? `<span class="chip c-na">${escapeHtml(this.error)}</span>`
      : d
        ? `<span class="chip c-live">read ${escapeHtml(istTime(d.as_of) || '')} IST · refreshes every ${Math.round(this.refreshMs / 1000)} s while open</span>`
        : `<span class="chip c-info">${this.loading ? 'reading the chain…' : 'no data yet'}</span>`;

    const style = this._pos ? ` style="left:${this._pos.left}px;top:${this._pos.top}px;transform:none"` : '';

    this.el.innerHTML = `
      <div class="ocm sw-desk" role="dialog" aria-label="Option chain"${style}>
        <div class="ocm-h" data-drag="1">
          <b>Option chain</b>
          ${status}
          <span class="r">hover a row for B and S · Esc or click outside to close · drag here to move</span>
          <button type="button" class="btn sm" data-act="close">Close</button>
        </div>
        <div class="ocm-stats">${head || '<div class="na" style="padding:8px 14px">Nothing read yet.</div>'}</div>
        <div class="ocm-scroll">
          <table class="ocm-t">
            <thead><tr>
              <th></th><th>OI</th><th>ΔOI</th><th>Vol</th><th>IV</th><th>Call</th>
              <th class="k-strike">Strike</th>
              <th>Put</th><th>IV</th><th>Vol</th><th>ΔOI</th><th>OI</th><th></th>
            </tr></thead>
            <tbody>${body || `<tr><td colspan="13" class="na" style="padding:18px;text-align:center">${this.error ? 'The chain could not be read.' : 'Loading…'}</td></tr>`}</tbody>
          </table>
        </div>
      </div>`;
  }

  _scrollToAtm() {
    if (!this.el || typeof this.el.querySelector !== 'function') return;
    const row = this.el.querySelector('tr.atm');
    if (row && typeof row.scrollIntoView === 'function') {
      try { row.scrollIntoView({ block: 'center' }); } catch (_) {}
    }
  }

  // ------------------------------------------------------------ events

  _onClick(e) {
    const t = e && e.target;
    if (!t || typeof t.closest !== 'function') return;
    const btn = t.closest('[data-act]');
    if (!btn) return;
    const act = btn.getAttribute('data-act');
    if (act === 'close') {
      this.close();
    } else if (act === 'add') {
      if (btn.disabled) return;
      this.addLeg(btn.getAttribute('data-bs'), Number(btn.getAttribute('data-strike')), btn.getAttribute('data-type'));
    }
  }

  /** Adds the leg at the price on screen, from the row the button sits in. */
  addLeg(bs, strike, type) {
    const row = (this.data && this.data.strikes || []).find((r) => r.strike === strike);
    const q = row ? (type === 'CE' ? row.ce : row.pe) : null;
    if (!q || typeof q.ltp !== 'number') return false;
    if (this.options.onAddLeg) {
      this.options.onAddLeg({
        bs: bs === 'S' ? 'S' : 'B',
        strike,
        type,
        price: q.ltp,
        iv: typeof q.iv === 'number' ? q.iv : null,
        expiry: this.data.expiry,
        asOf: this.data.as_of,
      });
    }
    return true;
  }

  _dragStart(e) {
    const t = e && e.target;
    const handle = t && typeof t.closest === 'function' ? t.closest('[data-drag]') : null;
    if (!handle || (t.closest && t.closest('button'))) return;
    const panel = this.el.querySelector('.ocm');
    if (!panel || typeof panel.getBoundingClientRect !== 'function') return;
    const rect = panel.getBoundingClientRect();
    this._drag = { dx: e.clientX - rect.left, dy: e.clientY - rect.top };
    if (typeof this.el.setPointerCapture === 'function' && e.pointerId !== undefined) {
      try { this.el.setPointerCapture(e.pointerId); } catch (_) {}
    }
  }

  _dragMove(e) {
    if (!this._drag) return;
    const panel = this.el.querySelector('.ocm');
    if (!panel) return;
    const left = Math.max(0, e.clientX - this._drag.dx);
    const top = Math.max(0, e.clientY - this._drag.dy);
    this._pos = { left, top };
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
    panel.style.transform = 'none';
  }

  _dragEnd() {
    this._drag = null;
  }
}

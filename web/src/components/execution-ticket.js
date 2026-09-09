/**
 * The execution ticket. docs/PLAN.md 2.12, PR 1.
 *
 * Pressing Execute on the desk used to send the trade straight out, at prices
 * he had not confirmed, in an order the server chose, with one order type for
 * the whole structure. Now it opens this ticket, and nothing is sent until he
 * presses a button on it.
 *
 * Per leg, in the order they will go: buy or sell, the contract, lots he can
 * edit, Market or Limit, a price he can edit, a proper Reset that puts the
 * live quote back, and what the fill would be right now. Up and down buttons
 * move a leg. Below the legs: net debit or credit at those prices, the charges
 * to get in, the margin the broker needs, and his four rules exactly as the
 * desk shows them. Two buttons: Execute all, and Execute one by one.
 *
 * His list, verbatim in intent, 2026-09-09: market or limit with a swap, an
 * editable price with a proper reset, editable lots, margin needed, control
 * over which leg goes first, all together or one at a time. NO bid-ask
 * ladder. NO market depth.
 *
 * The ticket owns no data. Quotes come from the desk, which re-quotes every
 * five seconds and calls `update()`; the send goes back to the desk through
 * `onSend`, which owns the API and the execution key. A Market leg follows
 * the live quote on screen; a Limit price is his and never overwritten.
 */

import { inr, num, escapeHtml, istTime } from '../utils/display.js';

const px = (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2) : '—');
const legName = (l) => `${num(l.strike)} ${l.type}`;

/**
 * What one leg would fill at right now. Mirrors services/fills.py on the
 * server: this is a preview, the server decides. In PR 1 the market is the
 * traded price; PR 2 moves a buy to the ask and a sell to the bid.
 */
export function previewFill(leg, state) {
  const market = typeof leg.price === 'number' ? leg.price : null;
  if (market === null) return { ok: false, price: null, how: 'no live price, so this leg cannot fill' };
  if (state.mode === 'MARKET') return { ok: true, price: market, how: `market · at ${px(market)}` };
  const limit = state.limit;
  if (typeof limit !== 'number' || !(limit > 0)) return { ok: false, price: null, how: 'type a limit price, or press Reset' };
  const marketable = leg.bs === 'B' ? limit >= market : limit <= market;
  return marketable
    ? { ok: true, price: limit, how: `limit ${px(limit)} · fills, market is ${px(market)}` }
    : { ok: false, price: null, how: `would not fill now · market is ${px(market)}` };
}

export class ExecutionTicket {
  /**
   * @param {HTMLElement} host Where the ticket mounts, usually a div on the desk.
   * @param {object} options
   *   onSend(legs, mode)   -> Promise<result>  the desk sends and returns what happened
   *   onSendNext(leg, i)   -> Promise<result>  one-by-one: the next leg
   *   onClose()                                the ticket was dismissed
   *   onChange()                               the order, lots or prices changed (desk may re-preview)
   *   rulesHtml()          -> string           the desk's four rules, as rendered on the desk
   */
  constructor(host, options = {}) {
    this.host = host;
    this.options = options;
    this.isOpen = false;
    this.legs = [];           // desk legs, in HIS order
    this.state = new Map();   // leg key -> { mode, limit, lots }
    this.ctx = {};            // { expiry, expiryLabel, lotSize, spot, spotAt, preview, capital, marginUsed, dataState }
    this.phase = 'ticket';    // ticket | sending | walking | done | error
    this.sendMode = null;     // all | one
    this.fills = [];          // what came back, in order
    this.pending = [];        // one-by-one: legs not yet sent
    this.result = null;
    this.error = null;
    this.refused = [];
    this._onKey = null;
  }

  // ------------------------------------------------------------ lifecycle

  open(legs, ctx) {
    this.legs = legs.map((l) => ({ ...l }));
    this.legs.forEach((l) => {
      const key = this._key(l);
      if (!this.state.has(key)) this.state.set(key, { mode: 'MARKET', limit: l.price, lots: l.lots });
    });
    // Buys first by default, because that earns the hedged margin. He can move them.
    this.legs.sort((a, b) => (a.bs === b.bs ? 0 : a.bs === 'B' ? -1 : 1));
    this.ctx = { ...ctx };
    this.phase = 'ticket';
    this.sendMode = null;
    this.fills = [];
    this.pending = [];
    this.result = null;
    this.error = null;
    this.refused = [];
    this.isOpen = true;
    if (typeof document !== 'undefined' && typeof document.addEventListener === 'function' && !this._onKey) {
      this._onKey = (e) => { if (e && e.key === 'Escape' && this.phase === 'ticket') this.close(); };
      document.addEventListener('keydown', this._onKey);
    }
    this.render();
  }

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    if (this._onKey && typeof document !== 'undefined' && typeof document.removeEventListener === 'function') {
      document.removeEventListener('keydown', this._onKey);
    }
    this._onKey = null;
    this.state.clear();
    if (this.host) this.host.innerHTML = '';
    if (this.options.onClose) this.options.onClose();
  }

  destroy() { this.close(); }

  /** The desk re-quoted its legs. Market legs follow; limit prices are his. */
  update(legs, ctx) {
    if (!this.isOpen) return;
    const byKey = new Map(legs.map((l) => [this._key(l), l]));
    this.legs = this.legs.map((l) => {
      const fresh = byKey.get(this._key(l));
      return fresh ? { ...l, price: fresh.price, priceSource: fresh.priceSource, priceAt: fresh.priceAt, bid: fresh.bid, ask: fresh.ask } : l;
    });
    if (ctx) this.ctx = { ...this.ctx, ...ctx };
    if (this.phase === 'ticket') this.render();
  }

  // ------------------------------------------------------------ state

  _key(l) { return `${l.bs}-${l.strike}-${l.type}-${l.expiry || ''}`; }
  _st(l) { return this.state.get(this._key(l)); }

  /** The legs as the server wants them, in his order. */
  payload() {
    return this.legs.map((l) => {
      const st = this._st(l);
      const f = previewFill(l, st);
      return {
        strike: l.strike,
        option_type: l.type,
        direction: l.bs === 'B' ? 'buy' : 'sell',
        quantity_lots: st.lots,
        expiry_date: this.ctx.expiry,
        order_type: st.mode,
        limit_price: st.mode === 'LIMIT' ? st.limit : null,
        // The price the ticket showed. The server fills at ITS quote; this is
        // kept so the record can show what the ticket said at the time.
        entry_premium: f.price !== null ? f.price : (typeof l.price === 'number' ? l.price : 0),
      };
    });
  }

  /** Why nothing can be sent right now, or null. The market clock is the one clock. */
  marketBlock() {
    const st = this.ctx.dataState;
    if (st === 'closing') return 'The market is closed, so nothing can fill. Keep the structure on the desk and send it in your window.';
    if (st === 'unavailable') return 'No live data, so nothing can fill. Check the data-health strip; if it names the token, refresh it.';
    return null;
  }

  totals() {
    const lot = this.ctx.lotSize;
    let net = 0;
    let priced = true;
    const blocked = [];
    this.legs.forEach((l) => {
      const st = this._st(l);
      const f = previewFill(l, st);
      if (!f.ok) { blocked.push(`${l.bs === 'B' ? 'BUY' : 'SELL'} ${legName(l)}`); priced = false; return; }
      if (typeof lot !== 'number') { priced = false; return; }
      net += (l.bs === 'S' ? 1 : -1) * f.price * st.lots * lot;
    });
    return { net: priced ? net : null, blocked };
  }

  // ------------------------------------------------------------ actions

  move(index, dir) {
    const j = index + dir;
    if (j < 0 || j >= this.legs.length) return;
    [this.legs[index], this.legs[j]] = [this.legs[j], this.legs[index]];
    this._changed();
  }

  setMode(index, mode) {
    const st = this._st(this.legs[index]);
    st.mode = mode === 'LIMIT' ? 'LIMIT' : 'MARKET';
    if (st.mode === 'LIMIT' && typeof st.limit !== 'number') st.limit = this.legs[index].price;
    this._changed();
  }

  setLimit(index, value) {
    const st = this._st(this.legs[index]);
    const v = parseFloat(value);
    st.limit = Number.isFinite(v) && v > 0 ? Math.round(v * 20) / 20 : null;
    this._changed({ keepFocus: `[data-limit="${index}"]` });
  }

  resetPrice(index) {
    const st = this._st(this.legs[index]);
    st.limit = this.legs[index].price;
    this._changed();
  }

  stepLots(index, delta) {
    const st = this._st(this.legs[index]);
    st.lots = Math.max(1, (st.lots || 1) + delta);
    this._changed();
  }

  _changed(opts = {}) {
    if (this.options.onChange) this.options.onChange(this.payload());
    this.render();
    if (opts.keepFocus && this.host && typeof this.host.querySelector === 'function') {
      const el = this.host.querySelector(opts.keepFocus);
      if (el && typeof el.focus === 'function') el.focus();
    }
  }

  async send(mode) {
    if (this.phase !== 'ticket') return;
    const { blocked } = this.totals();
    if (blocked.length || this.marketBlock()) return;
    this.sendMode = mode;
    this.error = null;
    this.refused = [];
    const legs = this.payload();
    if (mode === 'one') {
      this.pending = legs.slice(1);
      this.phase = 'sending';
      this.render();
      try {
        this.result = await this.options.onSend([legs[0]], 'one_by_one');
        this.fills = Array.isArray(this.result && this.result.fills) ? this.result.fills : [];
        this.phase = this.pending.length ? 'walking' : 'done';
      } catch (err) {
        this._fail(err);
      }
      this.render();
      return;
    }
    this.phase = 'sending';
    this.render();
    try {
      this.result = await this.options.onSend(legs, 'all');
      this.fills = Array.isArray(this.result && this.result.fills) ? this.result.fills : [];
      this.phase = 'done';
    } catch (err) {
      this._fail(err);
    }
    this.render();
  }

  async sendNext() {
    if (this.phase !== 'walking' || !this.pending.length) return;
    const leg = this.pending[0];
    this.phase = 'sending';
    this.render();
    try {
      const res = await this.options.onSendNext(leg, this.fills.length + 1);
      if (res && res.fill) this.fills.push(res.fill);
      this.pending = this.pending.slice(1);
      this.phase = this.pending.length ? 'walking' : 'done';
      if (this.phase === 'done') this.result = { ...(this.result || {}), ...res, fills: this.fills };
    } catch (err) {
      this._fail(err, { resumable: true });
    }
    this.render();
  }

  stopHere() {
    if (this.phase !== 'walking') return;
    this.pending = [];
    this.phase = 'done';
    this.result = { ...(this.result || {}), fills: this.fills, stopped: true };
    this.render();
  }

  _fail(err, opts = {}) {
    const detail = err && err.detail;
    if (detail && Array.isArray(detail.refused_legs)) {
      this.refused = detail.refused_legs;
      this.error = detail.error || 'Nothing was sent.';
    } else {
      this.error = String((err && err.message) || err);
    }
    // A refusal before anything was sent returns him to the ticket, with every
    // problem listed. A failure mid-walk keeps what has filled and lets him retry.
    this.phase = opts.resumable && this.fills.length ? 'walking' : 'ticket';
  }

  // ------------------------------------------------------------ render

  render() {
    if (!this.host || !this.isOpen) return;
    let body;
    if (this.phase === 'ticket') body = this._ticket();
    else if (this.phase === 'sending') body = this._progress('Sending…');
    else if (this.phase === 'walking') body = this._progress(null);
    else body = this._done();
    this.host.innerHTML = `<div class="xt-backdrop" data-xt="backdrop"><div class="xt sw-desk" role="dialog" aria-modal="true" aria-label="Execution ticket">${body}</div></div>`;
    this._bind();
  }

  _header(title, sub) {
    const s = this.ctx;
    const live = s.dataState === 'live';
    const chip = live
      ? `<span class="chip c-live">LIVE · ${escapeHtml(istTime(s.spotAt) || '')}</span>`
      : `<span class="chip c-na">${escapeHtml(s.dataState === 'closing' ? 'AT THE CLOSE · nothing can fill' : s.dataState === 'delayed' ? 'BEHIND' : 'NO LIVE DATA')}</span>`;
    return `<header class="xt-h"><div><h2>${escapeHtml(title)}</h2><div class="sub">${escapeHtml(sub)}</div></div>
      <div class="r">${chip}${this.phase === 'ticket' ? '<button class="btn sm" type="button" data-xt="close">Back to the desk</button>' : ''}</div></header>`;
  }

  _ticket() {
    const s = this.ctx;
    const rows = this.legs.map((l, i) => {
      const st = this._st(l);
      const f = previewFill(l, st);
      const own = l.priceSource && /own/i.test(String(l.priceSource));
      return `<div class="xt-row" data-i="${i}">
        <div class="seq">
          <button type="button" data-xt="up" data-i="${i}" ${i === 0 ? 'disabled' : ''} aria-label="Send earlier" title="Send earlier">▲</button>
          <b>${i + 1}</b>
          <button type="button" data-xt="down" data-i="${i}" ${i === this.legs.length - 1 ? 'disabled' : ''} aria-label="Send later" title="Send later">▼</button>
        </div>
        <div><span class="bs ${l.bs}">${l.bs === 'B' ? 'BUY' : 'SELL'}</span></div>
        <div class="contract">${escapeHtml(legName(l))}<small>${escapeHtml(s.expiryLabel || s.expiry || '')}</small></div>
        <div class="stepper">
          <button type="button" data-xt="lots-" data-i="${i}" ${st.lots <= 1 ? 'disabled' : ''} aria-label="One lot fewer">−</button>
          <input value="${st.lots}" readonly aria-label="Lots">
          <button type="button" data-xt="lots+" data-i="${i}" aria-label="One lot more">+</button>
        </div>
        <div class="seg" role="group" aria-label="Order type">
          <button type="button" data-xt="mode" data-mode="MARKET" data-i="${i}" aria-pressed="${st.mode === 'MARKET'}">Market</button>
          <button type="button" data-xt="mode" data-mode="LIMIT" data-i="${i}" aria-pressed="${st.mode === 'LIMIT'}">Limit</button>
        </div>
        <div class="price">
          <input type="number" step="0.05" inputmode="decimal" data-limit="${i}" aria-label="Price"
                 value="${st.mode === 'LIMIT' ? (typeof st.limit === 'number' ? st.limit.toFixed(2) : '') : px(l.price)}"
                 ${st.mode === 'MARKET' ? 'disabled' : ''}>
          <button class="btn sm" type="button" data-xt="reset" data-i="${i}" ${st.mode === 'MARKET' ? 'disabled' : ''} title="Put the live quote back">Reset</button>
          <div class="quote">${typeof l.price === 'number' ? `traded <b>${px(l.price)}</b>${own ? '<br>his price' : ''}` : '<span class="na">no price</span>'}${typeof l.bid === 'number' || typeof l.ask === 'number' ? `<br>bid <b>${px(l.bid)}</b> · ask <b>${px(l.ask)}</b>` : ''}</div>
        </div>
        <div class="fillnote ${f.ok ? 'ok' : 'no'}">${escapeHtml(f.how)}</div>
      </div>`;
    }).join('');

    const t = this.totals();
    const shut = this.marketBlock();
    const p = s.preview || {};
    const need = typeof p.margin_required_inr === 'number' ? p.margin_required_inr : null;
    const used = typeof s.marginUsed === 'number' ? s.marginUsed : null;
    const cap = s.capital || {};
    const ceiling = typeof cap.deployable_margin_ceiling_inr === 'number' ? cap.deployable_margin_ceiling_inr : null;
    const charges = typeof p.entry_charges_total_inr === 'number' ? p.entry_charges_total_inr : null;
    const refusedHtml = this.refused.length
      ? `<div class="xt-refused"><b>${escapeHtml(this.error || 'Nothing was sent.')}</b><ul>${this.refused.map((r) => `<li><b>${escapeHtml(r.leg)}</b> · ${escapeHtml(r.reason)}</li>`).join('')}</ul></div>`
      : this.error ? `<div class="xt-refused"><b>Not executed.</b> ${escapeHtml(this.error)}</div>` : '';

    return this._header('Execution ticket', `${s.strategyName || 'Custom'} · paper book · NIFTY ${num(s.spot, 2)} · lot ${typeof s.lotSize === 'number' ? s.lotSize : 'unconfirmed'}`) +
      refusedHtml +
      `<div class="xt-legs">
        <div class="xt-row h"><span>Order</span><span>Side</span><span>Contract</span><span>Lots</span><span>Type</span><span>Price</span><span>Fill now</span></div>
        ${rows}
      </div>
      <div class="xt-foot">
        <div class="kv">
          <span>Net ${t.net === null ? 'debit or credit' : t.net >= 0 ? 'credit' : 'debit'} at these prices</span>
          <b class="${t.net === null ? 'na' : t.net >= 0 ? 'up' : 'down'}">${t.net === null ? 'unavailable' : escapeHtml(inr(Math.abs(t.net)))}</b>
          <span>Charges to get in, per leg, summed</span>
          <b>${charges === null ? '<span class="na">unavailable</span>' : escapeHtml(inr(charges))}</b>
          <span>Margin the broker needs for this basket</span>
          <b>${need === null ? `<span class="na">${escapeHtml(p.margin_unavailable_reason || 'not priced yet')}</span>` : escapeHtml(inr(need))}</b>
          <span>Margin already used</span>
          <b>${used === null ? '<span class="na">unavailable</span>' : escapeHtml(inr(used))}</b>
          <span>Ceiling, twice the cash equivalent</span>
          <b>${ceiling === null ? '<span class="na">unavailable</span>' : escapeHtml(inr(ceiling))}</b>
        </div>
        <div class="rules xt-rules">${this.options.rulesHtml ? this.options.rulesHtml() : ''}</div>
      </div>
      <div class="xt-actions">
        <button class="btn pri" type="button" data-xt="send-all" ${t.blocked.length || shut ? 'disabled' : ''}>Execute all legs</button>
        <button class="btn" type="button" data-xt="send-one" ${t.blocked.length || shut ? 'disabled' : ''}>Execute one by one</button>
        <span class="why">${shut
          ? escapeHtml(shut)
          : t.blocked.length
            ? escapeHtml(`${t.blocked.join(', ')} would not fill at that price. Move it, press Reset, or switch it to market.`)
            : 'buys go first by default, that is what earns the hedged margin · one press, one trade · the server fills at its own live quote'}</span>
      </div>`;
  }

  _fillLine(f, i) {
    const side = String(f.direction || '').toUpperCase();
    return `<li><span class="st">FILLED</span><div><span class="bs ${side === 'BUY' ? 'B' : 'S'}">${side}</span> &nbsp;<b>${escapeHtml(num(f.strike))} ${escapeHtml(f.option_type || '')}</b> · ${f.quantity_lots} lot${f.quantity_lots > 1 ? 's' : ''}
      <small>${escapeHtml(f.how || '')}${typeof f.entry_charges_inr === 'number' ? ` · charges ${escapeHtml(inr(f.entry_charges_inr))}` : ''}</small></div><b class="num">${px(f.fill_price)}</b></li>`;
  }

  _progress(sendingText) {
    const s = this.ctx;
    const pending = this.pending.map((l) => `<li><span class="st wait">WAITING</span><div><span class="bs ${l.direction === 'buy' ? 'B' : 'S'}">${l.direction === 'buy' ? 'BUY' : 'SELL'}</span> &nbsp;<b>${escapeHtml(num(l.strike))} ${escapeHtml(l.option_type)}</b> · ${l.quantity_lots} lot<small>not sent yet</small></div><b class="num na">—</b></li>`).join('');
    const next = this.pending[0];
    const walking = this.phase === 'walking';
    return this._header(
      sendingText ? sendingText : `Leg ${this.fills.length} of ${this.fills.length + this.pending.length} is in. The next one waits for you.`,
      walking ? 'One by one: each leg is sent when you press, and the trade is the same trade throughout. Stopping here leaves a half-built structure, which is allowed.' : 'nothing else is sent until this answers',
    ) +
      (this.error ? `<div class="xt-refused"><b>The last leg was not sent.</b> ${escapeHtml(this.error)}${this.refused.map((r) => ` ${escapeHtml(r.reason)}`).join('')}</div>` : '') +
      `<div class="xt-fills"><ul class="fills">${this.fills.map((f, i) => this._fillLine(f, i)).join('')}${pending}</ul></div>
      <div class="xt-actions">
        ${walking && next ? `<button class="btn pri" type="button" data-xt="send-next">Send leg ${this.fills.length + 1} · ${next.direction === 'buy' ? 'BUY' : 'SELL'} ${escapeHtml(num(next.strike))} ${escapeHtml(next.option_type)}</button>
        <button class="btn" type="button" data-xt="stop">Stop here</button>` : '<span class="why">sending…</span>'}
        ${walking && this.result && this.result.position_id ? `<span class="why">trade #${escapeHtml(String(this.result.position_id).slice(0, 8))} is open with ${this.fills.length} leg${this.fills.length === 1 ? '' : 's'}</span>` : ''}
      </div>`;
  }

  _done() {
    const r = this.result || {};
    const id = r.position_id ? String(r.position_id).slice(0, 8) : '';
    const net = typeof r.net_debit_credit_inr === 'number' ? r.net_debit_credit_inr : null;
    const note = r.journal_status === 'written'
      ? 'The note is in your vault.'
      : r.journal_status === 'pending'
        ? 'The note is queued for your vault; the drainer writes it from your PC.'
        : r.journal_status === 'failed' ? 'The note could not be written or queued. Write it by hand.' : '';
    return this._header(
      r.stopped ? `Stopped. Trade #${id} is open with ${this.fills.length} leg${this.fills.length === 1 ? '' : 's'}.` : `Filled. Trade #${id} is open.`,
      'Every leg was filled at the server’s live quote at the moment of sending. Here is what actually happened.',
    ) +
      `<div class="xt-fills"><ul class="fills">${this.fills.map((f, i) => this._fillLine(f, i)).join('')}</ul></div>
      <div class="xt-foot">
        <div class="kv">
          <span>Net ${net === null ? 'debit or credit' : net >= 0 ? 'credit received' : 'debit paid'}</span><b class="${net === null ? 'na' : net >= 0 ? 'up' : 'down'}">${net === null ? 'unavailable' : escapeHtml(inr(Math.abs(net)))}</b>
          <span>Charges to get in, recorded on each leg</span><b>${typeof r.entry_charges_inr === 'number' ? escapeHtml(inr(r.entry_charges_inr)) : '<span class="na">unavailable</span>'}</b>
          <span>Spot at entry, stored on the row</span><b>${typeof r.spot_at_entry === 'number' ? escapeHtml(num(r.spot_at_entry, 2)) : '<span class="na">unavailable</span>'}</b>
          <span>Margin the broker needed, stored so rule 4 can be tested</span><b>${typeof r.margin_required_inr === 'number' ? escapeHtml(inr(r.margin_required_inr)) : `<span class="na">${escapeHtml(r.margin_source || 'unavailable')}</span>`}</b>
          <span>Max loss of what you hold</span><b>${typeof r.max_loss_inr === 'number' ? escapeHtml(inr(r.max_loss_inr)) : '<span class="na">unavailable</span>'}</b>
        </div>
        <div class="xt-note">${escapeHtml(note)}</div>
      </div>
      <div class="xt-actions">
        <button class="btn pri" type="button" data-xt="finish">Back to the desk</button>
        <span class="why">the position appears on Home and, from PR 3, in the position area below the payoff</span>
      </div>`;
  }

  _bind() {
    if (!this.host || typeof this.host.querySelector !== 'function') return;
    const root = this.host.querySelector('[data-xt="backdrop"]');
    if (!root || typeof root.addEventListener !== 'function') return;
    root.addEventListener('click', (e) => {
      const t = e && e.target && typeof e.target.closest === 'function' ? e.target.closest('[data-xt]') : null;
      if (!t) return;
      const act = t.getAttribute('data-xt');
      const i = Number(t.getAttribute('data-i'));
      if (act === 'backdrop') return; // a click on the dark area does nothing; money deserves a deliberate button
      if (act === 'close') this.close();
      else if (act === 'up') this.move(i, -1);
      else if (act === 'down') this.move(i, 1);
      else if (act === 'lots-') this.stepLots(i, -1);
      else if (act === 'lots+') this.stepLots(i, 1);
      else if (act === 'mode') this.setMode(i, t.getAttribute('data-mode'));
      else if (act === 'reset') this.resetPrice(i);
      else if (act === 'send-all') this.send('all');
      else if (act === 'send-one') this.send('one');
      else if (act === 'send-next') this.sendNext();
      else if (act === 'stop') this.stopHere();
      else if (act === 'finish') { const r = this.result; this.close(); if (this.options.onFinish) this.options.onFinish(r); }
    });
    root.addEventListener('change', (e) => {
      const t = e && e.target;
      if (t && t.getAttribute && t.getAttribute('data-limit') !== null) this.setLimit(Number(t.getAttribute('data-limit')), t.value);
    });
  }
}

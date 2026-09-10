/**
 * The exit ticket. The entry ticket, the other way round.
 *
 * docs/builds/BUILD_01_DESK_POSITION_AREA.md section 3.8, and his decision of
 * 2026-09-09 evening: "exiting a single leg or exiting all legs should have a
 * limit/market price option." So every way out of a trade comes through here,
 * one leg or all of them, with market or limit PER LEG, an editable price, a
 * proper Reset with the word on it, the charges both ways, and the net before
 * he presses.
 *
 * WHERE THE NUMBERS COME FROM. Nowhere in this file is money invented. Every
 * figure is read off `/api/positions/live`, which marks each leg at the side
 * he would actually get and costs the exit through the real charge engine.
 * A leg that could not be marked shows `unavailable` with the reason.
 *
 * WHY THE FIGURES STAY RIGHT WHEN HE TYPES A LIMIT. A limit fills at his price
 * OR BETTER, which in practice means it fills at the book. So whenever a leg
 * would fill at all, its fill price is the book price the server already
 * marked and costed, and the gross, the charges and the net on screen are
 * exactly what he will get. A limit the book has not reached does not fill in
 * this build, and that leg shows no figures at all rather than a hypothetical.
 *
 * WHAT THIS BUILD DOES NOT DO. Resting orders are Build B. A limit away from
 * the book refuses the send, in words that cannot be mistaken for a rule.
 */

import { inr, inrExact, num, escapeHtml, istTime, orNA } from '../utils/display.js';

const px = (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2) : '—');
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const legName = (l) => `${num(l.strike)} ${l.option_type}`;

/** The direction that closes a leg: a bought leg is sold, a sold leg is bought. */
export function exitSideOf(direction) {
  return String(direction).toLowerCase() === 'buy' || String(direction).toLowerCase() === 'long'
    ? 'sell'
    : 'buy';
}

/**
 * The price this exit would actually take, and which side of the book it is.
 * A leg he bought is SOLD at the bid; a leg he sold is BOUGHT back at the ask.
 * The server already marked it this way; this only names it for the screen.
 */
export function bookForExit(leg) {
  const side = exitSideOf(leg.direction) === 'buy' ? 'ask' : 'bid';
  const price = isNum(leg[side]) ? leg[side] : isNum(leg.mark) ? leg.mark : null;
  return { side, price };
}

/**
 * What one leg would do on send. Mirrors services/fills.py, reversed: the
 * server decides, this is the preview he reads first.
 */
export function previewExit(leg, state) {
  const { side, price } = bookForExit(leg);
  const buying = exitSideOf(leg.direction) === 'buy';
  if (price === null) {
    return { ok: false, price: null, how: `no ${side} published, so this leg cannot be exited` };
  }
  if (state.mode === 'MARKET') {
    return { ok: true, price, how: `market · at the ${side} ${px(price)}` };
  }
  const limit = state.limit;
  if (!isNum(limit) || limit <= 0) {
    return { ok: false, price: null, how: 'type a limit price, or press Reset' };
  }
  const marketable = buying ? limit >= price : limit <= price;
  if (!marketable) {
    return {
      ok: false,
      price: null,
      away: true,
      how: `your price, not a rule · the ${side} is ${px(price)}`,
    };
  }
  const better = Math.abs(price - limit) >= 0.005;
  return {
    ok: true,
    price,
    how: better ? `limit ${px(limit)} · fills at the ${side} ${px(price)}, better` : `limit ${px(limit)} · fills at the ${side}`,
  };
}

export class ExitTicket {
  /**
   * @param {HTMLElement} host Where the ticket mounts.
   * @param {object} options
   *   onExitAll(payload)      -> Promise<result>   close every open leg
   *   onExitLeg(seq, payload) -> Promise<result>   close one leg
   *   onDone(result)                              he pressed Back after a fill
   *   onClose()                                   dismissed with nothing sent
   */
  constructor(host, options = {}) {
    this.host = host;
    this.options = options;
    this.isOpen = false;
    this.position = null;
    this.legs = [];
    this.state = new Map();
    this.only = null;          // a sequence number, or null for every open leg
    this.phase = 'ticket';     // ticket | sending | walking | done
    this.reason = 'Manual';
    this.note = '';
    this.result = null;
    this.error = null;
    this.refused = [];
    this.pending = [];
    this.doneLegs = [];
    this._onKey = null;
  }

  // ------------------------------------------------------------- lifecycle

  /**
   * @param {object} position a row from /api/positions/live
   * @param {number|null} onlySequence one leg, or null for all of them
   */
  open(position, onlySequence = null) {
    this.position = position;
    this.only = onlySequence;
    this.legs = (position.legs || [])
      .filter((l) => String(l.status || 'open') !== 'closed')
      .filter((l) => (onlySequence === null ? true : Number(l.sequence) === Number(onlySequence)));
    this.legs.forEach((l) => {
      const { price } = bookForExit(l);
      this.state.set(this._key(l), { mode: 'MARKET', limit: price });
    });
    this.phase = 'ticket';
    this.reason = 'Manual';
    this.note = '';
    this.result = null;
    this.error = null;
    this.refused = [];
    this.pending = [];
    this.doneLegs = [];
    this.isOpen = true;
    if (typeof document !== 'undefined' && document.addEventListener && !this._onKey) {
      this._onKey = (e) => {
        if (e && e.key === 'Escape' && this.phase === 'ticket') this.close();
      };
      document.addEventListener('keydown', this._onKey);
    }
    this.render();
  }

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    if (this._onKey && typeof document !== 'undefined' && document.removeEventListener) {
      document.removeEventListener('keydown', this._onKey);
    }
    this._onKey = null;
    this.state.clear();
    if (this.host) this.host.innerHTML = '';
    if (this.options.onClose) this.options.onClose();
  }

  destroy() { this.close(); }

  /** The desk re-read the position. Market legs follow; a limit he typed is his. */
  update(position) {
    if (!this.isOpen || !position) return;
    if (String(position.position_id) !== String(this.position.position_id)) return;
    this.position = position;
    const fresh = new Map(
      (position.legs || []).map((l) => [this._key(l), l]),
    );
    this.legs = this.legs.map((l) => fresh.get(this._key(l)) || l);
    if (this.phase === 'ticket') this.render();
  }

  // ---------------------------------------------------------------- state

  _key(l) { return `${l.sequence}-${l.strike}-${l.option_type}`; }
  _st(l) { return this.state.get(this._key(l)); }

  marketBlock() {
    const s = this.position && this.position.market_state;
    if (s === 'closing') {
      return 'The market is closed, so nothing can fill. Exit it in your window, 1 to 2:30.';
    }
    if (s === 'unavailable') {
      return 'No live data, so nothing can fill. Check the data-health strip; if it names the token, refresh it.';
    }
    return null;
  }

  /**
   * The three figures, summed over the legs on this ticket, straight from the
   * server. Any leg the server could not mark makes the total unavailable
   * rather than a partial sum that looks whole.
   */
  totals() {
    let gross = 0;
    let chargesIn = 0;
    let chargesOut = 0;
    let known = true;
    const away = [];
    this.legs.forEach((l) => {
      const f = previewExit(l, this._st(l));
      if (f.away) away.push(l);
      if (!isNum(l.leg_pnl_inr) || !isNum(l.entry_charges_inr) || !isNum(l.exit_charges_now_inr)) {
        known = false;
        return;
      }
      gross += l.leg_pnl_inr;
      chargesIn += l.entry_charges_inr;
      chargesOut += l.exit_charges_now_inr;
    });
    return {
      gross: known ? gross : null,
      chargesIn: known ? chargesIn : null,
      chargesOut: known ? chargesOut : null,
      net: known ? gross - chargesIn - chargesOut : null,
      away,
    };
  }

  // -------------------------------------------------------------- actions

  setMode(index, mode) {
    const st = this._st(this.legs[index]);
    st.mode = mode === 'LIMIT' ? 'LIMIT' : 'MARKET';
    if (st.mode === 'LIMIT' && !isNum(st.limit)) st.limit = bookForExit(this.legs[index]).price;
    this.render();
  }

  setLimit(index, value) {
    const st = this._st(this.legs[index]);
    const v = parseFloat(value);
    st.limit = Number.isFinite(v) && v > 0 ? Math.round(v * 20) / 20 : null;
    this.render({ keepFocus: `[data-xlimit="${index}"]` });
  }

  resetPrice(index) {
    const st = this._st(this.legs[index]);
    st.limit = bookForExit(this.legs[index]).price;
    this.render();
  }

  payloadFor(leg) {
    const st = this._st(leg);
    return {
      order_type: st.mode,
      limit_price: st.mode === 'LIMIT' ? st.limit : null,
      close_reason: this.reason.toLowerCase().replace(/\s+/g, '_'),
      notes: this.note || null,
    };
  }

  /** Every open leg, as the whole-trade close wants them. */
  closePayload() {
    return {
      close_reason: this.reason.toLowerCase().replace(/\s+/g, '_'),
      notes: this.note || null,
      exit_legs: this.legs.map((l) => {
        const st = this._st(l);
        return {
          strike: l.strike,
          option_type: l.option_type,
          order_type: st.mode,
          limit_price: st.mode === 'LIMIT' ? st.limit : null,
        };
      }),
    };
  }

  async sendAll() {
    if (this.phase !== 'ticket' || this.marketBlock()) return;
    this.phase = 'sending';
    this.error = null;
    this.refused = [];
    this.render();
    try {
      // One leg on the ticket is a leg exit; the whole trade is a close.
      this.result = this.legs.length === 1 && this.only !== null
        ? await this.options.onExitLeg(this.legs[0].sequence, this.payloadFor(this.legs[0]))
        : await this.options.onExitAll(this.closePayload());
      this.phase = 'done';
    } catch (err) {
      this._fail(err);
    }
    this.render();
  }

  async sendOneByOne() {
    if (this.phase !== 'ticket' || this.marketBlock()) return;
    this.pending = [...this.legs];
    this.doneLegs = [];
    this.phase = 'walking';
    this.error = null;
    this.refused = [];
    this.render();
  }

  async sendNext() {
    if (this.phase !== 'walking' || !this.pending.length) return;
    const leg = this.pending[0];
    this.phase = 'sending';
    this.render();
    try {
      const res = await this.options.onExitLeg(leg.sequence, this.payloadFor(leg));
      this.doneLegs.push({ leg, res });
      this.pending = this.pending.slice(1);
      this.result = res;
      this.phase = this.pending.length && !res.last_leg ? 'walking' : 'done';
    } catch (err) {
      this._fail(err, { resumable: true });
    }
    this.render();
  }

  stopHere() {
    if (this.phase !== 'walking') return;
    this.pending = [];
    this.phase = this.doneLegs.length ? 'done' : 'ticket';
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
    this.phase = opts.resumable && this.doneLegs.length ? 'walking' : 'ticket';
  }

  // --------------------------------------------------------------- render

  render(opts = {}) {
    if (!this.host || !this.isOpen) return;
    let body;
    if (this.phase === 'ticket') body = this._ticket();
    else if (this.phase === 'sending') body = this._progress('Sending…');
    else if (this.phase === 'walking') body = this._progress(null);
    else body = this._done();
    this.host.innerHTML = `<div class="xt-backdrop" data-x="backdrop"><div class="xt xt2 sw-desk" role="dialog" aria-modal="true" aria-label="Exit ticket">${body}</div></div>`;
    this._bind();
    if (opts.keepFocus) {
      const el = this.host.querySelector(opts.keepFocus);
      if (el && el.focus) {
        el.focus();
        // Only a text-like input has a selection. A number input throws.
        try {
          if (el.type !== 'number' && el.setSelectionRange && el.value) {
            el.setSelectionRange(el.value.length, el.value.length);
          }
        } catch (_) {
          /* the caret is a convenience, never a reason to break the ticket */
        }
      }
    }
  }

  _header(title, sub) {
    const p = this.position || {};
    const live = p.market_state === 'live';
    const chip = live
      ? `<span class="chip c-live">LIVE · ${escapeHtml(istTime(p.read_at) || '')}</span>`
      : `<span class="chip c-na">${escapeHtml(p.market_state === 'unavailable' ? 'NO LIVE DATA' : `AT THE CLOSE${p.read_at ? ` · BOOK READ ${istTime(p.read_at, false)}` : ''}`)}</span>`;
    return `<header class="xt-h"><div><h2>${escapeHtml(title)}</h2><div class="sub">${escapeHtml(sub)}</div></div>
      <div class="r">${chip}${this.phase === 'ticket' ? '<button class="btn sm" type="button" data-x="close">Back</button>' : ''}</div></header>`;
  }

  _ticket() {
    const p = this.position || {};
    const t = this.totals();
    const shut = this.marketBlock();
    const rows = this.legs.map((l, i) => {
      const st = this._st(l);
      const f = previewExit(l, st);
      const side = exitSideOf(l.direction);
      const book = bookForExit(l);
      const showMoney = f.ok;
      const net = isNum(l.leg_pnl_inr) && isNum(l.entry_charges_inr) && isNum(l.exit_charges_now_inr)
        ? l.leg_pnl_inr - l.entry_charges_inr - l.exit_charges_now_inr
        : null;
      return `<div class="xt-row" data-i="${i}">
        <div class="seq"><b>${i + 1}</b></div>
        <div><span class="bs ${side === 'buy' ? 'B' : 'S'}">${side === 'buy' ? 'BUY' : 'SELL'}</span></div>
        <div class="contract">${escapeHtml(legName(l))}<small>${l.quantity_lots || 1} lot${(l.quantity_lots || 1) > 1 ? 's' : ''} · ${escapeHtml(l.expiry_date || p.expiry_date || '')}</small></div>
        <div class="n">${px(l.entry_premium)}</div>
        <div class="seg" role="group" aria-label="Order type">
          <button type="button" data-x="mode" data-mode="MARKET" data-i="${i}" aria-pressed="${st.mode === 'MARKET'}">Market</button>
          <button type="button" data-x="mode" data-mode="LIMIT" data-i="${i}" aria-pressed="${st.mode === 'LIMIT'}">Limit</button>
        </div>
        <div class="price">
          <input type="number" step="0.05" inputmode="decimal" data-xlimit="${i}" aria-label="Exit price"
                 value="${st.mode === 'LIMIT' ? (isNum(st.limit) ? st.limit.toFixed(2) : '') : px(book.price)}"
                 ${st.mode === 'MARKET' ? 'disabled' : ''}>
          <button class="btn sm" type="button" data-x="reset" data-i="${i}" ${st.mode === 'MARKET' ? 'disabled' : ''} title="Put the live quote back">${RESET_ICON} Reset</button>
          <div class="quote">bid <b>${px(l.bid)}</b> · ask <b>${px(l.ask)}</b>${isNum(l.current_ltp) ? `<br>traded <b>${px(l.current_ltp)}</b>` : ''}</div>
        </div>
        <div class="fillnote ${f.ok ? 'ok' : f.away ? 'away' : 'no'}">${escapeHtml(f.how)}</div>
        <div class="n big-n ${showMoney && isNum(l.leg_pnl_inr) ? (l.leg_pnl_inr >= 0 ? 'up' : 'down') : ''}">${showMoney ? orNA(signed(l.leg_pnl_inr)) : '—'}</div>
        <div class="n">${showMoney ? orNA(inrExact(l.entry_charges_inr)) : '—'}</div>
        <div class="n">${showMoney ? orNA(inrExact(l.exit_charges_now_inr)) : '—'}</div>
        <div class="n big-n ${showMoney && isNum(net) ? (net >= 0 ? 'up' : 'down') : ''}">${showMoney ? orNA(signed(net)) : '—'}</div>
      </div>`;
    }).join('');

    const shareOfGross = isNum(t.gross) && t.gross > 0 && isNum(t.chargesIn) && isNum(t.chargesOut)
      ? `${Math.round(((t.chargesIn + t.chargesOut) / t.gross) * 100)}%`
      : null;

    const refusedHtml = this.refused.length
      ? `<div class="xt-refused"><b>${escapeHtml(this.error || 'Nothing was sent.')}</b><ul>${this.refused.map((r) => `<li><b>${escapeHtml(r.leg)}</b> · ${escapeHtml(r.reason)}</li>`).join('')}</ul></div>`
      : this.error ? `<div class="xt-refused"><b>Not exited.</b> ${escapeHtml(this.error)}</div>` : '';

    const awayHtml = t.away.length
      ? `<div class="xt-pricenote">
          <span class="chip c-your">your price, not a rule</span>
          <span>${escapeHtml(t.away.map((l) => legName(l)).join(', '))} ${t.away.length === 1 ? 'is' : 'are'} away from the book, so ${t.away.length === 1 ? 'it' : 'they'} would not fill now and the send is refused.
          Resting orders arrive in the next build. For now move the price, press Reset, or switch ${t.away.length === 1 ? 'it' : 'them'} to market.</span>
        </div>`
      : '';

    const only = this.only !== null;
    const heldDays = isNum(p.days_held) ? `${p.days_held} day${p.days_held === 1 ? '' : 's'}` : null;

    return this._header(
      only ? 'Exit this leg' : 'Exit ticket',
      `${p.strategy_name || 'Trade'} · #${String(p.position_id || '').slice(0, 8)} · ${this.legs.length} leg${this.legs.length === 1 ? '' : 's'} · ${only ? 'the trade stays open behind it' : 'squares off the whole trade'}`,
    ) +
      refusedHtml +
      `<div class="xt-legs">
        <div class="xt-row h"><span>Order</span><span>Send</span><span>Leg</span><span class="n">Entry</span><span>Type</span><span>Exit price</span><span>Fill</span><span class="n">Gross</span><span class="n">Charges in</span><span class="n">Charges out</span><span class="n">Net</span></div>
        ${rows}
      </div>
      ${awayHtml}
      <div class="xt-foot">
        <div class="kv">
          <span>Gross at these exits</span><b class="${isNum(t.gross) ? (t.gross >= 0 ? 'up' : 'down') : ''}">${orNA(signed(t.gross), p.error)}</b>
          <span>Charges in, already paid, from the legs</span><b>${orNA(inrExact(t.chargesIn))}</b>
          <span>Charges out, per leg, at these prices</span><b>${orNA(inrExact(t.chargesOut))}</b>
          <span>Net, before you press</span><b class="hero ${isNum(t.net) ? (t.net >= 0 ? 'up' : 'down') : ''}">${orNA(signed(t.net), p.error)}</b>
          <span>Charges as a share of gross</span><b class="amber">${orNA(shareOfGross)}</b>
        </div>
        <div class="kv">
          <span>Close reason</span><b><select data-x="reason" aria-label="Close reason">${['Manual', 'Target hit', 'Stop hit', 'Time exit'].map((r) => `<option ${r === this.reason ? 'selected' : ''}>${r}</option>`).join('')}</select></b>
          <span>Note for the record</span><b><input type="text" data-x="note" value="${escapeHtml(this.note)}" placeholder="one line, in your words" aria-label="Note for the record"></b>
          <span>Held</span><b>${orNA(heldDays)}</b>
          <span>Result</span><b class="quiet">${only ? 'books on this leg; the trade stays open' : 'one row, recorded once'}</b>
        </div>
      </div>
      <div class="xt-actions">
        <button class="btn pri" type="button" data-x="send-all" ${shut || t.away.length ? 'disabled' : ''}>${only ? 'Exit this leg' : `Exit all ${this.legs.length} legs`}</button>
        ${only ? '' : `<button class="btn" type="button" data-x="send-one" ${shut || t.away.length ? 'disabled' : ''}>Exit one by one</button>`}
        <span class="why">${shut
          ? escapeHtml(shut)
          : t.away.length
            ? 'your price, not a rule · move it, press Reset, or switch to market'
            : 'one press, one result · a second press cannot record it twice · what you bought is sold at the bid, what you sold is bought back at the ask'}</span>
      </div>`;
  }

  _progress(sendingText) {
    const next = this.pending[0];
    const walking = this.phase === 'walking';
    const done = this.doneLegs.map(({ leg, res }) => {
      const f = (res && res.fill) || {};
      return `<li><span class="st">EXITED</span><div><span class="bs ${String(f.direction) === 'BUY' ? 'B' : 'S'}">${escapeHtml(String(f.direction || ''))}</span> &nbsp;<b>${escapeHtml(legName(leg))}</b>
        <small>${escapeHtml(f.how || '')}${isNum(f.exit_charges_inr) ? ` · charges ${inrExact(f.exit_charges_inr)}` : ''}</small></div>
        <b class="num ${isNum(f.net_pnl_inr) && f.net_pnl_inr >= 0 ? 'up' : 'down'}">${orNA(signed(f.net_pnl_inr))}</b></li>`;
    }).join('');
    const waiting = this.pending.map((l) => `<li><span class="st wait">WAITING</span><div><b>${escapeHtml(legName(l))}</b><small>not sent yet</small></div><b class="num na">—</b></li>`).join('');
    return this._header(
      sendingText || `${this.doneLegs.length} of ${this.doneLegs.length + this.pending.length} legs are out. The next one waits for you.`,
      walking ? 'One by one: each leg goes when you press, and the trade stays the same trade throughout.' : 'nothing else is sent until this answers',
    ) +
      (this.error ? `<div class="xt-refused"><b>The last leg was not sent.</b> ${escapeHtml(this.error)}${this.refused.map((r) => ` ${escapeHtml(r.reason)}`).join('')}</div>` : '') +
      `<div class="xt-fills"><ul class="fills">${done}${waiting}</ul></div>
      <div class="xt-actions">
        ${walking && next ? `<button class="btn pri" type="button" data-x="send-next">Exit ${escapeHtml(legName(next))}</button>
          <button class="btn" type="button" data-x="stop">Stop here</button>` : '<span class="why">sending…</span>'}
      </div>`;
  }

  _done() {
    const r = this.result || {};
    const closed = r.last_leg === true || r.status === 'closed';
    const net = isNum(r.realized_pnl_inr) ? r.realized_pnl_inr : (r.fill && r.fill.net_pnl_inr);
    const legs = this.doneLegs.length
      ? this.doneLegs
      : (r.fill ? [{ leg: { strike: r.fill.strike, option_type: r.fill.option_type }, res: r }] : []);
    const lines = legs.map(({ leg, res }) => {
      const f = (res && res.fill) || {};
      return `<li><span class="st">EXITED</span><div><b>${escapeHtml(legName(leg))}</b>
        <small>${escapeHtml(f.how || '')}${isNum(f.exit_charges_inr) ? ` · charges ${inrExact(f.exit_charges_inr)}` : ''}</small></div>
        <b class="num ${isNum(f.net_pnl_inr) && f.net_pnl_inr >= 0 ? 'up' : 'down'}">${orNA(signed(f.net_pnl_inr))}</b></li>`;
    }).join('');
    return this._header(
      closed ? 'The trade is closed and its result is in the record.' : 'That leg is out. The trade is still running.',
      escapeHtml(r.message || ''),
    ) +
      `<div class="xt-fills"><ul class="fills">${lines}</ul></div>
      <div class="xt-foot">
        <div class="kv">
          <span>${closed ? 'Net for the whole trade' : 'Net booked on this leg'}</span><b class="hero ${isNum(net) && net >= 0 ? 'up' : 'down'}">${orNA(signed(net))}</b>
          <span>Charges on the round trip</span><b>${orNA(inrExact(r.total_charges_inr))}</b>
          <span>${closed ? 'Legs closed' : 'Legs still open'}</span><b>${orNA(num(closed ? r.legs_closed : r.legs_open))}</b>
          <span>The note</span><b class="quiet">${escapeHtml(r.journal_status === 'written' ? 'written into your vault' : r.journal_status === 'pending' ? 'queued for your vault; the drainer writes it from your PC' : r.journal_status === 'failed' ? 'could not be written or queued' : '—')}</b>
        </div>
      </div>
      <div class="xt-actions">
        <button class="btn pri" type="button" data-x="finish">Back to the desk</button>
      </div>`;
  }

  _bind() {
    const root = this.host && this.host.querySelector ? this.host.querySelector('[data-x="backdrop"]') : null;
    if (!root || !root.addEventListener) return;
    root.addEventListener('click', (e) => {
      const t = e && e.target && e.target.closest ? e.target.closest('[data-x]') : null;
      if (!t) return;
      const act = t.getAttribute('data-x');
      const i = Number(t.getAttribute('data-i'));
      // A click on the dark area does nothing. Money deserves a deliberate button.
      if (act === 'backdrop') return;
      if (act === 'close') this.close();
      else if (act === 'mode') this.setMode(i, t.getAttribute('data-mode'));
      else if (act === 'reset') this.resetPrice(i);
      else if (act === 'send-all') this.sendAll();
      else if (act === 'send-one') this.sendOneByOne();
      else if (act === 'send-next') this.sendNext();
      else if (act === 'stop') this.stopHere();
      else if (act === 'finish') {
        const r = this.result;
        this.close();
        if (this.options.onDone) this.options.onDone(r);
      }
    });
    root.addEventListener('change', (e) => {
      const t = e && e.target;
      if (!t || !t.getAttribute) return;
      if (t.getAttribute('data-xlimit') !== null) this.setLimit(Number(t.getAttribute('data-xlimit')), t.value);
      else if (t.getAttribute('data-x') === 'reason') this.reason = t.value;
      else if (t.getAttribute('data-x') === 'note') this.note = t.value;
    });
    root.addEventListener('input', (e) => {
      const t = e && e.target;
      if (t && t.getAttribute && t.getAttribute('data-x') === 'note') this.note = t.value;
    });
  }
}

/** A signed rupee figure, or null so `orNA` can say unavailable. */
/** A signed rupee figure, to the paisa. Charges are the point of this screen. */
function signed(v) {
  if (!isNum(v)) return null;
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${inrExact(Math.abs(v))}`;
}

// A proper Reset: an icon AND the word, never a bare round arrow. His words,
// 2026-09-09: "No cheap round circle for reset, a proper reset button."
const RESET_ICON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" focusable="false"><path d="M3 8a5 5 0 1 0 1.5-3.6M3 2.5v3h3"/></svg>';

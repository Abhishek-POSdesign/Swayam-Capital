/**
 * THE TARGETS MODAL. What he wants this trade to tell him, and nothing else.
 *
 * His words, 2026-09-10: "My preference is to add a target for each leg.
 * Target always means both loss and profit... In case I cannot add profit and
 * loss for each leg, I have to add it for the whole trade."
 *
 * And why it is a modal rather than more columns on the card: "I don't want
 * unnecessary things lying on my position page." So the card keeps one small
 * sage button, and everything about targets lives behind it.
 *
 * WHAT A BOX MEANS
 * ----------------
 * A leg's two boxes are PRICES of that option. The row beside them says what
 * that price is worth in rupees on that leg, computed from the same entry fill
 * and lot size the rest of the desk uses, so he can set a price and read the
 * money without doing the arithmetic himself.
 *
 * The trade's two boxes are RUPEES, net of charges both ways.
 *
 * A BLANK BOX IS SILENCE. It is never zero and never a number the terminal
 * picked, because a number the terminal picked is a plan he did not make. The
 * one exception is a blank trade loss, which falls back to rule 1 read live,
 * and the row says so in words.
 *
 * NOTHING HERE TRADES. Saving a target moves no order, no fill and no charge.
 * A reached target lights Home up and waits for him.
 *
 * The money is NOT recomputed in the browser for anything the server already
 * knows. `pnlAt` is the one exception, and it exists only so a box he is
 * typing into can answer "and that is worth how much?" before he saves.
 */

import { inr, num, escapeHtml } from '../utils/display.js';

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

/** `23,800 CE`, the way he names a leg out loud. */
export function legLabel(leg) {
  if (!leg) return 'leg';
  const strike = isNum(Number(leg.strike)) ? Number(leg.strike) : null;
  const kind = String(leg.option_type || leg.type || '').toUpperCase();
  if (strike === null) return kind || 'leg';
  return `${num(strike, 0)} ${kind}`.trim();
}

export function isBuy(leg) {
  return ['BUY', 'B', 'LONG'].includes(String(leg && (leg.direction || leg.side) || '').toUpperCase());
}

/**
 * How many contracts a leg is, from what the server stored on it.
 *
 * Lots times the lot size, which is exactly how `_value_one_position` counts
 * them, so this figure and the leg's own profit agree. THE LOT SIZE IS NEVER
 * ASSUMED. It moved from 75 to 65 in January 2026 and a hardcoded fallback
 * here would quietly misprice every leg he ever set a target on, so a leg
 * without a stored lot size gets no answer at all.
 */
export function unitsOf(leg) {
  if (!leg) return null;
  const lots = Number(leg.quantity_lots ?? 1);
  const size = Number(leg.lot_size);
  if (!Number.isFinite(size) || size <= 0) return null;
  if (!Number.isFinite(lots) || lots <= 0) return null;
  return lots * size;
}

/**
 * What one leg would book, gross, if its price were `price`.
 *
 * Bought: (price - entry) x units. Sold: (entry - price) x units. The units
 * come from the leg as the server stored them; without them there is no answer
 * and this returns null rather than a figure computed from an assumed lot.
 */
export function pnlAt(leg, price) {
  if (!leg || !isNum(price)) return null;
  const entry = Number(leg.entry_premium);
  const units = unitsOf(leg);
  if (!Number.isFinite(entry) || units === null) return null;
  return isBuy(leg) ? (price - entry) * units : (entry - price) * units;
}

/**
 * A target that could never fire, named in one short line, or null.
 *
 * HIS REPORT, 2026-09-11: the box took a number on the wrong side of the entry
 * and saved it. It then sat on the trade looking like a plan he had made,
 * while the only price that could ever reach it was one that meant the
 * opposite of what he wanted.
 *
 *     a BOUGHT leg   take profit ABOVE entry, cut loss BELOW entry
 *     a SOLD leg     take profit BELOW entry, cut loss ABOVE entry
 *
 * EQUAL TO THE ENTRY IS FINE: that is a break-even exit, a real thing to want.
 * A leg with no stored entry is not judged, because there is nothing to be on
 * the wrong side of.
 *
 * THE RULE ALSO LIVES ON THE SERVER, in services/targets.py
 * `wrong_side_of_entry`, and that is the one that actually protects the
 * record: this copy exists only so the answer appears under his fingers as he
 * types rather than after a round trip. If the two ever disagree, the server
 * is right.
 */
export function wrongSide(leg, takeText, cutText) {
  if (!leg) return null;
  const entry = Number(leg.entry_premium);
  if (!isNum(entry)) return null;
  const buy = isBuy(leg);
  const px = (v) => num(v, 2);

  const read = (text) => {
    const t = String(text ?? '').trim();
    if (!t) return null;
    const v = Number(t);
    return isNum(v) && v !== 0 ? v : null;
  };
  const take = read(takeText);
  const cut = read(cutText);

  if (take !== null) {
    if (buy && take < entry) return `take profit must be above your entry of ${px(entry)}`;
    if (!buy && take > entry) return `you sold this: take profit must be below your entry of ${px(entry)}`;
  }
  if (cut !== null) {
    if (buy && cut > entry) return `cut loss must be below your entry of ${px(entry)}`;
    if (!buy && cut < entry) return `you sold this: cut loss must be above your entry of ${px(entry)}`;
  }
  return null;
}

export class TargetsModal {
  /**
   * @param {HTMLElement} host Where the modal mounts.
   * @param {object} options
   *   onSave(positionId, payload) -> Promise<result>
   *   onClose()
   */
  constructor(host, options = {}) {
    this.host = host;
    this.options = options;
    this.isOpen = false;
    this.position = null;
    this.legs = [];
    this.draft = new Map();   // sequence -> { take: string, cut: string }
    this.tradeProfit = '';
    this.tradeLoss = '';
    this.busy = false;
    this.error = null;
    this.saved = null;
    this._onKey = null;
  }

  /** @param {object} position a row from /api/positions/live */
  open(position) {
    if (!position) return;
    this.position = position;
    this.legs = (position.legs || []).filter((l) => String(l.status || 'open') !== 'closed');
    this.draft = new Map();
    for (const leg of this.legs) {
      this.draft.set(String(leg.sequence), {
        take: isNum(Number(leg.target_price)) && leg.target_price !== null ? String(leg.target_price) : '',
        cut: isNum(Number(leg.stop_price)) && leg.stop_price !== null ? String(leg.stop_price) : '',
      });
    }
    const t = position.targets || {};
    this.tradeProfit = isNum(t.target_profit_inr) ? String(t.target_profit_inr) : '';
    this.tradeLoss = isNum(t.target_loss_inr) ? String(t.target_loss_inr) : '';
    this.busy = false;
    this.error = null;
    this.saved = null;
    this.isOpen = true;
    if (typeof document !== 'undefined' && document.addEventListener && !this._onKey) {
      this._onKey = (e) => { if (e && e.key === 'Escape' && !this.busy) this.close(); };
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
    if (this.host) this.host.innerHTML = '';
    if (this.options.onClose) this.options.onClose();
  }

  destroy() { this.close(); }

  // ----------------------------------------------------------------- state

  /**
   * One box changed. Kept as the TEXT he typed, so an empty box stays empty
   * and a half-typed "1" does not become the number one on the screen beside
   * it. It is turned into a number only on save.
   */
  setLeg(sequence, which, value) {
    const key = String(sequence);
    const row = this.draft.get(key) || { take: '', cut: '' };
    row[which] = String(value ?? '');
    this.draft.set(key, row);
  }

  setTrade(which, value) {
    if (which === 'profit') this.tradeProfit = String(value ?? '');
    else this.tradeLoss = String(value ?? '');
  }

  clearAll() {
    for (const key of this.draft.keys()) this.draft.set(key, { take: '', cut: '' });
    this.tradeProfit = '';
    this.tradeLoss = '';
    this.render();
  }

  /**
   * Every leg whose boxes are on the wrong side of its entry, with the reason.
   *
   * Nothing is sent while this is not empty, so a target that could never fire
   * never reaches the record in the first place.
   */
  wrongSideLegs() {
    const out = [];
    for (const leg of this.legs) {
      const row = this.draft.get(String(leg.sequence)) || { take: '', cut: '' };
      const why = wrongSide(leg, row.take, row.cut);
      if (why) out.push({ sequence: leg.sequence, label: legLabel(leg), why });
    }
    return out;
  }

  /** What goes to the server. A blank box becomes null, which clears it. */
  payload() {
    const level = (text) => {
      const trimmed = String(text ?? '').trim();
      if (!trimmed) return null;
      const n = Number(trimmed);
      if (!Number.isFinite(n) || n === 0) return null;
      return n;
    };
    return {
      legs: this.legs.map((leg) => {
        const row = this.draft.get(String(leg.sequence)) || { take: '', cut: '' };
        return {
          sequence: Number(leg.sequence),
          target_price: level(row.take),
          stop_price: level(row.cut),
        };
      }),
      target_profit_inr: level(this.tradeProfit),
      target_loss_inr: level(this.tradeLoss),
    };
  }

  async save() {
    if (this.busy || !this.position) return;
    // A target on the wrong side of the entry never leaves this screen. The
    // server refuses it too, but he should not have to press Save to find out.
    const wrong = this.wrongSideLegs();
    if (wrong.length) {
      this.error = wrong.map((w) => `${w.label}: ${w.why}.`).join(' ');
      this.saved = null;
      this.render();
      return;
    }
    this.busy = true;
    this.error = null;
    this.render();
    try {
      const res = await this.options.onSave(this.position.position_id, this.payload());
      this.saved = (res && res.message) || 'Targets saved.';
      this.busy = false;
      this.render();
    } catch (err) {
      // His rule: a refusal on his screen says what he can DO.
      this.error = (err && err.message) || String(err);
      this.busy = false;
      this.render();
    }
  }

  // ---------------------------------------------------------------- paint

  _legRow(leg) {
    const row = this.draft.get(String(leg.sequence)) || { take: '', cut: '' };
    const buy = isBuy(leg);
    const takeMoney = pnlAt(leg, Number(row.take));
    const cutMoney = pnlAt(leg, Number(row.cut));
    const side = leg.mark_side ? ` at the ${escapeHtml(leg.mark_side)}` : '';
    const means = this._means(leg, row);
    const why = wrongSide(leg, row.take, row.cut);

    return `<tr class="${why ? 'tg-wrong' : ''}">
      <td><span class="bs ${buy ? 'B' : 'S'}">${buy ? 'BUY' : 'SELL'}</span>
        <b class="num tg-leg">${escapeHtml(legLabel(leg))}</b></td>
      <td class="n">${isNum(Number(leg.entry_premium)) ? escapeHtml(num(Number(leg.entry_premium), 2)) : '<span class="na">—</span>'}</td>
      <td class="n">${isNum(leg.mark) ? escapeHtml(num(leg.mark, 2)) : '<span class="na">—</span>'}<small>${side.trim()}</small></td>
      <td class="n"><input type="number" step="0.05" min="0" value="${escapeHtml(row.take)}" placeholder="—"
        data-tgt="take" data-seq="${escapeHtml(String(leg.sequence))}"
        aria-label="Take profit price for ${escapeHtml(legLabel(leg))}"></td>
      <td class="n"><input type="number" step="0.05" min="0" value="${escapeHtml(row.cut)}" placeholder="—"
        data-tgt="cut" data-seq="${escapeHtml(String(leg.sequence))}"
        aria-label="Cut loss price for ${escapeHtml(legLabel(leg))}"></td>
      <td class="tg-means">${means}</td>
    </tr>`;
  }

  /**
   * The Means cell for one leg: what each box is worth in rupees, or the one
   * line saying the box is on a side that could never be reached.
   *
   * Shared by the first paint and by the repaint that follows his typing, so
   * the two can never drift apart.
   */
  _means(leg, row) {
    const why = wrongSide(leg, row.take, row.cut);
    if (why) return `<span class="tg-why">${escapeHtml(why)}</span>`;
    const takeMoney = pnlAt(leg, Number(row.take));
    const cutMoney = pnlAt(leg, Number(row.cut));
    return [
      row.take.trim() && isNum(takeMoney)
        ? `<span class="${takeMoney < 0 ? 'down' : 'up'}">${escapeHtml(inr(takeMoney))}</span> on this leg`
        : '<span class="na">no profit signal</span>',
      row.cut.trim() && isNum(cutMoney)
        ? `<span class="${cutMoney < 0 ? 'down' : 'up'}">${escapeHtml(inr(cutMoney))}</span> on this leg`
        : '<span class="na">no loss signal</span>',
    ].join('<br>');
  }

  _tradeRow() {
    const p = this.position || {};
    const t = p.targets || {};
    const net = p.net_if_exit_now_inr;
    const capText = isNum(t.effective_loss_inr) && t.loss_source === 'rule1'
      ? `blank loss box falls back to rule 1, ${escapeHtml(inr(t.effective_loss_inr))}`
      : isNum(p.rule1_cap_inr)
        ? `blank loss box falls back to rule 1, ${escapeHtml(inr(p.rule1_cap_inr))}`
        : '<span class="na">rule 1 is unavailable, so a blank loss box gives no signal</span>';
    const maxProfit = isNum(p.max_profit_inr) && p.max_profit_inr > 0
      ? `max profit of this structure is ${escapeHtml(inr(p.max_profit_inr))}`
      : '';

    return `<tr class="tg-trade">
      <td><b>The whole trade</b><small>rupees, net of charges</small></td>
      <td class="n"><span class="na">—</span></td>
      <td class="n ${isNum(net) ? (net < 0 ? 'down' : 'up') : ''}">${isNum(net) ? escapeHtml(inr(net)) : '<span class="na">—</span>'}</td>
      <td class="n"><input type="number" step="50" min="0" value="${escapeHtml(this.tradeProfit)}" placeholder="—"
        data-tgt="trade-profit" aria-label="Profit target for the whole trade"></td>
      <td class="n"><input type="number" step="50" min="0" value="${escapeHtml(this.tradeLoss)}" placeholder="—"
        data-tgt="trade-loss" aria-label="Loss limit for the whole trade"></td>
      <td class="tg-means">${capText}${maxProfit ? `<br>${maxProfit}` : ''}</td>
    </tr>`;
  }

  render() {
    if (!this.host) return;
    if (!this.isOpen || !this.position) { this.host.innerHTML = ''; return; }
    const p = this.position;
    const shortId = String(p.position_id || '').slice(0, 8);

    this.host.innerHTML = `<div class="tg-backdrop" data-tgt-backdrop="1">
      <div class="tg sw-desk" role="dialog" aria-modal="true" aria-label="Targets for this trade">
        <header class="tg-h">
          <h2>Targets · ${escapeHtml(p.strategy_name || 'Trade')} #${escapeHtml(shortId)}</h2>
          <span class="chip c-sage">profit and loss, both</span>
          <div class="r"><button class="btn sm" type="button" data-tgt-act="close">Close</button></div>
        </header>
        <div class="tg-hint">a leg's boxes are prices · the trade's are rupees, net of charges · a blank box is no signal</div>
        <div class="tw"><table class="tg-t">
          <thead><tr><th>Leg</th><th class="n">Entry</th><th class="n">Now</th>
            <th class="n">Take profit at</th><th class="n">Cut loss at</th><th>Means</th></tr></thead>
          <tbody>
            ${this.legs.map((l) => this._legRow(l)).join('')}
            ${this._tradeRow()}
          </tbody>
        </table></div>
        ${this.error ? `<div class="tg-refused"><b>Nothing was saved.</b> ${escapeHtml(this.error)}</div>` : ''}
        ${this.saved ? `<div class="tg-saved">${escapeHtml(this.saved)}</div>` : ''}
        <div class="tg-actions">
          <button class="btn pri" type="button" data-tgt-act="save" ${this.busy || this.wrongSideLegs().length ? 'disabled' : ''}>${this.busy ? 'Saving…' : 'Save targets'}</button>
          <button class="btn" type="button" data-tgt-act="clear" ${this.busy ? 'disabled' : ''}>Clear all</button>
          <span class="why">changes nothing about the order</span>
        </div>
      </div>
    </div>`;

    this._bind();
  }

  /**
   * A thin adapter onto `act`, exactly as the position area does it, because
   * the test DOM cannot deliver a delegated click and the DECISION is what the
   * tests exercise.
   */
  _bind() {
    const root = this.host;
    if (!root || !root.querySelectorAll) return;

    root.querySelectorAll('[data-tgt-act]').forEach((btn) => {
      btn.addEventListener('click', () => this.act(btn.getAttribute('data-tgt-act')));
    });
    root.querySelectorAll('input[data-tgt]').forEach((input) => {
      input.addEventListener('input', () => {
        const which = input.getAttribute('data-tgt');
        if (which === 'trade-profit') this.setTrade('profit', input.value);
        else if (which === 'trade-loss') this.setTrade('loss', input.value);
        else this.setLeg(input.getAttribute('data-seq'), which, input.value);
        this._repaintMeans();
      });
    });
    const backdrop = root.querySelector('[data-tgt-backdrop]');
    if (backdrop && backdrop.addEventListener) {
      backdrop.addEventListener('click', (e) => {
        if (e && e.target === backdrop && !this.busy) this.close();
      });
    }
  }

  /**
   * The "Means" column follows what he is typing, and NOTHING ELSE is
   * repainted, so the caret does not jump out of the box mid-number.
   */
  _repaintMeans() {
    const root = this.host;
    if (!root || !root.querySelectorAll) return;
    const cells = root.querySelectorAll('.tg-means');
    if (!cells || !cells.length) return;
    this.legs.forEach((leg, i) => {
      const cell = cells[i];
      if (!cell) return;
      const row = this.draft.get(String(leg.sequence)) || { take: '', cut: '' };
      cell.innerHTML = this._means(leg, row);
      // The row carries the amber while he is still typing, so the warning
      // arrives with the number rather than when he presses Save.
      const tr = cell.parentElement;
      if (tr && tr.classList) {
        tr.classList.toggle('tg-wrong', !!wrongSide(leg, row.take, row.cut));
      }
    });
    // Save cannot go while any box is on the wrong side.
    const save = root.querySelector('[data-tgt-act="save"]');
    if (save) save.disabled = this.busy || this.wrongSideLegs().length > 0;
  }

  /** Every button's work lives here, so a test can press it without a DOM. */
  act(action) {
    if (action === 'close') return this.close();
    if (action === 'clear') return this.clearAll();
    if (action === 'save') return this.save();
    return undefined;
  }
}

export default TargetsModal;

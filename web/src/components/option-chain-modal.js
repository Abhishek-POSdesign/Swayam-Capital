/**
 * The option chain, as a floating panel on the desk.
 *
 * Calls on the left, strikes down the middle, puts on the right. Per side, at
 * a glance: open interest with a bar so the walls are visible, the change in
 * open interest, and the price with the live book beneath it. Implied
 * volatility and volume are on hover, or as two more columns behind More.
 * Above the table, six figures: NIFTY with the at-the-money strike, max pain
 * WITH ITS EXPIRY and the other expiry's beside it, the put-call ratio, the
 * two open-interest totals, and how many times the rows have been refreshed
 * without moving his scroll.
 *
 * WHAT CHANGED, AND WHY. docs/builds/BUILD_04_OPTION_CHAIN.md, from his own
 * use of it against a live market on 2026-09-10.
 *
 *   THE SCROLL. `render()` used to assign innerHTML in full every five
 *   seconds, which replaced the scrolling container along with everything in
 *   it, so the strike he was reading vanished from under his eye. Painting is
 *   now two jobs: `_paint()` builds the panel and runs only when the shape
 *   changes, and `_update()` writes the changed CELLS in place and touches
 *   nothing else. His words: it fights his scroll. It no longer does.
 *
 *   A DEAD STRIKE. The 22,850 call showed a last trade of 1,575.95 in live
 *   ink against a real book of 670.95 to 705.40. Volume is the honest test of
 *   whether a price is today's: open interest survives from earlier sessions
 *   and a last trade survives for ever. A strike with no volume today says so,
 *   shows its real book, strikes through the stale trade, and cannot be added.
 *
 *   MAX PAIN. Home read 23,500 and the desk read 24,000. Both were right and
 *   neither said which expiry it belonged to. Every max pain on this screen
 *   now carries its expiry.
 *
 * Every number here came out of /api/option-chain or the cell says so, and
 * nothing says LIVE unless /api/market/data-health says the market is open.
 */

import { api } from '../api.js';
import { num, escapeHtml, istTime } from '../utils/display.js';

const REFRESH_MS = 5000;
const MORE_KEY = 'swayam-chain-more-figures';

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

function fmtChange(v) {
  if (!isNum(v)) return '';
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}`;
}

function fmtInt(v) {
  return isNum(v) ? num(v, 0) : null;
}

function fmtIv(v) {
  return isNum(v) && v > 0 ? `${(v * 100).toFixed(1)}%` : null;
}

/** Open interest in crores and lakhs, the way he reads it. */
export function compact(v) {
  if (!isNum(v)) return null;
  const a = Math.abs(v);
  if (a >= 1e7) return `${(v / 1e7).toFixed(2)} cr`;
  if (a >= 1e5) return `${(v / 1e5).toFixed(1)} L`;
  return num(v, 0);
}

/**
 * Whether this side of this strike has traded TODAY.
 *
 * Volume is the test, and it is the only honest one on this screen. Open
 * interest carries over from earlier sessions and a last traded price never
 * expires, so both can look alive on a contract nobody has touched today. On
 * 2026-09-10 that put a price of 1,575.95 in live ink beside a book of 670.95
 * to 705.40, and he nearly placed a strike against it.
 */
export function tradedToday(q) {
  return Boolean(q) && isNum(q.volume) && q.volume > 0;
}

/** A short label for an expiry: "15 Sep". */
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function expiryLabel(iso) {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
  if (!m) return String(iso);
  const month = MONTHS[Number(m[2]) - 1];
  if (!month) return String(iso);
  return `${Number(m[3])} ${month}`;
}

export class OptionChainModalComponent {
  constructor(host, options = {}) {
    this.host = host; // usually document.body
    this.options = options; // { onAddLeg, getExpiry, getSpot, getMarketState, refreshMs }
    this.refreshMs = options.refreshMs || REFRESH_MS;
    this.el = null;
    this.isOpen = false;
    this.data = null;
    this.error = null;
    this.loading = false;
    this._timer = null;
    this._onKey = null;
    this._drag = null;
    this._pos = null;

    /** The expiry the PANEL is showing. The desk keeps its own. */
    this.expiry = null;
    /** Every expiry the market offers, for the switcher. */
    this.expiries = [];
    /** The other expiry's max pain, read once rather than on every tick. */
    this.otherPain = null;
    /** More figures adds IV and volume as columns. Remembered per browser. */
    this.more = this._readMore();
    /** How many times the rows have been rewritten in place. */
    this.ticks = 0;
    /** The last cell values written, so a refresh knows what actually changed. */
    this._cells = new Map();
    /** The strikes the table was built for. A change of shape forces a repaint. */
    this._shape = null;
  }

  _readMore() {
    try {
      return window.localStorage.getItem(MORE_KEY) === 'yes';
    } catch (_) {
      return false;
    }
  }

  _writeMore() {
    try {
      window.localStorage.setItem(MORE_KEY, this.more ? 'yes' : 'no');
    } catch (_) {
      /* a browser with storage off still works, it just forgets */
    }
  }

  // ------------------------------------------------------------ lifecycle

  open() {
    if (this.isOpen) {
      this.refresh();
      return;
    }
    this.isOpen = true;
    this.ticks = 0;
    this._cells.clear();
    this._shape = null;
    this.expiry = this.options.getExpiry ? this.options.getExpiry() : null;
    this._mount();
    this._paint();
    this.refresh(true);
    this._loadExpiries();
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
    this._cells.clear();
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

  // ------------------------------------------------------------------ data

  async refresh(centre = false) {
    if (!this.isOpen || this.loading) return;
    const expiry = this.expiry || (this.options.getExpiry ? this.options.getExpiry() : null);
    if (!expiry) {
      this.error = 'No expiry is selected on the desk.';
      this._paint();
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

    // A CHANGE OF SHAPE IS THE ONLY THING THAT REPAINTS. Strikes appearing or
    // disappearing between reads means the table itself is different; anything
    // else is a number moving, and a number moving must never cost him his
    // place in the table.
    const shape = this._shapeOf();
    if (this.error || shape !== this._shape) {
      this._paint();
      if (centre || shape !== this._shape) this.centreOnAtm();
      this._shape = shape;
    } else {
      this.ticks += 1;
      this._update();
    }
  }

  _shapeOf() {
    const rows = (this.data && this.data.strikes) || [];
    return `${this.expiry}|${this.more ? 'more' : 'few'}|${rows.map((r) => r.strike).join(',')}`;
  }

  /**
   * EVERY expiry the market offers, nearest first, each with its badge.
   *
   * HIS REPORT, 2026-09-11: the switcher showed two dates. It took the one the
   * endpoint calls `weekly_expiry` and the one it calls `monthly_expiry` and
   * threw the rest away, so on a day like 10 September he was offered 15 Sep
   * and 29 Sep and could not reach 22 Sep at all -- which is exactly the far
   * leg a calendar spread needs. Ten of his twenty-one profitable swing trades
   * were calendars.
   *
   * THE BADGES, and why they are derived rather than read. The endpoint flags
   * exactly ONE row `is_weekly`, the nearest, and exactly ONE `is_monthly`,
   * this month's. Every other row arrives with neither flag, so a middle
   * expiry such as 22 Sep would show a blank badge.
   *
   * "Anything not flagged monthly is a weekly" was the first thing tried and
   * it is WRONG, caught on the running panel the same hour: it badged 27 Oct,
   * 23 Nov, 29 Dec and the 2027 quarterlies as weeklies. Those are monthly and
   * quarterly contracts. A wrong label is a fabricated figure wearing words.
   *
   * A monthly expiry is the LAST one of its calendar month, which is exactly
   * what the exchange means by it, and the list is every upcoming expiry so
   * the question can be answered from the list itself. The endpoint's own flag
   * still wins wherever it gives one.
   */
  async _loadExpiries() {
    try {
      const res = await api.getExpiries();
      const all = (res && res.expiries) || [];
      const monthly = res && res.monthly_expiry;
      const rows = all.filter((e) => e && e.date);
      // The last expiry in each calendar month, taken from the list itself.
      const lastOfMonth = new Set();
      const seen = new Map();
      rows.forEach((e) => seen.set(String(e.date).slice(0, 7), e.date));
      seen.forEach((date) => lastOfMonth.add(date));
      // The endpoint already returns them in date order and has already
      // dropped anything expired, so the order here is the order it gave.
      this.expiries = rows.map((e) => ({
        date: e.date,
        kind: (e.is_monthly || e.date === monthly || lastOfMonth.has(e.date)) ? 'monthly' : 'weekly',
        days: isNum(e.calendar_days) ? e.calendar_days : null,
      }));
      // If the desk is on none of them, the panel still shows what the desk
      // chose; the switcher just has nothing lit.
      this._loadOtherPain();
      this._paintChrome();
    } catch (_) {
      // The switcher is a convenience. Without it the panel still shows the
      // expiry the desk chose, which is what it did before.
      this.expiries = [];
    }
  }

  /**
   * The OTHER expiry's max pain, so the two numbers he saw sit on one screen
   * with their labels attached. Read once per expiry change, never on the
   * refresh tick: it is a second call to the broker and the figure moves
   * slowly.
   */
  async _loadOtherPain() {
    const other = this._otherExpiry();
    if (!other) {
      this.otherPain = null;
      return;
    }
    try {
      const res = await api.getOptionChain(other, 30);
      this.otherPain = { expiry: other, max_pain: res && res.max_pain };
    } catch (_) {
      this.otherPain = { expiry: other, max_pain: null };
    }
    this._paintChrome();
  }

  /**
   * The expiry whose max pain is shown BESIDE this one's.
   *
   * The comparison he asked for is the near against the monthly: he saw 23,500
   * on Home and 24,000 on the chain and neither said which it meant. So from
   * anywhere except the monthly, the monthly is the other one; standing ON the
   * monthly, the nearest expiry is. With every expiry now in the switcher, a
   * plain "first one that is not this one" would have compared 22 Sep against
   * 15 Sep and quietly dropped the monthly out of the picture.
   */
  _otherExpiry() {
    if (!this.expiries.length) return null;
    const here = this.expiry;
    const monthly = this.expiries.find((e) => e.kind === 'monthly');
    if (monthly && monthly.date !== here) return monthly.date;
    const nearest = this.expiries.find((e) => e.date !== here);
    return nearest ? nearest.date : null;
  }

  setExpiry(expiry) {
    if (!expiry || expiry === this.expiry) return;
    this.expiry = expiry;
    this.otherPain = null;
    this._cells.clear();
    this._shape = null;
    this.ticks = 0;
    this._paint();
    this.refresh(true);
    this._loadOtherPain();
  }

  toggleMore() {
    this.more = !this.more;
    this._writeMore();
    this._cells.clear();
    this._shape = this._shapeOf();
    this._paint();
    this.centreOnAtm();
  }

  // ---------------------------------------------------------------- reading

  atmStrike() {
    const d = this.data;
    if (d && isNum(d.atm_strike)) return d.atm_strike;
    const rows = (d && d.strikes) || [];
    const spot = this.spot();
    if (!spot || !rows.length) return null;
    return rows.reduce(
      (best, r) => (Math.abs(r.strike - spot) < Math.abs(best - spot) ? r.strike : best),
      rows[0].strike,
    );
  }

  spot() {
    const d = this.data;
    if (d && isNum(d.spot)) return d.spot;
    return this.options.getSpot ? this.options.getSpot() : null;
  }

  /** live | closing | delayed | unavailable, from the ONE clock. */
  marketState() {
    return this.options.getMarketState ? this.options.getMarketState() : null;
  }

  // ------------------------------------------------------------------ cells

  /**
   * The cells of one side of one strike, as [key, html] pairs.
   *
   * Building them as a list rather than a string is what lets the refresh
   * write only what changed: the key names the cell, and the html is compared
   * against what was written last time.
   */
  _sideCells(q, type, strike, maxOi) {
    const lower = type.toLowerCase();
    const alive = tradedToday(q);
    const ltp = q && isNum(q.ltp) ? q.ltp : null;
    const bid = q && isNum(q.bid) ? q.bid : null;
    const ask = q && isNum(q.ask) ? q.ask : null;
    const oi = q && isNum(q.oi) ? q.oi : null;
    const dOi = q && isNum(q.oi_change) ? q.oi_change : null;
    const vol = q && isNum(q.volume) ? q.volume : null;
    const iv = fmtIv(q && q.iv);
    const chg = q ? q.ltp_change_pct : null;
    const bar = oi !== null && maxOi > 0 ? Math.max(1, (oi / maxOi) * 100) : 0;

    const book = bid !== null || ask !== null
      ? `${bid === null ? '—' : num(bid, 2)} / ${ask === null ? '—' : num(ask, 2)}`
      : 'no book';
    const title = `IV ${iv || 'unavailable'} · volume ${vol === null ? 'unavailable' : num(vol, 0)} · book ${book}`;

    const price = alive
      ? `<b>${escapeHtml(ltp === null ? '—' : num(ltp, 2))}</b><small>${escapeHtml(book)}</small>`
      // NO TRADE TODAY. The book is real and is shown; the last trade is not
      // today's and is struck through so it cannot be mistaken for one.
      : `<em>no trade today</em><small>${escapeHtml(book)}</small>${
          ltp === null ? '' : `<s>last traded ${escapeHtml(num(ltp, 2))}, stale</s>`
        }`;

    const why = alive ? '' : 'No trade today. The book is shown; it cannot be added for a fill.';
    const disabled = alive ? '' : ` disabled title="${escapeHtml(why)}"`;

    const cells = [
      [`${lower}-act`, `<td class="act ${lower}"><div class="pair"><button type="button" class="ocbtn B" data-act="add" data-bs="B" data-strike="${strike}" data-type="${type}"${disabled}>Buy</button><button type="button" class="ocbtn S" data-act="add" data-bs="S" data-strike="${strike}" data-type="${type}"${disabled}>Sell</button></div></td>`],
      [`${lower}-oi`, `<td class="n oi ${lower}${alive ? '' : ' dead'}" title="${escapeHtml(title)}"><i class="bar ${lower}" style="width:${bar.toFixed(1)}%"></i><span>${oi === null ? '<span class="na">—</span>' : escapeHtml(compact(oi))}</span></td>`],
      [`${lower}-doi`, `<td class="n doi ${lower} ${dOi === null ? '' : dOi > 0 ? 'up' : dOi < 0 ? 'down' : ''}">${dOi === null ? '<span class="na">—</span>' : dOi === 0 ? '—' : escapeHtml(`${dOi > 0 ? '+' : '−'}${compact(Math.abs(dOi))}`)}</td>`],
    ];
    if (this.more) {
      cells.push([`${lower}-iv`, `<td class="n iv ${lower} muted">${iv === null ? '<span class="na">—</span>' : escapeHtml(iv)}</td>`]);
      cells.push([`${lower}-vol`, `<td class="n vol ${lower} muted">${vol === null ? '<span class="na">—</span>' : escapeHtml(compact(vol))}</td>`]);
    }
    cells.push([
      `${lower}-px`,
      `<td class="px ${lower}${alive ? '' : ' dead'}" title="${escapeHtml(title)}">${price}</td>`,
    ]);

    // Calls read left to right towards the strike; puts mirror them.
    return type === 'CE' ? cells : cells.slice().reverse();
  }

  _rowCells(r, atm, maxOi) {
    const isAtm = atm !== null && r.strike === atm;
    return [
      ...this._sideCells(r.ce, 'CE', r.strike, maxOi),
      ['strike', `<td class="strike">${escapeHtml(num(r.strike, 0))}${isAtm ? '<span class="pill">ATM</span>' : ''}</td>`],
      ...this._sideCells(r.pe, 'PE', r.strike, maxOi),
    ];
  }

  // ----------------------------------------------------------------- paint

  /**
   * The whole panel. Runs when it opens, when the expiry changes, when More
   * is toggled and when the set of strikes changes. NEVER on a refresh tick.
   */
  _paint() {
    if (!this.el) return;
    const d = this.data;
    const rows = (d && d.strikes) || [];
    const atm = this.atmStrike();
    const spot = this.spot();
    const maxOi = rows.reduce(
      (m, r) => Math.max(m, (r.ce && r.ce.oi) || 0, (r.pe && r.pe.oi) || 0),
      0,
    );

    this._cells.clear();
    const body = rows.map((r) => {
      const cells = this._rowCells(r, atm, maxOi);
      cells.forEach(([key, html]) => this._cells.set(`${r.strike}:${key}`, html));
      const itm = spot ? (r.strike < spot ? ' itm-ce' : r.strike > spot ? ' itm-pe' : '') : '';
      return `<tr class="${atm !== null && r.strike === atm ? 'atm' : ''}${itm}" data-strike="${r.strike}">${cells.map(([, html]) => html).join('')}</tr>`;
    }).join('');

    const cols = this.more ? 6 : 4;
    const moreTh = this.more ? '<th class="n iv">IV</th><th class="n vol">Vol</th>' : '';
    const moreThR = this.more ? '<th class="n vol">Vol</th><th class="n iv">IV</th>' : '';

    this.el.innerHTML = `
      <div class="ocm sw-desk" role="dialog" aria-label="Option chain"${this._pos ? ` style="left:${this._pos.left}px;top:${this._pos.top}px;transform:none"` : ''}>
        <div class="ocm-h" data-drag="1">${this._headerInner()}</div>
        ${this._tiles(atm)}
        <div class="ocm-scroll" id="ocm-scroll">
          <table class="ocm-t">
            <thead>
              <tr><th class="side" colspan="${cols}">CALLS</th><th></th><th class="side" colspan="${cols}">PUTS</th></tr>
              <tr>
                <th class="act"></th><th class="n oi">OI</th><th class="n doi">ΔOI</th>${moreTh}<th class="n px">Call</th>
                <th class="strike">Strike</th>
                <th class="n px">Put</th>${moreThR}<th class="n doi">ΔOI</th><th class="n oi">OI</th><th class="act"></th>
              </tr>
            </thead>
            <tbody id="ocm-body">${body || `<tr><td colspan="${cols * 2 + 1}" class="na" style="padding:18px;text-align:center">${this.error ? escapeHtml(this.error) : 'Reading the chain…'}</td></tr>`}</tbody>
          </table>
        </div>
        <div class="ocm-foot">
          <span>shaded is in the money</span><span>·</span>
          <span><b>grey</b> is no trade today: the book is real, the last trade is not</span>
        </div>
      </div>`;
  }

  _headerInner() {
    return `<h4>Option chain</h4>
      ${this._expirySwitcher()}
      ${this._stateChip()}
      <span class="r">
        <button type="button" class="btn sm" data-act="centre">Centre on ATM</button>
        <button type="button" class="btn sm" data-act="more">${this.more ? 'Fewer figures' : 'More figures'}</button>
        <button type="button" class="btn sm" data-act="close">Close</button>
      </span>`;
  }

  /**
   * The header and the tiles, and NOTHING ELSE.
   *
   * Both sit outside the scrolling container, so rewriting them costs him
   * nothing. A full paint would replace the container and throw away wherever
   * he had scrolled to, which is the fault this whole build exists to remove.
   */
  _paintChrome() {
    if (!this.el || typeof this.el.querySelector !== 'function') return;
    const header = this.el.querySelector('.ocm-h');
    if (header) header.innerHTML = this._headerInner();
    const tiles = this.el.querySelector('.ocm-tiles');
    if (tiles) tiles.outerHTML = this._tiles(this.atmStrike());
  }

  _expirySwitcher() {
    if (!this.expiries.length) return '';
    return `<span class="ocm-exp">${this.expiries.map((e) => {
      const dte = isNum(e.days) ? `${e.days} day${e.days === 1 ? '' : 's'}` : '';
      const sub = [String(e.kind || '').toLowerCase(), dte].filter(Boolean).join(' · ');
      return `<button type="button" data-act="expiry" data-expiry="${escapeHtml(e.date)}" class="${e.date === this.expiry ? 'on' : ''}">${escapeHtml(expiryLabel(e.date) || e.date)}<small>${escapeHtml(sub)}</small></button>`;
    }).join('')}</span>`;
  }

  /**
   * THE ONE CLOCK. Nothing here may say LIVE unless the market is open, and
   * the age of the read is not the same question as whether it is live.
   */
  _stateChip() {
    if (this.error) return `<span class="chip c-na">${escapeHtml(this.error)}</span>`;
    const state = this.marketState();
    const at = this.data ? istTime(this.data.as_of) : null;
    if (state === 'live') {
      return `<span class="chip c-live">LIVE${at ? ` · read ${escapeHtml(at)}` : ''}</span>`;
    }
    if (state === 'unavailable') return '<span class="chip c-na">NO LIVE DATA</span>';
    if (state === 'delayed') return `<span class="chip c-na">BEHIND${at ? ` · read ${escapeHtml(at)}` : ''}</span>`;
    return `<span class="chip c-na">AT THE CLOSE${at ? ` · BOOK READ ${escapeHtml(at)}` : ''}</span>`;
  }

  _tiles(atm) {
    const d = this.data;
    const label = expiryLabel(this.expiry) || this.expiry || '—';
    const other = this.otherPain;
    const otherLabel = other ? (expiryLabel(other.expiry) || other.expiry) : null;
    const tile = (k, v, s) =>
      `<div class="met"><div class="k">${escapeHtml(k)}</div><div class="v">${v === null || v === undefined ? '<span class="na">unavailable</span>' : v}</div><div class="s">${s || ''}</div></div>`;

    return `<div class="ocm-tiles">
      ${tile('NIFTY', escapeHtml(num(this.spot(), 2) || '') || null, `at ${escapeHtml(this._readLabel())} · ATM <b>${escapeHtml(num(atm, 0) || '—')}</b>`)}
      ${tile(`Max pain · ${escapeHtml(label)}`, escapeHtml(num(d && d.max_pain, 0) || '') || null,
        // BOTH NUMBERS ON ONE SCREEN, EACH WITH ITS EXPIRY. He saw 23,500 on
        // Home and 24,000 here and neither said which expiry it meant.
        other
          ? `least payout at THIS expiry<br>${escapeHtml(otherLabel || '')}: <b>${escapeHtml(num(other.max_pain, 0) || 'unavailable')}</b>`
          : 'least payout at this expiry')}
      ${tile('Put-call ratio', isNum(d && d.pcr) ? escapeHtml(d.pcr.toFixed(2)) : null, `by open interest · ${escapeHtml(label)}`)}
      ${tile('Call OI', escapeHtml(compact(d && d.total_call_oi) || '') || null, `${escapeHtml(label)} · all strikes on screen`)}
      ${tile('Put OI', escapeHtml(compact(d && d.total_put_oi) || '') || null, `${escapeHtml(label)} · all strikes on screen`)}
      ${tile('Refreshed in place', String(this.ticks), 'times since you opened it<br><b>your scroll kept every time</b>')}
    </div>`;
  }

  _readLabel() {
    const at = this.data ? istTime(this.data.as_of, false) : null;
    return this.marketState() === 'live' ? `${at || 'now'} IST` : `the close${at ? `, book read ${at}` : ''}`;
  }

  // ---------------------------------------------------------------- update

  /**
   * The refresh. Writes only the cells whose contents changed, and touches
   * nothing else, so the scrolling container is never replaced and his place
   * in the table is never lost.
   */
  _update() {
    if (!this.el || typeof this.el.querySelector !== 'function') return;
    const rows = (this.data && this.data.strikes) || [];
    const atm = this.atmStrike();
    const maxOi = rows.reduce(
      (m, r) => Math.max(m, (r.ce && r.ce.oi) || 0, (r.pe && r.pe.oi) || 0),
      0,
    );

    rows.forEach((r) => {
      const tr = this.el.querySelector(`tr[data-strike="${r.strike}"]`);
      if (!tr) return;
      const cells = this._rowCells(r, atm, maxOi);
      const tds = tr.children;
      cells.forEach(([key, html], i) => {
        const id = `${r.strike}:${key}`;
        if (this._cells.get(id) === html) return;   // nothing moved in this cell
        this._cells.set(id, html);
        const td = tds && tds[i];
        if (td && typeof td.outerHTML === 'string') td.outerHTML = html;
      });
    });

    // The tiles above the table are outside the scrolling container, so they
    // can be rewritten whole without costing him anything.
    const tiles = this.el.querySelector('.ocm-tiles');
    if (tiles) tiles.outerHTML = this._tiles(atm);
    const chip = this.el.querySelector('.ocm-h .chip');
    if (chip) chip.outerHTML = this._stateChip();
  }

  /** Puts the at-the-money row back under his eye. */
  centreOnAtm() {
    if (!this.el || typeof this.el.querySelector !== 'function') return;
    const scroll = this.el.querySelector('#ocm-scroll');
    const row = this.el.querySelector('tr.atm');
    if (!scroll || !row) return;
    if (typeof row.offsetTop === 'number' && typeof scroll.clientHeight === 'number') {
      scroll.scrollTop = Math.max(0, row.offsetTop - scroll.clientHeight / 2 + (row.offsetHeight || 0) / 2);
    } else if (typeof row.scrollIntoView === 'function') {
      try { row.scrollIntoView({ block: 'center' }); } catch (_) { /* older browsers */ }
    }
  }

  // ------------------------------------------------------------------ events

  _onClick(e) {
    const t = e && e.target;
    if (!t || typeof t.closest !== 'function') return;
    const btn = t.closest('[data-act]');
    if (!btn) return;
    const act = btn.getAttribute('data-act');
    if (act === 'close') this.close();
    else if (act === 'centre') this.centreOnAtm();
    else if (act === 'more') this.toggleMore();
    else if (act === 'expiry') this.setExpiry(btn.getAttribute('data-expiry'));
    else if (act === 'add') {
      if (btn.disabled) return;
      this.addLeg(btn.getAttribute('data-bs'), Number(btn.getAttribute('data-strike')), btn.getAttribute('data-type'));
    }
  }

  /**
   * Adds the leg at the price on screen, from the row the button sits in.
   *
   * A strike with no trade today is refused here as well as being disabled on
   * screen, because a disabled button is a courtesy and this is the rule.
   */
  addLeg(bs, strike, type) {
    const row = ((this.data && this.data.strikes) || []).find((r) => r.strike === strike);
    const q = row ? (type === 'CE' ? row.ce : row.pe) : null;
    if (!q || !isNum(q.ltp)) return false;
    if (!tradedToday(q)) return false;
    if (this.options.onAddLeg) {
      this.options.onAddLeg({
        bs: bs === 'S' ? 'S' : 'B',
        strike,
        type,
        price: q.ltp,
        iv: isNum(q.iv) ? q.iv : null,
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
      try { this.el.setPointerCapture(e.pointerId); } catch (_) { /* not captured */ }
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

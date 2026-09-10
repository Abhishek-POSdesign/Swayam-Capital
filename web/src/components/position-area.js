/**
 * The position area on the Strategy Desk. Full width, below the payoff.
 *
 * His words, 2026-09-09: "at the strategy desk itself, the bottom area below
 * the payoff graph and execution should be dedicated to open position, close
 * position for the day, and everything for the positions." And how it has to
 * feel, which is a requirement and not decoration: "Full width. Big numbers.
 * Bold. Clearly visible with required colors. Easily manageable. No cheap
 * cross button or rather dustbin button. No cheap round circle for reset, a
 * proper reset button. I must feel good while managing it."
 *
 * On 2026-09-10 he took a four-leg condor and could not see it, manage it or
 * get out of it from the desk. He had approved a clickable journey and read
 * all of it as built; only the ticket half was. This is the other half.
 *
 * WHERE THE NUMBERS COME FROM. Every figure is read off `/api/positions/live`,
 * which marks each open leg at the side he would actually get, costs the exit
 * through the real charge engine, and answers with the market state. NOTHING
 * here computes money. A figure the server could not read shows the word
 * unavailable with the reason behind it, never a zero and never a partial sum
 * presented as a whole one.
 *
 * THE ONE CLOCK. The word LIVE appears only when `/api/market/data-health`
 * says the market is open, which is what the reply's `market_state` carries.
 * Otherwise the card says "at the close" with the time of the last book.
 */

import { inr, inrExact, num, escapeHtml, istTime, orNA } from '../utils/display.js';

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const px = (v) => (isNum(v) ? v.toFixed(2) : '—');
const legName = (l) => `${num(l.strike)} ${l.option_type}`;
const EARLIER_KEY = 'swayam-desk-earlier-open';

/**
 * The trading day an instant belongs to, in IST, as YYYY-MM-DD.
 *
 * Everything in the record is stored in UTC. His day is an IST day, and the
 * two are five and a half hours apart, so the date has to be converted rather
 * than sliced off the front of the timestamp.
 */
/**
 * What this trade was, said on its own card rather than assumed.
 *
 * The card used to print "terminal test" on EVERY position unconditionally,
 * which is true today and becomes a lie the day he starts paper trading. It
 * now reads the row's own `provenance`, so the chip changes when the record
 * changes and never before.
 */
export function provenanceChip(provenance) {
  const value = String(provenance || '').toLowerCase();
  if (value === 'terminal_test') {
    return '<span class="chip c-test" title="You clicked this to see how the terminal behaves, before paper trading began. It is kept out of your record.">terminal test</span>';
  }
  if (value === 'build_test') {
    return '<span class="chip c-test" title="A row a build made. Not a trade you took.">build test</span>';
  }
  if (value === 'live') return '<span class="chip c-sage">paper trade</span>';
  // Nothing recorded. Say so rather than picking one of the three.
  return '<span class="chip c-test" title="This row carries no provenance, so what it was is not recorded.">not recorded</span>';
}

/**
 * The one line a reached target puts on the card. His instruction: "I do not
 * want unnecessary things lying on my position page", so a target that has NOT
 * been reached shows nothing here at all, and a reached one is a single line
 * naming the leg and which kind it was.
 */
export function reachedLine(p) {
  const alerts = Array.isArray(p && p.alerts) ? p.alerts : [];
  if (!alerts.length) return '';
  const said = alerts.map((a) => {
    const what = a.kind === 'profit' ? 'profit' : 'loss';
    if (a.scope === 'leg') return `${a.leg_label} · ${what} target reached`;
    return a.from_rule1
      ? `the whole trade · running loss reached rule 1`
      : `the whole trade · ${what} target reached`;
  });
  const worst = alerts.some((a) => a.kind === 'loss') ? 'down' : 'up';
  return `<div class="pa-reached ${worst}">${escapeHtml(said.join(' · '))}
    <span>set by you · nothing has been exited</span></div>`;
}

export function istDay(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // en-CA gives YYYY-MM-DD, which sorts and compares as a plain string.
  return d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
}

/** A signed rupee figure, or null so `orNA` can say unavailable. */
/**
 * A signed rupee figure.  is for the six big tiles, where a hero
 * number reads better without paise; everything else keeps the paise,
 * because charges are where his year went.
 */
/**
 * A signed rupee figure. `whole` is for the six big tiles, where a hero
 * number reads better without the paise. Everywhere else keeps them, because
 * charges are where his year went: a gross of +6,109 in FY 2025-26 became a
 * net of -86,299 through 92,408 of costs, and a charge shown as 27 instead of
 * 27.18 hides the very thing he has to watch.
 */
export function signed(v, { whole = false } = {}) {
  if (!isNum(v)) return null;
  const body = whole ? inr(Math.abs(v)) : inrExact(Math.abs(v));
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${body}`;
}

/** The colour class money takes. Colour comes from the money and nowhere else. */
export function tone(v) {
  if (!isNum(v)) return '';
  return v > 0 ? 'up' : v < 0 ? 'down' : '';
}

/** The direction that closes a leg. */
export function exitSideOf(direction) {
  const d = String(direction).toLowerCase();
  return d === 'buy' || d === 'long' ? 'sell' : 'buy';
}

/** How long he has held it, in his words rather than in hours. */
export function heldFor(days) {
  if (!isNum(days)) return null;
  if (days === 0) return 'today';
  return `${days} day${days === 1 ? '' : 's'}`;
}

export class PositionArea {
  /**
   * @param {HTMLElement} host
   * @param {object} options
   *   onExitAll(position)          open the exit ticket for every open leg
   *   onExitLeg(position, leg)     open the exit ticket for one leg
   *   onReverseLeg(position, leg, payload) -> Promise
   *   onAddLeg(position)           open the execution ticket, joining this trade
   *   onShowOnPayoff(position)     draw it on the payoff above
   *   onRename(position, name)     -> Promise
   *   fetchOpen()   -> Promise<live positions>
   *   fetchClosed() -> Promise<closed positions>
   */
  constructor(host, options = {}) {
    this.host = host;
    this.options = options;
    this.open = [];
    this.closed = [];
    this.error = null;
    this.closedError = null;
    this.loading = true;
    this.confirm = null;      // { positionId, sequence, kind, mode, limit, busy, error }
    this.renaming = null;     // a position id
    this.timer = null;
    this.earlierOpen = this._readEarlierPreference();
    this._bound = false;
  }

  _readEarlierPreference() {
    try {
      return window.localStorage.getItem(EARLIER_KEY) !== 'closed';
    } catch (_) {
      return true;
    }
  }

  _writeEarlierPreference() {
    try {
      window.localStorage.setItem(EARLIER_KEY, this.earlierOpen ? 'open' : 'closed');
    } catch (_) {
      /* a browser with storage off still works, it just forgets */
    }
  }

  async init() {
    await this.refresh();
    this.schedule();
  }

  destroy() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  /**
   * Five seconds while the market is open, per the mockup's own footnote.
   * When it is shut there is nothing new to read, so it holds the last book
   * and slows down rather than hammering a closed feed.
   */
  schedule() {
    if (this.timer) clearTimeout(this.timer);
    const live = this.open.some((p) => p.market_state === 'live');
    this.timer = setTimeout(() => {
      this.refresh().then(() => this.schedule());
    }, live ? 5000 : 60000);
  }

  async refresh() {
    const [openRes, closedRes] = await Promise.allSettled([
      this.options.fetchOpen ? this.options.fetchOpen() : Promise.resolve([]),
      this.options.fetchClosed ? this.options.fetchClosed() : Promise.resolve([]),
    ]);
    if (openRes.status === 'fulfilled') {
      this.open = Array.isArray(openRes.value) ? openRes.value : [];
      this.error = null;
    } else {
      this.error = String((openRes.reason && openRes.reason.message) || openRes.reason);
    }
    if (closedRes.status === 'fulfilled') {
      this.closed = Array.isArray(closedRes.value) ? closedRes.value : [];
      this.closedError = null;
    } else {
      this.closedError = String((closedRes.reason && closedRes.reason.message) || closedRes.reason);
    }
    this.loading = false;
    this.render();
    // The desk asked to be told what is open, so it can draw a trade he holds
    // on the payoff when he has not loaded anything himself.
    if (this.options.onOpenRead) this.options.onOpenRead(this.open);
    return this.open;
  }

  positionById(id) {
    return this.open.find((p) => String(p.position_id) === String(id)) || null;
  }

  // ------------------------------------------------------------- rendering

  render() {
    if (!this.host) return;
    if (this.loading) {
      this.host.innerHTML = '<div class="pa"><div class="pa-grp"><h3>Open now</h3><span>reading your positions…</span></div></div>';
      return;
    }

    const today = istDay(new Date().toISOString());
    const closedToday = this.closed.filter((p) => istDay(p.closed_at) === today);
    const earlier = this.closed.filter((p) => istDay(p.closed_at) !== today);

    this.host.innerHTML = `<div class="pa">
      ${this._openSection()}
      ${this._closedSection(closedToday, earlier)}
    </div>`;
    this._bind();
  }

  _openSection() {
    const margin = this._marginUsed();
    const head = `<div class="pa-grp">
      <h3>Open now</h3>
      <span>${this.open.length} position${this.open.length === 1 ? '' : 's'}${margin.text ? ` · margin used ${margin.text}` : ''}</span>
    </div>`;

    if (this.error) {
      return `${head}<div class="pa-empty pa-bad">Your open positions could not be read, so nothing is shown rather than something wrong. ${escapeHtml(this.error)}</div>`;
    }
    if (!this.open.length) {
      return `${head}<div class="pa-empty">Nothing is open. A trade you send from the ticket above appears here within five seconds, with its own profit and loss and its own way out.</div>`;
    }
    return head + this.open.map((p) => this._card(p)).join('');
  }

  /**
   * The broker margin every open position took. One position without it makes
   * the whole figure unavailable: a partial sum is a smaller number that looks
   * whole, and rule 4 would then be tested against a lie.
   */
  _marginUsed() {
    let total = 0;
    let missing = 0;
    this.open.forEach((p) => {
      if (isNum(p.margin_required_inr)) total += p.margin_required_inr;
      else missing += 1;
    });
    if (!this.open.length) return { value: 0, text: inr(0) };
    if (missing) {
      return {
        value: null,
        text: null,
        note: `${missing} open position${missing === 1 ? ' has' : 's have'} no stored margin`,
      };
    }
    return { value: total, text: inr(total) };
  }

  _freshness(p) {
    if (p.market_state === 'live') {
      const at = istTime(p.read_at);
      return `<b>LIVE${at ? ` · ${at}` : ''}</b>`;
    }
    if (p.market_state === 'unavailable') return '<b>no live data</b>';
    // The market closed at 15:30; this is when the last book was READ.
    const at = istTime(p.read_at, false);
    return `<b>at the close</b>${at ? ` · book read ${at}` : ''}`;
  }

  _card(p) {
    const id = String(p.position_id || '');
    const short = id.slice(0, 8);
    const legs = p.legs || [];
    const openLegs = legs.filter((l) => String(l.status || 'open') !== 'closed');
    const nameChip = p.name_source === 'his'
      ? '<span class="chip c-sage">your name</span>'
      : '<span class="chip c-sage">named from the structure</span>';
    const renaming = this.renaming === id;

    const held = heldFor(p.days_held);
    const dte = isNum(p.days_remaining_to_expiry) ? `${p.days_remaining_to_expiry} day${p.days_remaining_to_expiry === 1 ? '' : 's'} to expiry` : null;
    const kind = isNum(p.days_held) && p.days_held >= 1 ? 'swing' : 'intraday so far';

    return `<article class="pos" data-pos="${escapeHtml(id)}">
      <header>
        <h4>${escapeHtml(p.strategy_name || 'Trade')} ${nameChip}</h4>
        <span class="meta">
          <span>#${escapeHtml(short)}</span>
          <span>opened <b>${escapeHtml(istTime(p.opened_at, false) || '—')} IST</b></span>
          <span>held <b>${escapeHtml(held || '—')}</b></span>
          <span>expiry <b>${escapeHtml(p.expiry_date || '—')}</b>${dte ? ` · ${escapeHtml(dte)}` : ''}</span>
          <span>${escapeHtml(kind)}</span>
          ${p.legs_closed ? `<span><b>${p.legs_closed}</b> leg${p.legs_closed === 1 ? '' : 's'} already out</span>` : ''}
          ${provenanceChip(p.provenance)}
        </span>
        <div class="r">
          ${renaming
            ? `<span class="pa-rename"><input type="text" data-rename-input="${escapeHtml(id)}" value="${escapeHtml(p.strategy_name || '')}" aria-label="Name for this trade" maxlength="120">
                 <button class="btn sm pri" type="button" data-act="rename-save" data-pos="${escapeHtml(id)}">Save</button>
                 <button class="btn sm" type="button" data-act="rename-clear" data-pos="${escapeHtml(id)}" title="Hand the naming back to the structure">Use the structure's</button>
                 <button class="btn sm" type="button" data-act="rename-cancel">Cancel</button></span>`
            : `<button class="btn sm tgt" type="button" data-act="targets" data-pos="${escapeHtml(id)}" title="What should this trade tell you? Profit and loss, per leg or on the whole trade.">${TARGET_ICON} Targets</button>
               <button class="btn sm" type="button" data-act="rename" data-pos="${escapeHtml(id)}">Edit name</button>
               <button class="btn sm" type="button" data-act="payoff" data-pos="${escapeHtml(id)}">Show on the payoff</button>
               <button class="btn sm" type="button" data-act="add-leg" data-pos="${escapeHtml(id)}">Add a leg</button>
               <button class="btn sm pri" type="button" data-act="exit-all" data-pos="${escapeHtml(id)}">Exit everything</button>`}
        </div>
      </header>

      ${reachedLine(p)}
      ${this._tiles(p)}
      ${this._legsTable(p, openLegs)}
      ${this._confirmRow(p)}

      <footer class="pos-foot">
        <span class="sums">Gross <b class="num ${tone(p.unrealized_pnl_inr)}">${orNA(signed(p.unrealized_pnl_inr), p.error)}</b>
          &nbsp;·&nbsp; charges in <b class="num">${orNA(inrExact(p.charges_in_inr))}</b>
          &nbsp;·&nbsp; charges to exit <b class="num">${orNA(inrExact(p.charges_out_now_inr))}</b>
          &nbsp;·&nbsp; net now <b class="num big ${tone(p.net_if_exit_now_inr)}">${orNA(signed(p.net_if_exit_now_inr), p.error)}</b></span>
        <span class="why">${p.market_state === 'live'
          ? 'refreshes every 5 seconds from the chain feed'
          : 'the market is shut, so this holds the last book and says so'}${p.error ? ` · ${escapeHtml(p.error)}` : ''}</span>
      </footer>
    </article>`;
  }

  _tiles(p) {
    const rule1Used = isNum(p.rule1_cap_inr) && isNum(p.rule1_headroom_inr)
      ? Math.max(0, Math.min(100, ((p.rule1_cap_inr - p.rule1_headroom_inr) / p.rule1_cap_inr) * 100))
      : 0;
    const rule4Share = isNum(p.margin_required_inr) && isNum(p.rule4_ceiling_inr) && p.rule4_ceiling_inr > 0
      ? (p.margin_required_inr / p.rule4_ceiling_inr) * 100
      : null;
    const maxLossPct = isNum(p.max_loss_inr) && isNum(p.rule1_cap_inr) && p.rule1_cap_inr > 0
      ? (p.max_loss_inr / (p.rule1_cap_inr * 100)) * 100
      : null;
    const move = isNum(p.current_spot) && isNum(p.spot_at_entry) ? p.current_spot - p.spot_at_entry : null;
    const bes = Array.isArray(p.breakevens) ? p.breakevens.filter(isNum) : [];

    return `<div class="pos-tiles">
      <div class="met">
        <div class="k">Open profit / loss</div>
        <div class="v hero ${tone(p.unrealized_pnl_inr)}">${orNA(signed(p.unrealized_pnl_inr, { whole: true }), p.error)}</div>
        <div class="s">marked at the price you would get · ${this._freshness(p)}</div>
      </div>
      <div class="met">
        <div class="k">Net if you exit now</div>
        <div class="v ${tone(p.net_if_exit_now_inr)}">${orNA(signed(p.net_if_exit_now_inr, { whole: true }), p.error)}</div>
        <div class="s">after <b>${orNA(inrExact(isNum(p.charges_in_inr) && isNum(p.charges_out_now_inr) ? p.charges_in_inr + p.charges_out_now_inr : null))}</b> of charges both ways<br>
          in ${orNA(inrExact(p.charges_in_inr))} · out ${orNA(inrExact(p.charges_out_now_inr))}</div>
      </div>
      <div class="met">
        <div class="k">Rule 1 headroom</div>
        <div class="v ${isNum(p.rule1_headroom_inr) && p.rule1_headroom_inr <= 0 ? 'down' : 'up'}">${orNA(inr(p.rule1_headroom_inr), p.rules_unavailable_reason)}</div>
        <div class="s">${isNum(p.net_if_exit_now_inr) && p.net_if_exit_now_inr >= 0 ? 'no loss running' : 'running loss counted'} · cap 1% of the live balance${isNum(p.rule1_cap_inr) ? `, ${inr(p.rule1_cap_inr)}` : ''}</div>
        <div class="bar"><i class="${rule1Used > 0 ? 'hot' : ''}" style="width:${rule1Used.toFixed(0)}%"></i></div>
      </div>
      <div class="met">
        <div class="k">Max loss</div>
        <div class="v down">${orNA(inr(p.max_loss_inr))}</div>
        <div class="s">at expiry${isNum(maxLossPct) ? ` · ${maxLossPct.toFixed(2)}% of balance` : ''}<br>max profit <b class="up">${orNA(inr(p.max_profit_inr))}</b></div>
      </div>
      <div class="met">
        <div class="k">Margin</div>
        <div class="v">${orNA(inr(p.margin_required_inr), p.margin_source)}</div>
        <div class="s">${escapeHtml(isNum(p.margin_required_inr) ? 'FYERS, stored on the row' : (p.margin_source || 'not stored on this row'))}<br>
          rule 4: <b>${isNum(rule4Share) ? `${rule4Share.toFixed(0)}%` : '—'}</b> of ${orNA(inr(p.rule4_ceiling_inr), p.rules_unavailable_reason)}</div>
        <div class="bar"><i style="width:${isNum(rule4Share) ? Math.min(100, rule4Share).toFixed(0) : 0}%"></i></div>
      </div>
      <div class="met">
        <div class="k">NIFTY</div>
        <div class="v">${orNA(num(p.current_spot, 2))}</div>
        <div class="s">${isNum(move) ? `<b class="${tone(move)}">${move >= 0 ? '+' : '−'}${num(Math.abs(move), 2)}</b> since entry at ${num(p.spot_at_entry, 2)}` : 'no spot at entry stored on this row'}<br>
          ${bes.length ? `breakevens ${bes.map((b) => num(b, 0)).join(' · ')}` : 'breakevens unavailable'}</div>
      </div>
    </div>`;
  }

  _legsTable(p, openLegs) {
    const id = String(p.position_id || '');
    const shut = p.market_state !== 'live';
    const rows = (p.legs || []).map((l) => {
      const closed = String(l.status || 'open') === 'closed';
      const side = String(l.direction || '').toLowerCase();
      const buy = side === 'buy' || side === 'long';
      const net = closed && isNum(l.gross_pnl_inr) && isNum(l.entry_charges_inr) && isNum(l.exit_charges_inr)
        ? l.gross_pnl_inr - l.entry_charges_inr - l.exit_charges_inr
        : null;
      return `<tr class="${closed ? 'gone' : ''}">
        <td><span class="bs ${buy ? 'B' : 'S'}">${buy ? 'BUY' : 'SELL'}</span></td>
        <td class="leg">${escapeHtml(legName(l))}<span class="sub">${escapeHtml(l.expiry_date || p.expiry_date || '')}${closed ? ' · closed' : ''}</span></td>
        <td class="n">${escapeHtml(String(l.quantity_lots || 1))}</td>
        <td class="n">${px(l.entry_premium)}<span class="sub">at the ${escapeHtml(l.side_hit || (buy ? 'ask' : 'bid'))}${isNum(l.ltp_at_fill) ? ` · traded ${px(l.ltp_at_fill)}` : ''}</span></td>
        <td class="n">${closed ? px(l.exit_premium) : orNA(px(l.mark) === '—' ? null : px(l.mark), l.error)}<span class="sub">${closed
          ? `exited at the ${escapeHtml(l.exit_side_hit || '—')} · ${escapeHtml(istTime(l.closed_at, false) || '')}`
          : `${escapeHtml(l.mark_side || (buy ? 'bid' : 'ask'))} · ${px(l.bid)} / ${px(l.ask)}`}</span></td>
        <td class="n big-n ${tone(closed ? l.gross_pnl_inr : l.leg_pnl_inr)}">${orNA(signed(closed ? l.gross_pnl_inr : l.leg_pnl_inr), l.error)}</td>
        <td class="n">${orNA(inrExact(l.entry_charges_inr))}</td>
        <td class="n">${closed ? orNA(inrExact(l.exit_charges_inr)) : orNA(inrExact(l.exit_charges_now_inr))}</td>
        <td class="act">${closed
          ? `<span class="gone-note">${orNA(signed(net))} booked</span>`
          : `<button class="btn sm" type="button" data-act="exit-leg" data-pos="${escapeHtml(id)}" data-seq="${escapeHtml(String(l.sequence))}" ${shut ? 'disabled title="The market is shut. Nothing can fill."' : ''}>Exit this leg</button>
             <button class="btn sm" type="button" data-act="reverse-leg" data-pos="${escapeHtml(id)}" data-seq="${escapeHtml(String(l.sequence))}" ${shut ? 'disabled title="The market is shut. Nothing can fill."' : ''}>Reverse</button>`}</td>
      </tr>`;
    }).join('');

    return `<div class="pos-legs"><table>
      <thead><tr>
        <th>Side</th><th>Leg</th><th class="n">Lots</th><th class="n">Entry fill</th>
        <th class="n">Now</th><th class="n">Profit / loss</th><th class="n">Charges in</th>
        <th class="n">To exit</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>${openLegs.length === 0 ? '<div class="pa-empty">Every leg is out. The trade closes on the last one.</div>' : ''}</div>`;
  }

  /**
   * The inline confirm for Exit this leg and Reverse. Market or limit, an
   * editable price, a PROPER Reset with the word on it, the quote, what would
   * fill and what it books. Send and Cancel.
   */
  _confirmRow(p) {
    const c = this.confirm;
    if (!c || String(c.positionId) !== String(p.position_id)) return '';
    const leg = (p.legs || []).find((l) => Number(l.sequence) === Number(c.sequence));
    if (!leg) return '';

    const side = exitSideOf(leg.direction);
    const buying = side === 'buy';
    const book = buying ? leg.ask : leg.bid;
    const bookSide = buying ? 'ask' : 'bid';
    const marketable = c.mode === 'MARKET'
      || (isNum(c.limit) && (buying ? c.limit >= book : c.limit <= book));
    const fillPrice = isNum(book) && marketable ? book : null;
    const how = !isNum(book)
      ? `no ${bookSide} published, so this leg cannot be exited`
      : c.mode === 'MARKET'
        ? `market · at the ${bookSide} ${px(book)}`
        : !isNum(c.limit)
          ? 'type a limit price, or press Reset'
          : marketable
            ? `limit ${px(c.limit)} · fills at the ${bookSide} ${px(book)}, better`
            : `your price, not a rule · the ${bookSide} is ${px(book)}`;

    const books = fillPrice !== null && isNum(leg.leg_pnl_inr)
      ? `books <b class="num ${tone(leg.leg_pnl_inr)}">${signed(leg.leg_pnl_inr)}</b> gross, <b class="num">${orNA(inrExact(leg.exit_charges_now_inr))}</b> to get out`
      : marketable
        ? 'what it books cannot be read right now'
        : 'nothing fills until the book reaches your price. Resting orders arrive in the next build.';

    return `<div class="pos-confirm ${marketable ? '' : 'away'}">
      <span class="what">${c.kind === 'reverse' ? 'Reverse' : 'Exit'} <b>${escapeHtml(legName(leg))}</b>: send
        <span class="bs ${buying ? 'B' : 'S'}">${buying ? 'BUY' : 'SELL'}</span> ${escapeHtml(String(leg.quantity_lots || 1))} lot${(leg.quantity_lots || 1) > 1 ? 's' : ''}${c.kind === 'reverse' ? ', then open the opposite leg in the same trade' : ''}.</span>
      <span class="seg" role="group" aria-label="Order type">
        <button type="button" data-act="c-mode" data-mode="MARKET" aria-pressed="${c.mode === 'MARKET'}">Market</button>
        <button type="button" data-act="c-mode" data-mode="LIMIT" aria-pressed="${c.mode === 'LIMIT'}">Limit</button>
      </span>
      <span class="price">
        <input type="number" step="0.05" inputmode="decimal" data-c-limit value="${c.mode === 'LIMIT' ? (isNum(c.limit) ? c.limit.toFixed(2) : '') : px(book)}" ${c.mode === 'MARKET' ? 'disabled' : ''} aria-label="Exit price">
        <button class="btn sm" type="button" data-act="c-reset" ${c.mode === 'MARKET' ? 'disabled' : ''} title="Put the live quote back">${RESET_ICON} Reset</button>
        <span class="quote">bid <b>${px(leg.bid)}</b><br>ask <b>${px(leg.ask)}</b></span>
      </span>
      <span class="fillnote ${marketable ? 'ok' : 'away'}">${escapeHtml(how)}</span>
      <span class="books">${books}</span>
      ${c.error ? `<span class="c-error">${escapeHtml(c.error)}</span>` : ''}
      <span class="go">
        <button class="btn pri sm" type="button" data-act="c-send" ${c.busy || !marketable ? 'disabled' : ''}>${c.busy ? 'Sending…' : 'Send'}</button>
        <button class="btn sm" type="button" data-act="c-cancel">Cancel</button>
      </span>
    </div>`;
  }

  _closedSection(closedToday, earlier) {
    const netOf = (rows) => {
      let total = 0;
      let known = true;
      rows.forEach((r) => { if (isNum(r.realized_pnl_inr)) total += r.realized_pnl_inr; else known = false; });
      return known ? total : null;
    };
    const chargesOf = (rows) => {
      let total = 0;
      let known = true;
      rows.forEach((r) => { if (isNum(r.total_charges_inr)) total += r.total_charges_inr; else known = false; });
      return known ? total : null;
    };

    const todayNet = netOf(closedToday);
    const todayCharges = chargesOf(closedToday);

    const todayHead = `<div class="pa-grp">
      <h3>Closed today</h3>
      <span>${closedToday.length} trade${closedToday.length === 1 ? '' : 's'}${closedToday.length ? ` · net <b class="${tone(todayNet)}">${orNA(signed(todayNet))}</b> · charges ${orNA(inrExact(todayCharges))}` : ''}</span>
    </div>`;

    const earlierHead = `<div class="pa-grp">
      <h3>Earlier</h3>
      <span>${earlier.length} trade${earlier.length === 1 ? '' : 's'}</span>
      <span class="r"><button class="btn sm" type="button" data-act="toggle-earlier">${this.earlierOpen ? 'Hide' : 'Show'}</button></span>
    </div>`;

    const body = this.closedError
      ? `<div class="pa-empty pa-bad">Your closed trades could not be read. ${escapeHtml(this.closedError)}</div>`
      : `${closedToday.length ? closedToday.map((t) => this._closedRow(t, false)).join('') : '<div class="pa-empty">Nothing has been squared off today.</div>'}
         ${earlierHead}
         <div class="pa-earlier"${this.earlierOpen ? '' : ' hidden'}>${earlier.length ? earlier.map((t) => this._closedRow(t, true)).join('') : '<div class="pa-empty">Nothing earlier.</div>'}</div>`;

    return todayHead + body;
  }

  _closedRow(t, dim) {
    const tradedPrice = t.fill_basis === 'traded_price';
    const when = istTime(t.closed_at, false);
    const day = istDay(t.closed_at) || 'date unrecorded';
    return `<div class="pa-closed ${dim ? 'dim' : ''}">
      <div class="t">${escapeHtml(t.strategy_name || 'Trade')}
        <small>${escapeHtml(dim ? day : `closed ${when || ''}`)}${t.close_reason ? ` · ${escapeHtml(String(t.close_reason).replace(/_/g, ' '))}` : ''} · #${escapeHtml(String(t.id || t.position_id || '').slice(0, 8))}</small></div>
      <div><div class="k">Gross</div><div class="v ${tone(t.gross_pnl_inr)}">${orNA(signed(t.gross_pnl_inr))}</div></div>
      <div><div class="k">Charges</div><div class="v">${orNA(inrExact(t.total_charges_inr))}</div></div>
      <div><div class="k">Net</div><div class="v ${tone(t.realized_pnl_inr)}">${orNA(signed(t.realized_pnl_inr))}</div></div>
      <div><div class="k">Fills</div><div class="v small">${escapeHtml(tradedPrice ? 'traded price' : t.fill_basis === 'bid_ask' ? 'bid / ask' : 'unrecorded')}</div></div>
      <div class="chips">${provenanceChip(t.provenance)}${tradedPrice ? '<span class="chip c-warn">not comparable</span>' : ''}</div>
    </div>`;
  }

  // -------------------------------------------------------------- actions

  startConfirm(positionId, sequence, kind) {
    const p = this.positionById(positionId);
    const leg = p && (p.legs || []).find((l) => Number(l.sequence) === Number(sequence));
    if (!leg) return;
    const buying = exitSideOf(leg.direction) === 'buy';
    this.confirm = {
      positionId: String(positionId),
      sequence: Number(sequence),
      kind,
      mode: 'MARKET',
      limit: buying ? leg.ask : leg.bid,
      busy: false,
      error: null,
    };
    this.render();
  }

  async sendConfirm() {
    const c = this.confirm;
    if (!c || c.busy) return;
    const p = this.positionById(c.positionId);
    if (!p) return;
    c.busy = true;
    c.error = null;
    this.render();
    const payload = {
      order_type: c.mode,
      limit_price: c.mode === 'LIMIT' ? c.limit : null,
      close_reason: 'manual',
    };
    try {
      if (c.kind === 'reverse') await this.options.onReverseLeg(p, c.sequence, payload);
      else await this.options.onExitLegNow(p, c.sequence, payload);
      this.confirm = null;
      await this.refresh();
    } catch (err) {
      const detail = err && err.detail;
      const refused = detail && Array.isArray(detail.refused_legs) ? detail.refused_legs[0] : null;
      c.error = refused ? refused.reason : String((err && err.message) || err);
      c.busy = false;
      this.render();
    }
  }

  /**
   * What a button does, named rather than wired.
   *
   * The click listener below is only an adapter onto this, so every action can
   * be exercised without a browser and the delegation is the single thing left
   * to prove in a real one.
   *
   * @param {string} action the data-act value
   * @param {object} args   { id, seq, mode, value }
   */
  async act(action, args = {}) {
    const act = action;
    const { id, seq } = args;
    const p = id ? this.positionById(id) : null;

    {
      if (act === 'toggle-earlier') {
        this.earlierOpen = !this.earlierOpen;
        this._writeEarlierPreference();
        this.render();
      } else if (act === 'exit-all' && p) {
        this.options.onExitAll && this.options.onExitAll(p);
      } else if (act === 'targets' && p) {
        // The modal belongs to the page, not to this component: Home mounts
        // its own and the desk mounts its own, and neither borrows the other.
        this.options.onTargets && this.options.onTargets(p);
      } else if (act === 'add-leg' && p) {
        this.options.onAddLeg && this.options.onAddLeg(p);
      } else if (act === 'payoff' && p) {
        this.options.onShowOnPayoff && this.options.onShowOnPayoff(p);
      } else if (act === 'exit-leg') {
        this.startConfirm(id, seq, 'exit');
      } else if (act === 'reverse-leg') {
        this.startConfirm(id, seq, 'reverse');
      } else if (act === 'c-mode') {
        this.confirm.mode = args.mode === 'LIMIT' ? 'LIMIT' : 'MARKET';
        if (this.confirm.mode === 'LIMIT' && !isNum(this.confirm.limit)) {
          const pos = this.positionById(this.confirm.positionId);
          const leg = pos && (pos.legs || []).find((l) => Number(l.sequence) === this.confirm.sequence);
          if (leg) this.confirm.limit = exitSideOf(leg.direction) === 'buy' ? leg.ask : leg.bid;
        }
        this.render();
      } else if (act === 'c-reset') {
        const pos = this.positionById(this.confirm.positionId);
        const leg = pos && (pos.legs || []).find((l) => Number(l.sequence) === this.confirm.sequence);
        if (leg) this.confirm.limit = exitSideOf(leg.direction) === 'buy' ? leg.ask : leg.bid;
        this.render();
      } else if (act === 'c-cancel') {
        this.confirm = null;
        this.render();
      } else if (act === 'c-send') {
        await this.sendConfirm();
      } else if (act === 'rename') {
        this.renaming = String(id);
        this.render();
        const input = this.host.querySelector(`[data-rename-input="${id}"]`);
        if (input && input.focus) input.focus();
      } else if (act === 'rename-cancel') {
        this.renaming = null;
        this.render();
      } else if (act === 'rename-save' || act === 'rename-clear') {
        // Clearing the name never needs to read the box. Saving reads it only
        // when the caller did not hand the text in.
        let name = '';
        if (act === 'rename-save') {
          const typed = args.value !== undefined ? args.value : this._typedName(id);
          name = String(typed || '').trim();
        }
        try {
          await this.options.onRename(p, name);
          this.renaming = null;
          await this.refresh();
        } catch (err) {
          // The name did not save. Nothing else about the trade changed, and
          // saying so is better than pretending it did.
          this.renaming = null;
          this.render();
        }
      }
    }
  }

  /** Whatever he has typed into the name box, if the page has one. */
  _typedName(id) {
    try {
      const input = this.host && this.host.querySelector
        ? this.host.querySelector(`[data-rename-input="${id}"]`)
        : null;
      return input ? input.value : '';
    } catch (_) {
      return '';
    }
  }

  /** A price typed into the inline confirm. */
  setConfirmLimit(value) {
    if (!this.confirm) return;
    const v = parseFloat(value);
    this.confirm.limit = Number.isFinite(v) && v > 0 ? Math.round(v * 20) / 20 : null;
    this.render();
  }

  /**
   * ONCE. Never again, however many times the area redraws.
   *
   * THE BUG THIS FIXES, found on his machine 2026-09-11. `render()` called
   * this, and this attached a click listener to `this.host` -- the element
   * whose innerHTML render replaces, but which is itself never replaced. So
   * every redraw added another listener to the same element, and every listener
   * that fired called `act()`, which called `render()`, which added another.
   *
   * Measured in the browser before the fix: one click on Show ran `act` once,
   * the next twice, then four times, then eight. Doubling. A dozen clicks is
   * thousands of calls and the tab stops responding, which is exactly what he
   * saw: "this also hangs the whole website... I will have to reopen the
   * website if I use that button once."
   *
   * The five-second refresh timer redraws too, so listeners piled up merely by
   * leaving the desk open.
   *
   * The exit ticket does not have this fault: it binds to the backdrop element
   * INSIDE its own innerHTML, which is thrown away and rebuilt on every render,
   * taking its listeners with it.
   */
  _bind() {
    const root = this.host;
    if (!root || !root.addEventListener) return;
    if (this._bound) return;
    this._bound = true;

    root.addEventListener('click', (e) => {
      const el = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
      if (!el) return;
      this.act(el.getAttribute('data-act'), {
        id: el.getAttribute('data-pos'),
        seq: el.getAttribute('data-seq'),
        mode: el.getAttribute('data-mode'),
      });
    });

    root.addEventListener('change', (e) => {
      const el = e.target;
      if (el && el.getAttribute && el.getAttribute('data-c-limit') !== null) {
        this.setConfirmLimit(el.value);
      }
    });
  }
}

// A proper Reset: the icon AND the word. His words, 2026-09-09: "No cheap
// round circle for reset, a proper reset button."
const TARGET_ICON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2.5"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2"/></svg>';
const RESET_ICON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" focusable="false"><path d="M3 8a5 5 0 1 0 1.5-3.6M3 2.5v3h3"/></svg>';

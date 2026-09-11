/**
 * OPEN ORDERS, inside the position area. Build B, screen 4 of the mockup.
 *
 * His words, 2026-09-10, after the ticket refused his limit price and cost him
 * a strangle: "It should not execute if the price is not available, but must
 * be sitting in the system till the time the bid and ask reach the price I
 * want."
 *
 * So a limit away from the book now WAITS, and this is where he watches it
 * wait. Three groups, each labelled and coloured by its nature, exactly as the
 * mockup draws them:
 *
 *   RESTING   amber, a pulsing dot, and a line saying what it is waiting for,
 *             where the book is now, how far that is, whether it is inside
 *             today's band, and when it expires. Modify with the price
 *             editable in place, and Cancel with a proper dustbin.
 *   FILLED    sage. The time, the price, the word better when it was better,
 *             the charges, and which trade it joined.
 *   EXPIRED   muted. The price the book never reached.
 *
 * WHERE THE NUMBERS COME FROM. Every figure is read off `/api/orders`, which
 * reads the book from the same chain feed the desk quotes from. Nothing here
 * computes a price, a distance or a charge. A figure the server could not read
 * is the word unavailable with its reason, never a zero.
 *
 * THE SENTENCE THAT MUST NEVER BE MISSING. A resting order fills only while
 * this terminal is awake and reading prices, which on the live site means
 * while one of his pages is open. It is not sitting at the broker. Believing
 * otherwise would be worse than not having the feature at all, so it is
 * printed under the group rather than hidden in a tooltip.
 */

import { inrExact, num, escapeHtml, istTime, orNA } from '../utils/display.js';

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const px = (v) => (isNum(v) ? v.toFixed(2) : '—');

/** A proper dustbin, not a cheap cross. His words, 2026-09-09. */
export const BIN_ICON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" focusable="false"><path d="M2.5 4h11M6 4V2.5h4V4M4 4l.7 9.5h6.6L12 4M6.5 7v4M9.5 7v4"/></svg>';

/**
 * What this order will do when it fills, in words rather than in a state name.
 */
export function kindWord(kind) {
  return ({
    entry: 'entry',
    add_leg: 'joins this trade',
    exit_leg: 'exit',
    reverse: 'reverse',
    exit_all_leg: 'exit everything',
  })[String(kind)] || String(kind || '');
}

/**
 * The state line under the amber chip: what it waits for, the book now, and
 * how far away that is.
 *
 * The distance is only ever shown when BOTH prices are real. Without a book
 * there is no distance, and saying so is the honest answer.
 */
export function restingState(order) {
  const s = order.state || {};
  const pieces = [];
  if (isNum(s.book)) {
    const word = s.needs === 'already there' ? 'is there now' : `needs to ${s.needs} ${px(s.distance)}`;
    pieces.push(`${s.side} ${px(s.book)} · ${word}`);
  } else {
    pieces.push(`the ${s.side || 'book'} could not be read just now`);
  }
  return {
    waiting: s.waiting_for || 'waiting for the book',
    book: pieces[0],
    band: s.band || '',
    expires: s.expires || 'expires 15:30',
  };
}

/** One waiting order, as a table row. */
function restingRow(order, editing) {
  const buy = String(order.direction).toLowerCase() === 'buy';
  const state = restingState(order);
  const id = escapeHtml(String(order.id));
  const inFlight = order.in_flight;

  const priceCell = editing === order.id
    ? `<input type="number" step="0.05" inputmode="decimal" data-order-price="${id}"
         value="${isNum(order.limit_price) ? order.limit_price.toFixed(2) : ''}" aria-label="Resting price">`
    : `${px(order.limit_price)}`;

  const actions = inFlight
    ? '<span class="oflight">filling now…</span>'
    : editing === order.id
      ? `<button class="btn sm pri" type="button" data-act="order-save" data-order="${id}">Save price</button>
         <button class="btn sm" type="button" data-act="order-edit-cancel">Cancel</button>`
      : `<button class="btn sm" type="button" data-act="order-edit" data-order="${id}">Modify</button>
         <button class="btn sm danger" type="button" data-act="order-cancel" data-order="${id}"
           title="Take this order out of the book. It has cost nothing and it will cost nothing.">${BIN_ICON} Cancel</button>`;

  return `<tr data-order-row="${id}">
    <td class="n">${escapeHtml(istTime(order.placed_at, false) || '—')}</td>
    <td class="trade">${escapeHtml(order.trade_label || 'Trade')}<span class="sub">${escapeHtml(order.trade_note || '')}</span></td>
    <td><span class="bs ${buy ? 'B' : 'S'}">${buy ? 'BUY' : 'SELL'}</span></td>
    <td class="leg">${escapeHtml(order.leg_label || '')}<span class="sub">${escapeHtml(order.expiry_date || '')} · ${escapeHtml(String(order.quantity_lots || 1))} lot${(order.quantity_lots || 1) > 1 ? 's' : ''}</span></td>
    <td class="n big-n">${priceCell}</td>
    <td class="n">${isNum(order.state && order.state.book) ? px(order.state.book) : orNA(null, 'the book could not be read')}<span class="sub">${escapeHtml(state.book)}</span></td>
    <td class="state">
      <span class="chip c-rest"><span class="dot ${inFlight ? '' : 'pulse'}"></span> ${inFlight ? 'filling' : 'resting'}</span>
      <b>${escapeHtml(state.waiting)}</b>
      <span class="muted">${escapeHtml(state.band)} · ${escapeHtml(state.expires)}</span>
    </td>
    <td class="act">${actions}</td>
  </tr>`;
}

/** One order that filled from the book today. */
function filledRow(order) {
  const fill = order.fill || {};
  const buy = String(order.direction).toLowerCase() === 'buy';
  const better = typeof fill.how === 'string' && /better/.test(fill.how);
  const joined = (order.result && order.result.position_id) || order.position_id;
  return `<tr>
    <td class="n">${escapeHtml(istTime(order.filled_at, false) || '—')}</td>
    <td><span class="bs ${buy ? 'B' : 'S'}">${buy ? 'BUY' : 'SELL'}</span></td>
    <td class="leg">${escapeHtml(order.leg_label || '')}<span class="sub">${escapeHtml(kindWord(order.kind))}</span></td>
    <td class="n">${px(order.limit_price)}<span class="sub">your price</span></td>
    <td class="n big-n">${px(fill.fill_price)}<span class="sub">at the ${escapeHtml(fill.side_hit || '—')}${better ? ' · better' : ''}</span></td>
    <td class="n">${orNA(inrExact(fill.entry_charges_inr ?? fill.exit_charges_inr))}<span class="sub">charges</span></td>
    <td class="joined">${joined ? `joined #${escapeHtml(String(joined).slice(0, 8))}` : 'recorded'}
      ${order.result && order.result.opened_the_trade ? '<span class="sub">this order opened the trade</span>' : ''}</td>
  </tr>`;
}

/** One order the bell killed, or he cancelled, or that failed. */
function closedRow(order) {
  const buy = String(order.direction).toLowerCase() === 'buy';
  const word = {
    expired: 'expired at 15:30',
    cancelled: 'cancelled by you',
    failed: 'failed',
  }[String(order.status)] || String(order.status);
  return `<tr class="gone">
    <td class="n">${escapeHtml(istTime(order.placed_at, false) || '—')}</td>
    <td><span class="bs ${buy ? 'B' : 'S'}">${buy ? 'BUY' : 'SELL'}</span></td>
    <td class="leg">${escapeHtml(order.leg_label || '')}<span class="sub">${escapeHtml(kindWord(order.kind))}</span></td>
    <td class="n big-n">${px(order.limit_price)}<span class="sub">the book never reached it</span></td>
    <td class="why">${escapeHtml(word)}${order.failure_reason && order.status === 'failed'
      ? `<span class="sub">${escapeHtml(order.failure_reason)}</span>`
      : '<span class="sub">nothing was charged</span>'}</td>
  </tr>`;
}

/**
 * The whole Open orders block: three groups, headed, each saying so when empty.
 *
 * @param {object|null} orders the reply from /api/orders
 * @param {object} opts { error, editing }
 */
export function ordersSection(orders, opts = {}) {
  const { error = null, editing = null } = opts;

  if (error) {
    return `${groupHead('Open orders', 'could not be read')}
      <div class="pa-empty pa-bad">Your open orders could not be read, so none are shown rather than a
      list that might be missing one. ${escapeHtml(error)}</div>`;
  }
  if (!orders) {
    return `${groupHead('Open orders', 'reading…')}
      <div class="pa-empty">reading your open orders…</div>`;
  }

  const resting = orders.resting || [];
  const filled = orders.filled || [];
  const closed = orders.closed || [];
  const warnings = orders.warnings || [];

  // One block per warning. Two legs left open by the bell are two separate
  // things he has to deal with, and running them together made them read as
  // one paragraph.
  const bell = warnings.map((w) => `<div class="ord-warn"><b>${escapeHtml(w.headline)}</b>
      <span>${escapeHtml(w.detail)}</span></div>`).join('');

  const restingBlock = resting.length
    ? `<div class="card ord-card"><div class="tw"><table class="orders">
        <thead><tr>
          <th class="n">Placed</th><th>Trade</th><th>Send</th><th>Leg</th>
          <th class="n">Your price</th><th class="n">Book now</th><th>State</th><th></th>
        </tr></thead>
        <tbody>${resting.map((o) => restingRow(o, editing)).join('')}</tbody>
      </table></div>
      <div class="ord-foot">
        <span class="say">A resting order holds no margin and books no charge until it fills. When it
          fills, the leg joins its trade exactly as a sent leg does, with its own fill, its spread cost
          and its charges, and the note gets its line.</span>
        <span class="awake">${escapeHtml(orders.awake_note || '')}</span>
      </div></div>`
    : `<div class="pa-empty">Nothing is waiting for a price. A limit the book has not reached appears
        here the moment you send it, and waits until your price arrives or the bell comes.
        <span class="awake-inline">${escapeHtml(orders.awake_note || '')}</span></div>`;

  const filledBlock = filled.length
    ? `<div class="card ord-card"><div class="tw"><table class="orders">
        <thead><tr><th class="n">Filled</th><th>Send</th><th>Leg</th><th class="n">Your price</th>
          <th class="n">Filled at</th><th class="n">Charges</th><th>Trade</th></tr></thead>
        <tbody>${filled.map(filledRow).join('')}</tbody>
      </table></div></div>`
    : '<div class="pa-empty">Nothing has filled from the book today.</div>';

  const closedBlock = closed.length
    ? `<div class="card ord-card"><div class="tw"><table class="orders">
        <thead><tr><th class="n">Placed</th><th>Send</th><th>Leg</th><th class="n">Your price</th>
          <th>What happened</th></tr></thead>
        <tbody>${closed.map(closedRow).join('')}</tbody>
      </table></div></div>`
    : '<div class="pa-empty">Nothing has expired or been cancelled today.</div>';

  const shut = orders.session_is_over
    ? ' · the bell has gone, so nothing new can rest until your next window'
    : '';

  return `${bell}
    ${groupHead('Open orders', `${resting.length} resting${resting.length ? ' · all expire at 15:30' : ''}${shut}`)}
    ${restingBlock}
    ${groupHead('Filled from the book today', `${filled.length} filled`)}
    ${filledBlock}
    ${groupHead('Expired or cancelled today', `${closed.length}`)}
    ${closedBlock}`;
}

function groupHead(title, note) {
  return `<div class="pa-grp"><h3>${escapeHtml(title)}</h3><span>${escapeHtml(note)}</span></div>`;
}

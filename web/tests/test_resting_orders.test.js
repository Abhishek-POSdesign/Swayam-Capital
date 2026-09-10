/**
 * OPEN ORDERS on the desk, rendered from a captured /api/orders reply.
 * Build B, screen 4 of the mockup.
 *
 * The reply below is shaped exactly as the endpoint answers, on his real open
 * condor 7cd4d017 with the book at the 15:26 IST close of 10 September: the
 * sold 23,800 call whose ask is 98.75 with his bid of 95.00 waiting under it,
 * and a 23,500 call he wants to sell at 111.00 with the bid at 108.40.
 *
 * What these tests hold:
 *   * three groups, each labelled, and each saying so when empty
 *   * a resting order says what it waits for, where the book is, and how far
 *   * a distance is never shown without both real prices
 *   * the sentence about being awake is on the screen, not in a tooltip
 *   * Modify edits the price in place and Save sends only the price
 *   * Cancel is a dustbin, never a cross
 *   * a resting exit the bell killed on an open trade is named in red
 */

import { describe, it, expect, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { PositionArea } from '../src/components/position-area.js';
import { ordersSection, restingState, kindWord } from '../src/components/orders-panel.js';

const EXPIRY = '2026-09-29';
const POSITION = '7cd4d017-2c92-445a-a348-28f395c03db8';

/** One order, as /api/orders renders it. */
function order(overrides = {}) {
  const base = {
    id: 'ord-1',
    kind: 'exit_leg',
    status: 'resting',
    position_id: POSITION,
    trade_label: 'Iron Condor',
    trade_note: `#${POSITION.slice(0, 8)} · exit`,
    direction: 'buy',
    strike: 23800,
    option_type: 'CE',
    expiry_date: EXPIRY,
    quantity_lots: 1,
    sequence: 3,
    leg_label: '23,800 CE',
    limit_price: 95,
    placed_at: '2026-09-10T09:01:00Z',
    expires_at: '2026-09-10T10:00:00Z',
    band_lower: 0.05,
    band_upper: 263.85,
    band_source: 'FYERS depth',
    band_note: "inside today's band, 0.05 to 263.85",
    bid: 98.6,
    ask: 98.75,
    can_modify: true,
    can_cancel: true,
    in_flight: false,
    state: {
      side: 'ask',
      waiting_for: 'waiting for the ask to reach 95.00',
      book: 98.75,
      distance: 3.75,
      needs: 'fall',
      band: "inside today's band, 0.05 to 263.85",
      expires: 'expires 15:30',
    },
  };
  return { ...base, ...overrides };
}

function reply(overrides = {}) {
  return {
    day: '2026-09-10',
    market_state: 'closing',
    read_at: '2026-09-10T09:56:00Z',
    session_is_over: false,
    awake_note:
      'A resting order fills only while this terminal is awake and reading prices, which means '
      + 'while one of your pages is open. It is not sitting at the broker and nothing is watched '
      + 'while you are away.',
    watcher: { passes: 12, filled: 0, last_pass_at: null, last_error: null },
    resting: [order()],
    filled: [],
    closed: [],
    counts: { resting: 1, filled: 0, closed: 0 },
    warnings: [],
    ...overrides,
  };
}

// ----------------------------------------------------------------- the words

describe('what an order says it is waiting for', () => {
  it('names the side, the price, the book and the distance', () => {
    const s = restingState(order());
    expect(s.waiting).toBe('waiting for the ask to reach 95.00');
    expect(s.book).toBe('ask 98.75 · needs to fall 3.75');
    expect(s.band).toContain("inside today's band");
    expect(s.expires).toBe('expires 15:30');
  });

  it('never shows a distance when the book could not be read', () => {
    const s = restingState(order({
      state: { side: 'ask', waiting_for: 'waiting for the ask to reach 95.00', book: null, distance: null, band: '', expires: 'expires 15:30' },
    }));
    expect(s.book).toBe('the ask could not be read just now');
    expect(s.book).not.toMatch(/\d/);
  });

  it('says when the book is already there', () => {
    const s = restingState(order({
      state: { side: 'bid', waiting_for: 'waiting for the bid to reach 111.00', book: 112.5, distance: 1.5, needs: 'already there', band: '', expires: 'expires 15:30' },
    }));
    expect(s.book).toBe('bid 112.50 · is there now');
  });

  it('says what filling it will do, in words rather than a state name', () => {
    expect(kindWord('entry')).toBe('entry');
    expect(kindWord('add_leg')).toBe('joins this trade');
    expect(kindWord('exit_all_leg')).toBe('exit everything');
  });
});

// ---------------------------------------------------------------- the groups

describe('the three groups', () => {
  it('draws the resting order with its price, its book and its two buttons', () => {
    const html = ordersSection(reply());
    expect(html).toContain('Open orders');
    expect(html).toContain('23,800 CE');
    expect(html).toContain('95.00');
    expect(html).toContain('98.75');
    expect(html).toContain('waiting for the ask to reach 95.00');
    expect(html).toContain('data-act="order-edit"');
    expect(html).toContain('data-act="order-cancel"');
    // A dustbin, never a cheap cross. His words, 2026-09-09.
    expect(html).toContain('<svg');
    expect(html).not.toContain('✕');
    expect(html).not.toContain('&times;');
  });

  it('carries the sentence about only filling while a page is open', () => {
    const html = ordersSection(reply());
    expect(html).toContain('while one of your pages is open');
    expect(html).toContain('not sitting at the broker');
  });

  it('says so in one quiet line when a group is empty, never nothing', () => {
    const html = ordersSection(reply({ resting: [], counts: { resting: 0, filled: 0, closed: 0 } }));
    expect(html).toContain('Nothing is waiting for a price');
    expect(html).toContain('Nothing has filled from the book today');
    expect(html).toContain('Nothing has expired or been cancelled today');
    // The sentence about being awake is on the screen in EVERY state, not
    // only when something happens to be resting.
    expect(html).toContain('while one of your pages is open');
  });

  it('an entry order says it opens a new trade when it fills', () => {
    const html = ordersSection(reply({
      resting: [order({ kind: 'entry', position_id: null, trade_label: 'New trade', trade_note: 'entry · opens when it fills' })],
    }));
    expect(html).toContain('New trade');
    expect(html).toContain('entry · opens when it fills');
  });

  it('a filled order shows the time, the price, better, the charges and its trade', () => {
    const html = ordersSection(reply({
      resting: [],
      filled: [order({
        id: 'ord-2', status: 'filled', filled_at: '2026-09-10T09:22:00Z', state: undefined,
        fill: { fill_price: 94.9, side_hit: 'ask', how: 'limit 95.00, filled at the ask 94.90 which is better', exit_charges_inr: 27.18 },
        result: { position_id: POSITION, sequence: 3 },
      })],
      counts: { resting: 0, filled: 1, closed: 0 },
    }));
    expect(html).toContain('94.90');
    expect(html).toContain('better');
    expect(html).toContain('₹27.18');
    expect(html).toContain(`joined #${POSITION.slice(0, 8)}`);
  });

  it('an expired order shows the price the book never reached, and no charge', () => {
    const html = ordersSection(reply({
      resting: [],
      closed: [order({ id: 'ord-3', status: 'expired', state: undefined })],
      counts: { resting: 0, filled: 0, closed: 1 },
    }));
    expect(html).toContain('expired at 15:30');
    expect(html).toContain('the book never reached it');
    expect(html).toContain('nothing was charged');
  });

  it('a failure says what went wrong and that the position did not move', () => {
    const html = ordersSection(reply({
      resting: [],
      closed: [order({ id: 'ord-4', status: 'failed', state: undefined, failure_reason: 'the trade was already closed' })],
      counts: { resting: 0, filled: 0, closed: 1 },
    }));
    expect(html).toContain('failed');
    expect(html).toContain('the trade was already closed');
  });

  it('shows the band it could not read, rather than a band it invented', () => {
    const html = ordersSection(reply({
      resting: [order({
        band_lower: null, band_upper: null, band_source: 'unavailable',
        state: { ...order().state, band: 'band not readable from FYERS; resting without a band check' },
      })],
    }));
    expect(html).toContain('band not readable from FYERS');
    expect(html).not.toContain('0.05 to 263.85');
  });

  it('an order in flight cannot be modified or cancelled', () => {
    const html = ordersSection(reply({
      resting: [order({ status: 'filling', in_flight: true, can_modify: false, can_cancel: false })],
    }));
    expect(html).toContain('filling now');
    expect(html).not.toContain('data-act="order-cancel"');
  });

  it('the whole block says so when the orders could not be read', () => {
    const html = ordersSection(null, { error: 'Supabase is unreachable' });
    expect(html).toContain('could not be read');
    expect(html).toContain('Supabase is unreachable');
    expect(html).not.toContain('waiting for the ask');
  });
});

// -------------------------------------------------------------- the warning

describe("the bell's warning, his instruction of 2026-09-10", () => {
  it('names the leg he is still holding after a resting exit expired', () => {
    const html = ordersSection(reply({
      resting: [],
      counts: { resting: 0, filled: 0, closed: 1 },
      closed: [order({ status: 'expired', kind: 'exit_all_leg', state: undefined })],
      warnings: [{
        position_id: POSITION,
        leg_label: '23,800 CE',
        kind: 'exit_all_leg',
        headline: 'You are NOT out of Iron Condor.',
        detail: 'Your 95.00 on 23,800 CE never got its price, so it expired at the bell and that leg is still yours. Check the 15:20 naked-shorts reading before you leave it overnight.',
      }],
    }));
    expect(html).toContain('You are NOT out of Iron Condor.');
    expect(html).toContain('naked-shorts');
    expect(html).toContain('still yours');
  });

  it('says nothing when nothing was left open', () => {
    expect(ordersSection(reply())).not.toContain('NOT out of');
  });
});

// ------------------------------------------------- modify and cancel, wired

function mount(orders, options = {}) {
  setupTestDOM();
  const host = document.createElement('div');
  document.body.appendChild(host);
  const area = new PositionArea(host, {
    fetchOpen: () => Promise.resolve([]),
    fetchClosed: () => Promise.resolve([]),
    fetchOrders: () => Promise.resolve(orders),
    ...options,
  });
  return { area, host };
}

describe('what the two buttons actually do', () => {
  it('Modify opens the price for typing, and Save sends only the price', async () => {
    const onModifyOrder = vi.fn(() => Promise.resolve({ id: 'ord-1', limit_price: 97.5 }));
    const { area, host } = mount(reply(), { onModifyOrder });
    await area.refresh();

    await area.act('order-edit', { order: 'ord-1' });
    expect(area.editingOrder).toBe('ord-1');
    expect(host.innerHTML).toContain('data-order-price="ord-1"');
    expect(host.innerHTML).toContain('data-act="order-save"');

    await area.act('order-save', { order: 'ord-1', value: '97.50' });
    expect(onModifyOrder).toHaveBeenCalledWith('ord-1', 97.5);
    expect(area.editingOrder).toBeNull();
  });

  it('a price that is not a number is refused before anything is sent', async () => {
    const onModifyOrder = vi.fn();
    const { area } = mount(reply(), { onModifyOrder });
    await area.refresh();
    await area.act('order-save', { order: 'ord-1', value: '' });
    expect(onModifyOrder).not.toHaveBeenCalled();
    expect(area.ordersError).toContain('needs a price');
  });

  it('a refusal from the server is shown, and the order is left alone', async () => {
    const err = new Error('refused');
    err.detail = { error: '500.00 is outside today’s price band for this contract' };
    const { area } = mount(reply(), { onModifyOrder: () => Promise.reject(err) });
    await area.refresh();
    await area.act('order-save', { order: 'ord-1', value: '500' });
    expect(area.ordersError).toContain('outside today');
  });

  it('Cancel calls through and refreshes', async () => {
    const onCancelOrder = vi.fn(() => Promise.resolve({ status: 'cancelled' }));
    const { area } = mount(reply(), { onCancelOrder });
    await area.refresh();
    await area.act('order-cancel', { order: 'ord-1' });
    expect(onCancelOrder).toHaveBeenCalledWith('ord-1');
  });

  it('the orders failing never takes the positions down with them', async () => {
    const { area, host } = mount(null, {
      fetchOrders: () => Promise.reject(new Error('orders are down')),
    });
    await area.refresh();
    expect(area.ordersError).toContain('orders are down');
    expect(host.innerHTML).toContain('Open now');
  });
});

// ------------------------------------------------------------ Home's band

describe("Home's band says how many orders are waiting", () => {
  it('shows the count as its third figure while anything rests', async () => {
    const { HomePage } = await import('../src/pages/home.js');
    setupTestDOM();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const page = new HomePage(container);

    const third = page._bandThird({ resting_orders: 2, targets: {}, alerts: [] });
    expect(third.k).toBe('Open orders');
    expect(third.v).toBe('2 resting');
    expect(third.tone).toBe('amber');
  });

  it('a target he set that was REACHED still comes first, because that needs him', async () => {
    const { HomePage } = await import('../src/pages/home.js');
    setupTestDOM();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const page = new HomePage(container);

    const third = page._bandThird({
      resting_orders: 2,
      alerts: [{ scope: 'leg', kind: 'profit', leg_label: '23,800 CE' }],
      targets: {},
    });
    expect(third.k).toBe('Reached');
    expect(third.v).toContain('23,800 CE');
  });

  it('falls back to the targets figure when nothing is waiting', async () => {
    const { HomePage } = await import('../src/pages/home.js');
    setupTestDOM();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const page = new HomePage(container);

    const third = page._bandThird({
      resting_orders: 0,
      alerts: [],
      targets: { legs_with_targets: 2, legs_total: 4 },
    });
    expect(third.k).toBe('Targets set');
    expect(third.v).toBe('2 of 4 legs');
  });

  it("names the leg he is still holding when a resting exit hit the bell", async () => {
    const { HomePage } = await import('../src/pages/home.js');
    setupTestDOM();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const page = new HomePage(container);

    const html = page._band({
      position_id: POSITION,
      strategy_name: 'Iron Condor',
      state: 'running',
      market_state: 'closing',
      unrealized_pnl_inr: 2925,
      net_if_exit_now_inr: 2712,
      legs_open: 1,
      legs_closed: 3,
      alerts: [],
      targets: {},
      resting_orders: 0,
      orders_warning:
        'You are NOT out of 23,800 CE. That exit never got your price and expired at 15:30, '
        + 'so the leg is still yours. Check the 15:20 naked-shorts reading before you carry it overnight.',
    });
    expect(html).toContain('hb-warn');
    expect(html).toContain('NOT out of 23,800 CE');
    expect(html).toContain('naked-shorts');
  });
});

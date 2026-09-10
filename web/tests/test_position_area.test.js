/**
 * The position area on the desk, rendered from a captured /api/positions/live
 * reply. docs/builds/BUILD_01_DESK_POSITION_AREA.md section 3.7.
 *
 * The reply below is shaped exactly as the endpoint answers, on his real open
 * condor 7cd4d017 marked at the 15:26 IST close of 10 September: four legs at
 * the bid and the ask his recorder captured, entry charges as recorded on the
 * legs, exit charges through the real charge engine, the broker margin stored
 * on the row and the spot at entry.
 *
 * What these tests hold:
 *   * the mark is the side he would GET, and the card says which side
 *   * a figure the server could not read says unavailable, never a zero
 *   * the word LIVE appears only when the market state says live
 *   * a leg already squared off stays in the table with its own result
 *   * the refusal wording for his own price never reads like a rule
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { PositionArea, signed, tone, heldFor, exitSideOf } from '../src/components/position-area.js';

const EXPIRY = '2026-09-29';

function leg(sequence, direction, strike, option_type, entry, entryCharges, bid, ask, ltp, exitCharges) {
  return {
    sequence,
    direction,
    strike,
    option_type,
    quantity_lots: 1,
    lot_size: 65,
    entry_premium: entry,
    entry_charges_inr: entryCharges,
    expiry_date: EXPIRY,
    side_hit: direction === 'buy' ? 'ask' : 'bid',
    ltp_at_fill: ltp,
    status: 'open',
    mark: direction === 'buy' ? bid : ask,
    mark_side: direction === 'buy' ? 'bid' : 'ask',
    bid,
    ask,
    current_ltp: ltp,
    leg_pnl_inr: (direction === 'buy' ? (bid - entry) : (entry - ask)) * 65,
    exit_charges_now_inr: exitCharges,
  };
}

/** His condor, at the 15:26 close. */
function condor(overrides = {}) {
  const legs = [
    leg(1, 'buy', 24200, 'CE', 34.5, 24.85, 30.6, 30.75, 34.45, 27.63),
    leg(2, 'buy', 22800, 'PE', 46.4, 25.27, 47.3, 47.4, 46.1, 29.83),
    leg(3, 'sell', 23800, 'CE', 109.15, 37.98, 98.6, 98.75, 109.4, 27.18),
    leg(4, 'sell', 23200, 'PE', 113.55, 38.55, 118.2, 118.55, 113.6, 27.89),
  ];
  const gross = legs.reduce((a, l) => a + l.leg_pnl_inr, 0);
  const chargesIn = legs.reduce((a, l) => a + l.entry_charges_inr, 0);
  const chargesOut = legs.reduce((a, l) => a + l.exit_charges_now_inr, 0);
  return {
    position_id: '7cd4d017-2c92-445a-a348-28f395c03db8',
    strategy_name: 'Iron Condor',
    name_source: 'structure',
    underlying: 'NIFTY',
    opened_at: '2026-09-10T08:15:49Z',
    expiry_date: EXPIRY,
    legs,
    entry_debit_credit_inr: 9217,
    max_loss_inr: 16783,
    max_profit_inr: 9217,
    breakevens: [23058.2, 23941.8],
    current_spot: 23389.25,
    spot_at_entry: 23435.05,
    unrealized_pnl_inr: gross,
    charges_in_inr: chargesIn,
    charges_out_now_inr: chargesOut,
    net_if_exit_now_inr: gross - chargesIn - chargesOut,
    rule1_cap_inr: 9711,
    rule1_headroom_inr: 9711,
    rule4_ceiling_inr: 554961,
    margin_required_inr: 84929.2,
    margin_source: 'FYERS span margin',
    legs_open: 4,
    legs_closed: 0,
    days_held: 1,
    days_remaining_to_expiry: 19,
    market_state: 'closing',
    read_at: '2026-09-10T09:56:00Z',
    error: null,
    ...overrides,
  };
}

function mount(open = [condor()], closed = [], options = {}) {
  setupTestDOM();
  const host = document.createElement('div');
  document.body.appendChild(host);
  const area = new PositionArea(host, {
    fetchOpen: () => Promise.resolve(open),
    fetchClosed: () => Promise.resolve(closed),
    ...options,
  });
  return { area, host };
}

async function rendered(open, closed, options) {
  const { area, host } = mount(open, closed, options);
  await area.refresh();
  return { area, host, html: host.innerHTML };
}

// --------------------------------------------------------------- helpers

describe('the helpers refuse to invent a number', () => {
  it('a missing figure is null, so the screen can say unavailable', () => {
    expect(signed(null)).toBeNull();
    expect(signed(undefined)).toBeNull();
    expect(tone(null)).toBe('');
    expect(heldFor(null)).toBeNull();
  });

  it('colour comes from the money and nowhere else', () => {
    expect(tone(1)).toBe('up');
    expect(tone(-1)).toBe('down');
    expect(tone(0)).toBe('');
  });

  it('charges keep their paise', () => {
    expect(signed(-196.91)).toBe('−₹196.91');
    expect(signed(2925)).toBe('+₹2,925.00');
    expect(signed(2925, { whole: true })).toBe('+₹2,925');
  });

  it('the exit of a leg is the other side of it', () => {
    expect(exitSideOf('buy')).toBe('sell');
    expect(exitSideOf('sell')).toBe('buy');
    expect(exitSideOf('long')).toBe('sell');
  });
});

// ------------------------------------------------------------- the card

describe('the position card', () => {
  it('shows the trade with its name, its id and every leg', async () => {
    const { html } = await rendered();
    expect(html).toContain('Iron Condor');
    expect(html).toContain('7cd4d017');
    expect(html).toContain('24,200 CE');
    expect(html).toContain('22,800 PE');
    expect(html).toContain('23,800 CE');
    expect(html).toContain('23,200 PE');
  });

  it('says where the name came from', async () => {
    const { html } = await rendered();
    expect(html).toContain('named from the structure');

    const his = await rendered([condor({ name_source: 'his', strategy_name: 'September income' })]);
    expect(his.html).toContain('your name');
    expect(his.html).toContain('September income');
  });

  it('marks each leg at the side he would actually get', async () => {
    const { html } = await rendered();
    // The bought 24,200 call is marked at the BID, 30.60, not at the traded 34.45.
    expect(html).toContain('30.60');
    // The sold 23,800 call is marked at the ASK, 98.75, not at the traded 109.40.
    expect(html).toContain('98.75');
    // and the card names which side of the book that mark is.
    expect(html).toMatch(/bid&nbsp;|bid ·|>bid/);
  });

  it('states the net after charges both ways, and the charges themselves', async () => {
    const { html } = await rendered();
    expect(html).toContain('Net if you exit now');
    expect(html).toContain('of charges both ways');
    // Entry charges on the sold call, to the paisa.
    expect(html).toContain('₹37.98');
    expect(html).toContain('₹27.18');
  });

  it('never says LIVE when the market is shut', async () => {
    const { html } = await rendered();
    expect(html).not.toContain('LIVE');
    expect(html).toContain('at the close');
  });

  it('says LIVE only when the market state says live', async () => {
    const { html } = await rendered([condor({ market_state: 'live' })]);
    expect(html).toContain('LIVE');
  });

  it('a figure the server could not read says unavailable, never zero', async () => {
    const broken = condor({
      unrealized_pnl_inr: null,
      net_if_exit_now_inr: null,
      charges_in_inr: null,
      charges_out_now_inr: null,
      error: 'the bid is not published for the 22,800 PE',
    });
    const { html } = await rendered([broken]);
    expect(html).toContain('unavailable');
    expect(html).toContain('the bid is not published');
    expect(html).not.toContain('₹0</div>');
  });

  it('one trade the feed cannot price does not blank the others', async () => {
    const good = condor();
    const bad = condor({
      position_id: 'other-1',
      strategy_name: 'Bull Put Spread',
      unrealized_pnl_inr: null,
      net_if_exit_now_inr: null,
      error: 'FYERS chain unreachable for this expiry',
    });
    const { html } = await rendered([good, bad]);
    expect(html).toContain('Iron Condor');
    expect(html).toContain('Bull Put Spread');
    expect(html).toContain('FYERS chain unreachable');
    // The good one still shows its money.
    expect(html).toContain('Open profit / loss');
  });

  it('margin used is unavailable when any open position lacks it', async () => {
    const { html } = await rendered([condor(), condor({ position_id: 'x', margin_required_inr: null })]);
    expect(html).not.toContain('margin used ₹');
  });
});

// ------------------------------------------------------- a leg already out

describe('a trade whose legs change while it runs', () => {
  const withOneOut = () => {
    const p = condor();
    p.legs = p.legs.map((l, i) => (i !== 2 ? l : {
      ...l,
      status: 'closed',
      closed_at: '2026-09-11T05:30:00Z',
      exit_premium: 98.75,
      exit_side_hit: 'ask',
      exit_charges_inr: 27.18,
      gross_pnl_inr: 676,
      net_pnl_inr: 610.84,
      mark: 98.75,
    }));
    p.legs_open = 3;
    p.legs_closed = 1;
    return p;
  };

  it('keeps the closed leg in the table, greyed, with its own result', async () => {
    const { html } = await rendered([withOneOut()]);
    expect(html).toContain('gone');
    expect(html).toContain('closed');
    expect(html).toContain('booked');
    expect(html).toContain('leg already out');
  });

  it('offers no way to exit a leg that has already gone', async () => {
    const { html } = await rendered([withOneOut()]);
    const rows = html.split('<tr').filter((r) => r.includes('23,800 CE'));
    expect(rows.length).toBe(1);
    expect(rows[0]).not.toContain('Exit this leg');
  });
});

// ------------------------------------------------------- his price, a rule

describe('a price he chose never reads like a rule', () => {
  it('the confirm row says "your price, not a rule" and refuses to send', async () => {
    const { area, host } = await rendered();
    area.startConfirm(condor().position_id, 3, 'exit');
    area.confirm.mode = 'LIMIT';
    area.confirm.limit = 95.0;   // the ask is 98.75, so this will not fill
    area.render();

    const html = host.innerHTML;
    expect(html).toContain('your price, not a rule');
    expect(html).toContain('the ask is 98.75');
    expect(html).toContain('Resting orders arrive in the next build');
    // Send is disabled: nothing can be sent that cannot fill.
    expect(html).toMatch(/data-act="c-send" disabled/);
  });

  it('a limit through the book fills at the book, and says so', async () => {
    const { area, host } = await rendered();
    area.startConfirm(condor().position_id, 3, 'exit');
    area.confirm.mode = 'LIMIT';
    area.confirm.limit = 105.0;
    area.render();

    const html = host.innerHTML;
    expect(html).toContain('fills at the ask 98.75, better');
    expect(html).not.toContain('your price, not a rule');
  });

  it('a market exit says which side of the book it takes', async () => {
    const { area, host } = await rendered();
    area.startConfirm(condor().position_id, 1, 'exit');
    area.render();
    // Leg 1 was BOUGHT, so getting out SELLS it at the bid.
    expect(host.innerHTML).toContain('market · at the bid 30.60');
    expect(host.innerHTML).toContain('SELL');
  });

  it('the Reset button carries the word, not just a circle', async () => {
    const { area, host } = await rendered();
    area.startConfirm(condor().position_id, 3, 'exit');
    area.render();
    expect(host.innerHTML).toContain('Reset');
  });
});

// -------------------------------------------------------------- the shut market

describe('when the market is shut', () => {
  it('nothing can be exited, and the buttons say why', async () => {
    const { html } = await rendered();
    expect(html).toMatch(/data-act="exit-leg"[^>]*disabled/);
    expect(html).toContain('The market is shut');
  });

  it('the exits are live when the market is', async () => {
    const { html } = await rendered([condor({ market_state: 'live' })]);
    expect(html).not.toMatch(/data-act="exit-leg"[^>]*disabled/);
  });
});

// ---------------------------------------------------------------- groups

describe('the three groups', () => {
  const closedRow = (over = {}) => ({
    id: '03a1b63d-1111-2222-3333-444444444444',
    strategy_name: 'Bear Call Spread',
    closed_at: `${new Date().toISOString().slice(0, 10)}T08:57:20Z`,
    close_reason: 'manual',
    gross_pnl_inr: -32.5,
    total_charges_inr: 164.41,
    realized_pnl_inr: -196.91,
    fill_basis: 'bid_ask',
    ...over,
  });

  it('splits closed today from earlier', async () => {
    const earlier = closedRow({
      id: 'aaaa1111-0000-0000-0000-000000000000',
      strategy_name: 'Bull Call Spread',
      closed_at: '2026-09-09T10:00:00Z',
      fill_basis: 'traded_price',
      realized_pnl_inr: -99.9,
    });
    const { html } = await rendered([condor()], [closedRow(), earlier]);
    expect(html).toContain('Closed today');
    expect(html).toContain('Bear Call Spread');
    expect(html).toContain('Earlier');
    expect(html).toContain('Bull Call Spread');
    // A trade filled at the traded price is not comparable with one at the book.
    expect(html).toContain('not comparable');
    expect(html).toContain('traded price');
  });

  it('says what a trade was from its own row, not from a fixed label', async () => {
    // The card used to print "terminal test" on EVERY position unconditionally.
    // That is true today and becomes a lie the day he starts paper trading, so
    // the chip reads the row's own provenance.
    const test = await rendered([condor({ provenance: 'terminal_test' })], [closedRow()]);
    expect(test.html).toContain('terminal test');

    const live = await rendered([condor({ provenance: 'live' })], [closedRow()]);
    expect(live.html).toContain('paper trade');
    expect(live.html).not.toContain('>terminal test<');

    // A row with nothing recorded says so rather than picking one of the three.
    const unknown = await rendered([condor()], [closedRow()]);
    expect(unknown.html).toContain('not recorded');
  });

  it('says plainly when nothing is open', async () => {
    const { html } = await rendered([], []);
    expect(html).toContain('Nothing is open');
  });

  it('remembers whether Earlier was hidden', async () => {
    const { area, host } = await rendered([condor()], []);
    expect(area.earlierOpen).toBe(true);
    await area.act('toggle-earlier');
    expect(area.earlierOpen).toBe(false);
    expect(host.innerHTML).toContain('Show');
    await area.act('toggle-earlier');
    expect(area.earlierOpen).toBe(true);
  });
});

// --------------------------------------------------------------- actions

describe('the buttons do what they say', () => {
  // The test DOM cannot deliver a DELEGATED click, so each button's work is
  // exercised through act(), which is exactly what the click listener calls.
  // That the listener is wired at all is what the browser pass proves.
  const ID = '7cd4d017-2c92-445a-a348-28f395c03db8';

  it('every button on the card has an action', async () => {
    const { html } = await rendered();
    ['exit-all', 'add-leg', 'payoff', 'rename', 'exit-leg', 'reverse-leg'].forEach((a) => {
      expect(html).toContain(`data-act="${a}"`);
    });
  });

  it('Exit everything opens the ticket for this trade', async () => {
    const onExitAll = vi.fn();
    const { area } = await rendered([condor()], [], { onExitAll });
    await area.act('exit-all', { id: ID });
    expect(onExitAll).toHaveBeenCalledTimes(1);
    expect(onExitAll.mock.calls[0][0].position_id).toContain('7cd4d017');
  });

  it('Show on the payoff hands the position up to the desk', async () => {
    const onShowOnPayoff = vi.fn();
    const { area } = await rendered([condor()], [], { onShowOnPayoff });
    await area.act('payoff', { id: ID });
    expect(onShowOnPayoff).toHaveBeenCalledTimes(1);
  });

  it('Add a leg opens the execution ticket on this trade', async () => {
    const onAddLeg = vi.fn();
    const { area } = await rendered([condor()], [], { onAddLeg });
    await area.act('add-leg', { id: ID });
    expect(onAddLeg).toHaveBeenCalledTimes(1);
  });

  it('Edit name offers his own name and a way back to the structure', async () => {
    const { area, host } = await rendered();
    await area.act('rename', { id: ID });
    expect(host.innerHTML).toContain('Save');
    expect(host.innerHTML).toContain("Use the structure's");
  });

  it('a name he types is sent as his; an empty one hands it back', async () => {
    const onRename = vi.fn().mockResolvedValue({});
    const { area } = await rendered([condor()], [], { onRename });
    await area.act('rename-save', { id: ID, value: '  September income  ' });
    expect(onRename.mock.calls[0][1]).toBe('September income');

    await area.act('rename-clear', { id: ID });
    expect(onRename.mock.calls[1][1]).toBe('');
  });

  it('Exit this leg opens the confirm rather than sending anything', async () => {
    const onExitLegNow = vi.fn();
    const { area, host } = await rendered([condor()], [], { onExitLegNow });
    await area.act('exit-leg', { id: ID, seq: '3' });
    expect(onExitLegNow).not.toHaveBeenCalled();
    expect(area.confirm.sequence).toBe(3);
    expect(host.innerHTML).toContain('Send');
    expect(host.innerHTML).toContain('Cancel');
  });

  it('the confirm sends the leg, and a refusal is shown rather than swallowed', async () => {
    const err = new Error('refused');
    err.detail = { refused_legs: [{ leg: 'BUY 23,800 CE', reason: 'Your price, not a rule: the ask is 98.75.' }] };
    const onExitLegNow = vi.fn().mockRejectedValue(err);
    const { area, host } = await rendered([condor({ market_state: 'live' })], [], { onExitLegNow });
    await area.act('exit-leg', { id: ID, seq: '3' });
    await area.act('c-send');
    expect(onExitLegNow).toHaveBeenCalledTimes(1);
    expect(host.innerHTML).toContain('Your price, not a rule');
    // The confirm stays open so he can move the price.
    expect(area.confirm).not.toBeNull();
  });

  it('Reverse sends through the reverse path, not the exit path', async () => {
    const onReverseLeg = vi.fn().mockResolvedValue({});
    const onExitLegNow = vi.fn();
    const { area } = await rendered([condor({ market_state: 'live' })], [], { onReverseLeg, onExitLegNow });
    await area.act('reverse-leg', { id: ID, seq: '3' });
    await area.act('c-send');
    expect(onReverseLeg).toHaveBeenCalledTimes(1);
    expect(onExitLegNow).not.toHaveBeenCalled();
  });
});

/**
 * The exit ticket. docs/builds/BUILD_01_DESK_POSITION_AREA.md section 3.8.
 *
 * His decision of 2026-09-09 evening: "exiting a single leg or exiting all
 * legs should have a limit/market price option." So the ticket is the entry
 * ticket reversed, and these tests hold the reversal itself:
 *
 *   * what he bought is SOLD at the bid; what he sold is BOUGHT at the ask
 *   * a limit fills at his price or better, which in practice is the book
 *   * a limit the book has not reached says "your price, not a rule", in
 *     amber, and refuses the send in this build
 *   * every figure comes off the server; a missing one says unavailable
 */

import { describe, it, expect, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { ExitTicket, previewExit, bookForExit, exitSideOf } from '../src/components/exit-ticket.js';

const EXPIRY = '2026-09-29';

function leg(sequence, direction, strike, option_type, entry, entryCharges, bid, ask, ltp, exitCharges) {
  const mark = direction === 'buy' ? bid : ask;
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
    status: 'open',
    mark,
    mark_side: direction === 'buy' ? 'bid' : 'ask',
    bid,
    ask,
    current_ltp: ltp,
    leg_pnl_inr: (direction === 'buy' ? (bid - entry) : (entry - ask)) * 65,
    exit_charges_now_inr: exitCharges,
  };
}

function condor(overrides = {}) {
  return {
    position_id: '7cd4d017-2c92-445a-a348-28f395c03db8',
    strategy_name: 'Iron Condor',
    expiry_date: EXPIRY,
    days_held: 1,
    market_state: 'live',
    read_at: '2026-09-10T09:56:00Z',
    legs: [
      leg(1, 'buy', 24200, 'CE', 34.5, 24.85, 30.6, 30.75, 34.45, 27.63),
      leg(2, 'buy', 22800, 'PE', 46.4, 25.27, 47.3, 47.4, 46.1, 29.83),
      leg(3, 'sell', 23800, 'CE', 109.15, 37.98, 98.6, 98.75, 109.4, 27.18),
      leg(4, 'sell', 23200, 'PE', 113.55, 38.55, 118.2, 118.55, 113.6, 27.89),
    ],
    ...overrides,
  };
}

function mount(options = {}) {
  setupTestDOM();
  const host = document.createElement('div');
  document.body.appendChild(host);
  return { t: new ExitTicket(host, options), host };
}

// ------------------------------------------------------- the rule, reversed

describe('the exit is the entry rule, reversed', () => {
  it('what he bought is sold, what he sold is bought back', () => {
    expect(exitSideOf('buy')).toBe('sell');
    expect(exitSideOf('sell')).toBe('buy');
  });

  it('a bought leg is marked at the bid, a sold leg at the ask', () => {
    expect(bookForExit({ direction: 'buy', bid: 30.6, ask: 30.75 })).toEqual({ side: 'bid', price: 30.6 });
    expect(bookForExit({ direction: 'sell', bid: 98.6, ask: 98.75 })).toEqual({ side: 'ask', price: 98.75 });
  });

  it('a market exit takes the side of the book it has to', () => {
    const bought = { direction: 'buy', bid: 30.6, ask: 30.75 };
    expect(previewExit(bought, { mode: 'MARKET' })).toEqual({
      ok: true, price: 30.6, how: 'market · at the bid 30.60',
    });
    const sold = { direction: 'sell', bid: 98.6, ask: 98.75 };
    expect(previewExit(sold, { mode: 'MARKET' })).toEqual({
      ok: true, price: 98.75, how: 'market · at the ask 98.75',
    });
  });

  it('a limit through the book fills at the book, which is better', () => {
    const sold = { direction: 'sell', bid: 98.6, ask: 98.75 };
    const f = previewExit(sold, { mode: 'LIMIT', limit: 105 });
    expect(f.ok).toBe(true);
    expect(f.price).toBe(98.75);
    expect(f.how).toContain('better');
  });

  it('a limit the book has not reached does not fill, and says whose price it is', () => {
    const sold = { direction: 'sell', bid: 98.6, ask: 98.75 };
    const f = previewExit(sold, { mode: 'LIMIT', limit: 95 });
    expect(f.ok).toBe(false);
    expect(f.away).toBe(true);
    expect(f.how).toContain('your price, not a rule');
    expect(f.how).toContain('the ask is 98.75');
  });

  it('no published book means no fill, and never a substitute price', () => {
    const f = previewExit({ direction: 'sell', bid: 98.6, ask: null, mark: null }, { mode: 'MARKET' });
    expect(f.ok).toBe(false);
    expect(f.price).toBeNull();
    expect(f.how).toContain('no ask published');
  });
});

// ------------------------------------------------------------- the screen

describe('the ticket as he reads it', () => {
  it('opens for every open leg, and totals them from the server figures', () => {
    const { t, host } = mount();
    t.open(condor());
    expect(t.legs.length).toBe(4);
    const html = host.innerHTML;
    expect(html).toContain('Exit ticket');
    expect(html).toContain('squares off the whole trade');
    expect(html).toContain('Net, before you press');
    expect(html).toContain('Exit all 4 legs');
    expect(html).toContain('Exit one by one');
    // Charges to the paisa, because charges are the point.
    expect(html).toContain('₹37.98');
    expect(html).toContain('₹27.18');
  });

  it('opens for one leg, and says the trade stays open behind it', () => {
    const { t, host } = mount();
    t.open(condor(), 3);
    expect(t.legs.length).toBe(1);
    const html = host.innerHTML;
    expect(html).toContain('Exit this leg');
    expect(html).toContain('the trade stays open behind it');
    expect(html).not.toContain('Exit one by one');
  });

  it('leaves out a leg that is already closed', () => {
    const p = condor();
    p.legs[2] = { ...p.legs[2], status: 'closed', exit_premium: 98.75 };
    const { t } = mount();
    t.open(p);
    expect(t.legs.length).toBe(3);
    expect(t.legs.some((l) => l.sequence === 3)).toBe(false);
  });

  it('says LIVE only when the market state says live', () => {
    const live = mount();
    live.t.open(condor({ market_state: 'live' }));
    expect(live.host.innerHTML).toContain('LIVE');

    const shut = mount();
    shut.t.open(condor({ market_state: 'closing' }));
    expect(shut.host.innerHTML).not.toContain('LIVE');
    expect(shut.host.innerHTML).toContain('AT THE CLOSE');
  });

  it('refuses to send after the bell, and says what he can do', () => {
    const { t, host } = mount();
    t.open(condor({ market_state: 'closing' }));
    expect(t.marketBlock()).toContain('Exit it in your window');
    expect(host.innerHTML).toMatch(/data-x="send-all"[^>]*disabled/);
  });

  it('a limit away from the book shows the amber note and greys the send', () => {
    const { t, host } = mount();
    t.open(condor());
    // Buying back the sold 23,800 call needs the ask, 98.75. Bidding 95 will not fill.
    const i = t.legs.findIndex((l) => l.sequence === 3);
    t.setMode(i, 'LIMIT');
    t.setLimit(i, '95');

    const html = host.innerHTML;
    expect(html).toContain('your price, not a rule');
    expect(html).toContain('Resting orders arrive in the next build');
    expect(html).toMatch(/data-x="send-all"[^>]*disabled/);
    // Never red, and never beside a rule.
    expect(html).not.toContain('Unlimited');
  });

  it('Reset puts the live quote back', () => {
    const { t } = mount();
    t.open(condor());
    const i = t.legs.findIndex((l) => l.sequence === 3);
    t.setMode(i, 'LIMIT');
    t.setLimit(i, '95');
    expect(t._st(t.legs[i]).limit).toBe(95);
    t.resetPrice(i);
    expect(t._st(t.legs[i]).limit).toBe(98.75);
  });

  it('a figure the server could not read says unavailable, never a zero', () => {
    const p = condor();
    p.legs = p.legs.map((l) => ({ ...l, leg_pnl_inr: null, exit_charges_now_inr: null }));
    const { t, host } = mount();
    t.open(p);
    expect(t.totals().net).toBeNull();
    expect(host.innerHTML).toContain('unavailable');
  });
});

// -------------------------------------------------------------- the sending

describe('sending', () => {
  it('one leg goes through the leg exit, not the whole close', async () => {
    const onExitLeg = vi.fn().mockResolvedValue({ status: 'leg_exited', last_leg: false, fill: {} });
    const onExitAll = vi.fn();
    const { t } = mount({ onExitLeg, onExitAll });
    t.open(condor(), 3);
    await t.sendAll();
    expect(onExitLeg).toHaveBeenCalledTimes(1);
    expect(onExitLeg.mock.calls[0][0]).toBe(3);
    expect(onExitAll).not.toHaveBeenCalled();
  });

  it('every leg goes through the whole close, carrying each order type', async () => {
    const onExitAll = vi.fn().mockResolvedValue({ status: 'closed', realized_pnl_inr: -83.18 });
    const { t } = mount({ onExitAll });
    t.open(condor());
    const i = t.legs.findIndex((l) => l.sequence === 3);
    t.setMode(i, 'LIMIT');
    t.setLimit(i, '105');
    await t.sendAll();

    expect(onExitAll).toHaveBeenCalledTimes(1);
    const payload = onExitAll.mock.calls[0][0];
    expect(payload.exit_legs.length).toBe(4);
    const limited = payload.exit_legs.find((l) => l.strike === 23800);
    expect(limited.order_type).toBe('LIMIT');
    expect(limited.limit_price).toBe(105);
    const market = payload.exit_legs.find((l) => l.strike === 24200);
    expect(market.order_type).toBe('MARKET');
    expect(market.limit_price).toBeNull();
  });

  it('the close reason and his note travel with the exit', async () => {
    const onExitAll = vi.fn().mockResolvedValue({ status: 'closed' });
    const { t } = mount({ onExitAll });
    t.open(condor());
    t.reason = 'Target hit';
    t.note = 'call side did its work';
    await t.sendAll();
    const payload = onExitAll.mock.calls[0][0];
    expect(payload.close_reason).toBe('target_hit');
    expect(payload.notes).toBe('call side did its work');
  });

  it('a refusal comes back onto the ticket, leg by leg, and nothing is lost', async () => {
    const err = new Error('refused');
    err.detail = {
      error: 'Not exited. BUY 23,800 CE could not be filled.',
      refused_legs: [{
        leg: 'BUY 23,800 CE',
        reason: 'Your price, not a rule: the ask is 98.75. Resting orders arrive in the next build; for now move the price or switch to market.',
      }],
    };
    const onExitAll = vi.fn().mockRejectedValue(err);
    const { t, host } = mount({ onExitAll });
    t.open(condor());
    await t.sendAll();

    expect(t.phase).toBe('ticket');
    const html = host.innerHTML;
    expect(html).toContain('Your price, not a rule');
    expect(html).toContain('BUY 23,800 CE');
  });

  it('after a fill it says what happened, and whether the note landed', async () => {
    const onExitAll = vi.fn().mockResolvedValue({
      status: 'closed',
      realized_pnl_inr: -83.18,
      total_charges_inr: 239.18,
      legs_closed: 4,
      journal_status: 'pending',
      message: 'Trade closed.',
      last_leg: true,
    });
    const { t, host } = mount({ onExitAll });
    t.open(condor());
    await t.sendAll();
    expect(t.phase).toBe('done');
    const html = host.innerHTML;
    expect(html).toContain('The trade is closed');
    expect(html).toContain('−₹83.18');
    expect(html).toContain('queued for your vault');
  });

  it('one by one walks the legs and stops when he says', async () => {
    const onExitLeg = vi.fn().mockResolvedValue({ status: 'leg_exited', last_leg: false, fill: { net_pnl_inr: 610.84, how: 'market, at the ask 98.75' } });
    const { t, host } = mount({ onExitLeg });
    t.open(condor());
    await t.sendOneByOne();
    expect(t.phase).toBe('walking');
    expect(t.pending.length).toBe(4);

    await t.sendNext();
    expect(onExitLeg).toHaveBeenCalledTimes(1);
    expect(t.pending.length).toBe(3);
    expect(host.innerHTML).toContain('EXITED');

    t.stopHere();
    expect(t.phase).toBe('done');
    expect(t.pending.length).toBe(0);
  });
});

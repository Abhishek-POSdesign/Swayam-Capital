import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { ExecutionTicket, previewFill } from '../src/components/execution-ticket.js';

// A condor as the desk holds it, in the order he built it: sells first.
function condor() {
  return [
    { on: true, bs: 'S', strike: 23700, type: 'CE', lots: 1, price: 185.0, priceSource: 'live', bid: 184.75, ask: 185.3 },
    { on: true, bs: 'S', strike: 23300, type: 'PE', lots: 1, price: 122.25, priceSource: 'live', bid: 122.0, ask: 122.5 },
    { on: true, bs: 'B', strike: 24000, type: 'CE', lots: 1, price: 82.2, priceSource: 'live', bid: 81.9, ask: 82.45 },
    { on: true, bs: 'B', strike: 23000, type: 'PE', lots: 1, price: 62.8, priceSource: 'live', bid: 62.55, ask: 63.05 },
  ];
}

const ctx = () => ({
  strategyName: 'Iron Condor',
  expiry: '2026-09-29',
  expiryLabel: '29 Sep (20d)',
  lotSize: 65,
  spot: 23635.1,
  spotAt: '2026-09-09T08:36:00+05:30',
  capital: { deployable_margin_ceiling_inr: 554960.92 },
  marginUsed: 0,
  dataState: 'live',
});

function ticket(options = {}) {
  setupTestDOM();
  const host = document.createElement('div');
  document.body.appendChild(host);
  const t = new ExecutionTicket(host, { rulesHtml: () => '<div class="rl pass">rule</div>', ...options });
  return { t, host };
}

describe('the fill preview mirrors the exchange', () => {
  it('a market buy pays the ask, a market sell gets the bid', () => {
    expect(previewFill({ bs: 'B', price: 82.2, bid: 81.9, ask: 82.45 }, { mode: 'MARKET' })).toEqual({ ok: true, price: 82.45, how: 'market · at the ask 82.45' });
    expect(previewFill({ bs: 'S', price: 185, bid: 184.75, ask: 185.3 }, { mode: 'MARKET' })).toEqual({ ok: true, price: 184.75, how: 'market · at the bid 184.75' });
  });
  it('a buy limit below the ask does not fill, and says where the ask is', () => {
    const f = previewFill({ bs: 'B', price: 82.2, bid: 81.9, ask: 82.45 }, { mode: 'LIMIT', limit: 80 });
    expect(f.ok).toBe(false);
    expect(f.how).toContain('would not fill now');
    expect(f.how).toContain('ask is 82.45');
  });
  it('a limit through the market fills at the market, which is better than his limit', () => {
    const f = previewFill({ bs: 'S', price: 185, bid: 184.75, ask: 185.3 }, { mode: 'LIMIT', limit: 184 });
    expect(f.price).toBe(184.75);
    expect(f.how).toContain('better');
  });
  it('a leg with a traded price but no book cannot fill', () => {
    expect(previewFill({ bs: 'B', price: 82.2 }, { mode: 'MARKET' }).ok).toBe(false);
    expect(previewFill({ bs: 'B', price: null }, { mode: 'MARKET' }).ok).toBe(false);
  });
});

describe('the execution ticket', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('opens with buys first, because that earns the hedged margin, and every leg on market', () => {
    const { t, host } = ticket();
    t.open(condor(), ctx());
    expect(t.legs.map((l) => l.bs)).toEqual(['B', 'B', 'S', 'S']);
    const html = host.innerHTML;
    expect(html).toContain('Execution ticket');
    expect(html).toContain('Execute all legs');
    expect(html).toContain('Execute one by one');
    expect(html).toContain('Reset');
    expect(html).not.toContain('depth'); // no ladder, no market depth
    t.legs.forEach((l) => expect(t._st(l).mode).toBe('MARKET'));
  });

  it('lets him move a leg, and the payload goes out in HIS order', () => {
    const { t } = ticket();
    t.open(condor(), ctx());
    t.move(2, -1); // the first sell up one
    expect(t.legs.map((l) => `${l.bs}${l.strike}`)).toEqual(['B24000', 'S23700', 'B23000', 'S23300']);
    const p = t.payload();
    expect(p.map((l) => l.direction)).toEqual(['buy', 'sell', 'buy', 'sell']);
    expect(p[1]).toMatchObject({ strike: 23700, option_type: 'CE', order_type: 'MARKET', expiry_date: '2026-09-29' });
  });

  it('a limit away from the market blocks both send buttons and names the leg', () => {
    const { t, host } = ticket();
    t.open(condor(), ctx());
    const i = t.legs.findIndex((l) => l.bs === 'B' && l.strike === 24000);
    t.setMode(i, 'LIMIT');
    t.setLimit(i, '80');
    const { blocked } = t.totals();
    expect(blocked).toEqual(['BUY 24,000 CE']);
    expect(host.innerHTML).toContain('would not fill now');
    expect(host.innerHTML).toContain('data-xt="send-all" disabled');
    expect(host.innerHTML).toContain('data-xt="send-one" disabled');
    expect(host.innerHTML).toContain('Move it, press Reset, or switch it to market');
    // The net at his prices is still a real figure, and says it is conditional.
    expect(t.totals().net).not.toBeNull();
    expect(t.totals().hypothetical).toBe(true);
    expect(host.innerHTML).toContain('if every leg fills');
  });

  it('Reset puts the live quote back and the buttons return', () => {
    const { t, host } = ticket();
    t.open(condor(), ctx());
    const i = t.legs.findIndex((l) => l.bs === 'B' && l.strike === 24000);
    t.setMode(i, 'LIMIT');
    t.setLimit(i, '80');
    t.resetPrice(i);
    expect(t._st(t.legs[i]).limit).toBe(82.45); // the ask, what a buy would pay
    expect(t.totals().blocked).toEqual([]);
    expect(host.innerHTML).not.toContain('data-xt="send-all" disabled');
  });

  it('a limit price he typed survives a re-quote; a market leg follows it', () => {
    const { t } = ticket();
    t.open(condor(), ctx());
    const i = t.legs.findIndex((l) => l.bs === 'S' && l.strike === 23700);
    t.setMode(i, 'LIMIT');
    t.setLimit(i, '184.5');
    const fresh = condor().map((l) => ({ ...l, price: l.price + 1, bid: l.bid + 1, ask: l.ask + 1 }));
    t.update(fresh, ctx());
    expect(t._st(t.legs[i]).limit).toBe(184.5); // his
    expect(t.legs[i].bid).toBe(185.75); // the market moved under it
    expect(t.legs.find((l) => l.bs === 'B' && l.strike === 24000).ask).toBe(83.45);
  });

  it('lots step with a floor of one and change the net', () => {
    const { t } = ticket();
    t.open(condor(), ctx());
    const before = t.totals().net;
    // Sells at the bid, buys at the ask: the real credit, not the traded one.
    expect(before).toBeCloseTo((184.75 + 122.0 - 82.45 - 63.05) * 65, 2);
    t.stepLots(0, -1);
    expect(t._st(t.legs[0]).lots).toBe(1);
    t.stepLots(0, 1);
    expect(t._st(t.legs[0]).lots).toBe(2);
    expect(t.totals().net).not.toBe(before);
    expect(t.payload()[0].quantity_lots).toBe(2);
  });

  it('Execute all sends every leg in his order, and shows what came back', async () => {
    const onSend = vi.fn(async (legs, mode) => ({
      position_id: 'a41c9f2e-0000',
      journal_status: 'pending',
      net_debit_credit_inr: 10546.25,
      entry_charges_inr: 140.13,
      spot_at_entry: 23635.1,
      margin_required_inr: 71204,
      max_loss_inr: 8953.75,
      fills: legs.map((l, i) => ({ sequence: i + 1, direction: l.direction.toUpperCase(), strike: l.strike, option_type: l.option_type, quantity_lots: 1, fill_price: l.entry_premium, how: 'market', entry_charges_inr: 30 })),
    }));
    const { t, host } = ticket({ onSend });
    t.open(condor(), ctx());
    await t.send('all');
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][1]).toBe('all');
    expect(onSend.mock.calls[0][0]).toHaveLength(4);
    expect(t.phase).toBe('done');
    const html = host.innerHTML;
    expect(html).toContain('Trade #a41c9f2e is open');
    expect(html).toContain('FILLED');
    expect(html).toContain('23,635.10');
    expect(html).toContain('queued for your vault');
    expect(html).toContain('Back to the desk');
  });

  it('a refusal returns him to the ticket with EVERY refused leg listed, and nothing sent', async () => {
    const err = new Error('Nothing was sent.');
    err.detail = {
      error: 'Nothing was sent. 2 legs could not be filled honestly; every leg is listed below with what to do.',
      refused_legs: [
        { sequence: 1, leg: 'BUY 24,000 CE', reason: 'a buy limit of 80.00 would not fill now; the market is 82.20.' },
        { sequence: 3, leg: 'SELL 23,700 CE', reason: 'the market is closed, so nothing can fill.' },
      ],
    };
    const { t, host } = ticket({ onSend: vi.fn(async () => { throw err; }) });
    t.open(condor(), ctx());
    await t.send('all');
    expect(t.phase).toBe('ticket');
    expect(host.innerHTML).toContain('BUY 24,000 CE');
    expect(host.innerHTML).toContain('SELL 23,700 CE');
    expect(host.innerHTML).toContain('market is closed');
  });

  it('one by one sends the first leg, then waits for him, then adds each leg to the SAME trade', async () => {
    const onSend = vi.fn(async (legs) => ({
      position_id: 'a41c9f2e-0000', journal_status: 'written', net_debit_credit_inr: -5343,
      fills: [{ sequence: 1, direction: 'BUY', strike: legs[0].strike, option_type: legs[0].option_type, quantity_lots: 1, fill_price: legs[0].entry_premium, how: 'market' }],
    }));
    const onSendNext = vi.fn(async (leg, seq) => ({
      position_id: 'a41c9f2e-0000', status: 'leg_added', legs_count: seq,
      fill: { sequence: seq, direction: leg.direction.toUpperCase(), strike: leg.strike, option_type: leg.option_type, quantity_lots: 1, fill_price: leg.entry_premium, how: 'market' },
    }));
    const { t, host } = ticket({ onSend, onSendNext });
    t.open(condor(), ctx());
    await t.send('one');
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][0]).toHaveLength(1);
    expect(onSend.mock.calls[0][1]).toBe('one_by_one');
    expect(t.phase).toBe('walking');
    expect(host.innerHTML).toContain('Leg 1 of 4 is in');
    expect(host.innerHTML).toContain('Send leg 2');
    expect(host.innerHTML).toContain('Stop here');

    await t.sendNext();
    expect(onSendNext).toHaveBeenCalledTimes(1);
    expect(onSendNext.mock.calls[0][1]).toBe(2);
    expect(t.fills).toHaveLength(2);
    expect(t.phase).toBe('walking');

    t.stopHere();
    expect(t.phase).toBe('done');
    expect(host.innerHTML).toContain('Stopped. Trade #a41c9f2e is open with 2 legs');
  });

  it('a leg with no book blocks the send and the net', () => {
    const { t } = ticket();
    const legs = condor();
    legs[0].price = null; legs[0].bid = null; legs[0].ask = null;
    t.open(legs, ctx());
    expect(t.totals().blocked).toContain('SELL 23,700 CE');
    expect(t.totals().net).toBeNull();
  });
});

describe('the market clock is the one clock', () => {
  it('after the close the send buttons are off and the ticket says what to do', () => {
    const { t, host } = ticket();
    t.open(condor(), { ...ctx(), dataState: 'closing' });
    expect(host.innerHTML).toContain('AT THE CLOSE');
    expect(host.innerHTML).toContain('data-xt="send-all" disabled');
    expect(host.innerHTML).toContain('send it in your window');
  });
});

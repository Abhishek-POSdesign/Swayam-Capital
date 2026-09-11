/**
 * The option chain, made usable. docs/builds/BUILD_04_OPTION_CHAIN.md.
 *
 * He used it against a live market on 2026-09-10 and it built him a real
 * trade. It was also, in his words, unusable while it fights his scroll.
 * These tests hold the five things that changed, and the sixth that must not:
 *
 *   * the scroll stays where he puts it, through refreshes that change prices
 *   * a strike with no trade TODAY shows its real book, strikes through the
 *     stale last trade, and cannot be added by any route
 *   * the at-the-money row is banded and centred
 *   * Buy and Sell are buttons, and a disabled one carries its reason
 *   * every max pain says which expiry it belongs to
 *   * nothing says LIVE unless the market state says live
 *
 * The chain fixture is shaped as /api/option-chain answers, with the 22,850
 * call carrying the fault he actually hit: a last trade of 1,575.95 against a
 * real book of 670.95 to 705.40, and no volume today.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import {
  OptionChainModalComponent,
  compact,
  tradedToday,
  expiryLabel,
} from '../src/components/option-chain-modal.js';
import { api } from '../src/api.js';

const MONTHLY = '2026-09-29';
const WEEKLY = '2026-09-15';

function chain(over = {}) {
  return {
    underlying: 'NIFTY',
    expiry: MONTHLY,
    spot: 23389.25,
    days_to_expiry: 19,
    atm_strike: 23400,
    total_call_oi: 35998950,
    total_put_oi: 47247890,
    pcr: 1.31,
    max_pain: 24000,
    as_of: '2026-09-10T09:56:00+00:00',
    strikes: [
      {
        strike: 22850,
        // THE FAULT HE HIT. A last trade from another session, in live ink,
        // against a real book. No volume today is what gives it away.
        ce: { ltp: 1575.95, bid: 670.95, ask: 705.40, oi: 325, oi_change: 0, volume: 0, iv: null },
        pe: { ltp: 6.50, bid: 6.45, ask: 6.50, oi: 1350115, oi_change: 713310, volume: 19683040, iv: 0.11 },
      },
      {
        strike: 23400,
        ce: { ltp: 278.40, bid: 277.20, ask: 278.15, oi: 1151865, oi_change: 859300, volume: 2576600, iv: 0.1132 },
        pe: { ltp: 183.75, bid: 183.75, ask: 184.45, oi: 1853085, oi_change: 631995, volume: 3531125, iv: 0.1025 },
      },
      {
        strike: 23500,
        ce: { ltp: 220.75, bid: 220.55, ask: 221.40, oi: 2470585, oi_change: 756725, volume: 4492020, iv: 0.11 },
        pe: { ltp: 227.50, bid: 227.05, ask: 227.95, oi: 4819555, oi_change: 244915, volume: 5047640, iv: 0.1002 },
      },
    ],
    ...over,
  };
}

const EXPIRIES = {
  expiries: [
    { date: WEEKLY, label: '15 Sep (5d)', calendar_days: 5, is_weekly: true, is_monthly: false },
    { date: '2026-09-22', label: '22 Sep (12d)', calendar_days: 12, is_weekly: false, is_monthly: false },
    { date: MONTHLY, label: '29 Sep (19d)', calendar_days: 19, is_weekly: false, is_monthly: true },
  ],
  weekly_expiry: WEEKLY,
  monthly_expiry: MONTHLY,
};

function panel(options = {}) {
  setupTestDOM();
  const m = new OptionChainModalComponent(document.body, {
    getExpiry: () => MONTHLY,
    getSpot: () => 23389.25,
    getMarketState: () => 'closing',
    refreshMs: 5000,
    ...options,
  });
  return m;
}

const settle = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, 'getOptionChain').mockResolvedValue(chain());
  vi.spyOn(api, 'getExpiries').mockResolvedValue(EXPIRIES);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// --------------------------------------------------------------- helpers

describe('the helpers read the chain the way he does', () => {
  it('open interest reads in crores and lakhs', () => {
    expect(compact(35998950)).toBe('3.60 cr');
    expect(compact(1350115)).toBe('13.5 L');
    expect(compact(325)).toBe('325');
    expect(compact(null)).toBeNull();
  });

  it('VOLUME is the test of whether a price is today\'s', () => {
    // Open interest survives from earlier sessions and a last traded price
    // survives for ever. Only volume is today's.
    expect(tradedToday({ volume: 0, oi: 325, ltp: 1575.95 })).toBe(false);
    expect(tradedToday({ volume: 12, oi: 0, ltp: null })).toBe(true);
    expect(tradedToday(null)).toBe(false);
    expect(tradedToday({})).toBe(false);
  });

  it('an expiry reads the way it reads everywhere else on the desk', () => {
    expect(expiryLabel('2026-09-15')).toBe('15 Sep');
    expect(expiryLabel('2026-09-29')).toBe('29 Sep');
    expect(expiryLabel(null)).toBeNull();
  });
});

// ------------------------------------------------------------- the scroll

describe('his scroll stays where he puts it', () => {
  it('a refresh that changes prices repaints NOTHING and rewrites only the cells that moved', async () => {
    const m = panel();
    m.open();
    await settle();

    // Painting is the thing that would cost him his place in the table.
    const paint = vi.spyOn(m, '_paint');
    const cellFor = (strike, key) => m._cells.get(`${strike}:${key}`);
    const before = cellFor(23500, 'ce-px');
    const untouched = cellFor(23400, 'ce-px');

    for (let i = 1; i <= 3; i += 1) {
      const moved = chain();
      moved.strikes[2].ce = { ...moved.strikes[2].ce, ltp: 220.75 + i, bid: 220.55 + i, ask: 221.40 + i };
      api.getOptionChain.mockResolvedValue(moved);
      await m.refresh();
      await settle();
    }

    expect(paint).not.toHaveBeenCalled();
    expect(m.ticks).toBe(3);
    // The cell that moved was rewritten, and carries the newest price.
    expect(cellFor(23500, 'ce-px')).not.toBe(before);
    expect(cellFor(23500, 'ce-px')).toContain('223.75');
    // The cell that did not move was left exactly as it was.
    expect(cellFor(23400, 'ce-px')).toBe(untouched);
    m.close();
  });

  it('a change in the STRIKES is the one thing that repaints', async () => {
    const m = panel();
    m.open();
    await settle();
    const paint = vi.spyOn(m, '_paint');

    const fewer = chain();
    fewer.strikes = fewer.strikes.slice(0, 2);
    api.getOptionChain.mockResolvedValue(fewer);
    await m.refresh();
    await settle();

    // The table is genuinely different, so it is rebuilt and re-centred, and
    // the tick count does not move: nothing was refreshed in place.
    expect(paint).toHaveBeenCalledTimes(1);
    expect(m.ticks).toBe(0);
    expect(m.el.innerHTML).not.toContain('data-strike="23500"');
    m.close();
  });

  it('the refresh count is what he sees, and it only counts refreshes in place', async () => {
    const m = panel();
    m.open();
    await settle();
    expect(m.ticks).toBe(0);
    await m.refresh();
    await settle();
    expect(m.ticks).toBe(1);
    expect(m.el.innerHTML).toContain('your scroll kept every time');
    m.close();
  });
});

// --------------------------------------------------------- the dead strike

describe('a strike with no trade today', () => {
  it('shows its real book, strikes through the stale price, and says so', async () => {
    const m = panel();
    m.open();
    await settle();

    const row = m.el.querySelector('tr[data-strike="22850"]').innerHTML;
    expect(row).toContain('no trade today');
    expect(row).toContain('670.95 / 705.40');       // the book is real and is kept
    expect(row).toContain('<s>last traded 1,575.95, stale</s>');
    expect(row).toContain('dead');
    m.close();
  });

  it('cannot be added, by the button or by the method behind it', async () => {
    const added = [];
    const m = panel({ onAddLeg: (l) => added.push(l) });
    m.open();
    await settle();

    expect(m.addLeg('B', 22850, 'CE')).toBe(false);
    expect(m.addLeg('S', 22850, 'CE')).toBe(false);
    expect(added).toEqual([]);

    const html = m.el.innerHTML;
    expect(html).toContain('data-strike="22850" data-type="CE" disabled title="No trade today. The book is shown; it cannot be added for a fill."');
    m.close();
  });

  it('the put on the same strike traded today, so it is untouched', async () => {
    const added = [];
    const m = panel({ onAddLeg: (l) => added.push(l) });
    m.open();
    await settle();

    expect(m.addLeg('S', 22850, 'PE')).toBe(true);
    expect(added[0]).toEqual(expect.objectContaining({ bs: 'S', strike: 22850, type: 'PE', price: 6.5 }));
    m.close();
  });

  it('the footer says once, in words, what the grey means', async () => {
    const m = panel();
    m.open();
    await settle();
    expect(m.el.innerHTML).toContain('the book is real, the last trade is not');
    m.close();
  });
});

// ------------------------------------------------------------ the ATM row

describe('the at-the-money row', () => {
  it('is banded, carries its pill, and is centred when the chain opens', async () => {
    const m = panel();
    m.open();
    await settle();

    // The ATM row is the one at 23,400, and it carries the band and the pill.
    // 23,400 is above spot, so it is ALSO the row where the put is in the
    // money. The band and the shading sit on the same row.
    expect(m.el.innerHTML).toContain('<tr class="atm itm-pe" data-strike="23400">');
    expect(m.el.innerHTML).toContain('class="pill"');
    expect(m.atmStrike()).toBe(23400);
    // Only one row is the ATM row.
    expect(m.el.innerHTML.split('class="atm').length - 1).toBe(1);
    m.close();
  });

  it('shades the money side, and only that side', async () => {
    const m = panel();
    m.open();
    await settle();
    const html = m.el.innerHTML;
    // 22,850 is below spot, so the CALL is in the money there.
    expect(html).toContain('itm-ce" data-strike="22850"');
    // 23,500 is above spot, so the PUT is.
    expect(html).toContain('itm-pe" data-strike="23500"');
    m.close();
  });
});

// ----------------------------------------------------------- the controls

describe('Buy and Sell are controls, not letters', () => {
  it('are real buttons with the words on them', async () => {
    const m = panel();
    m.open();
    await settle();
    const html = m.el.innerHTML;
    expect(html).toContain('>Buy</button>');
    expect(html).toContain('>Sell</button>');
    expect(html).toContain('class="ocbtn B"');
    expect(html).toContain('class="ocbtn S"');
    m.close();
  });

  it('adding a leg keeps the panel open, so four legs is four clicks', async () => {
    const added = [];
    const m = panel({ onAddLeg: (l) => added.push(l) });
    m.open();
    await settle();
    m.addLeg('S', 23400, 'CE');
    m.addLeg('B', 23500, 'CE');
    expect(added.length).toBe(2);
    expect(m.isOpen).toBe(true);
    m.close();
  });
});

// ---------------------------------------------------------- fewer figures

describe('four figures a side, the rest on demand', () => {
  it('keeps IV and volume off the table and on the hover', async () => {
    const m = panel();
    m.open();
    await settle();
    const html = m.el.innerHTML;
    expect(html).toContain('title="IV 11.3% · volume 25,76,600 · book 277.20 / 278.15"');
    expect(html).not.toContain('>IV</th>');
    m.close();
  });

  it('More figures adds the two columns and is remembered', async () => {
    const m = panel();
    m.open();
    await settle();
    m.toggleMore();
    expect(m.el.innerHTML).toContain('<th class="n iv">IV</th>');
    expect(m.el.innerHTML).toContain('Fewer figures');
    expect(m.more).toBe(true);

    // A second panel opens the way he left it. The test DOM hands out a
    // fresh localStorage on every setup, so the reader is asked directly
    // rather than through another panel.
    expect(m._readMore()).toBe(true);
    m.toggleMore();
    expect(m._readMore()).toBe(false);
    expect(m.el.innerHTML).toContain('More figures');
    m.close();
  });
});

// -------------------------------------------------------------- max pain

describe('max pain says which expiry it belongs to', () => {
  it('names its own expiry and the other one beside it', async () => {
    // The two figures he saw on 2026-09-10: 24,000 on the monthly here, and
    // 23,500 on the weekly, which is the one Home shows.
    api.getOptionChain.mockImplementation((expiry) =>
      Promise.resolve(expiry === WEEKLY ? chain({ expiry: WEEKLY, max_pain: 23500 }) : chain()));
    const m = panel();
    m.open();
    await settle();
    await settle();
    await settle();

    // The tiles are rewritten in place once the other expiry answers, and
    // the test DOM cannot see a write to a synthetic element, so the markup
    // they produce is asked for directly.
    expect(m.otherPain).toEqual({ expiry: WEEKLY, max_pain: 23500 });
    const tiles = m._tiles(m.atmStrike());
    expect(tiles).toContain('Max pain · 29 Sep');
    expect(tiles).toContain('24,000');
    expect(tiles).toContain('15 Sep');
    expect(tiles).toContain('23,500');
    expect(tiles).toContain('least payout at THIS expiry');
    m.close();
  });

  it('the other expiry is read once, not on every tick', async () => {
    const m = panel();
    m.open();
    await settle();
    await settle();
    const callsAfterOpen = api.getOptionChain.mock.calls.length;

    await m.refresh();
    await m.refresh();
    await settle();

    // Two refreshes, two calls, and none of them for the other expiry.
    expect(api.getOptionChain.mock.calls.length).toBe(callsAfterOpen + 2);
    m.close();
  });

  it('switching expiry re-reads both and starts the count again', async () => {
    const m = panel();
    m.open();
    await settle();
    await m.refresh();
    expect(m.ticks).toBe(1);

    m.setExpiry(WEEKLY);
    await settle();
    expect(m.expiry).toBe(WEEKLY);
    expect(m.ticks).toBe(0);
    expect(api.getOptionChain).toHaveBeenCalledWith(WEEKLY, 30);
    m.close();
  });

  it('the switcher offers the weekly and the monthly, not merely the next two', async () => {
    const m = panel();
    m.open();
    await settle();
    await settle();
    // 22 Sep is nearer than 29 Sep, and is neither the weekly nor the monthly.
    expect(m.expiries.map((e) => e.date)).toEqual([WEEKLY, MONTHLY]);
    expect(m.el.innerHTML).not.toContain('2026-09-22');
    m.close();
  });
});

// ------------------------------------------------------------- the clock

describe('the one clock', () => {
  it('never says LIVE when the market is shut', async () => {
    const m = panel({ getMarketState: () => 'closing' });
    m.open();
    await settle();
    expect(m.el.innerHTML).not.toContain('LIVE');
    expect(m.el.innerHTML).toContain('AT THE CLOSE');
    m.close();
  });

  it('says LIVE only when the market state says live', async () => {
    const m = panel({ getMarketState: () => 'live' });
    m.open();
    await settle();
    expect(m.el.innerHTML).toContain('LIVE');
    m.close();
  });

  it('says so when there is no data at all', async () => {
    const m = panel({ getMarketState: () => 'unavailable' });
    m.open();
    await settle();
    expect(m.el.innerHTML).toContain('NO LIVE DATA');
    expect(m.el.innerHTML).not.toContain('LIVE ·');
    m.close();
  });
});

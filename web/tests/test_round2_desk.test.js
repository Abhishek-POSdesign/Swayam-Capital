/**
 * Round 2, PR 2: the desk he wants to sit at.
 *
 * Logo and theme, So Far Today's voice and collapse, chat thumbnails, one leg
 * per row with a lots dropdown, greeks in the left rail, the payoff axis in
 * strike shapes, the date slider running today-to-expiry with resets, the
 * seventeen ready-made structures, and the option chain panel with click-to-add.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';
import { setupTestDOM } from './setup_test_dom.js';
import { StrategyBuilderPage } from '../src/pages/strategy-builder.js';
import { HomePage } from '../src/pages/home.js';
import { OptionChainModalComponent } from '../src/components/option-chain-modal.js';
import { SoFarTodayCardComponent } from '../src/components/so-far-today-card.js';
import { axisBounds } from '../src/components/payoff-svg.js';
import { initHeader } from '../src/components/header.js';
import { api } from '../src/api.js';

const CAPITAL = {
  risk_capital_inr: 971002.38, free_cash_inr: 100000, collateral_inr: 871002.38,
  deployable_margin_ceiling_inr: 554960.92, primary_risk_cap_inr: 9710.02, black_swan_fuse_inr: 48550.12,
  source: 'FYERS funds() id 1 Total Balance', taken_at: '2026-09-08T09:30:00+05:30',
};

const CHAIN = {
  underlying: 'NIFTY', expiry: '2026-09-29', expiry_epoch: '1790676600', spot: 23635.1, days_to_expiry: 21,
  atm_strike: 23650, total_call_oi: 6000000, total_put_oi: 9000000, pcr: 1.5, max_pain: 23600,
  as_of: '2026-09-08T11:40:00+00:00',
  strikes: [
    { strike: 23600, ce: { ltp: 160.2, ltp_change_pct: -3.1, iv: 0.11, oi: 2000000, oi_change: 50000, volume: 900000 },
                     pe: { ltp: 90.5, ltp_change_pct: 4.2, iv: 0.12, oi: 4000000, oi_change: -20000, volume: 1200000 } },
    { strike: 23650, ce: { ltp: 130.0, ltp_change_pct: -2.0, iv: 0.108, oi: 1500000, oi_change: 1000, volume: 500000 },
                     pe: { ltp: 110.0, ltp_change_pct: 3.0, iv: 0.115, oi: 3000000, oi_change: 9000, volume: 700000 } },
    { strike: 23700, ce: { ltp: null, iv: null, oi: 100, oi_change: 0, volume: 0 },
                     pe: { ltp: 140.0, ltp_change_pct: 1.0, iv: 0.12, oi: 2000000, oi_change: 100, volume: 10 } },
  ],
};

function desk(container, legs = [], patch = {}) {
  const page = new StrategyBuilderPage(container);
  page.renderLayout();
  page.initSubComponents();
  page.spot = 23635.1;
  page.lotSize = 65;
  page.lotSizeSource = 'FYERS contract master, resolved server-side';
  page.capital = CAPITAL;
  page.marginUsed = 0;
  page.targetSpot = 23635;
  page.expiry = '2026-09-29';
  page.expiries = [{ date: '2026-09-29', calendar_days: 21, label: '29 Sep (21d)', is_monthly: true }];
  page.dteMax = 21;
  page.dteDays = 21;
  page.today = '2026-09-08';
  page.nextTradingDay = '2026-09-09';
  page.legs = legs;
  page.baseLots = legs.map((l) => l.lots);
  Object.assign(page, patch);
  return page;
}

describe('One mark, in the header, only', () => {
  beforeEach(() => setupTestDOM());

  it('the header carries the Devanagari spelling in sage with the tagline, and nothing drawn above it', () => {
    const container = document.createElement('div');
    initHeader(container);
    const html = container.innerHTML;
    expect(html).toContain('स्वयम्');
    expect(html).toContain('Discipline builds tomorrow');
    // Nothing drawn inside the brand block itself (the theme switcher's icons live elsewhere).
    const brand = html.slice(html.indexOf('class="swayam-brand"'), html.indexOf('header-spot-pill'));
    expect(brand).not.toContain('<svg');
    expect(brand).not.toContain('swayam-logo-mark');
    expect(html).not.toContain('SWAYAM CAPITAL');
  });

  it('neither page draws its own brand mark any more', () => {
    const c1 = document.createElement('div');
    new HomePage(c1).render();
    expect(c1.innerHTML).not.toContain('brandmark');
    expect(c1.innerHTML).toContain('pagename');
    const c2 = document.createElement('div');
    const page = new StrategyBuilderPage(c2);
    page.renderLayout();
    expect(c2.innerHTML).not.toContain('brandmark');
    expect(c2.innerHTML).toContain('Strategy Desk');
  });

  it('the desk stylesheet lets auto follow the computer, exactly like the token stylesheet', () => {
    const css = fs.readFileSync(path.resolve(__dirname, '../src/styles/swayam-desk.css'), 'utf8');
    // The unconditional dark block must not name `auto` any more.
    expect(css).not.toMatch(/:root\[data-theme='auto'\]\s*\.sw-desk\s*\{/);
    // Dark under auto comes only from the media query.
    expect(css).toMatch(/@media \(prefers-color-scheme: dark\)[\s\S]*:root:not\(\[data-theme='light'\]\) \.sw-desk/);
    // Depth tokens exist in the light base and the dark blocks, and nothing purple.
    expect((css.match(/--shadow-hi:/g) || []).length).toBeGreaterThanOrEqual(3);
    expect((css.match(/--tile:/g) || []).length).toBeGreaterThanOrEqual(3);
    expect(css).toContain('--edge:');
    expect(css).toContain('max-width: 1840px');
    expect(css).toContain('minmax(430px, 520px)');
    // The words appear only in comments that ban them; no colour value may be one.
    const noComments = css.replace(/\/\*[\s\S]*?\*\//g, '');
    expect(noComments.toLowerCase()).not.toMatch(/purple|lilac|violet/);
  });
});

describe('So Far Today: a voice, a collapse, and the same cost gate', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    localStorage.clear();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('never fires on load, and offers a play button and a Hide control once generated', async () => {
    vi.spyOn(api, 'getSoFarToday').mockResolvedValue({ has_data: false, call_count_today: 0, daily_cap: 8 });
    const gen = vi.spyOn(api, 'generateSoFarToday').mockResolvedValue({
      has_data: true, text: 'NIFTY held 23,600.\n\nSetup: nothing yet.', sources: [], generated_at: new Date().toISOString(),
      age_minutes: 0, call_count_today: 1, daily_cap: 8, cap_reached: false,
    });
    const card = new SoFarTodayCardComponent(container);
    await card.init();
    expect(gen).not.toHaveBeenCalled();
    expect(container.textContent).toContain('Generate Summary');

    await card.generate(false);
    expect(gen).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain('NIFTY held 23,600');
    expect(container.innerHTML).toContain('btn-collapse-so-far');
    expect(container.innerHTML).toContain('sft-tools');
    expect(container.textContent).toContain('Calls today: 1/8');
  });

  it('starts collapsed for the rest of the day once it has been generated and expanded', async () => {
    vi.spyOn(api, 'getSoFarToday').mockResolvedValue({
      has_data: true, text: 'Already generated earlier today.', sources: [], generated_at: new Date().toISOString(),
      age_minutes: 12, call_count_today: 2, daily_cap: 8, cap_reached: false,
    });
    const first = new SoFarTodayCardComponent(container);
    await first.init();
    // Not yet expanded today: shown in full.
    expect(first.state.collapsed).toBe(false);
    expect(container.textContent).toContain('Already generated earlier today');

    first.toggleCollapsed(); // he hides it
    expect(container.textContent).not.toContain('Already generated earlier today');
    first.toggleCollapsed(); // and expands it once: remembered for today
    expect(container.textContent).toContain('Already generated earlier today');

    const second = new SoFarTodayCardComponent(container);
    await second.init();
    expect(second.state.collapsed).toBe(true);
    expect(container.textContent).not.toContain('Already generated earlier today');
    expect(container.textContent).toContain('Show');
  });
});

describe('The legs card: one leg, one row', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('lots is a dropdown of 1 to 20, styled like the type selector, and the dustbin is in the row', () => {
    const page = desk(container, [{ on: true, bs: 'B', strike: 23600, type: 'PE', lots: 3, price: 90.5, priceSource: 'live' }]);
    page.renderLegs();
    const html = container.querySelector('#leg-builder-mount').innerHTML;
    expect(html).toContain('<select class="lots" data-i="0" data-f="lots"');
    expect(html).toContain('<option value="20">20</option>');
    expect(html).toContain('<option value="3" selected>3</option>');
    expect(html).not.toContain('<option value="21">');
    expect(html).toContain('Delete leg');
  });

  it('the leg grid needs no more than the narrowest rail offers', () => {
    const css = fs.readFileSync(path.resolve(__dirname, '../src/styles/swayam-desk.css'), 'utf8');
    const m = css.match(/\.sw-desk \.lh, \.sw-desk \.lr \{[^}]*grid-template-columns:\s*([^;]+);[^}]*gap:\s*(\d+)px/);
    expect(m).not.toBeNull();
    // Each column is either "Npx" or "minmax(Npx, ...)"; the minimum counts.
    const cols = m[1].trim().match(/minmax\([^)]*\)|\S+/g);
    const fixed = cols.reduce((sum, c) => {
      const px = c.match(/^(\d+)px$/);
      const mm = c.match(/^minmax\((\d+)px/);
      return sum + (px ? Number(px[1]) : mm ? Number(mm[1]) : 0);
    }, 0);
    const gaps = (cols.length - 1) * Number(m[2]);
    expect(cols.length).toBe(8);
    // 430px rail less 28px of card padding.
    expect(fixed + gaps).toBeLessThanOrEqual(402);
  });
});

describe('Greeks, payoff axis, sliders and presets', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('puts the greeks at the bottom of the left rail as four pairs, and keeps the rules with the execute button', () => {
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23600, type: 'PE', lots: 1, price: 90.5, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23400, type: 'PE', lots: 1, price: 40.0, priceSource: 'live' },
    ]);
    page.ivPctByStrike = { 23600: 12, 23400: 13 };
    page.renderGreeks();
    const html = container.innerHTML;
    const rail = html.indexOf('strategy-left-rail');
    const greeks = html.indexOf('greeks-table');
    const metrics = html.indexOf('metric-row');
    expect(rail).toBeLessThan(greeks);
    expect(greeks).toBeLessThan(metrics); // the rail is before the right column
    expect(html.indexOf('rule-validation-mount')).toBeLessThan(html.indexOf('execute-row-mount'));
    const g = container.querySelector('#greeks-table').innerHTML;
    expect(g).toContain('Delta');
    expect(g).toContain('Theta / day');
    expect((g.match(/class="gk"/g) || []).length).toBe(4);
    expect(html).not.toContain('per position, at the target above');
  });

  it('snaps the axis to whole 50s', () => {
    // 23,635.1 × 0.94 = 22,217 → 22,200; × 1.06 = 25,053 → 25,100.
    expect(axisBounds(23635.1)).toEqual({ lo: 22200, hi: 25100 });
    // 24,000 × 0.94 = 22,560 → 22,550; × 1.06 = 25,440 → 25,450.
    expect(axisBounds(24000)).toEqual({ lo: 22550, hi: 25450 });
    const { lo, hi } = axisBounds(23779.15);
    expect(lo % 50).toBe(0);
    expect(hi % 50).toBe(0);
    expect(lo).toBeLessThanOrEqual(23779.15 * 0.94);
    expect(hi).toBeGreaterThanOrEqual(23779.15 * 1.06);
  });

  it('labels the axis every 100 points in strike shapes, with the drag maths untouched', () => {
    const page = desk(container, [
      { on: true, bs: 'B', strike: 23600, type: 'PE', lots: 1, price: 90.5, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23400, type: 'PE', lots: 1, price: 40.0, priceSource: 'live' },
    ]);
    page.ivPctByStrike = { 23600: 12, 23400: 13 };
    page.renderChart();
    const svg = container.querySelector('#payoff-svg').innerHTML;
    expect(svg).toContain('>22,200<');
    expect(svg).toContain('>22,300<');
    expect(svg).toContain('>25,000<');
    expect(svg).not.toContain('>23,441<');
    // The two curves and the drag hook are still there.
    expect(svg).toContain('stroke="var(--info)"');
    expect(svg).toContain('stroke="var(--fg)" stroke-width="2.2"');
    expect(typeof page.payoffChart._bindDrag).toBe('function');
  });

  it('runs the date slider from today on the left to expiry day on the right, with resets', () => {
    const page = desk(container, [{ on: true, bs: 'B', strike: 23600, type: 'PE', lots: 1, price: 90.5, priceSource: 'live' }]);
    page.renderSliders();
    const dte = container.querySelector('#dte-range');
    expect(dte.value).toBe('0'); // today: nothing elapsed
    expect(container.querySelector('#dte-text').textContent).toContain('today');
    const ends = container.innerHTML;
    expect(ends.indexOf('<span>today</span>')).toBeGreaterThan(0);
    expect(ends.indexOf('<span>today</span>')).toBeLessThan(ends.indexOf('<span>expiry day</span>'));

    // Dragging right advances the date; expiry day is the right end.
    dte.value = '21';
    container.querySelector('#dte-range').dispatchEvent('input');
    expect(page.dteDays).toBe(0);
    expect(container.querySelector('#dte-text').textContent).toContain('expiry day');

    container.querySelector('#dte-reset').click();
    expect(page.dteDays).toBe(21);

    page.setTarget(24000);
    container.querySelector('#target-reset').click();
    expect(page.targetSpot).toBe(23635);
    expect(container.innerHTML).toContain('class="btn sm" id="target-reset"');
  });

  it('offers every single-expiry structure, strike offsets only, never a premium', async () => {
    vi.spyOn(api, 'getOptionQuote').mockResolvedValue({ available: false, ltp: null, iv: null });
    const page = desk(container, []);
    page.renderPresets();
    const html = container.querySelector('#strategy-presets-container').innerHTML;
    const names = [
      'Bull Call Spread', 'Bear Call Spread', 'Bull Put Spread', 'Bear Put Spread',
      'Long Straddle', 'Short Straddle', 'Long Strangle', 'Short Strangle',
      'Iron Condor', 'Iron Butterfly', 'Call Butterfly', 'Put Butterfly',
      'Call Ratio Back Spread', 'Put Ratio Back Spread', 'Jade Lizard',
      'Broken-Wing Condor Bullish', 'Broken-Wing Condor Bearish',
    ];
    names.forEach((n) => expect(html).toContain(`data-name="${n}"`));
    expect(html).not.toContain('Calendar');
    expect(html).not.toContain('Diagonal');
    expect((html.match(/<path d="M/g) || []).length).toBeGreaterThanOrEqual(names.length);

    await page.loadPreset('Call Butterfly');
    expect(page.legs.map((l) => [l.bs, l.strike, l.type, l.lots])).toEqual([
      ['B', 23450, 'CE', 1], ['S', 23650, 'CE', 2], ['B', 23850, 'CE', 1],
    ]);
    expect(page.legs.every((l) => l.price === null)).toBe(true);

    await page.loadPreset('Jade Lizard');
    expect(page.legs.map((l) => [l.bs, l.strike, l.type])).toEqual([['S', 23450, 'PE'], ['S', 23850, 'CE'], ['B', 24050, 'CE']]);
  });
});

describe('The option chain panel', () => {
  let container;
  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });
  afterEach(() => vi.useRealTimers());

  it('renders calls left, strikes centre, puts right, marks the ATM row and shows the totals', async () => {
    vi.spyOn(api, 'getOptionChain').mockResolvedValue(CHAIN);
    const modal = new OptionChainModalComponent(document.body, { getExpiry: () => '2026-09-29', refreshMs: 5000 });
    modal.open();
    await new Promise((r) => setTimeout(r, 0));
    const html = modal.el.innerHTML;
    expect(api.getOptionChain).toHaveBeenCalledWith('2026-09-29', 30);
    expect(html).toContain('class="atm"');
    expect(html).toContain('>23,650<');
    expect(html).toContain('Put-call ratio');
    expect(html).toContain('1.50');
    expect(html).toContain('60,00,000'); // total call OI
    expect(html).toContain('Max pain');
    expect(html).toContain('23,600');
    expect(html).toContain('11.0%'); // IV solved server-side
    expect(html).toContain('bar ce');
    expect(html).toContain('bar pe');
    // Calls are left of the strike, puts to its right.
    const row = html.slice(html.indexOf('data-strike="23600"'), html.indexOf('data-strike="23650"'));
    expect(row.indexOf('data-type="CE"')).toBeLessThan(row.indexOf('k-strike'));
    expect(row.indexOf('k-strike')).toBeLessThan(row.indexOf('data-type="PE"'));
    modal.close();
  });

  it('adds a leg at the price on screen from an explicit B or S button, stays open, and refuses an unpriced strike', async () => {
    vi.spyOn(api, 'getOptionChain').mockResolvedValue(CHAIN);
    const added = [];
    const modal = new OptionChainModalComponent(document.body, { getExpiry: () => '2026-09-29', onAddLeg: (l) => added.push(l) });
    modal.open();
    await new Promise((r) => setTimeout(r, 0));

    expect(modal.addLeg('S', 23600, 'CE')).toBe(true);
    expect(modal.addLeg('B', 23650, 'PE')).toBe(true);
    expect(added).toEqual([
      expect.objectContaining({ bs: 'S', strike: 23600, type: 'CE', price: 160.2, iv: 0.11, expiry: '2026-09-29' }),
      expect.objectContaining({ bs: 'B', strike: 23650, type: 'PE', price: 110.0 }),
    ]);
    expect(modal.isOpen).toBe(true);

    // 23700 CE has no traded price: not clickable, and it says why.
    expect(modal.addLeg('B', 23700, 'CE')).toBe(false);
    expect(added.length).toBe(2);
    const html = modal.el.innerHTML;
    expect(html).toContain('data-strike="23700" data-type="CE" disabled title="no traded price for this strike, so it cannot be added"');
    expect(html).not.toContain('data-strike="23600" data-type="CE" disabled');
    modal.close();
  });

  it('refreshes every 5 s while open and stops when closed', async () => {
    vi.useFakeTimers();
    const chain = vi.spyOn(api, 'getOptionChain').mockResolvedValue(CHAIN);
    const modal = new OptionChainModalComponent(document.body, { getExpiry: () => '2026-09-29', refreshMs: 5000 });
    modal.open();
    await vi.advanceTimersByTimeAsync(0);
    expect(chain).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(chain).toHaveBeenCalledTimes(2);
    modal.close();
    expect(modal._timer).toBeNull();
    await vi.advanceTimersByTimeAsync(20000);
    expect(chain).toHaveBeenCalledTimes(2);
  });

  it('a leg added from the chain is an ordinary leg on the desk, with the real price and implied volatility', async () => {
    vi.spyOn(api, 'previewOrder').mockResolvedValue({ ordered_legs: [{ lot_size: 65 }], margin_required_inr: 90000 });
    vi.spyOn(api, 'validateStrategy').mockResolvedValue({ realistic_risk: {}, checks: [], capital: CAPITAL });
    const page = desk(container, []);
    page.addLegFromChain({ bs: 'S', strike: 23850, type: 'CE', price: 95.25, iv: 0.104, expiry: '2026-09-29', asOf: '2026-09-08T11:40:00+00:00' });
    page.addLegFromChain({ bs: 'B', strike: 24150, type: 'CE', price: 30.1, iv: 0.11, expiry: '2026-09-29', asOf: '2026-09-08T11:40:00+00:00' });
    expect(page.legs.length).toBe(2);
    expect(page.legs[0]).toEqual(expect.objectContaining({ bs: 'S', strike: 23850, type: 'CE', price: 95.25, lots: 1 }));
    expect(page.legs[0].priceSource).toContain('option chain');
    expect(page.ivPctByStrike[23850]).toBeCloseTo(10.4, 5);
    expect(page.ivSource[23850]).toBe('implied from the traded price');
    expect(JSON.stringify(page.legsPayload())).not.toContain('lot_size');
    expect(page.fullyPriced()).toBe(true);
    expect(container.querySelector('#leg-builder-mount').innerHTML).toContain('95.25');
  });
});

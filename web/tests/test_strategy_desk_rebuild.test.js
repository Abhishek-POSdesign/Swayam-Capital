import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { StrategyBuilderPage } from '../src/pages/strategy-builder.js';
import { api } from '../src/api.js';

const CAPITAL = {
  risk_capital_inr: 971002.38,
  free_cash_inr: 100000,
  collateral_inr: 871002.38,
  deployable_margin_ceiling_inr: 554960.92,
  primary_risk_cap_inr: 9710.02,
  black_swan_fuse_inr: 48550.12,
  source: 'FYERS funds() id 1 Total Balance',
  taken_at: '2026-09-08T09:30:00+05:30',
};

function deskWithLegs(container, legs, patch = {}) {
  const page = new StrategyBuilderPage(container);
  page.renderLayout();
  page.initSubComponents();
  page.spot = 23779.15;
  page.lotSize = 65; // as the server resolved it, never assumed by the page
  page.lotSizeSource = 'FYERS contract master, resolved server-side';
  page.capital = CAPITAL;
  page.marginUsed = 0;
  page.targetSpot = 23780;
  page.legs = legs;
  page.baseLots = legs.map((l) => l.lots);
  Object.assign(page, patch);
  return page;
}

describe('Strategy Desk — the rebuilt page', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('lays out legs first, then ready-made, then strikewise IV, with the rules block last', () => {
    const page = new StrategyBuilderPage(container);
    page.renderLayout();

    const html = container.innerHTML;
    expect(container.querySelector('#strategy-left-rail')).not.toBeNull();
    expect(container.querySelector('#leg-builder-mount')).not.toBeNull();
    expect(container.querySelector('#strategy-presets-container')).not.toBeNull();
    expect(container.querySelector('#iv-mount')).not.toBeNull();
    expect(container.querySelector('#rule-validation-mount')).not.toBeNull();
    expect(container.querySelector('#execute-row-mount')).not.toBeNull();

    // His order, checked by position in the markup rather than by eye.
    expect(html.indexOf('leg-builder-mount')).toBeLessThan(html.indexOf('strategy-presets-container'));
    expect(html.indexOf('strategy-presets-container')).toBeLessThan(html.indexOf('iv-mount'));
    expect(html.indexOf('metric-row')).toBeLessThan(html.indexOf('payoff-chart-mount'));
    expect(html.indexOf('payoff-chart-mount')).toBeLessThan(html.indexOf('rule-validation-mount'));
    expect(html.indexOf('greeks-table')).toBeLessThan(html.indexOf('rule-validation-mount'));
  });

  it('deletes a leg with a dustbin, never a cross', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
    ]);
    page.renderLegs();
    const legsHtml = container.querySelector('#leg-builder-mount').innerHTML;
    expect(legsHtml).toContain('Delete leg');
    expect(legsHtml).toContain('M3 6h18'); // the dustbin path
    expect(legsHtml).not.toContain('✕');
    expect(legsHtml).not.toContain('&times;');
  });

  it('renders Unlimited, never a number, when the position has a net short call', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'S', strike: 23900, type: 'CE', lots: 1, price: 95, priceSource: 'live' },
    ], { preview: { margin_required_inr: 200441, ordered_legs: [{ lot_size: 65 }] } });
    page.renderMetrics();

    const text = container.querySelector('#metric-row').textContent;
    expect(text).toContain('Unlimited');
    expect(text).toContain('no ceiling above');
    // A reward-to-risk ratio against an unlimited loss is meaningless, so it is not printed.
    expect(text).toContain('n/a');
    expect(text).not.toContain('1 : ');
  });

  it('says unavailable, and never a rupee figure, when the broker has not priced the margin', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130, priceSource: 'live' },
    ], { preview: null, previewError: 'FYERS margin service unreachable' });
    page.renderMetrics();

    const text = container.querySelector('#metric-row').textContent;
    expect(text).toContain('unavailable');
    expect(text).toContain('FYERS margin service unreachable');
    // The prototype modelled margin from two per-lot constants. Neither is here.
    expect(text).not.toContain('2,00,441');
    expect(text).not.toContain('66,836');
  });

  it('leaves a leg without a traded price blank rather than seeding one', async () => {
    vi.spyOn(api, 'getOptionQuote').mockResolvedValue({
      available: false,
      ltp: null,
      iv: null,
      note: 'No real price found for this strike/expiry — type your own price.',
    });
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: null, priceSource: null },
    ]);
    page.expiry = '2026-09-24';
    await page.repriceLeg(0);

    expect(page.legs[0].price).toBeNull();
    expect(container.querySelector('#leg-why').textContent).toContain('nothing is seeded for you');
    expect(container.querySelector('#iv-mount').textContent).toContain('unavailable');
  });

  it('does NOT multiply pct_of_margin by 100', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130, priceSource: 'live' },
    ], {
      validation: {
        realistic_risk: { loss_inr: 16879, cap_inr: 9710.02, pct_of_margin: 1.74, passed: false },
        blast_radius: { loss_inr: 20000, cap_inr: 48550.12, pct_of_margin: 2.06, passed: true },
        checks: [{ rule: 'deployable_margin_ceiling', cap_inr: 554960.92 }],
        capital: CAPITAL,
        intraday: true,
        max_loss_is_unlimited: false,
        warnings: [],
      },
    });
    page.renderRules();

    const text = container.querySelector('#rule-validation-mount').textContent;
    expect(text).toContain('1.74%');
    expect(text).toContain('2.06%');
    expect(text).not.toContain('174.00%');
    expect(text).not.toContain('206.00%');
  });

  it('shows every rule as unavailable, with the reason, when the server check could not run', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
    ], { validation: null, validationError: 'Supabase unreachable' });
    page.renderRules();

    expect(container.querySelector('#rule-validation-mount').textContent).toContain('unavailable');
    expect(container.querySelector('#rule-why').textContent).toContain('Supabase unreachable');
  });

  it('never blocks an intraday entry, and says so on the page', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'S', strike: 23900, type: 'CE', lots: 1, price: 95, priceSource: 'live' },
    ], {
      validation: {
        realistic_risk: { loss_inr: 16879, cap_inr: 9710.02, pct_of_margin: 1.74, passed: false },
        blast_radius: { loss_inr: null, cap_inr: 48550.12, pct_of_margin: null, passed: false },
        checks: [],
        capital: CAPITAL,
        intraday: true,
        max_loss_is_unlimited: true,
        carry: { may_carry_overnight: false, hedged: false, gap_loss_inr: null, cap_inr: 19420.05, reasons: [] },
        warnings: [],
      },
    });
    page.renderRules();
    page.renderExecute();

    expect(container.querySelector('#entry-banner').textContent).toContain('never blocked');
    expect(container.querySelector('#execute-row-mount').textContent).toContain('must close before the bell');
    expect(container.querySelector('#rule-validation-mount').textContent).toContain('Unlimited');
  });

  it('calls a structure with no crossing point "none", not "unavailable", and refuses a negative ratio', () => {
    // Four legs priced so the position loses everywhere: the payoff never
    // crosses zero and the best case is still a loss. A reward-to-risk of
    // 1 : -0.04 would be nonsense, so it is not printed.
    const page = deskWithLegs(container, [
      { on: true, bs: 'S', strike: 24000, type: 'CE', lots: 1, price: 94.42, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 93.58, priceSource: 'live' },
      { on: true, bs: 'B', strike: 24300, type: 'CE', lots: 1, price: 100.42, priceSource: 'live' },
      { on: true, bs: 'B', strike: 23300, type: 'PE', lots: 1, price: 99.58, priceSource: 'live' },
    ]);
    page.renderMetrics();

    const text = container.querySelector('#metric-row').textContent;
    expect(text).toContain('the payoff never crosses zero');
    expect(text).toContain('the best case here is still a loss');
    expect(text).toContain('n/a');
    expect(text).not.toContain('1 : -');
  });

  it('scales the lot multiplier from the base lots and back again', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 2, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130, priceSource: 'live' },
    ]);
    page.expiry = null; // keeps the debounced server refresh from firing in the test

    page.applyMultiplier(3);
    expect(page.legs.map((l) => l.lots)).toEqual([6, 3]);

    page.applyMultiplier(10);
    expect(page.legs.map((l) => l.lots)).toEqual([20, 10]);

    // Back to 1x returns to the original lots, not to one lot each.
    page.applyMultiplier(1);
    expect(page.legs.map((l) => l.lots)).toEqual([2, 1]);
  });

  it('reprices every leg when the expiry changes', async () => {
    const quote = vi.spyOn(api, 'getOptionQuote').mockImplementation(async ({ expiry }) => ({
      available: true,
      ltp: expiry === '2026-09-10' ? 40.5 : 121.25,
      iv: 0.118,
      source: 'live',
    }));

    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: null, priceSource: null },
    ]);
    page.expiries = [
      { date: '2026-09-10', calendar_days: 2, label: '10 Sep (2d)', is_weekly: true },
      { date: '2026-09-24', calendar_days: 16, label: '24 Sep (16d)', is_monthly: true },
    ];

    page.expiry = '2026-09-10';
    await page.repriceLegs();
    expect(page.legs[0].price).toBe(40.5);

    page.setExpiry('2026-09-24', false);
    expect(page.expiry).toBe('2026-09-24');
    expect(page.dteMax).toBe(16);

    await page.repriceLegs();
    expect(page.legs[0].price).toBe(121.25);
    expect(quote).toHaveBeenCalledWith(expect.objectContaining({ expiry: '2026-09-24' }));
  });

  it('never sends a browser-chosen contract size to the server', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
    ]);
    page.expiry = '2026-09-24';
    const payload = page.legsPayload();
    expect(payload[0].lot_size).toBeUndefined();
    expect(JSON.stringify(payload)).not.toContain('75');
  });

  it('holds every rupee figure back until the server confirms the contract size', () => {
    const page = deskWithLegs(container, [
      { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210, priceSource: 'live' },
      { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130, priceSource: 'live' },
    ], { lotSize: null, lotSizeSource: null });
    page.renderLegs();
    page.renderMetrics();

    expect(container.querySelector('#leg-why').textContent).toContain('Contract size not confirmed');
    expect(container.querySelector('#net-cost').textContent).toContain('unavailable');
    expect(container.querySelector('#metric-row').textContent).toContain('unavailable');
  });
});

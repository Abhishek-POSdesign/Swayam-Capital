/**
 * The payoff crosshair and the Targets modal.
 *
 * WHAT THESE PROVE
 * ----------------
 * The crosshair reads the SAME maths the curves were drawn from, it never
 * re-renders the graph, and the drag still wins while the pointer is down.
 * "Without moving any component" is his requirement, not a nicety.
 *
 * And the Targets modal turns his boxes into a payload where a blank box is
 * null, which CLEARS a target, and is never zero.
 *
 * The DOM is not the subject here. The test DOM hands out a new synthetic
 * element on every querySelector, so element identity means nothing in it;
 * these exercise the decisions, and the browser proves the delegation.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { PayoffSvgComponent, axisBounds } from '../src/components/payoff-svg.js';
import { TargetsModal, pnlAt, unitsOf, legLabel, isBuy } from '../src/components/targets-modal.js';
import { pnlAt as mathPnlAt } from '../src/modules/options-math.js';

const LEGS = [
  { on: true, direction: 'buy', strike: 24200, option_type: 'CE', price: 34.5, lots: 1 },
  { on: true, direction: 'sell', strike: 23800, option_type: 'CE', price: 109.15, lots: 1 },
];
const SPOT = 23389.25;
const LOT = 65;

/** A hand-made SVG, because the test DOM cannot hold one. */
function fakeSvg() {
  const nodes = new Map();
  const make = (id) => {
    const el = {
      id,
      attrs: {},
      textContent: '',
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return this.attrs[k]; },
    };
    nodes.set(`#${id}`, el);
    return el;
  };
  ['pay-cross', 'pay-cross-x', 'pay-cross-y', 'pay-cross-de', 'pay-cross-dt',
    'pay-cross-xb', 'pay-cross-xt', 'pay-cross-yb', 'pay-cross-yt'].forEach(make);

  const svg = {
    innerHTML: '',
    listeners: {},
    attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
    fire(type, ev) { (this.listeners[type] || []).forEach((fn) => fn(ev)); },
    querySelector(sel) { return nodes.get(sel) || null; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 900, height: 380 }; },
  };
  // The group answers querySelector for its own children too.
  nodes.get('#pay-cross').querySelector = (sel) => nodes.get(sel) || null;
  return { svg, nodes };
}

function mountedPayoff() {
  const { svg, nodes } = fakeSvg();
  const readout = {
    hidden: true,
    parts: {},
    querySelector(sel) {
      this.parts[sel] ||= { textContent: '', className: '' };
      return this.parts[sel];
    },
  };
  const container = {
    innerHTML: '',
    querySelector(sel) {
      if (sel === '#payoff-svg') return svg;
      if (sel === '#payoff-readout') return readout;
      return null;
    },
  };
  const comp = new PayoffSvgComponent(container);
  comp._bindDrag();
  comp._bindCrosshair();
  comp.update({ legs: LEGS, spot: SPOT, lotSize: LOT, ivFor: () => 0.11, dteDays: 19, dteMax: 19 });
  return { comp, svg, nodes, readout };
}

describe('the payoff crosshair', () => {
  beforeEach(() => setupTestDOM());

  it('keeps the geometry the curves were drawn with, and drops it when nothing is drawn', () => {
    const { comp } = mountedPayoff();
    expect(comp._geo).not.toBeNull();
    const { lo, hi } = axisBounds(SPOT);
    expect(comp._geo.lo).toBe(lo);
    expect(comp._geo.hi).toBe(hi);

    // Nothing loaded means no geometry at all, so a hover cannot read a stale
    // mapping and report a profit from a strategy that is no longer on screen.
    comp.update({ legs: [] });
    expect(comp._geo).toBeNull();
  });

  it('reads the same profit the curve was drawn from, at expiry and today', () => {
    const { comp, nodes, readout } = mountedPayoff();
    const opts = { lotSize: LOT, spot: SPOT, ivFor: () => 0.11 };
    const { lo, hi } = axisBounds(SPOT);

    // A point a third of the way across the axis.
    const x = 64 + (900 - 64 - 18) / 3;
    comp._moveCrosshair({ clientX: x });

    const level = Math.round((lo + ((x - 64) / (900 - 64 - 18)) * (hi - lo)) / 5) * 5;
    const expected = mathPnlAt(LEGS, level, 0, opts);
    const expectedToday = mathPnlAt(LEGS, level, 19 / 365, opts);

    // The axis label is the level, in fives.
    expect(nodes.get('#pay-cross-xt').textContent.replace(/,/g, '')).toBe(String(level));
    // And the readout is the same money the curve has at that level.
    expect(readout.parts['#payoff-ro-e'].textContent).toContain(
      Math.abs(Math.round(expected)).toLocaleString('en-IN'),
    );
    expect(readout.parts['#payoff-ro-t'].textContent).toContain(
      Math.abs(Math.round(expectedToday)).toLocaleString('en-IN'),
    );
    expect(readout.hidden).toBe(false);
  });

  it('never re-renders the graph while the pointer moves across it', () => {
    const { comp, svg } = mountedPayoff();
    let renders = 0;
    const real = comp.render.bind(comp);
    comp.render = () => { renders += 1; return real(); };

    svg.fire('pointermove', { clientX: 400 });
    svg.fire('pointermove', { clientX: 500 });
    svg.fire('pointermove', { clientX: 600 });

    // "Without moving any component" is the whole design: the curves, the
    // target marker and both sliders must be exactly where they were.
    expect(renders).toBe(0);
  });

  it('gets out of the way while he is dragging the target', () => {
    const { comp, svg, nodes } = mountedPayoff();
    svg.fire('pointermove', { clientX: 400 });
    expect(nodes.get('#pay-cross').getAttribute('style')).toBe('');

    comp._dragging = true;
    svg.fire('pointermove', { clientX: 500 });
    expect(nodes.get('#pay-cross').getAttribute('style')).toBe('display:none');
  });

  it('hides itself off the plotting area and on leave', () => {
    const { comp, svg, nodes } = mountedPayoff();
    comp._moveCrosshair({ clientX: 400 });
    expect(nodes.get('#pay-cross').getAttribute('style')).toBe('');

    comp._moveCrosshair({ clientX: 10 }); // left of the y axis
    expect(nodes.get('#pay-cross').getAttribute('style')).toBe('display:none');

    comp._moveCrosshair({ clientX: 400 });
    svg.fire('pointerleave', {});
    expect(nodes.get('#pay-cross').getAttribute('style')).toBe('display:none');
  });
});

describe('the Targets modal', () => {
  beforeEach(() => setupTestDOM());

  const position = () => ({
    position_id: '7cd4d017',
    strategy_name: 'Iron Condor',
    net_if_exit_now_inr: -1480,
    rule1_cap_inr: 9711,
    max_profit_inr: 9217,
    targets: { target_profit_inr: null, target_loss_inr: null, loss_source: 'rule1', effective_loss_inr: 9711 },
    legs: [
      { sequence: 1, direction: 'buy', strike: 24200, option_type: 'CE', status: 'open', entry_premium: 34.5, quantity_lots: 1, lot_size: 65, mark: 30.6, mark_side: 'bid' },
      { sequence: 3, direction: 'sell', strike: 23800, option_type: 'CE', status: 'open', entry_premium: 109.15, quantity_lots: 1, lot_size: 65, mark: 98.75, mark_side: 'ask' },
      { sequence: 9, direction: 'sell', strike: 23000, option_type: 'PE', status: 'closed', entry_premium: 40, quantity_lots: 1, lot_size: 65 },
    ],
  });

  const host = () => ({ innerHTML: '', querySelectorAll: () => [], querySelector: () => null });

  it('takes only the open legs, because a squared-off leg cannot reach a target', () => {
    const m = new TargetsModal(host(), {});
    m.open(position());
    expect(m.legs.map((l) => l.sequence)).toEqual([1, 3]);
  });

  it('turns a blank box into null, which clears the target, and never into zero', () => {
    const m = new TargetsModal(host(), {});
    m.open(position());
    m.setLeg(1, 'take', '38');
    m.setLeg(1, 'cut', '');
    m.setLeg(3, 'take', '0');   // a keystroke in an empty box, not a level
    m.setTrade('profit', '7000');
    m.setTrade('loss', '');

    const payload = m.payload();
    expect(payload.legs).toEqual([
      { sequence: 1, target_price: 38, stop_price: null },
      { sequence: 3, target_price: null, stop_price: null },
    ]);
    expect(payload.target_profit_inr).toBe(7000);
    // Blank, so rule 1 stands in on the server. Nothing is invented here.
    expect(payload.target_loss_inr).toBeNull();
  });

  it('reads back what is already saved on the trade', () => {
    const p = position();
    p.legs[0].target_price = 38;
    p.legs[1].stop_price = 160;
    p.targets.target_profit_inr = 7000;
    const m = new TargetsModal(host(), {});
    m.open(p);
    expect(m.draft.get('1').take).toBe('38');
    expect(m.draft.get('3').cut).toBe('160');
    expect(m.tradeProfit).toBe('7000');
    expect(m.tradeLoss).toBe('');
  });

  it('clears everything to blank, which is a save that removes every target', () => {
    const m = new TargetsModal(host(), {});
    m.open(position());
    m.setLeg(1, 'take', '38');
    m.setTrade('profit', '7000');
    m.clearAll();
    const payload = m.payload();
    expect(payload.legs.every((l) => l.target_price === null && l.stop_price === null)).toBe(true);
    expect(payload.target_profit_inr).toBeNull();
    expect(payload.target_loss_inr).toBeNull();
  });

  it('says what a price is worth in rupees on that leg, from the stored units', () => {
    const buy = position().legs[0];
    const sell = position().legs[1];
    // Bought at 34.50, out at 38.00, 65 units.
    expect(pnlAt(buy, 38)).toBeCloseTo((38 - 34.5) * 65, 6);
    // Sold at 109.15, bought back at 50.00, 65 units.
    expect(pnlAt(sell, 50)).toBeCloseTo((109.15 - 50) * 65, 6);
    // Two lots is twice the money.
    expect(pnlAt({ ...buy, quantity_lots: 2 }, 38)).toBeCloseTo((38 - 34.5) * 130, 6);
    // NO LOT SIZE MEANS NO ANSWER. It went from 75 to 65 in January 2026, and a
    // fallback here would misprice every target he ever set.
    expect(unitsOf({ quantity_lots: 1 })).toBeNull();
    expect(pnlAt({ direction: 'buy', entry_premium: 34.5, quantity_lots: 1 }, 38)).toBeNull();
    expect(pnlAt(buy, NaN)).toBeNull();
  });

  it('names a leg the way he says it out loud, and knows which side it is', () => {
    expect(legLabel({ strike: 23800, option_type: 'CE' })).toBe('23,800 CE');
    expect(isBuy({ direction: 'buy' })).toBe(true);
    expect(isBuy({ direction: 'sell' })).toBe(false);
  });

  it('keeps the trade and its legs untouched when the save is refused', async () => {
    let sent = null;
    const m = new TargetsModal(host(), {
      onSave: async (id, payload) => { sent = { id, payload }; throw new Error('This trade is closed.'); },
    });
    m.open(position());
    m.setLeg(1, 'take', '38');
    await m.act('save');

    expect(sent.id).toBe('7cd4d017');
    expect(m.error).toContain('This trade is closed.');
    expect(m.saved).toBeNull();
    expect(m.busy).toBe(false);
    // Still open, so he can correct it and press Save again.
    expect(m.isOpen).toBe(true);
  });

  it('reports back what the server said it saved, in the server’s words', async () => {
    const m = new TargetsModal(host(), {
      onSave: async () => ({ message: 'Targets saved on 1 leg and the whole trade.' }),
    });
    m.open(position());
    await m.act('save');
    expect(m.saved).toContain('Targets saved on 1 leg');
    expect(m.error).toBeNull();
  });
});

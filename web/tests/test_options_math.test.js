import { describe, it, expect } from 'vitest';
import {
  blackScholes,
  greeks,
  entryCost,
  pnlAt,
  unlimitedFlags,
  maxLossProfit,
  breakevens,
  twoSigmaLoss,
  gapLoss,
  netGreeks,
} from '../src/modules/options-math.js';

const LOT = 65; // supplied by the server in the app; a fixture here, never a default
const SPOT = 23779.15;

const bearPutSpread = [
  { on: true, bs: 'B', strike: 23800, type: 'PE', lots: 1, price: 210 },
  { on: true, bs: 'S', strike: 23600, type: 'PE', lots: 1, price: 130 },
];

const nakedShortCall = [{ on: true, bs: 'S', strike: 23900, type: 'CE', lots: 1, price: 95 }];

const opts = (extra = {}) => ({ lotSize: LOT, spot: SPOT, ivFor: () => 0.11, ...extra });

describe('options maths ported from the approved prototype', () => {
  it('values an option at expiry as its intrinsic value', () => {
    expect(blackScholes('CE', 24000, 23800, 0, 0.11)).toBeCloseTo(200, 6);
    expect(blackScholes('PE', 23600, 23800, 0, 0.11)).toBeCloseTo(200, 6);
    expect(blackScholes('CE', 23600, 23800, 0, 0.11)).toBe(0);
  });

  it('prices a call above its intrinsic value while time remains', () => {
    const t = blackScholes('CE', 23800, 23800, 30 / 365, 0.12);
    expect(t).toBeGreaterThan(0);
    expect(t).toBeLessThan(23800);
  });

  it('gives a bought call a positive delta and a bought put a negative one', () => {
    expect(greeks('CE', 23800, 23800, 30 / 365, 0.12).delta).toBeGreaterThan(0);
    expect(greeks('PE', 23800, 23800, 30 / 365, 0.12).delta).toBeLessThan(0);
  });

  it('reads the entry cost of a debit spread as a debit', () => {
    expect(entryCost(bearPutSpread, LOT)).toBeCloseTo((210 - 130) * LOT, 6);
  });

  it('detects an uncapped loss from the structure, not from a sampled minimum', () => {
    expect(unlimitedFlags(nakedShortCall)).toEqual({
      unlimitedUp: true,
      unlimitedDown: false,
      unlimited: true,
    });
    expect(unlimitedFlags(bearPutSpread).unlimited).toBe(false);
  });

  it('caps a bear put spread at the width of its strikes, less the debit', () => {
    const { maxLoss, maxProfit, unlimited } = maxLossProfit(bearPutSpread, opts());
    expect(unlimited).toBe(false);
    expect(maxLoss).toBeCloseTo(80 * LOT, 0);
    expect(maxProfit).toBeCloseTo((200 - 80) * LOT, 0);
  });

  it('finds the breakeven of a bear put spread at the long strike less the debit', () => {
    const bes = breakevens(bearPutSpread, opts());
    expect(bes.length).toBe(1);
    expect(Math.abs(bes[0] - (23800 - 80))).toBeLessThanOrEqual(2);
  });

  it('returns null rather than a number when the contract size is unknown', () => {
    expect(entryCost(bearPutSpread, null)).toBeNull();
    expect(pnlAt(bearPutSpread, SPOT, 0, opts({ lotSize: null }))).toBeNull();
    expect(maxLossProfit(bearPutSpread, opts({ lotSize: null })).maxLoss).toBeNull();
    expect(breakevens(bearPutSpread, opts({ lotSize: null }))).toEqual([]);
  });

  it('returns null rather than a number when a leg has no measured volatility', () => {
    const noIv = opts({ ivFor: () => null });
    expect(pnlAt(bearPutSpread, SPOT, 10 / 365, noIv)).toBeNull();
    expect(netGreeks(bearPutSpread, SPOT, 10 / 365, { lotSize: LOT, ivFor: () => null })).toBeNull();
    // At expiry no volatility is needed, so the same position still values.
    expect(pnlAt(bearPutSpread, SPOT, 0, noIv)).not.toBeNull();
  });

  it('refuses to stress-test against a volatility nobody measured', () => {
    expect(twoSigmaLoss(bearPutSpread, 0, opts({ realizedVol: null }))).toBeNull();
    expect(twoSigmaLoss(bearPutSpread, 0, opts({ realizedVol: 0.055 }))).not.toBeNull();
  });

  it('refuses to run the gap test without a measured average daily move', () => {
    expect(gapLoss(bearPutSpread, 16, opts({ averageDailyMove: null }))).toBeNull();
    expect(gapLoss(bearPutSpread, 16, opts({ averageDailyMove: 80.1 }))).not.toBeNull();
  });
});

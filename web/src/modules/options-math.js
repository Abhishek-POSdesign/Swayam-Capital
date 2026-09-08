/**
 * Option maths for instant feedback in the browser.
 *
 * Ported from the approved Strategy Desk prototype
 * (docs/reference/strategy-desk-prototype.html). The formulas are unchanged;
 * what changed is that nothing here invents an input. Every function takes the
 * contract size, the spot and the volatility as arguments and returns `null`
 * when one of them is missing, so the page can print "unavailable" instead of
 * a plausible-looking number.
 *
 * The server is the authority. These numbers exist so the sliders move without
 * a round trip; whenever /api/strategy/compute or /api/strategy/validate
 * answers, the page shows the server's figures instead.
 */

export const RISK_FREE_RATE = 0.065;

/** Cumulative normal distribution (Abramowitz & Stegun 26.2.17). */
export function cnd(x) {
  const a1 = 0.31938153;
  const a2 = -0.356563782;
  const a3 = 1.781477937;
  const a4 = -1.821255978;
  const a5 = 1.330274429;
  const k = 1 / (1 + 0.2316419 * Math.abs(x));
  const w =
    1 -
    (1 / Math.sqrt(2 * Math.PI)) *
      Math.exp((-x * x) / 2) *
      (a1 * k + a2 * k ** 2 + a3 * k ** 3 + a4 * k ** 4 + a5 * k ** 5);
  return x < 0 ? 1 - w : w;
}

/**
 * Black-Scholes value of one option, per unit of underlying.
 * `v` is the volatility as a fraction (0.11 for 11%), NOT a percentage.
 * At or after expiry, or with no volatility, this is the intrinsic value.
 */
export function blackScholes(type, S, K, T, v, r = RISK_FREE_RATE) {
  if (T <= 0 || !(v > 0)) {
    return type === 'CE' ? Math.max(0, S - K) : Math.max(0, K - S);
  }
  const d1 = (Math.log(S / K) + (r + (v * v) / 2) * T) / (v * Math.sqrt(T));
  const d2 = d1 - v * Math.sqrt(T);
  return type === 'CE'
    ? S * cnd(d1) - K * Math.exp(-r * T) * cnd(d2)
    : K * Math.exp(-r * T) * cnd(-d2) - S * cnd(-d1);
}

/** Per-unit greeks. Theta is per calendar day; vega is per 1 percentage point of IV. */
export function greeks(type, S, K, T, v, r = RISK_FREE_RATE) {
  if (T <= 0 || !(v > 0)) return { delta: 0, gamma: 0, theta: 0, vega: 0 };
  const st = v * Math.sqrt(T);
  const d1 = (Math.log(S / K) + (r + (v * v) / 2) * T) / st;
  const d2 = d1 - st;
  const nd1 = Math.exp((-d1 * d1) / 2) / Math.sqrt(2 * Math.PI);
  const delta = type === 'CE' ? cnd(d1) : cnd(d1) - 1;
  const gamma = nd1 / (S * st);
  const theta =
    (-(S * nd1 * v) / (2 * Math.sqrt(T)) -
      (type === 'CE' ? 1 : -1) * r * K * Math.exp(-r * T) * (type === 'CE' ? cnd(d2) : cnd(-d2))) /
    365;
  const vega = (S * nd1 * Math.sqrt(T)) / 100;
  return { delta, gamma, theta, vega };
}

const sign = (leg) => (leg.bs === 'B' ? 1 : -1);
const active = (legs) => (legs || []).filter((l) => l && l.on);

/**
 * Does every active leg carry what the maths needs?
 * `needIv` is true for any valuation before expiry.
 */
export function inputsReady(legs, { lotSize, spot, needIv = false, ivFor = null }) {
  const on = active(legs);
  if (!on.length) return false;
  if (!lotSize || !spot) return false;
  if (on.some((l) => l.price === null || l.price === undefined || Number.isNaN(l.price))) return false;
  if (needIv) {
    if (!ivFor) return false;
    if (on.some((l) => !(ivFor(l) > 0))) return false;
  }
  return true;
}

/**
 * Value of the whole position at spot S, `T` years from expiry, in rupees.
 * `ivFor(leg)` returns the leg's volatility as a fraction, or null when unknown.
 * Returns null rather than guessing when an input is missing.
 */
export function positionValue(legs, S, T, { lotSize, ivFor }) {
  const on = active(legs);
  if (!on.length || !lotSize) return null;
  let v = 0;
  for (const l of on) {
    let px;
    if (T <= 0) {
      px = l.type === 'CE' ? Math.max(0, S - l.strike) : Math.max(0, l.strike - S);
    } else {
      const iv = ivFor ? ivFor(l) : null;
      if (!(iv > 0)) return null;
      px = blackScholes(l.type, S, l.strike, T, iv);
    }
    v += sign(l) * px * l.lots * lotSize;
  }
  return v;
}

/** What the position cost to open: positive is a debit, negative a credit. */
export function entryCost(legs, lotSize) {
  const on = active(legs);
  if (!on.length || !lotSize) return null;
  let c = 0;
  for (const l of on) {
    if (l.price === null || l.price === undefined || Number.isNaN(l.price)) return null;
    c += sign(l) * l.price * l.lots * lotSize;
  }
  return c;
}

/** Profit or loss at spot S and time T. Null when an input is missing. */
export function pnlAt(legs, S, T, opts) {
  const v = positionValue(legs, S, T, opts);
  const c = entryCost(legs, opts.lotSize);
  if (v === null || c === null) return null;
  return v - c;
}

/**
 * Whether the loss has a ceiling, decided from the structure and never from a
 * sampled minimum: a net short call has no ceiling above, a net short put none
 * below.
 */
export function unlimitedFlags(legs) {
  const on = active(legs);
  let netCall = 0;
  let netPut = 0;
  for (const l of on) {
    if (l.type === 'CE') netCall += sign(l) * l.lots;
    else netPut += sign(l) * l.lots;
  }
  const unlimitedUp = netCall < 0;
  const unlimitedDown = netPut < 0;
  return { unlimitedUp, unlimitedDown, unlimited: unlimitedUp || unlimitedDown };
}

/** Worst loss and best profit at expiry, swept across ±45% of spot. */
export function maxLossProfit(legs, opts) {
  const { unlimited, unlimitedUp, unlimitedDown } = unlimitedFlags(legs);
  const on = active(legs);
  if (!on.length || !opts.lotSize || !opts.spot) {
    return { maxLoss: null, maxProfit: null, unlimited, unlimitedUp, unlimitedDown };
  }
  let lo = Infinity;
  let hi = -Infinity;
  for (let S = opts.spot * 0.55; S <= opts.spot * 1.45; S += 5) {
    const p = pnlAt(legs, S, 0, opts);
    if (p === null) return { maxLoss: null, maxProfit: null, unlimited, unlimitedUp, unlimitedDown };
    if (p < lo) lo = p;
    if (p > hi) hi = p;
  }
  return { maxLoss: -lo, maxProfit: hi, unlimited, unlimitedUp, unlimitedDown };
}

/** Every spot where the expiry payoff crosses zero. */
export function breakevens(legs, opts) {
  if (!active(legs).length || !opts.lotSize || !opts.spot) return [];
  const out = [];
  let prev = pnlAt(legs, opts.spot * 0.55, 0, opts);
  if (prev === null) return [];
  for (let S = opts.spot * 0.55 + 2; S <= opts.spot * 1.45; S += 2) {
    const p = pnlAt(legs, S, 0, opts);
    if (p === null) return [];
    if ((prev < 0 && p >= 0) || (prev > 0 && p <= 0)) out.push(Math.round(S));
    prev = p;
  }
  return out;
}

/**
 * Rule 1, the running loss: the worse of a two-sigma day in either direction.
 * `realizedVol` is the annualised realised volatility as a fraction. Without a
 * measured volatility this returns null; a stress test against an invented
 * volatility is worse than no stress test.
 */
export function twoSigmaLoss(legs, T, opts) {
  const { realizedVol, spot } = opts;
  if (!(realizedVol > 0) || !spot) return null;
  const move = spot * realizedVol * Math.sqrt(1 / 252) * 2;
  const up = pnlAt(legs, spot + move, T, opts);
  const down = pnlAt(legs, spot - move, T, opts);
  if (up === null || down === null) return null;
  return Math.max(0, -Math.min(up, down));
}

/**
 * Rule 2, the overnight gap: NIFTY gaps twice the average daily move either
 * way, valued one session closer to expiry. Null without a measured average.
 */
export function gapLoss(legs, dteDays, opts) {
  const { averageDailyMove, spot } = opts;
  if (!(averageDailyMove > 0) || !spot) return null;
  const gap = averageDailyMove * 2;
  const T = Math.max(0, dteDays - 1) / 365;
  const up = pnlAt(legs, spot + gap, T, opts);
  const down = pnlAt(legs, spot - gap, T, opts);
  if (up === null || down === null) return null;
  return Math.max(0, -Math.min(up, down));
}

/** Net position greeks at a chosen spot and time. Null when any IV is missing. */
export function netGreeks(legs, S, T, { lotSize, ivFor }) {
  const on = active(legs);
  if (!on.length || !lotSize || !S) return null;
  let delta = 0;
  let gamma = 0;
  let theta = 0;
  let vega = 0;
  for (const l of on) {
    const iv = ivFor ? ivFor(l) : null;
    if (!(iv > 0)) return null;
    const g = greeks(l.type, S, l.strike, Math.max(T, 1e-6), iv);
    const q = sign(l) * l.lots * lotSize;
    delta += g.delta * q;
    gamma += g.gamma * q;
    theta += g.theta * q;
    vega += g.vega * q;
  }
  return { delta, gamma, theta, vega };
}

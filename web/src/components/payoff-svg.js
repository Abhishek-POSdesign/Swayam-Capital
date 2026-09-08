/**
 * The payoff graph, drawn as a real SVG to a real scale.
 *
 * Ported from the approved Strategy Desk prototype. Black line is the value at
 * expiry, blue line the value on the chosen date, which still holds time value.
 * Dragging anywhere on the graph moves the target.
 *
 * It draws nothing at all when the maths cannot be done honestly: no contract
 * size, no spot, no price on a leg. In that case it prints why.
 */

import { pnlAt, breakevens, unlimitedFlags } from '../modules/options-math.js';
import { inr, num } from '../utils/display.js';

const W = 900;
const H = 380;
const L = 64;
const R = 18;
const TOP = 16;
const BOT = 44;

/**
 * The x-axis runs from 6% below spot to 6% above, snapped DOWN and UP to
 * whole 50s so it reads in NIFTY strike shapes (23,400, not 23,441), and is
 * labelled every 100 points. He confirmed 100. The labels sit on two
 * staggered rows so ~28 of them fit without colliding. Nothing else about the
 * graph, the drag or the maths changed.
 */
export function axisBounds(spot) {
  return { lo: Math.floor((spot * 0.94) / 50) * 50, hi: Math.ceil((spot * 1.06) / 50) * 50 };
}

export class PayoffSvgComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onTargetChange }
    this.state = {
      legs: [],
      spot: null,
      lotSize: null,
      ivFor: null,
      dteDays: 0,
      dteMax: 0,
      targetSpot: null,
      reason: null,
    };
    this._dragging = false;
  }

  init() {
    if (!this.container) return;
    this.container.innerHTML =
      `<div class="chartwrap"><svg class="pay" id="payoff-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"></svg></div>`;
    this._bindDrag();
    this.render();
  }

  /** main.js calls this on layout and theme changes; it must always exist. */
  retheme() {
    this.render();
  }

  update(patch = {}) {
    this.state = { ...this.state, ...patch };
    this.render();
  }

  _svg() {
    return this.container ? this.container.querySelector('#payoff-svg') : null;
  }

  _bindDrag() {
    const svg = this._svg();
    if (!svg || typeof svg.addEventListener !== 'function') return;
    const set = (ev) => {
      const rect = typeof svg.getBoundingClientRect === 'function' ? svg.getBoundingClientRect() : null;
      if (!rect || !rect.width || !this.state.spot) return;
      const clientX = ev.touches && ev.touches[0] ? ev.touches[0].clientX : ev.clientX;
      const x = ((clientX - rect.left) / rect.width) * W;
      const { lo, hi } = axisBounds(this.state.spot);
      const S = lo + ((x - L) / (W - L - R)) * (hi - lo);
      const clamped = Math.min(hi, Math.max(lo, Math.round(S / 5) * 5));
      if (this.options.onTargetChange) this.options.onTargetChange(clamped);
    };
    svg.addEventListener('pointerdown', (e) => {
      this._dragging = true;
      if (typeof svg.setPointerCapture === 'function' && e.pointerId !== undefined) {
        try { svg.setPointerCapture(e.pointerId); } catch (_) {}
      }
      set(e);
    });
    svg.addEventListener('pointermove', (e) => { if (this._dragging) set(e); });
    svg.addEventListener('pointerup', () => { this._dragging = false; });
    svg.addEventListener('pointercancel', () => { this._dragging = false; });
  }

  render() {
    const svg = this._svg();
    if (!svg) return;
    const { legs, spot, lotSize, ivFor, dteDays, dteMax, targetSpot, reason } = this.state;
    const on = (legs || []).filter((l) => l.on);

    if (!on.length) {
      svg.innerHTML = this._message('Load a strategy to draw its payoff');
      return;
    }
    if (!spot || !lotSize) {
      svg.innerHTML = this._message(
        reason || (!spot ? 'No live NIFTY price, so the payoff cannot be placed' : 'Contract size not confirmed by the server yet'),
      );
      return;
    }

    const opts = { lotSize, spot, ivFor };
    const { lo, hi } = axisBounds(spot);
    const T = (dteDays || 0) / 365;

    const pts = [];
    const ptsT = [];
    let targetCurveOk = true;
    for (let i = 0; i <= 180; i++) {
      const S = lo + ((hi - lo) * i) / 180;
      const expiryPnl = pnlAt(legs, S, 0, opts);
      if (expiryPnl === null) {
        svg.innerHTML = this._message('A leg has no price yet, so there is nothing to draw');
        return;
      }
      pts.push([S, expiryPnl]);
      if (targetCurveOk) {
        const tp = pnlAt(legs, S, T, opts);
        if (tp === null) targetCurveOk = false;
        else ptsT.push([S, tp]);
      }
    }

    const all = pts.concat(targetCurveOk ? ptsT : []).map((p) => p[1]);
    let yMax = Math.max(...all, 0);
    let yMin = Math.min(...all, 0);
    const pad = (yMax - yMin) * 0.16 || 1000;
    yMax += pad;
    yMin -= pad;

    const X = (S) => L + ((S - lo) / (hi - lo)) * (W - L - R);
    const Y = (p) => TOP + ((yMax - p) / (yMax - yMin)) * (H - TOP - BOT);
    const path = (a) => a.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');

    let g = '';
    const steps = 5;
    for (let i = 0; i <= steps; i++) {
      const val = yMin + ((yMax - yMin) * i) / steps;
      const y = Y(val);
      g += `<line x1="${L}" y1="${y.toFixed(1)}" x2="${W - R}" y2="${y.toFixed(1)}" stroke="var(--line)" stroke-width="1"/>`;
      g += `<text x="${L - 8}" y="${(y + 3.5).toFixed(1)}" text-anchor="end" fill="var(--fg-3)" font-family="var(--m)" font-size="10.5">${val >= 0 ? '' : '−'}${Math.abs(Math.round(val)).toLocaleString('en-IN')}</text>`;
    }
    const base = Y(0);
    g += `<line x1="${L}" y1="${base.toFixed(1)}" x2="${W - R}" y2="${base.toFixed(1)}" stroke="var(--line-2)" stroke-width="1.5"/>`;
    let tick = 0;
    for (let S = lo; S <= hi; S += 100, tick++) {
      const x = X(S).toFixed(1);
      g += `<line x1="${x}" y1="${H - BOT}" x2="${x}" y2="${H - BOT + 4}" stroke="var(--line-2)" stroke-width="1"/>`;
      const y = tick % 2 === 0 ? H - 24 : H - 10;
      g += `<text x="${x}" y="${y}" text-anchor="middle" fill="var(--fg-3)" font-family="var(--m)" font-size="10">${num(S)}</text>`;
    }

    g += `<defs>
        <clipPath id="pay-above"><rect x="${L}" y="${TOP}" width="${W - L - R}" height="${Math.max(0, base - TOP)}"/></clipPath>
        <clipPath id="pay-below"><rect x="${L}" y="${base}" width="${W - L - R}" height="${Math.max(0, H - BOT - base)}"/></clipPath>
      </defs>
      <path d="${path(pts)}L${X(hi)},${base}L${X(lo)},${base}Z" fill="var(--up)" opacity=".13" clip-path="url(#pay-above)"/>
      <path d="${path(pts)}L${X(hi)},${base}L${X(lo)},${base}Z" fill="var(--down)" opacity=".13" clip-path="url(#pay-below)"/>`;

    g += `<line x1="${X(spot)}" y1="${TOP}" x2="${X(spot)}" y2="${H - BOT}" stroke="var(--fg-3)" stroke-width="1" stroke-dasharray="2 4"/>
      <text x="${X(spot) + 5}" y="${TOP + 11}" fill="var(--fg-3)" font-family="var(--m)" font-size="10">spot ${num(spot)}</text>`;

    if (targetCurveOk) {
      g += `<path d="${path(ptsT)}" fill="none" stroke="var(--info)" stroke-width="2" opacity=".85"/>`;
    }
    g += `<path d="${path(pts)}" fill="none" stroke="var(--fg)" stroke-width="2.2"/>`;

    breakevens(legs, opts)
      .filter((b) => b > lo && b < hi)
      .forEach((b) => {
        g += `<circle cx="${X(b).toFixed(1)}" cy="${base.toFixed(1)}" r="3.5" fill="var(--fg)"/>
          <text x="${X(b).toFixed(1)}" y="${(base - 9).toFixed(1)}" text-anchor="middle" fill="var(--fg-2)" font-family="var(--m)" font-size="10">${num(b)}</text>`;
      });

    const tgt = targetSpot;
    if (tgt && tgt > lo && tgt < hi) {
      const py = pnlAt(legs, tgt, targetCurveOk ? T : 0, opts);
      if (py !== null) {
        g += `<line x1="${X(tgt).toFixed(1)}" y1="${TOP}" x2="${X(tgt).toFixed(1)}" y2="${H - BOT}" stroke="var(--info)" stroke-width="1.5"/>
          <circle cx="${X(tgt).toFixed(1)}" cy="${Y(py).toFixed(1)}" r="5.5" fill="var(--info)" stroke="var(--panel)" stroke-width="2"/>
          <rect x="${(X(tgt) - 56).toFixed(1)}" y="${(Y(py) - 32).toFixed(1)}" width="112" height="21" rx="4" fill="${py >= 0 ? 'var(--up)' : 'var(--down)'}"/>
          <text x="${X(tgt).toFixed(1)}" y="${(Y(py) - 17).toFixed(1)}" text-anchor="middle" fill="#fff" font-family="var(--m)" font-size="11.5" font-weight="600">${inr(py)}</text>`;
      }
    }

    const away = Math.max(0, (dteMax || 0) - (dteDays || 0));
    g += `<text x="${L}" y="${TOP + 11}" fill="var(--fg-2)" font-family="var(--m)" font-size="10">— at expiry</text>`;
    g += targetCurveOk
      ? `<text x="${L + 86}" y="${TOP + 11}" fill="var(--info)" font-family="var(--m)" font-size="10">— ${away === 0 ? 'today' : `in ${away}d`}</text>`
      : `<text x="${L + 86}" y="${TOP + 11}" fill="var(--fg-3)" font-family="var(--m)" font-size="10">on-date curve unavailable, no measured IV</text>`;

    svg.innerHTML = g;
    const { unlimited } = unlimitedFlags(legs);
    if (this.options.onRendered) this.options.onRendered({ unlimited, targetCurveOk });
  }

  _message(text) {
    return `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="var(--fg-3)" font-family="var(--f)" font-size="15">${text}</text>`;
  }
}

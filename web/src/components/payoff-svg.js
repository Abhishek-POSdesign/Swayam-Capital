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
    // What the last render drew, so the crosshair can answer without redrawing
    // anything. Null until the first successful render.
    this._geo = null;
  }

  init() {
    if (!this.container) return;
    this.container.innerHTML =
      `<div class="chartwrap"><svg class="pay" id="payoff-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"></svg>
        <div class="payoff-readout" id="payoff-readout" hidden aria-hidden="true">
          <span class="k">NIFTY</span><span class="v small" id="payoff-ro-s"></span>
          <span class="k">At expiry</span><span class="v" id="payoff-ro-e"></span>
          <span class="k">Today</span><span class="v small" id="payoff-ro-t"></span>
        </div></div>`;
    this._bindDrag();
    this._bindCrosshair();
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
      this._geo = null;
      this._hideCrosshair();
      return;
    }
    if (!spot || !lotSize) {
      svg.innerHTML = this._message(
        reason || (!spot ? 'No live NIFTY price, so the payoff cannot be placed' : 'Contract size not confirmed by the server yet'),
      );
      this._geo = null;
      this._hideCrosshair();
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
        this._geo = null;
        this._hideCrosshair();
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

    // The crosshair's elements, drawn once and then only moved. Nothing on a
    // timer and nothing about hovering may ever call render() again.
    g += `<g id="pay-cross" style="display:none" pointer-events="none">
      <line id="pay-cross-x" y1="${TOP}" y2="${H - BOT}" stroke="var(--fg-3)" stroke-width="1" stroke-dasharray="3 3"/>
      <line id="pay-cross-y" x1="${L}" x2="${W - R}" stroke="var(--fg-3)" stroke-width="1" stroke-dasharray="3 3"/>
      <circle id="pay-cross-de" r="4.5" fill="var(--fg)" stroke="var(--panel)" stroke-width="2"/>
      <circle id="pay-cross-dt" r="4.5" fill="var(--info)" stroke="var(--panel)" stroke-width="2"/>
      <rect id="pay-cross-xb" y="${H - BOT + 4}" width="74" height="18" rx="4" fill="var(--fg)"/>
      <text id="pay-cross-xt" y="${H - BOT + 17}" text-anchor="middle" fill="var(--bg)" font-family="var(--m)" font-size="11" font-weight="700"></text>
      <rect id="pay-cross-yb" x="2" width="60" height="18" rx="4" fill="var(--fg)"/>
      <text id="pay-cross-yt" x="32" text-anchor="middle" fill="var(--bg)" font-family="var(--m)" font-size="11" font-weight="700"></text>
    </g>`;

    svg.innerHTML = g;
    // Everything the crosshair needs to answer a hover, captured from the
    // render that just happened. Held rather than recomputed so a mouse moving
    // across the graph costs no maths beyond the two curve points it asks for.
    this._geo = { lo, hi, X, Y, T, opts, legs, targetCurveOk };
    this._hideCrosshair();
    const { unlimited } = unlimitedFlags(legs);
    if (this.options.onRendered) this.options.onRendered({ unlimited, targetCurveOk });
  }

  /**
   * THE CROSSHAIR. His words, 2026-09-10: "When I hover the mouse around the
   * payoff graph, it must have a crosshair... the vertical line will have the
   * Nifty level, and the horizontal line will have my profit and loss. Without
   * moving any component."
   *
   * "Without moving any component" is the whole design. This handler NEVER
   * calls render(). It sets attributes on elements the last render already put
   * in the SVG, and toggles one overlay. So the curves, the target marker, the
   * breakevens, the drag and both sliders are exactly where they were, and a
   * mouse crossing the graph cannot cost a repaint.
   *
   * THE DRAG STILL WINS. While the pointer is down the crosshair hides and
   * gets out of the way, because dragging the target is the thing he meant to
   * do and a line following his finger would only be noise.
   */
  _bindCrosshair() {
    const svg = this._svg();
    if (!svg || typeof svg.addEventListener !== 'function') return;

    svg.addEventListener('pointermove', (ev) => {
      if (this._dragging) { this._hideCrosshair(); return; }
      this._moveCrosshair(ev);
    });
    svg.addEventListener('pointerleave', () => this._hideCrosshair());
    svg.addEventListener('pointerdown', () => this._hideCrosshair());
  }

  _readout() {
    return this.container ? this.container.querySelector('#payoff-readout') : null;
  }

  _hideCrosshair() {
    const svg = this._svg();
    const g = svg && svg.querySelector ? svg.querySelector('#pay-cross') : null;
    if (g && g.setAttribute) g.setAttribute('style', 'display:none');
    const ro = this._readout();
    if (ro) ro.hidden = true;
  }

  /**
   * The pointer moved. Reads the NIFTY level under it, computes both curves at
   * that level from the SAME maths the curves were drawn with, and writes the
   * answers into elements that already exist.
   */
  _moveCrosshair(ev) {
    const svg = this._svg();
    const geo = this._geo;
    if (!svg || !geo) return;
    const g = svg.querySelector ? svg.querySelector('#pay-cross') : null;
    const ro = this._readout();
    if (!g) return;

    const rect = typeof svg.getBoundingClientRect === 'function' ? svg.getBoundingClientRect() : null;
    if (!rect || !rect.width) return;
    const clientX = ev.touches && ev.touches[0] ? ev.touches[0].clientX : ev.clientX;
    const x = ((clientX - rect.left) / rect.width) * W;
    if (x < L || x > W - R) { this._hideCrosshair(); return; }

    // Levels read in fives, the way a strike ladder does.
    const level = Math.round((geo.lo + ((x - L) / (W - L - R)) * (geo.hi - geo.lo)) / 5) * 5;
    const atExpiry = pnlAt(geo.legs, level, 0, geo.opts);
    if (atExpiry === null) { this._hideCrosshair(); return; }
    const today = geo.targetCurveOk ? pnlAt(geo.legs, level, geo.T, geo.opts) : null;

    const px = geo.X(level);
    const py = geo.Y(atExpiry);

    const set = (sel, attrs) => {
      const el = g.querySelector ? g.querySelector(sel) : null;
      if (!el || !el.setAttribute) return null;
      Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
      return el;
    };

    g.setAttribute('style', '');
    set('#pay-cross-x', { x1: px.toFixed(1), x2: px.toFixed(1) });
    set('#pay-cross-y', { y1: py.toFixed(1), y2: py.toFixed(1) });
    set('#pay-cross-de', { cx: px.toFixed(1), cy: py.toFixed(1) });

    const dotT = g.querySelector ? g.querySelector('#pay-cross-dt') : null;
    if (dotT && dotT.setAttribute) {
      if (today === null) dotT.setAttribute('style', 'display:none');
      else {
        dotT.setAttribute('style', '');
        dotT.setAttribute('cx', px.toFixed(1));
        dotT.setAttribute('cy', geo.Y(today).toFixed(1));
      }
    }

    set('#pay-cross-xb', { x: (px - 37).toFixed(1) });
    const xt = set('#pay-cross-xt', { x: px.toFixed(1) });
    if (xt) xt.textContent = num(level);

    set('#pay-cross-yb', { y: (py - 9).toFixed(1) });
    const yt = set('#pay-cross-yt', { y: (py + 4).toFixed(1) });
    if (yt) yt.textContent = inr(Math.round(atExpiry));

    if (ro) {
      ro.hidden = false;
      const put = (sel, text, tone) => {
        const el = ro.querySelector ? ro.querySelector(sel) : null;
        if (!el) return;
        el.textContent = text;
        if (tone !== undefined) el.className = tone;
      };
      const toneOf = (v) => (v > 0 ? 'v up' : v < 0 ? 'v down' : 'v');
      put('#payoff-ro-s', num(level), 'v small');
      put('#payoff-ro-e', inr(Math.round(atExpiry)), toneOf(atExpiry));
      put(
        '#payoff-ro-t',
        today === null ? 'unavailable' : inr(Math.round(today)),
        today === null ? 'v small na' : `${toneOf(today)} small`,
      );
    }
  }

  _message(text) {
    return `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="var(--fg-3)" font-family="var(--f)" font-size="15">${text}</text>`;
  }
}

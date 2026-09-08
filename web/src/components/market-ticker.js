/**
 * The running ticker that sits across the top of Home and the Strategy Desk.
 *
 * Every item is passed in already resolved. An item with a null value renders
 * the word "unavailable" in muted type: market breadth has no wired source and
 * must say so rather than borrow a number from somewhere else.
 *
 * The list is duplicated so the marquee loops seamlessly, it pauses on hover,
 * and it stops entirely when the reader has asked for reduced motion (handled
 * in swayam-desk.css).
 */

import { escapeHtml } from '../utils/display.js';

export class MarketTickerComponent {
  constructor(container) {
    this.container = container;
    this.items = [];
    this._previous = {}; // label -> last numeric value, for the change flash
    this._run = null;
  }

  /**
   * @param {Array<{label:string, value:string|null, note?:string, dir?:'up'|'down'|'flat', raw?:number}>} items
   *
   * Called every few seconds now that prices move. The marquee element is kept
   * and only its contents replaced, so the scroll does not jump back to the
   * start on every tick. An item whose `raw` number changed flashes.
   */
  render(items) {
    if (Array.isArray(items)) this.items = items;
    if (!this.container) return;
    const one = this.items.map((it) => this._item(it)).join('');
    const run = this._run;
    if (run && run.isConnected && run.parentNode && run.parentNode.parentNode === this.container) {
      run.innerHTML = `${one}${one}`;
      return;
    }
    this.container.innerHTML = `<div class="ticker"><div class="ticker-run">${one}${one}</div></div>`;
    const el = this.container.querySelector('.ticker-run');
    this._run = el && el.isConnected ? el : null;
  }

  _item({ label, value, note, dir, raw }) {
    const missing = value === null || value === undefined || value === '';
    let flash = '';
    if (typeof raw === 'number' && Number.isFinite(raw)) {
      const prev = this._previous[label];
      if (typeof prev === 'number' && prev !== raw) flash = raw > prev ? ' fl-up' : ' fl-down';
      this._previous[label] = raw;
    }
    const colour = missing
      ? 'var(--fg-3)'
      : dir === 'down'
        ? 'var(--down)'
        : dir === 'up'
          ? 'var(--up)'
          : 'var(--fg)';
    const shown = missing ? 'unavailable' : escapeHtml(value);
    return (
      `<span class="tk"><i>${escapeHtml(label)}</i>` +
      `<b class="tv${flash}" style="color:${colour}${missing ? ';font-style:italic' : ''}">${shown}</b>` +
      `${note ? `<i>${escapeHtml(note)}</i>` : ''}</span>`
    );
  }
}

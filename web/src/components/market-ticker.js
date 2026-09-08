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
  }

  /**
   * @param {Array<{label:string, value:string|null, note?:string, dir?:'up'|'down'|'flat'}>} items
   */
  render(items) {
    if (Array.isArray(items)) this.items = items;
    if (!this.container) return;
    const one = this.items.map((it) => this._item(it)).join('');
    this.container.innerHTML = `<div class="ticker"><div class="ticker-run">${one}${one}</div></div>`;
  }

  _item({ label, value, note, dir }) {
    const missing = value === null || value === undefined || value === '';
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
      `<b style="color:${colour}${missing ? ';font-style:italic' : ''}">${shown}</b>` +
      `${note ? `<i>${escapeHtml(note)}</i>` : ''}</span>`
    );
  }
}

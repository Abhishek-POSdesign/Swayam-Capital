/**
 * Whether the numbers on this screen are real and current, always on show.
 *
 * His question, 2026-09-08: "If, while live in the market, FYERS stops giving
 * me the data, how will I work, and how will I know?"
 *
 * This is the "how will I know". It is deliberately visible when everything is
 * fine, not only when something breaks, because a warning that only appears on
 * failure is a warning he has never seen before and will not trust the first
 * time it matters. Green while live, amber when behind or after the close, red
 * when there is nothing. The red state also says what to do.
 *
 * It never invents a state. Everything it shows comes from
 * `/api/market/data-health`, which reads the two feeds directly.
 */

import { api } from '../api.js';

const POLL_MS = 15000;

const LABEL = {
  live: 'LIVE',
  closing: 'CLOSED',
  delayed: 'BEHIND',
  unavailable: 'NO DATA',
};

export class DataHealthStrip {
  constructor(container, options = {}) {
    this.container = container;
    this.pollMs = options.pollMs || POLL_MS;
    this.fetchHealth = options.fetchHealth || (() => api.getDataHealth());
    // The desk uses this to slow its own re-quoting once the market shuts.
    this.onHealth = options.onHealth || null;
    this.timer = null;
    this.health = null;
    this.error = null;
  }

  async init() {
    await this.refresh();
    if (typeof setInterval === 'function' && !this.timer) {
      this.timer = setInterval(() => this.refresh(), this.pollMs);
      if (this.timer && typeof this.timer.unref === 'function') this.timer.unref();
    }
  }

  async refresh() {
    try {
      this.health = await this.fetchHealth();
      this.error = null;
    } catch (err) {
      // The check itself failing is its own kind of not-knowing, and is shown
      // as such rather than left looking healthy.
      this.health = null;
      this.error = err && err.message ? err.message : 'the data check could not run';
    }
    this.render();
    if (this.onHealth) {
      try { this.onHealth(this.health, this.state()); } catch (err) { console.warn('health listener threw:', err); }
    }
    return this.health;
  }

  /** The state actually being shown, for tests and for the desk to read. */
  state() {
    if (this.error) return 'unavailable';
    return (this.health && this.health.state) || 'unavailable';
  }

  render() {
    if (!this.container) return;
    const state = this.state();
    const h = this.health;

    const headline = this.error
      ? 'Cannot tell whether prices are live'
      : (h && h.headline) || 'No prices from FYERS';
    const detail = this.error ? this.error : (h && h.detail) || '';
    const action = this.error
      ? 'Reload the page. If it persists, the service is not answering.'
      : (h && h.action) || '';

    const age =
      h && h.sources && h.sources.chain && typeof h.sources.chain.age_seconds === 'number'
        ? `${Math.round(h.sources.chain.age_seconds)}s old`
        : '';

    this.container.innerHTML = `
      <div class="sw-health sw-health--${state}" role="status" aria-live="polite">
        <span class="sw-health__dot" aria-hidden="true"></span>
        <span class="sw-health__label">${LABEL[state] || 'NO DATA'}</span>
        <span class="sw-health__headline">${escapeHtml(headline)}</span>
        ${age ? `<span class="sw-health__age">${escapeHtml(age)}</span>` : ''}
        ${detail ? `<span class="sw-health__detail">${escapeHtml(detail)}</span>` : ''}
        ${action ? `<span class="sw-health__action">${escapeHtml(action)}</span>` : ''}
      </div>
    `;
  }

  destroy() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.container) this.container.innerHTML = '';
  }
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export default DataHealthStrip;

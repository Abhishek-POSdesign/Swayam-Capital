/**
 * Live NIFTY spot ticks for every page.
 *
 * Two parts:
 *
 * 1. `spotFeed`, a tiny in-page bus. The socket client publishes each tick to
 *    it; Home and the Strategy Desk subscribe in `init()` and unsubscribe in
 *    `destroy()`. It is what lets the sidebar price, the ticker and the desk
 *    spot all move from ONE stream instead of each page polling on its own.
 *
 * 2. `SpotWebSocketClient`, the socket to `/ws/spot`, with a watchdog. Until
 *    round 2 the socket opened, answered ping with pong, and never received a
 *    frame, because the server never sent one. A socket that is open but silent
 *    must not freeze the screen: if no frame arrives within 10 seconds the
 *    client falls back to a 3-second REST poll, and stops polling again the
 *    moment frames resume.
 *
 * Nothing here invents a price. A tick is a number the server sent, or the
 * REST endpoint returned, or nothing.
 */

import { api } from '../api.js';

const WATCHDOG_MS = 10000;
const REST_POLL_MS = 3000;

function makeFeed() {
  const listeners = new Set();
  let last = null; // { spot, asOf, source }
  return {
    /** Returns an unsubscribe function. */
    subscribe(fn) {
      listeners.add(fn);
      if (last) {
        try { fn(last.spot, last); } catch (_) {}
      }
      return () => listeners.delete(fn);
    },
    publish(spot, meta = {}) {
      if (typeof spot !== 'number' || !Number.isFinite(spot) || spot <= 0) return;
      last = { spot, asOf: meta.asOf || new Date().toISOString(), source: meta.source || 'unknown' };
      listeners.forEach((fn) => {
        try { fn(spot, last); } catch (err) { console.warn('spot listener threw:', err); }
      });
    },
    last() { return last; },
    listenerCount() { return listeners.size; },
  };
}

export const spotFeed = makeFeed();

export class SpotWebSocketClient {
  constructor(onTick, options = {}) {
    this.onTick = onTick;
    this.ws = null;
    this.reconnectTimeout = null;
    this.watchdogTimer = null;
    this.restTimer = null;
    this.lastFrameAt = null;
    this.framesReceived = 0;
    this.mode = 'idle'; // 'socket' when frames flow, 'rest' when polling instead
    this.watchdogMs = options.watchdogMs || WATCHDOG_MS;
    this.restPollMs = options.restPollMs || REST_POLL_MS;
    this.fetchSpot = options.fetchSpot || (() => api.getNiftySpot());
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/spot`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('Connected to spot WebSocket stream; waiting for the first frame.');
        this._armWatchdog();
      };

      this.ws.onmessage = (event) => {
        let data = null;
        try {
          data = JSON.parse(event.data);
        } catch (e) {
          return; // pong, or a non-JSON keep-alive
        }
        if (data && typeof data.spot === 'number') {
          this._frameArrived(data.spot, { asOf: data.as_of, source: data.source || 'websocket' });
        }
      };

      this.ws.onclose = () => {
        console.warn('Spot WebSocket closed. Reconnecting in 3s...');
        this._startRestPolling('socket closed');
        this.reconnectTimeout = setTimeout(() => this.connect(), 3000);
      };

      this.ws.onerror = (err) => {
        console.warn('Spot WebSocket encountered error:', err);
      };
    } catch (err) {
      console.warn('Could not establish WebSocket, falling back to REST poll:', err);
      this._startRestPolling('socket could not be opened');
    }
    this._armWatchdog();
  }

  _frameArrived(spot, meta) {
    this.framesReceived += 1;
    this.lastFrameAt = Date.now();
    if (this.mode !== 'socket') {
      if (this.mode === 'rest') console.log('Spot frames are arriving on the socket again; REST poll stopped.');
      this.mode = 'socket';
    }
    this._stopRestPolling();
    this._armWatchdog();
    this._deliver(spot, meta);
  }

  _deliver(spot, meta) {
    spotFeed.publish(spot, meta);
    if (this.onTick) {
      try { this.onTick(spot, meta); } catch (err) { console.warn('onTick threw:', err); }
    }
  }

  _armWatchdog() {
    if (typeof setTimeout !== 'function') return;
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    this.watchdogTimer = setTimeout(() => {
      this._startRestPolling(`no frame within ${Math.round(this.watchdogMs / 1000)} s`);
    }, this.watchdogMs);
    if (this.watchdogTimer && typeof this.watchdogTimer.unref === 'function') this.watchdogTimer.unref();
  }

  _startRestPolling(reason) {
    if (this.restTimer) return;
    this.mode = 'rest';
    console.warn(`Spot socket is silent (${reason}); polling REST every ${this.restPollMs / 1000} s instead.`);
    const poll = async () => {
      try {
        const res = await this.fetchSpot();
        if (res && typeof res.spot === 'number') {
          this._deliver(res.spot, { asOf: res.as_of, source: 'REST poll (socket silent)' });
        }
      } catch (_) {
        // A failed poll is a missing tick, never an invented one.
      }
    };
    poll();
    this.restTimer = setInterval(poll, this.restPollMs);
    if (this.restTimer && typeof this.restTimer.unref === 'function') this.restTimer.unref();
  }

  _stopRestPolling() {
    if (this.restTimer) {
      clearInterval(this.restTimer);
      this.restTimer = null;
    }
  }

  disconnect() {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    this._stopRestPolling();
    if (this.ws) {
      this.ws.onclose = null; // a deliberate close must not schedule a reconnect
      this.ws.close();
    }
    this.mode = 'idle';
  }
}

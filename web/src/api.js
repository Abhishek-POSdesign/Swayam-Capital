import {
  executionKeyFor,
  releaseAllExecutionKeys,
  releaseExecutionKey,
} from './utils/idempotency.js';
/**
 * API client wrapper for Swayam Capital backend.
 */

const BASE_URL = '';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  try {
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: response.statusText };
      }
      const err = new Error(errorData.detail?.error || errorData.detail || `Request failed with status ${response.status}`);
      // The structured detail travels with the error. The execution ticket
      // reads `refused_legs` from it to show every leg that could not fill,
      // rather than only the first sentence.
      err.status = response.status;
      err.detail = errorData.detail;
      throw err;
    }
    return await response.json();
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

/**
 * Sends a trade and manages its execution key.
 *
 * The key belongs to the TRADE, so a retry of the same trade reuses it and
 * cannot open a second position, while a genuinely different trade gets its
 * own. On a final answer the key is released, so storage does not fill with
 * spent keys.
 *
 * If the server still says the key is spent, that answer is final and the
 * trade was NOT executed: the payload hash it holds differs from the one just
 * sent. Every stored key is cleared and the trade is sent once more with a
 * fresh one, because the alternative is what happened to him on 2026-09-09,
 * which was being unable to trade at all with no way out from the screen.
 */
async function submitTrade(path, payload, ticketId) {
  const body = {
    ...payload,
    idempotency_key: payload.idempotency_key || executionKeyFor(ticketId, payload),
  };

  try {
    const res = await request(path, { method: 'POST', body: JSON.stringify(body) });
    releaseExecutionKey(ticketId, payload);
    return res;
  } catch (err) {
    const message = String((err && err.message) || err);
    if (!/already been used for a different trade/i.test(message)) throw err;

    releaseAllExecutionKeys();
    const retry = {
      ...payload,
      idempotency_key: executionKeyFor(ticketId, payload),
    };
    const res = await request(path, { method: 'POST', body: JSON.stringify(retry) });
    releaseExecutionKey(ticketId, payload);
    return res;
  }
}

export const api = {
  getHealth: () => request('/health'),
  getRules: (forceReload = false) => request(`/api/rules?force_reload=${forceReload}`),
  getNiftySpot: () => request('/api/nifty/spot'),
  getOptionChain: (expiry, strikeCount = 20) =>
    request(`/api/option-chain?expiry=${expiry}&strike_count=${strikeCount}`),
  getStrategyPreset: (name, expiry, spot, farExpiry = null) => {
    let url = `/api/strategy/preset?name=${name}&expiry=${expiry}&spot=${spot}`;
    if (farExpiry) url += `&far_expiry=${farExpiry}`;
    return request(url, { method: 'POST' });
  },
  computeStrategy: (payload) =>
    request('/api/strategy/compute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  validateStrategy: (payload) =>
    request('/api/strategy/validate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  // A trade carries an execution key so a double click, or a retry after a
  // lost response, cannot open a second position. The caller passes a stable
  // ticketId; the key is generated once for it and reused on every retry.
  executeTrade: (payload, ticketId = 'default') =>
    submitTrade('/api/execute', payload, ticketId),
  getPositions: (status = 'open') => request(`/api/positions?status=${status}`),
  getPositionsLive: () => request('/api/positions/live'),
  // Has paper trading begun. One timestamp, set by a script only he runs.
  getPhase: () => request('/api/phase'),
  closePosition: (positionId, payload) =>
    request(`/api/positions/${positionId}/close`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getTodayReadiness: () => request('/api/readiness/today'),
  getReadinessKPIs: () => request('/api/readiness/kpis'),
  logReadiness: (payload) =>
    request('/api/readiness/log', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  reconcileReadiness: () => request('/api/readiness/reconcile', { method: 'POST' }),
  getNiftyCandles: (timeframe = '1d') => request(`/api/market/nifty/candles?timeframe=${timeframe}`),
  getVixHistory: (days = 365) => request(`/api/market/vix/history?days=${days}`),
  getOptionQuote: ({ strike, expiry, type, symbol = 'NSE:NIFTY50-INDEX' }) =>
    request(`/api/market/option/quote?strike=${strike}&expiry=${expiry}&type=${type}&symbol=${symbol}`),
  getExpiries: () => request('/api/market/expiries'),
  // Whether the prices on screen are live, old, or missing, and why. Read on a
  // slow timer by the data-health strip, so a broker outage is never silent.
  getDataHealth: () => request('/api/market/data-health'),
  previewOrder: (payload) =>
    request('/api/execute/preview-order', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  executeMultiLeg: (payload, ticketId = 'default-multi') =>
    submitTrade('/api/execute/multi-leg', payload, ticketId),
  // "Execute one by one": the first leg opens the trade, every later leg joins
  // it here. Same execution key rule, so a retry cannot add a leg twice.
  addLegToPosition: (positionId, payload, ticketId = 'add-leg') =>
    submitTrade(`/api/positions/${positionId}/legs`, payload, ticketId),
  // A leg squared off on its own, inside a trade that stays open. Same
  // execution key rule as a send: one press, one exit.
  exitLeg: (positionId, sequence, payload, ticketId = 'exit-leg') =>
    submitTrade(`/api/positions/${positionId}/legs/${sequence}/exit`, payload, ticketId),
  // Close one leg and open its opposite, in one request, under one key.
  reverseLeg: (positionId, sequence, payload, ticketId = 'reverse-leg') =>
    submitTrade(`/api/positions/${positionId}/legs/${sequence}/reverse`, payload, ticketId),
  // His own name for a trade, or an empty one to hand the naming back to the
  // structure. Touches the name and nothing else.
  renamePosition: (positionId, name) =>
    request(`/api/positions/${positionId}/name`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  // What he wants a trade to tell him. It moves no order, no fill and no
  // charge; a reached target lights Home up and waits for him.
  setPositionTargets: (positionId, payload) =>
    request(`/api/positions/${positionId}/targets`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  detectNakedShorts: (atTime = '15:20') =>
    request(`/api/positions/naked-shorts?at_time=${encodeURIComponent(atTime)}`),

  // BUILD B. His open orders: a limit the book has not reached, waiting for
  // it. Read, re-price and cancel. None of these is a trade; a resting order
  // becomes one only when the watcher fills it.
  getOrders: (date = 'today') => request(`/api/orders?date=${encodeURIComponent(date)}`),
  // The price and nothing else. The order keeps its id and its place.
  modifyOrder: (orderId, limitPrice) =>
    request(`/api/orders/${orderId}`, {
      method: 'PATCH',
      body: JSON.stringify({ limit_price: limitPrice }),
    }),
  cancelOrder: (orderId) => request(`/api/orders/${orderId}`, { method: 'DELETE' }),
  getSessionContextSummary: (sessionId) =>
    request(`/api/ai/session/${sessionId}/context-summary`),
  getJournalTrades: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return request(`/api/journal/trades${qs ? `?${qs}` : ''}`);
  },
  getJournalTradeDetail: (positionId) => request(`/api/journal/trade/${positionId}`),
  getJournalAnalytics: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, v);
    });
    const qs = q.toString();
    return request(`/api/journal/analytics${qs ? `?${qs}` : ''}`);
  },
  generateLesson: (positionId) => request(`/api/lessons/generate/${positionId}`, { method: 'POST' }),
  updateLesson: (lessonId, lessonText) =>
    request(`/api/lessons/${lessonId}`, {
      method: 'PUT',
      body: JSON.stringify({ lesson_text: lessonText }),
    }),
  sendChatMessageWithImage: async (sessionId, text, imageBlob, filename = 'screenshot.png') => {
    const formData = new FormData();
    formData.append('content', text || '');
    if (imageBlob) {
      formData.append('image', imageBlob, filename);
    }
    const response = await fetch(`${BASE_URL}/api/ai/conversations/${sessionId}/messages`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}`;
      try {
        const errJson = await response.json();
        errorDetail = errJson.detail || errorDetail;
      } catch (_) {}
      throw new Error(errorDetail);
    }
    return response;
  },
  getSoFarToday: () => request('/api/home/so-far-today'),
  generateSoFarToday: (force = false) => request(`/api/home/so-far-today?force=${force}`, { method: 'POST' }),
  getNiftySnapshot: (refresh = false) => request(`/api/home/nifty-snapshot?refresh=${refresh}`),
  getBackupAge: () => request('/api/home/backup-age'),
  getMacroEvents: (highlightedOnly = true) => request(`/api/macro/events?highlighted_only=${highlightedOnly}`),
  // Live capital and the caps derived from it. The home page shows the four
  // rules in rupees, and every one of them is a percentage of this balance.
  getRiskCapital: () => request('/api/risk/capital'),
  registerDevice: (deviceToken, browserUa = null, platform = 'web') =>
    request('/api/notifications/register-device', {
      method: 'POST',
      body: JSON.stringify({ device_token: deviceToken, browser_ua: browserUa, platform }),
    }),
};


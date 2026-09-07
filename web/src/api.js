import { executionKeyFor } from './utils/idempotency.js';
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
      throw new Error(errorData.detail?.error || errorData.detail || `Request failed with status ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
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
    request('/api/execute', {
      method: 'POST',
      body: JSON.stringify({
        ...payload,
        idempotency_key: payload.idempotency_key || executionKeyFor(ticketId),
      }),
    }),
  getPositions: (status = 'open') => request(`/api/positions?status=${status}`),
  getPositionsLive: () => request('/api/positions/live'),
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
  previewOrder: (payload) =>
    request('/api/execute/preview-order', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  executeMultiLeg: (payload, ticketId = 'default-multi') =>
    request('/api/execute/multi-leg', {
      method: 'POST',
      body: JSON.stringify({
        ...payload,
        idempotency_key: payload.idempotency_key || executionKeyFor(ticketId),
      }),
    }),
  detectNakedShorts: (atTime = '15:20') =>
    request(`/api/positions/naked-shorts?at_time=${encodeURIComponent(atTime)}`),
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
  archiveTestTrades: () => request('/api/journal/archive-test-trades', { method: 'POST' }),
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
  getMacroEvents: (highlightedOnly = true) => request(`/api/macro/events?highlighted_only=${highlightedOnly}`),
  registerDevice: (deviceToken, browserUa = null, platform = 'web') =>
    request('/api/notifications/register-device', {
      method: 'POST',
      body: JSON.stringify({ device_token: deviceToken, browser_ua: browserUa, platform }),
    }),
};


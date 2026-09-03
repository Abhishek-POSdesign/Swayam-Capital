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
  executeTrade: (payload) =>
    request('/api/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getPositions: (status = 'open') => request(`/api/positions?status=${status}`),
  getTodayReadiness: () => request('/api/readiness/today'),
  logReadiness: (payload) =>
    request('/api/readiness/log', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  reconcileReadiness: () => request('/api/readiness/reconcile', { method: 'POST' }),
};

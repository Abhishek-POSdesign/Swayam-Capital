/**
 * Display helpers that refuse to invent a number.
 *
 * `formatINR` in utils/format.js turns null into "₹0", which reads as a real
 * zero balance. These helpers turn a missing value into the word "unavailable"
 * instead, which is the rule this repository is built around.
 */

export const UNAVAILABLE = 'unavailable';

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

/** Rupees, Indian grouping, no decimals. Null-safe: missing means unavailable. */
export function inr(v) {
  if (!isNum(v)) return null;
  return `${v < 0 ? '-' : ''}₹${Math.round(Math.abs(v)).toLocaleString('en-IN')}`;
}

/** A plain number with Indian grouping. */
export function num(v, decimals = 0) {
  if (!isNum(v)) return null;
  return v.toLocaleString('en-IN', {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  });
}

/** A value already expressed in percent (1.74 means 1.74%). Never multiplied again. */
export function pct(v, decimals = 2) {
  if (!isNum(v)) return null;
  return `${v >= 0 ? '' : ''}${v.toFixed(decimals)}%`;
}

export function signedPct(v, decimals = 2) {
  if (!isNum(v)) return null;
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
}

/** Wraps a formatted value, or renders the honest unavailable marker. */
export function orNA(formatted, reason = null) {
  if (formatted === null || formatted === undefined || formatted === '') {
    return `<span class="na" ${reason ? `title="${escapeHtml(reason)}"` : ''}>${UNAVAILABLE}</span>`;
  }
  return formatted;
}

/** "13:42:07" in IST from an ISO timestamp; null when there is no timestamp. */
export function istTime(iso, withSeconds = true) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    ...(withSeconds ? { second: '2-digit' } : {}),
  });
}

/**
 * The class that flashes a value green or red for about 400 ms when it has
 * changed since the last render. `store` is a plain object the caller keeps
 * per page; the previous value is remembered there. A first render, a missing
 * value or an unchanged value flashes nothing. The animation itself lives in
 * swayam-desk.css and is switched off under prefers-reduced-motion.
 */
export function flashFor(store, key, value) {
  if (!store) return '';
  const prev = store[key];
  store[key] = value;
  if (!isNum(value) || !isNum(prev) || prev === value) return '';
  return value > prev ? ' fl-up' : ' fl-down';
}

export function escapeHtml(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

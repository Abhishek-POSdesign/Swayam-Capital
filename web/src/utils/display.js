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

export function escapeHtml(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

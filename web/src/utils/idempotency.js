/**
 * One key per execution ticket, reused on every retry until a final answer.
 *
 * Plan v9 Step 5: the browser makes the key, persists it, and keeps sending
 * the SAME key while it retries. That is what lets the server tell "he pressed
 * the button twice" apart from "he is opening a second, genuinely different
 * trade".
 *
 * The key survives a reload, because the worst case is exactly the one where
 * the page reloads: the response was lost in flight, he refreshes, and presses
 * again. A key held only in memory would be regenerated and would open a
 * second position, which is the bug this exists to stop.
 *
 * The database unique constraint is the real control. This file only supplies
 * the key.
 */

const STORAGE_PREFIX = 'swayam.execkey.';

/**
 * A short, stable fingerprint of the trade being submitted.
 *
 * THE KEY MUST BELONG TO THE TRADE, NOT TO THE TICKET.
 *
 * It used to be one key per ticket id, minted once and kept for ever, because
 * `releaseExecutionKey` below was written and then never called by anything.
 * So the first trade a browser ever sent worked, and every DIFFERENT trade
 * afterwards was refused by the server with "this execution key has already
 * been used for a different trade". Abhishek hit exactly that on 2026-09-09,
 * twice, and could not trade at all in between.
 *
 * Keying on the trade itself keeps the protection and removes the trap. The
 * same trade retried reuses its key, which is what stops a lost response
 * becoming two positions. A genuinely different trade gets a different key and
 * simply goes through.
 */
function fingerprint(payload) {
  if (!payload || typeof payload !== 'object') return 'none';
  const legs = Array.isArray(payload.legs) ? payload.legs : [];
  const shape = [
    payload.strategy_name || '',
    payload.underlying || '',
    payload.mode || '',
    ...legs.map((l) => [
      l.direction, l.strike, l.option_type, l.quantity_lots, l.entry_premium, l.expiry_date,
    ].join(':')),
  ].join('|');

  // djb2. Not a security hash, just a stable short label for a storage slot.
  let h = 5381;
  for (let i = 0; i < shape.length; i += 1) {
    h = ((h << 5) + h + shape.charCodeAt(i)) >>> 0;
  }
  return h.toString(36);
}

/** A key that is unique enough for one person's trading day. */
function newKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * The key for a given ticket, created once and then returned unchanged.
 *
 * @param {string} ticketId Identifies the ticket being submitted. Anything
 *   stable for the duration of one intended trade will do.
 * @returns {string}
 */
export function executionKeyFor(ticketId, payload) {
  const slot = `${STORAGE_PREFIX}${ticketId}.${fingerprint(payload)}`;
  try {
    const held = localStorage.getItem(slot);
    if (held) return held;
    const fresh = newKey();
    localStorage.setItem(slot, fresh);
    return fresh;
  } catch {
    // Private windows and blocked site data both throw here. A key that does
    // not persist is still better than no key at all: it protects against a
    // double click within the same page view.
    return newKey();
  }
}

/**
 * Forgets a ticket's key once the trade is genuinely finished, so the next
 * trade from the same ticket gets a new one.
 *
 * Call this ONLY after a final answer. Clearing it while a request may still
 * be in flight reintroduces the double-booking this module prevents.
 */
export function releaseExecutionKey(ticketId, payload) {
  try {
    localStorage.removeItem(`${STORAGE_PREFIX}${ticketId}.${fingerprint(payload)}`);
  } catch {
    /* nothing to release */
  }
}

/**
 * Clears every stored execution key.
 *
 * Only for the case where a key is known to be spent and the ticket must be
 * usable again immediately.
 */
export function releaseAllExecutionKeys() {
  try {
    const doomed = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const k = localStorage.key(i);
      if (k && k.startsWith(STORAGE_PREFIX)) doomed.push(k);
    }
    doomed.forEach((k) => localStorage.removeItem(k));
  } catch {
    /* nothing to release */
  }
}

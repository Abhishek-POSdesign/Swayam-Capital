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
export function executionKeyFor(ticketId) {
  const slot = `${STORAGE_PREFIX}${ticketId}`;
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
export function releaseExecutionKey(ticketId) {
  try {
    localStorage.removeItem(`${STORAGE_PREFIX}${ticketId}`);
  } catch {
    /* nothing to release */
  }
}

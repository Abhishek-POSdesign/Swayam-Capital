import { describe, it, expect, beforeEach } from 'vitest';
import {
  executionKeyFor,
  releaseExecutionKey,
  releaseAllExecutionKeys,
} from '../src/utils/idempotency.js';

const tradeA = {
  strategy_name: 'Bull Call Spread',
  underlying: 'NIFTY',
  mode: 'paper',
  legs: [
    { direction: 'buy', strike: 23550, option_type: 'CE', quantity_lots: 1, entry_premium: 293.35, expiry_date: '2026-09-29' },
  ],
};
const tradeB = {
  ...tradeA,
  legs: [
    { direction: 'buy', strike: 23350, option_type: 'PE', quantity_lots: 1, entry_premium: 186.45, expiry_date: '2026-09-29' },
  ],
};

// This runner has no DOM, so give the module the storage a browser would.
function installStorage() {
  const store = new Map();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      get length() { return store.size; },
      key: (i) => Array.from(store.keys())[i] ?? null,
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => { store.set(k, String(v)); },
      removeItem: (k) => { store.delete(k); },
      clear: () => store.clear(),
    },
  });
}

describe('the execution key belongs to the trade, not the ticket', () => {
  beforeEach(() => {
    installStorage();
    releaseAllExecutionKeys();
  });

  it('gives the SAME key when the same trade is retried', () => {
    // This is the protection: a lost response, he presses again, one position.
    expect(executionKeyFor('desk', tradeA)).toBe(executionKeyFor('desk', tradeA));
  });

  it('gives a DIFFERENT key for a genuinely different trade', () => {
    // The trap that stopped him trading on 2026-09-09. One key per ticket was
    // minted once and never released, so the server refused every later trade
    // with "this execution key has already been used for a different trade".
    expect(executionKeyFor('desk', tradeA)).not.toBe(executionKeyFor('desk', tradeB));
  });

  it('mints a fresh key once a trade is released', () => {
    const first = executionKeyFor('desk', tradeA);
    releaseExecutionKey('desk', tradeA);
    expect(executionKeyFor('desk', tradeA)).not.toBe(first);
  });

  it('clears every key when the whole store is released', () => {
    const a = executionKeyFor('desk', tradeA);
    const b = executionKeyFor('desk', tradeB);
    releaseAllExecutionKeys();
    expect(executionKeyFor('desk', tradeA)).not.toBe(a);
    expect(executionKeyFor('desk', tradeB)).not.toBe(b);
  });

  it('still returns a key when storage is unavailable', () => {
    const real = globalThis.localStorage;
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get() { throw new Error('blocked'); },
    });
    try {
      expect(typeof executionKeyFor('desk', tradeA)).toBe('string');
    } finally {
      Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: real });
    }
  });
});

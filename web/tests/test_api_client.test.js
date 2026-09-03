import { describe, it, expect, vi } from 'vitest';
import { api } from '../src/api.js';

describe('API Client', () => {
  it('handles successful requests', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', version: '0.3.0' }),
    });

    const res = await api.getHealth();
    expect(res.status).toBe('ok');
    expect(res.version).toBe('0.3.0');
  });

  it('throws descriptive error on failed response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Invalid option type' }),
    });

    await expect(api.computeStrategy({})).rejects.toThrow('Invalid option type');
  });
});

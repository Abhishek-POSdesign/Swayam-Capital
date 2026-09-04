import { describe, it, expect } from 'vitest';
import { build } from 'vite';
import path from 'node:path';

describe('Frontend Build & Syntax Validation', () => {
  it('bundles all components without syntax or parse errors', async () => {
    // Run vite build programmatically in memory to verify full bundle parse integrity
    const result = await build({
      root: path.resolve(__dirname, '..'),
      logLevel: 'silent',
      build: {
        write: false, // In-memory build, don't overwrite dist/
      },
    });

    expect(result).toBeDefined();
  }, 15000);
});

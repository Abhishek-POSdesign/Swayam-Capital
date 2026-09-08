import { defineConfig } from 'vite';

// The backend the dev server talks to. Port 8000 by default, but overridable so
// a second session can run its own backend without fighting over the port, and
// so a stale server left running on 8000 cannot silently serve old code to a
// page you are trying to verify. That happened on 2026-09-08.
const API_ORIGIN = process.env.SWAYAM_API_ORIGIN || 'http://localhost:8000';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: API_ORIGIN,
        changeOrigin: true,
      },
      '/ws': {
        target: API_ORIGIN.replace(/^http/, 'ws'),
        ws: true,
      },
    },
  },
});

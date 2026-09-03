# Swayam Capital Web Dashboard

Frontend interface for Swayam Capital options strategy builder and paper trading platform.

## Architecture

- **Stack:** Vanilla Modern JavaScript (ES Modules), Vite 6, Plotly.js (`plotly.js-dist-min`).
- **Theme:** Dark mode default with POS Design Bible tokens (`--bg-primary: #0f1419`).
- **Communication:** REST API via `/api/*` and WebSocket ticks via `/ws/spot` (proxied to backend on port 8000).

## Running Locally

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Run dev server:**
   ```bash
   npm run dev
   ```
   Opens on `http://localhost:5173`. Ensure backend is running on `http://localhost:8000`.

3. **Build for production:**
   ```bash
   npm run build
   ```

4. **Run frontend tests:**
   ```bash
   npm test
   ```

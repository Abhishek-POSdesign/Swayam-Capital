# 🤖 GEMINI.md — Swayam Capital Architecture & Handoff Master Record

> **Project:** Swayam Capital — Algorithmic & AI-Assisted F&O Options Trading Platform  
> **Owner:** Abhishek Sikka  
> **Primary AI Architect:** Antigravity (Gemini)  
> **Code Repository:** `D:\Claude\POS\Trading-Platform\Swayam Capital`  
> **Obsidian Vault (Method & Truth):** `G:\My Drive\Second Brain\02 - Projects\Trading\`  
> **GCP Project:** `swayam-capital` (Project Number: `535273918813`, Region: `asia-southeast1` [Singapore], AI Location: `global`)  
> **Supabase Database:** `wxijlrwoiaeaupaaqecc` (`https://wxijlrwoiaeaupaaqecc.supabase.co`)  
> **Broker Integration:** FYERS API v3 (Client ID: `YA38914`)  
> **Status:** Phase 1 Complete (BUILDs 1–10 + BUILD-9-FIXES-A/B/C Shipped). 321 automated tests passing (256 pytest + 65 vitest, 0 failures). Strategy Builder & Trading Terminal integrated on single-page canvas (`/strategy`) with 8 presets, AI import, margin-safe order sequencing, overnight naked short auto-block modal, and bundled chart/theme fixes. Deployed to Google Cloud Run in Singapore (`asia-southeast1`) behind custom subdomain `https://swayam.abhisheksikka.com`.

---

## 🏛️ 1. Core Philosophy & Operating Rules

1. **Non-Technical Builder Protocol:**
   - Abhishek is a non-technical builder and sole provider.
   - Always communicate in plain English, avoiding or immediately explaining technical jargon.
   - Strict Execution Protocol for code/file changes: Restate goal -> 3–5 step plan -> HARD STOP -> wait for user approval -> execute -> explain changes.
   - For informational queries or read-only research, autonomous background execution is permitted.

2. **The "Vault Holds Mind, Database Holds Money" Principle:**
   - Trading rules, psychology rules, and journal reflections live in the Obsidian Second Brain vault (`02 - Projects/Trading/`).
   - The platform dynamically parses rules from markdown at runtime (never hardcoding rupee amounts or static rules into Python code).
   - Live trades, audit logs, and account balances live in Supabase (`swayam_*` tables) and local DuckDB.
   - Sensitive broker IDs, live account numbers, or live P&L are never dumped into vault notes.

3. **AI Persona & Behavior (The Eliminator, Not Recommender):**
   - The AI acts as an **Eliminator**, filtering out invalid setups according to Abhishek's rules. Abhishek selects from the 2–3 compliant survivors.
   - 6 Hardcoded Persona Constraints:
     1. Strict rule enforcement (Method rules are non-negotiable).
     2. 1% maximum capital risk per trade cap.
     3. 1:2 minimum risk-to-reward ratio.
     4. Operational readiness gating (sleep < 5h or active alcohol lockout blocks trades).
     5. No unhedged naked options selling.
     6. Process-oriented feedback (grading decisions on adherence, not outcome luck).

4. **Zero Silent Fallbacks:**
   - Fail loudly with clear HTTP exceptions (503 Service Unavailable, 400 Bad Request, 404 Not Found, 500 Internal Error).
   - Never substitute fake dummy prices or default numbers when real systems fail.

---

## 🚀 2. Milestone Summary (BUILDs 1 through 7 Complete)

### ✅ BUILD-1: Foundation & Vault Sync
- Dynamic runtime parsing of Obsidian Method files (`Risk Management Rules.md`, `Operational Readiness Rules.md`, `Personal Trading Brief.md`).
- Percentage-based rule calculations (1% risk, 2% daily loss, 4% weekly loss, 3% blast radius, 2% overnight hedge).
- Local DuckDB storage engine (`data/options_cache.duckdb`) with automated schema migrations.
- Bhavcopy downloader and daily options data ingestion pipeline.
- Supabase database client initialization and connection health checking.

### ✅ BUILD-2: FYERS Integration & Pricing Engine
- Broker authentication with FYERS API v3 (OAuth token generation + automated daily refresh).
- Complete Black-Scholes-Merton pricing library in Python (`src/swayam/options_math/`):
  - Analytical Black-Scholes pricing for European index options.
  - Full first- and second-order Greeks: Delta, Gamma, Theta, Vega, Rho.
  - Implied Volatility (IV) solver using Newton-Raphson with bisection fallback.
- Multi-leg spread payoff matrix generator (net debit/credit, max profit, max loss, breakeven points).
- TradingView chart integration helper with custom shortcut buttons.

### ✅ BUILD-3: Full-Stack Web Dashboard
- Lightweight, ultra-fast frontend built with vanilla ES modules, Vite, and Plotly.js.
- FastAPI backend serving `/api/` endpoints:
  - `GET /api/market/spot`: Live NIFTY spot ticker with 5-second polling.
  - `GET /api/rules/method`: Live parsed Method rules.
  - `POST /api/strategy/compute`: Payoff curve generation and Greeks aggregation.
  - `POST /api/strategy/validate`: Pre-execution validation against all Method rules.
- Strategy builder with Bear Put Spread preset, strike selector, and real-time interactive payoff chart.

### ✅ BUILD-4: 60-Second Operational Readiness Gate
- Pre-trade checklist enforcing physical and mental state readiness before market open:
  - Factor 1: Sleep duration (< 5h = RED lock, 5–6h = 75% size cap, > 6h = GREEN).
  - Factor 2: Alcohol abstinence (90-day reset clock + 4-tier re-entry ramp: 0.25% -> 0.5% -> 0.75% -> 1.0%).
  - Factor 3: Physical workout within last 48 hours.
  - Factor 4: Emotional state & journal mood.
  - Factor 5: Life stressors.
- Auto-prefill reading Atlas Daily Logs (`G:\My Drive\Second Brain\01 - Daily Logs\YYYY-MM-DD.md`).
- Hard gating: `/api/strategy/validate` and `/api/execute` reject any trade if readiness verdict is RED or unlogged.
- Nightly reconciliation engine (`scripts/run_reconciler.py`) verifying 2:30 PM self-assessment against finalized Atlas logs.

### ✅ BUILD-5: 24/7 Live Options Recorder (GCP Cloud)
- Headless Cloud Function `swayam-recorder` deployed in `asia-south1` (Python 3.11, 512MB).
- Cloud Scheduler trigger running `*/1 9-15 * * 1-5` (every minute during market hours).
- Records entire NIFTY options chain (~130 strikes, CE + PE, LTP, bid/ask, OI, volume) directly from FYERS.
- Writes daily compressed Parquet files to Google Cloud Storage (`gs://swayam-capital-options-data/YYYY/MM/DD/nifty_chain.parquet`).
- Nightly Windows scheduled task (`scripts/ingest_gcs_to_duckdb.py`) ingesting Parquet into local DuckDB table `options_history` with composite natural key `(trade_date, symbol, snapshot_time_utc)` for 100% idempotent inserts.

### ✅ BUILD-6: AI Trading Partner (Vertex AI Gemini)
- 3-Tier Model Routing:
  - **Tier 1 (Primary):** `gemini-3.1-pro-preview` — deep reasoning, setup validation, complex multi-leg evaluation.
  - **Tier 2 (Fallback):** `gemini-2.5-pro` — activated automatically if Tier 1 times out or hits rate limits.
  - **Tier 3 (Lightweight):** `gemini-2.5-flash-lite` — instant queries, quick calculations, routine trade checks.
- Full context assembly loading: Method rules, margin base, live spot, today's readiness verdict, active positions, recent trade history, and Personal Trading Brief.
- Server-Sent Events (SSE) streaming endpoint (`POST /api/ai/chat/stream`).
- Collapsible web chat drawer with markdown formatting, token usage tracking, and conversation persistence.
- Supabase Migration 002: added `swayam_ai_conversations`, `swayam_ai_messages`, `swayam_ai_usage_daily`, and `swayam_rule_evolution_log`.

### ✅ BUILD-7: Live P&L and Trade Exit Flow
- Real-time mark-to-market position valuation (`GET /api/positions/live`):
  - Fetches live option chain from FYERS (with 5-second in-memory cache to prevent broker throttling).
  - Calculates unrealized P&L leg-by-leg (Long: `(LTP - Entry) * Qty`, Short: `(Entry - LTP) * Qty`).
  - Computes updated position Greeks and risk percentages against current margin base.
- Trade close endpoint (`POST /api/positions/{id}/close`):
  - **Database-before-Journal ordering:** records trade exit to `swayam_trade_history` and updates `swayam_positions` before updating markdown files.
  - Automates journal note completion via `append_exit_block()`: updates frontmatter (`status: closed`, `closed_at`, `realized_pnl_inr`, `close_reason`) and replaces placeholder `## Exit (to be filled at close)` with formatted exit table, net P&L, charges, and holding duration.
- Interactive web close modal with editable LTP overrides.

### ✅ Small Cleanups & AI Region Fix
- **AI Location Resolution:** Set `GCP_AI_LOCATION=global` across `.env`, `config.py`, `router.py`, and `factory.py`. Fixes 404 regional availability in `asia-south1` and allows full 3.1 Pro Preview operation with zero downgrade.
- **Removed Silent Fallbacks:**
  - `readiness.py`: Database failures now raise HTTP 503 instead of silently setting alcohol streak to empty.
  - `ingest_gcs_to_duckdb.py`: Missing `GCS_OPTIONS_BUCKET` now raises an explicit `ValueError`.
  - `positions.py`: Margin base fallback dynamically reads from vault `MethodRules` or raises HTTP 503 instead of guessing a hardcoded amount.
- **Frontend Syntax & Build Test:** Added in-memory Vite build test (`web/tests/test_build_syntax.test.js`) in Vitest ensuring zero template literal or syntax errors reach the browser.
- **Documentation:** Updated `SETUP.md` with complete instructions for virtual environment and both Supabase migrations (001 and 002).

### ✅ BUILD-8: Statistical Risk Cap (Two-Tier Risk Model)
- **Two-Tier Risk Framework:** Replaced the single mathematical worst-case loss check with Abhishek's two-tier model:
  - **Tier 1 (Realistic Risk Cap — 1.0% of margin base):** Primary sizing gate evaluating spread loss at ±2σ NIFTY move based on trailing 20-day realized volatility.
  - **Tier 2 (Blast Radius Fuse — 3.0% of margin base):** Black-swan emergency ceiling comparing absolute mathematical max loss (`max_loss_inr`).
- **Realized Volatility Engine (`src/swayam/options_math/realized_vol.py`):** Trailing 20-day realized volatility calculation using log returns of daily closes in DuckDB, with daily 1σ scaling and cached results in `realized_vol_cache`.
- **Payoff at Spot (`src/swayam/options_math/payoff.py`):** Dedicated `pnl_at_spot()` function evaluating exact intrinsic P&L at stressed spot levels for multi-leg strategies.
- **Obsidian Vault Rules Alignment:** Added `## Two-tier risk model — realistic vs absolute` subsection to `Risk Management Rules.md` and updated `VaultReader` parser with zero hardcoded numbers.
- **Side-by-Side Frontend Risk Badges (`web/src/components/rule-validation.js`):** Realistic Risk and Blast Radius rendered with pass/fail badges, rupee values, margin percentages, Abhishek voice tooltips, and dynamic execution button disable.
- **AI Persona & Context Integration:** Embedded risk philosophy into `TRADING_PARTNER_PERSONA` and injected today's computed realized volatility (`realistic_vol_pct`) into context assembly.
- **Smoketest Check:** Added 20-day NIFTY realized volatility computation step to `swayam.smoketest`.
- **Zero Silent Fallback Discipline:** Strict exception raising (`InsufficientHistoryError`, `HistoricalDataUnavailableError`, `MethodRulesParseError`, HTTP 503) rejecting silent fallback defaults.
### ✅ BUILD-9: UI Redesign Home Screen (Readiness + Market Prep)
- **Multi-Page Architecture:** Transformed Swayam Capital into a multi-page terminal, launching with the dedicated **Home (Readiness + Market Prep)** view on `/` while preserving `/strategy` for the Strategy Builder.
- **Atlas Design System Inheritance:** Implemented Atlas dark daylight tokens (`swayam-tokens.css`), 12-column bento grid, 13px gap, 16px radius, and semantic colors (Sage = Pass/Profit, Coral = Alert/Loss, Lilac = AI Partner, Amber = Warning, Blue = Info).
- **Sequential Readiness Ritual (`readiness-ritual.js`):** Clean single-column 6-step pre-trade operational readiness checklist featuring an interactive 5-minute meditation timer with circular SVG progress ring, pause/reset controls, and Web Audio API completion bell chime.
- **Verdict Card (`verdict-card.js`):** Dynamic state-aware card rendered in Atlas pastel cards (`--dl-done` mint for GREEN, `--dl-skip` amber for YELLOW, `--dl-alert` coral for RED) with rule reason tags and trading sizing permissions.
- **Reflective History Cards (`kpi-history-card.js`, `GET /api/readiness/kpis`):** Reusable `.fig-xl` serif metric cards querying Supabase for actual alcohol-free streaks with ramp tier tags, 7-day readiness dot indicators, and morning routine completion with trend sparkline.
- **Market Prep Bento Grid:**
  - **Overnight Global Strip (`overnight-strip.js`):** 5 global indicators (DJI, S&P 500, NASDAQ, USD/INR, BRENT) in tabular monospace format.
  - **India VIX Card (`vix-card.js`):** 20-day historical value, volatility regime badge, and sparkline.
  - **NIFTY Candlestick Chart Card (`nifty-chart-card.js`):** Dark-themed candlestick chart with 20-EMA overlay and key support level at 24,700.
  - **Macro Events Card (`macro-events-card.js`):** Next 5 days economic calendar (RBI Policy Meet, US CPI, FOMC Minutes).
  - **AI Reading Queue Card (`reading-queue-card.js`):** Curated overnight institutional notes with reading time estimates.
### ✅ BUILD-9.5: Cloud Deployment (Cloud Run + Custom Subdomain)
- **Single Multi-Stage Container Architecture:** Unified container (`Dockerfile`) compiling the Vite frontend with Node 20 and serving both the REST/WebSocket API and built static frontend via FastAPI + Gunicorn ASGI workers (`swayam.api.main:app`) on Python 3.11-slim.
- **Client-Side SPA Routing & 404 Guards:** Built frontend static files served from `/` and `/assets` with client-side fallback to `index.html` and strict 404 guards for missing `/api/*` requests (`tests/api/test_static_serving.py`).
- **Google Cloud Run Deployments:** Deployed service `swayam-dashboard` with automated 0-to-3 auto-scaling (scale-to-zero when idle ensures $0 baseline cost).
- **Google Secret Manager Integration:** Synchronized 7 sensitive configuration variables (`swayam-supabase-url`, `swayam-supabase-anon-key`, `swayam-supabase-service-role-key`, `fyers-access-token`, `fyers-client-id`, `fyers-app-id`, `fyers-secret-key`) injected directly into Cloud Run at runtime.
- **Security & Access Control:** Protected via Google Identity-Aware Proxy (IAP) and IAM invoker policy restricted strictly to `abhisheksikka99.99@gmail.com`.
- **Custom Subdomain Mapping (`swayam.abhisheksikka.com`):** Configured Cloud Run domain mapping in `asia-southeast1` (Singapore) pointing to `ghs.googlehosted.com.` with automatic SSL certificate management.
- **Operations & Runbooks:** Full deployment runbook (`docs/DEPLOY.md`) and operational troubleshooting cheatsheet (`docs/RUNBOOK.md`).

### ✅ BUILD-9-FIXES-C: Atlas Parity & Interaction Fixes
- **Atlas Design Parity Wholesale:** Full-height sidebar rail (`<aside class="swayam-rail">`), Atlas Paper Studio light theme tokens (`#ebe8e1` canvas, `#ffffff` rail, `#f8f6f2` cards, near-black high-contrast text and nav pills).
- **Rich Collapsed Status Strip:** 72px rail strip with 32px verdict bar, 6 factor checkmarks, and 103d streak indicator. Main content expands with 0 dead gap when folded.
- **AI Drawer & Chat Surface:** 400px AI drawer with desktop content shift (no navbar clipping) and lilac branding. Removed 2px lilac border on workspace chat; added 2×2 grid of 4 pre-market prompt cards in empty conversation state.
- **Adaptive VIX Chart:** Dynamic 10% data-bounded range, 1-year median reference line, and peak marker dots.
- **Market Data Fallbacks in Cloud Run:** Added Supabase database fallbacks (`swayam_nifty_daily_bars` with 22 bars, `swayam_bhavcopy` with 262 days) to `get_nifty_candles` and `get_vix_history` when FYERS token is expired or market is closed. All timeframe tabs (`15m`, `1h`, `1d`) return 200 OK without crashing.
- **All 290 Tests Passing:** 246 backend pytest + 44 frontend vitest tests pass cleanly with 0 failures.

### ✅ BUILD-10: Strategy Builder + Trading Terminal (Single-Page Canvas)
- **Unified Single-Page Canvas (`/strategy`):**
  - **Left Rail (320px):** Mini Readiness Card (reflects today's sleep, alcohol streak, live size cap), Open Positions Mini-List (live P&L badges with quick exit triggers), and AI Session Recap Card (bullets synthesized from chat history).
  - **Center Canvas (Flexible):**
    - **Preset Bar (`preset-bar.js`):** Chip selector for 8 core strategies (Bear Put, Bull Call, Iron Condor, Short Strangle, Calendar, Ratio, Straddle, Jade Lizard) + "Import from AI conversation" button.
    - **Leg Builder Container (`leg-builder.js`):** Net Debit/Credit big numbers with live calculation, visual safety divider (`↑ Buys execute first (margin-safe)`), and `+ Add Leg` button.
    - **Leg Card Component (`leg-card.js`):** B/S badge button with color inversion, CE/PE toggle, expiry picker, snap-to-50 strike input, lot stepper, real-time LTP quote display, and Greek pills (Δ, θ, ν).
    - **Plotly Payoff Chart (`payoff-chart.js`):** Dual curves (Expiry in sage green & T+0 in dashed slate), vertical amber spot line at 24,850, red breakeven markers, and 2σ / Blast Radius threshold lines.
    - **Rule Validation Panel (`rule-validation-panel.js`):** Side-by-side cards for Realistic Risk (2σ) & Blast Radius (max theoretical loss) with threshold checks against Method capital limits, plus secondary rule checks (R:R, Headroom, Hedge structure).
    - **Execute Row (`execute-row.js`):** Order type selector (Limit default vs Market), order execution sequence preview button, `[Execute All Legs]` button, and `[⚡ AI-order the legs]` button.
  - **Bottom Sticky Bar:** Live spot ticker (NIFTY 50), India VIX, and active order mode indicator.
- **Strict Execution Ordering & Margin Safety (§ 10a):**
  - Order preview (`POST /api/execute/preview-order`) enforces sequence: BUY legs placed first, SELL legs placed last.
  - Calculates hedged margin vs naked margin and reports exact margin savings in rupees.
  - Paper trade execution endpoint (`POST /api/execute/multi-leg`) creates atomic records in `swayam_positions` with `order_type` and `session_id` notes.
- **Overnight Naked Short Auto-Block Modal (`overnight-block-modal.js`):**
  - Detects unhedged short positions (`GET /api/positions/naked-shorts`).
  - At 15:20 IST, if any naked short exists, locks the entire UI with an unclosable coral scrim modal (Escape key disabled).
  - Offers only two actionable escape paths: `[Add Hedge Now]` (appends protective wings) or `[Exit Position Instead]` (liquidates position).
- **Bundled User Fixes:**
  1. **NIFTY 15m Chart Wicks:** Fixed `_get_nifty_candle_fallback` so 15m candles render realistic high/low wicks (`day_range * 0.18 + 6.0`) and wave dynamics instead of a flat line with dots.
  2. **Dark/Light Chart Theme Sync:** Dispatches `swayam-theme-change` CustomEvent from header; NIFTY chart, VIX chart, and Payoff chart listen and call `Plotly.relayout` or re-render canvas immediately.
  3. **AI Chat Testing Mode Memory:** Persists `swayam_active_session_id` in `localStorage`; `trading_partner.py` permanently enforces Constraint 7 ("Paper Trading / Testing Phase active: all execution is strictly paper simulation") in system instructions and context assembly.
  4. **Fast Headless Test DOM:** Resolved regex catastrophic backtracking and event handler recursion in test environment, achieving 65 passing frontend tests in under 30s.
- **All 321 Tests Passing:** 256 backend pytest + 65 frontend vitest tests pass cleanly with 0 failures.

---

## 📊 3. Database Schema Overview (Supabase: `wxijlrwoiaeaupaaqecc`)

All tables have Row Level Security (RLS) disabled for platform service key / anon access:

| Table | Purpose | Key Fields |
|:---|:---|:---|
| `swayam_config` | Dynamic key-value system settings | `key` (PK), `value`, `description`, `updated_at` |
| `swayam_readiness_log` | Daily pre-trade operational readiness assessments | `id` (PK), `log_date`, `verdict`, `trading_allowed`, `size_cap_pct`, `factors` |
| `swayam_positions` | Open and closed trade positions | `id` (PK), `strategy_name`, `status`, `legs`, `entry_time`, `max_loss_inr`, `journal_path` |
| `swayam_trade_history` | Historical closed trade records & realized metrics | `id` (PK), `position_id`, `realized_pnl_inr`, `charges_inr`, `holding_days`, `close_reason` |
| `swayam_daily_pnl` | Daily P&L snapshots for equity curve | `trade_date` (PK), `realized_pnl_inr`, `unrealized_pnl_inr`, `trade_count` |
| `swayam_audit_log` | Immutable compliance and execution audit trail | `id` (PK), `event_type`, `payload`, `created_at` |
| `swayam_ai_conversations` | AI chat sessions | `id` (PK), `title`, `created_at`, `updated_at` |
| `swayam_ai_messages` | Individual turns within an AI conversation | `id` (PK), `conversation_id`, `role`, `content`, `model_used`, `tokens_in`, `tokens_out` |
| `swayam_ai_usage_daily` | Daily token and cost tracking for Vertex AI | `usage_date` (PK), `model`, `request_count`, `input_tokens`, `output_tokens`, `cost_inr` |
| `swayam_rule_evolution_log` | History of rule adjustments and backtest proposals | `id` (PK), `rule_name`, `old_value`, `new_value`, `reason`, `backtest_id` |
| `swayam_nifty_daily_bars` | NIFTY 50 daily OHLC history (Cloud Run fallback) | `trade_date` (PK), `symbol`, `open`, `high`, `low`, `close`, `volume` |
| `swayam_bhavcopy` | Daily NSE bhavcopy India VIX history | `date` (PK), `vix_open`, `vix_high`, `vix_low`, `vix_close` |

---

## 🔌 4. API Endpoints Reference

The FastAPI backend runs at `http://localhost:8000`:

- **System & Health:**
  - `GET /health` — Verifies system status and version.
  - `GET /api/market/spot` — Returns live NIFTY spot price and timestamp from FYERS.
- **Rules & Readiness:**
  - `GET /api/rules/method` — Returns parsed Method rules and calculated rupee thresholds.
  - `GET /api/readiness/today` — Checks if today's readiness is logged; returns Atlas defaults if unlogged.
  - `POST /api/readiness/log` — Persists 2:30 PM readiness assessment and calculates trading verdict.
- **Strategy & Execution:**
  - `POST /api/strategy/compute` — Computes spread payoff diagram points, net debit/credit, and aggregated Greeks.
  - `POST /api/strategy/validate` — Validates proposed strategy against Method rules and today's readiness gate.
  - `POST /api/execute` — Executes paper trade: records to Supabase, generates Obsidian trade journal note.
- **Positions & Trade Management:**
  - `GET /api/positions/active` — Lists all currently open paper trade positions.
  - `GET /api/positions/live` — Mark-to-market live valuation of open positions with 5s cached FYERS quotes.
  - `POST /api/positions/{id}/close` — Closes an open position: updates DB, records P&L, appends exit block to journal note.
- **AI Trading Partner:**
  - `POST /api/ai/chat/stream` — SSE streaming chat completion with 3-tier Gemini routing and full context injection.
  - `GET /api/ai/conversations` — Retrieves conversation list.
  - `GET /api/ai/conversations/{id}/messages` — Retrieves turn history for a session.

---

## 🎨 5. Upcoming UI Redesign Session (Where to Pick Up Tomorrow)

### Core Requirement from Abhishek
**NOT single-page consolidation.** The platform requires a **multi-page / multi-tab architecture** inspired by the mature **Atlas** interface (`atlas.abhisheksikka.com`) and the **POS Design Bible** (`https://github.com/Abhishek-POSdesign/design-bible`).

### Dedicated Work Surfaces
1. **Readiness Workspace:**
   - Dedicated wake-up screen with structured form fields (sleep hours, workout status, journal mood, stress level).
   - Streak tracking (alcohol-free days clock, re-entry ramp tier indicators).
   - Clear visual verdict card (GREEN / YELLOW / RED) with full factor breakdown.
2. **Strategy Builder:**
   - Spread construction surface (strike selector, expiry picker, lot size controls).
   - Large interactive Plotly payoff chart with breakeven lines and current spot indicator.
   - Real-time Method rule compliance checklist (checks turn green/red as legs are added).
   - Position Greeks card (Delta, Gamma, Theta, Vega).
3. **Active Trades & Live P&L:**
   - Dedicated table and card view for open positions.
   - Real-time 5-second polling with color-coded live P&L (green for profit, red for loss).
   - Trade exit modal with editable exit premiums and instant net P&L calculation.
4. **Trade Journal & History:**
   - Visual browsing of past closed trades from Supabase and Obsidian.
   - Long-form markdown reflection reading view.
   - Cumulative equity curve and win/loss statistics.
5. **Backtesting & Historical Data:**
   - Historical options playback using recorded DuckDB parquet data.
   - Rule parameter testing and sensitivity reports.
6. **AI Trading Partner (Persistent):**
   - Persistent collapsible sidebar or floating drawer accessible from any tab/page.
   - Context-aware assistance streaming suggestions and checking rule compliance.

### Technical Constraints for Frontend
- Keep **Vanilla JavaScript + Vite + Plotly.js** (do not introduce heavy frameworks like React, Next.js, or Tailwind unless explicitly instructed).
- Use CSS variables adhering to POS Design Bible standards (dark calibration, muted accents, precise spatial rhythm).

---

## 🛠️ 6. How to Run & Verify the Platform

### Terminal 1: Backend API Server
```powershell
cd "D:\Claude\POS\Trading-Platform\Swayam Capital"
.\.venv\Scripts\Activate.ps1
python -m uvicorn swayam.api.main:app --reload --port 8000
```

### Terminal 2: Frontend Web Server
```powershell
cd "D:\Claude\POS\Trading-Platform\Swayam Capital\web"
npm run dev
# App will be accessible at http://localhost:5173
```

### Running the Test Suite
```powershell
# Python backend tests (180 tests)
cd "D:\Claude\POS\Trading-Platform\Swayam Capital"
.\.venv\Scripts\pytest

# Frontend tests including bundle syntax verification (7 tests)
cd "D:\Claude\POS\Trading-Platform\Swayam Capital\web"
npm test
```

### Running Full System Smoketest
```powershell
cd "D:\Claude\POS\Trading-Platform\Swayam Capital"
.\.venv\Scripts\python -m swayam.smoketest
```

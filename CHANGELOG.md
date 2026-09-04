# Changelog

All notable changes to **Swayam Capital** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - BUILD-9-FIXES-B (2026-09-07)
- **Full-Width Interactive Conversational Workspace (`web/src/components/chat-surface.js`, `web/src/pages/home.js`)**: Upgraded "What Matters Today" into an expansive 1,000–1,400px wide conversational workspace matching Cursor terminal standards, complete with pre-market briefing, speech synthesizer playback, per-message actions (save to memory, pin rule), streaming dialogue history, and continuous session bridge to Strategy Builder.
- **Indian English Text-to-Speech (`src/swayam/ai/tts.py`, `src/swayam/api/routes/tts.py`, `web/src/components/tts-player.js`)**: Integrated Google Cloud Text-to-Speech via Cloud Run Application Default Credentials (ADC), featuring Neural2 Indian English voices (`swayam_calm` male default, `swayam_warm` female alternate), configurable speech rate (0.5x–2.0x), audio caching, and single-stream playback.
- **3-Tier Event-Driven Memory Model (`src/swayam/ai/memory.py`, `src/swayam/api/routes/notebook.py`, `pinned.py`, `session.py`, `migrations/005_ai_memory_system.sql`)**:
  - Layer 1: Verbatim Working Memory preserved across the trading day and active positions.
  - Layer 2: Event-driven compaction (Daily 4:00 PM IST cron + closed trade with journal reflection).
  - Layer 3: Persistent Memory Notebook and Pinned Decisions injected permanently into system context.
  - Layer 4: 200-message safety valve auto-compacting oldest half.
- **AI Settings Drawer (`web/src/components/ai-settings-drawer.js`)**: Voice selection, speech rate slider, auto-play toggle, and direct management for pinned rules and notebook memories.
- **Fixes A1–A7 UI Polishing**:
  - Fix A1: Repainted light theme tokens to match Atlas paper-cream (`#ebe8e1` canvas, `#f8f6f2` cards, `#1a1a1c` text).
  - Fix A2: Added streak-protecting double-confirmation modal for alcohol = "Yes".
  - Fix A3: Applied correct charcoal `#191b21` and lilac theme tokens to AI drawer.
  - Fix A4: Implemented non-blocking content-shift layout pattern (`margin-right: 370px`).
  - Fix A5: Corrected API endpoints to relative URLs (`API_BASE = ''`).
  - Fix A6: Added context-aware pre-market starter prompts.
  - Fix A7: Added collapsible Morning Ritual panel folding to a slim 56px strip with `localStorage` state.
- **Test Suite Expansion**: Total automated test suite expanded to **286 passing tests** (242 pytest + 44 vitest, 0 failures).

### Added - BUILD-9.5 (2026-09-07)
- **Multi-Stage Dockerfile & Containerization (`Dockerfile`, `.dockerignore`, `.gcloudignore`)**: Single multi-stage container build bundling Node 20 (Vite frontend compilation) and Python 3.11-slim (FastAPI + Gunicorn ASGI production server) running under 1GB RAM / 1 vCPU with 0-to-3 auto-scaling instances.
- **Vite Frontend Static Serving from FastAPI (`src/swayam/api/main.py`, `tests/api/test_static_serving.py`)**: Seamless static file serving from `/` and `/assets` with client-side SPA routing fallback to `index.html` and explicit 404 guards for missing `/api/*` requests.
- **Automated Cloud Build Pipeline (`cloudbuild.yaml`)**: High-performance Cloud Build definition compiling container images, pushing to Artifact Registry (`asia-south1`), and deploying directly to Cloud Run with environment variables and secret injections.
- **Google Cloud Security & Secret Manager Wiring**: Dedicated Service Account `swayam-dashboard-sa` provisioned with minimal least-privilege roles (`roles/secretmanager.secretAccessor`, `roles/aiplatform.user`, `roles/storage.objectViewer`). All 7 core secrets safely synchronized to Google Secret Manager.
- **Custom Domain Mapping (`swayam.abhisheksikka.com`)**: Configured Cloud Run domain mapping pointing to `ghs.googlehosted.com.` with automatic SSL certificate management and Identity-Aware Proxy (IAP) access control.
- **Deployment Documentation & Runbooks (`docs/DEPLOY.md`, `docs/RUNBOOK.md`)**: Comprehensive operations guides covering manual deployment, log inspection, rollback procedures, and troubleshooting.

### Added - BUILD-9 (2026-09-07)
- **Multi-Page Architecture & Home Page View (`web/src/pages/home.js`, `web/src/main.js`, `web/index.html`)**: Transformed Swayam Capital from a single crowded screen into a multi-page terminal, launching with the dedicated **Home (Readiness + Market Prep)** view.
- **Atlas Design System Inheritance (`web/src/styles/swayam-tokens.css`)**: Implemented Atlas daylight dark-mode tokens (`#101116` background, `#191b21` cards, 12-column bento grid, 13px gap, 16px border-radius) and strictly mapped the 5 locked semantic meanings (Sage = PASS/Profit, Coral = Alert/Loss, Lilac = AI Partner, Amber = Warning, Blue = Info).
- **Sequential Readiness Ritual (`web/src/components/readiness-ritual.js`)**: Clean single-column 6-step pre-trade operational readiness checklist:
  1. Interactive 5-minute meditation timer with circular SVG progress ring, pause/resume/reset controls, and Web Audio API completion bell chime.
  2. Sleep duration selector.
  3. Alcohol in last 24h toggle (No/Yes).
  4. Workout in last 48h toggle (Yes/No).
  5. Current mood pills (Calm & Focused, Neutral, Restless, Anxious, Angry).
  6. Life stressor pills (None, Work, Family, Health, Financial).
- **Verdict Card (`web/src/components/verdict-card.js`)**: Dynamic state-aware card rendered in Atlas pastel cards (`--dl-done` mint for GREEN, `--dl-skip` amber for YELLOW, `--dl-alert` coral for RED) with rule reason tags and trading sizing permissions.
- **Reflective History Cards (`web/src/components/kpi-history-card.js`, `GET /api/readiness/kpis`)**: Reusable `.fig-xl` serif metric cards querying Supabase for actual alcohol-free streaks with ramp tier tags, 7-day readiness dot indicators, and morning routine completion with trend sparkline.
- **Market Prep Bento Grid (`web/src/components/`)**:
  - **Overnight Global Strip (`overnight-strip.js`)**: 5 global indicators (DJI, S&P 500, NASDAQ, USD/INR, BRENT) in tabular monospace format.
  - **India VIX Card (`vix-card.js`)**: 20-day historical value, volatility regime badge, and sparkline.
  - **NIFTY Candlestick Chart Card (`nifty-chart-card.js`)**: Dark-themed candlestick chart with 20-EMA overlay and key support level at 24,700.
  - **Macro Events Card (`macro-events-card.js`)**: Next 5 days economic calendar (RBI Policy Meet, US CPI, FOMC Minutes).
  - **AI Reading Queue Card (`reading-queue-card.js`)**: Curated overnight institutional notes with reading time estimates.
- **AI Trading Partner Pre-Market Brief (`GET /api/ai/brief/today`, `web/src/components/ai-brief-card.js`)**: New backend endpoint generating <80-word actionable daily briefing framed as elimination criteria via Gemini AI Router, with lilac left-border card finish and persistent floating AI launcher orb in the bottom-right corner.
- **Test Suite Expansion**: Added 25 new automated tests across backend routes (`tests/api/test_ai_brief.py`, `tests/api/test_readiness_kpis.py`) and frontend components (`web/tests/test_readiness_ritual.test.js`, `web/tests/test_verdict_card.test.js`, `web/tests/test_ai_brief_card.test.js`, `web/tests/test_home_composition.test.js`), bringing the automated test suite to **244 passing tests** (216 pytest + 28 vitest, 0 failures).

### Added - BUILD-8 (2026-09-07)
- **Two-Tier Risk Model (`src/swayam/rule_engine/statistical_risk.py`, `src/swayam/vault_reader.py`, `src/swayam/api/routes/validation.py`)**: Replaced single mathematical worst-case loss check with Abhishek's two-tier risk framework:
  1. **Tier 1 — Realistic Risk Cap (1.0% of margin base)**: Primary sizing gate evaluating candidate spread losses if NIFTY moves ±2σ over 1 day based on trailing 20-day realized volatility.
  2. **Tier 2 — Blast Radius Fuse (3.0% of margin base)**: Emergency black-swan ceiling gating against absolute mathematical max loss (`max_loss_inr`).
- **Realized Volatility Engine (`src/swayam/options_math/realized_vol.py`)**: Trailing annualized historical volatility calculation from daily closes stored in DuckDB (`nifty_daily_bars`), converted to daily 1σ standard deviation, backed by `realized_vol_cache`.
- **DuckDB Migration 003 (`migrations/duckdb/003_realized_vol_cache.sql`)**: Additive migration schema for caching daily realized volatility calculations with idempotent migration runner wired into `LocalDB.init_schema()`.
- **Payoff PnL at Spot Engine (`src/swayam/options_math/payoff.py`)**: Pure calculation function `pnl_at_spot()` computing exact intrinsic payoff at stressed index levels for arbitrary multi-leg options structures.
- **Obsidian Vault Method Rules Integration (`Risk Management Rules.md`)**: Enriched vault rules with the two-tier philosophy and dynamic parsing in `VaultReader` (`realistic_risk_cap_pct`, `realistic_stress_sigma`, `realized_vol_window_days`).
- **Frontend Two-Tier Risk Badges (`web/src/components/rule-validation.js`)**: Displays Realistic Risk and Blast Radius side-by-side with Abhishek voice tooltips, rupee caps, margin base percentages, and execution gating.
- **AI Persona & Context Alignment (`src/swayam/ai/persona/trading_partner.py`)**: Embedded two-tier risk explanation in `TRADING_PARTNER_PERSONA` and injected today's computed 20-day realized volatility (`realistic_vol_pct`) into context assembly.
- **Unified Smoketest Check (`src/swayam/smoketest.py`)**: Added check step computing and displaying trailing 20-day NIFTY realized volatility.
- **Zero Silent Fallback Discipline**: Strictly eliminated silent defaults in trade validation; raises `InsufficientHistoryError`, `HistoricalDataUnavailableError`, `MethodRulesParseError`, and HTTP 503 when historical bars are missing.
- **Test Suite Expansion**: Added 30 new tests across options math, DuckDB migrations, statistical risk, vault parsing, API routes, AI persona, and web components, bringing the suite to 207 pytest + 10 vitest (217 total passing).

### Added - BUILD-7 (2026-09-06)
- **Live P&L & Valuation Endpoint (`GET /api/positions/live`)**: Computes real-time mark-to-market position valuations, unrealized P&L in rupees, % of risk, and updated Greeks from live FYERS option chain quotes, backed by 5-second in-memory caching to eliminate rate limit overhead.
- **Position Exit Flow (`POST /api/positions/{id}/close`)**: Complete trade close endpoint implementing strict Database-before-Journal ordering (`swayam_trade_history` insert -> `swayam_positions` closed update -> Obsidian journal update). Realizes P&L and estimates transaction charges without hardcoded values.
- **Obsidian Journal Exit Block Generator (`append_exit_block()`)**: Auto-updates the YAML frontmatter (`status: closed`, `closed_at`, `realized_pnl_inr`, `close_reason`) and cleanly replaces the placeholder section with a formatted exit table, realized P&L metrics, and post-trade reflection prompts.
- **Interactive Active Trades Panel (`web/src/components/active-trades.js`)**: Real-time frontend component with 5s background polling, live P&L color changes (green/red), non-destructive stale quote banner on 503 errors, and an interactive Close modal with editable exit leg premiums.
- **AI Model Region Resolution**: Enabled global routing (`GCP_AI_LOCATION=global`) for Google Cloud Vertex AI Gemini calls, unblocking `gemini-3.1-pro-preview` without requiring model downgrades.
- **Test Suite Expansion**: Added 16 new automated tests across `tests/api/test_positions_live.py`, `tests/api/test_close_position.py`, and `tests/api/test_journal_exit_block.py`, bringing the automated test suite to 176 pytest + 6 vitest (182 total passing).

### Added - BUILD-6 (2026-09-06)
- **AI Trading Partner (`src/swayam/ai/`)**: Purpose-built options specialist AI colleague powered by Google Cloud Vertex AI Gemini with Application Default Credentials (ADC) and zero JSON key files.
- **3-Tier Model Router (`router.py`)**: Automatic multi-tier model fallback: Primary `gemini-3.1-pro-preview` for deep reasoning, fallback `gemini-2.5-pro` on rate limits or permissions, and lightweight `gemini-2.5-flash-lite` for quick widget calculations.
- **Trading Partner Persona (`persona/trading_partner.py`)**: Strict trading mentor persona enforcing 6 non-negotiable behavioral constraints (never naked longs, never revenge encouragement, never stop-widening, never override RED readiness verdicts, never claim direction certainty, and never break risk caps).
- **Dynamic Context Assembly (`assemble_context()`)**: Real-time context builder refreshing every user message with Method rules, margin base, live NIFTY spot, readiness check, open positions, recent journal entries, and historical summaries.
- **SSE Streaming Endpoints (`routes/ai.py`)**: Server-Sent Events API endpoints (`POST /api/ai/conversations/{id}/messages`, `GET/POST /conversations`, `archive`, `delete`, `usage/today`) with conversation persistence in Supabase and daily rupee cost tracking (`swayam_ai_usage_daily`).
- **Collapsible Dashboard Chat Panel (`web/src/components/ai-chat.js`)**: Real-time streaming AI chat sidebar on the dashboard with quick starter prompts, history drawer, and daily spend footer.
- **Database Migration 002 (`migrations/002_ai_conversations_and_rule_log.sql`)**: Created tables for conversations, messages, rule evolution log, daily usage tracking, and documented single-user private trading terminal posture with RLS disabled.
- **Test Suite Expansion**: Added 48 new tests across `tests/ai/` and `tests/api/test_ai_endpoints.py`, bringing the automated test suite to 160 pytest + 6 vitest (166 total passing).

### Added - BUILD-5 (2026-09-05)
- **Live Options Recorder Cloud Function (`cloud/recorder/`)**: Standalone Gen2 Cloud Function deployed to Google Cloud (`asia-south1`) running every 60s during trading hours (09:15–15:30 IST, Mon–Fri).
- **Time Gating & Idempotency**: Strict market hours check exits as an idempotent HTTP 200 no-op outside trading hours. GCS Parquet writes deduplicate strictly on `(snapshot_time_utc, symbol)` before rewriting the daily file, preventing duplicates from scheduler retries or clock skew.
- **Unified DuckDB Historical Storage (`src/swayam/local_db.py`)**: Extended `options_history` table with intraday columns (`snapshot_time_utc`, `bid`, `ask`, `iv`, `delta`, `gamma`, `theta`, `vega`) and composite natural key `(trade_date, symbol, snapshot_time_utc)`. Unified table houses both historical Bhavcopy and live recorded snapshots without schema fragmentation.
- **FYERS Token Refresher & Secret Manager Sync (`scripts/refresh_fyers_token.py`)**: Interactive helper to authenticate with FYERS and push the new access token to Google Cloud Secret Manager (`fyers-access-token`) and update `.env`.
- **Automated Cloud Deployer (`scripts/deploy_recorder.py`)**: One-command deployment script provisioning the Cloud Function Gen2 and configuring Cloud Scheduler.
- **Nightly GCS Ingest Tool (`scripts/ingest_gcs_to_duckdb.py`)**: Synchronizes daily Parquet files from Cloud Storage to local DuckDB with full `--date-range` backfill support and execution logging.
- **Documentation**: Added `docs/gcp_setup.md`, `docs/recorder_architecture.md`, updated `SETUP.md` with morning refresh and nightly ingest scheduled tasks, and expanded `README.md`.
- **Test Suite Expansion**: Added 10 new tests across `tests/cloud/` and `tests/scripts/`, bringing the verified automated suite to 112 pytest + 6 vitest (118 total passing).

### Added - BUILD-4 (2026-09-05)
- **Operational Readiness Engine (`src/swayam/readiness/`)**: 60-second manual-first readiness check operationalizing Method `Operational Readiness Rules.md`.
- **Verdict Calculator (`verdict.py`)**: Computes 🟢/🟡/🔴 verdicts evaluating sleep buckets (<5h blocks, 5-6h caps at 75% size), alcohol lockout (90-day lockout & re-entry ramp), 48h workout window, mood turbulence (Angry/Grief blocks), and life stressors via `TolerantComparator`.
- **Daily Log Reader (`daily_log_reader.py`)**: Parses today's Obsidian daily log (`01 - Daily Logs/{YYYY-MM-DD}.md`) for available Atlas defaults to pre-populate form suggestions while keeping manual feelings primary.
- **Evening Reconciler (`reconciler.py` & `scripts/run_reconciler.py`)**: Nightly 22:00 IST cross-check comparing pre-market self-assessment against synced Atlas health data for pattern tracking without modifying trade history.
- **REST API Endpoints (`routes/readiness.py`)**: Added `GET /api/readiness/today`, `POST /api/readiness/log`, and `POST /api/readiness/reconcile`.
- **Validation Safety Gate Integration (`routes/validation.py`)**: Integrated readiness gate into `/api/strategy/validate`—RED verdict strictly blocks trade validation; YELLOW verdict automatically enforces reduced sizing ceiling.
- **Frontend Readiness Component (`readiness-check.js`)**: Compact pre-trade form with mood pill selectors and live verdict badge with re-log and reconciliation capabilities.
- **Test Suite Expansion**: Added 20 new tests across `tests/readiness/` and `tests/api/test_readiness_endpoints.py`, bringing the automated test suite to 102 pytest + 6 vitest (108 total passing).

### Fixed - BUILD-3 FIXES (2026-09-05)
- **api (validation)**: Eliminated silent fallback `margin_base_inr = 850000.0`. Missing or unreachable Supabase margin base now raises `HTTPException(503)` loudly with diagnostic detail.
- **api (execution)**: Eliminated silent fallback `margin_base_inr = 850000.0`. Missing margin base now raises `HTTPException(503)` loudly.
- **api (execution)**: Reordered execution lifecycle: Supabase INSERT to `swayam_positions` now executes BEFORE markdown journal writing, preventing orphan files on database failure. Eliminated silent `except Exception: pass` swallowing.
- **api (execution)**: Added `expiry_date` to `db_record` to satisfy NOT NULL schema constraint on `swayam_positions`.
- **api (validation)**: Replaced hardcoded `0.02` tolerance literals with configurable `settings.default_tolerance_pct` from `.env`.
- **tests**: Added 5 new regression tests across `test_execute_paper.py` and `test_strategy_validate.py`, expanding the verified test suite to 82 pytest + 6 vitest (88 total passing).

### Added - BUILD-3 (2026-09-05)
- **FastAPI Backend (`src/swayam/api/`)**: High-performance asynchronous REST API and WebSocket services for market data, rules gating, strategy calculations, and paper execution.
- **Obsidian Trade Journal Writer (`journal_writer.py`)**: Automatic generation of YAML-frontmattered companion markdown trade logs in `02 - Projects/Trading/04 - Journal/{YYYY-MM-DD}-trade{XX}.md`.
- **Real-Time Strategy Builder (`web/`)**: Dark-mode web dashboard built with Vite 6 and Plotly.js (`plotly.js-dist-min`).
- **Interactive Payoff Visualizer (`payoff-chart.js`)**: Dual-horizon interactive payoff curve (T+0 today vs at-expiry) with labeled breakevens and live spot markers.
- **Pre-Trade Method Rule Gating (`routes/validation.py`)**: Automatic audit against 1% risk ceiling, 1:2.0 R:R floor, and overnight hedge caps using `TolerantComparator`.
- **Paper Execution Modal & Active Trades Panel**: Safe simulation mode saving open positions to database while strictly blocking real broker orders (`mode: "real"` returns 403 Forbidden).
- **Test Suite Expansion**: Added 17 new backend integration tests and 6 frontend unit tests, expanding the total automated suite to 83 passing tests.

### Added - BUILD-2 (2026-09-05)
- **Options Math Engine (`src/swayam/options_math/`)**: pure-Python computation layer for pricing, Greeks, and payoff curves.
- **Typed models (`models.py`)**: `Leg`, `Spread`, `GreeksSummary`, `PayoffCurve` dataclasses.
- **Pricing engine (`engine.py`)**: Black-Scholes wrapper via `vollib` / `py_vollib` with edge-case handling and `IVSolveFailed` exception.
- **Payoff computation (`payoff.py`)**: dual-curve (today + at-expiry) computation with breakeven and max/min detection.
- **Aggregated Greeks (`greeks.py`)**: multi-leg position Greeks with unit normalization (theta in ₹/day, vega in ₹ per 1% IV).
- **Strategy presets (`strategies.py`)**: Bear Put Spread, Bull Call Spread, Iron Condor, Calendar Spread factories with 50-point strike snapping.
- **Test coverage**: 25 new unit tests bringing total to 60 passing tests.

### Fixed - BUILD-1 FIXES (2026-09-04)
- **vault_reader**: Eliminated silent fallback on missing margin base range ('₹X–Y lakh'); now raises `MethodRulesParseError`.
- **vault_reader**: Eliminated silent fallback on missing sleep threshold; now raises `MethodRulesParseError`.
- **vault_reader**: Eliminated silent fallback on missing sleep reduced sizing parameters; now raises `MethodRulesParseError`.
- **vault_reader**: Eliminated silent fallback on missing alcohol lockout duration; now raises `MethodRulesParseError`.
- **vault_reader**: Replaced hardcoded `reentry_ramp` default with dynamic parsing of all 4 tiers from `Operational Readiness Rules.md`.
- **db**: Removed silent rupee fallback in `get_margin_base_inr()`; now raises `DatabaseError` if row missing or invalid.
- **git**: Added Python packaging build artifacts (`*.egg-info/`, `build/`, `dist/`, `*.egg`) to `.gitignore`.
- **tests**: Added regression tests across `test_vault_reader.py` and `test_db.py`, expanding the verified test suite to 35 passing tests.

### Added - BUILD-1 (2026-09-04)
- **Scaffold**: Initial repository layout with typed modules, `.env.example`, `requirements.txt`, `pyproject.toml`, and `package.json`.
- **Architectural Principles**: Documented multi-year sustainability guidelines in `README.md`.
- **Rules Engine (`rules_engine.py`)**: Implemented `TolerantComparator` with a 2% tolerance band for all rule caps and floors.
- **Vault Reader (`vault_reader.py`)**: Built dynamic parser extracting Method rules as percentages from Obsidian Second Brain.
- **AI Adapter (`src/swayam/ai/`)**: Established provider adapter architecture (`vertex`, `openrouter`, `direct`) and authored `docs/AI_INTEGRATION.md` adapting POS design bible principles.
- **TradingView Helper (`tradingview_helper.py`)**: Built URL generator for dual-monitor charting with TradingView.
- **Broker & Data Clients**: Skeleton for FYERS API v3 (`fyers_client.py`), local DuckDB cache (`local_db.py`), and official NSE UDiFF Bhavcopy downloader (`bhavcopy.py`).
- **Database Schema**: Additive-only initial Supabase migration `001_initial_schema.sql` and migration runner.
- **Health Check**: Comprehensive verification tool `swayam.smoketest` checking environment, vault, rules, DB, and broker links.

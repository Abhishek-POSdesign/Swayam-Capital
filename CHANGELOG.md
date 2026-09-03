# Changelog

All notable changes to **Swayam Capital** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

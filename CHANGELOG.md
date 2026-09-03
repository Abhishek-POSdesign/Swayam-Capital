# Changelog

All notable changes to **Swayam Capital** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

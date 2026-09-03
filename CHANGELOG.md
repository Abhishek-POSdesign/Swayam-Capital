# Changelog

All notable changes to **Swayam Capital** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

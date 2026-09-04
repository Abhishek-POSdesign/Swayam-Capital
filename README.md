# Swayam Capital 🏛️

> *"I will NOT trade from the broker's platform, especially in the beginning. I will have my own platform, with my rules, my system — where I want to look, what time it will open, what time it will close, how it will close, how it will behave. I'll build on my terms, my rules, my requirement."*  
> — **Abhishek Sikka (Personal Trading Brief, 2026-09-03)**

**Swayam Capital** is a custom, rule-enforced trading platform built by and for Abhishek Sikka. It replaces discretionary decision moments with rigorous rule enforcement, pre-trade risk filters, automated readiness assessments, and an integrated visual options strategy builder.

---

## 🏛️ Architectural Principles — Read Before Contributing

To guarantee multi-year sustainability and protect against system drift, every contributor and AI assistant must adhere strictly to these principles:

1. **Percentages-Only Rule Storage & Tolerant Comparisons:**  
   Every risk parameter (per-trade risk, daily loss, weekly loss) is stored strictly as a **percentage of margin base**, never as a rupee amount. All rule evaluations must use the `TolerantComparator` with a default 2% tolerance band. Hardcoded rupee values are prohibited.
2. **Every Module Has a Clear Purpose & Documentation:**  
   Every Python file begins with a top-of-file docstring explaining its exact responsibility in one paragraph. Every public function, class, and method must contain clear type hints and docstrings.
3. **Additive-Only Migrations:**  
   Database migrations in `migrations/` are immutable history. Never edit an existing migration once shipped. All schema modifications require a new numbered file (e.g., `002_add_field.sql`).
4. **Strict Modular Isolation:**  
   Modules in `src/swayam/` must remain decoupled. Modules do not import from peer modules across domain boundaries (e.g., `vault_reader.py` never imports from `fyers_client.py`). `config.py` is the only cross-cutting configuration provider.
5. **AI as a First-Class Collaborator:**  
   AI acts as an advisory partner, explanation layer, and synthesizer (see `docs/AI_INTEGRATION.md`). It never operates as an unverified automatic execution bot. The rule engine and broker client own execution truth.
6. **Dual-Screen TradingView Philosophy:**  
   Swayam minimizes internal charting. Only the interactive Strategy Builder payoff curve uses Plotly.js internally. All price action charting is surfaced on the second screen via TradingView (`tradingview_helper.py`).
7. **Secrets and Data Isolation:**  
   `.env` and `data/` are strictly local and gitignored. Secrets are never committed to version control or saved in cloud drives.

---

## 📁 Repository Layout

```
Swayam Capital/
├── .gitignore                     # Excludes secrets (.env), local data (data/), caches
├── README.md                      # Platform overview and architectural principles
├── SETUP.md                       # Step-by-step developer environment setup guide
├── CHANGELOG.md                   # Keep-a-Changelog tracking of all revisions
├── pyproject.toml                 # Pinned Python package dependencies and build config
├── requirements.txt               # Pinned pip requirements
├── package.json                   # Web frontend dependencies (Vite + Plotly.js)
├── .env.example                   # Template configuration file with all secret keys blank
├── src/
│   └── swayam/
│       ├── __init__.py
│       ├── config.py              # Typed settings singleton loaded from .env
│       ├── rules_engine.py        # TolerantComparator and rule evaluation logic
│       ├── vault_reader.py        # Dynamic parser for Obsidian Second Brain Method files
│       ├── fyers_client.py        # FYERS API v3 REST and WebSocket wrapper skeleton
│       ├── bhavcopy.py            # Official NSE UDiFF Bhavcopy historical data downloader
│       ├── db.py                  # Supabase client wrapper
│       ├── local_db.py            # Local DuckDB manager for historical options cache
│       ├── tradingview_helper.py  # TradingView URL generator for second-screen charts
│       ├── ai/                    # Multi-provider AI adapter architecture (BUILD-6)
│       │   ├── __init__.py
│       │   ├── adapter.py         # Abstract AIProvider interface with custom error types
│       │   ├── factory.py         # Provider factory resolving AI_PROVIDER
│       │   ├── router.py          # 3-tier model router (primary / fallback / lightweight)
│       │   ├── persona/           # Purpose-built Trading Partner mentor persona
│       │   │   ├── __init__.py
│       │   │   └── trading_partner.py # Static persona rules + dynamic context assembler
│       │   └── providers/
│       │       ├── __init__.py
│       │       ├── vertex.py      # Real Google Cloud Vertex AI (Gemini) provider via ADC
│       │       ├── openrouter.py  # OpenRouter provider stub
│       │       └── direct.py      # Direct API provider stub (Anthropic/OpenAI)
│       ├── readiness/             # Operational Readiness evaluation engine (BUILD-4)
│       │   ├── __init__.py
│       │   ├── models.py          # ReadinessInput, ReadinessVerdict, ReadinessReconciliation
│       │   ├── verdict.py         # 🟢/🟡/🔴 verdict calculator against Method rules
│       │   ├── daily_log_reader.py# Parses today's Obsidian daily log for defaults
│       │   └── reconciler.py      # End-of-day cross-check against synced Atlas data
│       └── smoketest.py           # Unified connection and health verification tool
├── cloud/
│   └── recorder/                  # 24/7 Live Options Recorder Cloud Function Gen2 (BUILD-5)
│       ├── main.py                # HTTP entrypoint called every 60s by Cloud Scheduler
│       ├── fyers_recorder.py      # Time gating, FYERS chain fetch, GCS append & deduplication
│       ├── config.py              # Cloud Function config and Secret Manager token loader
│       ├── requirements.txt       # Minimal cloud runtime dependencies
│       └── README.md              # Cloud recorder documentation
├── web/                           # Dashboard and Strategy Builder frontend
│   ├── src/components/ai-chat.js  # Collapsible streaming AI chat sidebar panel
│   └── README.md                  # Frontend scaffolding notes (BUILD-3)
├── migrations/                    # Additive SQL migrations for Supabase
│   ├── 001_initial_schema.sql     # Core positions, trade history, and readiness tables
│   ├── 002_ai_conversations_and_rule_log.sql # AI chat state, rule log, daily cost tracking
│   └── README.md                  # Migration instructions
├── scripts/                       # Operational utility scripts
│   ├── apply_migration.py         # Executes SQL migrations against Supabase
│   ├── download_all_bhavcopy.py   # Bulk historical NSE Bhavcopy downloader
│   ├── generate_fyers_token.py    # Helper for FYERS OAuth access token flow
│   ├── refresh_fyers_token.py     # Interactive FYERS token refresher & Secret Manager sync
│   ├── deploy_recorder.py         # Automated GCP Cloud Function & Scheduler deployer
│   ├── ingest_gcs_to_duckdb.py    # Local nightly GCS to DuckDB options ingest tool
│   └── run_reconciler.py          # Windows task script for nightly readiness reconciliation
├── tests/                         # Pytest automated test suite (176 tests + 6 vitest)

│   ├── ai/                        # Vertex provider, persona, context assembly tests
│   ├── api/                       # API route integration tests (including AI routes)
│   ├── cloud/                     # Cloud recorder unit tests
│   ├── readiness/                 # Readiness engine and reconciler tests
│   ├── scripts/                   # CLI and ingest script tests
│   └── ...                        # Core unit and mock tests
├── data/                          # Local data cache (gitignored)
│   ├── bhavcopy/                  # Raw downloaded NSE CSV files
│   ├── options_cache.duckdb       # DuckDB multi-year options history database
│   └── ingest.log                 # Nightly sync execution log
└── docs/
    ├── architecture.md            # System architecture mapping
    ├── AI_INTEGRATION.md          # Distilled POS design-bible AI philosophy
    ├── AI_TRADING_PARTNER.md      # Purpose-built AI partner architecture & persona guide
    ├── readiness_workflow.md      # 60-second manual-first readiness workflow
    ├── gcp_setup.md               # One-time Google Cloud setup walkthrough
    └── recorder_architecture.md   # Live options recorder design and schema

```

---

## ⚡ Quick Start

1. **Clone & Setup Environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. **Configure Secrets:**
   ```powershell
   copy .env.example .env
   # Edit .env with your FYERS and Supabase credentials
   ```
3. **Run Health Verification (Smoketest):**
   ```powershell
   python -m swayam.smoketest
   ```

## 🚀 Running the Dashboard (Full MVP)

Run the backend and frontend in two separate terminals:

1. **Terminal 1 — Start the FastAPI Backend:**
   ```powershell
   python -m uvicorn swayam.api.main:app --reload --port 8000
   ```

2. **Terminal 2 — Start the Vite Frontend Dev Server:**
   ```powershell
   cd web
   npm install
   npm run dev
   ```

3. **Open in Browser:**
   Navigate to [**http://localhost:5173**](http://localhost:5173) in your browser.
   - Choose a preset (e.g. Bear Put Spread)
   - Inspect the live Plotly.js payoff curve and portfolio Greeks
   - Audit against Obsidian Method rules
   - Click "⚡ EXECUTE PAPER TRADE" to write directly to your Obsidian vault!

See [`SETUP.md`](SETUP.md) for full walkthrough and database setup.

---

## 🔒 License

Private, proprietary software for personal use only by Abhishek Sikka. All rights reserved.

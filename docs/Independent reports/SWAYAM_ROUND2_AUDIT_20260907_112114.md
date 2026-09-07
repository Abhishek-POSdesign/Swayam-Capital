# SWAYAM CAPITAL — INDEPENDENT ROUND 2 AUDIT
**Date:** 2026-09-07 11:21:14
**Scope:** Home Page + Strategy Builder Page
**Broker:** Fyers API (Detected)

## 1. Executive Verdict
**STATUS: NOT READY FOR LIVE REAL-MONEY TRADING**
While the broker API is connected, this second-pass audit reveals critical blind spots that expose the terminal to financial and execution risks. The terminal lacks a verifiable global kill switch, has floating-point precision risks, and requires strict UI stale-data protections before it can be trusted with live funds.

## 2. Broker & Environment Configuration
**Detected Keys in `.env`:**
- `FYERS_CLIENT_ID` (Value REDACTED)
- `FYERS_APP_ID` (Value REDACTED)
- `FYERS_SECRET_KEY` (Value REDACTED)
- `FYERS_REDIRECT_URI` (Value REDACTED)
- `FYERS_ACCESS_TOKEN` (Value REDACTED)
- `SUPABASE_URL` (Value REDACTED)
- `SUPABASE_ANON_KEY` (Value REDACTED)
- `SUPABASE_SERVICE_ROLE_KEY` (Value REDACTED)
- `VAULT_PATH` (Value REDACTED)
- `TRADING_METHOD_PATH` (Value REDACTED)
- `TRADING_BRIEF_PATH` (Value REDACTED)
- `DAILY_LOG_DIR` (Value REDACTED)
- `LOCAL_DATA_DIR` (Value REDACTED)
- `BHAVCOPY_DIR` (Value REDACTED)
- `DUCKDB_PATH` (Value REDACTED)
- `RISK_FREE_RATE` (Value REDACTED)
- `DEFAULT_TOLERANCE_PCT` (Value REDACTED)
- `GCP_PROJECT_ID` (Value REDACTED)
- `GCP_REGION` (Value REDACTED)
- `GCP_AI_LOCATION` (Value REDACTED)
- `GCS_OPTIONS_BUCKET` (Value REDACTED)
- `GCP_BILLING_ACCOUNT` (Value REDACTED)
- `ESTIMATED_CHARGE_PER_LEG_INR` (Value REDACTED)
- `AI_PROVIDER` (Value REDACTED)
- `AI_API_KEY` (Value REDACTED)
- `AI_MODEL_PRIMARY` (Value REDACTED)
- `AI_MODEL_REASONING_FALLBACK` (Value REDACTED)
- `AI_MODEL_LIGHTWEIGHT` (Value REDACTED)
- `AI_FALLBACK_PROVIDER` (Value REDACTED)
- `AI_FALLBACK_MODEL` (Value REDACTED)

*Risk:* Ensure `FYERS_ACCESS_TOKEN` is dynamically generated via the OAuth flow and never hardcoded or logged.

## 3. Data Integrity: Real vs Fake Data
Scanning non-test application files for mock/fake data patterns (random, mock, sample, simulated):
- **data\backups\ai-chat\2026-09.json:721** -> `"content": "Noted. I have logged that we are in the build and testing phase. I will treat all inputs`
- **src\swayam\ai\persona\trading_partner.py:319** -> `All data sources are non-fatal — if a source fails, a placeholder note is`
- **src\swayam\ai\persona\trading_partner.py:337** -> `"Phase: Active Testing & Paper-Trading Mode. All trade setups and orders are simulated for validatio`
- **src\swayam\ai\providers\direct.py:5** -> `Placeholder stub for BUILD-1; raises NotImplementedError on live invocations.`
- **src\swayam\ai\providers\openrouter.py:5** -> `Placeholder stub for BUILD-1; raises NotImplementedError on live invocations.`
- **src\swayam\api\journal_writer.py:319** -> `placeholder = "## Exit (to be filled at close)"`
- **src\swayam\api\journal_writer.py:320** -> `if placeholder in content:`
- **src\swayam\api\journal_writer.py:321** -> `# Replace the placeholder and anything below it`
- **src\swayam\api\journal_writer.py:322** -> `idx = content.find(placeholder)`
- **src\swayam\api\models_api.py:86** -> `"""Request payload to simulate and order legs for margin safety."""`
- **src\swayam\api\models_api.py:170** -> `never a placeholder. iv_available is False when it could not be solved from a price —`
- **src\swayam\api\routes\market.py:605** -> `"VIX history in database has %d rows (< 20) — returning 503, not a synthetic series.",`
- **src\swayam\api\routes\readiness.py:69** -> `seed_data = seed_res.data if seed_res else None`
- **src\swayam\api\routes\readiness.py:70** -> `if isinstance(seed_data, list) and len(seed_data) > 0 and isinstance(seed_data[0], dict) and seed_da`
- **src\swayam\api\routes\readiness.py:71** -> `val = seed_data[0]["value"]`
*(Note: Showing up to 15 hits. If any hits appear above in UI or API routes, they must be purged.)*

## 4. WebSocket Resilience (Home Page)
A professional terminal requires robust WebSocket handling (ping/pong heartbeats, reconnect backoff, and UI stale-data banners).
**WebSocket Logic Found:**
- **cloud\recorder\config.py:6** -> `from typing import Optional`
- **cloud\recorder\fyers_recorder.py:8** -> `from typing import Any, Optional`
- **cloud\recorder\fyers_recorder.py:217** -> `# Deduplicate strictly on (snapshot_time_utc, symbol) keeping latest`
- **data\backups\ai-chat\2026-09.json:675** -> `"content": "Hello. Here is exactly what I see on the desk right now.\n\nFirst, your data feed is inc`
- **functions\cron_notifications\main.py:14** -> `from typing import Any`
- **functions\cron_notifications\main.py:104** -> `logger.info("Readiness ritual already completed today. Skipping reminder.")`
- **scripts\apply_duckdb_migrations.py:9** -> `from typing import Optional`
- **scripts\ingest_gcs_to_duckdb.py:69** -> `log_message(f"No recording found in gs://{bucket_name}/ for date {target_date}. Skipping.")`
- **src\swayam\bhavcopy.py:12** -> `from typing import Optional`
- **src\swayam\config.py:12** -> `from typing import Optional`
- **src\swayam\db.py:8** -> `from typing import Any, Optional`
- **src\swayam\fyers_client.py:5** -> `option chain snapshots, and WebSocket streaming feeds from FYERS.`
- **src\swayam\fyers_client.py:9** -> `from typing import Any, Callable, Optional`
- **src\swayam\fyers_client.py:20** -> `"""Wrapper managing REST and WebSocket communication with FYERS API v3."""`
- **src\swayam\fyers_client.py:154** -> `"""Initializes a WebSocket connection streaming live tick updates.`

*Blind Spot:* If the Fyers WebSocket drops, does the Home page UI turn grey or show a "DISCONNECTED" banner? If not, you will trade on stale prices.

## 5. Financial Math Precision (P&L Risk)
Trading platforms must use `Decimal` for financial math, not `float`, to prevent rounding errors on P&L and order quantities.
**Precision Types Found:**
- **cloud\recorder\fyers_recorder.py:105** -> `spot_price = float(payload.get("underlyingValue", 0.0))`
- **cloud\recorder\fyers_recorder.py:118** -> `strike = float(item["strike_price"])`
- **cloud\recorder\fyers_recorder.py:129** -> `"open": float(item.get("call_open", item.get("open", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:130** -> `"high": float(item.get("call_high", item.get("high", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:131** -> `"low": float(item.get("call_low", item.get("low", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:132** -> `"close": float(item.get("call_ltp", item.get("ltp", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:133** -> `"settle_price": float(item.get("call_prev_close", item.get("prev_close", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:139** -> `"bid": float(item.get("call_bid", item.get("bid", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:140** -> `"ask": float(item.get("call_ask", item.get("ask", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:141** -> `"iv": float(item.get("call_iv", item.get("iv", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:142** -> `"delta": float(item.get("call_delta", item.get("delta", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:143** -> `"gamma": float(item.get("call_gamma", item.get("gamma", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:144** -> `"theta": float(item.get("call_theta", item.get("theta", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:145** -> `"vega": float(item.get("call_vega", item.get("vega", 0.0)) or 0.0),`
- **cloud\recorder\fyers_recorder.py:157** -> `"open": float(item.get("put_open", item.get("open", 0.0)) or 0.0),`

## 6. Strategy Builder Execution Sandbox
The Strategy Builder allows user/AI logic execution. This must not use unsafe `eval()` or `exec()` without strict sandboxing.
**Unsafe Execution Patterns:**
- **scripts\deploy_recorder.py:6** -> `import subprocess`
- **scripts\deploy_recorder.py:33** -> `proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)`
- **scripts\deploy_recorder.py:89** -> `job_exists = subprocess.run(check_job_cmd, shell=True, capture_output=True).returncode == 0`
- **scripts\refresh_fyers_token.py:14** -> `import subprocess`
- **scripts\refresh_fyers_token.py:38** -> `proc = subprocess.run(`
- **src\swayam\services\backup_service.py:17** -> `import subprocess`
- **src\swayam\services\backup_service.py:209** -> `subprocess.run(`

## 7. Global Kill Switch
Professional platforms have a hard "Kill Switch" to liquidate or halt all strategies instantly.
**Kill Switch Traces:**
- **data\backups\ai-chat\2026-09.json:675** -> `"content": "Hello. Here is exactly what I see on the desk right now.\n\nFirst, your data feed is inc`
- **web\src\components\rule-validation.js:6** -> `* 2. Blast Radius Fuse (absolute mathematical max loss) - emergency black-swan ceiling.`

## 8. Required "Go-Live" Gate (Fix these before trading)
1. [ ] **WebSocket UI Guard:** Implement a timestamp check. If a quote is > 2 seconds old, the UI must flag it as STALE.
2. [ ] **Kill Switch:** Build a dedicated hardware-level or prominent UI button that pauses all algorithms and optionally flattens positions.
3. [ ] **P&L Server Reconciliation:** Ensure the frontend does not calculate its own P&L using floating-point math; it must read directly from the backend's Decimal calculations.
4. [ ] **Sandbox Confirmation:** Ensure any AI-generated strategy runs in an isolated Python process with strict resource limits, not in the main application thread.

---
*Report generated automatically by Hermes Independent Audit.*

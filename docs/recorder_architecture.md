# 📼 Swayam Live Options Recorder Architecture

## 1. Purpose & Motivation
Brokers (including FYERS) purge expired option contracts from their servers, making historical options data and intraday Greeks unavailable for backtesting. 

To build a proprietary high-resolution database of NIFTY options prices, Greeks, and Open Interest, Swayam Capital runs an autonomous 24/7 Cloud Function in Google Cloud (`asia-south1`).

---

## 2. Architecture & Data Flow

```
[Cloud Scheduler]
       │
       ▼ (Every 1 min: 09:15–15:30 IST, Mon–Fri)
[Cloud Function: swayam-recorder]
       │
       ├─► Check Market Hours (Exits 200 immediately on weekends/outside hours)
       ├─► Fetch Token from Google Secret Manager (`fyers-access-token`)
       ├─► Call FYERS API v3 (20 strikes each side of ATM, weekly + monthly expiries)
       ├─► Extract LTP, Bid/Ask, Greeks, Volume, OI, PDOI
       │
       ▼ (Append & Deduplicate on snapshot_time_utc + symbol)
[Cloud Storage: gs://swayam-capital-options-data/]
       │ Path: {YYYY}/{MM}/{DD}/nifty_chain.parquet
       │
       ▼ (Nightly 22:30 IST sync via Windows Task Scheduler)
[scripts/ingest_gcs_to_duckdb.py]
       │
       ▼ (Idempotent UPSERT on trade_date + symbol + snapshot_time_utc)
[Local DuckDB: data/options_cache.duckdb -> options_history]
```

---

## 3. Data Schema

### `options_history` (DuckDB) & Parquet File Schema
| Column | Type | Description |
|---|---|---|
| `snapshot_time_utc` | `TIMESTAMP` | UTC timestamp of the snapshot |
| `trade_date` | `DATE` | Trading date in IST (`YYYY-MM-DD`) |
| `symbol` | `VARCHAR` | Option contract symbol (e.g. `NSE:NIFTY26SEP24850CE`) |
| `underlying` | `VARCHAR` | Underlying index (`NIFTY`) |
| `expiry_date` | `DATE` | Expiry date of the contract |
| `strike` | `DECIMAL(10,2)` | Strike price |
| `option_type` | `VARCHAR` | `CE` (Call) or `PE` (Put) |
| `open` | `DECIMAL(10,2)` | Day open price |
| `high` | `DECIMAL(10,2)` | Day high price |
| `low` | `DECIMAL(10,2)` | Day low price |
| `close` | `DECIMAL(10,2)` | Last traded price (LTP) at snapshot time |
| `settle_price` | `DECIMAL(10,2)` | Previous close or settlement price |
| `volume` | `BIGINT` | Cumulative traded contracts |
| `turnover_inr` | `DECIMAL(15,2)` | Cumulative turnover in INR |
| `open_interest` | `BIGINT` | Current Open Interest (OI) |
| `change_in_oi` | `BIGINT` | Day change in OI (PDOI) |
| `underlying_spot`| `DECIMAL(10,2)` | NIFTY 50 spot price at snapshot time |
| `bid` | `DECIMAL(10,2)` | Best bid price |
| `ask` | `DECIMAL(10,2)` | Best ask price |
| `iv` | `DECIMAL(6,4)` | Implied Volatility (annualized, e.g. `0.1450`) |
| `delta` | `DECIMAL(6,4)` | Option Delta |
| `gamma` | `DECIMAL(8,6)` | Option Gamma |
| `theta` | `DECIMAL(10,2)` | Option Theta (decay per day) |
| `vega` | `DECIMAL(10,2)` | Option Vega (sensitivity to 1% IV change) |

---

## 4. Idempotency Guarantees

1. **Cloud Storage Write:**
   - Every invocation downloads the day's existing Parquet file from GCS, combines it with the newly captured snapshot, and runs `.drop_duplicates(subset=["snapshot_time_utc", "symbol"], keep="last")`.
   - Double triggers or retries by Cloud Scheduler never produce duplicate records.

2. **DuckDB Ingestion:**
   - Primary key is `(trade_date, symbol, snapshot_time_utc)`.
   - `insert_options_df()` executes `INSERT OR REPLACE INTO options_history (...)`.
   - Running `ingest_gcs_to_duckdb.py` multiple times for the same date or date range is 100% idempotent.

---

## 5. Backfill & Catch-Up

If the user's PC is turned off or offline for days (e.g. during a trip):
The Cloud Function continues recording in GCS without interruption. Once the PC is turned back on, run:
```powershell
python scripts/ingest_gcs_to_duckdb.py --date-range 2026-09-08:2026-09-12
```
This syncs all missed days into local DuckDB in seconds.

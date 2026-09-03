# 📼 Swayam Live Options Recorder (Cloud Function Gen2)

## Overview
This standalone service executes in Google Cloud (`asia-south1`) every 60 seconds from Monday to Friday between 09:15 and 15:30 IST.

It captures real-time NIFTY options chain snapshots across 80+ strikes, calculating Greeks and tracking Open Interest (OI) changes. The snapshots are appended to daily Parquet files in Google Cloud Storage at `gs://swayam-capital-options-data/{YYYY}/{MM}/{DD}/nifty_chain.parquet`.

## Architecture & Guarantees
- **Time Gating:** Non-trading hours and weekends exit immediately as idempotent HTTP 200 no-ops.
- **Strict Deduplication:** Appending to GCS deduplicates by `(snapshot_time_utc, symbol)` keeping the latest record. Cloud Scheduler double-fires or clock skews never create duplicate rows.
- **Security:** Zero credentials stored on disk; authentication token is retrieved on-demand from Google Secret Manager (`fyers-access-token`).
- **Cost:** Uses Google Cloud Functions Gen2 free tier (60 calls/day × 22 days = ~1,320 invocations/month, ₹0 cost).

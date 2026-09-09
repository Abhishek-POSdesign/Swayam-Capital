# Swayam Live Options Recorder (Cloud Function Gen2)

## What it does

A standalone service in Google Cloud (`asia-south1`), triggered by Cloud
Scheduler every 60 seconds, Monday to Friday, between 09:15 and 15:30 IST. It
takes a snapshot of the NIFTY option chain and appends it to a daily Parquet
file at `gs://swayam-capital-options-data/{YYYY}/{MM}/{DD}/nifty_chain.parquet`,
with a copy at the flat path `{YYYY-MM-DD}/nifty_chain.parquet`.

It exists to accumulate the intraday history a backtester needs, from now
forward, because historical NIFTY options data cannot be bought back from
FYERS. See `docs/PLAN.md` §2.15.

**Two expiries every snapshot:** the nearest expiry and the nearest monthly
expiry after it. One expiry cannot value a calendar spread, and ten of his
twenty-one historical swing trades were calendars. If the far expiry fetch
fails, the near one is still written and the failure is logged.

## What is in each row, and where it comes from

| Column | Source | Notes |
|---|---|---|
| `close`, `bid`, `ask` | FYERS, real | `close` is the last traded price |
| `volume`, `open_interest` | FYERS, real | |
| `change_in_oi`, `prev_oi` | FYERS, real | `oich` and `prev_oi` in the reply |
| `underlying_spot` | FYERS, real | The chain's underlying row, the one with an empty `option_type` and a strike of -1. There is no `underlyingValue` field |
| `expiry_date` | FYERS `expiryData`, real | Cross-checked against the contract's own symbol; a row whose symbol disagrees is dropped, not filed under the wrong expiry |
| `tte_years` | Computed | Snapshot to 15:30 IST on the expiry day, in years. Not whole days |
| `iv` | Computed | Solved from `close` with `bs_math`, at the risk-free rate in `config.RISK_FREE_RATE` |
| `delta`, `gamma`, `theta`, `vega` | Computed | From that `iv`. Per share, not per lot. `theta` per calendar day, `vega` per 1% of volatility |
| `open`, `high`, `low`, `settle_price`, `turnover_inr` | **Always NULL** | The FYERS option chain does not carry them. They are exactly the columns the free NSE end-of-day file does carry, and that is where they are meant to come from |

**Nothing is ever written as zero to mean unknown.** A missing value is NULL. A
zero open interest and an unknown open interest are different facts.

`iv` and the four Greeks are NULL when the price cannot support them: no traded
price, an expiry already past, or a contract so deep in the money that a single
tick of price would move the implied volatility by more than five volatility
points. On a live chain that is typically the in-the-money wing of the near
expiry and nothing else.

## What this corrects

Its first real day, 2026-09-09, produced 10,332 rows in which twelve columns
were zero in every row and `expiry_date` was wrong in every row: it said each
contract expired that afternoon, while the contract's own name said otherwise.

This README claimed at the time that the service "calculates Greeks and tracks
Open Interest changes". **It did not.** Both faults came from parsing a
response shape FYERS does not return (`call_ltp`, `put_oi`, `call_iv`,
`call_pdoi`) and from an expiry parser that was an empty shell returning today's
date. `tests/cloud/test_recorder_real_shape.py` now drives a reply captured from
the live API, so a claim like that one cannot pass its tests again.

## Guarantees

- **Time gating.** Weekends, hours outside 09:15 to 15:30 IST, **and NSE trading
  holidays** exit immediately as HTTP 200 no-ops. The holiday list is a copy of
  the repository's `data/nse_holidays_2026.json`; a test fails if the two drift.
  If the calendar does not cover the current year it records anyway and logs a
  warning, because losing a real year in silence is the worse failure.
- **Deduplication.** Appending to GCS deduplicates on `(snapshot_time_utc,
  symbol)`, keeping the latest. A scheduler double-fire cannot double the rows.
- **The date is India's**, not the container's, so a run near midnight UTC
  cannot file a session under the wrong day.
- **Security.** No credentials on disk. The FYERS token is read from Secret
  Manager at request time with a 60-second cache, so a refreshed token is in use
  within a minute without a redeploy.
- **Cost.** Free tier. Two FYERS calls a minute, roughly 750 a day.

## Proving a change without waiting for the morning

The service only records between 09:15 and 15:30 IST, so out of hours a
deployment can be proved to start and nothing else. `?dry_run=1` fetches from
FYERS and computes everything, ignores the market-hours gate, and **writes
nothing**. It returns the row count, the NIFTY level it read, the expiries it
recorded, and how many rows came back with a real implied volatility.

```
gcloud functions call swayam-recorder --gen2 --region=asia-south1 --data '{}'
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$(gcloud functions describe swayam-recorder --gen2 --region=asia-south1 \
     --format='value(serviceConfig.uri)')?dry_run=1"
```

Cloud Scheduler POSTs with no query string and therefore never dry-runs.

## The known gap: the morning

On 2026-09-09 every call between 09:15 and 13:25 IST failed with `Please
provide valid token`. Recording began the minute the FYERS token was refreshed
by hand, and the day holds 126 minutes out of 375. Abhishek is asleep at 09:15,
so **as things stand the recorder captures only the afternoon**. Fixing it needs
the FYERS refresh-token flow, which needs his PIN in Secret Manager, which is
his decision. `docs/PLAN.md` §2.10 carries it.

## Deploying

```
.\.venv\Scripts\python.exe scripts\deploy_recorder.py
```

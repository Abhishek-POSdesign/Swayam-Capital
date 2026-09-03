# Swayam Capital REST API Reference

**Version:** 0.3.0  
**Base URL:** `http://localhost:8000`

The Swayam Capital API powers the options strategy builder, real-time risk gating against Obsidian Method rules, and paper trade execution with automated trade journal note creation.

---

## 1. System Health & Rules

### `GET /health`
Returns application status and semantic version.

- **Response:**
  ```json
  {
    "status": "ok",
    "version": "0.3.0"
  }
  ```

### `GET /api/rules`
Returns active Method rules dynamically parsed from Abhishek's Second Brain files (`Risk Management Rules.md`, `Operational Readiness Rules.md`, and `Personal Trading Brief.md`).

- **Query Parameters:**
  - `force_reload` (bool, default `false`): When `true`, invalidates disk cache and re-reads vault files immediately.
- **Response:**
  ```json
  {
    "per_trade_risk_pct": 0.01,
    "per_trade_risk_cap_inr": 8500.0,
    "rr_minimum": 2.0,
    "rr_target": 2.5,
    "daily_loss_cap_pct": 0.02,
    "daily_loss_cap_inr": 17000.0,
    "weekly_loss_cap_pct": 0.04,
    "weekly_loss_cap_inr": 34000.0,
    "blast_radius_pct": 0.03,
    "blast_radius_cap_inr": 25500.0,
    "overnight_hedge_cap_pct": 0.02,
    "overnight_hedge_cap_inr": 17000.0,
    "margin_base_min_inr": 800000.0,
    "margin_base_max_inr": 900000.0,
    "margin_base_default_inr": 850000.0,
    "sleep_no_trade_threshold_hours": 5.0,
    "alcohol_lockout_days": 90,
    "reentry_ramp": {...},
    "margin_base_inr": 850000.0
  }
  ```

---

## 2. Market Data

### `GET /api/nifty/spot`
Returns current NIFTY 50 index spot quote fetched from FYERS API v3 (cached for 3 seconds).

- **Response:**
  ```json
  {
    "spot": 24867.50,
    "as_of": "2026-09-04T14:23:15+00:00"
  }
  ```

### `GET /api/option-chain`
Returns option chain snapshot around ATM strikes (cached for 5 seconds).

- **Query Parameters:**
  - `expiry` (string, required): Expiration date (`YYYY-MM-DD`).
  - `strike_count` (int, default `20`): Number of strikes around ATM.

---

## 3. Strategy & Risk Engine

### `POST /api/strategy/preset`
Returns structured legs with strikes snapped to 50-point NIFTY interval granularity.

- **Query Parameters:**
  - `name`: `bear_put_spread`, `bull_call_spread`, `iron_condor`, `calendar_spread`
  - `expiry`: `YYYY-MM-DD`
  - `spot`: Current underlying price
  - `far_expiry`: Optional far expiry for calendar spread

### `POST /api/strategy/compute`
Computes 100-point dual payoff curves (T+0 today vs At-Expiry) and portfolio Greeks.

- **Request Body:**
  ```json
  {
    "strategy_name": "Bear Put Spread",
    "underlying": "NIFTY",
    "legs": [
      {
        "strike": 24850,
        "option_type": "PE",
        "direction": "buy",
        "quantity_lots": 1,
        "entry_premium": 150.0,
        "expiry_date": "2026-09-24",
        "lot_size": 75
      },
      {
        "strike": 24100,
        "option_type": "PE",
        "direction": "sell",
        "quantity_lots": 1,
        "entry_premium": 50.0,
        "expiry_date": "2026-09-24",
        "lot_size": 75
      }
    ],
    "current_spot": 24867.5,
    "iv_per_leg": {
      "default": 0.15
    }
  }
  ```

### `POST /api/strategy/validate`
Audits candidate setup against Method rules using `TolerantComparator` (2% tolerance buffer).

- **Response:**
  ```json
  {
    "passed": true,
    "checks": [
      {
        "rule": "per_trade_risk_cap",
        "verdict": "PASS",
        "actual_inr": 7500.0,
        "cap_inr": 8500.0,
        "tolerance_pct": 0.02,
        "note": "Max loss ₹7,500 vs cap ₹8,500 (1.0% + 2% tolerance)"
      },
      {
        "rule": "rr_minimum",
        "verdict": "PASS",
        "actual": 4.0,
        "floor": 2.0,
        "tolerance_pct": 0.02
      },
      {
        "rule": "no_single_leg",
        "verdict": "PASS",
        "actual": 2.0,
        "floor": 2.0
      },
      {
        "rule": "overnight_hedge_cap",
        "verdict": "PASS",
        "actual_inr": 7500.0,
        "cap_inr": 17000.0
      },
      {
        "rule": "hedged_structure",
        "verdict": "PASS"
      }
    ],
    "warnings": []
  }
  ```

---

## 4. Execution & Positions

### `POST /api/execute`
Executes trade in paper mode. Re-validates rules, logs to database, and creates companion Obsidian journal markdown note.

- **Request Body:** Same as `/api/strategy/compute` with `"mode": "paper"`.
- **Note:** `mode: "real"` returns `403 Forbidden` with explanation.
- **Response:**
  ```json
  {
    "position_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-04-trade01.md",
    "status": "opened"
  }
  ```

### `GET /api/positions`
Returns active open paper/live positions.

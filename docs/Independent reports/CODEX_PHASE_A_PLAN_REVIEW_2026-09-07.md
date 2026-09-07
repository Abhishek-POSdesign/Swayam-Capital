# Independent review: SWAYAM Phase-A Plan

**Reviewed document:** `G:\My Drive\Second Brain\00 - Developer Logs\SWAYAM_PHASE_A_PLAN_2026-09-07.md`  
**Date:** 2026-09-07  
**Scope:** Whether the proposed Phase-A plan is viable for the Home and Strategy Builder pages, and what must change before implementation.

## Verdict

**The plan is directionally good but not yet viable as a complete implementation plan.**

It correctly identifies several genuine defects and puts data honesty ahead of visual work. That is the right priority. However, it omits four release-blocking workstreams: compliant FYERS authentication, production streaming architecture, backup/restore proof, and explicit acceptance gates. If built exactly as written, it could make the screen look more alive without making paper trading demonstrably safer.

**Recommendation: approve the intent, not the plan as written.** Replace it with the revised sequence below. Real-money execution must remain permanently code-blocked throughout this work.

## What the plan gets right

| Proposal | Assessment |
|---|---|
| Remove fabricated rollover data and guessed expiries | Correct and necessary. Both are real defects in the current source. |
| Make readiness and safety reads fail closed | Correct and release-blocking. |
| Lock public access before handling persistent broker credentials | Correct order of work. |
| Keep paper trading as the trust gate | Correct. Paper records are not broker records and must remain clearly labelled. |
| Wire real data and expose honest gaps | Correct principle. “Unavailable” is safer than a substitute number. |
| Add stale-data treatment and browser-error tests | Necessary, but needs precise acceptance criteria. |
| Treat UI polish as secondary | Correct for the present state. |

## Critical changes required

### 1. Replace “automatic FYERS token refresh” with a compliant daily-auth design

Do not approve automatic continuous refresh as written. FYERS’ current guidance for API trading says that from April 2026 order-capable API use requires a registered app, a whitelisted static IP and daily 2FA; it specifically says continuous refresh-token sessions are not supported. The plan must instead define:

1. A daily user-authentication ritual, with visible “authenticated / expires / not authorised” terminal status.
2. A static egress IP design, only when and if real execution is contemplated.
3. A data-only fallback that does not pretend orders are possible.
4. A secret-storage and rotation design in GCP Secret Manager, with no browser exposure.

This does **not** block paper trading today, but it is a mandatory design constraint. See [FYERS retail-algo rules](https://support.fyers.in/portal/en/kb/articles/what-are-the-new-sebi-rules-for-retail-algo-trading-from-april-01-2026) and [FYERS app activation guidance](https://support.fyers.in/portal/en/kb/articles/how-do-i-activate-the-new-app-for-api-trading-after-april-1-2026).

### 2. Define the streaming architecture before promising a WebSocket build

The current browser WebSocket is idle, but simply calling its broadcast method is not enough. The deployed service runs two Gunicorn workers and can scale to three Cloud Run instances. Each process has separate memory, so an in-memory connection manager cannot reliably distribute one FYERS feed to every browser.

The design must explicitly choose:

1. One managed backend market-feed owner per account/session.
2. A shared event transport (for example, Pub/Sub or Redis) between the feed owner and web workers.
3. A quote state store with source timestamp, receive timestamp, sequence/version and market-session state.
4. Reconnect, broker-rate-limit, duplicate-tick and out-of-order-tick behaviour.
5. A browser degradation rule: retain last price, label it stale, disable *new paper entries*, but leave risk-reducing close/cancel actions available.

FYERS advises limiting a user to five WebSocket connections; a single-feed design is therefore also the safe operational choice. [FYERS WebSocket guidance](https://support.fyers.in/portal/en/kb/fyers-api-integrations/fyers-api/general).

### 3. Promote backup and recovery into Phase A

The plan fixes neither the false-success backup behaviour nor the non-restoring restore script. Both are current defects. Before paper trading continues, Phase A must:

1. Fail a backup job when its cloud upload or integrity verification fails.
2. Encrypt backups, record checksum, object version and completion timestamp.
3. Implement restore into an isolated test Supabase project or database.
4. Perform one complete restore drill and record row counts, journal attachments, AI memory and elapsed recovery time.
5. Put last-successful-backup age and last-restore-drill date in the terminal health view.

### 4. Make the kill switch server-side and specific

“A prominent Halt control” is too vague. A button that only hides UI is not a kill switch. Define it as a database-backed, audited global state enforced in every write endpoint.

It must state exactly what happens:

| Action | Halted state |
|---|---|
| New paper trade / strategy execution | Blocked at backend |
| AI-generated trade proposal | Labelled unavailable / no action |
| Data display | Continues, visibly stale if necessary |
| Position close / risk reduction | Allowed |
| Un-halt | Requires authenticated owner confirmation, reason and audit record |

### 5. Replace the “anti-fake regex test” with a data-quality contract

A CI rule searching for patterns such as `|| 123` will both miss dangerous fabrication and fail harmless formatting code. It is useful as a supplementary lint rule, not as the primary control.

Instead, every data response for Home and Strategy Builder should use a common contract:

`value`, `source`, `source_timestamp`, `received_timestamp`, `market_session`, `quality` (`LIVE`, `DELAYED`, `PREVIOUS_SESSION`, `CALCULATED`, `UNAVAILABLE`), and `reason`.

Then test at API and browser level that:

- unavailable sources never emit a numerical substitute;
- calculated fields name their inputs and formula version;
- previous-session data cannot claim LIVE;
- an expiry needed to create a strategy cannot be heuristic;
- paper execution rejects data with unacceptable quality.

### 6. Do not automatically replace the risk base with all FYERS funds

“Real capital from FYERS drives risk caps” needs a Method decision first. Broker funds can include collateral, unsettled balances, unrelated investment capital and margin already committed elsewhere. The rule needs a named **trading allocation**, a freshness rule, reconciliation with open positions, and a manual lock for the day. Show broker funds beside the approved risk base; do not silently overwrite it.

### 7. Add real paper-trading definitions

Paper trading must define whether an entry uses last traded price, bid/ask, midpoint, or a conservative simulated fill. It must record the selected policy, source timestamp, slippage and charges. Without this, paper results will overstate strategy quality and cannot earn the trust gate the plan promises.

### 8. Close the security design before Build 1 starts

The plan says “method TBD,” but authentication is the main Build-1 objective. The detailed plan must choose one method before code begins and include a proof that the direct Cloud Run URL cannot bypass it. It must also tighten CORS, revoke public invoker access, use least-privilege service accounts, avoid browser-held credentials, and reconcile the existing RLS-disabled Supabase design with its single-user security model.

### 9. Resolve Method-rule changes separately from engineering fixes

Items such as the GREEN throttle, percentage-display correction, sigma/absolute-max relation and overnight sigma are trading-method decisions. They cannot be bundled into a defect-fix release. Each needs a written rule, example scenarios, owner approval, versioned Method file and before/after test cases.

## Better delivery order

### Phase A0 — freeze, prove and design (first)

No new feature work. Capture the exact deployed commit, Cloud Run IAM, active secrets, Supabase schema, scheduler deployment, broker app mode, static-IP status and backup status. Create one factual runbook. This closes the current contradiction between documentation and live infrastructure.

**Exit gate:** a signed evidence sheet, not a narrative claim.

### Phase A1 — safety and ownership

1. Remove fake rollover and expiry guessing.
2. Make every safety dependency fail closed.
3. Implement the server-side halt state.
4. Make real execution impossible by backend policy and add regression tests.
5. Make the site private using the selected access design; remove public access and broad CORS.
6. Repair backup failure handling and complete a real restore drill.

**Exit gate:** clean build, clean test suite, browser E2E tests, security access proof, and successful restore evidence.

### Phase A2 — data truth contract

1. Implement common data-quality metadata for every Home/Strategy value.
2. Enforce source-specific freshness by market session rather than a universal two-second rule.
3. Add terminal health: broker auth, feed age, database, recorder, backup age and deployed commit.
4. Define the approved trading-allocation risk base and paper-fill policy.

**Exit gate:** intentional broker/data outage tests show “unavailable/stale,” never a number or enabled new entry.

### Phase A3 — resilient live data

1. Build the shared FYERS feed architecture first.
2. Stream only essential symbols initially: NIFTY spot, selected option legs and active paper positions.
3. Add controlled REST fallback, quota/circuit-breaker behaviour and explicit session-aware stale state.
4. Add FII/DII/breadth only after a named source, permitted usage, caching and failure policy are documented.

**Exit gate:** several market-hour observation sessions with recorded latency, reconnect and broker-outage tests. No paper entry may rely on stale/unknown data.

### Phase B — paper-trading maturity

Run paper trading with the documented fill policy, daily authentication status and reconciled data for a defined period. Review every mismatch between platform records and FYERS data. Only then revisit risk-method changes and future real-money architecture.

## Required acceptance criteria for every build

Each build should be rejected unless all are supplied:

1. A list of changed source files and migrations.
2. Automated test results with exact counts and no ignored browser console errors.
3. Desktop and mobile screenshots of Home and Strategy Builder.
4. A live market-hours proof for feed-related changes, or a clearly labelled off-hours proof.
5. A before/after table for every displayed number changed.
6. A rollback procedure and deployed commit identifier.
7. Updated runbook and handover folder.

## Decision for the offered plan

**Approve with changes.** Keep its “honest data first, paper remains paper” purpose and its first three repair targets. Do not start Build 2 or token automation until Phase A0 and A1 are complete. Replace the token-refresh promise, add resilient feed architecture, make recovery/security first-class, and define measurable release gates.

No application code was changed by this review.


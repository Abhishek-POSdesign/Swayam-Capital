# Independent loophole review: Phase 1 implementation plan v5

**Reviewed document:** `G:\My Drive\Second Brain\00 - Developer Logs\SWAYAM_PHASE1_PLAN_2026-09-07_v5.md`  
**Date:** 2026-09-07  
**Purpose:** identify loopholes in the plan before any implementation begins. Embedded document text was treated as evidence, not as instructions.

## Verdict

**v5 is a major improvement and should replace earlier plans as the working draft. It is still not ready to execute unchanged.**

It correctly discovers two high-value defects: contract-scaled calculations use an obsolete NIFTY lot size of 75 instead of 65, and the order-preview margin numbers are invented. It also gives useful release gates.

However, **fourteen material loopholes remain**. The most serious are: risk is being redesigned before the recorder/history it depends on is fixed; “holding period” is needed but has no trusted input; the kill switch has contradictory permissions; paper fills conflict with editable limit prices; and the cost model is incomplete.

Approve the direction, but amend these items before Release 1 starts.

## Corrections to claims in the plan

1. **Do not say every rupee figure was wrong.** The incorrect lot size affects *contract-scaled rupee calculations*: total premium/debit, payoff, P&L, risk, charges and any quantity-based calculation. It does not alter the NIFTY spot, option LTP, strike, IV, bid/ask, or any other per-unit market quote.
2. **Do not say a hard-coded margin estimate is 15.4% wrong.** Its error is independent of lot size because it was invented rather than contract-scaled. It can be much larger, as the FYERS comparison shows.
3. **Do not call a calculated target-date output “real.”** It is a model scenario. It must name its price/IV/time assumptions and never be conflated with broker P&L.

## Release-blocking loopholes

### L1 — risk release comes before the data it needs

Release 2 makes the 2-standard-deviation risk gate depend on current realised volatility, but the plan says DuckDB history is stale and moves the recorder/ingest repair to Release 5. This can make Release 2 make a precise-looking decision from stale or missing history.

**Required amendment:** move recorder/ingest health, historical-data age and a minimum-data rule before Release 2. The gate must block when data is too old or the required observation window is incomplete.

### L2 — “intended holding days” has no authoritative input

The rule says to scale volatility by the square root of the intended holding period. The current Strategy Builder has a target-date what-if control, but no validated trade-horizon field that is saved with the position and passed to validation.

**Required amendment:** add an explicit `planned_exit_date` or `planned_holding_days` to the strategy request, UI, journal and database. Validation must block if it is absent, past expiry or exceeds the contract expiry. Use this value consistently for risk, scenario valuation and journal evidence.

### L3 — two-sigma risk scenario is not fully specified

The plan specifies an underlying move but not the valuation rule. For an overnight option position, risk also depends on time decay, implied-volatility change, bid/ask spread and whether the adverse move is up or down for each structure. The current maths has IV defaults in some paths.

**Required amendment:** define one versioned risk scenario: target timestamp, adverse direction(s), price source, IV source/shift, bid/ask valuation rule and risk-free rate. No default IV or zero premium may enter the trade path. Display those assumptions beside the verdict.

### L4 — twenty sessions is too weak without a stability rule

Twenty observations meets a minimum coding threshold, not a robust risk-data standard. A recent event can distort it; missing sessions and stale records can falsely compress it.

**Required amendment:** retain the agreed 20-session primary window if desired, but add data-age, completeness, outlier and historical-gap checks. Display the sample period and use a defined fallback policy of **block**, not substitute volatility.

### L5 — the broker balance is not automatically usable risk capital

The locked decision includes pledged collateral and floats with broker funds. The plan itself notes zero clear cash. Broker funds can change intraday, include collateral with haircut, and include margin already committed to positions.

**Required amendment:** preserve the owner’s decision but define the risk denominator precisely: named FYERS fields, timestamp, collateral haircut, available margin, existing open-position exposure and a once-per-session snapshot rule. Show raw broker funds and approved risk capital separately. Do not silently change a live trade’s allowed risk when the balance changes.

### L6 — hedge validation needs explicit geometry, not a phrase

“Protective strike” is not enough for implementation. A put hedge must be below the short put; a call hedge must be above the short call; option type, underlying, expiry and quantity must match. Different-expiry structures need separate treatment.

**Required amendment:** define hedged structures by contract graph/net exposure, reject unmatched short quantity, and hide calendar/diagonal structures until their payoff and hedge rules are implemented correctly.

### L7 — the kill-switch design contradicts itself

R1.7 says the halt is enforced in every write endpoint, including position close, journal, notebook, readiness and AI messages. The same section says closing remains allowed. If implemented literally, it can block the action needed to reduce risk and prevent recordkeeping during an incident.

**Required amendment:** enforce the halt only on risk-increasing actions: new paper entry, new strategy execution, order replacement that increases risk and automated proposal actions. Explicitly permit close/reduce, journal, audit, notebook and incident communication. Test both allowed and blocked paths at the backend.

### L8 — editable limit prices conflict with the paper-fill policy

R3 says buys fill at ask and sells at bid, while the Strategy Builder intentionally supports editable limit prices. These are different policies. A user-entered limit should not be overwritten silently, nor should it create a flattering fill.

**Required amendment:** choose and visibly label one of these modes:

- **Market simulation:** fill buy at ask / sell at bid.
- **Limit simulation:** fill only when the limit is marketable; otherwise create a pending paper order and fill it later only when a recorded quote reaches it.

Store raw quote snapshot, spread, quote timestamps, requested order type and fill policy. Apply the same rules at exit; do not retain a separate LTP-based close path.

### L9 — the proposed charge model is incomplete

The plan correctly flags uncertainty, but it still proposes a fixed formula before the required sources are pinned. FYERS’ current public charges describe equity-options transaction charges as **0.03503% plus 0.009%**, include clearing-related charges, and list NSE options IPFT at ₹50 per crore. The plan currently omits those components and leaves stamp duty as a single generic rate. [FYERS charges](https://support.fyers.in/portal/en/kb/articles/what-are-the-brokerage-statutory-and-other-applicable-charges-at-fyers), [FYERS statutory charges](https://support.fyers.in/portal/en/kb/articles/what-are-the-statutory-charges-on-trades-at-fyers-stt-gst-sebi-turnover-fee-ipft-etc)

STT at 0.15% on option-sale premium is current from 1 April 2026; exercised options have a different taxable value. [NSE STT schedule](https://www.nseindia.com/static/products-services/equity-derivatives-securities-transaction-tax)

**Required amendment:** version charges by effective date and exchange, include CM/IPFT where applicable, define expiry/exercise handling, and accept a charge schedule only after one full broker contract note reconciles line by line. Never calculate historical journal charges using today’s rates.

### L10 — IAP plan is technically sound but operationally incomplete

Direct Cloud Run IAP is now supported, so the chosen direction is valid. But the first enablement may require Cloud Console OAuth/branding setup for a project without an organisation; the IAP service agent must have Cloud Run Invoker; and the selected user must be granted IAP access. `--iap` alone can lock out the owner or break future deployment/callback traffic. [Google Cloud IAP for Cloud Run](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)

**Required amendment:** add a runbook with pre-change backup/export, exact IAM bindings, owner-access verification, rollback, direct `run.app` verification, custom-domain verification and a test that the app still deploys after Cloud Build runs.

### L11 — database migrations are not yet a deployment mechanism

The existing `scripts/apply_migration.py` only validates and prints a migration; it does not execute SQL. v5 proposes new kill-switch/audit and paper-fill fields without defining how they are applied to Supabase or verified in production.

**Required amendment:** establish one migration deployment mechanism, a schema-version table, staging validation, production backup before migration, and a post-migration schema/assertion test. Do not add tables as source files without applying them safely.

### L12 — backups use the wrong ownership model unless identities are mapped first

The plan says to grant the application service account write access. The scheduled backup functions may run under a different runtime identity, and Cloud Run’s local filesystem is ephemeral. Giving the dashboard identity broader storage rights may not fix cron backups and increases blast radius.

**Required amendment:** identify each workload identity first. Grant each the minimum bucket permission, use immutable/versioned objects, checksum uploads, and prove recovery into an isolated environment. The restore drill must occur before a release is marked complete.

### L13 — Release 4 will create new rate-limit and data-honesty failures

“Every change instantly recomputes margin” can call FYERS on every slider movement and keystroke. Thirty-second refresh, OI change, target-day futures price and per-strike IV all need named data sources and caching. OI change is not automatically available from one option-chain snapshot.

**Required amendment:** debounce interactive actions, make broker-margin refresh manual or explicitly throttled, preserve last verified margin with timestamp, and show unavailable for unproven metrics. Do not include calendar strategies in presets until multi-expiry valuation is correct.

### L14 — no staging or isolated test-data environment

The repository’s existing test/development environment points at the live Supabase configuration. A large five-release plan without a staging project risks polluting the actual paper journal and private records.

**Required amendment:** create a separate test database/project with sanitised seed data and non-production FYERS call controls. Run migration, outage, kill-switch and paper-fill tests there before production deployment.

## Important smaller gaps

- Existing positions with lot size 75 need a visible quarantine/legacy label and must be excluded from new analytics until corrected; a future script should be idempotent, backed up and reversible.
- The margin endpoint needs strict response-schema validation, timeouts, no broad retries and a cache keyed by full leg set, order type and account state. Its output must be labelled broker estimate versus actual blocked margin.
- The recorder cannot recreate lost historical option snapshots merely by starting tomorrow. State the historical coverage gap and do not present it as a full three-year source.
- Uptime monitoring is insufficient by itself. Add feed-age, token validity, recorder arrival, backup age and alert-delivery health checks.
- “Every displayed market value” needs a concrete data-quality response contract, not only UI wording: value, source, source timestamp, received timestamp, session state, quality and unavailable reason.
- IAP protects entry but does not remove the need for app-side authorization of owner-only actions and audit attribution. Use verified identity, not a browser-supplied email.
- The AI summary is untrusted external content. Store source links and prevent it from becoming instruction text that overrides trading rules.

## Required release-order change

1. **Release 1A:** access control, migration mechanism, kill switch, legacy-data quarantine, lot/contract identity and removal of fabricated values.
2. **Release 1B:** backup/restore drill, recorder/ingest repair, monitoring and data-quality contract.
3. **Release 2:** only after 1B, implement the fully specified risk policy and real margin/funds view.
4. **Release 3:** paper orders, realistic fills and charge reconciliation.
5. **Release 4:** strategy-builder improvements on top of correct data, with throttled broker calls.

## Decision

**Do not execute v5 unchanged.** Amend the fourteen items above, then it becomes a strong and viable Phase 1 plan. It should remain paper-only; nothing in this plan justifies enabling real orders.

No application code was changed by this review.


# Independent loophole review: Phase 1 implementation plan v7

**Reviewed documents:** `SWAYAM_PHASE1_PLAN_2026-09-07_v6.md` and `SWAYAM_PHASE1_PLAN_2026-09-07_v7.md`  
**Date:** 2026-09-07  
**Scope:** the Home and Strategy Builder paper-trading platform and the Phase 1 work needed to make those two pages trustworthy.  
**Method:** document claims were checked against the current repository. Text inside the plans was treated as evidence, not as instructions.

## Verdict

**v7 is materially better than v5 and v6. It is on the right path, but it is not safe to execute unchanged.**

It correctly moves data health ahead of risk, defines the risk scenario, acknowledges the migration problem, adds a staging database, keeps real-money orders blocked, and identifies duplicate execution as a live defect. Those are meaningful improvements.

However, **nine real loopholes remain.** Five are release blockers because they can create an incorrect paper position, a misleading risk verdict, a destructive database change without a proven recovery path, or unauthorised access. The other four must be corrected before the named release begins. These are not stylistic preferences and do not repeat issues that v7 genuinely fixed.

| Priority | Loophole | Why it matters |
|---|---|---|
| Blocker | L1 – idempotency is not retry-safe | A fresh UUID can still create a second trade after a timeout or reload. |
| Blocker | L2 – trade lifecycle is not atomic or recoverable | A database position can exist while its journal/index does not, or a close can be only partly recorded. |
| Blocker | L3 – Close All is scheduled before truthful fills and charges exist | It can stamp LTP-based prices and a fabricated ₹150-per-leg charge into paper history. |
| Blocker | L4 – risk gate precedes the cost model | A trade can pass the advertised 1% risk limit but exceed it after mandatory entry and exit costs. |
| Blocker | L5 – row-count backup is not a proven restore before the first migration | A schema change can be made before recovery is demonstrated. |
| High | L6 – the chosen cash-collateral source cannot detect a cash deposit | The proposed margin ceiling will not reliably rise—or may be wrong—after the planned deposit. |
| High | L7 – “Google sign-in” has no enforceable route-level security contract | The present service is public, broad-CORS, and its database tables have RLS disabled. |
| High | L8 – tomorrow’s duplicate test writes to production before staging exists | It intentionally creates duplicate paper records in the live journal/database without isolation or cleanup. |
| High | L9 – the plan permits paper entries during unfinished safety releases | The existing execution endpoint remains live while risk, margin, fills and charges are still incomplete. |

## What v7 has genuinely fixed

The following earlier issues should **not** be carried forward as open findings: data repair now comes before the risk release; the target exit date and the two-sided, time-aware risk scenario are defined; calendar/diagonal execution is blocked until multi-expiry valuation arrives; a live-schema baseline is required; a staging database is planned; the artificial 75-lot legacy data is quarantined; and the plan no longer proposes automatic real-money liquidation. These are improvements, not loopholes.

## Release-blocking loopholes

### L1 — the idempotency key would not safely survive a retry

v7 says the browser generates a UUID “per execution attempt,” and the database makes that UUID unique. This prevents an ordinary double-click only if the same UUID reaches the server both times. A timeout after the server commits, a browser reload, or a second submission commonly creates a **new** UUID. The server would see a new request and insert another position.

The current route makes this risk concrete: it creates a new `position_id` for every call and has no idempotency field or duplicate check. Both `/api/execute` and `/api/execute/multi-leg` reach that path. The latter must not become a loophole around the former.

**Required amendment:**

1. Create an execution-attempt record before the position with a client key that is persisted in the browser until a final answer is received.
2. Store a canonical payload hash with the key. The same key plus a changed payload must be rejected, not replayed.
3. Make the server return the original complete result for a repeat at any time appropriate for its retention policy—not merely “within 60 seconds.”
4. Cover direct calls to both execution URLs, including “server commits, response is lost, client retries.”
5. Use a database uniqueness constraint and a transaction/procedure; a front-end disabled button is only a convenience layer.

**Acceptance proof:** an automated test sends the same persisted key twice after simulating a lost response, then verifies exactly one position, one journal intent and one notification event.

### L2 — the position, history and journal can still disagree

The existing code explicitly inserts `swayam_positions` first, writes a local Markdown journal second, then inserts the journal-index row. If either later step fails, it returns HTTP 500 **after** creating the position. The close flow has the equivalent problem: it inserts trade history, then changes the position to closed, then appends the journal. Its own test expects the “closed in DB, journal failed” state.

v7 adds duplicate prevention but does not define a transaction, outbox, repair worker or reconciliation process for these known partial states. “Database before journal” is safer than a missing database row, but it is not atomic. A one-click Close All would multiply the same fault across several positions.

**Required amendment:**

1. Make the database the authoritative transaction boundary. Persist position state, execution attempt, trade-history intent and an outbox/journal task in one transaction or stored procedure.
2. Generate the Markdown journal after commit from the outbox. It must be retryable and idempotent.
3. Display an explicit `pending_journal` or `reconciliation_required` state; do not report a fully opened/closed trade when the audit record is incomplete.
4. Make Close All a batch with a deterministic per-position outcome and retry key; do not claim all closed if only some close operations commit.
5. Add a reconciliation job and an operator screen/report before paper execution is reopened.

**Acceptance proof:** forced failures after each step leave no ambiguous state: either the database transaction is absent, or a visible, replayable outbox record restores the journal without duplicating P&L/history.

### L3 — one-click Close All is being placed before the truthful pricing layer

v7 puts Close All in Release 1A but puts the quoted fill policy and versioned charge schedule in Release 3. Today, a close without supplied exit legs takes option **LTP**, not bid/ask, and calculates charges as `number of legs × ESTIMATED_CHARGE_PER_LEG_INR` (default ₹150). That is neither the promised limit/market simulation nor the promised real cost model.

Consequently Release 1A could create irreversible paper-history rows that look like an emergency close but are valued by known placeholder rules. The plan says Close All will show prices and charges, which makes the discrepancy more misleading, not less.

**Required amendment:** either move functional Close All to Release 3, or implement its price source, stale-quote block, conservative bid/ask logic, quote snapshot, Decimal calculation, and versioned costs in Release 1A. A UI-only button is not an adequate substitute.

**Acceptance proof:** an outage, stale quote and wide-spread test each blocks Close All; a successful close stores the requested mode, per-leg quote, bid/ask/LTP source, timestamps, pricing policy and charge-schedule version.

### L4 — the 1% risk promise excludes costs until the next release

Release 2 is where the plan enforces the 2-sigma loss cap of 1% of approved risk capital. Release 3 is where it calculates the entry and exit costs that a real paper trade must include. The loss gate therefore has no stated way to reserve both sides’ unavoidable charges.

This is a direct business-rule conflict, not a modelling preference. A position with price loss just below ₹8,710 can pass the Release 2 rule and still lose more than ₹8,710 after entry and exit taxes, transaction charges, clearing charges and IPFT.

**Required amendment:** bring the audited cost schedule needed for the risk calculation into Release 2, or reserve a conservative, documented maximum round-trip cost in the risk gate and replace it only after Release 3 reconciliation. The final risk evidence must show `scenario price loss + round-trip costs = total risk used by the cap`.

**Acceptance proof:** a boundary test proves a strategy failing only once costs are added is blocked, and the displayed 1% figure agrees with the stored calculation.

### L5 — Release 0’s row-count backup is not recovery proof before migration

v7 requires a “full backup, verified by row count” in Release 0, but a real restore drill is scheduled for Release 1B. The migration runner and version table then change the live database in Release 1A. Row counts show only that some rows were exported; they do not prove that schema, constraints, indexes, sequence values, journal files, data types or a usable import procedure can recreate the service.

The current backup/restore implementation is already known not to provide a restore. v7’s ordering therefore lets the first live schema change happen before recovery has been proved.

**Required amendment:** before the first production migration, perform an isolated restore using the exact Release 0 backup into the new staging project. The inventory must define the backup scope: all database schema/data, migration state, journal files/attachments needed by the two pages, configuration needed to interpret them, checksums and immutable object versions. A row count is a secondary validation after the restore, not the proof itself.

**Acceptance proof:** a dated drill report shows a fresh isolated database can start, read Home and Strategy Builder data, and reconcile schema plus row counts with production. Only then may Release 1A migrate production.

## High-priority loopholes

### L6 — the cash-ceiling data source cannot perform the promised automatic deposit update

v7 says cash-equivalent collateral is derived by classifying instruments from `holdings()` because `funds()` has no cash/non-cash split. It then says the margin ceiling will rise automatically when a cash deposit is made. Those statements conflict: `holdings()` identifies securities such as LIQUIDBEES and SGB; it does not represent a cash balance deposited in the broker account. A classification list cannot classify a cash balance that the source does not return.

The consequence is practical: after the planned deposit, the system can keep rejecting valid paper trades because it cannot see the cash, or it can be changed manually without an auditable broker source.

**Required amendment:** define a verified source for the cash component (for example an authenticated FYERS collateral report/API field if available), its polling and timestamp rule, and its reconciliation to total/available broker margin. If no reliable machine-readable field exists, use an explicit owner-confirmed cash ledger with an evidence attachment, two-person-style review checklist even for a single owner, and an expiry/reconfirmation rule. Never call this automatic until the source has passed a deposit and withdrawal test.

### L7 — access control is named, not specified end to end

The plan says “Google sign-in with the full lockout-proof runbook” and “CORS narrowed,” but it does not say which identity service issues the token, how FastAPI verifies it, which user IDs are authorised, how every REST endpoint and `/ws/spot` is protected, or how service-role database access is constrained.

This is a real present exposure: the deployment file uses `--allow-unauthenticated`; the API currently accepts all origins with credentials; and current migrations explicitly disable Supabase Row Level Security. “Google sign-in” shown only in the browser would not protect direct API calls.

**Required amendment:** select one enforceable design and put it in the plan: Cloud Run IAP plus its IAM/owner-access/rollback proof, or server-verified identity tokens with an explicit allow-list. State that the public Cloud Run Invoker binding is removed, all state-changing and private read routes enforce identity server-side, the WebSocket is authenticated before connection, CORS has exact production origins, and the service-role key never reaches the browser. Add an unauthorised-access test suite.

### L8 — the proposed market test is allowed to pollute production

The 2026-09-08 test asks Claude to deliberately make a duplicate paper execution “to confirm the bug is real.” Staging is not created until Release 1A, after that test. The existing application writes paper positions and journals to the live database/vault. Therefore the test can create two production paper positions, two notifications and two journal entries. The plan gives no test flag, isolated account, cleanup procedure or immutable evidence rule.

**Required amendment:** do not intentionally duplicate a strategy in production. Reproduce it in staging once Release 1A exists, or use a dedicated, visibly labelled production test record with a server-side `test_run_id`, no notifications, no analytics/AI inclusion, and an approved archival—not deletion—procedure. Capture the fault-injection evidence without changing a real paper book.

### L9 — paper execution needs a release-wide lock until its dependencies are complete

The current `/api/execute` endpoint remains active in paper mode. v7 improves it in Release 1A, but correct risk/margin arrives in Release 2 and correct charges/fills in Release 3. Nothing in the plan says that new paper entry is disabled between deployments, so the user can produce new “paper results” through an unfinished and changing safety model.

**Required amendment:** introduce a server-side `paper_execution_enabled` release gate, defaulting to false during Release 0 through Release 3. It may be enabled only after the Release 3 evidence pack is accepted. Read-only strategy building and explicit test fixtures may remain available, but every real user-created paper entry must return a clear maintenance message. If the owner explicitly wants a short observation period, put it behind a separate labelled `observation_only` mode that cannot write positions.

## Minimum corrected sequence

1. **Release 0:** schema/data inventory; complete backup; isolated restore drill; establish staging. Keep user paper entry locked.
2. **Release 1A:** private access enforced at the network and API layers; migration runner; durable idempotency; transactional/outbox trade lifecycle; no functional Close All yet.
3. **Release 1B:** data-quality contract, recorder and monitoring. Test broker and data outages.
4. **Release 2:** contract identity, verified cash-component source, broker margin, risk scenario **including round-trip cost reservation**.
5. **Release 3:** versioned charges, fill/close policy, quote snapshots and then functional Close All. Run reconciliation and recovery tests. Only then unlock ordinary paper execution.
6. **Release 4:** Strategy Builder visual/what-if improvements, still subject to the same data and execution contracts.

## Decision

**Approve v7 as the direction, not as an implementation-ready plan.** Add the nine amendments above and keep paper execution locked until the data, risk, fill, cost and recovery gates have passed. At that point it becomes a credible plan for a professional-grade paper terminal; it still does not authorise real-money execution.

No application code, database, deployment, broker account or live paper position was changed by this review.

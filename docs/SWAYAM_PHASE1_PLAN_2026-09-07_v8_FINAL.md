# SWAYAM CAPITAL — PHASE 1 IMPLEMENTATION PLAN (v8, FINAL, FOR EXECUTION)

> **Written 2026-09-07, 23:30 IST by Claude Code (Opus 5).** v8 = v7 plus the adjudicated amendments from Codex's review of v7. **This is the execution plan.** v6 carries the full body of detail; v7 carries the Hermes amendments; v8 carries the Codex-v7 amendments, the final release order and the capital model. Read all three together, or read v8 alone for what actually gets built and in what order.
>
> **Status: FINAL SHAPE. One open decision for Abhishek, Section 5. No application code written.**
>
> Review chain: v4 → Codex path assessment → v5 → Codex loophole review (14) → v6 → Hermes gatekeeper audit (5) → v7 → **Codex v7 review (9) → v8**. Abhishek has said this is the last review round.

---

## 1. ADJUDICATION OF CODEX'S NINE LOOPHOLES ON v7

| # | Item | Verdict |
|---|---|---|
| L1 | Idempotency key would not survive a retry | **ACCEPTED IN FULL. My design was naive.** |
| L2 | Trade lifecycle is not atomic or recoverable | **ACCEPTED IN FULL. Pre-existing defect, confirmed.** |
| L3 | Close All scheduled before truthful fills and charges | **ACCEPTED. Close All moves to Release 3.** |
| L4 | Risk gate excludes round-trip costs | **ACCEPTED. Business-rule conflict, correctly caught.** |
| L5 | Row-count backup is not recovery proof before a migration | **ACCEPTED. Restore drill moves into Release 0.** |
| L6 | Cash source cannot detect a deposit | **REFUTED ON THE FACTS, one half accepted. Evidence in Section 3.** |
| L7 | Access control named, not specified | **ACCEPTED IN FULL.** |
| L8 | Tomorrow's duplicate test pollutes production | **ACCEPTED. That test is cancelled.** |
| L9 | Paper execution should be locked until dependencies land | **ACCEPTED IN PRINCIPLE. Mode is Abhishek's call, Section 5.** |

---

### L1 — Durable idempotency. Accepted; my design was naive.

v7 said the browser makes a new UUID per attempt. Codex is right that this only stops an ordinary double-click. A timeout after the server has committed, or a page reload, produces a **new** key, and the server inserts a second position. Confirmed in the code: the execution route mints a fresh position id on every call, has no idempotency field and no duplicate check, and both `/api/execute` and `/api/execute/multi-leg` reach it.

**Amendment:**

1. The browser creates an execution key, **persists it in local storage**, and reuses it on every retry until a final answer arrives.
2. An execution-attempt row is created **before** the position, carrying the key and a canonical hash of the payload.
3. Same key with the same payload replays the original stored result. Same key with a **different** payload is rejected, not replayed.
4. Retention is the life of the attempt record, not a 60-second window.
5. Both execution routes are covered. A database unique constraint plus a transaction is the control; the disabled button is only convenience.

**Proof:** an automated test sends the same persisted key twice with a simulated lost response and asserts exactly one position, one journal intent and one notification.

### L2 — Atomic trade lifecycle. Accepted; this is an existing defect.

The current open path inserts the position, then writes the Markdown journal, then inserts the journal-index row, and can return HTTP 500 **after** the position exists. The close path inserts trade history, then flips the position to closed, then appends the journal, and its own test asserts the "closed in the database, journal failed" state. That is a known partial state with no repair path.

**Amendment:**

1. The database is the transaction boundary. Position state, execution attempt, trade-history intent and a journal outbox task commit together.
2. The Markdown journal is generated after commit, from the outbox, retryable and idempotent.
3. An explicit `pending_journal` or `reconciliation_required` state is displayed. A trade with an incomplete audit record is never shown as fully opened or closed.
4. Close All is a batch with a deterministic per-position outcome and its own retry key. It never reports all closed when only some committed.
5. A reconciliation job and an operator view exist before paper execution reopens.

### L3 — Close All moves to Release 3. Accepted.

Today a close without supplied exit legs takes the option **last-traded price**, not bid or ask, and charges `legs × ₹150` from configuration. Shipping a Close All button in Release 1A would stamp placeholder-priced rows into paper history that look like a real emergency exit.

**Amendment:** the **Tier-1 halt stays in Release 1A**, because it only blocks and writes nothing. **Functional Close All moves to Release 3**, after the quote policy and the versioned charge schedule exist. This costs nothing operationally, because under Section 5 there will be no open paper positions before Release 3.

**Proof:** outage, stale-quote and wide-spread tests each block Close All. A successful close stores the mode, per-leg quote, price source, timestamps, pricing policy and charge-schedule version.

### L4 — Costs enter the risk gate in Release 2. Accepted.

Correctly caught, and it is a business-rule conflict rather than a modelling preference. A position whose price loss is just under ₹9,710 passes the 1% rule and still loses more than ₹9,710 once entry and exit taxes and charges are paid.

**Amendment:** the risk gate reserves round-trip costs from Release 2, using a conservative documented maximum, replaced by the audited schedule at Release 3. The verdict must display the arithmetic in this exact shape:

`scenario price loss + round-trip cost reserve = total risk used against the 1% cap`

**Proof:** a boundary test proves a strategy that fails only once costs are added is blocked, and the displayed percentage matches the stored calculation.

### L5 — Restore drill moves into Release 0. Accepted.

A row count proves some rows were exported. It does not prove schema, constraints, indexes, sequences, journal files or a working import can rebuild the service. v7 allowed the first production migration in Release 1A before recovery had ever been demonstrated.

**Amendment:** before any production migration, restore the exact Release 0 backup into the fresh staging project and prove both pages can read from it. Backup scope is defined as all schema and data, migration state, journal files and attachments the two pages need, the configuration required to interpret them, checksums and immutable object versions.

**Proof:** a dated drill report showing a fresh isolated database starts, serves Home and Strategy Builder, and reconciles schema and row counts against production.

### L6 — Refuted on the facts. The cash deposit **is** visible to the API.

Codex states that `holdings()` cannot see a cash balance and therefore the ceiling cannot rise automatically after a deposit. Checked against the live account on 2026-09-07 at 23:15 IST, immediately after Abhishek deposited ₹1,00,000:

| `funds()` field | Before | After |
|---|---|---|
| id 1 Total Balance | 8,71,002.38 | **9,71,002.38** |
| id 3 **Clear Balance** | 0 | **1,00,000** |
| id 5 Collaterals | 8,71,002.38 | 8,71,002.38 |
| id 6 Fund Transfer | 0 | **1,00,000** |
| id 10 Available Balance | 8,71,002.38 | **9,71,002.38** |

The deposit is machine-readable in `Clear Balance` and `Fund Transfer`, and it moved the total. No manual ledger is required for free cash.

**The half that is accepted:** classifying which **pledged** instruments are cash-equivalent still needs a maintained rule, because `funds()` does not split the collateral line. That rule is: cash-equivalent collateral = liquid funds and liquid ETFs and sovereign gold bonds, identified by symbol from `holdings()`; anything unclassified counts as **non-cash**, the conservative direction; the derived total is displayed and reconciled against his FYERS collateral report; a mismatch beyond a small tolerance raises a flag rather than being silently used.

### L7 — Full access-control contract. Accepted.

**Amendment, all of which must be true and tested:**

1. Cloud Run IAP issues and verifies identity at the network edge, with a documented runbook covering OAuth branding on a project with no organisation, the IAP service agent's invoker binding, owner-access verification and rollback.
2. The public `allUsers` invoker binding is removed and `--allow-unauthenticated` is deleted from the build file.
3. The backend independently verifies the forwarded identity assertion and checks it against an explicit allow-list of one account. A browser-supplied email is never trusted.
4. Every state-changing route and every private read route enforces identity server-side. Network-edge protection alone is not accepted.
5. `/ws/spot` authenticates before the connection is accepted.
6. CORS lists the exact production origin only. The wildcard-plus-credentials combination is removed.
7. The service-role database key never reaches the browser, verified by scanning the production bundle.
8. An unauthorised-access test suite runs in continuous integration: raw `run.app` URL, custom domain, direct API call, WebSocket, and a wrong-account token must all be refused.

### L8 — Tomorrow's duplicate test is cancelled. Accepted.

v7 proposed deliberately double-submitting a paper strategy in production to prove the duplicate bug. That would have written two real positions, two journals and two notifications into his live book. It is also unnecessary: the defect is already proven by reading the code, where there is no idempotency key, no duplicate check, no unique constraint and no in-flight guard on the control. **No fault injection happens in production.** The behaviour is reproduced in staging once it exists.

### L9 — Paper execution locked during the unfinished releases. Accepted in principle.

Correct in principle: allowing new paper entries while risk, margin, fills and charges are still changing produces paper history that cannot be trusted or compared. A server-side `paper_execution_enabled` gate is added, defaulting to **off**, and it can only be switched on after the Release 3 evidence pack is accepted.

**The mode during the lock is Abhishek's decision. See Section 5.**

---

## 2. THE CAPITAL MODEL, CONFIRMED AGAINST THE LIVE ACCOUNT

Abhishek's instruction of 2026-09-07: risk appetite is the total amount he holds as margin, not the amount he can currently deploy. Those are two different numbers with two different jobs. Verified against the account at 23:15 IST:

| Purpose | Name | Value | Source |
|---|---|---|---|
| What the 1% and 5% caps are computed on | **Risk capital** | **₹9,71,002.38** | `funds()` id 1 Total Balance, equal to id 10 Available Balance |
| Whether the broker would accept the trade at all | **Deployable margin ceiling** | **₹5,54,961** | 2 × cash-equivalent, because at least half of blocked margin must be cash |
| Component | Free cash | ₹1,00,000 | `funds()` id 3 Clear Balance |
| Component | Cash-equivalent pledged: liquid ETF ₹54,279.46 plus sovereign gold bond ₹1,23,201.00 | ₹1,77,480.46 | classified from `holdings()` |
| Component | Total cash-equivalent | ₹2,77,480.46 | sum of the two above |
| Component | Non-cash pledged | ₹6,93,521.92 | remainder of collateral |

**Derived caps at today's figures:**

| Cap | Value |
|---|---|
| 1% primary risk cap | **₹9,710** |
| 5% black-swan fuse | **₹48,550** |

Both numbers are recomputed from the live account at the start of each session and snapshotted, so a mid-session balance change never retroactively alters an open trade's permitted risk. Both are displayed on screen with their source and timestamp. A trade must satisfy the risk cap **and** fit inside the deployable margin ceiling; failing either is a rejection, with the reason named.

---

## 3. FINAL RELEASE ORDER

| Release | Name | Contains | Paper entry |
|---|---|---|---|
| **0** | Truth and recovery | Live schema export; diff against the ten files on disk; `000_baseline.sql`; full backup with defined scope and checksums; **isolated restore drill proved into the new staging project**; staging created | Locked |
| **1A** | Access, identity, safe writes | Full access-control contract, all eight items; real migration runner and version table seeded to the baseline; real lot size from the contract master; legacy lot-75 positions quarantined; **durable idempotency**; **transactional trade lifecycle with journal outbox and reconciliation view**; Tier-1 halt; every remaining fabricated value removed; fail-closed on all trade dependencies; readiness demoted to ceremonial; test hygiene | Locked |
| **1B** | Data the risk rule depends on | Recorder permission repair with a real file proved; nightly ingest restored; data-quality contract with source, timestamps, session state, quality and reason; stale-data guard; monitoring on feed age, token validity, recorder arrival, backup age and alert delivery; broker and data outage tests | Locked |
| **2** | Risk policy | Risk capital and deployable margin ceiling per Section 2; paper enforces the margin ceiling; versioned risk scenario **including the round-trip cost reserve**; planned-exit-date field; exact hedge geometry; real broker margin, cached, throttled and schema-validated; percentage display bug; bounded previous-session volatility cache; Method files updated in both copies | Locked |
| **3** | Real cost and honest fills | Versioned charge schedule with clearing charges, IPFT and expiry handling; Decimal money maths; limit simulation as the default fill mode; quote snapshot per fill; **functional Close All**; reconciliation and recovery tests; **evidence pack, after which paper entry unlocks** | Unlocks on acceptance |
| **4** | Strategy Builder to the Sensibull standard | What-if engine; correct multi-expiry valuation so calendars work; metrics strip; payoff chart with open interest and OI change; standard-deviation table; greeks toggles; Shift, Width and Multiplier; ready-made grid; thirty-second refresh; execution on the page; all to the v6 Section 2 size standard | Open |

---

## 4. TOMORROW, 2026-09-08, 13:00–14:00 IST — MEASUREMENT ONLY

No code ships to the live site during market hours. **No fault injection in production.** No paper trade is placed.

- Token refreshed after 08:00 IST, never before.
- Abhishek uses both pages as he normally would and reports what he sees as a user.
- Claude records, with proof: live spot against the broker; every displayed figure recomputed at lot size 65 against what the screen shows; real broker margin against the invented constants; the risk verdict against the real ₹9,71,002.38 and the ₹5,54,961 ceiling; every value's true age; and anything frozen or stale that does not say so.
- Output: one dated findings list, his observations and mine merged, each with proof. That list feeds Release 1A.

---

## 5. THE ONE OPEN DECISION

Paper execution is gated off from Release 0 through Release 3. What Abhishek can do in the meantime is his call:

- **Option A, observation mode (recommended).** Build strategies, get real prices, see payoff, greeks, margin and the risk verdict. Execution returns a clear message saying the cost and fill engine is not yet honest. Nothing is written to his book. This matches his stated need to observe and judge this week, and keeps his journal clean.
- **Option B, provisional paper entries.** Execution stays available, every position written during this period is permanently flagged provisional, excluded from analytics and from the AI, and archived when the real engine lands. He gets to place trades now, at the cost of a journal containing rows priced by rules we already know are wrong.

**Recommendation: Option A.** His own words were that he wants to observe, judge and bring problems back. Observation mode delivers that completely and does not put known-bad rows into the record he is building his future on.

---

## 6. THE SEVEN PERMANENT CHECKS

From Release 1A onward these are automated and fail the build. They exist so that a problem found next week is a new problem.

1. No fabricated fallback in any data or trade path.
2. No hardcoded contract size, margin figure or charge rate.
3. Every safety control fails closed, proven by removing its dependency.
4. A browser console error fails the frontend suite.
5. Every displayed market value carries source and timestamp; an unavailable source renders as unavailable, never as a number.
6. Execution is idempotent across retries and reloads, not just double-clicks.
7. Real-money execution stays blocked.

---

*Nothing here is a claim of readiness. Real-money trading remains code-blocked. Written 2026-09-07 by Claude Code (Opus 5).*

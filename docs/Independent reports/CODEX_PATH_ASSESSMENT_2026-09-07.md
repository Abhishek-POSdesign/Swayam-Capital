# Swayam: Are we now on the right path?

**Date:** 2026-09-07  
**Evidence considered:** the Phase-A proposal, the Codex audit, the independent round-two audit, and the consolidated master audit. Documents were treated as evidence and claims, not as instructions.

## Straight answer

**We are no longer wandering in the dark. The diagnosis has converged. But we are not yet on a safe execution path.**

The project has identified the real class of problems: dishonest fallback data, fail-open controls, public access, unproven recovery, idle “live” feeds, and weak proof before claiming success. That is a major improvement over cosmetic bug fixing.

The remaining danger is organisational rather than visual: treating the master audit as a large backlog and trying to build Phase A and Phase B as broad feature sprints. That would recreate the same pattern — many changes, partial testing, contradictory notes, and new loopholes.

## What is now right

1. **The direction is correct.** Keep the existing system; do not rebuild. Its options maths, paper-trade flow, database, FYERS integration and Home/Strategy Builder foundation have real value.
2. **The priority is correct.** Data honesty, safety, access control and recovery must come before UI polish, AI features or real-money execution.
3. **The audits agree.** Independent reviews found the same core issues. This is no longer one agent’s opinion.
4. **Paper remains the gate.** That is the right discipline. It allows the terminal to earn trust with evidence.
5. **The scope is narrower.** Home and Strategy Builder are the correct two-page focus.

## Where the path still has loopholes

| Loophole | Why it matters | Correction |
|---|---|---|
| A defect list is being treated as an implementation plan | A list does not define ownership, interfaces, tests, rollback or proof. | Turn each release into a small, gated change with named acceptance evidence. |
| Phase B is too broad | Streaming, capital, risk policy, Decimal math, data lineage, AI governance and background jobs are separate programmes. | Split Phase B into data transport, risk policy, and paper-trading accounting. |
| Token “auto-refresh” remains in the consolidated plan | This conflicts with current FYERS guidance for daily 2FA and no continuous refresh session. | Replace it with a compliant daily authentication/session-status design. |
| “Use FYERS funds for risk caps” is underspecified | Broker funds are not automatically the capital assigned to this strategy. | Preserve an approved trading allocation; show broker funds separately. |
| WebSocket is described as wiring work | Cloud Run’s multiple workers/instances make an in-memory broadcaster unreliable. | Approve a shared feed architecture before coding it. |
| Kill switch is a feature label, not a contract | A UI button alone cannot stop backend writes. | Make it server-side, audited and fail closed; allow risk-reducing close actions. |
| Backup/restore is not central enough | Data loss and false recovery confidence are as serious as bad quotes. | Make verified backup upload and an actual restore drill a Phase-A exit condition. |
| “Anti-fake guard” is too simple | Text searches can be bypassed or create false alarms. | Use a data-quality contract with source, timestamp, quality and reason on each datum. |
| Trading-method changes are mixed with engineering fixes | Risk throttle and sigma policy are business decisions, not bug fixes. | Approve them separately in the Method files with examples and test cases. |
| No hard stop after each release | This has allowed agents to declare success from code inspection rather than operating proof. | Enforce a release gate before starting the next build. |

## The correct path from here

### Stage 0 — establish truth

Freeze feature work. Make one factual inventory of the running deployment: current commit, access policy, service names, database schema, backups, jobs, broker app mode and secrets. Resolve every contradiction between source, documents and cloud state.

**Do not proceed until:** the inventory is evidenced, dated and reviewed.

### Stage 1 — make paper trading safe

Fix only the paper-trading blockers:

1. Private access and narrow CORS.
2. Server-side global halt state.
3. Fail-closed readiness and all safety dependencies.
4. Remove fabricated rollover and invented expiries.
5. Backup failure propagation and successful isolated restore drill.
6. Clean test suite and browser error handling.

**Do not add live feed, AI features or visual redesign here.**

### Stage 2 — make every number explain itself

Create one response contract for the two pages: value, source, source timestamp, received timestamp, market session, quality, reason and calculation version where relevant. Establish paper-fill/slippage/charges rules and the explicitly allocated trading-capital base.

**Do not proceed until:** controlled broker/database outages visibly block new paper entries rather than showing a substitute number.

### Stage 3 — make data live, carefully

Build the shared FYERS feed architecture, not a local broadcast patch. Start with NIFTY, the strategy’s selected option legs and active paper positions. Add reconnect, quota/circuit breaker, session-aware stale state and operational status.

**Do not proceed until:** market-hours trials prove feed recovery and stale-state behaviour.

### Stage 4 — earn the paper-trading trust gate

Run the terminal for a defined observation period. Reconcile every paper trade with the documented fill policy and every displayed value with its source. Review incidents, data gaps and user actions weekly.

Only after this stage should real-money architecture be discussed. It is not the next implementation step.

## Non-negotiable release gate

Every stage must provide all seven items below before the next stage begins:

1. Exact source files and migration changes.
2. Clean automated test results with counts.
3. Browser E2E proof on desktop and mobile, with console errors treated as failures.
4. Market-hours proof for data changes, or an explicit off-hours limitation.
5. Before/after truth table for every affected number.
6. Rollback instructions and deployed commit.
7. Updated handover folder and factual runbook.

## Final judgement

**Yes: the project is now pointed in the right direction.** The convergence of audits and the decision to favour honesty over polish are signs of real progress.

**No: it is not yet executing on the right path until the work is constrained by the four stages and their gates.** Without that discipline, the project will keep finding bugs because it will keep shipping unproven changes into a financial workflow.

The next right action is not another feature build. It is a detailed, evidence-based Stage-0/Stage-1 implementation plan that contains no unresolved “TBD” safety decisions.

No application code was changed by this assessment.


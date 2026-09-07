# 🏁 SWAYAM CAPITAL — FINAL MASTER AUDIT & FIX PLAN (2026-09-07)

> **THE single source of truth.** Consolidates THREE independent audits — Claude, Codex (`CODEX_INDEPENDENT_AUDIT_2026-09-07.md`), and Hermes (`SWAYAM_ROUND2_AUDIT_20260907_112114.md`) — all verified against source by Claude. Plus data-source research and what professional traders actually use. This supersedes the earlier piecemeal Claude docs. **Start here to fix.**
>
> Responsibility for the defects is the AI's that built + "inspected" it (Gemini + Claude). Not deflected.

---

## 1. VERDICT (all three audits converge)
- **FIXABLE — do NOT rebuild.** Real spine: live FYERS data, real options math, real DB (10 migrations), rule engine, paper-execute+journal, ~400 tests, ~25k LOC. Rebuilding discards real value and, without a process change, reproduces the same defects.
- **NOT safe for real money; not yet a professional terminal.** Paper-only, and only after the Priority-0 items are fixed AND independently retested.
- Root cause = **process** (fixes claimed without live/independent proof, hardcoded fallbacks, fail-OPEN safety controls, public deploy, no anti-fake guard) — **not foundation**.

## 2. Which audit found what (honest reconciliation)
- **Claude found:** dead WebSocket + 10s poll; frozen dashboard; most fake fallbacks (removed PR#19/#20); RLS disabled; unreliable docs; undeployed infra; capital not wired from FYERS; risk-gate 0.3% readiness throttle; 62%↔0.62% display bug.
- **Codex added (Claude missed — safety/security/DR):** readiness gate **fails OPEN**; backup returns success on failure; **restore doesn't restore**; **rollover 68.5 still fake**; **`--allow-unauthenticated` + CORS `*`** (public, contradicts the IAP claim Claude wrongly repeated); expiry **invents Tuesdays**; hedge check trivial; order-preview margin hardcoded ₹32k/₹115k; nav error hidden in a passing test; 5.2 MB bundle; SW caches dev paths.
- **Hermes added (both missed):** **no global KILL SWITCH**; **float used for money math** (should be Decimal); **no UI stale-data banner** (quote >2s must flag STALE); **frontend P&L should read backend Decimal, not compute float**. *(Hermes "eval/sandbox" concern = non-issue: no `eval/exec` of AI strategies exists; only ops-script `subprocess`. Its "websocket/kill-switch/fake" greps were mostly noise.)*
- **Claude's extra round (all three missed):** **live position P&L is also dead** (`broadcast_position` defined, never called); **no app-level auth/login** — combined with the public deploy, anyone with the URL can hit paper-execute and read your data.

## 3. MASTER FINDINGS — prioritised (src: C=Claude, X=Codex, H=Hermes)

### 🔴 P0 — block further paper trading until fixed & retested
| # | Finding | Src |
|---|---|---|
| P0-1 | Readiness safety gate **fails OPEN** (`except: pass`) → make all safety-control failures **fail CLOSED**. | X |
| P0-2 | **No auth + public deploy** (`--allow-unauthenticated`, CORS `*`, RLS off) → anyone with the URL can use it. Lock down (IAP/auth), tighten CORS, review RLS. **Verify true posture — do NOT assume IAP.** | X+C |
| P0-3 | Backups **report success on upload failure**; **restore doesn't restore** → fail-fatal uploads + a real, drilled restore. | X |
| P0-4 | Last **fake numbers**: rollover `68.5`; **invented Tuesday expiries** on source failure → remove from trade paths. | X |
| P0-5 | **No global KILL SWITCH** (halt-all / flatten). Even paper: a prominent halt/close-all control. | H |
| P0-6 | **UI stale-data guard**: any quote older than ~2s must show **STALE**; on WS/feed drop, grey the terminal. | H |
| P0-7 | **Anti-fake guard test** in CI (fails on `\|\| <number>` fallbacks / hardcoded data / fail-open safety). Stops recurrence. | C |

### 🟠 P1 — before trusting it as a live dashboard / real-money design
| # | Finding | Src |
|---|---|---|
| P1-1 | **Dashboard frozen** (load-once + 15-min cache; spot WS idle; **position WS idle**). Wire FYERS WebSocket (spot + option legs + position P&L) or short-interval polling with a single lifecycle owner. | C+X |
| P1-2 | **Capital not from FYERS** → wire FYERS `funds()`; drive risk caps off real capital. | C |
| P1-3 | **Risk gate**: 0.3% throttle on GREEN day; 62%↔0.62% display bug; gates on absolute max loss vs your σ-only wish; overnight not modelled; **hedge validation trivial** (any sell leg). | C+X |
| P1-4 | **Money math uses float** → use `Decimal` server-side; frontend must **read backend P&L**, not recompute with float. | H |
| P1-5 | **Order-preview margin hardcoded** ₹32k/₹115k → real broker margin (FYERS) or "unavailable". | X |
| P1-6 | **No data lineage** (source/timestamp/session/error per field) → add a **terminal status strip** (token health, data age, DB, AI, recorder, backup age, release commit). | X |
| P1-7 | **AI gaps**: can't see So Far Today summary; context falls back to a generic prompt on failure; cost estimated from chars; no source citation/audit. | C+X |
| P1-8 | **FYERS reliability**: 429/401/403 in logs; no circuit breaker / quota monitor / token auto-refresh (undeployed). | X |

### 🟡 P2 — quality / trust
| # | Finding | Src |
|---|---|---|
| P2-1 | Docs unreliable (test counts, cloud resources). | C+X |
| P2-2 | Tests not clean: hidden `rule-panel.js` toFixed error in a "passing" nav test; stale option-chain double; temp-path env errors → browser errors must fail tests. | X |
| P2-3 | **5.2 MB JS bundle** (Plotly) → code-split/lazy-load. | X |
| P2-4 | Service worker precaches dev paths absent from prod build. | X |
| P2-5 | TTS pause restarts; So Far Today has no TTS. | C |
| P2-6 | Infra (notifications/macro/digest/backup crons) coded, **not deployed**. | C+X |
| P2-7 | Calendar-spread payoff approximate across two expiries. | C |

---

## 4. DATA-SOURCE RESEARCH — what we can get (API / DB / free / paid)

### ✅ FYERS (your broker — FREE to you, mostly UNWIRED) — this is the biggest unlock
FYERS API v3 provides, free to an account holder: **Funds/capital**, **Positions + live P&L**, Holdings, **Order book / place-modify-cancel orders** (Phase 2), Quotes, **Market depth**, **Option chain**, **Historical candles**, and **WebSockets** (market data, market depth, **Order socket**, **Position socket w/ live P&L**, Trade socket; up to 5,000 symbols). → Covers spot, SENSEX, Bank Nifty, VIX, chain, **your capital**, **live positions/P&L**, and true streaming. Most of this exists in the code only as an unused client method.

### 🟡 NSE (free, FRAGILE scrape — no official API)
FII/DII flows (EOD), advance/decline (breadth), bhavcopy. Via community libs (`nsefin`, `jugaad-data`) or Sensibull's free page. Cloudflare-gated, rate-limited — cache server-side, fail to "unavailable" honestly.

### 🔴 Paid pro-grade data vendors (exchange-certified, low-latency)
**TrueData** and **Global Datafeeds (GDFL)** — authorised NSE/BSE/MCX vendors: real-time WebSocket, option chain + Greeks, historical, ultra-low latency. This is what serious Indian algo/options desks pay for. (Monthly fee.)

### 🔴 Independent free (global/US) — rate-limited or ToS-gray
US indices (Dow/Nasdaq/S&P), Brent: **Alpha Vantage** (free key, ~25/day or 5/min — not truly live), FMP/Twelve Data (paid for real-time), Yahoo/Stooq (free, no key, ToS-gray). **GIFT Nifty:** no reliable free source.

## 5. What professional traders actually use (the "medium")
- **Retail pros:** their **broker's API + WebSocket** for streaming + execution — Zerodha **Kite Connect**, **FYERS API**, Upstox, Angel SmartAPI, Dhan — often *with* a data terminal (**Sensibull / Opstra / Quantsapp**) layered on the broker feed.
- **Serious/algo desks:** an **exchange-certified data vendor** (**TrueData / GDFL**) for market data + the **broker API** for execution — because broker APIs focus on execution while vendors specialise in certified low-latency data.
- **Swayam's correct path:** use the **FYERS WebSocket you already have** for live ticks + positions + capital (free), keep Swayam's unique layer (Method-rule gating, AI partner, journal) on top, and *optionally* add TrueData/GDFL later for pro-grade data. You do **not** need to abandon Swayam to get a live terminal — you need to wire FYERS properly.

## 6. Swayam vs professional terminal — the gap
Core (strategy builder, payoff, greeks, chain, PCR/OI) = present. Missing vs pro: entitled **streaming** + stale detection, broker **OMS** (acks/fills/cancel/idempotency/reconciliation), **fail-closed** real-margin risk + **kill switch**, per-field **data lineage** + alerting, verified **security/auth**, monitored **immutable backups + restore drills**, clean CI + browser E2E + market-hours smoke tests. Swayam's edge pros lack: **your Method-rule gating, AI partner + memory, readiness ritual, journal.**

## 7. FIX PLAN (phased — verify each against live data + show proof)
**Phase A — SAFE & HONEST (P0):** fail-closed safety controls; lock down auth/public exposure; backups fatal-on-failure + real restore drill; remove rollover + expiry guessing; add kill switch + stale-data banner; anti-fake guard test; fix hidden nav error + test hygiene.
**Phase B — LIVE & TRUE (P1):** FYERS WebSocket → live spot + legs + **positions/P&L**; **wire FYERS capital**; risk-gate fixes (throttle/display/σ-only/overnight/hedge); Decimal money math + frontend reads backend P&L; broker/"unavailable" margin; data-lineage + status strip; AI sees So Far Today + governed context; FYERS circuit breaker + token auto-refresh; deploy background jobs.
**Phase C — REAL-MONEY READINESS (future):** broker-paper env + weeks of market-hours acceptance; OMS state/fills/idempotency/kill switch/reconciliation; immutable audit + monitoring + DR; independent security review; written release gate signed with evidence.
**Process (throughout):** every fix verified against live data (independently where possible) and shown to Abhishek — never "I fixed it" without proof.

---
*Saved at: `docs/Independent reports/SWAYAM_FINAL_MASTER_AUDIT_2026-09-07.md` (repo) — mirror in vault `00 - Developer Logs/`. Sibling reports: `CODEX_INDEPENDENT_AUDIT_2026-09-07.md`, `SWAYAM_ROUND2_AUDIT_20260907_112114.md`.*
